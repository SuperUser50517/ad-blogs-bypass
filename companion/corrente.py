"""Percorre as trajetórias do encurtador até o destino final."""
import json
import re
import time
from datetime import datetime
from urllib.parse import urljoin, urlparse

_Q = r'\\?"'  # aspas, escapadas ou não
_REF = re.compile(r'createServerReference\)\("([0-9a-f]{40,})"[^)]*?"(\w+)"\)')
_CHUNK = re.compile(r'/_next/static/chunks/[\w.~-]+\.js')
_FRAME = re.compile('adFrameSrc' + _Q + ':' + _Q + r'/ad-frame/(content_\d)' + _Q
                    + r'[^{}]*?interactionGateEnabled' + _Q + r':(true|false)')
_CHAVE = re.compile('automaticGateKey' + _Q + ':' + _Q + r'([^"\\]+)')


class Parada(Exception):
    """Resposta inesperada: a corrente para aqui."""


def chunks(texto):
    return set(_CHUNK.findall(texto))


def mapa_actions(textos_js):
    return {nome: id_ for t in textos_js for id_, nome in _REF.findall(t)}


def ler_post(texto):
    """RSC de /post/{id} -> ({"content_1"|"content_2": interactionGateEnabled}, [gateKeys])."""
    frames = {f: g == "true" for f, g in _FRAME.findall(texto) if f != "content_0"}
    return frames, list(dict.fromkeys(_CHAVE.findall(texto)))


def resultado_action(texto):
    for linha in texto.splitlines():
        if linha.startswith("1:"):
            try:
                r = json.loads(linha[2:])
            except json.JSONDecodeError:
                return None
            return r if isinstance(r, dict) else None
    return None


MAX_TRAJETORIAS = 10
MAX_POSTS = 5
MAX_CONFIRM = 20


class Sessao:
    """Chamadas HTTP da corrente: para em qualquer resposta inesperada. Com `log` (arquivo aberto),
    registra cada chamada em JSON Lines; sem ele (o companion), não grava nada."""

    def __init__(self, req, log=None):
        self.req, self.log = req, log
        self.etapa, self.post = "", None
        self.mapas = {}  # host -> {nome da action: id}
        self._chunks_vistos = set()

    @property
    def onde(self):
        return self.etapa + (f" · post {self.post}" if self.post else "")

    def _registrar(self, metodo, url, status, resposta, action=None, corpo=None, url_final=None):
        if self.log is None:
            return
        linha = {
            "hora": datetime.now().isoformat(timespec="milliseconds"), "metodo": metodo, "url": url,
            "action": action, "corpo": corpo, "status": status, "resposta": resposta,
        }
        if url_final is not None:
            linha["url_final"] = url_final
        self.log.write(json.dumps(linha, ensure_ascii=False) + "\n")
        self.log.flush()

    def _parar(self, o_que, status, texto):
        raise Parada(f"{self.onde} · {o_que}\n{status} {texto[:1000]}")

    def get(self, url, rsc=False, headers=None):
        h = {"RSC": "1"} if rsc else {}
        h.update(headers or {})
        resp = self.req.get(url, headers=h)
        texto = resp.text()
        self._registrar("GET", url, resp.status, texto, url_final=resp.url)
        if not resp.ok:
            self._parar("GET " + url, resp.status, texto)
        self._carregar_chunks(resp.url, texto)
        return resp.url, texto

    def _carregar_chunks(self, base, texto):
        mapa = self.mapas.setdefault(urlparse(base).netloc, {})
        for caminho in sorted(chunks(texto)):
            url = urljoin(base, caminho)
            if url in self._chunks_vistos:
                continue
            self._chunks_vistos.add(url)
            resp = self.req.get(url)
            js = resp.text()
            self._registrar("GET", url, resp.status, f"<{len(js)} bytes>")
            if not resp.ok:
                self._parar("GET " + url, resp.status, js)
            mapa.update(mapa_actions([js]))

    def action(self, nome, url, args):
        host = urlparse(url).netloc
        id_ = self.mapas.get(host, {}).get(nome)
        if not id_:
            raise Parada(f"{self.onde} · action {nome} não encontrada nos chunks de {host}")
        corpo = json.dumps(args)
        resp = self.req.post(url, data=corpo, headers={
            "next-action": id_, "content-type": "text/plain;charset=UTF-8",
            "accept": "text/x-component", "origin": f"https://{host}", "referer": url,
        })
        texto = resp.text()
        self._registrar("POST", url, resp.status, texto, action=nome, corpo=corpo, url_final=resp.url)
        r = resultado_action(texto) if resp.ok else None
        if r is None or r.get("ok") is False or r.get("allowed") is False:
            self._parar(nome, resp.status, texto)
        return r

    def departure(self, frame_url):
        url = urljoin(frame_url, urlparse(frame_url).path.rstrip("/") + "/departure")
        resp = self.req.post(url, headers={"origin": f"https://{urlparse(url).netloc}", "referer": frame_url})
        self._registrar("POST", url, resp.status, resp.text(), url_final=resp.url)
        if not resp.ok:
            self._parar("departure", resp.status, resp.text())


def abrir_frame(s, base, nome, gate, post_url):
    q = "?interaction_gate=1&frame_instance=0&wp_post_id=1" if gate else "?wp_post_id=1"
    url, _ = s.get(urljoin(base, f"/ad-frame/{nome}{q}"), headers={
        "referer": post_url, "sec-fetch-dest": "iframe",
        "sec-fetch-mode": "navigate", "sec-fetch-site": "same-origin",
    })
    return url


def confirmar(s, nome, frame):
    for _ in range(MAX_CONFIRM):
        r = s.action(nome, frame, [])
        if r.get("unlocked"):
            return
        time.sleep(max(r.get("waitMs") or 0, 200) / 1000)
    raise Parada(f"{s.onde} · {nome} não liberou em {MAX_CONFIRM} tentativas")


def sair(s, base, gate, post_url):
    frame = abrir_frame(s, base, "content_2", gate, post_url)
    s.action("checkContentTwoFrameAction", frame, [{"interactionGateEnabled": gate}])
    if gate:
        s.departure(frame)
        s.action("checkContentTwoFrameAction", frame, [{"interactionGateEnabled": gate}])
        confirmar(s, "confirmContentTwoExternalReturnAction", frame)
    r = s.action("contentInterestAction", frame, [])
    if r.get("source") != "flow" or not r.get("destinationUrl"):
        raise Parada(f"{s.onde} · contentInterestAction sem destino de fluxo\n{json.dumps(r, ensure_ascii=False)}")
    return r


def trajetoria(s, url):
    """Percorre um blog e devolve a resposta da contentInterestAction."""
    s.post = None
    home, _ = s.get(url)
    post = s.action("getRecommendedPostAction", home, [])["post"]
    for _ in range(MAX_POSTS):
        pid = s.post = post["id"]
        post_url, rsc = s.get(urljoin(home, f"/post/{pid}?wp_post_id=1"), rsc=True)
        frames, chaves = ler_post(rsc)
        for chave in chaves:
            s.action("unlockAutomaticReadingAction", post_url,
                     [{"currentPostId": pid, "accessId": None, "gateKey": chave}])
        if "content_2" in frames:
            return sair(s, home, frames["content_2"], post_url)
        if "content_1" not in frames:
            raise Parada(f"{s.onde} · post sem content_1 nem content_2")
        frame = abrir_frame(s, home, "content_1", frames["content_1"], post_url)
        s.action("checkAdFrameViewAction", frame, [])
        if frames["content_1"]:
            s.departure(frame)
            confirmar(s, "confirmContentOneExternalReturnAction", frame)
        post = s.action("getNextRecommendedReadingPostAction", post_url,
                        [{"currentPostId": pid, "accessId": None}])["post"]
    raise Parada(f"{s.onde} · mais de {MAX_POSTS} posts nesta etapa")


def percorrer(s, url, progresso):
    """Repete trajetoria() até o contador mini chegar ao fim; devolve o destino final.
    progresso(b, a, host) é chamado a cada trajetória (o host do Native Messaging não pode usar o stdout)."""
    for n in range(1, MAX_TRAJETORIAS + 1):
        host = urlparse(url).netloc
        s.etapa = f"etapa {n} · {host}"
        r = trajetoria(s, url)
        mini = r.get("mini") or {}
        progresso(mini.get("b", n), mini.get("a", "?"), host)
        url = r["destinationUrl"]
        if mini.get("a") is not None and mini.get("a") == mini.get("b"):
            return url
    raise Parada(f"mais de {MAX_TRAJETORIAS} etapas sem chegar ao destino final")

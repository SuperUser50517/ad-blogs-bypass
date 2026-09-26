"""Testes offline do companion. Rodar: python tests\\test_companion.py"""
import base64
import hashlib
import json
import re
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / "companion"))

import corrente  # noqa: E402
from corrente import Parada, chunks, ler_post, mapa_actions, resultado_action, trajetoria  # noqa: E402

FIX = Path(__file__).resolve().parent / "fixtures"


def fixture(nome):
    return (FIX / nome).read_text(encoding="utf-8")


def test_mapa_actions_do_shufflepost():
    mapa = mapa_actions([fixture("shufflepost_chunks.js")])
    usadas = {
        "getRecommendedPostAction", "getNextRecommendedReadingPostAction",
        "unlockAutomaticReadingAction", "checkAdFrameViewAction",
        "confirmContentOneExternalReturnAction", "checkContentTwoFrameAction",
        "confirmContentTwoExternalReturnAction", "contentInterestAction",
    }
    assert usadas <= mapa.keys(), usadas - mapa.keys()
    assert mapa["contentInterestAction"] == "005168a1c299144f4285dd34533b70acd5b9a09fcc"


def test_post_com_clique_forcado():
    frames, chaves = ler_post(fixture("pinkbella_post38.rsc"))
    assert frames == {"content_2": True}
    assert chaves == ["content_0:block:1-1", "content_0:block:2-4"]


def test_post_sem_blocos():
    frames, chaves = ler_post(fixture("koaladesign_post25.rsc"))
    assert frames == {"content_2": False}
    assert chaves == []


def test_post_do_meio():
    frames, chaves = ler_post(fixture("shufflepost_post20.rsc"))
    assert frames == {"content_1": False}
    assert chaves == ["content_0:block:1-1", "content_0:block:2-2"]


def test_resultado_da_action_final():
    r = resultado_action(fixture("acao_final.txt"))
    assert r["destinationUrl"] == "https://t.me/+ConviteDeExemplo"
    assert r["mini"] == {"a": 6, "b": 6}
    assert resultado_action("0:{}\n") is None
    assert resultado_action("1:{nao-json\n") is None
    assert resultado_action('1:"$undefined"\n') is None


def test_rsc_do_post_cita_o_chunk_das_actions_de_leitura():
    assert "/_next/static/chunks/0nfrzcknk_r-y.js" in chunks(fixture("shufflepost_post20.rsc"))


class SessaoFalsa:
    """Mesma interface da Sessao, com respostas prontas e sem rede."""

    def __init__(self, posts, respostas):
        self.posts = posts  # id do post -> texto RSC
        self.respostas = {nome: list(v) for nome, v in respostas.items()}
        self.chamadas = []
        self.referers_frame = []  # referer de cada GET de /ad-frame/
        self.etapa, self.post = "teste", None

    @property
    def onde(self):
        return f"{self.etapa} · post {self.post}"

    def get(self, url, rsc=False, headers=None):
        self.chamadas.append("GET " + url.split("?")[0].split("/", 3)[3])
        if "/ad-frame/" in url:
            self.referers_frame.append((headers or {}).get("referer"))
        if "/post/" in url:
            return url, self.posts[int(url.split("/post/")[1].split("?")[0])]
        return url, ""

    def action(self, nome, url, args):
        self.chamadas.append(nome)
        return self.respostas[nome].pop(0)

    def departure(self, frame_url):
        self.chamadas.append("departure")


FIM = {"ok": True, "destinationUrl": "https://proximo.blog/?ad_id=1", "source": "flow", "mini": {"a": 6, "b": 2}}


def test_trajetoria_sem_clique_forcado():
    s = SessaoFalsa(
        {20: fixture("shufflepost_post20.rsc"), 38: fixture("shufflepost_post38.rsc")},
        {
            "getRecommendedPostAction": [{"ok": True, "post": {"id": 20}}],
            "unlockAutomaticReadingAction": [{"ok": True}] * 4,
            "checkAdFrameViewAction": [{"allowed": True, "delayMs": 5000}],
            "getNextRecommendedReadingPostAction": [{"ok": True, "post": {"id": 38}}],
            "checkContentTwoFrameAction": [{"allowed": True}],
            "contentInterestAction": [FIM],
        },
    )
    assert trajetoria(s, "https://shufflepost.com/?ad_id=1") == FIM
    assert s.chamadas == [
        "GET ", "getRecommendedPostAction",
        "GET post/20", "unlockAutomaticReadingAction", "unlockAutomaticReadingAction",
        "GET ad-frame/content_1", "checkAdFrameViewAction", "getNextRecommendedReadingPostAction",
        "GET post/38", "unlockAutomaticReadingAction", "unlockAutomaticReadingAction",
        "GET ad-frame/content_2", "checkContentTwoFrameAction", "contentInterestAction",
    ], s.chamadas
    assert s.referers_frame == [
        "https://shufflepost.com/post/20?wp_post_id=1", "https://shufflepost.com/post/38?wp_post_id=1",
    ], s.referers_frame


def test_trajetoria_com_clique_forcado():
    s = SessaoFalsa(
        {38: fixture("pinkbella_post38.rsc")},
        {
            "getRecommendedPostAction": [{"ok": True, "post": {"id": 38}}],
            "unlockAutomaticReadingAction": [{"ok": True}] * 2,
            "checkContentTwoFrameAction": [{"allowed": True}, {"allowed": True, "pendingExternalReturn": True}],
            "confirmContentTwoExternalReturnAction": [
                {"ok": True, "unlocked": False, "waitMs": 19},
                {"ok": True, "unlocked": True, "waitMs": 0},
            ],
            "contentInterestAction": [FIM],
        },
    )
    assert trajetoria(s, "https://app.pinkbella.com.br/?ad_id=1") == FIM
    assert s.chamadas == [
        "GET ", "getRecommendedPostAction",
        "GET post/38", "unlockAutomaticReadingAction", "unlockAutomaticReadingAction",
        "GET ad-frame/content_2", "checkContentTwoFrameAction", "departure",
        "checkContentTwoFrameAction",
        "confirmContentTwoExternalReturnAction", "confirmContentTwoExternalReturnAction",
        "contentInterestAction",
    ], s.chamadas
    assert s.referers_frame == ["https://app.pinkbella.com.br/post/38?wp_post_id=1"], s.referers_frame


def test_mensagens_do_host_ida_e_volta():
    import io

    from host import escrever_mensagem, ler_mensagem

    canal = io.BytesIO()
    escrever_mensagem(canal, {"tipo": "erro", "texto": "etapa 4 · não validou"})
    canal.seek(0)
    assert ler_mensagem(canal) == {"tipo": "erro", "texto": "etapa 4 · não validou"}
    assert ler_mensagem(canal) is None  # entrada acabou


def test_host_responde_progresso_e_destino():
    import io

    from host import atender, escrever_mensagem, ler_mensagem

    def resolver(next_url, ua, progresso):
        assert (next_url, ua) == ("https://blog/?ad_id=1", "UA")
        progresso(1, 6, "a.blog")
        progresso(6, 6, "b.blog")
        return "https://t.me/+x"

    entrada, saida = io.BytesIO(), io.BytesIO()
    escrever_mensagem(entrada, {"nextUrl": "https://blog/?ad_id=1", "ua": "UA"})
    entrada.seek(0)
    atender(entrada, saida, resolver)
    saida.seek(0)
    assert ler_mensagem(saida) == {"tipo": "progresso", "b": 1, "a": 6, "host": "a.blog"}
    assert ler_mensagem(saida) == {"tipo": "progresso", "b": 6, "a": 6, "host": "b.blog"}
    assert ler_mensagem(saida) == {"tipo": "destino", "url": "https://t.me/+x"}
    assert ler_mensagem(saida) is None


def test_host_responde_erro_localizado():
    import io

    from host import atender, escrever_mensagem, ler_mensagem

    def resolver(next_url, ua, progresso):
        raise Parada("etapa 2 · shufflepost.com · post 20 · unlockAutomaticReadingAction")

    entrada, saida = io.BytesIO(), io.BytesIO()
    escrever_mensagem(entrada, {"nextUrl": "https://blog/?ad_id=1", "ua": "UA"})
    entrada.seek(0)
    atender(entrada, saida, resolver)
    saida.seek(0)
    assert ler_mensagem(saida) == {
        "tipo": "erro", "texto": "etapa 2 · shufflepost.com · post 20 · unlockAutomaticReadingAction",
        "definitivo": False,
    }


def test_host_avisa_erro_definitivo():
    import io

    from host import atender, escrever_mensagem, ler_mensagem

    def resolver(next_url, ua, progresso):
        raise Parada("etapa 1 · blog · já foi", definitivo=True)

    entrada, saida = io.BytesIO(), io.BytesIO()
    escrever_mensagem(entrada, {"nextUrl": "https://blog/?ad_id=1", "ua": "UA"})
    entrada.seek(0)
    atender(entrada, saida, resolver)
    saida.seek(0)
    assert ler_mensagem(saida) == {"tipo": "erro", "texto": "etapa 1 · blog · já foi", "definitivo": True}


def servidor_local():
    """Servidor HTTP em 127.0.0.1 numa thread: /entrar redireciona e grava um cookie, /eco devolve o que recebeu."""
    import threading
    from http.server import BaseHTTPRequestHandler, HTTPServer

    class Eco(BaseHTTPRequestHandler):
        def log_message(self, *a):
            pass

        def responder(self, status, corpo=b"", **extras):
            self.send_response(status)
            for k, v in extras.items():
                self.send_header(k.replace("_", "-"), v)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.send_header("Content-Length", str(len(corpo)))
            self.end_headers()
            self.wfile.write(corpo)

        def do_GET(self):
            if self.path == "/entrar":
                self.responder(302, Location="/depois", Set_Cookie="sessao=abc; Path=/")
            elif self.path == "/eco":
                self.responder(200, json.dumps({"cookie": self.headers.get("Cookie"),
                                                "ua": self.headers.get("User-Agent")}).encode("utf-8"))
            else:
                self.responder(404, "não há".encode("utf-8"))

        def do_POST(self):
            corpo = self.rfile.read(int(self.headers["Content-Length"]))
            self.responder(200, json.dumps({"corpo": corpo.decode("utf-8"),
                                            "action": self.headers.get("next-action")}).encode("utf-8"))

    srv = HTTPServer(("127.0.0.1", 0), Eco)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv, f"http://127.0.0.1:{srv.server_port}"


def test_req_nao_segue_redirecionamento_e_guarda_cookie():
    """As duas coisas que o contexto do Playwright fazia sozinho: sem cookie o site responde
    "Sessão de acesso não encontrada"; seguir o 3xx pularia a checagem de rede local do corrente.py."""
    from host import Req

    srv, base = servidor_local()
    try:
        req = Req("UA-teste")
        r = req.get(base + "/entrar", max_redirects=0)
        assert (r.status, r.ok, r.headers.get("location")) == (302, False, "/depois"), (r.status, r.headers)
        assert r.url == base + "/entrar", r.url  # o corrente.py lê resp.url em action() e departure()
        eco = json.loads(req.get(base + "/eco", max_redirects=0).text())
        assert eco == {"cookie": "sessao=abc", "ua": "UA-teste"}, eco
        r = req.post(base + "/eco", max_redirects=0, data='["x"]', headers={"next-action": "id1"})
        assert r.ok and json.loads(r.text()) == {"corpo": '["x"]', "action": "id1"}, r.text()
        assert r.url == base + "/eco", r.url
        r = req.get(base + "/nada", max_redirects=0)
        assert (r.status, r.ok, r.text()) == (404, False, "não há"), (r.status, r.text())
    finally:
        srv.shutdown()


def test_resumir_conexao_recusada():
    import socket

    from host import Req, resumir

    with socket.socket() as livre:  # porta que acabou de ficar livre: ninguém escuta nela
        livre.bind(("127.0.0.1", 0))
        porta = livre.getsockname()[1]
    try:
        Req("UA").get(f"http://127.0.0.1:{porta}/", max_redirects=0)
    except Exception as e:
        assert resumir(e) == "falha de rede: conexão recusada", resumir(e)
    else:
        raise AssertionError("deveria falhar")


def test_resumir_erros_de_rede():
    import socket
    import urllib.error

    from host import resumir

    assert resumir(urllib.error.URLError(socket.gaierror(11001, "getaddrinfo failed"))) \
        == "falha de rede: endereço não encontrado"
    assert resumir(TimeoutError("timed out")) == "falha de rede: tempo de resposta esgotado"
    assert resumir(ConnectionResetError(10054, "x")) == "falha de rede: conexão interrompida"


def test_resumir_erro_comum_mantem_tipo_e_primeira_linha():
    from host import resumir

    e = KeyError("post")
    assert resumir(e) == "KeyError: 'post'", resumir(e)
    e = ValueError("formato inesperado\nsegunda linha")
    assert resumir(e) == "ValueError: formato inesperado", resumir(e)


def test_percorrer_avisa_o_progresso():
    respostas = [{"destinationUrl": f"https://b{n}.blog/?ad_id=1", "mini": {"a": 3, "b": n}} for n in (1, 2, 3)]
    visitados, avisos = [], []

    def trajetoria_falsa(s, url):
        visitados.append(url)
        return respostas[len(visitados) - 1]

    original = corrente.trajetoria
    corrente.trajetoria = trajetoria_falsa
    try:
        s = SessaoFalsa({}, {})
        destino = corrente.percorrer(s, "https://b0.blog/?ad_id=1", lambda b, a, host: avisos.append((b, a, host)))
    finally:
        corrente.trajetoria = original
    assert destino == "https://b3.blog/?ad_id=1"
    assert avisos == [(1, 3, "b0.blog"), (2, 3, "b1.blog"), (3, 3, "b2.blog")], avisos


class RespFalsa:
    def __init__(self, url, status=200, location=None, texto=""):
        self.url, self.status, self.ok, self.texto = url, status, 200 <= status < 300, texto
        self.headers = {"location": location} if location else {}

    def text(self):
        return self.texto


class ReqFalsa:
    """APIRequestContext falso: registra cada URL pedida; responde 200 vazio ou o que estiver em `respostas`."""

    def __init__(self, respostas=None):
        self.respostas, self.pedidos = respostas or {}, []

    def get(self, url, **kw):
        assert kw.get("max_redirects") == 0, kw  # o redirecionamento é seguido à mão, para ser conferido
        self.pedidos.append(url)
        return self.respostas.get(url) or RespFalsa(url)

    post = get


DNS = {"blog.example": "93.184.216.34", "interno.example": "192.168.0.2", "localhost": "127.0.0.1"}


def com_dns_falso(f):
    """Roda f() com o getaddrinfo do corrente trocado pelo DNS acima (IP literal resolve para ele mesmo)."""
    def getaddrinfo(host, porta, *a, **k):
        if host == "sumiu.example":
            raise corrente.socket.gaierror("sem DNS")
        ip = DNS.get(host, host)
        familia = corrente.socket.AF_INET6 if ":" in ip else corrente.socket.AF_INET
        return [(familia, corrente.socket.SOCK_STREAM, 6, "", (ip, porta))]

    original = corrente.socket.getaddrinfo
    corrente.socket.getaddrinfo = getaddrinfo
    try:
        f()
    finally:
        corrente.socket.getaddrinfo = original


def bloqueado(s, url):
    try:
        s.get(url)
    except Parada as e:
        assert "bloqueado por segurança" in str(e), e
        return
    raise AssertionError(f"não bloqueou {url}")


def test_sessao_bloqueia_rede_local_sem_pedir():
    def f():
        for url in ["https://127.0.0.1/?ad_id=1", "https://192.168.0.2/?ad_id=1", "https://localhost/?ad_id=1",
                    "https://interno.example/?ad_id=1", "https://[::1]/?ad_id=1", "http://100.64.0.1/",
                    "file:///C:/Windows/win.ini"]:
            req = ReqFalsa()
            bloqueado(corrente.Sessao(req), url)
            assert req.pedidos == [], (url, req.pedidos)
    com_dns_falso(f)


def test_sessao_bloqueia_redirecionamento_para_rede_local():
    def f():
        req = ReqFalsa({"https://blog.example/": RespFalsa("https://blog.example/", 302, "http://192.168.0.2/admin")})
        bloqueado(corrente.Sessao(req), "https://blog.example/")
        assert req.pedidos == ["https://blog.example/"], req.pedidos
    com_dns_falso(f)


def test_sessao_segue_redirecionamento_publico():
    def f():
        req = ReqFalsa({"https://blog.example/": RespFalsa("https://blog.example/", 301, "/home")})
        url, _ = corrente.Sessao(req).get("https://blog.example/")
        assert url == "https://blog.example/home", url
        assert req.pedidos == ["https://blog.example/", "https://blog.example/home"], req.pedidos
    com_dns_falso(f)


def test_sessao_nao_segue_redirecionamento_de_post():
    def f():
        req = ReqFalsa({"https://blog.example/f/departure": RespFalsa("https://blog.example/f/departure", 302, "/x")})
        try:
            corrente.Sessao(req).departure("https://blog.example/f")
        except Parada:
            pass
        else:
            raise AssertionError("3xx de POST deveria parar")
        assert req.pedidos == ["https://blog.example/f/departure"], req.pedidos
    com_dns_falso(f)


def test_sessao_com_dns_que_falha_deixa_a_requisicao_dar_o_erro():
    def f():
        req = ReqFalsa()
        corrente.Sessao(req).get("https://sumiu.example/")
        assert req.pedidos == ["https://sumiu.example/"], req.pedidos
    com_dns_falso(f)


def recusa(corpo, status=200):
    """Parada que a Sessao levanta quando a getRecommendedPostAction responde `corpo`."""
    url = "https://blog.example/"
    resp = RespFalsa(url, status, texto=f'0:{{"a":"$@1"}}\n1:{corpo}' if status == 200 else corpo)
    s = corrente.Sessao(ReqFalsa({url: resp}))
    s.etapa = "etapa 1 · blog.example"
    s.mapas = {"blog.example": {"getRecommendedPostAction": "id1"}}
    erro = []

    def f():
        try:
            s.action("getRecommendedPostAction", url, [])
        except Parada as e:
            erro.append(e)
    com_dns_falso(f)
    assert erro, "deveria parar"
    return erro[0]


def test_recusa_de_fluxo_finalizado_vira_mensagem_amigavel_e_definitiva():
    e = recusa('{"ok":false,"message":"Este fluxo já foi finalizado.","href":"/"}')
    assert str(e) == ("etapa 1 · blog.example · Este link já foi resolvido até o fim. Para obter o destino de novo, "
                      "abra o link do encurtador e resolva o captcha outra vez."), str(e)
    assert e.definitivo


def test_recusa_de_sessao_perdida_vira_mensagem_amigavel_e_definitiva():
    e = recusa('{"ok":false,"message":"Sessão de acesso não encontrada. Recarregue a página.","href":"/"}')
    assert str(e) == ("etapa 1 · blog.example · A sessão deste link se perdeu. "
                      "Abra o link do encurtador e resolva o captcha outra vez."), str(e)
    assert e.definitivo


def test_recusa_desconhecida_mostra_o_texto_do_site_sem_json():
    e = recusa('{"ok":false,"message":"Algo novo aconteceu.","href":"/"}')
    assert str(e) == "etapa 1 · blog.example · Algo novo aconteceu.", str(e)
    assert not e.definitivo


def test_resposta_sem_message_mantem_o_detalhe_tecnico():
    e = recusa("<html>erro interno</html>", status=500)
    assert str(e).startswith("etapa 1 · blog.example · getRecommendedPostAction\n500 <html>"), str(e)
    assert not e.definitivo
    e = recusa('{"ok":false}')
    assert "getRecommendedPostAction" in str(e) and not e.definitivo, str(e)


def test_id_da_extensao_bate_com_o_instalador():
    """ID do Chromium: SHA-256 da chave pública (DER), 32 primeiros hex, com 0-f trocados por a-p."""
    chave = json.loads((RAIZ / "extension" / "manifest.json").read_text(encoding="utf-8"))["key"]
    digest = hashlib.sha256(base64.b64decode(chave)).hexdigest()[:32]
    ext_id = "".join(chr(ord("a") + int(c, 16)) for c in digest)
    assert ext_id == "gdffnebealemedjembikfbagoijgmeij", ext_id
    iss = (RAIZ / "installer" / "ad-blogs-bypass-companion.iss").read_text(encoding="utf-8-sig")
    m = re.search(r'^#define\s+ExtensionId\s+"([^"]*)"', iss, re.M)
    assert m and m.group(1) == ext_id, m and m.group(1)


if __name__ == "__main__":
    falhas = 0
    for nome, f in list(globals().items()):
        if nome.startswith("test_"):
            try:
                f()
            except Exception as e:
                falhas += 1
                print("FALHOU", nome, f"({type(e).__name__}: {e})")
            else:
                print("ok", nome)
    sys.exit(1 if falhas else 0)

"""Host do Native Messaging da extensão Ad Blogs Bypass.

Roda empacotado como snet-bypass-companion.exe (PyInstaller; ver companion/build.ps1). O Brave inicia
um processo por link capturado. Recebe {nextUrl, ua}, percorre as trajetórias e responde
{tipo: progresso|destino|erro}. Não grava arquivo nenhum: o erro vai só para o popup.
O stdout é exclusivo do protocolo: nada de print aqui.
"""
import json
import socket
import struct
import sys
import urllib.error
import urllib.request

from corrente import Parada, Sessao, percorrer

# ConnectionRefusedError antes de ConnectionError, de quem é subclasse.
_CAUSAS = ((ConnectionRefusedError, "conexão recusada"), (socket.gaierror, "endereço não encontrado"),
           (ConnectionError, "conexão interrompida"), (TimeoutError, "tempo de resposta esgotado"))


def resumir(e):
    """Erro de rede vira "falha de rede: <causa>"; o resto, tipo e primeira linha."""
    causa = e.reason if isinstance(e, urllib.error.URLError) else e  # o urlopen embrulha o erro de conexão
    for tipo, texto in _CAUSAS:
        if isinstance(causa, tipo):
            return f"falha de rede: {texto}"
    return f"{type(e).__name__}: {str(e).partition(chr(10))[0]}"


class _SemRedirecionar(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *a, **k):
        return None  # o 3xx volta como resposta: o corrente.py confere o destino antes de segui-lo


class Resposta:
    def __init__(self, status, headers, corpo, url):
        self.status, self.ok, self._corpo, self.url = status, 200 <= status < 300, corpo, url
        self.headers = {k.lower(): v for k, v in headers.items()}
        self._charset = headers.get_content_charset() or "utf-8"

    def text(self):
        return self._corpo.decode(self._charset, errors="replace")


class Req:
    """HTTP da corrente com a stdlib, no formato que o corrente.Sessao usa (get/post -> status, ok,
    headers, url, text()). Guarda cookies (sem eles o site responde "Sessão de acesso não encontrada") e
    nunca segue redirecionamento."""

    def __init__(self, ua):
        self.base = {"user-agent": ua or "Mozilla/5.0", "accept-language": "pt-BR,pt;q=0.9"}
        self._abrir = urllib.request.build_opener(_SemRedirecionar, urllib.request.HTTPCookieProcessor()).open

    def _pedir(self, metodo, url, headers=None, data=None, max_redirects=0):
        corpo = data.encode("utf-8") if isinstance(data, str) else data
        pedido = urllib.request.Request(url, data=corpo, headers={**self.base, **(headers or {})}, method=metodo)
        try:
            with self._abrir(pedido, timeout=30) as r:
                return Resposta(r.status, r.headers, r.read(), r.url)
        except urllib.error.HTTPError as e:  # 3xx, 4xx e 5xx também são respostas
            with e:
                return Resposta(e.code, e.headers, e.read(), url)

    def get(self, url, **kw):
        return self._pedir("GET", url, **kw)

    def post(self, url, **kw):
        return self._pedir("POST", url, **kw)


def ler_mensagem(entrada):
    """Uma mensagem: 4 bytes (uint32 little-endian) de tamanho + JSON UTF-8. None se a entrada acabou."""
    cabecalho = entrada.read(4)
    if len(cabecalho) < 4:
        return None
    (tamanho,) = struct.unpack("<I", cabecalho)
    return json.loads(entrada.read(tamanho).decode("utf-8"))


def escrever_mensagem(saida, dados):
    corpo = json.dumps(dados, ensure_ascii=False).encode("utf-8")
    saida.write(struct.pack("<I", len(corpo)))
    saida.write(corpo)
    saida.flush()


def atender(entrada, saida, resolver):
    """Lê um pedido, resolve e responde. Qualquer falha vira {tipo: "erro"} com o texto localizado."""
    pedido = ler_mensagem(entrada)
    if not pedido:
        return

    def progresso(b, a, host):
        escrever_mensagem(saida, {"tipo": "progresso", "b": b, "a": a, "host": host})

    try:
        url = resolver(pedido["nextUrl"], pedido.get("ua"), progresso)
        escrever_mensagem(saida, {"tipo": "destino", "url": url})
    except Parada as e:
        escrever_mensagem(saida, {"tipo": "erro", "texto": str(e), "definitivo": e.definitivo})
    except Exception as e:  # rede, timeout, formato inesperado: mesmo contrato do ERRO do terminal
        escrever_mensagem(saida, {"tipo": "erro", "texto": resumir(e)})


def resolver(next_url, ua, progresso):
    s = Sessao(Req(ua))
    try:
        return percorrer(s, next_url, progresso)
    except Parada:
        raise
    except Exception as e:  # acrescenta onde parou
        raise Parada(f"{s.onde} · {resumir(e)}") from e


def main():
    atender(sys.stdin.buffer, sys.stdout.buffer, resolver)


if __name__ == "__main__":
    main()

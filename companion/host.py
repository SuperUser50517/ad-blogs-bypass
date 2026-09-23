"""Host do Native Messaging da extensão Ad Blogs Bypass.

Roda empacotado como snet-bypass-companion.exe (PyInstaller; ver companion/build.ps1). O Brave inicia
um processo por link capturado. Recebe {nextUrl, ua}, percorre as trajetórias e responde
{tipo: progresso|destino|erro}. Não grava arquivo nenhum: o erro vai só para o popup.
O stdout é exclusivo do protocolo: nada de print aqui.
"""
import json
import re
import struct
import sys

from corrente import Parada, Sessao, percorrer

_CAUSAS = {"ECONNREFUSED": "conexão recusada", "ENOTFOUND": "endereço não encontrado",
           "EAI_AGAIN": "endereço não encontrado", "ECONNRESET": "conexão interrompida",
           "ETIMEDOUT": "tempo de conexão esgotado", "Timeout": "tempo de resposta esgotado",
           "timed out": "tempo de resposta esgotado"}


def resumir(e):
    """Sem o "Call log" do Playwright e sem o nome da API (vazio no exe congelado: "Error: : connect…")."""
    texto = str(e).split("Call log:")[0].strip()
    texto = re.sub(r"^[\w.]*:\s+", "", texto)  # "APIRequestContext.get: " ou ": "
    for chave, causa in _CAUSAS.items():
        if chave in texto:
            return f"falha de rede: {causa}"
    return f"{type(e).__name__}: {texto}"


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
        escrever_mensagem(saida, {"tipo": "erro", "texto": str(e)})
    except Exception as e:  # rede, timeout, formato inesperado: mesmo contrato do ERRO do terminal
        escrever_mensagem(saida, {"tipo": "erro", "texto": resumir(e)})


def main():
    # Falha antes do atender (Playwright ausente no pacote…) também responde; sem isso a extensão só
    # veria a porta fechar. O atender fica fora do try: ele já responde por conta própria.
    try:
        from playwright.sync_api import sync_playwright
    except Exception as e:
        escrever_mensagem(sys.stdout.buffer, {"tipo": "erro", "texto": f"Falha ao iniciar: {resumir(e)}"})
        return

    def resolver(next_url, ua, progresso):
        with sync_playwright() as p:
            req = p.request.new_context(user_agent=ua, extra_http_headers={"accept-language": "pt-BR,pt;q=0.9"})
            s = Sessao(req)
            try:
                return percorrer(s, next_url, progresso)
            except Parada:
                raise
            except Exception as e:  # acrescenta onde parou
                raise Parada(f"{s.onde} · {resumir(e)}") from e

    atender(sys.stdin.buffer, sys.stdout.buffer, resolver)


if __name__ == "__main__":
    main()

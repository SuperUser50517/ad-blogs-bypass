"""Testes da extensão (sem rede: o encurtador é simulado por rotas locais). Rodar: python tests\\test_extensao.py

Carrega o ponte.js real numa página do encurtador simulada, com uma lista falsa no chrome.storage,
e confere a faixa "Este link já foi resolvido".
"""
import json
from pathlib import Path

from playwright.sync_api import sync_playwright

RAIZ = Path(__file__).resolve().parent.parent
PONTE = (RAIZ / "extension" / "ponte.js").read_text(encoding="utf-8")
DESTINO = "https://t.me/+ConviteDeExemplo"
STUB = """window.chrome = { runtime: { id: "teste", sendMessage: async () => {} },
  storage: { local: { get: async () => ({ itens: %s }) } } };"""


def item(link, status="ok", destino=DESTINO):
    return {"id": link, "link": link, "status": status, "destino": destino if status == "ok" else None}


def faixa(navegador, url, itens, antes_de_ler=None):
    """Abre `url` com a lista `itens`; devolve o destino mostrado na faixa (ou None) e a página."""
    ctx = navegador.new_context()
    ctx.route("**/*", lambda rota: rota.fulfill(status=200, content_type="text/html",
                                                 body="<html><body><p>encurtador simulado</p></body></html>"))
    ctx.add_init_script(STUB % json.dumps(itens))
    ctx.add_init_script(PONTE)
    pagina = ctx.new_page()
    pagina.goto(url, wait_until="load")
    pagina.wait_for_timeout(150)
    if antes_de_ler:
        antes_de_ler(pagina)
        pagina.wait_for_timeout(100)
    texto = pagina.evaluate("""() => {
        const h = document.getElementById('snet-bypass-resolvido');
        return h ? h.shadowRoot.querySelector('.destino').textContent : null;
    }""")
    ctx.close()
    return texto


def test_faixa_do_link_ja_resolvido():
    with sync_playwright() as p:
        b = p.chromium.launch()
        try:
            salvo = [item("https://snet.blog/exemplo1")]
            # 1. mesmo link
            assert faixa(b, "https://snet.blog/exemplo1", salvo) == DESTINO
            # 2. variações que devem contar como o mesmo link
            assert faixa(b, "https://snet.blog/exemplo1?dl_fake_done=1", salvo) == DESTINO
            assert faixa(b, "https://www.snet.blog/exemplo1/", salvo) == DESTINO
            # 3. link diferente (inclusive só na caixa das letras: o alias diferencia)
            assert faixa(b, "https://snet.blog/outro", salvo) is None
            assert faixa(b, "https://snet.blog/EXEMPLO1", salvo) is None
            # 4. item que não está pronto não conta
            assert faixa(b, "https://snet.blog/exemplo1", [item("https://snet.blog/exemplo1", "erro")]) is None
            assert faixa(b, "https://snet.blog/exemplo1", [item("https://snet.blog/exemplo1", "resolvendo")]) is None
            # 5. "Resolver de novo" tira a faixa
            fechar = lambda pg: pg.evaluate(
                "document.getElementById('snet-bypass-resolvido').shadowRoot"
                ".querySelector('[data-acao=refazer]').click()")
            assert faixa(b, "https://snet.blog/exemplo1", salvo, antes_de_ler=fechar) is None
        finally:
            b.close()


if __name__ == "__main__":
    for nome, f in list(globals().items()):
        if nome.startswith("test_"):
            f()
            print("ok", nome)

"""Testes da extensão (sem rede: o encurtador é simulado por rotas locais). Rodar: python tests\\test_extensao.py

Carrega o ponte.js real numa página do encurtador simulada, com uma lista falsa no chrome.storage,
e confere a faixa "Este link já foi resolvido".
"""
import json
import time
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


POPUP = (RAIZ / "extension" / "popup.html").as_uri()
API = "https://api.github.com/repos/joaomgabaldi/ad-blogs-bypass/releases/latest"
STUB_POPUP = """
window.__guardado = %s;
window.__abas = [];
window.chrome = {
  storage: {
    local: {
      get: async (chave) => ({ [chave]: window.__guardado[chave] }),
      set: async (valores) => { Object.assign(window.__guardado, valores); },
    },
    onChanged: { addListener() {} },
  },
  runtime: { sendMessage() {}, getManifest: () => ({ version: "2.0.2" }) },
  tabs: { create: (o) => { window.__abas.push(o.url); } },
};
"""


def popup(navegador, tag=None, guardado=None, acao=None):
    """Abre o popup (versão 2.0.2) com a API respondendo `tag` (None = sem rede).
    Devolve (texto da faixa ou None, quantas vezes a API foi chamada, storage final, abas abertas)."""
    ctx = navegador.new_context()
    chamadas = []

    def api(rota):
        chamadas.append(rota.request.url)
        if tag is None:
            return rota.abort()
        rota.fulfill(status=200, content_type="application/json", headers={"access-control-allow-origin": "*"},
                     body=json.dumps({"tag_name": tag, "html_url": "https://github.com/x"}))

    ctx.route(API, api)
    ctx.add_init_script(STUB_POPUP % json.dumps({"itens": [], **(guardado or {})}))
    pagina = ctx.new_page()
    pagina.goto(POPUP, wait_until="load")
    pagina.wait_for_timeout(300)
    if acao:
        acao(pagina)
        pagina.wait_for_timeout(150)
    faixa = pagina.locator("#versao-nova")
    texto = faixa.inner_text().strip() if faixa.is_visible() else None
    resultado = texto, len(chamadas), pagina.evaluate("window.__guardado"), pagina.evaluate("window.__abas")
    ctx.close()
    return resultado


def test_aviso_de_versao_nova():
    agora = int(time.time() * 1000)
    with sync_playwright() as p:
        b = p.chromium.launch()
        try:
            # 1. versão mais nova: mostra, e guarda a consulta
            texto, chamadas, guardado, _ = popup(b, "v2.0.3")
            assert texto and "Versão 2.0.3 disponível" in texto, texto
            assert chamadas == 1 and guardado["versao"]["ultima"] == "2.0.3", guardado
            # 2. mesma versão ou mais antiga: não mostra
            assert popup(b, "v2.0.2")[0] is None
            assert popup(b, "v1.9.9")[0] is None
            # 3. comparação por número, não por texto: 2.0.10 é mais nova que 2.0.2
            assert popup(b, "v2.0.10")[0] is not None
            # 4. sem rede: não mostra e não grava, para tentar de novo na próxima abertura
            texto, chamadas, guardado, _ = popup(b, None)
            assert texto is None and chamadas == 1 and "versao" not in guardado, (texto, guardado)
            # 5. consultada há menos de 24 h: usa o que está guardado, sem chamar a API
            recente = {"versao": {"verificado": agora, "ultima": "2.0.3"}}
            texto, chamadas, _, _ = popup(b, "v9.9.9", recente)
            assert texto and "2.0.3" in texto and chamadas == 0, (texto, chamadas)
            # 6. o × dispensa esta versão e grava
            fechar = lambda pg: pg.click("#fechar-versao")
            texto, _, guardado, _ = popup(b, "v2.0.3", acao=fechar)
            assert texto is None and guardado["versao"]["dispensada"] == "2.0.3", (texto, guardado)
            # 7. versão dispensada não volta; uma mais nova que ela, sim
            dispensada = {"versao": {"verificado": 0, "ultima": "2.0.3", "dispensada": "2.0.3"}}
            assert popup(b, "v2.0.3", dispensada)[0] is None
            assert popup(b, "v2.0.4", dispensada)[0] is not None
            # 8. "Ver novidades" abre a página do release
            ver = lambda pg: pg.click(".versao-link")
            _, _, _, abas = popup(b, "v2.0.3", acao=ver)
            assert abas == ["https://github.com/joaomgabaldi/ad-blogs-bypass/releases/latest"], abas
        finally:
            b.close()


if __name__ == "__main__":
    for nome, f in list(globals().items()):
        if nome.startswith("test_"):
            f()
            print("ok", nome)

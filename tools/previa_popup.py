"""Prévia do popup com uma API chrome falsa e itens de exemplo, sem rede.
Grava popup_itens.png, popup_vazio.png e popup_limpar.png em tools/previa/. Rodar: python tools/previa_popup.py"""
import json
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

RAIZ = Path(__file__).resolve().parent.parent
POPUP = (RAIZ / "extension" / "popup.html").as_uri()
SAIDA = Path(__file__).resolve().parent / "previa"
agora = int(time.time() * 1000)
MIN = 60_000
EXEMPLO = [
    {"id": "1", "status": "resolvendo", "link": "https://snet.blog/k7r2pqa", "capturado": agora - 20_000,
     "progresso": {"b": 3, "a": 6, "host": "app.pinkbella.com.br"}},
    {"id": "2", "status": "ok", "link": "https://snet.blog/exemplo1", "capturado": agora - 4 * MIN,
     "destino": "https://t.me/+ConviteDeExemplo"},
    {"id": "3", "status": "erro", "link": "https://snet.blog/m3v9zte", "capturado": agora - 12 * MIN,
     "erro": "etapa 4 · app.pinkbella.com.br · post 38 · confirmContentTwoExternalReturnAction\n500 Internal Server Error"},
    {"id": "4", "status": "ok", "link": "https://suaurl.com/a8Qe21", "capturado": agora - 95 * MIN,
     "destino": "https://mega.nz/folder/Xk2a8QeB#s9d8f7g6h5j4k3l2"},
]
STUB = """
window.__itens = %s;
window.chrome = {
  storage: { local: { get: async () => ({ itens: window.__itens }) }, onChanged: { addListener() {} } },
  runtime: { sendMessage() {} }, tabs: { create() {} },
};
"""


def foto(b, itens, nome, antes=None):
    ctx = b.new_context(viewport={"width": 400, "height": 580}, device_scale_factor=2, color_scheme="dark")
    ctx.add_init_script(STUB % json.dumps(itens))
    pg = ctx.new_page()
    pg.goto(POPUP)
    pg.wait_for_timeout(300)
    if antes:
        antes(pg)
        pg.wait_for_timeout(250)
    altura = pg.evaluate("document.body.scrollHeight")
    pg.set_viewport_size({"width": 400, "height": min(580, altura)})
    pg.screenshot(path=str(SAIDA / nome))
    ctx.close()


SAIDA.mkdir(exist_ok=True)
with sync_playwright() as p:
    b = p.chromium.launch()
    foto(b, EXEMPLO, "popup_itens.png")
    foto(b, [], "popup_vazio.png")
    foto(b, EXEMPLO, "popup_limpar.png", antes=lambda pg: pg.click("#limpar"))
    b.close()
print("prévias em", SAIDA)

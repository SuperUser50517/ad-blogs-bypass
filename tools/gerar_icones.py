"""Gera os ícones com o Chromium do Playwright: extension/icones/{16,32,48,128}.png e installer/icone.ico
(PNGs de 16, 32, 48 e 256 embutidos). Mesmo logo do popup. Rodar: python tools/gerar_icones.py"""
import struct
from pathlib import Path

from playwright.sync_api import sync_playwright

RAIZ = Path(__file__).resolve().parent.parent
ICONES = RAIZ / "extension" / "icones"
ICO = RAIZ / "installer" / "icone.ico"
LOGO = ('<path d="M10 13a5 5 0 0 0 7.54.54l3-3a5 5 0 0 0-7.07-7.07l-1.72 1.71"/>'
        '<path d="M14 11a5 5 0 0 0-7.54-.54l-3 3a5 5 0 0 0 7.07 7.07l1.71-1.71"/>')


def desenhar(b, tam):
    """PNG (bytes) do ícone em tam×tam: quadrado arredondado em gradiente com o logo de corrente."""
    pg = b.new_page(viewport={"width": tam, "height": tam})
    traco = 3 if tam <= 16 else 2.6 if tam <= 32 else 2.4
    pg.set_content(f"""<html><body style="margin:0;background:transparent">
    <div style="width:{tam}px;height:{tam}px;border-radius:{tam * 0.26}px;display:grid;place-items:center;
         background:linear-gradient(135deg,#52d69c 0%,#2e9e6c 100%)">
      <svg viewBox="0 0 24 24" width="{tam * 0.62}" height="{tam * 0.62}" fill="none" stroke="#0e1014"
           stroke-width="{traco}" stroke-linecap="round" stroke-linejoin="round">{LOGO}</svg>
    </div></body></html>""")
    png = pg.screenshot(omit_background=True)
    pg.close()
    return png


def ico(pngs):
    """Arquivo .ico com payload PNG (aceito desde o Windows Vista). pngs: {tamanho: bytes}."""
    cabecalho = struct.pack("<HHH", 0, 1, len(pngs))
    entradas, dados = b"", b""
    deslocamento = 6 + 16 * len(pngs)
    for tam, png in pngs.items():
        lado = 0 if tam >= 256 else tam  # 0 significa 256 no formato ICO
        entradas += struct.pack("<BBBBHHII", lado, lado, 0, 0, 1, 32, len(png), deslocamento + len(dados))
        dados += png
    return cabecalho + entradas + dados


with sync_playwright() as p:
    b = p.chromium.launch()
    for tam in (16, 32, 48, 128):
        (ICONES / f"{tam}.png").write_bytes(desenhar(b, tam))
    ICO.parent.mkdir(exist_ok=True)
    ICO.write_bytes(ico({tam: desenhar(b, tam) for tam in (16, 32, 48, 256)}))
    b.close()
print("gerados:", sorted(f.name for f in ICONES.iterdir()), ICO.name)

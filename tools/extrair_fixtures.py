"""Gera as fixtures dos testes (tests/fixtures) a partir de um HAR gravado no navegador.

Uso:  python tools/extrair_fixtures.py caminho/para/gravacao.har

O HAR precisa ser de uma corrente completa pelos blogs (DevTools > Rede > "Preservar log" >
"Salvar tudo como HAR"). Os índices das entradas abaixo são os da gravação usada no projeto;
com outra gravação, ajuste-os.

As fixtures são EXTRATOS MÍNIMOS: guardam só os trechos reais que o código lê — as mesmas regex do
companion/corrente.py — e descartam o resto (texto dos artigos, código dos sites). Assim os testes
continuam exercitando o formato real sem publicar conteúdo de terceiros.
"""
import json
import re
import sys
from pathlib import Path
from urllib.parse import urlparse

RAIZ = Path(__file__).resolve().parent.parent
DESTINO = RAIZ / "tests" / "fixtures"
sys.path.insert(0, str(RAIZ / "companion"))

from corrente import _CHAVE, _CHUNK, _FRAME, _REF  # noqa: E402

CONVITE_DE_EXEMPLO = "https://t.me/+ConviteDeExemplo"

# arquivo -> (índice da entrada no HAR, trecho que a URL precisa conter)
POSTS = {
    "shufflepost_post20.rsc": (496, "shufflepost.com/post/20"),
    "shufflepost_post38.rsc": (593, "shufflepost.com/post/38"),
    "pinkbella_post38.rsc": (2122, "app.pinkbella.com.br/post/38"),
    "koaladesign_post25.rsc": (382, "koaladesign.com.br/post/25"),
}
ACAO_FINAL = (2998, "app.radiology.com.br/ad-frame/content_2")


def extrato_do_post(texto):
    """Chunks citados, frames (adFrameSrc…interactionGateEnabled) e gateKeys, na ordem em que aparecem."""
    achados, vistos = [], set()
    for m in _CHUNK.finditer(texto):  # o RSC repete o mesmo chunk muitas vezes: basta a primeira
        if m.group(0) not in vistos:
            vistos.add(m.group(0))
            achados.append((m.start(), m.group(0)))
    achados += [(m.start(), m.group(0)) for m in _FRAME.finditer(texto)]
    # o match da gateKey para antes da aspas de fechamento: ela vai junto, senão a releitura atravessa a linha
    achados += [(m.start(), m.group(0) + '"') for m in _CHAVE.finditer(texto)]
    linhas = [trecho for _, trecho in sorted(achados)]
    return "# extrato mínimo de uma resposta RSC real (tools/extrair_fixtures.py)\n" + "\n".join(linhas) + "\n"


def extrato_dos_chunks(chunks):
    """Só as chamadas createServerReference(id, …, nome) de cada chunk."""
    partes = []
    for caminho, texto in chunks:
        refs = [m.group(0) for m in _REF.finditer(texto)]
        if refs:
            partes.append(f"/* {caminho} */\n" + "\n".join(refs))
    return "\n".join(partes) + "\n"


def main():
    if len(sys.argv) != 2:
        sys.exit("uso: python tools/extrair_fixtures.py caminho/para/gravacao.har")
    entradas = json.load(open(sys.argv[1], encoding="utf-8"))["log"]["entries"]
    DESTINO.mkdir(parents=True, exist_ok=True)

    def resposta(indice, trecho):
        e = entradas[indice]
        assert trecho in e["request"]["url"], (indice, e["request"]["url"])
        return e["response"]["content"]["text"]

    for nome, (i, trecho) in POSTS.items():
        (DESTINO / nome).write_text(extrato_do_post(resposta(i, trecho)), encoding="utf-8")

    # a resposta da última action traz o destino final: o convite real é trocado por um de exemplo
    acao = resposta(*ACAO_FINAL)
    acao = re.sub(r'"destinationUrl":"[^"]*"', f'"destinationUrl":"{CONVITE_DE_EXEMPLO}"', acao)
    (DESTINO / "acao_final.txt").write_text(acao, encoding="utf-8")

    chunks = []
    for e in entradas:
        u = urlparse(e["request"]["url"])
        texto = e["response"]["content"].get("text") or ""
        if u.netloc == "shufflepost.com" and "/_next/static/chunks/" in u.path and "createServerReference" in texto:
            chunks.append((u.path, texto))
    (DESTINO / "shufflepost_chunks.js").write_text(extrato_dos_chunks(chunks), encoding="utf-8")

    for p in sorted(DESTINO.iterdir()):
        print(f"{p.name}: {p.stat().st_size} bytes")


if __name__ == "__main__":
    main()

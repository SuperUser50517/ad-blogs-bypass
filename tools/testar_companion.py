"""Teste de fumaça do companion: conversa com ele pelo stdin/stdout como o Brave faz (uint32 LE + JSON UTF-8).

Rodar: python tools\\testar_companion.py        (contra companion\\dist\\snet-bypass-companion\\snet-bypass-companion.exe)
       python tools\\testar_companion.py --py   (contra companion\\host.py, com o Python do sistema)

Manda um nextUrl em 127.0.0.1:9 (nunca um site real). Esperado: uma única mensagem {tipo: "erro"} com o
bloqueio de rede local ("etapa 1 · 127.0.0.1:9 · endereço bloqueado por segurança…"), o que também prova que o
exe empacotado inicia, e o processo saindo sozinho, sem nenhum byte fora do protocolo.
"""
import json
import struct
import subprocess
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
PEDIDO = {"nextUrl": "http://127.0.0.1:9/?ad_id=teste", "ua": "Mozilla/5.0"}


def main():
    sys.stdout.reconfigure(encoding="utf-8")  # o texto do erro traz "→"; a saída redirecionada em cp1252 quebraria
    if "--py" in sys.argv:
        cmd = [sys.executable, str(RAIZ / "companion" / "host.py")]
    else:
        cmd = [str(RAIZ / "companion" / "dist" / "snet-bypass-companion" / "snet-bypass-companion.exe")]
    corpo = json.dumps(PEDIDO).encode("utf-8")
    # O Brave mantém o stdin aberto; aqui ele fecha depois do pedido, o que o host também aceita (lê uma mensagem só).
    r = subprocess.run(cmd, input=struct.pack("<I", len(corpo)) + corpo, capture_output=True, timeout=120)

    saida, mensagens = r.stdout, []
    while len(saida) >= 4:
        (tamanho,) = struct.unpack("<I", saida[:4])
        mensagens.append(json.loads(saida[4:4 + tamanho].decode("utf-8")))
        saida = saida[4 + tamanho:]
    for m in mensagens:
        print(json.dumps(m, ensure_ascii=False))
    print("código de saída:", r.returncode)
    if r.stderr:
        print("stderr:", r.stderr.decode("utf-8", "replace"))

    assert not saida, f"bytes fora do protocolo no stdout: {saida!r}"
    assert len(mensagens) == 1 and mensagens[0]["tipo"] == "erro", mensagens
    assert mensagens[0]["texto"].startswith("etapa 1 · 127.0.0.1:9 · endereço bloqueado por segurança"), mensagens[0]["texto"]
    print("ok")


if __name__ == "__main__":
    main()

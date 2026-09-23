# Ad Blogs Bypass

Extensão para o navegador **Brave** (Manifest V3) que desencurta os links dos
[sites suportados](#sites-suportados) sem passar pelo monte de sequência de anúncios.

Você resolve o captcha **no próprio site**, a extensão lê o resultado, fecha a aba antes de qualquer
anúncio e desencurta o link, usando um app auxiliar (companion). O popup
guarda cada link resolvido, como um bloco de notas.

> O projeto não tem nenhum vínculo com o encurtador nem com os blogs, só odeio essa estratégia de enfiar anúncios até no ** do usuário.

## Sites suportados

- `snet.blog`
- `suaurl.com`
- `sbio.pro`

## Instalar

Requisitos: Windows 10 ou 11 (64 bits) e Brave.

1. **Baixe** os dois arquivos da [última versão](../../releases/latest).
2. **Rode o instalador do companion.** 
3. **Instale a extensão:**
   1. extraia o `.zip`;
   2. abra `brave://extensions`, ligue o **Modo do desenvolvedor**;
   3. clique em **Carregar sem compactação** e escolha a pasta onde você extraiu o zip.
4. Pronto: abra um link do encurtador, resolva o captcha e acompanhe na extensão.

Se o site mostrar "Bloqueador de anúncios detectado", desligue os Shields do Brave só para o domínio do
encurtador.

## Como funciona

```
página do encurtador ── captcha ──▶ a extensão lê o link seguinte e fecha a aba
                                                                 │ Native Messaging
                                                                 ▼
                                              componente local: percorre as 6 etapas por HTTP
                                                                 │ progresso · destino · erro
                                                                 ▼
                                   popup: resolvendo (etapa N de 6) · pronto (copiar, abrir) · erro
```

- Ao abrir de novo um link que já foi resolvido, a extensão mostra o destino na hora, sem novo captcha.
- A lista fica salva até você limpá-la: fechar o navegador não limpa.
- Em caso de erro, o cartão do link mostra onde parou e, enquanto o link valer (30 minutos), oferece
  "Tentar de novo" sem novo captcha.
- O componente local não grava arquivos e não abre navegador; só faz chamadas HTTP.
- O Brave é recusado pelo site; a extensão se apresenta como Google Chrome **apenas** nos domínios do
  encurtador.

## Compilar

Para gerar o instalador a partir do código:

1. Instale:
   - [Python](https://www.python.org/downloads/) 3.10 ou mais recente (desenvolvido no 3.14), com a
     opção "Add python.exe to PATH";
   - as bibliotecas: `python -m pip install playwright pyinstaller` (o componente usa só as chamadas HTTP
     do Playwright — não é preciso baixar navegadores com `playwright install`);
   - o [Inno Setup 6](https://jrsoftware.org/isdl.php).
2. Na pasta do projeto, rode:
   ```powershell
   powershell -NoProfile -ExecutionPolicy Bypass -File .\installer\build-installer.ps1
   ```
   O script gera o executável do companion (`companion\build.ps1`, PyInstaller) se ele faltar ou
   estiver desatualizado, confere o ID da extensão, lê a versão do `extension\manifest.json` e gera em
   `installer\output\` os dois arquivos de uma versão: `ad-blogs-bypass-companion-<versão>-setup.exe` e
   `ad-blogs-bypass-extensao-<versão>.zip`. Os caminhos são todos relativos à pasta do projeto — clone
   onde quiser.
3. Para usar a extensão direto do código, carregue sem compactação a pasta `extension\`.

O ID da extensão é fixo (`gdffnebealemedjembikfbagoijgmeij`), definido pelo campo `key` do
`extension\manifest.json`, e o instalador autoriza só esse ID. Se você mudar a `key`, atualize também o
`ExtensionId` do `installer\ad-blogs-bypass-companion.iss` (o `build-installer.ps1` interrompe a compilação se não baterem).

## Testes

```powershell
python -m pip install playwright
python -m playwright install chromium   # só para test_extensao.py e as ferramentas de tools\
python tests\test_companion.py
python tests\test_extensao.py
```

Todos rodam sem acessar a internet (o Chromium do Playwright é usado só como página de teste local): leitura das respostas dos blogs (trechos reais reduzidos ao mínimo que
o código lê), etapas com uma sessão falsa, protocolo do componente e a faixa "Este link já foi resolvido"
numa página simulada. Depois de gerar o `.exe`, `python tools\testar_companion.py` o executa como o
navegador faria, contra `127.0.0.1`.

## Pastas

| Pasta | O que é |
|---|---|
| `extension/` | A extensão (carregar sem compactação). |
| `companion/` | O componente local: `host.py` (protocolo com a extensão) e `corrente.py` (percorre as etapas). |
| `installer/` | Instalador Inno Setup 6 e o script que gera tudo. |
| `tests/` | Testes offline e `fixtures/`. |
| `tools/` | Utilitários: fixtures a partir de uma gravação HAR, ícones, prévia do popup, teste do `.exe`. |

## Contribuir

Issues e pull requests são bem-vindos. Antes de enviar, rode os testes. O site muda de tempos em tempos;
ao investigar uma quebra, uma gravação HAR do fluxo completo (DevTools → Rede → "Preservar log" → "Salvar
tudo como HAR") ajuda muito — mas **não publique HARs**: eles contêm cookies e identificadores da sua
sessão.

## Aviso

Projeto independente e não oficial, feito para uso pessoal e disponibilizado como está, sem garantia.
Ele depende do funcionamento atual do encurtador e dos blogs, que podem mudar a qualquer momento e fazê-lo
parar de funcionar. Verifique os termos de uso dos sites que você acessa; o uso é de sua responsabilidade.

## Licença

[GPL-3.0](LICENSE).





## 


obrig pela ajuda IA 🫂

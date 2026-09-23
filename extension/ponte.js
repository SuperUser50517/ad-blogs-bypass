// Ad Blogs Bypass — world ISOLATED, document_start. Repassa o nextUrl capturado pelo captura.js
// (world MAIN, sem acesso às APIs da extensão) para o background.
//
// Se a extensão foi recarregada com esta aba aberta, este script fica órfão: chrome.runtime some
// (ou sendMessage lança "Extension context invalidated") e o nextUrl não tem para onde ir.
// Nesse caso, avisa na própria página em vez de falhar em silêncio.

function avisarQueFicouOrfao() {
  if (document.getElementById("snet-bypass-aviso")) return;
  const aviso = document.createElement("div");
  aviso.id = "snet-bypass-aviso";
  aviso.textContent = "Atualize a página e tente novamente";
  aviso.style.cssText = "position:fixed;top:0;left:0;right:0;z-index:2147483647;padding:12px 16px;"
    + "background:#f06464;color:#1a0b0b;font:600 14px/1.4 'Segoe UI',system-ui,sans-serif;"
    + "text-align:center;box-shadow:0 2px 12px rgba(0,0,0,.35)";
  document.documentElement.append(aviso);
}

// ---------- link já resolvido ----------
// Ao abrir um link que já tem destino pronto na lista, mostra uma faixa no topo antes de o usuário
// gastar um captcha. A comparação ignora www., query (dl_fake_done etc.), # e a barra final; o caminho
// mantém maiúsculas/minúsculas, porque o alias do encurtador as diferencia.
function chave(url) {
  try {
    const u = new URL(url);
    return u.hostname.toLowerCase().replace(/^www\./, "") + u.pathname.replace(/\/+$/, "");
  } catch (e) {
    return "";
  }
}

const CSS_FAIXA = `
  :host { all: initial; }
  .faixa { position: fixed; top: 12px; left: 50%; transform: translateX(-50%); z-index: 2147483647;
    width: min(560px, calc(100vw - 24px)); box-sizing: border-box; padding: 14px 16px 14px 14px;
    display: flex; gap: 12px; align-items: flex-start;
    background: #161920; color: #e8eaf0; border: 1px solid #262b36; border-left: 3px solid #3fbf86;
    border-radius: 12px; box-shadow: 0 12px 32px rgba(0,0,0,.5);
    font: 13px/1.45 "Segoe UI Variable Text", "Segoe UI", system-ui, sans-serif; }
  .logo { flex: none; width: 32px; height: 32px; border-radius: 9px; display: grid; place-items: center;
    color: #0e1014; background: linear-gradient(135deg, #52d69c 0%, #2e9e6c 100%); }
  .logo svg { width: 18px; height: 18px; }
  svg { fill: none; stroke: currentColor; stroke-width: 2.4; stroke-linecap: round; stroke-linejoin: round; }
  .corpo { flex: 1; min-width: 0; }
  .titulo { font-weight: 650; font-size: 13.5px; }
  .destino { margin: 6px 0 10px; padding: 6px 9px; background: #0f1217; border: 1px solid #20242e;
    border-radius: 8px; font: 12.5px/1.4 "Cascadia Mono", Consolas, ui-monospace, monospace; color: #d7f5e6;
    white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
  .botoes { display: flex; flex-wrap: wrap; gap: 8px; }
  button { font: inherit; font-size: 12.5px; cursor: pointer; border-radius: 8px; padding: 6px 12px; }
  .principal { background: #3fbf86; color: #0e1014; border: 0; font-weight: 600; }
  .principal:hover { filter: brightness(1.08); }
  .secundario { background: #1d212a; color: #e8eaf0; border: 1px solid #333a48; }
  .secundario:hover { border-color: #3fbf86; }
  .fechar { flex: none; background: none; border: 0; color: #6b7285; padding: 2px 6px; font-size: 18px; line-height: 1; }
  .fechar:hover { color: #e8eaf0; }
`;
const LOGO = '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M10 13a5 5 0 0 0 7.54.54l3-3a5 5 0 0 0-7.07-7.07l-1.72 1.71"/><path d="M14 11a5 5 0 0 0-7.54-.54l-3 3a5 5 0 0 0 7.07 7.07l1.71-1.71"/></svg>';

function mostrarJaResolvido(destino) {
  if (document.getElementById("snet-bypass-resolvido")) return;
  const host = document.createElement("div");
  host.id = "snet-bypass-resolvido";
  const raiz = host.attachShadow({ mode: "open" }); // isolada do CSS do site
  raiz.innerHTML = `<style>${CSS_FAIXA}</style>
    <div class="faixa" role="status">
      <span class="logo">${LOGO}</span>
      <div class="corpo">
        <div class="titulo">Este link já foi resolvido</div>
        <div class="destino"></div>
        <div class="botoes">
          <button class="principal" data-acao="abrir" type="button">Abrir destino</button>
          <button class="secundario" data-acao="copiar" type="button">Copiar</button>
          <button class="secundario" data-acao="refazer" type="button">Resolver de novo</button>
        </div>
      </div>
      <button class="fechar" data-acao="refazer" type="button" title="Fechar" aria-label="Fechar">×</button>
    </div>`;
  const caixaDestino = raiz.querySelector(".destino");
  caixaDestino.textContent = destino; // texto, nunca HTML
  caixaDestino.title = destino;
  raiz.addEventListener("click", (evento) => {
    const acao = evento.target.closest && evento.target.closest("[data-acao]");
    if (!acao) return;
    if (acao.dataset.acao === "abrir") {
      location.href = destino;
    } else if (acao.dataset.acao === "copiar") {
      navigator.clipboard.writeText(destino).then(
        () => { acao.textContent = "Copiado"; setTimeout(() => { acao.textContent = "Copiar"; }, 1400); },
        () => { acao.textContent = "Não foi possível copiar"; });
    } else {
      host.remove(); // segue o fluxo normal: o usuário pode resolver o captcha de novo
    }
  });
  document.documentElement.append(host);
}

async function verificarSeJaFoiResolvido() {
  if (!globalThis.chrome || !chrome.runtime || !chrome.runtime.id || !chrome.storage) return;
  const minha = chave(location.href);
  if (!minha) return;
  const { itens = [] } = await chrome.storage.local.get("itens"); // mais recente primeiro
  const pronto = itens.find((i) => i.status === "ok" && typeof i.destino === "string"
    && /^https?:\/\//i.test(i.destino) && chave(i.link) === minha);
  if (!pronto) return;
  // Depois do "load": o site é Next.js/React, e mexer no DOM antes da hidratação pode atrapalhá-lo.
  if (document.readyState === "complete") mostrarJaResolvido(pronto.destino);
  else window.addEventListener("load", () => mostrarJaResolvido(pronto.destino), { once: true });
}
verificarSeJaFoiResolvido().catch(() => {});

// ---------- captura ----------
window.addEventListener("message", (evento) => {
  if (evento.source !== window || !evento.data || evento.data.corrente !== "prepare") return;
  if (!globalThis.chrome || !chrome.runtime || !chrome.runtime.id) return avisarQueFicouOrfao();
  const link = new URL(location.href);
  link.searchParams.delete("dl_fake_done");
  try {
    chrome.runtime.sendMessage({
      tipo: "capturado",
      nextUrl: evento.data.nextUrl,
      link: link.href,
      ua: navigator.userAgent,
    }).catch((e) => {
      // "message port closed" (o background não responde) não é problema: a mensagem foi entregue.
      if (!chrome.runtime || !chrome.runtime.id || /invalidated/i.test(String(e && e.message))) avisarQueFicouOrfao();
    });
  } catch (e) {
    avisarQueFicouOrfao();
  }
});

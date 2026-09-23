// Ad Blogs Bypass — world MAIN, document_start.
// Envolve o fetch da página e lê uma CÓPIA da resposta do /api/short-links/prepare/, que o site
// só chama depois que o usuário resolve o captcha. A resposta original volta intacta.
(() => {
  "use strict";
  const original = window.fetch;

  window.fetch = async function (...args) {
    const resposta = await original.apply(this, args);
    try {
      const alvo = args[0];
      const url = typeof alvo === "string" ? alvo : alvo instanceof URL ? alvo.href : (alvo && alvo.url) || "";
      if (url.includes("/api/short-links/prepare/")) {
        resposta.clone().json().then((dados) => {
          if (dados && dados.ok && typeof dados.nextUrl === "string") {
            window.postMessage({ corrente: "prepare", nextUrl: dados.nextUrl }, location.origin);
          }
        }).catch(() => {});
      }
    } catch (e) {
      // o site nunca pode quebrar por causa da extensão
    }
    return resposta;
  };
})();

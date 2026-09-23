// Ad Blogs Bypass — world MAIN, document_start, só nos domínios do encurtador (ver manifest.json).
// Adaptado do ua.js da versão 8.1 anterior deste projeto: esconde o que denuncia o Brave
// no JS da página. O que de fato barrava o Brave é o cabeçalho Sec-CH-UA, tratado no background.js.
// Não mexe em userAgent/platform/vendor: no Brave eles já são idênticos aos do Chrome.
(() => {
  "use strict";
  const MAJOR = (/Chrome\/(\d+)/.exec(navigator.userAgent) || [])[1] || "152";
  const VERSAO = MAJOR + ".0.0.0";

  // Apaga no protótipo dono (Navigator.prototype), sem sombrear: sombrear com undefined deixaria
  // 'brave' in navigator === true, o que denuncia mais do que o valor original.
  const apagar = (obj, prop) => {
    let alvo = obj;
    while (alvo && !Object.prototype.hasOwnProperty.call(alvo, prop)) alvo = Object.getPrototypeOf(alvo);
    if (alvo) try { delete alvo[prop]; } catch (e) {}
  };
  apagar(navigator, "brave");                 // navigator.brave.isBrave()
  apagar(navigator, "globalPrivacyControl");  // o Brave liga por padrão; o Chrome não tem

  // userAgentData sem a marca "Brave". Os getters nativos exigem o slot interno, então o objeto
  // é reconstruído — com o construtor chamado NavigatorUAData, como o do navegador.
  const real = navigator.userAgentData;
  const marcas = [
    { brand: "Not/A)Brand", version: "8" },
    { brand: "Chromium", version: MAJOR },
    { brand: "Google Chrome", version: MAJOR },
  ];
  const marcasCompletas = [
    { brand: "Not/A)Brand", version: "8.0.0.0" },
    { brand: "Chromium", version: VERSAO },
    { brand: "Google Chrome", version: VERSAO },
  ];
  const NavigatorUAData = class NavigatorUAData {
    constructor() {
      this.brands = marcas;
      this.mobile = real ? !!real.mobile : false;
      this.platform = (real && real.platform) || "Windows";
    }
    toJSON() {
      return { brands: this.brands, mobile: this.mobile, platform: this.platform };
    }
    getHighEntropyValues(dicas) {
      if (!Array.isArray(dicas)) {
        return Promise.reject(new TypeError("Failed to execute 'getHighEntropyValues' on 'NavigatorUAData'"));
      }
      const r = this.toJSON();
      if (dicas.includes("architecture")) r.architecture = "x86";
      if (dicas.includes("bitness")) r.bitness = "64";
      if (dicas.includes("model")) r.model = "";
      if (dicas.includes("platformVersion")) r.platformVersion = "15.0.0";
      if (dicas.includes("uaFullVersion")) r.uaFullVersion = VERSAO;
      if (dicas.includes("fullVersionList")) r.fullVersionList = marcasCompletas;
      return Promise.resolve(r);
    }
  };
  const falso = new NavigatorUAData();
  try {
    Object.defineProperty(navigator, "userAgentData", { get: () => falso, configurable: true });
  } catch (e) {}
})();

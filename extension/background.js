// Ad Blogs Bypass — service worker.
// Recebe o nextUrl capturado, fecha a aba do encurtador, entrega o nextUrl ao host Python
// (Native Messaging, um processo por link) e guarda o resultado na lista do popup.
const HOST = "com.corrente.host";
const DOMINIOS = ["snet.blog", "suaurl.com", "sbio.pro"];
const VALIDADE_MS = 30 * 60 * 1000; // o ad_id vale 30 min: depois disso não adianta reenviar
const MAJOR = (/Chrome\/(\d+)/.exec(navigator.userAgent) || [])[1] || "152";
const REGRA_CABECALHOS = 100;

// ---------- cabeçalhos: o Brave se entrega no Sec-CH-UA, antes de a página existir ----------
// Reaproveitado da versão 8.1 anterior deste projeto. Só nos domínios
// do encurtador; o resto da navegação não é tocado. Regra dinâmica: persiste quando o Brave fecha e
// quando a extensão é desativada e reativada. Ainda assim é recriada (remove + add, atômico) toda vez
// que o service worker inicia, para acompanhar o MAJOR depois de uma atualização do Brave.
async function esconderBraveNosCabecalhos() {
  await chrome.declarativeNetRequest.updateDynamicRules({
    removeRuleIds: [REGRA_CABECALHOS],
    addRules: [{
      id: REGRA_CABECALHOS,
      priority: 10,
      action: {
        type: "modifyHeaders",
        requestHeaders: [
          { header: "sec-ch-ua", operation: "set",
            value: `"Not/A)Brand";v="8", "Chromium";v="${MAJOR}", "Google Chrome";v="${MAJOR}"` },
          { header: "sec-ch-ua-mobile", operation: "set", value: "?0" },
          { header: "sec-ch-ua-platform", operation: "set", value: '"Windows"' },
          { header: "sec-ch-ua-full-version-list", operation: "remove" },
          { header: "sec-ch-ua-full-version", operation: "remove" },
          { header: "sec-gpc", operation: "remove" },
        ],
      },
      condition: {
        requestDomains: DOMINIOS,
        resourceTypes: ["main_frame", "sub_frame", "xmlhttprequest", "script", "stylesheet",
                        "image", "font", "media", "ping", "websocket", "other"],
      },
    }],
  });
}

// ---------- lista: toda escrita passa por esta fila, para duas correntes não se atropelarem ----------
let fila = Promise.resolve();

function alterarItens(alterar) {
  fila = fila
    .then(async () => {
      const { itens = [] } = await chrome.storage.local.get("itens");
      await chrome.storage.local.set({ itens: alterar(itens) });
    })
    .catch((e) => console.error("[snet-bypass] falha ao gravar a lista:", e));
  return fila;
}

function atualizar(id, campos) {
  return alterarItens((itens) => itens.map((i) => (i.id === id ? { ...i, ...campos } : i)));
}

// ---------- host ----------
function motivoDaDesconexao(motivo) {
  const m = motivo.toLowerCase();
  if (m.includes("not found")) return "O componente local não está instalado. Execute o instalador do Ad Blogs Bypass Companion e tente novamente.";
  if (m.includes("forbidden")) return "O componente local não autorizou esta extensão. Reinstale o Ad Blogs Bypass Companion.";
  if (m.includes("exited")) return "O componente local foi encerrado antes de responder.";
  if (m.includes("failed to start")) return "O componente local não pôde ser iniciado. Reinstale o Ad Blogs Bypass Companion.";
  return "Falha de comunicação com o componente local.";
}

function resolver(item) {
  let terminou = false;
  const porta = chrome.runtime.connectNative(HOST);
  porta.onMessage.addListener((msg) => {
    if (msg.tipo === "progresso") {
      atualizar(item.id, { status: "resolvendo", progresso: { b: msg.b, a: msg.a, host: msg.host } });
    } else if (msg.tipo === "destino") {
      terminou = true;
      if (destinoValido(msg.url)) atualizar(item.id, { status: "ok", destino: msg.url, erro: null });
      else atualizar(item.id, { status: "erro", erro: "O destino recebido não é um endereço válido." });
    } else if (msg.tipo === "erro") {
      terminou = true;
      atualizar(item.id, { status: "erro", erro: msg.texto });
    }
  });
  porta.onDisconnect.addListener(() => {
    if (terminou) return;
    const motivo = (chrome.runtime.lastError && chrome.runtime.lastError.message) || "";
    // o usuário vê só a tradução do erro do navegador
    atualizar(item.id, { status: "erro", erro: motivoDaDesconexao(motivo) });
  });
  porta.postMessage({ nextUrl: item.nextUrl, ua: item.ua });
}

// O nextUrl chega por postMessage da página, e qualquer script dela (anúncios inclusive) poderia postar
// um: só segue para o componente local um https: com ad_id, o formato que o encurtador devolve. Sem isso,
// uma página poderia fazer o componente requisitar endereços arbitrários (127.0.0.1, rede local...).
function nextUrlValido(url) {
  try {
    const u = new URL(url);
    return u.protocol === "https:" && u.searchParams.has("ad_id");
  } catch (e) {
    return false;
  }
}

function destinoValido(url) {
  try {
    return ["https:", "http:"].includes(new URL(url).protocol);
  } catch (e) {
    return false;
  }
}

// Fecha a aba do encurtador antes do CONTINUAR, que leva ao anúncio. Se ela for a única da janela,
// fechar a aba fecharia a janela — e, sendo a última, o Brave inteiro, derrubando a resolução.
// Nesse caso abre antes uma aba nova (página inicial) na mesma janela.
async function fecharAbaDoEncurtador(aba) {
  const daJanela = await chrome.tabs.query({ windowId: aba.windowId });
  if (daJanela.length <= 1) await chrome.tabs.create({ windowId: aba.windowId, active: true });
  await chrome.tabs.remove(aba.id);
}

// ---------- mensagens da ponte e do popup ----------
chrome.runtime.onMessage.addListener((msg, sender) => {
  if (msg.tipo === "capturado" && sender.tab) {
    if (!nextUrlValido(msg.nextUrl)) {
      console.warn("[snet-bypass] nextUrl ignorado (não é https com ad_id):", msg.nextUrl);
      return;
    }
    fecharAbaDoEncurtador(sender.tab).catch((e) => console.error("[snet-bypass] falha ao fechar a aba:", e));
    const item = {
      id: crypto.randomUUID(), link: msg.link, nextUrl: msg.nextUrl, ua: msg.ua, capturado: Date.now(),
      status: "resolvendo", progresso: null, destino: null, erro: null,
    };
    alterarItens((itens) => [item, ...itens]).then(() => resolver(item));
  } else if (msg.tipo === "tentar") {
    chrome.storage.local.get("itens").then(({ itens = [] }) => {
      const item = itens.find((i) => i.id === msg.id);
      if (!item || item.status !== "erro" || Date.now() - item.capturado >= VALIDADE_MS) return;
      atualizar(item.id, { status: "resolvendo", progresso: null, erro: null }).then(() => resolver(item));
    });
  } else if (msg.tipo === "apagar") {
    alterarItens((itens) => itens.filter((i) => i.id !== msg.id));
  } else if (msg.tipo === "limpar") {
    alterarItens(() => []);
  }
});

// ---------- início do service worker ----------
function garantirCabecalhos() {
  esconderBraveNosCabecalhos().catch((e) =>
    console.error("[snet-bypass] sem a regra de cabeçalhos o site recusa o Brave:", e));
}
garantirCabecalhos();
// A regra dinâmica persiste, mas o MAJOR muda quando o Brave atualiza, e o onMessage só acorda o worker
// depois do captcha, tarde demais. O onStartup (e o onInstalled) acorda o worker antes de qualquer página
// carregar e renova a regra.
chrome.runtime.onStartup.addListener(garantirCabecalhos);
chrome.runtime.onInstalled.addListener(garantirCabecalhos);

// Instalar ou recarregar a extensão deixa órfãos os scripts das abas do encurtador já abertas: o
// captcha seria resolvido e o nextUrl não chegaria aqui. Recarregar essas abas dá a elas os scripts novos.
// tabs.query por URL funciona sem a permissão "tabs", porque a extensão tem host_permissions nesses domínios.
async function recarregarAbasDoEncurtador() {
  const padroes = DOMINIOS.flatMap((d) => [`https://${d}/*`, `https://www.${d}/*`]);
  for (const aba of await chrome.tabs.query({ url: padroes })) {
    chrome.tabs.reload(aba.id).catch(() => {});
  }
}
chrome.runtime.onInstalled.addListener(() => {
  recarregarAbasDoEncurtador().catch((e) => console.error("[snet-bypass] falha ao recarregar as abas:", e));
});

// Um service worker que (re)inicia não tem nenhuma conexão viva: o que estava "resolvendo" morreu.
alterarItens((itens) => itens.map((i) => (i.status === "resolvendo"
  ? { ...i, status: "erro", erro: "Interrompido: a extensão foi reiniciada durante a resolução." }
  : i)));

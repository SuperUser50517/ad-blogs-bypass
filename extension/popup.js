// Ad Blogs Bypass — popup: o bloco de notas dos destinos.
// Só lê a lista; toda alteração vai ao background, que grava numa fila única.
"use strict";

const VALIDADE_MS = 30 * 60 * 1000; // o ad_id vale 30 min

// Ícones (traços no estilo Lucide). Constantes: nenhum dado do usuário passa por innerHTML.
const ICONES = {
  logo: '<path d="M10 13a5 5 0 0 0 7.54.54l3-3a5 5 0 0 0-7.07-7.07l-1.72 1.71"/><path d="M14 11a5 5 0 0 0-7.54-.54l-3 3a5 5 0 0 0 7.07 7.07l1.71-1.71"/>',
  abas: '<rect x="2" y="4" width="20" height="16" rx="2"/><path d="M2 9h20"/><path d="M7 4v5"/><path d="M12 4v5"/>',
  prancheta: '<rect x="8" y="2" width="8" height="4" rx="1"/><path d="M16 4h2a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2h2"/><path d="M9 12h6"/><path d="M9 16h6"/>',
  baixar: '<path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><path d="m7 10 5 5 5-5"/><path d="M12 15V3"/>',
  lixeira: '<path d="M3 6h18"/><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6"/><path d="M8 6V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/>',
  copiar: '<rect x="8" y="8" width="14" height="14" rx="2"/><path d="M4 16a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h10a2 2 0 0 1 2 2"/>',
  abrir: '<path d="M15 3h6v6"/><path d="M10 14 21 3"/><path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6"/>',
  certo: '<path d="M20 6 9 17l-5-5"/>',
  alerta: '<circle cx="12" cy="12" r="10"/><path d="M12 8v4"/><path d="M12 16h.01"/>',
  girar: '<path d="M21 12a9 9 0 1 1-6.22-8.56"/>',
  refazer: '<path d="M3 12a9 9 0 1 0 9-9 9.75 9.75 0 0 0-6.74 2.74L3 8"/><path d="M3 3v5h5"/>',
  subir: '<circle cx="12" cy="12" r="10"/><path d="m16 12-4-4-4 4"/><path d="M12 16V8"/>',
  caixa: '<path d="M22 12h-6l-2 3h-4l-2-3H2"/><path d="M5.45 5.11 2 12v6a2 2 0 0 0 2 2h16a2 2 0 0 0 2-2v-6l-3.45-6.89A2 2 0 0 0 16.76 4H7.24a2 2 0 0 0-1.79 1.11z"/>',
};

const $ = (seletor) => document.querySelector(seletor);
let itens = [];
const errosAbertos = new Set(); // ids com a mensagem de erro expandida, para sobreviver ao redesenho

function icone(nome, classe = "ico") {
  const span = document.createElement("span");
  span.className = classe;
  span.innerHTML = `<svg viewBox="0 0 24 24" aria-hidden="true">${ICONES[nome]}</svg>`;
  return span;
}

function el(tag, classe, texto) {
  const e = document.createElement(tag);
  if (classe) e.className = classe;
  if (texto != null) e.textContent = texto;
  return e;
}

function botaoIcone(nome, titulo, aoClicar, classe = "") {
  const b = el("button", `botao-ico ${classe}`.trim());
  b.type = "button";
  b.title = titulo;
  b.setAttribute("aria-label", titulo);
  b.append(icone(nome));
  b.addEventListener("click", aoClicar);
  return b;
}

function tempoRelativo(ms) {
  const minutos = Math.floor((Date.now() - ms) / 60000);
  if (minutos < 1) return "agora";
  if (minutos < 60) return `há ${minutos} min`;
  const horas = Math.floor(minutos / 60);
  if (horas < 24) return `há ${horas} h`;
  const d = new Date(ms);
  return `${d.toLocaleDateString("pt-BR", { day: "2-digit", month: "2-digit" })} ${d.toLocaleTimeString("pt-BR", { hour: "2-digit", minute: "2-digit" })}`;
}

function semEsquema(url) {
  try {
    const u = new URL(url);
    return (u.host + u.pathname).replace(/\/$/, "") + u.search + u.hash;
  } catch (e) {
    return url;
  }
}

let temporizadorAviso;
function avisar(texto) {
  const aviso = $("#aviso");
  aviso.textContent = texto;
  aviso.classList.add("visivel");
  clearTimeout(temporizadorAviso);
  temporizadorAviso = setTimeout(() => aviso.classList.remove("visivel"), 1600);
}

async function copiar(texto, botao, mensagem = "Copiado") {
  try {
    await navigator.clipboard.writeText(texto);
  } catch (e) {
    avisar("Não foi possível copiar.");
    return;
  }
  avisar(mensagem);
  if (botao) {
    const original = botao.firstChild;
    botao.classList.add("feito");
    botao.replaceChild(icone("certo"), original);
    setTimeout(() => { botao.classList.remove("feito"); botao.replaceChild(original, botao.firstChild); }, 1200);
  }
}

function abrir(url, ativa = true) {
  chrome.tabs.create({ url, active: ativa });
}

function enviar(msg) {
  chrome.runtime.sendMessage(msg);
}

// ---------- cartões ----------
function cartao(item) {
  const c = el("article", `cartao ${item.status}`);
  const cabeca = el("div", "cabeca");
  const botoes = el("div", "botoes");

  if (item.status === "ok") {
    const selo = el("span", "selo");
    selo.append(icone("certo"), document.createTextNode("Pronto"));
    let host = "";
    try { host = new URL(item.destino).host; } catch (e) {}
    cabeca.append(selo, el("span", "titulo", host));
    botoes.append(
      botaoIcone("copiar", "Copiar destino", (ev) => copiar(item.destino, ev.currentTarget)),
      botaoIcone("abrir", "Abrir em nova aba", () => abrir(item.destino)),
    );
  } else if (item.status === "resolvendo") {
    const selo = el("span", "selo");
    selo.append(icone("girar", "ico girando"), document.createTextNode("Resolvendo"));
    const p = item.progresso;
    cabeca.append(selo, el("span", "titulo", p ? `etapa ${p.b} de ${p.a}` : "iniciando…"));
  } else {
    const selo = el("span", "selo");
    selo.append(icone("alerta"), document.createTextNode("Erro"));
    cabeca.append(selo, el("span", "titulo", ""));
  }
  botoes.append(botaoIcone("lixeira", "Apagar item", () => enviar({ tipo: "apagar", id: item.id }), "apagar"));
  cabeca.append(botoes);
  c.append(cabeca);

  if (item.status === "ok") {
    const destino = el("a", "destino", semEsquema(item.destino));
    destino.href = item.destino;
    destino.title = item.destino;
    destino.addEventListener("click", (ev) => { ev.preventDefault(); abrir(item.destino); });
    c.append(destino);
  } else if (item.status === "resolvendo") {
    const p = item.progresso;
    const total = p && Number.isInteger(p.a) ? p.a : 6;
    const feitos = p ? p.b : 0;
    const barra = el("div", "progresso");
    barra.style.setProperty("--total", total);
    for (let i = 1; i <= total; i++) {
      barra.append(el("span", i <= feitos ? "feito" : i === feitos + 1 ? "atual" : ""));
    }
    c.append(barra);
  } else {
    const erro = el("p", "mensagem-erro", item.erro || "Erro sem detalhe.");
    erro.title = "Clique para ver a mensagem completa";
    erro.classList.toggle("aberta", errosAbertos.has(item.id));
    erro.addEventListener("click", () => {
      if (erro.classList.toggle("aberta")) errosAbertos.add(item.id);
      else errosAbertos.delete(item.id);
    });
    c.append(erro);
    const restante = VALIDADE_MS - (Date.now() - item.capturado);
    if (restante > 0 && !item.definitivo) { // definitivo: o site já recusou este link; só um captcha novo resolve
      const tentar = el("button", "tentar");
      tentar.type = "button";
      tentar.append(icone("refazer"), el("span", null, "Tentar de novo"),
        el("small", null, `· válido por mais ${Math.max(1, Math.round(restante / 60000))} min`));
      tentar.addEventListener("click", () => { tentar.disabled = true; enviar({ tipo: "tentar", id: item.id }); });
      c.append(tentar);
    }
  }

  const rodape = el("div", "rodape");
  const origem = el("span", "origem", semEsquema(item.link));
  origem.title = item.link;
  rodape.append(origem, el("span", null, "·"), el("span", "hora", tempoRelativo(item.capturado)));
  c.append(rodape);
  return c;
}

// ---------- tela ----------
function prontos() {
  return itens.filter((i) => i.status === "ok" && i.destino);
}

function desenhar() {
  const ok = prontos().length;
  const andamento = itens.filter((i) => i.status === "resolvendo").length;
  const erros = itens.filter((i) => i.status === "erro").length;
  const partes = [];
  if (ok) partes.push(`${ok} ${ok === 1 ? "pronto" : "prontos"}`);
  if (andamento) partes.push(`resolvendo ${andamento} ${andamento === 1 ? "link" : "links"}`);
  if (erros) partes.push(`${erros} com erro`);
  $("#resumo").textContent = partes.length ? partes.join(" · ") : "Nenhum link";

  for (const id of ["#abrir-todos", "#copiar-todos", "#exportar"]) $(id).disabled = ok === 0;
  $("#limpar").disabled = itens.length === 0;

  const lista = $("#lista");
  lista.replaceChildren(...itens.map(cartao));
  lista.hidden = itens.length === 0;
  $("#vazio").hidden = itens.length !== 0;
}

function exportar() {
  const texto = prontos().map((i) => i.destino).join("\r\n") + "\r\n";
  const d = new Date();
  const dois = (n) => String(n).padStart(2, "0");
  const nome = `destinos-${d.getFullYear()}-${dois(d.getMonth() + 1)}-${dois(d.getDate())}-${dois(d.getHours())}${dois(d.getMinutes())}.txt`;
  const url = URL.createObjectURL(new Blob([texto], { type: "text/plain;charset=utf-8" }));
  const a = el("a");
  a.href = url;
  a.download = nome;
  a.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
  avisar(`${prontos().length} ${prontos().length === 1 ? "destino exportado" : "destinos exportados"}`);
}

// ---------- versão nova ----------
// Consulta o último release no GitHub no máximo uma vez por dia (a API aceita 60 consultas/h sem login).
// Falha de rede não grava nada: tenta de novo na próxima abertura, sem erro na tela.
const API_RELEASE = "https://api.github.com/repos/joaomgabaldi/ad-blogs-bypass/releases/latest";
const PAGINA_RELEASE = "https://github.com/joaomgabaldi/ad-blogs-bypass/releases/latest";
const INTERVALO_VERSAO_MS = 24 * 60 * 60 * 1000;
let versao = {}; // { verificado, ultima, dispensada }

function maisNova(a, b) { // por número: 2.0.10 > 2.0.9
  const x = a.split(".").map(Number), y = b.split(".").map(Number);
  for (let i = 0; i < Math.max(x.length, y.length); i++) {
    const d = (x[i] || 0) - (y[i] || 0);
    if (d) return d > 0;
  }
  return false;
}

function mostrarVersao() {
  const nova = versao.ultima && versao.ultima !== versao.dispensada
    && maisNova(versao.ultima, chrome.runtime.getManifest().version);
  $("#versao-numero").textContent = nova ? versao.ultima : "";
  $("#versao-nova").hidden = !nova;
}

async function verificarVersao() {
  versao = (await chrome.storage.local.get("versao")).versao || {};
  if (!(Date.now() - (versao.verificado || 0) < INTERVALO_VERSAO_MS)) {
    try {
      const r = await fetch(API_RELEASE, { headers: { accept: "application/vnd.github+json" } });
      const tag = r.ok ? String((await r.json()).tag_name).replace(/^v/, "") : "";
      if (/^\d+(\.\d+)*$/.test(tag)) {
        versao = { ...versao, verificado: Date.now(), ultima: tag };
        await chrome.storage.local.set({ versao });
      }
    } catch (e) {}
  }
  mostrarVersao();
}

$(".versao-link").addEventListener("click", () => abrir(PAGINA_RELEASE));
$("#fechar-versao").addEventListener("click", () => {
  versao = { ...versao, dispensada: versao.ultima };
  chrome.storage.local.set({ versao });
  mostrarVersao();
});
verificarVersao();

// ---------- ligações ----------
document.querySelectorAll("[data-icone]").forEach((alvo) => {
  alvo.innerHTML = `<svg viewBox="0 0 24 24" aria-hidden="true">${ICONES[alvo.dataset.icone]}</svg>`;
});
$(".logo").innerHTML = `<svg viewBox="0 0 24 24" aria-hidden="true">${ICONES.logo}</svg>`;

$("#abrir-todos").addEventListener("click", () => {
  const lista = prontos();
  lista.forEach((i) => abrir(i.destino, false));
  avisar(`${lista.length} ${lista.length === 1 ? "aba aberta" : "abas abertas"}`);
});
$("#copiar-todos").addEventListener("click", () => {
  const lista = prontos();
  copiar(lista.map((i) => i.destino).join("\n"), null,
    `${lista.length} ${lista.length === 1 ? "destino copiado" : "destinos copiados"}`);
});
$("#exportar").addEventListener("click", exportar);
$("#limpar").addEventListener("click", () => { $("#confirmacao").hidden = false; });
$("#cancelar-limpeza").addEventListener("click", () => { $("#confirmacao").hidden = true; });
$("#confirmar-limpeza").addEventListener("click", () => {
  $("#confirmacao").hidden = true;
  enviar({ tipo: "limpar" });
});

chrome.storage.onChanged.addListener((mudancas, area) => {
  if (area === "local" && mudancas.itens) {
    itens = mudancas.itens.newValue || [];
    desenhar();
  }
});
chrome.storage.local.get("itens").then(({ itens: salvos = [] }) => {
  itens = salvos;
  desenhar();
});
setInterval(desenhar, 30000); // "há N min" e a validade do "tentar de novo" andam sozinhos

'use strict';

/* ---------- utilidades ---------- */
const $ = (s, r = document) => r.querySelector(s);
const esc = (s) => String(s ?? '').replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
const NUM = new Intl.NumberFormat('pt-BR');
const fmt = (n) => NUM.format(Math.round(n || 0));
const CORES = ['#7f77dd', '#f0a830', '#3ccf8e', '#ed93b1', '#5dcaa5', '#85b7eb', '#f0997b', '#c0dd97'];
const ESTADOS = {
  farmando: 'Farmando', iniciando: 'Iniciando…', precisa_entrar: 'Precisa entrar',
  pausada: 'Pausada', sem_canais: 'Sem canais', erro: 'Com erro', parada: 'Parada',
  bloqueada: 'Precisa do Lunar Premium',
};
const MOTIVOS = {
  WATCH: 'assistindo', CLAIM: 'baú de bônus', WATCH_STREAK: 'sequência de lives',
  RAID: 'raid', FOLLOW: 'seguiu o canal', PREDICTION: 'previsão', REFUND: 'previsão devolvida',
};

function horas(seg) {
  const m = Math.round((seg || 0) / 60);
  if (m < 60) return `${m}min`;
  const h = Math.floor(m / 60);
  return m % 60 ? `${h}h ${String(m % 60).padStart(2, '0')}min` : `${h}h`;
}
function abreviar(v) {
  if (v >= 1e6) return `${NUM.format(+(v / 1e6).toFixed(1))} mi`;
  if (v >= 1e3) return `${NUM.format(+(v / 1e3).toFixed(1))} mil`;
  return fmt(v);
}
function topoBonito(v) {
  const p = 10 ** Math.floor(Math.log10(v));
  return [1, 2, 2.5, 5, 10].map((m) => m * p).find((x) => x >= v);
}
const capital = (s) => s.charAt(0).toUpperCase() + s.slice(1);
function setHTML(el, html) {
  if (el && el._html !== html) { el.innerHTML = html; el._html = html; }
}

const ICONES = {
  resumo: '<path d="M4 20V11M10 20V5M16 20v-6M21 20H3"/>',
  historico: '<circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/>',
  celular: '<rect x="7" y="2.5" width="10" height="19" rx="2"/><path d="M11 18h2"/>',
  opcoes: '<path d="M4 7h10M18 7h2M4 17h4M12 17h8"/><circle cx="16" cy="7" r="2"/><circle cx="10" cy="17" r="2"/>',
  mais: '<path d="M12 5v14M5 12h14"/>',
  pausa: '<path d="M8 5v14M16 5v14"/>',
  play: '<path d="M7 4.5l12 7.5-12 7.5z"/>',
  refazer: '<path d="M20 12a8 8 0 1 1-2.4-5.7L20 8.5"/><path d="M20 3.5v5h-5"/>',
  lixo: '<path d="M4 7h16M10 11v6M14 11v6M5.5 7l1 13h11l1-13M9 7V4h6v3"/>',
  cima: '<path d="M12 19V5M6 11l6-6 6 6"/>',
  baixo: '<path d="M12 5v14M6 13l6 6 6-6"/>',
  x: '<path d="M6 6l12 12M18 6L6 18"/>',
  copiar: '<rect x="9" y="9" width="11" height="11" rx="2"/><path d="M5 15V6a2 2 0 0 1 2-2h8"/>',
  abrir: '<path d="M14 4h6v6M20 4l-9 9M18 14v5a1 1 0 0 1-1 1H5a1 1 0 0 1-1-1V7a1 1 0 0 1 1-1h5"/>',
  tv: '<rect x="3" y="6" width="18" height="13" rx="2"/><path d="M8 2.5l4 3.5 4-3.5"/>',
  loja: '<path d="M5 8h14l-1.2 12H6.2z"/><path d="M9 10V7a3 3 0 0 1 6 0v3"/>',
  moeda: '<circle cx="12" cy="12" r="8.5"/><path d="M12 7.5a4.5 4.5 0 0 1 4.5 4.5"/>',
  raio: '<path d="M13 2.5L5 13.5h6l-1 8 8-11h-6z"/>',
  estrela: '<path d="M12 3.5l2.6 5.3 5.9.9-4.3 4.1 1 5.8L12 16.9l-5.2 2.7 1-5.8-4.3-4.1 5.9-.9z"/>',
  relogio: '<circle cx="12" cy="12" r="8.5"/><path d="M12 7.5V12l3 2"/>',
  coroa: '<path d="M3.5 8.5l4.5 4 4-6.5 4 6.5 4.5-4-1.8 10H5.3z"/>',
  presente: '<rect x="3.5" y="8" width="17" height="4.5" rx="1"/><path d="M5.5 12.5V20h13v-7.5M12 8v12M12 8C10.5 4.5 7 4.5 7 6.6 7 8 9.5 8 12 8zM12 8c1.5-3.5 5-3.5 5-1.4C17 8 14.5 8 12 8z"/>',
  ajuda: '<circle cx="12" cy="12" r="9"/><path d="M9.6 9.4a2.5 2.5 0 0 1 4.8.9c0 1.7-2.4 2.1-2.4 3.6"/><path d="M12 17.2h.01"/>',
  cadeado: '<rect x="5" y="11" width="14" height="10" rx="2"/><path d="M8 11V8a4 4 0 0 1 8 0v3"/>',
  lampada: '<path d="M9 18h6M10 21h4M12 3a6 6 0 0 0-3.5 10.9c.6.5 1 1.2 1 2V16h5v-.1c0-.8.4-1.5 1-2A6 6 0 0 0 12 3z"/>',
  energia: '<path d="M12 3v8"/><path d="M6.6 6.6a8 8 0 1 0 10.8 0"/>',
};
const ic = (n) => `<svg class="i" viewBox="0 0 24 24" aria-hidden="true">${ICONES[n]}</svg>`;

function toast(msg, erro) {
  if (!msg) return;
  const t = document.createElement('div');
  t.className = `toast${erro ? ' erro' : ''}`;
  t.textContent = msg;
  $('#toasts').appendChild(t);
  setTimeout(() => t.remove(), 3800);
}

async function copiar(texto) {
  try {
    await navigator.clipboard.writeText(texto);
  } catch (e) {
    const ta = document.createElement('textarea');
    ta.value = texto;
    document.body.appendChild(ta);
    ta.select();
    document.execCommand('copy');
    ta.remove();
  }
  toast('Copiado');
}

function abrirLink(url) {
  if (S.estado?.local) api('/api/abrir', 'POST', { url }).catch((e) => toast(e.message, true));
  else window.open(url, '_blank');
}

/* ---------- API ---------- */
const S = { estado: null, view: null, offline: false };
// Versão desta página (o ?v= do app.js). Se o app for atualizado, a janela recarrega sozinha.
const MEU_CARIMBO = new URL(document.currentScript.src).searchParams.get('v');

async function api(caminho, metodo = 'GET', corpo) {
  let r;
  try {
    r = await fetch(caminho, {
      method: metodo,
      headers: corpo ? { 'Content-Type': 'application/json' } : {},
      body: corpo ? JSON.stringify(corpo) : undefined,
    });
  } catch (e) {
    throw Object.assign(new Error('Sem conexão com o Lunar Farm'), { offline: true });
  }
  if (r.status === 401) { telaPin(); throw new Error('pin'); }
  if (r.status === 402) {
    let motivo = 'menu';
    try { motivo = (await r.json()).premium || motivo; } catch (e) { /* sem corpo */ }
    Premium.abrir(motivo);
    throw Object.assign(new Error(''), { premium: true });
  }
  let dados = {};
  try { dados = await r.json(); } catch (e) { /* resposta vazia */ }
  if (!r.ok) throw new Error(dados.erro || `Algo deu errado (${r.status})`);
  return dados;
}

const conta = (login) => S.estado?.contas.find((c) => c.login === login);
// Quantas lives cada conta farma ao mesmo tempo: 2 no Lunar Premium, 1 na versão grátis.
const lives = () => S.estado?.premium?.limites?.lives || 2;
const textoLives = () => `${lives()} por vez`;
function linhaLives(resto) {
  if (lives() > 1) return `${lives()} lives por conta · ${resto}`;
  return `1 live por conta · ${resto}`;
}
function cor(login) {
  const i = (S.estado?.contas || []).findIndex((c) => c.login === login);
  return i < 0 ? '#4a4370' : CORES[i % CORES.length];
}

/* ---------- rotas ---------- */
const VIEWS = {};
function rota() {
  const h = location.hash.replace(/^#\/?/, '') || 'resumo';
  return h.split('/').map(decodeURIComponent);
}
function montar() {
  const [nome, arg] = rota();
  const V = VIEWS[nome] || VIEWS.resumo;
  S.view = V;
  const el = $('#conteudo');
  el.scrollTop = 0;
  el.innerHTML = '<div id="faixa"></div><div class="pagina"></div>';
  V.montar($('.pagina', el), arg);
  desenharLado();
  desenharFaixa();
}

/* ---------- versão nova (faixa no topo) ---------- */
function desenharFaixa() {
  const el = $('#faixa');
  const a = S.estado?.atualizacao;
  if (!el) return;
  let html = '';
  if (a?.nova && a.fase !== 'nada') {
    const v = esc(a.nova.versao);
    const novidades = a.nova.novidades?.length
      ? `<ul>${a.nova.novidades.slice(0, 4).map((n) => `<li>${esc(n)}</li>`).join('')}</ul>` : '';
    if (a.fase === 'disponivel') {
      html = `<div class="faixa"><div><b>Saiu a versão ${v} do Lunar Farm</b> <span class="sub">(você está na ${esc(a.atual)})</span>${novidades}</div>
        ${S.estado.local ? `<button class="btn primario" data-acao="atualizar" type="button">${ic('refazer')} Atualizar agora</button>` : '<span class="sub">Atualize pelo PC</span>'}</div>`;
    } else if (a.fase === 'baixando') {
      html = `<div class="faixa"><div><b>Baixando a versão ${v}…</b><div class="barra"><i style="width:${a.progresso}%"></i></div></div><span class="sub">${a.progresso}%</span></div>`;
    } else if (a.fase === 'instalando') {
      html = `<div class="faixa"><div class="esperando"><span class="roda"></span> <span><b>Instalando a versão ${v}.</b> O Lunar Farm fecha e abre de novo sozinho em menos de 1 minuto. As contas continuam conectadas.</span></div></div>`;
    } else if (a.fase === 'erro') {
      html = `<div class="faixa erro"><div><b>Não deu para atualizar para a versão ${v}.</b> ${esc(a.erro || '')}</div>
        ${S.estado.local ? '<button class="btn" data-acao="atualizar" type="button">Tentar de novo</button>' : ''}</div>`;
    }
  }
  setHTML(el, html);
}

function atualizarApp() {
  Versao.adiada = null;
  Versao.abrirAtualizar();
}

/* ---------- janelas de versão: atualização disponível, novidades e histórico ---------- */
const listaNovidades = (itens) => `<ul class="nv-lista">${(itens || []).map((n) => `<li>${esc(n)}</li>`).join('')}</ul>`;
const dataVersao = (d) => (d ? new Date(`${d}T12:00:00`).toLocaleDateString('pt-BR', { day: 'numeric', month: 'long', year: 'numeric' }) : '');
const topoVersao = (selo, titulo, sub, verde) => `
  <div class="vc-topo"><img src="/static/icon-192.png" alt="">
    <div><span class="vc-selo${verde ? ' verde' : ''}">${selo}</span><h2>${titulo}</h2><p class="sub">${sub}</p></div></div>`;

const Versao = {
  // "Agora não" vale até fechar a janela do app (ao abrir de novo, ela avisa outra vez).
  get adiada() { try { return sessionStorage.getItem('lunar-adiada'); } catch (e) { return this._adiada; } },
  set adiada(v) {
    this._adiada = v;
    try { if (v) sessionStorage.setItem('lunar-adiada', v); else sessionStorage.removeItem('lunar-adiada'); } catch (e) { /* sem storage */ }
  },
  novidadesAbertas: false,
  aberta: (nome) => $(`#modal [data-janela="${nome}"]`),

  // A cada ciclo: abre sozinha quando sai versão nova ou quando o app acabou de ser atualizado.
  conferir() {
    const e = S.estado;
    if (!e || S.offline) return;
    if (this.aberta('atualizar')) { this.desenharAtualizar(); return; }
    if ($('#modal').innerHTML) return;  // não passa por cima de outra janela
    const a = e.atualizacao;
    if (e.local && a?.nova && a.fase === 'disponivel' && this.adiada !== a.nova.versao) this.abrirAtualizar();
  },

  abrirAtualizar() {
    if (!S.estado?.atualizacao?.nova) return;
    $('#modal').innerHTML = '<div class="caixa versao-caixa" data-janela="atualizar"></div>';
    this.desenharAtualizar();
  },

  desenharAtualizar() {
    const caixa = this.aberta('atualizar');
    const a = S.estado.atualizacao;
    if (!a?.nova || a.fase === 'nada') { $('#modal').innerHTML = ''; return; }
    if (a.fase === 'baixando' && caixa.dataset.fase === 'baixando') {
      // Só anda a barra (sem redesenhar a janela toda).
      $('.vc-barra i', caixa).style.width = `${a.progresso}%`;
      $('#vc-pct', caixa).textContent = `${a.progresso}%`;
      return;
    }
    if (caixa.dataset.fase === a.fase) return;
    caixa.dataset.fase = a.fase;
    const v = esc(a.nova.versao);
    const mb = a.nova.tamanho ? ` · ${NUM.format(Math.round(a.nova.tamanho / 1048576))} MB` : '';
    let corpo;
    if (a.fase === 'disponivel') {
      corpo = `
        <div class="vc-rot">O que vem nessa versão</div>
        ${listaNovidades(a.nova.novidades)}
        <p class="vc-nota">O farm para por uns 30 segundos enquanto instala e volta sozinho. Contas, canais e histórico continuam.</p>
        <div class="btns"><button class="btn" data-vs="depois" type="button">Agora não</button>
          <button class="btn primario" data-vs="instalar" type="button">${ic('refazer')} Atualizar agora</button></div>`;
    } else if (a.fase === 'baixando') {
      corpo = `
        <div class="vc-rot">Baixando a versão ${v}… <span id="vc-pct">${a.progresso}%</span></div>
        <div class="vc-barra"><i style="width:${a.progresso}%"></i></div>
        <p class="vc-nota">Pode continuar usando o app. Quando terminar de baixar, ele instala sozinho.</p>`;
    } else if (a.fase === 'instalando') {
      corpo = `
        <div class="esperando vc-esperando"><span class="roda"></span> <span><b>Instalando a versão ${v}.</b> O Lunar Farm fecha e abre de novo sozinho em menos de 1 minuto.</span></div>`;
    } else {
      corpo = `
        <div class="aviso vermelho"><span>${esc(a.erro || 'Não deu para atualizar.')}</span></div>
        <div class="btns"><button class="btn" data-vs="depois" type="button">Fechar</button>
          <button class="btn primario" data-vs="instalar" type="button">${ic('refazer')} Tentar de novo</button></div>`;
    }
    caixa.innerHTML = topoVersao('Atualização disponível', `Lunar Farm ${v}`, `Você está na versão ${esc(a.atual)}${mb}`) + corpo;
  },

  async instalar(botao) {
    botao.disabled = true;
    try {
      await api('/api/atualizacao/instalar', 'POST');
      await ciclo(true);
    } catch (e) { toast(e.message, true); botao.disabled = false; }
  },

  async abrirNovidades() {
    this.novidadesAbertas = true;
    let n;
    try { n = await api('/api/novidades'); } catch (e) { return; }
    if (!n.nao_vistas.length || $('#modal').innerHTML) return;
    const varias = n.nao_vistas.length > 1;
    $('#modal').innerHTML = `
      <div class="caixa versao-caixa" data-janela="novidades">
        ${topoVersao('Atualizado', `Novidades da versão ${esc(n.atual)}`, 'O Lunar Farm foi atualizado. Veja o que mudou:', true)}
        ${n.nao_vistas.map((v) => `${varias ? `<div class="vc-rot">Versão ${esc(v.versao)}</div>` : ''}${listaNovidades(v.itens)}`).join('')}
        <div class="btns"><button class="btn primario" data-vs="visto" type="button">Entendi</button></div>
      </div>`;
  },

  async abrirHistorico() {
    let n;
    try { n = await api('/api/novidades'); } catch (e) { toast(e.message, true); return; }
    $('#modal').innerHTML = `
      <div class="caixa versao-caixa" data-janela="historico">
        ${topoVersao('Histórico', 'O que mudou em cada versão', `Você está na versão ${esc(n.atual)}`)}
        ${n.versoes.map((v) => `
          <div class="vc-versao">
            <div class="vc-cab"><b>Versão ${esc(v.versao)}</b>${v.versao === n.atual ? '<span class="vc-selo verde">a sua</span>' : ''}<span class="sub">${esc(dataVersao(v.data))}</span></div>
            ${listaNovidades(v.itens)}
          </div>`).join('')}
        <div class="btns"><button class="btn" data-vs="fechar" type="button">Fechar</button></div>
      </div>`;
  },
};

$('#modal').addEventListener('click', (ev) => {
  const b = ev.target.closest('[data-vs]');
  if (!b) return;
  const acao = b.dataset.vs;
  if (acao === 'instalar') { Versao.instalar(b); return; }
  if (acao === 'depois') Versao.adiada = S.estado?.atualizacao?.nova?.versao || null;
  if (acao === 'visto') api('/api/novidades/vistas', 'POST').catch(() => {});
  $('#modal').innerHTML = '';
});
window.addEventListener('hashchange', montar);

function desenharLado() {
  const e = S.estado;
  if (!e) return;
  const [nome, arg] = rota();
  const ativo = (n, a) => (nome === n && (a === undefined || a === arg) ? ' ativo' : '');
  setHTML($('#lado'), `
    <div class="marca"><img src="/static/icon.svg" alt=""><span class="marca-texto"><span class="marca-nome">Lunar Farm</span><span class="marca-sub">TWITCH · KICK FARM</span></span></div>
    <a class="item${ativo('resumo')}${nome in VIEWS ? '' : ' ativo'}" href="#/resumo">${ic('resumo')}<span class="nome">Resumo</span></a>
    ${e.contas.length ? `<a class="item${ativo('loja')}" href="#/loja">${ic('loja')}<span class="nome">Loja</span></a>` : ''}
    <div class="rotulo">Contas</div>
    ${e.contas.map((c) => {
      // Pontos de cada canal são separados; a soma dá ideia de quanto a conta tem guardado.
      const total = (c.canais || []).reduce((s, x) => s + (x.points || 0), 0);
      const dica = `${ESTADOS[c.estado] || ''}\nHoje: +${fmt(c.hoje)} pontos\nSaldo somado nos ${(c.canais || []).length} canais: ${fmt(total)} pontos`;
      return `
      <a class="item${ativo('conta', c.login)}" href="#/conta/${encodeURIComponent(c.login)}" title="${esc(dica)}">
        <span class="dot ${c.estado}"></span><span class="nome">${esc(c.login)}</span>
        <span class="numeros"><span class="hoje">+${fmt(c.hoje)}</span><span class="total">${ic('moeda')}${abreviar(total)}</span></span>
      </a>`;
    }).join('')}
    <button class="item add" data-acao="login">${ic('mais')}<span class="nome">Adicionar conta</span></button>
    <div class="lado-baixo">
      <div class="lado-rodape">LUNAR FARM &nbsp; / &nbsp; ${esc(e.versao || '')}</div>
    </div>`);
}

document.addEventListener('click', (ev) => {
  const b = ev.target.closest('[data-acao="login"]');
  if (b) { ev.preventDefault(); Login.abrir(b.dataset.conta); }
  if (ev.target.closest('[data-acao="atualizar"]')) { ev.preventDefault(); atualizarApp(); }
  const pm = ev.target.closest('[data-acao="premium"]');
  if (pm) { ev.preventDefault(); Premium.abrir(pm.dataset.motivo || 'menu'); }
  if (ev.target.closest('[data-acao="indicar"]')) { ev.preventDefault(); Indicar.abrir(); }
});

/* ---------- pedaços ---------- */
function cartoesResumo(r) {
  const c = r.cartoes || {};
  return `
    <div class="cartao destaque"><div class="r">Hoje</div><div class="v">+${fmt(c.hoje)}<small>pontos</small></div></div>
    <div class="cartao"><div class="r">Últimos 7 dias</div><div class="v">${fmt(c.semana)}</div></div>
    <div class="cartao"><div class="r">Últimos 30 dias</div><div class="v">${fmt(c.mes)}</div></div>
    <div class="cartao"><div class="r">Total farmado</div><div class="v">${fmt(c.total)}</div></div>`;
}

function grafico(serie) {
  const logins = (S.estado?.contas || []).map((c) => c.login);
  const L = 22, G = 8, H = 200, T = 12, B = 26, E = 46;
  const totais = serie.map((d) => Object.values(d.contas).reduce((a, b) => a + b, 0));
  const escala = topoBonito(Math.max(50, ...totais));
  const largura = E + serie.length * (L + G);
  const alto = H - T - B;
  const y = (v) => H - B - (v / escala) * alto;
  let s = '';
  for (const f of [0, 0.5, 1]) {
    s += `<line x1="${E - 4}" x2="${largura}" y1="${y(escala * f)}" y2="${y(escala * f)}" stroke="#2b2547" ${f ? 'stroke-dasharray="3 5"' : ''}/>`;
    s += `<text x="${E - 10}" y="${y(escala * f) + 4}" text-anchor="end">${abreviar(escala * f)}</text>`;
  }
  serie.forEach((d, i) => {
    const x = E + i * (L + G) + G / 2;
    let base = H - B;
    const outras = Object.entries(d.contas).filter(([l]) => !logins.includes(l)).reduce((a, [, v]) => a + v, 0);
    for (const [l, v] of [...logins.map((l) => [l, d.contas[l] || 0]), ['', outras]]) {
      if (!v) continue;
      const h = Math.max(1.5, (v / escala) * alto);
      base -= h;
      s += `<rect x="${x}" y="${base}" width="${L}" height="${h}" rx="2" fill="${l ? cor(l) : '#4a4370'}"/>`;
    }
    const dt = new Date(`${d.dia}T12:00:00`);
    const detalhe = logins.filter((l) => d.contas[l]).map((l) => `${l}: ${fmt(d.contas[l])}`).join('\n');
    s += `<rect x="${x - G / 2}" y="${T}" width="${L + G}" height="${alto}" fill="transparent"><title>${dt.toLocaleDateString('pt-BR')}: ${fmt(totais[i])} pontos${detalhe ? `\n${esc(detalhe)}` : ''}</title></rect>`;
    const doFim = serie.length - 1 - i;
    if (doFim % 5 === 0) {
      s += `<text x="${x + L / 2}" y="${H - 7}" text-anchor="middle">${doFim === 0 ? 'hoje' : `${dt.getDate()}/${dt.getMonth() + 1}`}</text>`;
    }
  });
  return `<svg class="grafico" viewBox="0 0 ${largura} ${H}" role="img" aria-label="Pontos por dia">${s}</svg>`;
}

function legenda() {
  return (S.estado?.contas || []).map((c) => `<span><i style="background:${cor(c.login)}"></i>${esc(c.login)}</span>`).join('');
}

function ranking(top) {
  if (!top?.length) return '<div class="vazio">Os canais aparecem aqui quando começarem a dar pontos.</div>';
  const max = Math.max(1, ...top.map((t) => t.pontos));
  return top.map((t, i) => `
    <div class="rank"><span class="n">${i + 1}</span>
      <div><b>${esc(t.canal)}</b><div class="barra"><i style="width:${Math.max(3, (t.pontos / max) * 100)}%"></i></div></div>
      <div class="p"><b>+${fmt(t.pontos)}</b><span>${horas(t.segundos)} assistidas</span></div>
    </div>`).join('');
}

function porConta(lista) {
  if (!lista?.length) return '<div class="vazio">Ainda sem pontos registrados.</div>';
  return `<div class="linha-conta cab"><span>Conta</span><span>Hoje</span><span>30 dias</span><span>Baús</span><span>Horas</span></div>` +
    lista.map((c) => `
      <div class="linha-conta">
        <span class="quem"><i style="background:${cor(c.conta)}"></i>${esc(c.conta)}</span>
        <span class="ouro">+${fmt(c.hoje)}</span><span>${fmt(c.mes)}</span><span>${fmt(c.baus)}</span><span>${horas(c.segundos)}</span>
      </div>`).join('');
}

function rotuloDia(ts) {
  const d = new Date(ts * 1000);
  const hoje = new Date();
  const ontem = new Date(Date.now() - 864e5);
  if (d.toDateString() === hoje.toDateString()) return 'Hoje';
  if (d.toDateString() === ontem.toDateString()) return 'Ontem';
  return d.toLocaleDateString('pt-BR', { weekday: 'long', day: '2-digit', month: '2-digit' });
}

function itemTempo(e, mostrarConta) {
  const hora = new Date(e.ts * 1000).toLocaleTimeString('pt-BR', { hour: '2-digit', minute: '2-digit' });
  let classe, texto, pts = '';
  if (e.tipo === 'ganho') {
    classe = String(e.motivo || '').startsWith('WATCH_STREAK') ? 'WATCH_STREAK' : e.motivo;
    texto = `${capital(MOTIVOS[classe] || String(e.motivo || '').toLowerCase())} em <b>${esc(e.canal)}</b>`;
    pts = `${e.pontos >= 0 ? '+' : ''}${fmt(e.pontos)}`;
  } else if (e.tipo === 'gasto' && e.pontos < 0) {
    classe = 'WATCH';  // pontos que o jogo devolveu de uma compra
    texto = `Pontos devolvidos: ${esc(e.titulo || 'compra')} em <b>${esc(e.canal)}</b>`;
    pts = `+${fmt(-e.pontos)}`;
  } else if (e.tipo === 'gasto') {
    classe = 'gasto';
    texto = e.titulo ? `Comprou ${esc(e.titulo)} em <b>${esc(e.canal)}</b>` : `Gastou pontos na loja de <b>${esc(e.canal)}</b>`;
    pts = `-${fmt(e.pontos)}`;
  } else {
    classe = e.tipo;
    texto = esc(e.texto);
  }
  return `<div class="ev ev-${esc(classe)}"><span class="ev-hora">${hora}</span><span class="ev-ponto"></span>
    <span class="ev-txt">${mostrarConta ? `<span class="ev-conta">${esc(e.conta)}</span>` : ''}${texto}</span><span class="ev-pts">${pts}</span></div>`;
}

function linhaDoTempo(lista, mostrarConta, limite, comDias) {
  const vistos = new Set();
  const itens = [];
  for (const e of lista) {
    let conta = mostrarConta;
    if (mostrarConta && (e.tipo === 'online' || e.tipo === 'offline')) {
      // Várias contas veem a mesma live abrir: mostra uma vez só.
      const k = `${e.tipo}|${e.canal}|${Math.floor(e.ts / 180)}`;
      if (vistos.has(k)) continue;
      vistos.add(k);
      conta = false;
    }
    itens.push([e, conta]);
    if (limite && itens.length >= limite) break;
  }
  if (!itens.length) return '<div class="vazio">Nada por aqui ainda. Baús, sequências de dias e lives aparecem aqui conforme o farm roda.</div>';
  let html = '';
  let dia = '';
  for (const [e, c] of itens) {
    if (comDias) {
      const d = rotuloDia(e.ts);
      if (d !== dia) { html += `<div class="dia">${esc(d)}</div>`; dia = d; }
    }
    html += itemTempo(e, c);
  }
  return html;
}

function boasVindas() {
  return `
    <section class="card boas">
      <img src="/static/icon-192.png" alt="">
      <h1>Bem-vindo ao Lunar Farm</h1>
      <p>Uma janela só para farmar os pontos de todas as suas contas da Twitch, sem deixar vários Chatterinos abertos.</p>
      <div class="passos">
        <div><b>1. Adicione uma conta</b>Você entra pelo twitch.tv/activate com um código.</div>
        <div><b>2. Coloque os canais</b>Um clique no atalho Lives PokeIdle, ou cole os links das lives.</div>
        <div><b>3. Pronto</b>O farm roda sozinho, até com a janela fechada.</div>
      </div>
      <button class="btn primario grande" data-acao="login">${ic('mais')} Adicionar a primeira conta</button>
    </section>`;
}

/* ---------- Resumo ---------- */
VIEWS.resumo = {
  montar(el) {
    this.el = el;
    this.carregado = 0;
    el.innerHTML = `
      <div class="topo">
        <div><h1>Resumo</h1><div class="sub">Todas as contas juntas</div></div>
        <button class="btn primario" data-acao="login">${ic('mais')} Adicionar conta</button>
      </div>
      <div id="r-boas"></div>
      <div id="r-corpo" style="display:flex;flex-direction:column;gap:18px">
        <div class="cartoes" id="r-cartoes"></div>
        <div class="mini" id="r-mini"></div>
        <section class="card">
          <div class="card-topo"><h2>Farmando agora</h2><span class="sub" id="r-lives"></span></div>
          <div id="r-agora"></div>
        </section>
        <section class="card">
          <div class="card-topo"><h2>Pontos por dia</h2><span class="sub">últimos 30 dias</span></div>
          <div id="r-grafico"></div><div class="legenda" id="r-legenda"></div>
        </section>
        <div class="duas">
          <section class="card"><div class="card-topo"><h2>Canais que mais deram pontos</h2><span class="sub">30 dias</span></div><div id="r-top"></div></section>
          <section class="card"><div class="card-topo"><h2>Por conta</h2><span class="sub">30 dias</span></div><div id="r-contas"></div></section>
        </div>
        <section class="card">
          <div class="card-topo"><h2>Últimos acontecimentos</h2><a href="#/historico">Ver histórico completo</a></div>
          <div id="r-feed"></div>
        </section>
      </div>`;
    this.atualizar(true);
  },
  async atualizar(forcar) {
    const e = S.estado;
    if (!e || !this.el.isConnected) return;
    const vazio = e.contas.length === 0;
    setHTML($('#r-boas'), vazio ? boasVindas() : '');
    $('#r-corpo').style.display = vazio ? 'none' : 'flex';
    if (vazio) return;
    setHTML($('#r-lives'), linhaLives('trocando sozinho quando uma sai do ar'));

    if (forcar || Date.now() - this.carregado > 20000) {
      this.carregado = Date.now();
      try {
        const [r, feed] = await Promise.all([api('/api/resumo'), api('/api/historico?limite=40')]);
        this.r = r;
        setHTML($('#r-cartoes'), cartoesResumo(r));
        setHTML($('#r-grafico'), grafico(r.serie));
        setHTML($('#r-legenda'), legenda());
        setHTML($('#r-top'), ranking(r.top_canais));
        setHTML($('#r-contas'), porConta(r.contas));
        setHTML($('#r-feed'), linhaDoTempo(feed, true, 10));
      } catch (err) { /* tenta de novo no próximo ciclo */ }
    }
    setHTML($('#r-agora'), e.contas.map((c) => {
      const ganhando = c.canais.filter((x) => x.watching);
      const lives = ganhando.length
        ? ganhando.map((x) => `<span class="chip"><b>${esc(x.login)}</b><span class="ouro">+${fmt(x.farmado_hoje)}</span></span>`).join('')
        : `<span class="sub">${esc(porQueSemLive(c))}</span>`;
      return `<a class="agora" href="#/conta/${encodeURIComponent(c.login)}"><span class="quem"><span class="dot ${c.estado}"></span>${esc(c.login)}</span><span class="lives">${lives}</span><span class="sub">${c.ao_vivo} de ${c.canais.length} ao vivo</span></a>`;
    }).join(''));
    const farmando = e.contas.filter((c) => c.estado === 'farmando').length;
    const aoVivo = new Set(e.contas.flatMap((c) => c.canais.filter((x) => x.online).map((x) => x.login))).size;
    const ganhando = e.contas.reduce((a, c) => a + c.assistindo.length, 0);
    setHTML($('#r-mini'), `
      <div>${ic('tv')}<span><b>${farmando}</b> de ${e.contas.length} contas farmando</span></div>
      <div><span class="vivo"></span><span><b>${aoVivo}</b> canais ao vivo agora</span></div>
      <div>${ic('play')}<span><b>${ganhando}</b> lives dando pontos</span></div>
      <div>${ic('historico')}<span><b>${horas(this.r?.segundos)}</b> assistidas em 30 dias</span></div>`);
  },
};

// Botões das listas prontas de canais (lunar/atalhos.json), ex.: "Lives PokeIdle".
function botoesAtalho(classe) {
  return (S.atalhos || []).map((a, i) => `
    <button class="${classe}" type="button" data-atalho="${i}" title="${esc(a.canais.join(', '))}">${ic('raio')} ${esc(a.nome)}</button>`).join('');
}

// O que dizer quando a conta ainda não está ganhando em nenhuma live.
function porQueSemLive(c) {
  if (c.estado === 'farmando') return c.ao_vivo ? 'Escolhendo as lives…' : 'Nenhum canal da lista ao vivo';
  if (c.estado === 'iniciando') return 'Ligando e carregando os canais…';
  return ESTADOS[c.estado] || c.estado;
}

// Etiqueta "Auto" ao lado do canal que tem compra automática ligada.
function autoDoCanal(contaLogin, canal) {
  const regras = (conta(contaLogin)?.auto_compras || []).filter((r) => r.canal === canal);
  if (!regras.length) return '';
  const pausada = regras.every((r) => r.pausada);
  const dica = regras.map((r) => `${r.titulo} (${fmt(r.custo)})${r.pausada ? ` · pausado: ${r.pausada}` : ''}`).join('\n');
  return `<span class="auto-chip${pausada ? ' pausada' : ''}" title="Compra sozinho:\n${esc(dica)}">Auto</span>`;
}

/* ---------- Conta ---------- */
const farmadoAntes = new Map();

function linhaKick(x, i, total, podeSeguir) {
  let status = 'Conferindo…';
  if (x.existe === false) status = 'Não tem canal com esse nome na Kick';
  else if (x.ao_vivo) status = `<span class="vivo">Ao vivo</span>${x.jogo ? ` · ${esc(x.jogo)}` : ''}${x.viewers ? ` · ${fmt(x.viewers)} vendo` : ''}`;
  else if (x.ao_vivo === false) status = 'Offline';
  let farm = '';
  if (x.assistindo && !x.tocando) farm = '<span class="sub">Abrindo a live…</span>';
  else if (x.assistindo && x.rendendo === true) farm = '<span class="pill ganhando">Ganhando pontos</span>';
  else if (x.assistindo && x.rendendo === false) farm = '<span class="pill iniciando" title="A live está tocando, mas a Kick não deu pontos nos últimos 12 min. Se continuar, o Lunar recarrega a live.">Sem pontos</span>';
  else if (x.assistindo) farm = '<span class="pill ganhando" title="Os pontos aparecem na próxima conferência (de 5 em 5 min)">Tocando</span>';
  else if (x.ao_vivo && x.favorito) farm = '<span class="sub ouro">Favorito · entrando…</span>';
  else if (x.ao_vivo) farm = '<span class="sub">Na fila</span>';
  return `
    <div class="canal${x.assistindo ? ' ativo' : ''}">
      <span class="ordem">${i + 1}</span>
      <div class="canal-nome">
        <button class="estrela${x.favorito ? ' ligada' : ''}" type="button" data-kick-estrela="${esc(x.canal)}" aria-pressed="${x.favorito ? 'true' : 'false'}"
          title="${x.favorito ? 'Favorito: quando abrir live, entra na frente. Clique para tirar.' : 'Marcar como favorito: quando abrir live, entra na frente das outras.'}">${ic('estrela')}</button>
        <div class="canal-txt"><span class="canal-linha"><a href="#" data-abrir-kick="${esc(x.canal)}">${esc(x.canal)}</a>${x.existe === false ? ''
          : x.seguido ? '<span class="kick-segue" title="Essa conta já segue o canal na Kick">Seguindo</span>'
          : !podeSeguir ? ''
          : `<button class="kick-seguir" type="button" data-seguir-kick="${esc(x.canal)}" title="Abre o canal numa janela do Edge desta conta (já logada na Kick): é só clicar em Seguir lá. A Kick dá 50 pontos na primeira vez.">+ Seguir (+50)</button>`}</span><span class="canal-jogo">${status}</span></div>
      </div>
      <span class="farm">${farm}</span>
      <span class="num hoje" data-r="ganho">${x.ganho ? `+${fmt(x.ganho)}` : '<span class="apagado">0</span>'}</span>
      <span class="saldo" data-r="saldo">${x.saldo != null ? fmt(x.saldo) : '<span class="apagado">—</span>'}</span>
      <span class="mover">
        <button type="button" title="Subir na prioridade" data-kick-sobe="${i}" ${i === 0 ? 'disabled' : ''}>${ic('cima')}</button>
        <button type="button" title="Descer na prioridade" data-kick-desce="${i}" ${i === total - 1 ? 'disabled' : ''}>${ic('baixo')}</button>
        <button type="button" class="x" title="Tirar da lista da Kick" data-kick-tira="${esc(x.canal)}">${ic('x')}</button>
      </span>
    </div>`;
}

function linhaCanal(contaLogin, c, i, total, rodando, chatSempre) {
  let status = 'Status aparece quando o farm ligar';
  if (c.online === true) status = `<span class="vivo">Ao vivo</span>${c.game ? ` · ${esc(c.game)}` : ''}${c.viewers ? ` · ${fmt(c.viewers)} vendo` : ''}`;
  else if (c.online === false) status = 'Offline';
  let farm = '';
  if (c.watching) farm = '<span class="pill ganhando">Ganhando pontos</span>';
  else if (rodando && c.online && c.favorito) farm = '<span class="sub ouro">Favorito · entrando…</span>';
  else if (rodando && c.online) farm = '<span class="sub">Na fila · no chat</span>';
  else if (rodando && chatSempre) farm = '<span class="sub">No chat</span>';
  // Pisca o número quando entra ponto novo nesse canal.
  const chave = `${contaLogin}|${c.login}`;
  const antes = farmadoAntes.get(chave);
  const subiu = antes !== undefined && c.farmado_total > antes ? ' subiu' : '';
  farmadoAntes.set(chave, c.farmado_total);
  return `
    <div class="canal${c.watching ? ' ativo' : ''}">
      <span class="ordem">${i + 1}</span>
      <div class="canal-nome">
        <button class="estrela${c.favorito ? ' ligada' : ''}" type="button" data-estrela="${esc(c.login)}" aria-pressed="${c.favorito ? 'true' : 'false'}"
          title="${c.favorito ? 'Favorito: quando abrir live, entra na frente. Clique para tirar.' : 'Marcar como favorito: quando abrir live, entra na frente das outras.'}">${ic('estrela')}</button>
        <div class="canal-txt"><span class="canal-linha"><a href="#" data-abrir="${esc(c.login)}">${esc(c.login)}</a>${autoDoCanal(contaLogin, c.login)}</span><span class="canal-jogo">${status}</span></div>
      </div>
      <span class="farm">${farm}</span>
      <span class="num hoje${subiu}" data-r="hoje">${c.farmado_hoje ? `+${fmt(c.farmado_hoje)}` : '<span class="apagado">0</span>'}</span>
      <span class="num total${subiu}" data-r="farmado">${fmt(c.farmado_total)}</span>
      <span class="num gasto" data-r="gasto" title="${c.gasto_hoje ? `Hoje: -${fmt(c.gasto_hoje)}` : 'Nada gasto hoje'}">${c.gasto_total ? `-${fmt(c.gasto_total)}` : '<span class="apagado">0</span>'}</span>
      <span class="saldo" data-r="saldo">${c.points != null ? fmt(c.points) : '<span class="apagado">—</span>'}</span>
      <span class="mover">
        <button title="Subir na prioridade" data-sobe="${i}" ${i === 0 ? 'disabled' : ''}>${ic('cima')}</button>
        <button title="Descer na prioridade" data-desce="${i}" ${i === total - 1 ? 'disabled' : ''}>${ic('baixo')}</button>
        <button class="x" title="Tirar da lista" data-tira="${esc(c.login)}">${ic('x')}</button>
      </span>
    </div>`;
}

VIEWS.conta = {
  montar(el, login) {
    this.el = el;
    this.login = login;
    this.carregado = 0;
    const c = conta(login);
    if (!c) { el.innerHTML = '<div class="vazio">Essa conta não está mais no Lunar Farm.</div>'; return; }
    const outras = S.estado.contas.filter((x) => x.login !== login);
    el.innerHTML = `
      <div class="topo">
        <div class="topo-conta">
          <span class="avatar" style="background:${cor(login)}">${esc(login[0].toUpperCase())}</span>
          <div><h1>${esc(login)}</h1><div id="c-estado"></div></div>
        </div>
        <div class="acoes" id="c-acoes"></div>
      </div>
      <div id="c-aviso"></div>
      <div class="cartoes" id="c-cartoes"></div>
      <section class="card">
        <div class="card-topo"><h2>Ganhando pontos agora</h2><span class="sub" id="c-lives"></span></div>
        <div id="c-assist"></div>
      </section>
      <section class="card">
        <div class="card-topo"><h2>Kick</h2><span class="sub" id="c-kick-sub"></span></div>
        <div id="c-kick"></div>
        <div id="c-kick-config" style="display:none">
          <form class="add" id="c-kick-form" style="margin-top:14px">
            <input id="c-kick-input" placeholder="Canal da Kick: cole o link (kick.com/nome) ou o nome" autocomplete="off">
            <button class="btn" type="submit">${ic('mais')} Adicionar</button>
          </form>
          <div class="ordem-lives" style="margin-top:14px"><span class="sub">Lives da Kick ao mesmo tempo:</span><div class="segmento" id="c-kick-lives"></div>
            <span class="sub">Com 2, a live do canal favorito abre primeiro: é a que a Kick paga direito. A segunda rende de vez em quando e troca de canal se não render.</span></div>
          <div class="add-extra"><button class="btn atalho" type="button" data-kick="twitch">${ic('mais')} Trazer os canais da lista da Twitch</button>
            <span class="sub">Procura cada canal na Kick, com o nome que o streamer usa lá; os que não existem lá ficam de fora.</span></div>
        </div>
        <p class="nota">Na Kick os pontos vêm com a live tocando: <b>+10 a cada 5 min</b>. O Lunar toca as lives escondido, sem som e na menor qualidade, num Microsoft Edge só desta conta, e mostra em cada uma se a Kick está dando os pontos. Para o bônus do PokeIdle valer, vincule a Kick no jogo (Bônus na Kick).</p>
      </section>
      <section class="card">
        <div class="card-topo"><h2>Canais</h2><span class="sub" id="c-qtd"></span></div>
        <form class="add" id="c-form">
          <input id="c-input" placeholder="Cole o link da live (twitch.tv/nome) ou o nome. Pode colar vários de uma vez." autocomplete="off">
          <button class="btn primario" type="submit">${ic('mais')} Adicionar</button>
        </form>
        <div class="add-extra">
          <span class="atalhos" id="c-atalhos"></span>
          ${S.estado.local ? '<button class="btn leve" id="c-chatterino" type="button">Importar canais do Chatterino</button>' : ''}
          ${outras.length ? `<select id="c-copiar"><option value="">Copiar canais de outra conta…</option>${outras.map((x) => `<option value="${esc(x.login)}">${esc(x.login)} (${x.canais.length} canais)</option>`).join('')}</select>` : ''}
        </div>
        <div class="aviso roxo" style="margin-bottom:12px"><span>Pode colocar quantos canais quiser (10, 20, 30…). O app farma em <b>${textoLives()}</b>: primeiro os com ${ic('estrela')} que estiverem ao vivo, depois os outros pela regra abaixo. Quando um sai do ar, o próximo entra no lugar; quando um favorito volta, ele toma a vaga.</span></div>
        <div class="ordem-lives"><span class="sub">Depois dos favoritos, escolher as lives:</span><div class="segmento" id="c-ordem"></div></div>
        <div class="tabela-topo" id="c-cab"><span>#</span><span>Canal</span><span>Farm</span><span class="r" title="Pontos que o Lunar Farm ganhou hoje nesse canal">Hoje</span><span class="r" title="Tudo que o Lunar Farm já ganhou nesse canal">Farmado</span><span class="r" title="Pontos gastos na loja desse canal, pelo app ou pelo chat da Twitch">Gasto</span><span class="r" title="Pontos que a conta tem agora nesse canal, conferidos na Twitch. Conta também os pontos de antes do Lunar Farm, por isso não é Farmado menos Gasto.">Saldo</span><span></span></div>
        <div id="c-canais"></div>
        <p class="nota"><b>Hoje</b> e <b>Farmado</b> = o que o Lunar Farm ganhou nesse canal. <b>Gasto</b> = o que saiu na loja do canal, comprando pelo app ou pelo chat da Twitch, enquanto o app estava aberto. <b>Saldo</b> = quantos pontos a conta tem lá agora, igual aparece no chat da Twitch; inclui pontos de antes do Lunar Farm. Canal que acabou de abrir live pode passar na frente por alguns minutos para pegar a sequência de lives (os favoritos ${ic('estrela')} nunca saem para isso). Nos outros, a conta fica no chat, como no Chatterino.</p>
      </section>
      <section class="card">
        <div class="card-topo"><h2>Acontecimentos</h2><a href="#/historico/${encodeURIComponent(login)}">Ver tudo</a></div>
        <div id="c-feed"></div>
      </section>`;

    $('#c-kick-form').addEventListener('submit', async (ev) => {
      ev.preventDefault();
      const input = $('#c-kick-input');
      if (!input.value.trim()) return;
      try {
        const antes = (conta(login)?.kick?.canais || []).length;
        const r = await api(`/api/contas/${encodeURIComponent(login)}/kick`, 'POST', { texto: input.value });
        const novos = (r.canais || []).length - antes;
        input.value = '';
        toast(novos > 0 ? `${novos} canal(is) da Kick adicionado(s)` : 'Nada novo: o canal já estava na lista ou o nome não parece da Kick (use kick.com/nome)', novos <= 0);
        await ciclo(true);
      } catch (e) { toast(e.message, true); }
    });
    $('#c-form').addEventListener('submit', async (ev) => {
      ev.preventDefault();
      const input = $('#c-input');
      if (!input.value.trim()) return;
      try {
        const r = await api(`/api/contas/${encodeURIComponent(login)}/canais`, 'POST', { texto: input.value });
        input.value = '';
        toast(r.adicionados.length ? `${r.adicionados.length} canal(is) adicionado(s)` : 'Esses canais já estavam na lista');
        await ciclo(true);
      } catch (e) { toast(e.message, true); }
    });
    $('#c-chatterino')?.addEventListener('click', async () => {
      try {
        const r = await api('/api/chatterino');
        if (!r.canais.length) { toast('O Chatterino não tem nenhum canal aberto'); return; }
        if (!confirm(`Achei ${r.canais.length} canais no Chatterino:\n\n${r.canais.join(', ')}\n\nAdicionar todos nesta conta?`)) return;
        const a = await api(`/api/contas/${encodeURIComponent(login)}/canais`, 'POST', { texto: r.canais.join(' ') });
        toast(`${a.adicionados.length} canal(is) importado(s) do Chatterino`);
        await ciclo(true);
      } catch (e) { toast(e.message, true); }
    });
    $('#c-copiar')?.addEventListener('change', async (ev) => {
      const de = ev.target.value;
      ev.target.value = '';
      if (!de) return;
      try {
        await api(`/api/contas/${encodeURIComponent(login)}/copiar`, 'POST', { de });
        toast(`Canais de ${de} copiados`);
        await ciclo(true);
      } catch (e) { toast(e.message, true); }
    });
    el.addEventListener('click', (ev) => this.clique(ev));
    this.atualizar(true);
  },

  async clique(ev) {
    const alvo = ev.target.closest('button, a');
    if (!alvo) return;
    const login = this.login;
    const c = conta(login);
    const base = `/api/contas/${encodeURIComponent(login)}`;
    const lista = c.canais.map((x) => x.login);
    const d = alvo.dataset;
    try {
      if (d.kick) { await this.kick(d.kick); return; }
      const kickLista = (c.kick?.canais || []).map((x) => x.canal);
      if (d.kickTira) {
        await api(`${base}/kick`, 'POST', { canais: kickLista.filter((x) => x !== d.kickTira) });
        toast(`${d.kickTira} saiu da lista da Kick`);
        await ciclo(true);
        return;
      }
      if (d.kickEstrela) {
        const ligar = !(c.kick?.canais || []).find((x) => x.canal === d.kickEstrela)?.favorito;
        await api(`${base}/kick`, 'POST', { favorito: d.kickEstrela, ligado: ligar });
        toast(ligar ? `${d.kickEstrela} é favorito na Kick: quando abrir live, entra na frente` : `${d.kickEstrela} não é mais favorito na Kick`);
        await ciclo(true);
        return;
      }
      if (d.kickSobe !== undefined || d.kickDesce !== undefined) {
        const i = Number(d.kickSobe ?? d.kickDesce);
        const j = d.kickSobe !== undefined ? i - 1 : i + 1;
        [kickLista[i], kickLista[j]] = [kickLista[j], kickLista[i]];
        await api(`${base}/kick`, 'POST', { canais: kickLista });
        await ciclo(true);
        return;
      }
      if (d.abrirKick) { ev.preventDefault(); abrirLink(`https://kick.com/${d.abrirKick}`); return; }
      if (d.seguirKick) {
        await api(`${base}/kick`, 'POST', { seguir: [d.seguirKick] });
        toast(`Abrimos ${d.seguirKick} numa janela do Edge desta conta: clique em Seguir lá e feche a janela`);
        await ciclo(true);
        return;
      }
      if (d.kickLives) {
        if (Number(d.kickLives) > 1 && !S.estado.premium?.ativo) { Premium.abrir('lives'); return; }
        await api(`${base}/kick`, 'POST', { lives: Number(d.kickLives) });
        toast(`A Kick vai assistir até ${d.kickLives} lives por vez nesta conta`);
        await ciclo(true);
        return;
      }
      if (d.abrir) { ev.preventDefault(); abrirLink(`https://www.twitch.tv/${d.abrir}`); return; }
      if (d.estrela) {
        const canal = c.canais.find((x) => x.login === d.estrela);
        const ligar = !canal?.favorito;
        await api(`${base}/favorito`, 'POST', { canal: d.estrela, ligado: ligar });
        toast(ligar ? `${d.estrela} é favorito: quando abrir live, entra na frente` : `${d.estrela} não é mais favorito`);
        await ciclo(true);
        return;
      }
      if (d.ordem) {
        if (d.ordem === c.ordem) return;
        await api(`${base}/ordem`, 'POST', { modo: d.ordem });
        toast(d.ordem === 'pontos' ? 'Agora escolhe as lives onde a conta tem mais pontos' : 'Agora escolhe as lives pela ordem da lista');
        await ciclo(true);
        return;
      }
      if (d.atalho !== undefined) {
        const a = S.atalhos?.[Number(d.atalho)];
        if (!a) return;
        const novos = a.canais.filter((x) => !lista.includes(x));
        if (!novos.length) { toast(`Os ${a.canais.length} canais de "${a.nome}" já estão na lista`); return; }
        if (!confirm(`Adicionar ${novos.length} canais de "${a.nome}" nesta conta?\n\n${novos.join(', ')}`)) return;
        const r = await api(`${base}/canais`, 'POST', { texto: novos.join(' ') });
        toast(`${r.adicionados.length} canais de "${a.nome}" adicionados`);
        await ciclo(true);
        return;
      }
      if (d.sobe !== undefined || d.desce !== undefined) {
        const i = Number(d.sobe ?? d.desce);
        const j = d.sobe !== undefined ? i - 1 : i + 1;
        [lista[i], lista[j]] = [lista[j], lista[i]];
        await api(`${base}/canais`, 'PUT', { canais: lista });
      } else if (d.tira) {
        await api(`${base}/canais`, 'PUT', { canais: lista.filter((x) => x !== d.tira) });
        toast(`${d.tira} saiu da lista`);
      } else if (d.c === 'pausar') {
        await api(`${base}/pausar`, 'POST', { pausada: c.estado !== 'pausada' });
      } else if (d.c === 'reiniciar') {
        await api(`${base}/reiniciar`, 'POST');
        toast('Reiniciando o farm dessa conta');
      } else if (d.c === 'remover') {
        if (!confirm(`Tirar a conta ${login} do Lunar Farm?\n\nO login dela é apagado deste PC. O histórico de pontos fica guardado.`)) return;
        await api(base, 'DELETE');
        toast(`${login} removida`);
        location.hash = '#/resumo';
      } else return;
      await ciclo(true);
    } catch (e) { toast(e.message, true); }
  },

  async kick(acao) {
    const base = `/api/contas/${encodeURIComponent(this.login)}/kick`;
    if (acao === 'ligar' && conta(this.login)?.kick?.usuario) {
      await api(base, 'POST', { ligada: true });
      toast('Kick ligada nesta conta');
    } else if (acao === 'ligar' || acao === 'entrar') {
      await api(`${base}/entrar`, 'POST');
      toast('Abrimos uma janela do Edge na Kick: entre na sua conta e depois feche a janela');
    } else if (acao === 'twitch') {
      const r = await api(base, 'POST', { trazer_twitch: true });
      toast(r.trazidos ? `${r.trazidos} canal(is) da Twitch na lista da Kick. Os que não existem lá saem em seguida.` : 'Os canais da Twitch já estão na lista da Kick');
    } else if (acao === 'seguir') {
      await api(base, 'POST', { seguir: true });
      toast('Abrimos os canais que faltam numa janela do Edge desta conta: clique em Seguir em cada aba e feche a janela');
    } else if (acao === 'loja') {
      S.lojaSite = 'kick';  // só desta vez: o "Loja" do menu continua abrindo a da Twitch
      location.hash = `#/loja/${encodeURIComponent(this.login)}`;
      return;
    } else if (acao === 'pronto') {
      await api(`${base}/pronto`, 'POST');
      toast('Conferindo o login da Kick…');
    } else if (acao === 'desligar') {
      await api(base, 'POST', { ligada: false });
      toast('Kick desligada nesta conta');
    } else if (acao === 'sair') {
      if (!confirm('Sair da Kick nesta conta?\n\nO login da Kick é apagado deste PC e as lives da Kick param.')) return;
      await api(`${base}/sair`, 'POST');
      toast('Saiu da Kick nesta conta');
    } else if (acao === 'mostrar' || acao === 'esconder') {
      await api(`${base}/mostrar`, 'POST', { mostrar: acao === 'mostrar' });
    } else return;
    await ciclo(true);
  },

  desenharKick(c) {
    const k = c.kick || { ligada: false, canais: [] };
    const ligada = k.ligada;
    $('#c-kick-config').style.display = ligada && !['sem_login', 'entrando', 'seguindo'].includes(k.estado) ? '' : 'none';
    const premium = !!S.estado.premium?.ativo;
    setHTML($('#c-kick-lives'), [1, 2].map((n) => `
      <button type="button" class="${(k.lives || 2) === n ? 'ativo' : ''}" data-kick-lives="${n}"${!premium && n > 1 ? ' title="Mais de 1 live é do Lunar Premium"' : ''}>${!premium && n > 1 ? ic('coroa') : ''}${n}</button>`).join(''));
    setHTML($('#c-kick-sub'), ligada ? (k.usuario ? `conectada como ${esc(k.usuario)}` : 'ligada') : 'desligada');
    if (!ligada) {
      setHTML($('#c-kick'), `<div class="aviso roxo"><span>Junte também os pontos dos canais do PokeIdle na <b>Kick</b>, para resgatar mais bônus no jogo. Você entra na sua conta da Kick uma vez, numa janela da própria Kick (o Lunar não vê a sua senha).</span>
        ${S.estado.local || k.usuario ? '<button class="btn primario" data-kick="ligar" type="button">Ligar a Kick nesta conta</button>' : '<span class="sub">Ligue no PC (a janela da Kick abre lá).</span>'}</div>`);
      return;
    }
    const botoes = (extra) => `<div class="kick-botoes">${extra}<button class="btn leve" data-kick="desligar" type="button">Desligar a Kick</button></div>`;
    if (k.estado === 'sem_login') {
      setHTML($('#c-kick'), `${k.aviso ? `<div class="aviso ambar" style="margin-bottom:10px"><span>${esc(k.aviso)}</span></div>` : ''}<div class="aviso roxo"><span>Falta entrar na sua conta da Kick. Abre uma janela do Edge na Kick: entre na sua conta (pode ser com o Google) e depois feche a janela.</span>${S.estado.local ? '<button class="btn primario" data-kick="entrar" type="button">Entrar na Kick</button>' : '<span class="sub">Faça isso no PC.</span>'}</div>${botoes('')}`);
      return;
    }
    if (k.estado === 'seguindo') {
      const n = (k.seguindo || []).length;
      setHTML($('#c-kick'), `<div class="aviso roxo"><span>Abrimos ${n === 1 ? 'o canal' : `os ${n} canais`} numa janela do Edge desta conta, já logada na Kick. <b>Clique em Seguir</b>${n > 1 ? ' em cada aba' : ''} e depois feche a janela (ou clique em Pronto). As lives da Kick voltam sozinhas.</span><button class="btn primario" data-kick="pronto" type="button">Pronto</button></div>${botoes('')}`);
      return;
    }
    if (k.estado === 'entrando') {
      setHTML($('#c-kick'), `<div class="aviso roxo"><span>Entre na sua conta da Kick na janela do Edge que abriu (pode ser com o Google). <b>Depois de entrar, feche a janela</b> ou clique em Já entrei.</span><button class="btn primario" data-kick="pronto" type="button">Já entrei</button></div>${botoes('<button class="btn" data-kick="entrar" type="button">Abrir a janela de novo</button>')}`);
      return;
    }
    let topo = '';
    if (k.estado === 'pausada') topo = '<div class="aviso roxo"><span>Conta pausada: as lives da Kick também pararam.</span></div>';
    else if (k.estado === 'bloqueada') topo = `<div class="aviso ambar"><span>${ic('cadeado')} Na versão grátis só a primeira conta farma, na Twitch e na Kick.</span><button class="btn dourado" data-acao="premium" data-motivo="conta" type="button">${ic('coroa')} Desbloquear</button></div>`;
    else if (k.estado === 'erro') topo = `<div class="aviso vermelho"><span>A Kick parou${k.erro ? `: ${esc(k.erro)}` : ''}. Tentando de novo em 1 minuto.</span></div>`;
    else if (k.estado === 'iniciando') topo = '<div class="esperando" style="padding:14px 0"><span class="roda"></span> Ligando as lives da Kick…</div>';
    if (k.aviso) topo += `<div class="aviso ambar" style="margin-top:10px"><span>${esc(k.aviso)}</span></div>`;
    const lista = k.canais || [];
    const noPc = S.estado.local && k.estado === 'farmando';  // seguir/mostrar abrem janela no PC e precisam do Edge ligado
    const linhas = lista.length
      ? `<div class="tabela-topo"><span>#</span><span>Canal</span><span>Farm</span><span class="r" title="Pontos que o Lunar juntou nesse canal da Kick desde que o app abriu">Ganho</span><span class="r" title="Pontos que a conta tem nesse canal da Kick agora">Saldo</span><span></span></div>
        ${lista.map((x, i) => linhaKick(x, i, lista.length, noPc)).join('')}`
      : '<div class="vazio">Nenhum canal da Kick na lista.</div>';
    const r = k.ultimo_resgate;
    const rodape = [
      k.sem_kick ? `<span class="sub">${k.sem_kick} canal(is) da Twitch não têm canal com o mesmo nome na Kick e ficaram de fora</span>` : '',
      (() => {
        const existem = lista.filter((x) => x.existe !== false);
        const faltam = existem.filter((x) => !x.seguido).length;
        return faltam ? `<span class="sub">Segue ${existem.length - faltam} de ${existem.length} na Kick (+50 pontos em cada canal que seguir)</span>` : '';
      })(),
      k.ganho ? `<span class="ouro" style="font-weight:700">+${fmt(k.ganho)}</span> <span class="sub">pontos na Kick desde que o app abriu</span>` : '',
      (k.auto || []).length ? `<span class="sub">Compra automática: ${(k.auto || []).length} recompensa(s)${k.resgate_pausado ? ' (pausada)' : ''}</span>` : '',
      r ? `<span class="sub">Última compra: ${esc(r.titulo || 'recompensa')} em ${esc(r.canal)} às ${hora(r.ts)}</span>` : '',
    ].filter(Boolean).join(' · ');
    setHTML($('#c-kick'), `${topo}<div class="kick-tab">${linhas}</div>${rodape ? `<p style="margin:10px 0 0">${rodape}</p>` : ''}
      ${botoes(`<button class="btn primario" data-kick="loja" type="button">${ic('loja')} Loja da Kick</button>
        ${noPc && lista.some((x) => x.existe !== false && !x.seguido) ? `<button class="btn" data-kick="seguir" type="button" title="Abre os canais que faltam numa janela do Edge desta conta: é só clicar em Seguir em cada aba">+ Seguir os que faltam (+50 cada)</button>` : ''}
        ${noPc ? `<button class="btn" data-kick="${k.mostrando ? 'esconder' : 'mostrar'}" type="button">${k.mostrando ? 'Esconder as lives' : 'Mostrar as lives'}</button>` : ''}
        <button class="btn leve" data-kick="sair" type="button">Sair da Kick</button>`)}`);
  },

  async atualizar(forcar) {
    if (!this.el?.isConnected) return;
    const c = conta(this.login);
    if (!c) { location.hash = '#/resumo'; return; }
    this.desenharKick(c);
    const rodando = c.estado === 'farmando' || c.estado === 'iniciando';
    setHTML($('#c-estado'), `<span class="pill ${c.estado}">${ESTADOS[c.estado] || c.estado}</span> <span class="sub">${c.ao_vivo} de ${c.canais.length} canais ao vivo</span>`);
    setHTML($('#c-acoes'), `
      <a class="btn" href="#/loja/${encodeURIComponent(c.login)}">${ic('loja')} Loja</a>
      <button class="btn" data-c="pausar">${c.estado === 'pausada' ? `${ic('play')} Retomar` : `${ic('pausa')} Pausar`}</button>
      <button class="btn" data-c="reiniciar">${ic('refazer')} Reiniciar</button>
      <button class="btn perigo" data-c="remover">${ic('lixo')} Remover</button>`);

    let aviso = '';
    if (c.estado === 'precisa_entrar') {
      aviso = `<div class="aviso ambar"><span>O login dessa conta venceu ou ainda não foi feito.</span><button class="btn primario" data-acao="login" data-conta="${esc(c.login)}">Entrar de novo</button></div>`;
    } else if (c.estado === 'sem_canais') {
      aviso = `<div class="aviso roxo"><span>Falta dizer quais canais essa conta vai farmar. ${S.atalhos?.length ? 'Use o atalho, cole' : 'Cole'} os links aqui embaixo ou importe do Chatterino.</span>
        <span class="atalhos">${botoesAtalho('btn primario')}</span></div>`;
    } else if (c.estado === 'erro') {
      aviso = `<div class="aviso vermelho"><span>O farm dessa conta parou${c.erro ? `: ${esc(c.erro)}` : ''}.${c.religa_em != null ? ` Tentando de novo em ${c.religa_em}s.` : ''}</span><button class="btn" data-c="reiniciar">Tentar agora</button></div>`;
    } else if (c.estado === 'bloqueada') {
      aviso = `<div class="aviso ambar"><span>${ic('cadeado')} Na versão grátis só a primeira conta farma. Essa conta volta a farmar com o <b>Lunar Premium</b>.</span><button class="btn dourado" data-acao="premium" data-motivo="conta" type="button">${ic('coroa')} Desbloquear</button></div>`;
    } else if (c.estado === 'pausada') {
      aviso = `<div class="aviso roxo"><span>Conta pausada: ela não está farmando nem no chat.</span><button class="btn primario" data-c="pausar">${ic('play')} Retomar</button></div>`;
    }
    setHTML($('#c-aviso'), aviso);
    setHTML($('#c-lives'), linhaLives('a Twitch paga em até 2 por vez'));

    const ganhando = c.canais.filter((x) => x.watching);
    let assist;
    if (ganhando.length) {
      assist = `<div class="assistindo">${ganhando.map((x) => `
        <div><b>${esc(x.login)}</b><span class="t">${esc(x.game || 'Ao vivo')}${x.viewers ? ` · ${fmt(x.viewers)} assistindo` : ''}</span>
        <span><span class="ouro" style="font-weight:700">+${fmt(x.farmado_hoje)}</span> <span class="sub">hoje · saldo ${x.points != null ? fmt(x.points) : '—'}</span></span></div>`).join('')}</div>`;
    } else if (c.estado === 'farmando' && c.ao_vivo) {
      assist = `<div class="esperando" style="padding:22px 0"><span class="roda"></span> ${c.ao_vivo} canais ao vivo: escolhendo ${lives() > 1 ? `as ${lives()} lives` : 'a live'} para farmar…</div>`;
    } else if (c.estado === 'farmando') {
      assist = '<div class="vazio">Nenhum canal da lista está ao vivo agora. Quando um abrir live, ele começa a farmar sozinho.</div>';
    } else if (c.estado === 'iniciando') {
      assist = '<div class="esperando" style="padding:22px 0"><span class="roda"></span> Ligando o farm e carregando os canais da lista (cerca de 1 minuto)…</div>';
    } else {
      assist = '<div class="vazio">Essa conta não está farmando agora.</div>';
    }
    setHTML($('#c-assist'), assist);

    setHTML($('#c-atalhos'), botoesAtalho('btn atalho'));
    setHTML($('#c-ordem'), [['lista', 'Pela ordem da lista'], ['pontos', 'Onde tem mais pontos']].map(([modo, nome]) => `
      <button type="button" class="${c.ordem === modo ? 'ativo' : ''}" data-ordem="${modo}">${nome}</button>`).join(''));
    setHTML($('#c-qtd'), `${c.canais.length} canais`);
    $('#c-cab').style.display = c.canais.length ? '' : 'none';
    setHTML($('#c-canais'), c.canais.length
      ? c.canais.map((x, i) => linhaCanal(c.login, x, i, c.canais.length, rodando, S.estado.chat_mode !== 'ao_vivo')).join('')
      : '<div class="vazio">Nenhum canal ainda.</div>');

    if (forcar || Date.now() - this.carregado > 20000) {
      this.carregado = Date.now();
      try {
        const q = encodeURIComponent(this.login);
        const [r, feed] = await Promise.all([api(`/api/resumo?conta=${q}`), api(`/api/historico?conta=${q}&limite=12`)]);
        setHTML($('#c-cartoes'), `
          <div class="cartao destaque"><div class="r">Hoje</div><div class="v">+${fmt(r.cartoes.hoje)}<small>pontos</small></div></div>
          <div class="cartao"><div class="r">Últimos 30 dias</div><div class="v">${fmt(r.cartoes.mes)}</div></div>
          <div class="cartao"><div class="r">Baús resgatados (30 dias)</div><div class="v">${fmt(r.baus)}</div></div>
          <div class="cartao"><div class="r">Horas assistidas (30 dias)</div><div class="v">${horas(r.segundos)}</div></div>`);
        setHTML($('#c-feed'), linhaDoTempo(feed, false, 12));
      } catch (e) { /* próximo ciclo */ }
    }
  },
};

/* ---------- Loja ---------- */
const FILTROS_LOJA = [
  { id: 'jogo', nome: 'Do jogo', re: /poke\s*[il1]dle|capture\s*boost|secret\s*lure/i },
  { id: 'pokeidle', nome: 'PokeIdle', re: /poke\s*[il1]dle/i },
  { id: 'capture', nome: 'Capture Boost', re: /capture\s*boost/i },
  { id: 'lure', nome: 'Secret Lure', re: /secret\s*lure/i },
  { id: 'todas', nome: 'Todas', re: null },
];
const GRUPOS_JOGO = FILTROS_LOJA.slice(1, 4);
const corSegura = (c) => (/^#[0-9a-f]{3,8}$/i.test(c || '') ? c : '#9146FF');

// Só lembra a última escolha neste navegador; se não der para guardar, tudo bem.
function guardado(chave) { try { return localStorage.getItem(`fp.${chave}`); } catch (e) { return null; } }
function guardar(chave, valor) { try { localStorage.setItem(`fp.${chave}`, valor); } catch (e) { /* sem memória */ } }

function caraRecompensa(r) {
  return `<span class="rec-cara" style="background:${corSegura(r.cor)}">
    ${r.imagem ? `<img src="${esc(r.imagem)}" alt="" loading="lazy">` : ''}
    <span class="rec-custo">${ic('moeda')} ${fmt(r.custo)}</span></span>`;
}

VIEWS.loja = {
  montar(el, login) {
    this.el = el;
    this.dados = null;
    const contas = S.estado.contas;
    if (!contas.length) { el.innerHTML = '<div class="vazio">Adicione uma conta primeiro.</div>'; return; }
    const salvo = guardado('loja.conta');
    this.login = conta(login) ? login : conta(salvo) ? salvo : contas[0].login;
    this.canal = guardado('loja.canal');
    this.filtro = FILTROS_LOJA.some((f) => f.id === guardado('loja.filtro')) ? guardado('loja.filtro') : 'jogo';
    this.site = S.lojaSite === 'kick' ? 'kick' : 'twitch';
    S.lojaSite = null;
    this.canalKick = guardado('loja.canalKick');
    el.innerHTML = `
      <div class="topo"><div><h1>Loja de pontos</h1><div class="sub">As recompensas do chat de cada canal, compradas com os pontos que o farm juntou</div></div>
        <div class="segmento loja-abas" id="lj-abas"></div></div>
      <div id="lj-comprar">
      <section class="card loja-escolha">
        <div class="loja-linha"><span class="loja-rot">Site</span><div class="loja-chips" id="lj-site"></div></div>
        <div class="loja-linha"><span class="loja-rot">Conta</span><div class="loja-chips" id="lj-contas"></div></div>
        <div class="loja-linha"><span class="loja-rot">Canal</span><select id="lj-canal"></select><button class="btn" id="lj-atualizar" type="button">${ic('refazer')} Atualizar</button></div>
        <div class="loja-linha"><span class="loja-rot">Mostrar</span><div class="loja-chips" id="lj-filtros"></div></div>
      </section>
      <section class="card">
        <div class="card-topo"><h2 id="lj-titulo">Recompensas</h2><span class="loja-saldo" id="lj-saldo"></span></div>
        <div id="lj-itens"></div>
        <p class="nota" id="lj-nota"></p>
      </section>
      </div>
      <div id="lj-auto" hidden></div>`;
    // Veio de uma conta ou da Kick: abre em Comprar. Pelo menu, volta na aba que estava.
    this.aba = login || this.site === 'kick' ? 'comprar' : guardado('loja.aba') === 'auto' ? 'auto' : 'comprar';
    this.resumoAuto = null;
    el.addEventListener('click', (ev) => this.clique(ev));
    $('#lj-canal').addEventListener('change', (ev) => {
      let canal = ev.target.value;
      if (this.site === 'kick') {
        if (canal === '__outro') {
          canal = (prompt('Nome ou link do canal da Kick (kick.com/nome):') || '').trim().replace(/^.*kick\.com\//i, '').replace(/[/?#].*$/, '').replace(/^@/, '').toLowerCase();
          if (!/^[a-z0-9_-]{2,30}$/.test(canal)) { if (canal) toast('Esse nome de canal não parece certo', true); this.desenharEscolhas(); return; }
        }
        this.canalKick = canal;
        guardar('loja.canalKick', canal);
        this.desenharEscolhas();
        this.carregar();
        return;
      }
      if (canal === '__outro') {
        canal = (prompt('Nome ou link do canal (twitch.tv/nome):') || '').trim().replace(/^.*twitch\.tv\//i, '').replace(/[/?#].*$/, '').replace(/^@/, '').toLowerCase();
        if (!/^[a-z0-9_]{2,25}$/.test(canal)) { if (canal) toast('Esse nome de canal não parece certo', true); this.desenharEscolhas(); return; }
      }
      this.canal = canal;
      guardar('loja.canal', canal);
      this.desenharEscolhas();
      this.carregar();
    });
    this.desenharEscolhas();
    this.carregar();
    this.mostrarAba();
  },

  // --- abas: comprar na hora ou ver e controlar tudo o que está na compra automática ---
  desenharAbas() {
    const n = contarAuto().ligadas;
    setHTML($('#lj-abas'), [['comprar', `${ic('loja')} Comprar`],
      ['auto', `${ic('refazer')} Compra automática${n ? ` <span class="lj-aba-num">${n}</span>` : ''}`]]
      .map(([id, txt]) => `<button type="button" class="${this.aba === id ? 'ativo' : ''}" data-lj-aba="${id}">${txt}</button>`).join(''));
  },

  mostrarAba() {
    this.desenharAbas();
    $('#lj-comprar').hidden = this.aba !== 'comprar';
    $('#lj-auto').hidden = this.aba !== 'auto';
    if (this.aba === 'auto') {
      this.desenharAuto();
      this.carregarAuto();
    } else if (this.dados) {
      this.desenharItens();
    }
  },

  async carregarAuto() {
    this.autoEm = Date.now();
    try {
      this.resumoAuto = await api('/api/auto-compra/resumo?limite=25');
    } catch (e) {
      return;
    }
    if (this.aba === 'auto' && this.el?.isConnected) this.desenharAuto();
  },

  // A compra automática da Twitch agrupada por recompensa (pelo nome) e, dentro, por conta.
  gruposAuto() {
    const grupos = new Map();
    for (const c of S.estado.contas) {
      for (const r of c.auto_compras || []) {
        const chave = (r.titulo || '').trim().toLowerCase();
        if (!grupos.has(chave)) grupos.set(chave, { chave, titulo: r.titulo || '', custo: r.custo, id: r.id, contas: new Map() });
        const g = grupos.get(chave);
        if (!g.contas.has(c.login)) g.contas.set(c.login, []);
        g.contas.get(c.login).push(r);
      }
    }
    return [...grupos.values()].sort((a, b) => a.titulo.localeCompare(b.titulo, 'pt-BR'));
  },

  // Última compra de uma recompensa numa conta: a desta sessão do app ou a do histórico.
  ultimaAuto(login, titulo, regras) {
    const nome = (titulo || '').trim().toLowerCase();
    const doHist = (this.resumoAuto?.recentes || [])
      .filter((x) => x.conta === login && (x.titulo || '').trim().toLowerCase() === nome).map((x) => x.ts);
    return Math.max(0, ...regras.map((r) => r.ultima_compra || 0), ...doHist);
  },

  desenharAuto() {
    const el = $('#lj-auto');
    if (!el || el.hidden) return;
    const livre = S.estado.premium?.ativo !== false;
    const n = contarAuto();
    const grupos = this.gruposAuto();
    const kicks = S.estado.contas.filter((c) => (c.kick?.auto || []).length);
    const res = this.resumoAuto;
    const plural = (q, um, varios) => `${fmt(q)} ${q === 1 ? um : varios}`;
    const partes = [];

    if (!livre) {
      partes.push(`<div class="aviso roxo"><span>${ic('coroa')} A compra automática é do Lunar Premium. O que você já deixou configurado fica guardado e volta a funcionar quando ativar.</span>
        <button class="btn dourado" data-acao="premium" data-motivo="auto" type="button">${ic('coroa')} Ver o Premium</button></div>`);
    }
    partes.push(`
      <section class="card ap-resumo">
        <div class="ap-kpis">
          <div class="ap-kpi"><span>Ligadas agora</span><b>${fmt(n.ligadas)}</b><small>${n.contas ? `em ${plural(n.contas, 'conta', 'contas')}` : 'nenhuma conta no automático'}</small></div>
          <div class="ap-kpi"><span>Compras hoje</span><b>${res ? fmt(res.hoje.compras) : '…'}</b><small>${res ? `${fmt(res.hoje.pontos)} pontos gastos na Twitch` : 'contando…'}</small></div>
          <div class="ap-kpi${n.porErro ? ' alerta' : ''}"><span>Pausadas</span><b>${fmt(n.pausadas)}</b><small>${n.porErro ? `${plural(n.porErro, 'parou sozinha', 'pararam sozinhas')}` : n.pausadas ? 'pausadas por você' : 'nenhuma'}</small></div>
        </div>
      </section>`);
    if (n.porErro) {
      partes.push(`<div class="aviso ambar"><span>${ic('ajuda')} ${n.porErro === 1 ? 'Uma compra automática parou sozinha' : `${n.porErro} compras automáticas pararam sozinhas`}. O motivo aparece passando o mouse no canal em amarelo. Depois de resolver, clique em <b>Retomar</b>.</span></div>`);
    }

    if (!grupos.length && !kicks.length) {
      partes.push(`
        <section class="card ap-vazio">
          <div class="ap-vazio-icone">${ic('refazer')}</div>
          <h2>Nenhuma compra automática ligada</h2>
          <p class="sub">Na aba <b>Comprar</b>, escolha uma recompensa (o Bônus de XP do PokeIdle, por exemplo) e clique em <b>Compra automática</b>, embaixo dela. O Lunar Farm compra sozinho sempre que a conta juntar os pontos, nos canais e contas que você escolher.</p>
          <button class="btn primario" data-lj-aba="comprar" type="button">${ic('loja')} Escolher uma recompensa</button>
        </section>`);
    }

    if (grupos.length) {
      const twAtivas = grupos.some((g) => [...g.contas.values()].flat().some((r) => !r.pausada));
      const twPausadas = grupos.some((g) => [...g.contas.values()].flat().some((r) => r.pausada));
      partes.push(`<div class="ap-secao-topo"><h2>Twitch</h2><span class="ap-btns">
        ${twAtivas ? `<button class="btn" data-ap-acao="pausar" type="button">${ic('pausa')} Pausar todas</button>` : ''}
        ${twPausadas ? `<button class="btn" data-ap-acao="retomar" type="button">${ic('play')} Retomar todas</button>` : ''}</span></div>`);
      for (const g of grupos) {
        const todas = [...g.contas.values()].flat();
        const ativas = todas.filter((r) => !r.pausada).length;
        const pausadas = todas.length - ativas;
        const canais = new Set(todas.map((r) => r.canal)).size;
        const [classe, estado] = !pausadas ? ['farmando', 'Ligada'] : !ativas ? ['pausada', 'Pausada'] : ['iniciando', 'Parte pausada'];
        const linhas = [...g.contas.entries()].map(([login, regras]) => {
          const ult = this.ultimaAuto(login, g.titulo, regras);
          const algumaAtiva = regras.some((r) => !r.pausada);
          const algumaPausada = regras.some((r) => r.pausada);
          const chips = regras.map((r) => {
            const tipo = r.pausada ? (r.pausada === PAUSA_MANUAL ? 'manual' : 'pausado') : r.aviso ? 'esperando' : 'ok';
            const dica = r.pausada ? `Pausada: ${r.pausada}` : r.aviso ? `Esperando: ${r.aviso}`
              : `Ligada: compra ${r.titulo} em ${r.canal} sempre que juntar ${fmt(r.custo)} pontos`;
            return `<span class="ap-chip ${tipo}" title="${esc(dica)}">${esc(r.canal)}</span>`;
          }).join('');
          const filtro = `data-ap-titulo="${esc(g.titulo)}" data-ap-conta="${esc(login)}"`;
          return `
            <div class="ap-linha">
              <span class="ap-conta"><i style="background:${cor(login)}"></i>${esc(login)}</span>
              <span class="ap-canais">${chips}</span>
              <span class="ap-ult">${ult ? `${ic('relogio')} última compra ${quandoCurto(ult)}` : 'ainda não comprou'}</span>
              <span class="ap-linha-btns">
                ${algumaAtiva ? `<button class="btn leve" data-ap-acao="pausar" ${filtro} type="button" title="Pausar nesta conta">${ic('pausa')}</button>` : ''}
                ${algumaPausada ? `<button class="btn leve" data-ap-acao="retomar" ${filtro} type="button" title="Retomar nesta conta">${ic('play')}</button>` : ''}
                <button class="btn leve perigo" data-ap-acao="desligar" ${filtro} type="button" title="Desligar nesta conta">${ic('x')}</button>
              </span>
            </div>`;
        }).join('');
        const filtroG = `data-ap-titulo="${esc(g.titulo)}"`;
        partes.push(`
          <section class="card ap-grupo">
            <div class="ap-grupo-topo">
              <div class="ap-grupo-nome"><h3>${esc(g.titulo)}</h3>
                <span class="sub">${ic('moeda')} ${fmt(g.custo)} · ${plural(g.contas.size, 'conta', 'contas')} · ${plural(canais, 'canal', 'canais')}</span></div>
              <span class="pill ${classe}">${estado}</span>
              <div class="ap-btns">
                <button class="btn" data-ap-editar="${esc(g.chave)}" type="button">${ic('opcoes')} Canais e contas</button>
                ${ativas ? `<button class="btn" data-ap-acao="pausar" ${filtroG} type="button">${ic('pausa')} Pausar</button>` : ''}
                ${pausadas ? `<button class="btn" data-ap-acao="retomar" ${filtroG} type="button">${ic('play')} Retomar</button>` : ''}
                <button class="btn perigo" data-ap-acao="desligar" ${filtroG} type="button">${ic('lixo')} Desligar</button>
              </div>
            </div>
            <div class="ap-linhas">${linhas}</div>
          </section>`);
      }
    }

    if (kicks.length) {
      const linhas = kicks.map((c) => {
        const k = c.kick || {};
        const pausada = !!k.resgate_pausado;
        const chips = (k.auto || []).map((f) => `<span class="ap-chip ${pausada ? 'pausado' : 'ok'}"
            title="${esc(pausada ? 'Pausada: os pontos de uma compra voltaram (a Kick está vinculada no PokeIdle dessa conta?)' : `Compra sozinha em todos os canais da Kick de ${c.login}, na versão de melhor preço por hora`)}">${esc(nomeFamilia(f))}
            <button class="ap-chip-x" data-ap-kick="${esc(f)}" data-ap-conta="${esc(c.login)}" type="button" title="Desligar">${ic('x')}</button></span>`).join('');
        return `
          <div class="ap-linha">
            <span class="ap-conta"><i style="background:${cor(c.login)}"></i>${esc(c.login)}</span>
            <span class="ap-canais">${chips}</span>
            <span class="ap-ult">${pausada ? 'pausada: os pontos voltaram' : k.ligada ? 'em todos os canais da Kick' : 'a Kick está desligada nesta conta'}</span>
            <span class="ap-linha-btns">${pausada ? `<button class="btn" data-ap-kickretomar="${esc(c.login)}" type="button">${ic('play')} Retomar</button>` : ''}</span>
          </div>`;
      }).join('');
      partes.push(`<div class="ap-secao-topo"><h2>Kick</h2></div>
        <section class="card ap-grupo"><div class="ap-linhas sem-borda">${linhas}</div>
          <p class="nota">Na Kick, a compra automática vale para a recompensa em todos os canais da Kick da conta. Para ligar outra, abra a aba Comprar, escolha <b>Kick</b> e clique em Compra automática.</p></section>`);
    }

    if (grupos.length || (res?.recentes || []).length) {
      const compras = (res?.recentes || []).map((x) => `
        <div class="ap-compra">
          <span class="ap-q">${quandoCurto(x.ts)}</span>
          <span class="ap-conta"><i style="background:${cor(x.conta)}"></i>${esc(x.conta)}</span>
          <span class="ap-canal-col">${esc(x.canal)}</span>
          <span class="ap-tit" title="${esc(x.titulo)}">${esc(x.titulo)}</span>
          <span class="ap-pts">−${fmt(x.pontos)}</span>
        </div>`).join('');
      partes.push(`
        <section class="card">
          <div class="card-topo"><h2>Últimas compras automáticas</h2><a class="btn leve" href="#/historico">Ver tudo no Histórico</a></div>
          ${!res ? '<div class="esperando"><span class="roda"></span> Carregando…</div>' : compras ? `<div class="ap-compras">${compras}</div>` : '<div class="vazio">Nenhuma compra automática ainda. Elas aparecem aqui assim que a conta juntar os pontos.</div>'}
        </section>`);
    }
    setHTML(el, partes.join(''));
  },

  async mudarAuto(acao, filtro, botao) {
    const alvo = filtro.titulo ? `a compra automática de "${filtro.titulo}"` : 'todas as compras automáticas da Twitch';
    const onde = filtro.conta ? ` na conta ${filtro.conta}` : '';
    if (acao === 'desligar' && !confirm(`Desligar ${alvo}${onde}?\n\nO Lunar Farm para de comprar sozinho. Para ligar de novo, use o botão Compra automática embaixo da recompensa, na aba Comprar.`)) return;
    if (botao) botao.disabled = true;
    try {
      const d = await api('/api/auto-compra/mudar', 'POST', { acao, ...filtro });
      const nome = { pausar: 'pausada', retomar: 'retomada', desligar: 'desligada' }[acao];
      toast(!d.mudadas ? 'Nada para mudar' : d.mudadas === 1 ? `Compra automática ${nome}` : `${d.mudadas} compras automáticas ${nome}s`);
      await ciclo(true);
    } catch (e) {
      if (!e.premium) toast(e.message, true);
    }
    if (botao) botao.disabled = false;
  },

  editarAuto(chave) {
    const g = this.gruposAuto().find((x) => x.chave === chave);
    if (g) Auto.abrir(this, { id: g.id, titulo: g.titulo, custo: g.custo });
  },

  async kickAuto(familiaKick, login, retomar) {
    const k = conta(login)?.kick || {};
    const alvo = retomar ? (k.auto || [])[0] : familiaKick;
    if (!alvo) return;
    if (!retomar && !confirm(`Desligar a compra automática de "${familiaKick}" na Kick de ${login}?`)) return;
    try {
      await api(`/api/contas/${encodeURIComponent(login)}/kick`, 'POST', { auto: alvo, ligado: !!retomar });
      toast(retomar ? 'Compra automática da Kick retomada' : 'Compra automática da Kick desligada');
      await ciclo(true);
    } catch (e) {
      if (!e.premium) toast(e.message, true);
    }
  },

  desenharEscolhas() {
    const c = conta(this.login);
    setHTML($('#lj-site'), [['twitch', 'Twitch'], ['kick', 'Kick']].map(([id, nome]) => `
      <button class="loja-chip${id === this.site ? ' ativo' : ''}" data-lj-site="${id}" type="button">${nome}</button>`).join(''));
    setHTML($('#lj-nota'), this.site === 'kick'
      ? 'A compra vai direto para a Kick, igual a clicar na loja do chat da Kick: o jogo recebe na hora (com a Kick vinculada no PokeIdle). A compra automática compra sempre que a conta juntar os pontos, em todos os canais da Kick dela, uma atrás da outra até os pontos acabarem.'
      : 'A compra vai direto para a Twitch, igual a clicar na loja do chat: o jogo recebe na hora. Os pontos saem do saldo da conta nesse canal.');
    if (this.site === 'kick') { this.desenharEscolhasKick(c); return; }
    setHTML($('#lj-contas'), S.estado.contas.map((x) => `
      <button class="loja-chip${x.login === this.login ? ' ativo' : ''}" data-lj-conta="${esc(x.login)}" type="button"><i style="background:${cor(x.login)}"></i>${esc(x.login)}</button>`).join(''));
    setHTML($('#lj-filtros'), FILTROS_LOJA.map((f) => `
      <button class="loja-chip${f.id === this.filtro ? ' ativo' : ''}" data-lj-filtro="${f.id}" type="button">${f.nome}</button>`).join(''));
    const canais = c ? c.canais : [];
    if (!this.canal && canais.length) {
      // Sem escolha anterior: começa pelo canal onde a conta tem mais pontos.
      this.canal = [...canais].sort((a, b) => (b.points || 0) - (a.points || 0))[0].login;
    }
    const opcoes = canais.map((x) => `<option value="${esc(x.login)}">${esc(x.login)}${x.points != null ? ` · ${fmt(x.points)} pontos` : ''}</option>`);
    if (this.canal && !canais.some((x) => x.login === this.canal)) opcoes.unshift(`<option value="${esc(this.canal)}">${esc(this.canal)}</option>`);
    opcoes.push('<option value="__outro">Outro canal…</option>');
    $('#lj-canal').innerHTML = opcoes.join('');
    if (this.canal) $('#lj-canal').value = this.canal;
  },

  desenharEscolhasKick(c) {
    setHTML($('#lj-contas'), S.estado.contas.map((x) => `
      <button class="loja-chip${x.login === this.login ? ' ativo' : ''}" data-lj-conta="${esc(x.login)}" type="button"><i style="background:${cor(x.login)}"></i>${esc(x.login)}${x.kick?.ligada ? '' : ' <span class="sub">(sem Kick)</span>'}</button>`).join(''));
    setHTML($('#lj-filtros'), FILTROS_LOJA.map((f) => `
      <button class="loja-chip${f.id === this.filtro ? ' ativo' : ''}" data-lj-filtro="${f.id}" type="button">${f.nome}</button>`).join(''));
    const canais = c?.kick?.canais || [];
    if (!this.canalKick && canais.length) {
      this.canalKick = [...canais].sort((a, b) => (b.saldo || 0) - (a.saldo || 0))[0].canal;
    }
    const opcoes = canais.map((x) => `<option value="${esc(x.canal)}">${esc(x.canal)}${x.saldo != null ? ` · ${fmt(x.saldo)} pontos` : ''}</option>`);
    if (this.canalKick && !canais.some((x) => x.canal === this.canalKick)) opcoes.unshift(`<option value="${esc(this.canalKick)}">${esc(this.canalKick)}</option>`);
    opcoes.push('<option value="__outro">Outro canal…</option>');
    $('#lj-canal').innerHTML = opcoes.join('');
    if (this.canalKick) $('#lj-canal').value = this.canalKick;
  },

  async carregarKick(silencioso, pedido) {
    const c = conta(this.login);
    if (!silencioso) this.dados = null;
    if (!c?.kick?.ligada) {
      setHTML($('#lj-titulo'), 'Loja da Kick');
      setHTML($('#lj-saldo'), '');
      setHTML($('#lj-itens'), `<div class="vazio">A Kick não está ligada em ${esc(this.login)}. Ligue no cartão <b>Kick</b>, na <a href="#/conta/${encodeURIComponent(this.login)}">página da conta</a>.</div>`);
      return;
    }
    if (!this.canalKick) { setHTML($('#lj-itens'), '<div class="vazio">Essa conta ainda não tem canais da Kick na lista.</div>'); return; }
    if (!silencioso) {
      this.dados = null;
      setHTML($('#lj-saldo'), '');
      setHTML($('#lj-titulo'), `Loja de ${esc(this.canalKick)} na Kick`);
      setHTML($('#lj-itens'), '<div class="esperando" style="padding:30px 0"><span class="roda"></span> Abrindo a loja da Kick…</div>');
    }
    try {
      const d = await api(`/api/kick/loja?conta=${encodeURIComponent(this.login)}&canal=${encodeURIComponent(this.canalKick)}`);
      if (pedido !== this.pedido || !this.el.isConnected) return;
      this.dados = {
        kick: true, canal: d.canal, saldo: d.saldo, pontos_ligados: true, auto: d.auto || [],
        recompensas: (d.recompensas || []).filter((r) => r.ativa).map((r) => ({ ...r, imagem: null })),
      };
      this.desenharItens();
    } catch (e) {
      if (pedido !== this.pedido || !this.el.isConnected || silencioso) return;
      setHTML($('#lj-itens'), `<div class="vazio">${esc(e.message)}</div>`);
    }
  },

  async carregar(silencioso) {
    // silencioso: atualiza o saldo por trás, sem trocar a loja por "Abrindo a loja…"
    const pedido = (this.pedido = (this.pedido || 0) + 1);
    this.carregadoEm = Date.now();
    if (this.site === 'kick') { await this.carregarKick(silencioso, pedido); return; }
    if (!this.canal) { setHTML($('#lj-itens'), '<div class="vazio">Essa conta ainda não tem canais na lista.</div>'); return; }
    if (!silencioso) {
      this.dados = null;
      setHTML($('#lj-saldo'), '');
      setHTML($('#lj-titulo'), `Loja de ${esc(this.canal)}`);
      setHTML($('#lj-itens'), '<div class="esperando" style="padding:30px 0"><span class="roda"></span> Abrindo a loja…</div>');
    }
    try {
      const d = await api(`/api/loja?conta=${encodeURIComponent(this.login)}&canal=${encodeURIComponent(this.canal)}`);
      if (pedido !== this.pedido || !this.el.isConnected) return;
      this.dados = d;
      this.desenharItens();
    } catch (e) {
      if (pedido !== this.pedido || !this.el.isConnected || silencioso) return;
      setHTML($('#lj-itens'), `<div class="vazio">${esc(e.message)}</div>`);
    }
  },

  bloqueio(r) {
    if (r.pausada) return 'Pausada pelo streamer';
    if (r.sem_estoque) return 'Esgotada';
    if (r.recarga_ate && new Date(r.recarga_ate) > new Date()) {
      return `Em recarga até ${new Date(r.recarga_ate).toLocaleTimeString('pt-BR', { hour: '2-digit', minute: '2-digit' })}`;
    }
    return null;
  },

  item(r, saldo) {
    const bloq = this.bloqueio(r);
    const falta = saldo != null && saldo < r.custo ? r.custo - saldo : 0;
    return `
      <div class="rec-bloco">
        <button class="recompensa${falta ? ' fraca' : ''}" data-lj-rec="${esc(r.id)}" type="button" ${bloq ? 'disabled' : ''} title="${esc(r.titulo)}">
          ${caraRecompensa(r)}
          <span class="rec-nome">${esc(r.titulo)}</span>
          ${bloq ? `<span class="rec-obs">${esc(bloq)}</span>` : falta ? `<span class="rec-obs">Faltam ${fmt(falta)} nesta conta</span>` : ''}
          ${r.limite_live && !bloq ? `<span class="rec-limite" title="Regra do streamer: cada conta compra no máximo ${r.limite_live} por live">${ic('relogio')} ${r.compradas_live >= r.limite_live ? `Esta conta: ${r.compradas_live}/${r.limite_live} na live` : `Máx. ${r.limite_live} por live`}</span>` : ''}
        </button>
        ${r.pede_texto ? '' : this.dados?.kick ? this.botaoAutoKick(r) : this.botaoAuto(r)}
      </div>`;
  },

  // Botão "Compra automática" embaixo da recompensa, já dizendo como está.
  botaoAuto(r) {
    const regras = S.estado.contas
      .map((c) => (c.auto_compras || []).find((x) => x.canal === this.dados.canal && x.id === r.id))
      .filter(Boolean);
    const ligadas = regras.filter((x) => !x.pausada).length;
    let texto = 'Compra automática';
    let classe = '';
    if (ligadas) {
      texto = `Automático em ${ligadas} conta${ligadas > 1 ? 's' : ''}`;
      classe = ' ligado';
    } else if (regras.length) {
      texto = 'Automático pausado';
      classe = ' pausado';
    } else if (outrasVersoes(r.titulo).length) {
      texto = 'Outra versão no automático';
      classe = ' outra';
    }
    const livre = S.estado.premium?.ativo !== false;
    return `<button class="rec-auto-btn${classe}${livre ? '' : ' so-premium'}" type="button" data-lj-auto="${esc(r.id)}">${ic(livre ? 'refazer' : 'coroa')} ${texto}</button>`;
  },

  // Kick: a compra automática vale para essa recompensa (mesmo nome, qualquer versão de horas) em todos os
  // canais da Kick da conta.
  botaoAutoKick(r) {
    const ligado = (this.dados.auto || []).includes(familia(r.titulo));
    const pausado = ligado && conta(this.login)?.kick?.resgate_pausado;
    const livre = S.estado.premium?.ativo !== false;
    const texto = pausado ? 'Automático pausado' : ligado ? 'Automático ligado' : 'Compra automática';
    const dica = pausado ? 'Os pontos de uma compra voltaram (a Kick não está vinculada no PokeIdle?). Clique para ligar de novo.'
      : `Compra sozinha em todos os canais da Kick de ${this.login}, sempre que juntar os pontos`;
    return `<button class="rec-auto-btn${pausado ? ' pausado' : ligado ? ' ligado' : ''}${livre ? '' : ' so-premium'}" type="button" data-lj-auto="${esc(r.id)}"
      title="${esc(dica)}">${ic(livre ? 'refazer' : 'coroa')} ${texto}</button>`;
  },

  async autoKick(r) {
    if (!S.estado.premium?.ativo) { Premium.abrir('auto'); return; }
    const fam = familia(r.titulo);
    const pausado = conta(this.login)?.kick?.resgate_pausado && (this.dados.auto || []).includes(fam);
    const ligar = pausado || !(this.dados.auto || []).includes(fam);
    try {
      const res = await api(`/api/contas/${encodeURIComponent(this.login)}/kick`, 'POST', { auto: fam, ligado: ligar });
      if (!this.dados) return;  // trocou de canal enquanto isso
      this.dados.auto = res.auto || [];
      this.desenharItens();
      toast(ligar ? `Automático ligado: compra "${r.titulo}" sempre que juntar os pontos, em todos os canais da Kick de ${this.login}` : 'Compra automática desligada');
      ciclo(true);
    } catch (e) { toast(e.message, true); }
  },

  comprarKick(r) {
    if (r.pede_texto) { toast('Essa recompensa pede um texto: compre pelo chat da Kick', true); return; }
    CompraKick.abrir(this, r);
  },

  desenharItens() {
    const d = this.dados;
    if (!d) return;
    setHTML($('#lj-titulo'), d.kick ? `Loja de ${esc(d.canal)} na Kick` : `Loja de ${esc(d.canal)}`);
    setHTML($('#lj-saldo'), d.saldo != null ? `${ic('moeda')} <b>${fmt(d.saldo)}</b> ${esc(d.nome_pontos || 'pontos')} de ${esc(this.login)}` : '');
    if (!d.pontos_ligados) { setHTML($('#lj-itens'), '<div class="vazio">Esse canal não usa pontos do canal.</div>'); return; }
    const f = FILTROS_LOJA.find((x) => x.id === this.filtro) || FILTROS_LOJA[0];
    const lista = d.recompensas.filter((r) => !f.re || f.re.test(r.titulo)).sort((a, b) => a.custo - b.custo);
    if (!lista.length) {
      setHTML($('#lj-itens'), `<div class="vazio">${f.re
        ? `A loja de ${esc(d.canal)} não tem recompensas de ${esc(f.id === 'jogo' ? 'PokeIdle, Capture Boost ou Secret Lure' : f.nome)}. Escolha outro canal ou clique em <b>Todas</b>.`
        : 'Esse canal não tem nada na loja.'}</div>`);
      return;
    }
    const grade = (itens) => `<div class="loja-grade">${itens.map((r) => this.item(r, d.saldo)).join('')}</div>`;
    setHTML($('#lj-itens'), f.id === 'jogo'
      ? GRUPOS_JOGO.map((g) => {
        const itens = lista.filter((r) => g.re.test(r.titulo));
        return itens.length ? `<h3 class="loja-grupo">${g.nome}</h3>${grade(itens)}` : '';
      }).join('')
      : grade(lista));
  },

  clique(ev) {
    const b = ev.target.closest('[data-lj-site], [data-lj-conta], [data-lj-filtro], [data-lj-rec], [data-lj-auto], #lj-atualizar, '
      + '[data-lj-aba], [data-ap-acao], [data-ap-editar], [data-ap-kick], [data-ap-kickretomar]');
    if (!b) return;
    const d = b.dataset;
    if (d.ljAba) {
      if (d.ljAba !== this.aba) {
        this.aba = d.ljAba;
        guardar('loja.aba', this.aba);
        this.mostrarAba();
      }
      return;
    }
    if (d.apAcao) { this.mudarAuto(d.apAcao, { titulo: d.apTitulo, conta: d.apConta }, b); return; }
    if (d.apEditar) { this.editarAuto(d.apEditar); return; }
    if (d.apKick) { this.kickAuto(d.apKick, d.apConta, false); return; }
    if (d.apKickretomar) { this.kickAuto(null, d.apKickretomar, true); return; }
    if (d.ljSite) {
      if (d.ljSite === this.site) return;
      this.site = d.ljSite;
      this.dados = null;
      this.desenharEscolhas();
      this.carregar();
    } else if (d.ljConta) {
      if (d.ljConta === this.login) return;
      this.login = d.ljConta;
      guardar('loja.conta', this.login);
      this.desenharEscolhas();
      this.carregar();
    } else if (d.ljFiltro) {
      this.filtro = d.ljFiltro;
      guardar('loja.filtro', this.filtro);
      this.desenharEscolhas();
      this.desenharItens();
    } else if (d.ljRec) {
      const r = this.dados?.recompensas.find((x) => x.id === d.ljRec);
      if (r) { if (this.dados.kick) this.comprarKick(r); else Compra.abrir(this, r); }
    } else if (d.ljAuto) {
      const r = this.dados?.recompensas.find((x) => x.id === d.ljAuto);
      if (r) { if (this.dados.kick) this.autoKick(r); else Auto.abrir(this, r); }
    } else {
      this.carregar();
    }
  },

  // A cada ciclo: saldos da lista de canais em dia; a loja aberta pergunta de novo
  // para a Twitch de minuto em minuto (o "faltam X" acompanha os pontos entrando).
  atualizar() {
    if (!this.el?.isConnected) return;
    this.desenharAbas();
    if (this.aba === 'auto') {
      this.desenharAuto();
      if (Date.now() - (this.autoEm || 0) > 30000) this.carregarAuto();
      return;
    }
    const c = conta(this.login);
    const sel = $('#lj-canal');
    if (c && sel && this.site === 'kick') {
      for (const op of sel.options) {
        const x = (c.kick?.canais || []).find((k) => k.canal === op.value);
        const texto = x ? `${x.canal}${x.saldo != null ? ` · ${fmt(x.saldo)} pontos` : ''}` : null;
        if (texto && op.textContent !== texto) op.textContent = texto;
      }
    } else if (c && sel) {
      for (const op of sel.options) {
        const x = c.canais.find((k) => k.login === op.value);
        const texto = x ? `${x.login}${x.points != null ? ` · ${fmt(x.points)} pontos` : ''}` : null;
        if (texto && op.textContent !== texto) op.textContent = texto;
      }
    }
    if (this.dados) this.desenharItens();  // botão "Compra automática" em dia
    if (this.dados && Date.now() - (this.carregadoEm || 0) > 60000 && !$('#modal').innerHTML) this.carregar(true);
  },
};

/* ---------- Compra (janela da loja) ---------- */
const Compra = {
  abrir(view, r) {
    this.view = view;
    this.r = r;
    this.canal = view.dados.canal;
    this.comprou = false;
    this.infos = {};  // saldo e compras na live de cada conta, direto da Twitch
    $('#modal').innerHTML = `
      <div class="caixa compra">
        ${caraRecompensa(r)}
        <h2>${esc(r.titulo)}</h2>
        <p class="sub" style="margin:0"><b class="ouro">${fmt(r.custo)}</b> pontos por conta, na loja de <b>${esc(this.canal)}</b></p>
        ${r.pergunta ? `<p class="sub" style="margin:0">${esc(r.pergunta)}</p>` : ''}
        ${r.limite_live ? `<p class="cp-limite">${ic('relogio')} <span><b>Regra do streamer:</b> cada conta pode comprar esta só <b>${r.limite_live} ${r.limite_live === 1 ? 'vez' : 'vezes'} por live</b>. Na próxima live, libera de novo.</span></p>` : ''}
        ${r.pede_texto ? '<input id="cp-texto" maxlength="200" placeholder="Essa recompensa pede um texto">' : ''}
        <div class="cp-contas"><div class="cp-rot">Comprar em quais contas?</div><div id="cp-linhas"></div></div>
        <div id="cp-resultado"></div>
        <div class="btns" id="cp-btns"><button class="btn primario" data-cp="comprar" type="button">${ic('loja')} Comprar</button><button class="btn" data-cp="fechar" type="button">Cancelar</button></div>
      </div>`;
    this.desenharContas();
    api(`/api/loja/contas?canal=${encodeURIComponent(this.canal)}&recompensa=${encodeURIComponent(r.id)}`).then((d) => {
      if (this.r !== r || !$('#cp-linhas') || $('#cp-resultado').innerHTML) return;
      this.infos = d.contas;
      this.desenharContas();
    }).catch(() => {});
  },

  desenharContas() {
    const r = this.r;
    const marcadas = new Set([...document.querySelectorAll('.cp-conta input:checked')].map((i) => i.value));
    const primeira = !document.querySelector('.cp-conta');
    $('#cp-linhas').innerHTML = S.estado.contas.map((c) => {
      const info = this.infos[c.login];
      const saldo = info ? info.saldo : c.login === this.view.login
        ? this.view.dados.saldo : conta(c.login)?.canais.find((x) => x.login === this.canal)?.points;
      const limite = info?.limite_live ?? r.limite_live;
      const noLimite = limite && info && info.compradas_live >= limite;
      const falta = saldo != null && saldo < r.custo;
      const bloqueada = falta || noLimite;
      const marcado = !bloqueada && (primeira ? c.login === this.view.login : marcadas.has(c.login));
      let texto = saldo == null ? 'saldo aparece depois' : falta ? `tem ${fmt(saldo)} · faltam ${fmt(r.custo - saldo)}` : `${fmt(saldo)} → ${fmt(saldo - r.custo)}`;
      if (noLimite) texto = `já comprou ${info.compradas_live} de ${limite} nessa live`;
      else if (limite && info) texto += ` · ${info.compradas_live}/${limite} na live`;
      return `
        <label class="cp-conta${bloqueada ? ' falta' : ''}">
          <input type="checkbox" value="${esc(c.login)}" ${marcado ? 'checked' : ''} ${bloqueada ? 'disabled' : ''}>
          <i style="background:${cor(c.login)}"></i><span class="nome">${esc(c.login)}</span><span class="cp-saldo">${texto}</span>
        </label>`;
    }).join('');
  },

  async comprar() {
    const contas = [...document.querySelectorAll('.cp-conta input:checked')].map((i) => i.value);
    if (!contas.length) { toast('Marque pelo menos uma conta', true); return; }
    const texto = $('#cp-texto')?.value.trim() || '';
    if (this.r.pede_texto && !texto) { toast('Essa recompensa pede um texto', true); return; }
    const botao = $('[data-cp="comprar"]');
    botao.disabled = true;
    botao.textContent = contas.length > 1 ? `Comprando em ${contas.length} contas…` : 'Comprando…';
    try {
      const { resultados } = await api('/api/loja/comprar', 'POST', { canal: this.canal, recompensa: this.r.id, contas, texto });
      const certos = resultados.filter((x) => x.ok).length;
      $('#cp-resultado').innerHTML = resultados.map((x) => `
        <div class="cp-res ${x.ok ? 'ok' : 'erro'}">${x.ok ? '✓' : '✗'} <b>${esc(x.conta)}</b>
          ${x.ok ? `comprou${x.saldo != null ? ` · ficou com ${fmt(x.saldo)}` : ''}` : esc(x.erro)}</div>`).join('');
      $('#cp-btns').innerHTML = '<button class="btn primario" data-cp="fechar" type="button">Fechar</button>';
      document.querySelectorAll('.cp-conta input').forEach((i) => { i.disabled = true; });
      if (certos) {
        this.comprou = true;
        toast(certos === resultados.length ? 'Compra feita' : `Comprou em ${certos} de ${resultados.length} contas`);
        ciclo(true);
      }
    } catch (e) {
      toast(e.message, true);
      botao.disabled = false;
      botao.innerHTML = `${ic('loja')} Comprar`;
    }
  },

  fechar() {
    $('#modal').innerHTML = '';
    if (this.comprou && this.view?.el?.isConnected) this.view.carregar();  // saldo novo
  },
};

/* ---------- Compra na loja da Kick (janela) ---------- */
// Igual à da Twitch: escolhe as contas (as que têm a Kick ligada) e compra em cada uma.
const CompraKick = {
  abrir(view, r) {
    this.view = view;
    this.r = r;
    this.canal = view.dados.canal;
    this.comprou = false;
    $('#modal').innerHTML = `
      <div class="caixa compra">
        ${caraRecompensa(r)}
        <h2>${esc(r.titulo)}</h2>
        <p class="sub" style="margin:0"><b class="ouro">${fmt(r.custo)}</b> pontos por conta, na loja de <b>${esc(this.canal)}</b> na Kick</p>
        ${r.descricao ? `<p class="sub" style="margin:0">${esc(r.descricao)}</p>` : ''}
        <div class="cp-contas"><div class="cp-rot">Comprar em quais contas?</div><div id="cpk-linhas"></div></div>
        <div id="cpk-resultado"></div>
        <div class="btns" id="cpk-btns"><button class="btn primario" data-cpk="comprar" type="button">${ic('loja')} Comprar</button><button class="btn" data-cpk="fechar" type="button">Cancelar</button></div>
      </div>`;
    this.desenharContas();
  },

  desenharContas() {
    const r = this.r;
    $('#cpk-linhas').innerHTML = S.estado.contas.map((c) => {
      const k = c.kick || {};
      const ligada = k.ligada && k.estado === 'farmando';
      const saldo = c.login === this.view.login ? this.view.dados.saldo : (k.canais || []).find((x) => x.canal === this.canal)?.saldo;
      const falta = saldo != null && saldo < r.custo;
      const bloqueada = !ligada || falta;
      const marcado = !bloqueada && c.login === this.view.login;
      let texto = !ligada ? (k.ligada ? 'a Kick dessa conta não está farmando agora' : 'sem a Kick ligada') : saldo == null ? 'saldo aparece depois' : falta ? `tem ${fmt(saldo)} · faltam ${fmt(r.custo - saldo)}` : `${fmt(saldo)} → ${fmt(saldo - r.custo)}`;
      return `
        <label class="cp-conta${bloqueada ? ' falta' : ''}">
          <input type="checkbox" value="${esc(c.login)}" ${marcado ? 'checked' : ''} ${bloqueada ? 'disabled' : ''}>
          <i style="background:${cor(c.login)}"></i><span class="nome">${esc(c.login)}</span><span class="cp-saldo">${texto}</span>
        </label>`;
    }).join('');
  },

  async comprar() {
    const contas = [...document.querySelectorAll('#cpk-linhas input:checked')].map((i) => i.value);
    if (!contas.length) { toast('Marque pelo menos uma conta', true); return; }
    const botao = $('[data-cpk="comprar"]');
    botao.disabled = true;
    botao.textContent = contas.length > 1 ? `Comprando em ${contas.length} contas…` : 'Comprando…';
    const cancelar = $('[data-cpk="fechar"]');
    if (cancelar) cancelar.disabled = true;
    const resultados = [];
    for (const login of contas) {
      try {
        await api('/api/kick/comprar', 'POST', { conta: login, canal: this.canal, id: this.r.id, custo: this.r.custo });
        resultados.push({ conta: login, ok: true });
      } catch (e) { resultados.push({ conta: login, ok: false, erro: e.message }); }
    }
    const certos = resultados.filter((x) => x.ok).length;
    if (certos) { this.comprou = true; ciclo(true); }
    if (!$('#cpk-resultado')) return;  // a janela foi fechada
    $('#cpk-resultado').innerHTML = resultados.map((x) => `
      <div class="cp-res ${x.ok ? 'ok' : 'erro'}">${x.ok ? '✓' : '✗'} <b>${esc(x.conta)}</b> ${x.ok ? 'comprou' : esc(x.erro)}</div>`).join('');
    $('#cpk-btns').innerHTML = '<button class="btn primario" data-cpk="fechar" type="button">Fechar</button>';
    document.querySelectorAll('#cpk-linhas input').forEach((i) => { i.disabled = true; });
    if (certos) toast(certos === resultados.length ? 'Compra feita na Kick' : `Comprou em ${certos} de ${resultados.length} contas`);
  },

  fechar() {
    $('#modal').innerHTML = '';
    if (this.comprou && this.view?.el?.isConnected) this.view.carregar(true);
  },
};

$('#modal').addEventListener('click', (ev) => {
  const b = ev.target.closest('[data-cpk]');
  if (!b) return;
  ev.preventDefault();
  if (b.dataset.cpk === 'comprar') CompraKick.comprar();
  else CompraKick.fechar();
});

/* ---------- Compra automática (janela) ---------- */
const PAUSA_MANUAL = 'Pausada por você';  // o mesmo texto de config.MOTIVO_PAUSA_MANUAL
// "03:38" se foi hoje; "14/11 03:38" se não.
function quandoCurto(ts) {
  const d = new Date(ts * 1000);
  const h = d.toLocaleTimeString('pt-BR', { hour: '2-digit', minute: '2-digit' });
  return d.toDateString() === new Date().toDateString() ? h : `${d.toLocaleDateString('pt-BR', { day: '2-digit', month: '2-digit' })} ${h}`;
}
// Compras automáticas ligadas em outras versões da mesma recompensa ("Bônus XP" de 1h quando a aberta é a de 3h).
function outrasVersoes(titulo) {
  return (S.estado?.contas || []).flatMap((c) => (c.auto_compras || [])
    .filter((x) => familia(x.titulo || '') === familia(titulo || '') && !mesmoNome(x.titulo, titulo))
    .map((x) => ({ ...x, conta: c.login })));
}
// Nome da recompensa da Kick para mostrar: ela fica guardada em minúsculas ("bônus +15% xp pokeidle").
function nomeFamilia(f) {
  const nome = String(f || '').replace(/\bxp\b/gi, 'XP').replace(/poke\s*idle/gi, 'PokeIdle')
    .replace(/capture boost/gi, 'Capture Boost').replace(/secret lure/gi, 'Secret Lure');
  return nome.charAt(0).toUpperCase() + nome.slice(1);
}
// Quantas compras automáticas estão ligadas e pausadas (Twitch e Kick), para a aba e o resumo.
function contarAuto() {
  let ligadas = 0;
  let pausadas = 0;
  let porErro = 0;
  const contas = new Set();
  for (const c of S.estado?.contas || []) {
    for (const r of c.auto_compras || []) {
      if (r.pausada) {
        pausadas += 1;
        if (r.pausada !== PAUSA_MANUAL) porErro += 1;
      } else {
        ligadas += 1;
        contas.add(c.login);
      }
    }
    const k = c.kick || {};
    const fams = (k.auto || []).length;
    if (fams && k.resgate_pausado) {
      pausadas += fams;
      porErro += fams;
    } else if (fams && k.ligada) {
      ligadas += fams;
      contas.add(c.login);
    }
  }
  return { ligadas, pausadas, porErro, contas: contas.size };
}
// A mesma recompensa nos outros canais é achada pelo nome (cada canal tem a sua, com preço próprio).
const mesmoNome = (a, b) => (a || '').trim().toLowerCase() === (b || '').trim().toLowerCase();
const hora = (ts) => new Date(ts * 1000).toLocaleTimeString('pt-BR', { hour: '2-digit', minute: '2-digit' });

// "Bônus +15% XP PokeIdle (10h)" = 10 horas; sem "(Nh)" no nome, a descrição diz ("1 hora de...").
function horasDe(r) {
  const m = r.titulo.match(/\(\s*(\d+)\s*h\s*\)/i) || (r.pergunta || '').match(/(\d+)\s*hora/i);
  return m ? Number(m[1]) : null;
}
const familia = (titulo) => titulo.replace(/\(\s*\d+\s*h\s*\)/i, '').trim().toLowerCase();

// Mesma recompensa em versão maior, pelo mesmo preço por hora (ou menos): vale mais no automático.
function versaoMaior(r, recompensas) {
  const h = horasDe(r);
  if (!h) return null;
  return recompensas
    .filter((x) => x.id !== r.id && !x.pede_texto && familia(x.titulo) === familia(r.titulo))
    .map((x) => ({ x, h: horasDe(x) }))
    .filter(({ h: hx }) => hx > h)
    .filter(({ x, h: hx }) => x.custo / hx <= (r.custo / h) * 1.001)
    .sort((a, b) => b.h - a.h)[0] || null;
}

const Auto = {
  async abrir(view, r) {
    if (!S.estado.premium?.ativo) { Premium.abrir('auto'); return; }
    this.view = view;
    this.r = r;
    this.canais = null;
    // Cada conta tem os seus canais: a janela abre na conta da loja, marcando os canais que ELA já usa
    // (se nada, o canal aberto na loja). Outra conta só muda se for marcada também, e aí recebe os mesmos canais.
    const regras = S.estado.contas.flatMap((c) => (c.auto_compras || [])
      .filter((x) => mesmoNome(x.titulo, r.titulo)).map((x) => ({ ...x, conta: c.login })));
    const minhas = regras.filter((x) => x.conta === view.login);
    // Nada ligado nesta versão nessa conta, mas outra (1h, 3h…) está no automático: mostra marcado o que ela usa.
    const outras = minhas.length ? [] : outrasVersoes(r.titulo).filter((x) => x.conta === view.login);
    const base = minhas.length ? minhas : outras;
    this.trocar = [...new Set(outras.map((x) => x.titulo))];
    this.selCanais = new Set(base.length ? base.map((x) => x.canal) : [view.dados?.canal].filter(Boolean));
    this.selContas = new Set([view.login]);
    const nOutras = new Set(outras.map((x) => x.canal)).size;
    const avisoOutra = this.trocar.length ? `
        <div class="au-sugestao">
          <p>${ic('refazer')} <b>${esc(view.login)} já compra ${esc(this.trocar.join(' e '))} no automático</b>, em
            ${nOutras} ${nOutras === 1 ? 'canal' : 'canais'} (marcados abaixo).
            Se salvar aqui, essa conta passa a comprar <b>${esc(r.titulo)}</b> nesses canais e para de comprar a outra versão.</p>
        </div>` : '';
    const maior = versaoMaior(r, view.dados?.recompensas || []);
    this.maior = maior?.x || null;
    const porHora = (x, h) => fmt(x.custo / h);
    const sugestao = maior ? `
        <div class="au-sugestao">
          <p>${ic('lampada')} <b>Compensa mais o de ${maior.h}h.</b> ${esc(maior.x.titulo)} custa ${fmt(maior.x.custo)}: ${porHora(maior.x, maior.h)} por hora,
            ${maior.x.custo / maior.h < r.custo / horasDe(r) ? 'mais barato que' : 'o mesmo preço por hora que'} este.
            ${r.limite_live && !maior.x.limite_live ? `E este tem limite de <b>${r.limite_live} por live</b> em cada conta; o de ${maior.h}h não tem.` : ''}
            No automático, a conta junta ${fmt(maior.x.custo)} pontos e compra vários de uma vez (as horas acumulam no jogo).</p>
          <button class="btn" data-au="maior" type="button">Usar o de ${maior.h}h no automático</button>
        </div>` : '';
    $('#modal').innerHTML = `
      <div class="caixa auto-caixa">
        ${caraRecompensa(r)}
        <div>
          <h2>${ic('refazer')} Compra automática</h2>
          <p class="sub" style="margin:6px 0 0">${esc(r.titulo)}</p>
        </div>
        ${avisoOutra || sugestao}
        <div class="au-explica">
          <p>Quando a conta juntar os pontos em <b>qualquer um dos canais marcados</b>, o Lunar Farm compra <b>${esc(r.titulo)}</b> sozinho naquele canal. Você não precisa abrir a loja nem a Twitch.</p>
          <p class="au-dica">${ic('estrela')} Dica: marque seus canais principais com a estrelinha na página da conta. Assim eles farmam sempre que estiverem ao vivo e o bônus nunca acaba.</p>
          <ul>
            <li>Compra uma atrás da outra até os pontos do canal acabarem. Juntou de novo, compra de novo.</li>
            <li>Cada streamer faz as regras da loja dele: o preço, se só vende com a live no ar e quantas vezes cada conta pode comprar por live (aparece como <b>3/live</b> do lado do preço). O app segue essas regras: chegou no limite, ele espera a próxima live.</li>
            <li>Se o streamer mudar o preço, ele não compra e pausa.</li>
            <li>Se os pontos voltarem (Twitch não vinculada no PokeIdle), ele pausa e avisa.</li>
            <li>Cada compra aparece no Histórico como "(automático)".</li>
          </ul>
        </div>
        <div class="au-bloco">
          <div class="au-topo"><span class="cp-rot">Em quais canais? <span class="au-custo" title="Preço de ${esc(r.titulo)}">${ic('moeda')}${fmt(r.custo)}</span></span>
            <span><button class="btn leve" data-au="todos" type="button">Todos</button><button class="btn leve" data-au="nenhum" type="button">Nenhum</button></span></div>
          <div class="au-legenda" id="au-legenda"></div>
          <div class="au-canais" id="au-canais"><div class="esperando"><span class="roda"></span> Procurando essa recompensa nos seus canais…</div></div>
        </div>
        <div class="au-bloco"><span class="cp-rot">Em quais contas?</span>
          <div class="au-legenda">Só as contas marcadas mudam. Cada conta guarda os canais dela: as outras continuam como estão.</div>
          <div class="au-contas" id="au-contas"></div></div>
        <div class="btns"><button class="btn primario" data-au="salvar" type="button">Salvar</button>${regras.length ? `<button class="btn perigo" data-au="desligar" type="button">${ic('lixo')} Desligar em tudo</button>` : ''}<button class="btn" data-au="fechar" type="button">Cancelar</button></div>
      </div>`;
    this.desenharContas();
    try {
      const d = await api(`/api/auto-compra/canais?titulo=${encodeURIComponent(r.titulo)}`);
      if (this.r !== r || !$('#au-canais')) return;
      this.canais = d.canais;
      this.desenharCanais();
    } catch (e) {
      if ($('#au-canais')) setHTML($('#au-canais'), `<div class="vazio">${esc(e.message)}</div>`);
    }
  },

  desenharCanais() {
    $('#au-canais').innerHTML = this.canais.map((c) => {
      // Canal que não deu para conferir agora continua marcável: marcado, fica como já estava salvo.
      const pode = c.existe || c.falhou;
      const dicas = [];
      if (c.existe) dicas.push(`${esc(this.r.titulo)} custa ${fmt(c.custo)} nesse canal`);
      if (c.existe && c.limite_live) dicas.push(`O streamer deixa cada conta comprar ${c.limite_live} ${c.limite_live === 1 ? 'vez' : 'vezes'} por live`);
      if (c.falhou) dicas.push('Não deu para conferir esse canal agora. Se ficar marcado, continua como já estava salvo.');
      if (!pode) dicas.push('Esse canal não tem essa recompensa');
      return `
        <label class="au-canal${pode ? '' : ' sem'}${c.falhou ? ' falhou' : ''}" title="${esc(dicas.join('. '))}">
          <input type="checkbox" data-au-canal="${esc(c.canal)}" ${pode && this.selCanais.has(c.canal) ? 'checked' : ''} ${pode ? '' : 'disabled'}>
          <span class="nome">${esc(c.canal)}</span>
          <span class="preco" data-au-saldo="${esc(c.canal)}">${c.existe ? '' : c.falhou ? 'não deu para ver' : 'não tem'}</span>
        </label>`;
    }).join('');
    this.desenharSaldos();
  },

  // Ao lado de cada canal, os pontos que a conta marcada tem nele (várias contas: a soma; cada uma aparece na dica).
  // Dourado quando alguma conta já tem o bastante para comprar; cinza quando ainda falta.
  desenharSaldos() {
    if (!this.canais || !$('#au-canais')) return;
    let logins = [...document.querySelectorAll('[data-au-conta]:checked')].map((i) => i.dataset.auConta);
    if (!logins.length) logins = [this.view?.login].filter(Boolean);
    const legenda = $('#au-legenda');
    if (legenda) {
      legenda.textContent = logins.length > 1 ? `Ao lado de cada canal: a soma dos pontos das ${logins.length} contas marcadas`
        : logins.length ? `Ao lado de cada canal: os pontos de ${logins[0]} nele` : '';
    }
    for (const c of this.canais) {
      const el = document.querySelector(`[data-au-saldo="${CSS.escape(c.canal)}"]`);
      if (!el || !c.existe) continue;
      const partes = logins.map((l) => ({ l, p: conta(l)?.canais?.find((x) => x.login === c.canal)?.points }))
        .filter((x) => x.p != null);
      const total = partes.reduce((soma, x) => soma + x.p, 0);
      // Embaixo do saldo, pequeno: o preço quando é outro nesse canal e o limite por live.
      const extras = [c.custo !== this.r.custo ? `custa ${fmt(c.custo)}` : '', c.limite_live ? `${c.limite_live}/live` : '']
        .filter(Boolean).join(' · ');
      el.innerHTML = `<span class="v">${partes.length ? `${ic('moeda')}${fmt(total)}` : '<span class="apagado">—</span>'}</span>`
        + (extras ? `<small>${extras}</small>` : '');
      el.classList.toggle('falta', !partes.some((x) => x.p >= c.custo));
      el.title = partes.length > 1 ? partes.map((x) => `${x.l}: ${fmt(x.p)}`).join('\n') : '';
    }
  },

  desenharContas() {
    $('#au-contas').innerHTML = S.estado.contas.map((c) => {
      const regras = (c.auto_compras || []).filter((x) => mesmoNome(x.titulo, this.r.titulo));
      const ativas = regras.filter((x) => !x.pausada).length;
      const pausadas = regras.filter((x) => x.pausada);
      const ultima = Math.max(0, ...regras.map((x) => x.ultima_compra || 0));
      const esperando = regras.filter((x) => !x.pausada && x.aviso);
      const daOutra = regras.length ? [] : (c.auto_compras || []).filter((x) => familia(x.titulo || '') === familia(this.r.titulo));
      let info = regras.length ? `ligado em ${ativas} ${ativas === 1 ? 'canal' : 'canais'}`
        : daOutra.length ? `em outra versão: ${daOutra.length} ${daOutra.length === 1 ? 'canal' : 'canais'}` : 'desligado';
      if (pausadas.length) info += ` · ${pausadas.length} pausado${pausadas.length > 1 ? 's' : ''}`;
      if (esperando.length) info += ` · ${esperando.length} esperando`;
      if (ultima) info += ` · última compra ${hora(ultima)}`;
      const dica = [...pausadas.map((x) => `${x.canal}: ${x.pausada}`), ...esperando.map((x) => `${x.canal}: ${x.aviso}`)].join('\n');
      return `
        <label class="cp-auto-linha${pausadas.length ? ' pausada' : ''}" title="${esc(dica)}">
          <input type="checkbox" data-au-conta="${esc(c.login)}" ${this.selContas.has(c.login) ? 'checked' : ''}>
          <i style="background:${cor(c.login)}"></i><span class="nome">${esc(c.login)}</span><span class="cp-saldo">${esc(info)}</span>
        </label>`;
    }).join('');
  },

  marcarCanais(ligar) {
    document.querySelectorAll('[data-au-canal]:not(:disabled)').forEach((i) => { i.checked = ligar; });
  },

  async salvar() {
    if (!this.canais) { toast('Espere terminar de procurar os canais', true); return; }
    const canais = [...document.querySelectorAll('[data-au-canal]:checked')].map((i) => i.dataset.auCanal);
    const contas = [...document.querySelectorAll('[data-au-conta]:checked')].map((i) => i.dataset.auConta);
    if (!contas.length) { toast('Marque a conta que vai usar esses canais', true); return; }
    const botao = $('[data-au="salvar"]');
    botao.disabled = true;
    botao.textContent = 'Salvando…';
    try {
      const d = await api('/api/auto-compra/salvar', 'POST', { titulo: this.r.titulo, canais, contas });
      if (d.ligadas && this.trocar?.length) {
        for (const titulo of this.trocar) {
          for (const conta of contas) await api('/api/auto-compra/mudar', 'POST', { acao: 'desligar', titulo, conta });
        }
        toast(`Trocou para ${this.r.titulo} no automático`);
      }
      const quem = contas.length === 1 ? contas[0] : `${contas.length} contas`;
      toast(d.ligadas
        ? `Compra automática ligada em ${quem}: ${canais.length} ${canais.length === 1 ? 'canal' : 'canais'}`
        : `Compra automática desligada em ${quem}`);
      if (d.nao_conferidos?.length) toast(`Não deu para conferir ${d.nao_conferidos.join(', ')} agora: ficou como estava`);
      await ciclo(true);
      this.fechar();
    } catch (e) {
      toast(e.message, true);
      botao.disabled = false;
      botao.textContent = 'Salvar';
    }
  },

  // Desliga essa recompensa em todas as contas e canais de uma vez.
  async desligar() {
    if (!confirm(`Desligar a compra automática de "${this.r.titulo}" em todas as contas e canais?`)) return;
    try {
      const d = await api('/api/auto-compra/mudar', 'POST', { acao: 'desligar', titulo: this.r.titulo });
      toast(d.mudadas ? 'Compra automática desligada para essa recompensa' : 'Ela já estava desligada');
      await ciclo(true);
      this.fechar();
    } catch (e) {
      toast(e.message, true);
    }
  },

  fechar() {
    $('#modal').innerHTML = '';
    if (this.view?.el?.isConnected) {  // botão e painel com o estado novo
      this.view.desenharItens();
      this.view.desenharAuto?.();
    }
  },
};

$('#modal').addEventListener('change', (ev) => {
  if (ev.target.matches('[data-au-conta]')) Auto.desenharSaldos();
});
$('#modal').addEventListener('click', (ev) => {
  const b = ev.target.closest('[data-cp], [data-au]');
  if (!b) return;
  ev.preventDefault();
  const acao = b.dataset.au;
  if (acao === 'salvar') Auto.salvar();
  else if (acao === 'todos' || acao === 'nenhum') Auto.marcarCanais(acao === 'todos');
  else if (acao === 'maior' && Auto.maior) Auto.abrir(Auto.view, Auto.maior);
  else if (acao === 'desligar') Auto.desligar();
  else if (acao) Auto.fechar();
  else if (b.dataset.cp === 'comprar') Compra.comprar();
  else Compra.fechar();
});

/* ---------- Histórico ---------- */
VIEWS.historico = {
  montar(el, login) {
    this.el = el;
    this.itens = [];
    el.innerHTML = `
      <div class="topo">
        <div><h1>Histórico</h1><div class="sub">Tudo que o farm fez, do mais novo para o mais antigo</div></div>
        <div class="filtros">
          <select id="h-conta"><option value="">Todas as contas</option>${S.estado.contas.map((c) => `<option value="${esc(c.login)}">${esc(c.login)}</option>`).join('')}</select>
          <label class="check"><input type="checkbox" id="h-assistir"> Mostrar os +10 de assistir</label>
        </div>
      </div>
      <section class="card"><div id="h-lista"></div>
        <div style="text-align:center;margin-top:14px"><button class="btn" id="h-mais">Carregar mais</button></div>
      </section>`;
    if (login) $('#h-conta').value = login;
    $('#h-conta').addEventListener('change', () => this.carregar(true));
    $('#h-assistir').addEventListener('change', () => this.carregar(true));
    $('#h-mais').addEventListener('click', () => this.carregar(false));
    this.carregar(true);
  },
  async carregar(doZero) {
    const contaSel = $('#h-conta').value;
    const assistir = $('#h-assistir').checked ? '1' : '0';
    const antes = !doZero && this.itens.length ? `&antes=${this.itens[this.itens.length - 1].ts}` : '';
    try {
      const novos = await api(`/api/historico?conta=${encodeURIComponent(contaSel)}&assistir=${assistir}&limite=150${antes}`);
      this.itens = doZero ? novos : this.itens.concat(novos);
      $('#h-mais').style.display = novos.length < 150 ? 'none' : '';
      setHTML($('#h-lista'), linhaDoTempo(this.itens, !contaSel, 0, true));
    } catch (e) { toast(e.message, true); }
  },
  atualizar() {},
};

/* ---------- Celular ---------- */
VIEWS.celular = {
  async montar(el) {
    this.el = el;
    el.innerHTML = `
      <div class="topo"><div><h1>Celular</h1><div class="sub">Veja e controle o farm pelo celular, Android ou iPhone</div></div></div>
      <section class="card">
        <div class="opcao">
          <div><b>Abrir o painel no celular</b><p>O celular precisa estar no mesmo Wi-Fi deste PC. O farm continua rodando aqui no PC.</p></div>
          <label class="chave"><input type="checkbox" id="m-liga"><span></span></label>
        </div>
      </section>
      <section class="card" id="m-info" style="display:none"></section>`;
    $('#m-liga').addEventListener('change', async (ev) => {
      try { this.mostrar(await api('/api/celular', 'POST', { ligado: ev.target.checked })); } catch (e) { toast(e.message, true); }
    });
    el.addEventListener('click', async (ev) => {
      if (ev.target.closest('#m-pin')) {
        try { this.mostrar(await api('/api/celular', 'POST', { novo_pin: true })); toast('PIN trocado'); } catch (e) { toast(e.message, true); }
      }
    });
    try { this.mostrar(await api('/api/celular')); } catch (e) { toast(e.message, true); }
  },
  mostrar(m) {
    $('#m-liga').checked = m.ligado;
    const info = $('#m-info');
    info.style.display = m.ligado ? '' : 'none';
    if (!m.ligado) return;
    info.innerHTML = `
      <div class="celular">
        <div class="qr">${m.qr}</div>
        <div style="display:flex;flex-direction:column;gap:12px">
          <div><div class="sub">PIN</div><div class="pin">${esc(m.pin)}</div></div>
          <div><div class="sub">Endereço</div><b>${esc(m.url)}</b></div>
          <ol class="passo-a-passo">
            <li>Aponte a câmera do celular para o QR code.</li>
            <li>Digite o PIN acima.</li>
            <li><b>Android:</b> no Chrome, toque em ⋮ e depois em <b>Adicionar à tela inicial</b>.</li>
            <li><b>iPhone:</b> no Safari, toque em Compartilhar e depois em <b>Adicionar à Tela de Início</b>.</li>
          </ol>
          <p class="nota" style="margin:0">Se o Windows perguntar se o Lunar Farm pode usar a rede, marque <b>Redes privadas</b> e clique em <b>Permitir acesso</b>.</p>
          <div><button class="btn" id="m-pin">Trocar o PIN</button></div>
        </div>
      </div>`;
  },
  atualizar() {},
};

/* ---------- Configurações ---------- */
VIEWS.opcoes = {
  async montar(el) {
    this.el = el;
    let o;
    try { o = await api('/api/opcoes'); } catch (e) { toast(e.message, true); return; }
    const chave = (id, titulo, texto, ligado) => `
      <div class="opcao"><div><b>${titulo}</b><p>${texto}</p></div>
        <label class="chave"><input type="checkbox" data-op="${id}" ${ligado ? 'checked' : ''}><span></span></label></div>`;
    el.innerHTML = `
      <div class="topo"><div><h1>Configurações</h1></div></div>
      <section class="card">
        ${chave('start_with_windows', 'Iniciar com o Windows', 'Liga o farm sozinho quando o PC ligar, sem abrir a janela.', o.start_with_windows)}
        ${chave('keep_awake', 'Não deixar o PC dormir', 'Com o Lunar Farm aberto, o PC não entra em suspensão (a tela pode apagar normalmente). Se o PC dormir, o farm para.', o.keep_awake)}
        ${chave('auto_follow', 'Seguir os canais da lista', 'Cada conta segue sozinha os canais da lista da Twitch (a Twitch dá 300 pontos na primeira vez). Na Kick, siga pelo botão + Seguir de cada canal (a Kick dá 50). Os avisos de live por e-mail ficam desligados.', o.auto_follow)}
        <div class="opcao">
          <div><b>Chat dos canais</b><p>Igual ao Chatterino: a conta fica conectada no chat dos canais da lista. Mudar isso reinicia o farm das contas.</p></div>
          <select id="o-chat"><option value="sempre">Em todos, sempre</option><option value="ao_vivo">Só nos que estão ao vivo</option></select>
        </div>
      </section>
      <section class="card">
        <div class="opcao"><div><b>Versão ${esc(S.estado?.versao)}</b><p id="o-versao"></p></div><button class="btn" id="o-conferir" type="button">${ic('refazer')} Procurar atualização</button></div>
        <div class="opcao"><div><b>Histórico de versões</b><p>O que mudou em cada atualização do Lunar Farm.</p></div><button class="btn" id="o-historico" type="button">Ver o que mudou</button></div>
      </section>
      <section class="card">
        <div class="opcao"><div><b>Pasta dos dados</b><p>${esc(o.pasta_dados)}<br>Logins e histórico ficam aqui, separados do programa.</p></div><button class="btn" id="o-pasta">Abrir pasta</button></div>
        <div class="opcao"><div><b>Sair do Lunar Farm</b><p>Para o farm de todas as contas e fecha o app. Fechar só a janela não para o farm.</p></div><button class="btn perigo" id="o-sair">Sair e parar o farm</button></div>
      </section>
      <p class="nota" style="text-align:center">Lunar Farm ${esc(S.estado?.versao)} · usa o Twitch Channel Points Miner (fork Armi1014, licença GPL-3.0)</p>`;
    $('#o-chat').value = o.chat_mode;
    el.addEventListener('change', async (ev) => {
      const alvo = ev.target;
      const novo = alvo.dataset.op ? { [alvo.dataset.op]: alvo.checked } : alvo.id === 'o-chat' ? { chat_mode: alvo.value } : null;
      if (!novo) return;
      try { await api('/api/opcoes', 'POST', novo); toast('Salvo'); } catch (e) { toast(e.message, true); }
    });
    const versao = (a) => {
      $('#o-conferir').style.display = a.ligado ? '' : 'none';
      if (a.loja) {
        $('#o-versao').textContent = 'Instalado pela Microsoft Store: as versões novas chegam pela própria Store, sozinhas.';
      } else if (!a.instalado) {
        $('#o-versao').textContent = 'Esta cópia roda da pasta de desenvolvimento, então não se atualiza sozinha. Quem instalou pelo instalador recebe as versões novas pelo próprio app.';
      } else if (!a.ligado) {
        $('#o-versao').textContent = 'A atualização pelo app ainda não está configurada nesta versão.';
      } else {
        const quando = a.conferido_em ? ` Última conferida às ${new Date(a.conferido_em * 1000).toLocaleTimeString('pt-BR', { hour: '2-digit', minute: '2-digit' })}.` : '';
        $('#o-versao').textContent = `O app confere sozinho se saiu versão nova (de hora em hora) e abre uma janela mostrando o que muda.${quando}`;
      }
    };
    versao(S.estado.atualizacao);
    $('#o-conferir').addEventListener('click', async (ev) => {
      ev.target.disabled = true;
      try {
        const a = await api('/api/atualizacao/conferir', 'POST');
        versao(a);
        await ciclo(true);
        if (a.nova) atualizarApp();
        else toast('Você já está na versão mais nova');
      } catch (e) { toast(e.message, true); }
      ev.target.disabled = false;
    });
    $('#o-historico').addEventListener('click', () => Versao.abrirHistorico());
    $('#o-pasta').addEventListener('click', () => api('/api/pasta', 'POST').catch((e) => toast(e.message, true)));
    $('#o-sair').addEventListener('click', async () => {
      if (!confirm('Parar o farm de todas as contas e fechar o Lunar Farm?')) return;
      await api('/api/sair', 'POST').catch(() => {});
      S.fechado = true;
      document.body.innerHTML = '<div class="boas" style="min-height:100vh;justify-content:center"><img src="/static/icon-192.png" alt=""><h1>Lunar Farm fechado</h1><p>O farm parou. Para ligar de novo, abra o Lunar Farm pelo atalho.</p></div>';
      setTimeout(() => window.close(), 1200);
    });
  },
  atualizar() {},
};

/* ---------- Lunar Premium (removido) ---------- */
// O Lunar Farm vem com tudo liberado: sem plano pago, sem chave e sem Pix. O stub mantém
// as poucas chamadas Premium.abrir() espalhadas pelo código como no-ops seguros.
const Premium = { abrir() {} };


/* ---------- Indicar a um amigo ---------- */
// O link leva um código curto deste PC (?ref=amigo-xxxxxx): o painel do site conta quantos amigos
// cada PC trouxe. Não diz quem é a pessoa.
const Indicar = {
  mensagem() {
    return `Tô usando o Lunar Farm pra farmar ponto da Twitch sem deixar live aberta. Ele pega o baú sozinho e troca de live quando acaba. É grátis pra Windows: ${S.estado.indicar}`;
  },
  abrir() {
    if (!S.estado?.indicar) return;
    $('#modal').innerHTML = `
      <div class="caixa" data-janela="indicar">
        <div class="pm-coroa grande">${ic('presente')}</div>
        <h2>Indique o Lunar Farm para um amigo</h2>
        <p class="sub" style="margin:0">Mande o link para quem também farma pontos da Twitch. Baixar é grátis.</p>
        <textarea class="ind-msg" readonly rows="4" aria-label="Mensagem para o amigo">${esc(this.mensagem())}</textarea>
        <div class="btns">
          <button class="btn primario" data-ind="whats" type="button">Mandar no WhatsApp</button>
          <button class="btn" data-ind="copiar" type="button">${ic('copiar')} Copiar mensagem</button>
          <button class="btn leve" data-ind="fechar" type="button">Fechar</button>
        </div>
      </div>`;
  },
};
$('#modal').addEventListener('click', (ev) => {
  const b = ev.target.closest('[data-ind]');
  if (!b) return;
  ev.preventDefault();
  const acao = b.dataset.ind;
  if (acao === 'whats') abrirLink(`https://wa.me/?text=${encodeURIComponent(Indicar.mensagem())}`);
  else if (acao === 'copiar') copiar(Indicar.mensagem());
  else $('#modal').innerHTML = '';
});

/* ---------- Ajuda e suporte (tickets) ---------- */
const ASSUNTOS = [['pagamento', 'Pagamento / Premium'], ['farm', 'Problema no farm'], ['conta', 'Conta da Twitch'], ['duvida', 'Dúvida'], ['outro', 'Outro']];
const STATUS_TICKET = { aberto: 'Esperando resposta', respondido: 'Respondido', fechado: 'Fechado' };
const quandoTicket = (ts) => new Date(ts * 1000).toLocaleString('pt-BR', { dateStyle: 'short', timeStyle: 'short' });

VIEWS.suporte = {
  async montar(el, arg) {
    this.el = el;
    this.ticket = null;
    if (arg && arg.startsWith('novo')) return this.novo(arg.split('-')[1]);
    if (arg) return this.abrir(arg);
    el.innerHTML = `
      <div class="topo"><div><h1>Ajuda e suporte</h1><div class="sub">Abra um ticket e a resposta aparece aqui mesmo</div></div>
        <a class="btn primario" href="#/suporte/novo">${ic('mais')} Abrir um ticket</a></div>
      <section class="card"><div id="sp-lista"><div class="esperando"><span class="roda"></span> Carregando…</div></div></section>
      <p class="nota">Quer saber o que o Lunar Farm guarda e o que fica só no seu PC? Veja a <a href="#" data-privacidade>política de privacidade</a>.</p>`;
    el.querySelector('[data-privacidade]').addEventListener('click', (ev) => { ev.preventDefault(); abrirLink('https://vexpulse.com.br/privacidade/'); });
    let d;
    try { d = await api('/api/suporte?atualizar=1'); } catch (e) { setHTML($('#sp-lista'), `<div class="vazio">${esc(e.message)}</div>`); return; }
    if (!this.el.isConnected) return;
    setHTML($('#sp-lista'), d.tickets.length ? d.tickets.map((t) => `
      <a class="sp-item" href="#/suporte/${encodeURIComponent(t.ticket)}">
        <div><b>${esc(t.ticket)}</b> · ${esc(t.assunto_nome || '')}${t.resposta_nova ? ' <span class="sp-nova">Resposta nova</span>' : ''}
          <p>${t.ultimo_autor === 'suporte' ? 'Suporte: ' : ''}${esc(t.ultima || '')}</p></div>
        <span class="sp-status ${esc(t.status || 'aberto')}">${STATUS_TICKET[t.status] || 'Aberto'}</span>
      </a>`).join('') : `
      <div class="vazio">Nenhum ticket ainda.<br>Problema com o pagamento, o farm ou alguma conta? Abra um ticket que a gente responde aqui mesmo.</div>`);
  },

  novo(assunto) {
    this.el.innerHTML = `
      <div class="topo"><div><h1>Abrir um ticket</h1><div class="sub">A resposta aparece em Ajuda e suporte e num aviso perto do relógio</div></div>
        <a class="btn" href="#/suporte">Voltar</a></div>
      <form class="card sp-form" id="sp-form">
        <label>Assunto<select id="sp-assunto" required><option value="">Escolha…</option>
          ${ASSUNTOS.map(([id, nome]) => `<option value="${id}" ${id === assunto ? 'selected' : ''}>${nome}</option>`).join('')}</select></label>
        <label>O que aconteceu?<textarea id="sp-mensagem" maxlength="4000" required placeholder="Conte com detalhes: o que você fez, o que apareceu na tela e, se for pagamento, o horário do Pix."></textarea></label>
        <label>Como falar com você <span class="sub">(opcional: Discord, e-mail…)</span><input id="sp-contato" maxlength="120"></label>
        <label class="check"><input type="checkbox" id="sp-registro"> Incluir o registro do app (ajuda em problemas no farm; mostra os nomes das suas contas da Twitch)</label>
        <p class="sub" style="margin:0">Vai junto com o ticket: a versão do app, se é grátis ou Premium e o último Pix gerado.</p>
        <div class="btns"><button class="btn primario" type="submit">Enviar ticket</button></div>
      </form>`;
    $('#sp-form').addEventListener('submit', async (ev) => {
      ev.preventDefault();
      const b = ev.target.querySelector('button[type="submit"]');
      b.disabled = true;
      try {
        const t = await api('/api/suporte/criar', 'POST', {
          assunto: $('#sp-assunto').value, mensagem: $('#sp-mensagem').value, contato: $('#sp-contato').value, com_registro: $('#sp-registro').checked,
        });
        toast(`Ticket ${t.ticket} aberto. A gente responde aqui mesmo.`);
        location.hash = `#/suporte/${encodeURIComponent(t.ticket)}`;
      } catch (e) { toast(e.message, true); b.disabled = false; }
    });
  },

  async abrir(ticket) {
    this.ticket = ticket;
    this.el.innerHTML = `
      <div class="topo"><div><h1>Ticket ${esc(ticket)}</h1><div class="sub" id="sp-assunto-ver"></div></div>
        <a class="btn" href="#/suporte">Voltar</a></div>
      <section class="card"><div class="sp-conversa" id="sp-conversa"><div class="esperando"><span class="roda"></span> Carregando…</div></div>
        <form class="sp-responder" id="sp-responder"><textarea id="sp-resposta" maxlength="4000" placeholder="Escreva a sua resposta"></textarea>
          <button class="btn primario" type="submit">Enviar</button></form></section>`;
    $('#sp-responder').addEventListener('submit', async (ev) => {
      ev.preventDefault();
      try {
        this.desenhar(await api(`/api/suporte/${encodeURIComponent(ticket)}/responder`, 'POST', { mensagem: $('#sp-resposta').value }));
        $('#sp-resposta').value = '';
      } catch (e) { toast(e.message, true); }
    });
    await this.recarregar();
  },

  async recarregar() {
    const ticket = this.ticket;
    try {
      const t = await api(`/api/suporte/${encodeURIComponent(ticket)}`);
      if (this.ticket === ticket && this.el.isConnected) this.desenhar(t);
    } catch (e) { setHTML($('#sp-conversa'), `<div class="vazio">${esc(e.message)}</div>`); }
    this.carregadoEm = Date.now();
  },

  desenhar(t) {
    setHTML($('#sp-assunto-ver'), `${esc(t.assunto_nome)} · <span class="sp-status ${esc(t.status)}">${STATUS_TICKET[t.status] || t.status}</span>`);
    setHTML($('#sp-conversa'), t.mensagens.map((m) => `
      <div class="sp-msg ${m.autor}"><span class="quem">${m.autor === 'suporte' ? 'Suporte Lunar Farm' : 'Você'} · ${quandoTicket(m.quando)}</span>${esc(m.texto)}</div>`).join(''));
  },

  atualizar() {
    // Conversa aberta: confere a cada 30 s se o suporte respondeu.
    if (this.ticket && Date.now() - (this.carregadoEm || 0) > 30000) this.recarregar();
  },
};

/* ---------- Login com código ---------- */
// Vídeo de 1 minuto mostrando como conectar a conta (fica no site; o app só toca).
const TUTORIAL = {
  video: 'https://vexpulse.com.br/video/tutorial-conectar-conta.mp4?v=1',
  capa: 'https://vexpulse.com.br/video/tutorial-conectar-conta-capa.jpg?v=1',
};
function htmlTutorial(aberto) {
  if (!aberto) return `<button class="btn leve" data-l="video">${ic('play')} Ver como fazer (1 minuto)</button>`;
  return `<video src="${TUTORIAL.video}" poster="${TUTORIAL.capa}" controls preload="none" playsinline
    onerror="this.parentElement.innerHTML='<p class=&quot;nota&quot; style=&quot;margin:0&quot;>Não deu para carregar o vídeo agora. Siga os passos abaixo.</p>'"></video>`;
}

const Login = {
  timer: null,
  alvo: null,
  estado: null,
  async abrir(alvo) {
    this.alvo = alvo || null;
    const p = S.estado?.premium;
    if (!this.alvo && p && !p.ativo && S.estado.contas.length >= p.limites.contas) { Premium.abrir('conta'); return; }
    this.mostrar({ fase: 'carregando' });
    try { this.mostrar(await api('/api/login/iniciar', 'POST', { alvo: this.alvo })); } catch (e) { if (!e.premium) this.mostrar({ fase: 'erro', erro: e.message }); }
    this.vigiar();
  },
  vigiar() {
    clearTimeout(this.timer);
    this.timer = setTimeout(async () => {
      if (!$('#modal').innerHTML) return;
      try {
        const st = await api('/api/login');
        this.mostrar(st);
        if (st.fase === 'esperando') this.vigiar();
      } catch (e) { this.vigiar(); }
    }, 2000);
  },
  fechar(cancelar = true) {
    clearTimeout(this.timer);
    $('#modal').innerHTML = '';
    $('#modal').dataset.codigo = '';
    if (cancelar) api('/api/login/cancelar', 'POST').catch(() => {});
  },
  mostrar(st) {
    const m = $('#modal');
    this.estado = st;
    if (st.fase === 'esperando') {
      const tempo = `${Math.floor(st.segundos / 60)}:${String(st.segundos % 60).padStart(2, '0')}`;
      if (m.dataset.codigo === st.codigo) { $('#l-tempo').textContent = tempo; return; }
      m.dataset.codigo = st.codigo;
      const codigo = st.codigo.length === 8 ? `${st.codigo.slice(0, 4)}-${st.codigo.slice(4)}` : st.codigo;
      m.innerHTML = `
        <div class="caixa">
          <h2>${this.alvo ? `Entrar de novo na conta ${esc(this.alvo)}` : 'Adicionar uma conta da Twitch'}</h2>
          <div class="tutorial" id="l-tutorial">${htmlTutorial(!this.alvo && !(S.estado?.contas || []).length)}</div>
          <ol>
            <li>Clique em <b>Abrir twitch.tv/activate</b> e entre na conta que você quer ${this.alvo ? 'reconectar' : 'adicionar'}.</li>
            <li>Confira se o código é este e clique em <b>Ativar</b>.</li>
          </ol>
          <div class="codigo">${esc(codigo)}</div>
          <div class="btns">
            <button class="btn primario" data-l="abrir">${ic('abrir')} Abrir twitch.tv/activate</button>
            <button class="btn" data-l="copiar">${ic('copiar')} Copiar código</button>
          </div>
          <p class="nota" style="margin:0">O navegador já está logado em outra conta? Abra uma janela anônima (Ctrl+Shift+N), entre na conta certa e cole o link: <a href="#" data-l="link">copiar link</a></p>
          <div class="esperando"><span class="roda"></span> Esperando a Twitch confirmar… vence em <span id="l-tempo">${tempo}</span></div>
          <button class="btn leve" data-l="cancelar">Cancelar</button>
        </div>`;
      return;
    }
    m.dataset.codigo = '';
    if (st.fase === 'carregando') {
      m.innerHTML = '<div class="caixa"><div class="esperando"><span class="roda"></span> Pedindo um código para a Twitch…</div></div>';
    } else if (st.fase === 'pronto') {
      const login = st.login;
      m.innerHTML = `
        <div class="caixa">
          <div class="grande-ok">✓</div>
          <h2>Conta ${esc(login)} conectada</h2>
          <p class="sub" style="margin:0">${this.alvo && this.alvo !== login ? `Atenção: você entrou na conta <b>${esc(login)}</b>, não na ${esc(this.alvo)}.` : 'O login fica salvo. Da próxima vez ela entra sozinha.'}</p>
          <div class="btns"><button class="btn primario" data-l="ir" data-login="${esc(login)}">Ver a conta</button><button class="btn" data-l="outra">Adicionar outra</button></div>
        </div>`;
      ciclo(true);
    } else if (st.fase === 'expirou') {
      m.innerHTML = `
        <div class="caixa"><h2>O código venceu</h2><p class="sub" style="margin:0">Cada código vale 30 minutos. É só gerar outro.</p>
          <div class="btns"><button class="btn primario" data-l="outra">Gerar outro código</button><button class="btn" data-l="cancelar">Fechar</button></div></div>`;
    } else if (st.fase === 'premium') {
      Premium.abrir('conta');  // entrou numa conta nova, mas a versão grátis só tem 1
    } else if (st.fase === 'erro') {
      m.innerHTML = `
        <div class="caixa"><h2>Não deu certo</h2><p class="sub" style="margin:0">${esc(st.erro || 'Erro desconhecido')}</p>
          <div class="btns"><button class="btn primario" data-l="outra">Tentar de novo</button><button class="btn" data-l="cancelar">Fechar</button></div></div>`;
    } else {
      this.fechar(false);
    }
  },
};

$('#modal').addEventListener('click', (ev) => {
  const b = ev.target.closest('[data-l]');
  if (!b) return;
  ev.preventDefault();
  const st = Login.estado || {};
  const acao = b.dataset.l;
  if (acao === 'abrir') abrirLink(st.link || 'https://www.twitch.tv/activate');
  else if (acao === 'copiar') copiar(st.codigo || '');
  else if (acao === 'video') {
    const caixa = $('#l-tutorial');
    caixa.innerHTML = htmlTutorial(true);
    caixa.querySelector('video')?.play().catch(() => {});
  }
  else if (acao === 'link') copiar(st.link || 'https://www.twitch.tv/activate');
  else if (acao === 'cancelar') Login.fechar(true);
  else if (acao === 'outra') Login.abrir(null);
  else if (acao === 'ir') { Login.fechar(false); location.hash = `#/conta/${encodeURIComponent(b.dataset.login)}`; }
});

/* ---------- PIN (celular) ---------- */
function telaPin() {
  if (S.pin) return;
  S.pin = true;
  document.body.innerHTML = `
    <div class="boas" style="min-height:100dvh;justify-content:center">
      <img src="/static/icon-192.png" alt="">
      <h1>Lunar Farm</h1>
      <p>Digite o PIN que aparece no PC, na tela <b>Celular</b>.</p>
      <form id="pin-form" class="add" style="max-width:280px;width:100%">
        <input id="pin" inputmode="numeric" autocomplete="one-time-code" maxlength="8" placeholder="PIN" style="text-align:center;font-size:20px;letter-spacing:.3em">
        <button class="btn primario">Entrar</button>
      </form>
      <div id="pin-erro" class="sub"></div>
    </div>`;
  $('#pin-form').addEventListener('submit', async (ev) => {
    ev.preventDefault();
    try {
      await api('/api/pin', 'POST', { pin: $('#pin').value });
      location.reload();
    } catch (e) { $('#pin-erro').textContent = e.message; }
  });
  $('#pin').focus();
}

/* ---------- ciclo ---------- */
let ultimoCiclo = null;
async function ciclo(forcar) {
  if (S.pin || S.fechado) return;
  try {
    S.estado = await api('/api/estado');
    if (!S.atalhos) api('/api/atalhos').then((a) => { S.atalhos = a; }).catch(() => {});
    const janelaAberta = /cp-contas|au-contas/.test($('#modal').innerHTML);  // não atrapalha uma compra aberta
    if (MEU_CARIMBO && S.estado.carimbo && S.estado.carimbo !== MEU_CARIMBO && !janelaAberta) {
      location.reload();  // o app foi atualizado (sem atrapalhar uma compra aberta)
      return;
    }
    if (S.offline) { S.offline = false; $('#modal').innerHTML = ''; }
    if (!S.view) montar();
    desenharLado();
    desenharFaixa();
    Versao.conferir();
    if (S.estado.suporte_novas > (S.novasSuporte ?? S.estado.suporte_novas)) toast('O suporte respondeu o seu ticket: veja em Ajuda e suporte');
    S.novasSuporte = S.estado.suporte_novas;
    await S.view?.atualizar?.(forcar);
  } catch (e) {
    if (e.offline && !S.offline) {
      S.offline = true;
      const texto = S.estado?.atualizacao?.fase === 'instalando'
        ? 'Instalando a versão nova… o Lunar Farm abre de novo sozinho.'
        : 'Sem conexão com o Lunar Farm. Ele foi fechado? Tentando de novo…';
      $('#modal').innerHTML = `<div class="caixa"><div class="esperando"><span class="roda"></span> ${texto}</div></div>`;
    }
  }
}
function loop() {
  clearTimeout(ultimoCiclo);
  ciclo().finally(() => { ultimoCiclo = setTimeout(loop, 3000); });
}
loop();

Indicar.abrir = function () {};
/* Lunar Farm: só Resumo, Loja e as contas. */
for (const v of ['historico', 'suporte', 'celular', 'opcoes']) delete VIEWS[v];

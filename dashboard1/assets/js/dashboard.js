/**
 * dashboard.js
 * Observatório do Emprego — Natal/RN
 * Fetch assíncrono + manipulação de DOM + Chart.js
 */

/* ============================================================
   CONFIGURAÇÃO
   ============================================================ */
const API_URL    = 'http://127.0.0.1:8000/api/dashboard';
const STATUS_URL = 'http://127.0.0.1:8000/api/status';
const POLL_INTERVAL_MS = 5000;  // polling quando status === loading
const CHARTS = {};               // instâncias Chart.js registradas

/* ============================================================
   UTILITÁRIOS
   ============================================================ */

/**
 * Formata números inteiros com separador de milhar (pt-BR).
 * Adiciona sinal + para positivos quando signed=true.
 */
function fmtNum(val, signed = false) {
  if (val === null || val === undefined) return '—';
  const abs  = Math.abs(val);
  const str  = abs.toLocaleString('pt-BR');
  if (signed) return val >= 0 ? `+${str}` : `−${str}`;
  return str;
}

/** Formata percentual */
function fmtPct(val) {
  if (val === null || val === undefined) return '—';
  const sign = val >= 0 ? '+' : '−';
  return `${sign}${Math.abs(val).toFixed(2)}%`;
}

/** Cor semântica para saldos */
function saldoClass(val) {
  return val > 0 ? 'positive' : val < 0 ? 'negative' : '';
}

/** Define texto e classe de um elemento */
function setEl(id, text, extraClass = '') {
  const el = document.getElementById(id);
  if (!el) return;
  el.textContent = text;
  if (extraClass) el.className = (el.className || '') + ' ' + extraClass;
}

/** Mostra/oculta elementos */
function show(id) { const el = document.getElementById(id); if (el) el.classList.remove('hidden'); }
function hide(id) { const el = document.getElementById(id); if (el) el.classList.add('hidden'); }

/** Destrói e recria instância de Chart.js */
function getOrCreateChart(canvasId, config) {
  if (CHARTS[canvasId]) { CHARTS[canvasId].destroy(); }
  const canvas = document.getElementById(canvasId);
  if (!canvas) return;
  CHARTS[canvasId] = new Chart(canvas, config);
}

/* ============================================================
   PALETA PADRÃO
   ============================================================ */
const PALETTE = {
  primary:  '#1A4480',
  accent:   '#0071BC',
  success:  '#198754',
  danger:   '#C0392B',
  warning:  '#D4810A',
  neutral:  '#94A3B8',
  gray:     '#DDE4EF',
  light:    '#EEF2F7',
};
const SECTOR_COLORS = ['#1A4480','#0071BC','#2C7A47','#D4810A','#8B5CF6'];

/* ============================================================
   ESTADO DA APLICAÇÃO
   ============================================================ */
let _polling = null;   // setInterval handle
let _lastRef = null;   // última referência carregada

/* ============================================================
   FETCH PRINCIPAL
   ============================================================ */
async function fetchDashboard() {
  showLoadingState();
  try {
    const res = await fetch(API_URL, { cache: 'no-store' });

    if (!res.ok) {
      throw new Error(`Servidor retornou HTTP ${res.status}: ${res.statusText}`);
    }

    const json = await res.json();

    if (json.status === 'loading') {
      // API ainda está processando — polling
      showLoadingState(json.message || 'Processando dados do CAGED…');
      startPolling();
      return;
    }

    if (json.status === 'error') {
      throw new Error(json.message || 'Erro interno no servidor.');
    }

    // Dados prontos
    stopPolling();
    renderDashboard(json);

  } catch (err) {
    stopPolling();
    showErrorState(err.message);
  }
}

/* ============================================================
   POLLING (quando API está carregando)
   ============================================================ */
function startPolling() {
  if (_polling) return;
  _polling = setInterval(fetchDashboard, POLL_INTERVAL_MS);
}

function stopPolling() {
  if (_polling) { clearInterval(_polling); _polling = null; }
}

/* ============================================================
   ESTADOS DE UI
   ============================================================ */
function showLoadingState(msg = 'Carregando dados do CAGED…') {
  hide('dash-content');
  hide('error-state');
  show('loading-state');
  setEl('loading-msg', msg);
}

function showErrorState(msg) {
  hide('dash-content');
  hide('loading-state');
  show('error-state');
  setEl('error-msg', msg);
}

function showContent() {
  hide('loading-state');
  hide('error-state');
  show('dash-content');
}

/* ============================================================
   RENDERIZAÇÃO PRINCIPAL
   ============================================================ */
function renderDashboard(data) {
  try {
    renderBoletim(data);
    renderKPIs(data);
    renderMotorEmprego(data);
    renderChartSaldoMensal(data);
    renderChartSetores(data);
    renderChartComparativo(data);
    renderChartPorte(data);
    renderTabelaMunicipios(data);
    renderTabelaParticipacao(data);
    renderContextoRegional(data);
    atualizarReferencia(data.referencia);
    showContent();

    // Animações de entrada
    document.querySelectorAll('.kpi-card, .chart-card, .motor-card')
      .forEach((el, i) => {
        el.style.opacity = '0';
        setTimeout(() => {
          el.style.transition = 'opacity 0.4s ease, transform 0.4s ease';
          el.style.opacity = '1';
        }, 60 * i);
      });

    _lastRef = data.referencia;
  } catch (err) {
    console.error('[Dashboard] Erro na renderização:', err);
    showErrorState('Erro ao renderizar os dados: ' + err.message);
  }
}

function atualizarReferencia(ref) {
  document.querySelectorAll('.js-referencia').forEach(el => el.textContent = ref || '—');
  const badge = document.getElementById('header-badge-ref');
  if (badge && ref) badge.textContent = 'Ref.: ' + ref;
}

/* ============================================================
   BOLETIM AUTOMÁTICO
   ============================================================ */
function renderBoletim(data) {
  setEl('boletim-text', data.boletim || '—');
  setEl('boletim-ref', `Referência: ${data.referencia || '—'} · Fonte: MTE/CAGED`);
}

/* ============================================================
   KPIs
   ============================================================ */
function renderKPIs(data) {
  const c = data.comparativo_detalhado || {};
  const natal = c.natal || {};
  const rn    = c.rn    || {};

  // --- Natal ---
  setElKPI('kpi-natal-saldo',         fmtNum(natal.saldo, true),        saldoClass(natal.saldo));
  setElKPI('kpi-natal-admissoes',     fmtNum(natal.admissoes));
  setElKPI('kpi-natal-desligamentos', fmtNum(natal.desligamentos));
  setElKPI('kpi-natal-estoque',       fmtNum(natal.estoque));
  setElKPI('kpi-natal-acum-ano',      fmtNum(natal.acumulado_ano, true), saldoClass(natal.acumulado_ano));
  setElKPI('kpi-natal-acum-12m',      fmtNum(natal.acumulado_12m, true),saldoClass(natal.acumulado_12m));

  // --- RN ---
  setElKPI('kpi-rn-saldo',         fmtNum(rn.saldo, true),        saldoClass(rn.saldo));
  setElKPI('kpi-rn-admissoes',     fmtNum(rn.admissoes));
  setElKPI('kpi-rn-desligamentos', fmtNum(rn.desligamentos));
  setElKPI('kpi-rn-estoque',       fmtNum(rn.estoque));
  setElKPI('kpi-rn-acum-ano',      fmtNum(rn.acumulado_ano, true), saldoClass(rn.acumulado_ano));
  setElKPI('kpi-rn-acum-12m',      fmtNum(rn.acumulado_12m, true),saldoClass(rn.acumulado_12m));
}

function setElKPI(id, text, cls = '') {
  const el = document.getElementById(id);
  if (!el) return;
  el.textContent = text;
  el.className = 'kpi-value' + (cls ? ' ' + cls : '');
}

/* ============================================================
   NATAL COMO MOTOR
   ============================================================ */
function renderMotorEmprego(data) {
  const m = data.natal_motor_rn || {};
  setEl('motor-vagas',        fmtNum(m.vagas_criadas_12m, true));
  setEl('motor-crescimento',  fmtPct(m.crescimento_12m_pct));
  setEl('motor-participacao', (m.participacao_no_estado_12m_pct?.toFixed(1) || '—') + '%');
}

/* ============================================================
   GRÁFICO: Evolução do Saldo Mensal (Natal vs RN)
   ============================================================ */
function renderChartSaldoMensal(data) {
  // Construir série a partir do comparativo setorial + histórico, se disponível
  // Se não há histórico de série temporal, usamos saldo_setor
  const setores = data.saldo_setor || [];
  const setoresNatal = data.saldo_setor_natal || [];

  const labels = setores.map(s => s.nome);
  const rnVals = setores.map(s => s.saldo);
  const natalVals = setoresNatal.map(s => {
    const found = setoresNatal.find(x => x.nome === s.nome);
    return found ? found.saldo : 0;
  });

  getOrCreateChart('chart-saldo-mensal', {
    type: 'bar',
    data: {
      labels,
      datasets: [
        {
          label: 'RN',
          data: rnVals,
          backgroundColor: PALETTE.primary + 'CC',
          borderColor: PALETTE.primary,
          borderWidth: 1,
          borderRadius: 4,
        },
        {
          label: 'Natal',
          data: natalVals,
          backgroundColor: PALETTE.accent + 'CC',
          borderColor: PALETTE.accent,
          borderWidth: 1,
          borderRadius: 4,
        }
      ]
    },
    options: defaultBarOptions('Saldo de Empregos por Setor')
  });
}

/* ============================================================
   GRÁFICO: Saldo por Setor Natal (donut)
   ============================================================ */
function renderChartSetores(data) {
  const setores = data.saldo_setor_natal || [];
  const labels  = setores.map(s => s.nome);
  const valores  = setores.map(s => s.saldo);

  getOrCreateChart('chart-setores-natal', {
    type: 'doughnut',
    data: {
      labels,
      datasets: [{
        data: valores.map(Math.abs),
        backgroundColor: SECTOR_COLORS,
        borderWidth: 2,
        borderColor: '#fff',
        hoverOffset: 8,
      }]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      cutout: '62%',
      plugins: {
        legend: { position: 'right', labels: { font: { size: 12 }, padding: 12 } },
        tooltip: {
          callbacks: {
            label: ctx => {
              const orig = valores[ctx.dataIndex];
              return ` ${ctx.label}: ${fmtNum(orig, true)}`;
            }
          }
        }
      }
    }
  });
}

/* ============================================================
   GRÁFICO: Comparativo Setorial RN vs Natal (horizontal)
   ============================================================ */
function renderChartComparativo(data) {
  const comp = data.comparativo_setorial_rn_natal || [];
  const labels = comp.map(s => s.setor);
  const rnVals = comp.map(s => s.rn.saldo);
  const natalVals = comp.map(s => s.natal.saldo);

  getOrCreateChart('chart-comparativo', {
    type: 'bar',
    data: {
      labels,
      datasets: [
        {
          label: 'RN',
          data: rnVals,
          backgroundColor: PALETTE.primary + 'BB',
          borderColor: PALETTE.primary,
          borderWidth: 1,
          borderRadius: 4,
        },
        {
          label: 'Natal',
          data: natalVals,
          backgroundColor: PALETTE.success + 'BB',
          borderColor: PALETTE.success,
          borderWidth: 1,
          borderRadius: 4,
        }
      ]
    },
    options: {
      ...defaultBarOptions('Saldo por Setor (Comparativo)'),
      indexAxis: 'y',
    }
  });
}

/* ============================================================
   GRÁFICO: Saldo por Porte da Empresa
   ============================================================ */
function renderChartPorte(data) {
  const portes = data.saldo_porte || [];
  const labels = portes.map(p => p.porte);
  const valores = portes.map(p => p.saldo);
  const colors  = valores.map(v => v >= 0 ? PALETTE.success : PALETTE.danger);

  getOrCreateChart('chart-porte', {
    type: 'bar',
    data: {
      labels,
      datasets: [{
        label: 'Saldo',
        data: valores,
        backgroundColor: colors.map(c => c + 'BB'),
        borderColor: colors,
        borderWidth: 1,
        borderRadius: 4,
      }]
    },
    options: {
      ...defaultBarOptions('Saldo por Porte da Empresa'),
      indexAxis: 'y',
    }
  });
}

/* ============================================================
   TABELA: Top Municípios RN
   ============================================================ */
function renderTabelaMunicipios(data) {
  const muns = (data.municipios_rn || []).slice(0, 15);
  if (!muns.length) return;

  const maxSaldo = Math.max(...muns.map(m => Math.abs(m.saldo)));
  const tbody = document.getElementById('tbody-municipios');
  if (!tbody) return;

  tbody.innerHTML = muns.map((m, i) => {
    const cls = m.saldo > 0 ? 'td-positive' : m.saldo < 0 ? 'td-negative' : '';
    const pct = maxSaldo > 0 ? (Math.abs(m.saldo) / maxSaldo * 100).toFixed(1) : 0;
    return `
      <tr>
        <td><span style="color:var(--color-neutral-400);font-weight:700;margin-right:8px">${i + 1}</span>${m.nome}</td>
        <td class="num td-positive">${fmtNum(m.admissoes)}</td>
        <td class="num td-negative">${fmtNum(m.desligamentos)}</td>
        <td class="num ${cls}" style="font-weight:700">${fmtNum(m.saldo, true)}</td>
        <td class="bar-cell">
          <div class="bar-wrap">
            <div class="bar-fill" style="width:${pct}%;background:${m.saldo >= 0 ? 'var(--color-success)' : 'var(--color-danger)'}"></div>
          </div>
        </td>
      </tr>`;
  }).join('');
}

/* ============================================================
   TABELA: Participação Natal nas Admissões
   ============================================================ */
function renderTabelaParticipacao(data) {
  const partic = data.participacao_natal_admissoes || [];
  const tbody = document.getElementById('tbody-participacao');
  if (!tbody) return;

  tbody.innerHTML = partic.map(p => {
    const pct = p.participacao_pct.toFixed(1);
    return `
      <tr>
        <td><strong>${p.setor}</strong></td>
        <td class="num td-positive">${fmtNum(p.admissoes_natal)}</td>
        <td class="num">${fmtNum(p.admissoes_rn)}</td>
        <td class="num"><strong>${pct}%</strong></td>
        <td class="bar-cell">
          <div class="bar-wrap">
            <div class="bar-fill" style="width:${pct}%"></div>
          </div>
        </td>
      </tr>`;
  }).join('');
}

/* ============================================================
   CONTEXTO REGIONAL (Nordeste)
   ============================================================ */
function renderContextoRegional(data) {
  const reg = data.contexto_regional || {};

  // KPIs — saldo, admissões e desligamentos regionais
  setEl('regional-saldo',         fmtNum(reg.saldo, true),  saldoClass(reg.saldo));
  setEl('regional-admissoes',     fmtNum(reg.admissoes));
  setEl('regional-desligamentos', fmtNum(reg.desligamentos));

  // Gráfico de barras horizontais — Saldo por Estado do Nordeste
  const estados = (reg.estados || []).sort((a, b) => b.saldo - a.saldo);
  if (estados.length) {
    const labels = estados.map(e => e.nome);
    const valores = estados.map(e => e.saldo);
    const bgColors = valores.map(v => v >= 0 ? PALETTE.success + 'BB' : PALETTE.danger + 'BB');
    const bdColors = valores.map(v => v >= 0 ? PALETTE.success : PALETTE.danger);

    getOrCreateChart('chart-nordeste', {
      type: 'bar',
      data: {
        labels,
        datasets: [{
          label: 'Saldo de Empregos',
          data: valores,
          backgroundColor: bgColors,
          borderColor: bdColors,
          borderWidth: 1,
          borderRadius: 4,
        }]
      },
      options: {
        ...defaultBarOptions('Saldo por Estado — Nordeste'),
        indexAxis: 'y',
        plugins: {
          ...defaultBarOptions().plugins,
          legend: { display: false },
          tooltip: {
            callbacks: {
              label: ctx => ` ${fmtNum(ctx.raw, true)} vagas`
            }
          }
        }
      }
    });
  }

  // Gráfico de barras — Saldo por Capital do Nordeste
  const capitais = (reg.capitais || []).sort((a, b) => b.saldo - a.saldo);
  if (capitais.length && document.getElementById('chart-capitais-nordeste')) {
    const labCap = capitais.map(c => c.nome);
    const valCap = capitais.map(c => c.saldo);
    const bgCap  = valCap.map(v => v >= 0 ? PALETTE.accent + 'BB' : PALETTE.danger + 'BB');
    const bdCap  = valCap.map(v => v >= 0 ? PALETTE.accent : PALETTE.danger);

    getOrCreateChart('chart-capitais-nordeste', {
      type: 'bar',
      data: {
        labels: labCap,
        datasets: [{
          label: 'Saldo de Empregos',
          data: valCap,
          backgroundColor: bgCap,
          borderColor: bdCap,
          borderWidth: 1,
          borderRadius: 4,
        }]
      },
      options: {
        ...defaultBarOptions('Saldo por Capital — Nordeste'),
        indexAxis: 'y',
        plugins: {
          ...defaultBarOptions().plugins,
          legend: { display: false },
          tooltip: {
            callbacks: {
              label: ctx => ` ${fmtNum(ctx.raw, true)} vagas`
            }
          }
        }
      }
    });
  }
}

/* ============================================================
   OPÇÕES PADRÃO Chart.js
   ============================================================ */
function defaultBarOptions(title = '') {
  return {
    responsive: true,
    maintainAspectRatio: false,
    plugins: {
      legend: { display: true, position: 'top', labels: { font: { size: 12 }, padding: 14 } },
      tooltip: {
        callbacks: {
          label: ctx => ` ${ctx.dataset.label}: ${fmtNum(ctx.raw, true)}`
        }
      }
    },
    scales: {
      x: {
        grid: { color: '#EEF2F7' },
        ticks: { font: { size: 11 }, color: '#475569' }
      },
      y: {
        grid: { color: '#EEF2F7' },
        ticks: {
          font: { size: 11 }, color: '#475569',
          callback: v => fmtNum(v, true)
        }
      }
    }
  };
}

/* ============================================================
   TABS (Natal / RN)
   ============================================================ */
function initTabs() {
  document.querySelectorAll('.tab-btn').forEach(btn => {
    btn.addEventListener('click', () => {
      const group = btn.closest('.tab-group');
      if (!group) return;
      group.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
      const target = btn.dataset.target;
      group.querySelectorAll('.tab-pane').forEach(p => p.classList.add('hidden'));
      const pane = document.getElementById(target);
      if (pane) pane.classList.remove('hidden');
    });
  });
}

/* ============================================================
   BOTÃO REFRESH MANUAL
   ============================================================ */
function initRefreshBtn() {
  const btn = document.getElementById('btn-refresh');
  if (!btn) return;
  btn.addEventListener('click', async () => {
    btn.disabled = true;
    btn.innerHTML = `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" class="spin-icon"><path d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15"/></svg> Atualizando…`;
    await fetchDashboard();
    btn.disabled = false;
    btn.innerHTML = `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15"/></svg> Atualizar`;
  });
}

/* ============================================================
   INICIALIZAÇÃO
   ============================================================ */
document.addEventListener('DOMContentLoaded', () => {
  initTabs();
  initRefreshBtn();
  fetchDashboard();
});

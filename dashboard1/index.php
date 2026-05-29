<?php
/**
 * index.php — Observatório do Emprego
 * Prefeitura do Natal / SEMPLA
 * Frontend em PHP puro servindo o dashboard SPA.
 */

// Pode-se fazer pré-renderização aqui no futuro (SSR leve)
$titulo     = 'Observatório do Emprego — Natal / RN | OBSERVA NATAL';
$descricao  = 'Painel interativo com dados do CAGED sobre emprego formal em Natal e no Rio Grande do Norte. Secretaria Municipal de Planejamento — SEMPLA.';
$ano_atual  = date('Y');
?>
<!DOCTYPE html>
<html lang="pt-BR">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title><?= htmlspecialchars($titulo) ?></title>
  <meta name="description" content="<?= htmlspecialchars($descricao) ?>" />

  <!-- SEO / Open Graph -->
  <meta property="og:type"        content="website" />
  <meta property="og:title"       content="Observatório do Emprego — Natal/RN" />
  <meta property="og:description" content="<?= htmlspecialchars($descricao) ?>" />
  <meta property="og:locale"      content="pt_BR" />
  <meta name="robots"             content="index, follow" />

  <!-- Fonts -->
  <link rel="preconnect" href="https://fonts.googleapis.com" />
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin />
  <link href="https://fonts.googleapis.com/css2?family=Source+Sans+3:ital,wght@0,300;0,400;0,500;0,600;0,700;1,400&family=DM+Serif+Display:ital@0;1&display=swap" rel="stylesheet" />

  <!-- Chart.js (CDN) -->
  <script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.3/dist/chart.umd.min.js"></script>

  <!-- Estilos -->
  <link rel="stylesheet" href="assets/css/style.css" />
</head>
<body>

<!-- ============================================================
     BARRA INSTITUCIONAL
     ============================================================ -->
<div class="gov-bar" role="navigation" aria-label="Links institucionais">
  <span>Portal oficial da Prefeitura de Natal</span>
  <span class="gov-bar-sep">|</span>
  <a href="https://natal.rn.gov.br" target="_blank" rel="noopener">Portal da Prefeitura</a>
  <a href="https://natal.rn.gov.br/transparencia/" target="_blank" rel="noopener">Transparência</a>
  <a href="https://leideacesso.natal.rn.gov.br" target="_blank" rel="noopener">Lei de Acesso</a>
  <a href="https://natal.rn.gov.br/ouvidoria" target="_blank" rel="noopener">Ouvidoria</a>
</div>

<!-- ============================================================
     HEADER
     ============================================================ -->
<header class="site-header" role="banner">
  <div class="header-inner">
    <!-- Brand -->
    <a href="/" class="header-brand" aria-label="Observatório do Emprego — página inicial">
      <div class="brand-logo-wrap" aria-hidden="true">📊</div>
      <div>
        <div class="brand-text-main">Observatório do Emprego</div>
        <div class="brand-text-sub">Prefeitura de Natal &bull; SEMPLA</div>
      </div>
    </a>

    <!-- Meta ações -->
    <div class="header-meta">
      <span class="header-badge" id="header-badge-ref">Carregando…</span>
      <a href="https://observa.natal.rn.gov.br" target="_blank" rel="noopener" class="header-badge" style="text-decoration:none">
        OBSERVA NATAL ↗
      </a>
      <button class="btn-refresh" id="btn-refresh" aria-label="Atualizar dados">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true">
          <path d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15"/>
        </svg>
        Atualizar
      </button>
    </div>
  </div>
</header>

<!-- ============================================================
     NAV / ÂNCORAS
     ============================================================ -->
<nav class="nav-bar" aria-label="Seções do painel">
  <div class="nav-inner">
    <a href="#secao-kpis"      class="nav-link active">Indicadores</a>
    <a href="#secao-natal"     class="nav-link">Motor do Emprego</a>
    <a href="#secao-graficos"  class="nav-link">Gráficos</a>
    <a href="#secao-municipios"class="nav-link">Municípios</a>
    <a href="#secao-nordeste"  class="nav-link">Nordeste</a>
  </div>
</nav>

<!-- ============================================================
     CONTEÚDO PRINCIPAL
     ============================================================ -->
<main class="main-content" id="main-content" role="main">

  <!-- ── LOADING ─────────────────────────────────────────── -->
  <div id="loading-state" class="loading-overlay" role="status" aria-live="polite">
    <div class="spinner" aria-hidden="true"></div>
    <p class="loading-text" id="loading-msg">Carregando dados do CAGED…</p>
    <p class="text-muted text-sm">Os dados são obtidos diretamente do Ministério do Trabalho.</p>
  </div>

  <!-- ── ERRO ─────────────────────────────────────────────── -->
  <div id="error-state" class="error-box hidden" role="alert">
    <span class="error-icon">⚠️</span>
    <div>
      <div class="error-title">Não foi possível carregar os dados</div>
      <div class="error-msg" id="error-msg">Erro desconhecido.</div>
      <p class="text-sm" style="margin-top:8px;color:#991B1B">
        Verifique se a API está rodando em <code>http://127.0.0.1:8000</code> e tente novamente.
      </p>
    </div>
  </div>

  <!-- ── DASHBOARD ─────────────────────────────────────────── -->
  <div id="dash-content" class="hidden">

    <!-- BOLETIM AUTOMATIZADO -->
    <div class="boletim-card" role="article" aria-labelledby="boletim-heading">
      <div class="boletim-label" id="boletim-heading">
        Boletim Automático do Emprego
      </div>
      <p class="boletim-text" id="boletim-text">—</p>
      <p class="boletim-ref" id="boletim-ref">—</p>
    </div>

    <!-- ── SEÇÃO: KPIs ──────────────────────────────────────── -->
    <section id="secao-kpis" aria-labelledby="kpis-title">
      <div class="section-header">
        <h2 id="kpis-title">Indicadores do Mês de Referência</h2>
        <p>Resultados de admissões, desligamentos e saldo de emprego formal — <span class="js-referencia">—</span></p>
      </div>

      <!-- Tabs Natal / RN -->
      <div class="tab-group" role="tablist">
        <div class="tab-strip">
          <button class="tab-btn active" data-target="tab-natal" role="tab" aria-selected="true" id="tab-btn-natal">🏙️ Natal</button>
          <button class="tab-btn"        data-target="tab-rn"    role="tab" aria-selected="false" id="tab-btn-rn">🗺️ Rio Grande do Norte</button>
        </div>

        <!-- Pane Natal -->
        <div id="tab-natal" class="tab-pane" role="tabpanel" aria-labelledby="tab-btn-natal">
          <div class="kpi-grid">
            <div class="kpi-card kpi-positive fade-up">
              <div class="kpi-icon" aria-hidden="true">📈</div>
              <div class="kpi-scope">Natal</div>
              <div class="kpi-label">Saldo do Mês</div>
              <div class="kpi-value" id="kpi-natal-saldo">—</div>
              <div class="kpi-sub">Admissões menos Desligamentos</div>
            </div>
            <div class="kpi-card kpi-accent fade-up fade-up-delay-1">
              <div class="kpi-icon" aria-hidden="true">✅</div>
              <div class="kpi-scope">Natal</div>
              <div class="kpi-label">Admissões</div>
              <div class="kpi-value" id="kpi-natal-admissoes">—</div>
              <div class="kpi-sub">Vínculos ativos no mês</div>
            </div>
            <div class="kpi-card kpi-negative fade-up fade-up-delay-2">
              <div class="kpi-icon" aria-hidden="true">📉</div>
              <div class="kpi-scope">Natal</div>
              <div class="kpi-label">Desligamentos</div>
              <div class="kpi-value" id="kpi-natal-desligamentos">—</div>
              <div class="kpi-sub">Vínculos encerrados no mês</div>
            </div>
            <div class="kpi-card kpi-neutral fade-up fade-up-delay-3">
              <div class="kpi-icon" aria-hidden="true">🏦</div>
              <div class="kpi-scope">Natal</div>
              <div class="kpi-label">Estoque de Empregos</div>
              <div class="kpi-value" id="kpi-natal-estoque">—</div>
              <div class="kpi-sub">Total de empregos formais</div>
            </div>
            <div class="kpi-card kpi-positive fade-up fade-up-delay-4">
              <div class="kpi-icon" aria-hidden="true">📆</div>
              <div class="kpi-scope">Natal</div>
              <div class="kpi-label">Acumulado do Ano</div>
              <div class="kpi-value" id="kpi-natal-acum-ano">—</div>
              <div class="kpi-sub">Saldo acumulado em <?= $ano_atual ?></div>
            </div>
            <div class="kpi-card kpi-positive fade-up fade-up-delay-5">
              <div class="kpi-icon" aria-hidden="true">🕐</div>
              <div class="kpi-scope">Natal</div>
              <div class="kpi-label">Acumulado 12 Meses</div>
              <div class="kpi-value" id="kpi-natal-acum-12m">—</div>
              <div class="kpi-sub">Saldo últimos 12 meses</div>
            </div>
          </div>
        </div><!-- /tab-natal -->

        <!-- Pane RN -->
        <div id="tab-rn" class="tab-pane hidden" role="tabpanel" aria-labelledby="tab-btn-rn">
          <div class="kpi-grid">
            <div class="kpi-card kpi-positive fade-up">
              <div class="kpi-icon" aria-hidden="true">📈</div>
              <div class="kpi-scope">Rio Grande do Norte</div>
              <div class="kpi-label">Saldo do Mês</div>
              <div class="kpi-value" id="kpi-rn-saldo">—</div>
              <div class="kpi-sub">Admissões menos Desligamentos</div>
            </div>
            <div class="kpi-card kpi-accent fade-up fade-up-delay-1">
              <div class="kpi-icon" aria-hidden="true">✅</div>
              <div class="kpi-scope">Rio Grande do Norte</div>
              <div class="kpi-label">Admissões</div>
              <div class="kpi-value" id="kpi-rn-admissoes">—</div>
              <div class="kpi-sub">Vínculos ativos no mês</div>
            </div>
            <div class="kpi-card kpi-negative fade-up fade-up-delay-2">
              <div class="kpi-icon" aria-hidden="true">📉</div>
              <div class="kpi-scope">Rio Grande do Norte</div>
              <div class="kpi-label">Desligamentos</div>
              <div class="kpi-value" id="kpi-rn-desligamentos">—</div>
              <div class="kpi-sub">Vínculos encerrados no mês</div>
            </div>
            <div class="kpi-card kpi-neutral fade-up fade-up-delay-3">
              <div class="kpi-icon" aria-hidden="true">🏦</div>
              <div class="kpi-scope">Rio Grande do Norte</div>
              <div class="kpi-label">Estoque de Empregos</div>
              <div class="kpi-value" id="kpi-rn-estoque">—</div>
              <div class="kpi-sub">Total de empregos formais</div>
            </div>
            <div class="kpi-card kpi-positive fade-up fade-up-delay-4">
              <div class="kpi-icon" aria-hidden="true">📆</div>
              <div class="kpi-scope">Rio Grande do Norte</div>
              <div class="kpi-label">Acumulado do Ano</div>
              <div class="kpi-value" id="kpi-rn-acum-ano">—</div>
              <div class="kpi-sub">Saldo acumulado em <?= $ano_atual ?></div>
            </div>
            <div class="kpi-card kpi-positive fade-up fade-up-delay-5">
              <div class="kpi-icon" aria-hidden="true">🕐</div>
              <div class="kpi-scope">Rio Grande do Norte</div>
              <div class="kpi-label">Acumulado 12 Meses</div>
              <div class="kpi-value" id="kpi-rn-acum-12m">—</div>
              <div class="kpi-sub">Saldo últimos 12 meses</div>
            </div>
          </div>
        </div><!-- /tab-rn -->
      </div><!-- /tab-group -->
    </section>

    <!-- ── SEÇÃO: MOTOR DO EMPREGO ──────────────────────────── -->
    <section id="secao-natal" class="mt-xl" aria-labelledby="motor-title">
      <div class="section-header">
        <h2 id="motor-title">Natal como Motor do Emprego</h2>
        <p>Contribuição da capital para o mercado de trabalho formal do Rio Grande do Norte nos últimos 12 meses.</p>
      </div>
      <div class="motor-grid">
        <div class="motor-card fade-up">
          <div class="motor-card-icon" aria-hidden="true">🚀</div>
          <div class="motor-card-value" id="motor-vagas">—</div>
          <div class="motor-card-label">Vagas Criadas (12 meses)</div>
          <div class="motor-card-desc">Saldo acumulado em Natal</div>
        </div>
        <div class="motor-card fade-up fade-up-delay-1">
          <div class="motor-card-icon" aria-hidden="true">📊</div>
          <div class="motor-card-value" id="motor-crescimento">—</div>
          <div class="motor-card-label">Crescimento (12 meses)</div>
          <div class="motor-card-desc">Variação relativa no estoque</div>
        </div>
        <div class="motor-card fade-up fade-up-delay-2">
          <div class="motor-card-icon" aria-hidden="true">🏆</div>
          <div class="motor-card-value" id="motor-participacao">—</div>
          <div class="motor-card-label">Participação no Estado</div>
          <div class="motor-card-desc">% das vagas do RN geradas em Natal</div>
        </div>
      </div>
    </section>

    <!-- ── SEÇÃO: GRÁFICOS ──────────────────────────────────── -->
    <section id="secao-graficos" class="mt-xl" aria-labelledby="graficos-title">
      <div class="section-header">
        <h2 id="graficos-title">Análise Setorial</h2>
        <p>Distribuição de saldo por setor econômico e porte de empresa — <span class="js-referencia">—</span></p>
      </div>

      <!-- Linha 1: 2 gráficos -->
      <div class="charts-grid charts-grid-2">
        <div class="chart-card fade-up">
          <div class="chart-card-header">
            <div>
              <div class="chart-card-title">Saldo por Setor — RN vs Natal</div>
              <div class="chart-card-sub">Comparativo das principais atividades econômicas</div>
            </div>
            <span class="chart-badge chart-badge-blue">Mês de Ref.</span>
          </div>
          <div class="chart-canvas-wrap">
            <canvas id="chart-saldo-mensal" aria-label="Gráfico de saldo por setor RN vs Natal" role="img"></canvas>
          </div>
        </div>

        <div class="chart-card fade-up fade-up-delay-1">
          <div class="chart-card-header">
            <div>
              <div class="chart-card-title">Distribuição Setorial — Natal</div>
              <div class="chart-card-sub">Participação de cada setor no saldo de Natal</div>
            </div>
            <span class="chart-badge chart-badge-green">Natal</span>
          </div>
          <div class="chart-canvas-wrap">
            <canvas id="chart-setores-natal" aria-label="Gráfico de pizza setores Natal" role="img"></canvas>
          </div>
        </div>
      </div>

      <!-- Linha 2: 2 gráficos -->
      <div class="charts-grid charts-grid-2">
        <div class="chart-card fade-up">
          <div class="chart-card-header">
            <div>
              <div class="chart-card-title">Saldo Setorial Comparativo</div>
              <div class="chart-card-sub">RN vs Natal por setor (horizontal)</div>
            </div>
            <span class="chart-badge chart-badge-blue">Comparativo</span>
          </div>
          <div class="chart-canvas-wrap" style="min-height:280px">
            <canvas id="chart-comparativo" aria-label="Gráfico comparativo setorial RN Natal" role="img"></canvas>
          </div>
        </div>

        <div class="chart-card fade-up fade-up-delay-1">
          <div class="chart-card-header">
            <div>
              <div class="chart-card-title">Saldo por Porte de Empresa — RN</div>
              <div class="chart-card-sub">Micro, pequenas, médias e grandes empresas</div>
            </div>
            <span class="chart-badge chart-badge-blue">RN</span>
          </div>
          <div class="chart-canvas-wrap" style="min-height:280px">
            <canvas id="chart-porte" aria-label="Gráfico saldo por porte de empresa RN" role="img"></canvas>
          </div>
        </div>
      </div>
    </section>

    <!-- ── SEÇÃO: TABELA MUNICÍPIOS ─────────────────────────── -->
    <section id="secao-municipios" class="mt-xl" aria-labelledby="muns-title">
      <div class="section-header">
        <h2 id="muns-title">Top 15 Municípios do RN</h2>
        <p>Municípios com maior movimentação no mercado de trabalho formal — <span class="js-referencia">—</span></p>
      </div>

      <div class="table-card fade-up">
        <div class="table-card-header">
          <div>
            <div class="table-card-title">Admissões, Desligamentos e Saldo por Município</div>
            <div class="table-card-sub">Ordenado por volume de admissões · Fonte: MTE/CAGED</div>
          </div>
        </div>
        <div style="overflow-x:auto">
          <table class="data-table" aria-label="Top 15 municípios RN por saldo de empregos">
            <thead>
              <tr>
                <th scope="col">Município</th>
                <th scope="col" style="text-align:right">Admissões</th>
                <th scope="col" style="text-align:right">Desligamentos</th>
                <th scope="col" style="text-align:right">Saldo</th>
                <th scope="col">Proporção</th>
              </tr>
            </thead>
            <tbody id="tbody-municipios">
              <tr>
                <td colspan="5" style="text-align:center;color:var(--color-neutral-400);padding:24px">
                  <div class="skeleton" style="height:16px;width:80%;margin:0 auto"></div>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>

      <!-- Tabela Participação -->
      <div class="table-card fade-up" style="margin-top: var(--space-lg)">
        <div class="table-card-header">
          <div>
            <div class="table-card-title">Participação de Natal nas Admissões por Setor</div>
            <div class="table-card-sub">% das admissões do estado concentradas na capital · Fonte: MTE/CAGED</div>
          </div>
        </div>
        <div style="overflow-x:auto">
          <table class="data-table" aria-label="Participação de Natal nas admissões por setor">
            <thead>
              <tr>
                <th scope="col">Setor</th>
                <th scope="col" style="text-align:right">Admissões Natal</th>
                <th scope="col" style="text-align:right">Admissões RN</th>
                <th scope="col" style="text-align:right">Participação</th>
                <th scope="col">Proporção</th>
              </tr>
            </thead>
            <tbody id="tbody-participacao">
              <tr>
                <td colspan="5" style="text-align:center;color:var(--color-neutral-400);padding:24px">
                  <div class="skeleton" style="height:16px;width:80%;margin:0 auto"></div>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
    </section>

    <!-- ── SEÇÃO: CONTEXTO NORDESTE ─────────────────────────── -->
    <section id="secao-nordeste" class="mt-xl" aria-labelledby="nordeste-title">
      <div class="section-header">
        <h2 id="nordeste-title">Contexto Regional — Nordeste</h2>
        <p>Posicionamento do RN no mercado de trabalho do Nordeste brasileiro.</p>
      </div>

      <div class="kpi-grid" style="max-width:700px">
        <div class="kpi-card kpi-positive fade-up">
          <div class="kpi-icon" aria-hidden="true">🌎</div>
          <div class="kpi-scope">Nordeste</div>
          <div class="kpi-label">Saldo Regional</div>
          <div class="kpi-value positive" id="regional-saldo">—</div>
        </div>
        <div class="kpi-card kpi-accent fade-up fade-up-delay-1">
          <div class="kpi-icon" aria-hidden="true">📋</div>
          <div class="kpi-scope">Nordeste</div>
          <div class="kpi-label">Admissões</div>
          <div class="kpi-value" id="regional-admissoes">—</div>
        </div>
        <div class="kpi-card kpi-negative fade-up fade-up-delay-2">
          <div class="kpi-icon" aria-hidden="true">📋</div>
          <div class="kpi-scope">Nordeste</div>
          <div class="kpi-label">Desligamentos</div>
          <div class="kpi-value" id="regional-desligamentos">—</div>
        </div>
      </div>

      <div class="charts-grid charts-grid-2 fade-up" style="margin-top:var(--space-lg)">
        <div class="chart-card">
          <div class="chart-card-header">
            <div>
              <div class="chart-card-title">Saldo por Estado — Nordeste</div>
              <div class="chart-card-sub">Distribuição do saldo entre os estados nordestinos</div>
            </div>
            <span class="chart-badge chart-badge-blue">Estados</span>
          </div>
          <div class="chart-canvas-wrap" style="min-height:300px">
            <canvas id="chart-nordeste" aria-label="Gráfico saldo nordeste por estado" role="img"></canvas>
          </div>
        </div>

        <div class="chart-card">
          <div class="chart-card-header">
            <div>
              <div class="chart-card-title">Saldo por Capital — Nordeste</div>
              <div class="chart-card-sub">Comparativo do saldo de empregos nas capitais nordestinas</div>
            </div>
            <span class="chart-badge chart-badge-green">Capitais</span>
          </div>
          <div class="chart-canvas-wrap" style="min-height:300px">
            <canvas id="chart-capitais-nordeste" aria-label="Gráfico saldo nordeste por capital" role="img"></canvas>
          </div>
        </div>
      </div>
    </section>

  </div><!-- /dash-content -->
</main>

<!-- ============================================================
     FOOTER
     ============================================================ -->
<footer class="site-footer" role="contentinfo">
  <div class="footer-inner">
    <div>
      <div class="footer-brand">OBSERVA NATAL</div>
      <div class="footer-info">
        Secretaria Municipal de Planejamento (SEMPLA)<br>
        Prefeitura do Natal — Rio Grande do Norte<br>
        Dados: MTE/CAGED · Atualização mensal
      </div>
    </div>
    <nav class="footer-links" aria-label="Links do rodapé">
      <a href="https://observa.natal.rn.gov.br" target="_blank" rel="noopener">Portal Observa Natal</a>
      <a href="https://natal.rn.gov.br" target="_blank" rel="noopener">Prefeitura de Natal</a>
      <a href="https://natal.rn.gov.br/transparencia" target="_blank" rel="noopener">Transparência</a>
      <a href="https://natal.rn.gov.br/ouvidoria" target="_blank" rel="noopener">Ouvidoria</a>
      <a href="https://empregodash-slnnbsqr.manus.space" target="_blank" rel="noopener">Dashboard de Emprego ↗</a>
    </nav>
  </div>
  <div class="footer-bottom">
    &copy; <?= $ano_atual ?> Prefeitura Municipal de Natal. Todos os direitos reservados.
    &nbsp;|&nbsp; Fonte dos dados: Cadastro Geral de Empregados e Desempregados (CAGED) — MTE.
  </div>
</footer>

<!-- Script principal -->
<script src="assets/js/dashboard.js"></script>

</body>
</html>

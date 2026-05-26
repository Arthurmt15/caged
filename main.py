"""
main.py
FastAPI backend para o Dashboard do Observatório do Emprego (Natal/RN).
Gerencia o download automático do FTP, processamento dos dados e API REST.
"""

import json
import logging
import threading
import time
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from ftp_downloader import get_latest_month, download_cagedmov, cleanup_old_files
from data_processor import process_caged_data

# Configuração de logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

# Estado global (cache dos dados processados)
_cache: dict = {
    "data": None,
    "anomes": None,
    "status": "idle",   # idle | loading | ready | error
    "error": None,
    "last_check": None,
}
_lock = threading.Lock()

DATA_DIR = Path(__file__).parent / "data"
UPDATE_INTERVAL_HOURS = 24

BASELINE_RN_STOCK = 553451
BASELINE_NATAL_STOCK = 238450
SETORES_ORDER = ["Serviços", "Comércio", "Construção", "Indústria", "Agropecuária"]


# ---------------------------------------------------------------------------
# Helpers para Histórico
# ---------------------------------------------------------------------------

def load_history() -> list[dict]:
    """Carrega o histórico compilado de caged_history.json."""
    history_path = DATA_DIR / "caged_history.json"
    if history_path.exists():
        try:
            with open(history_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Erro ao ler histórico: {e}")
            return []
    return []


def save_to_history(result: dict):
    """Salva de forma persistente o resultado processado de um novo mês no histórico."""
    history = load_history()
    current_anomes = result["anomes"]
    
    # Verifica se já existe
    exists = any(m["anomes"] == current_anomes for m in history)
    if not exists:
        new_entry = {
            "anomes": current_anomes,
            "referencia": result["referencia"],
            "rn_saldo": result["rn"]["kpis"]["saldo"],
            "rn_admissoes": result["rn"]["kpis"]["admissoes"],
            "rn_desligamentos": result["rn"]["kpis"]["desligamentos"],
            "natal_saldo": result["natal"]["kpis"]["saldo"],
            "natal_admissoes": result["natal"]["kpis"]["admissoes"],
            "natal_desligamentos": result["natal"]["kpis"]["desligamentos"]
        }
        history.append(new_entry)
        history = sorted(history, key=lambda x: x["anomes"])
        
        history_path = DATA_DIR / "caged_history.json"
        try:
            with open(history_path, "w", encoding="utf-8") as f:
                json.dump(history, f, ensure_ascii=False, indent=2)
            logger.info(f"Mês {current_anomes} adicionado permanentemente ao caged_history.json.")
        except Exception as e:
            logger.error(f"Erro ao salvar histórico local: {e}")


def build_dashboard_response(result: dict) -> dict:
    """Combina o mês processado ao vivo com o histórico de 12 meses e gera as novas métricas."""
    current_anomes = result["anomes"]
    history = load_history()
    
    # Criar entrada do mês atual se não estiver no histórico carregado
    current_entry = {
        "anomes": current_anomes,
        "referencia": result["referencia"],
        "rn_saldo": result["rn"]["kpis"]["saldo"],
        "rn_admissoes": result["rn"]["kpis"]["admissoes"],
        "rn_desligamentos": result["rn"]["kpis"]["desligamentos"],
        "natal_saldo": result["natal"]["kpis"]["saldo"],
        "natal_admissoes": result["natal"]["kpis"]["admissoes"],
        "natal_desligamentos": result["natal"]["kpis"]["desligamentos"]
    }
    
    full_history = [m for m in history if m["anomes"] != current_anomes]
    full_history.append(current_entry)
    full_history = sorted(full_history, key=lambda x: x["anomes"])
    
    # Calcular estoques correntes
    rn_stock_running = BASELINE_RN_STOCK
    natal_stock_running = BASELINE_NATAL_STOCK
    monthly_stocks = {}
    
    for m in full_history:
        rn_stock_running += m["rn_saldo"]
        natal_stock_running += m["natal_saldo"]
        monthly_stocks[m["anomes"]] = {
            "rn": rn_stock_running,
            "natal": natal_stock_running
        }
        
    current_rn_stock = monthly_stocks[current_anomes]["rn"]
    current_natal_stock = monthly_stocks[current_anomes]["natal"]
    
    # Calcular Acumulado do Ano
    current_year = current_anomes[:4]
    year_entries = [m for m in full_history if m["anomes"].startswith(current_year) and m["anomes"] <= current_anomes]
    rn_acumulado_ano = sum(m["rn_saldo"] for m in year_entries)
    natal_acumulado_ano = sum(m["natal_saldo"] for m in year_entries)
    
    # Calcular Acumulado de 12 meses
    last_12 = [m for m in full_history if m["anomes"] <= current_anomes][-12:]
    rn_acumulado_12m = sum(m["rn_saldo"] for m in last_12)
    natal_acumulado_12m = sum(m["natal_saldo"] for m in last_12)
    
    rn_stock_12m_ago = current_rn_stock - rn_acumulado_12m
    natal_stock_12m_ago = current_natal_stock - natal_acumulado_12m
    
    rn_var_12m = (rn_acumulado_12m / rn_stock_12m_ago * 100) if rn_stock_12m_ago > 0 else 0.0
    natal_var_12m = (natal_acumulado_12m / natal_stock_12m_ago * 100) if natal_stock_12m_ago > 0 else 0.0
    
    # Calcular Participação de Natal e Comparativo Setorial
    participacao_admissoes = []
    comparativo_setorial = []
    
    natal_setores = {s["nome"]: s for s in result["natal"]["por_setor"]}
    rn_setores = {s["nome"]: s for s in result["rn"]["por_setor"]}
    
    for setor_name in SETORES_ORDER:
        natal_sec = natal_setores.get(setor_name, {"saldo": 0, "admissoes": 0, "desligamentos": 0})
        rn_sec = rn_setores.get(setor_name, {"saldo": 0, "admissoes": 0, "desligamentos": 0})
        
        # Participação nas admissões
        if rn_sec["admissoes"] > 0:
            part_pct = (natal_sec["admissoes"] / rn_sec["admissoes"]) * 100
        else:
            part_pct = 0.0
            
        participacao_admissoes.append({
            "setor": setor_name,
            "admissoes_natal": natal_sec["admissoes"],
            "admissoes_rn": rn_sec["admissoes"],
            "participacao_pct": round(part_pct, 2)
        })
        
        # Comparativo Setorial
        comparativo_setorial.append({
            "setor": setor_name,
            "rn": {
                "saldo": rn_sec["saldo"],
                "admissoes": rn_sec["admissoes"],
                "desligamentos": rn_sec["desligamentos"]
            },
            "natal": {
                "saldo": natal_sec["saldo"],
                "admissoes": natal_sec["admissoes"],
                "desligamentos": natal_sec["desligamentos"]
            }
        })
        
    # Natal como Motor do Emprego
    motor_emprego = {
        "vagas_criadas_12m": natal_acumulado_12m,
        "crescimento_12m_pct": round(natal_var_12m, 2),
        "participacao_no_estado_12m_pct": round((natal_acumulado_12m / rn_acumulado_12m * 100), 2) if rn_acumulado_12m != 0 else 0.0
    }
    
    # Comparativo Detalhado
    comparativo_detalhado = {
        "natal": {
            "saldo": result["natal"]["kpis"]["saldo"],
            "admissoes": result["natal"]["kpis"]["admissoes"],
            "desligamentos": result["natal"]["kpis"]["desligamentos"],
            "acumulado_ano": natal_acumulado_ano,
            "acumulado_12m": natal_acumulado_12m,
            "var_relativa_12m": round(natal_var_12m, 2),
            "estoque": current_natal_stock
        },
        "rn": {
            "saldo": result["rn"]["kpis"]["saldo"],
            "admissoes": result["rn"]["kpis"]["admissoes"],
            "desligamentos": result["rn"]["kpis"]["desligamentos"],
            "acumulado_ano": rn_acumulado_ano,
            "acumulado_12m": rn_acumulado_12m,
            "var_relativa_12m": round(rn_var_12m, 2),
            "estoque": current_rn_stock
        }
    }
    
    # Boletim Automatizado
    rn_setor_sorted = sorted(result["rn"]["por_setor"], key=lambda x: x["saldo"], reverse=True)
    lider = rn_setor_sorted[0] if len(rn_setor_sorted) > 0 else {"nome": "N/A", "saldo": 0}
    segundo = rn_setor_sorted[1] if len(rn_setor_sorted) > 1 else {"nome": "N/A", "saldo": 0}
    terceiro = rn_setor_sorted[2] if len(rn_setor_sorted) > 2 else {"nome": "N/A", "saldo": 0}
    
    def fmt_saldo(val):
        return f"+{val:,}" if val > 0 else f"{val:,}"
        
    boletim = (
        f"O Rio Grande do Norte registrou saldo de {fmt_saldo(result['rn']['kpis']['saldo'])} vagas em {result['referencia'].lower()}. "
        f"O setor de {lider['nome']} liderou com {fmt_saldo(lider['saldo'])} postos, seguido de {segundo['nome']} ({fmt_saldo(segundo['saldo'])}) "
        f"e {terceiro['nome']} ({fmt_saldo(terceiro['saldo'])}). No acumulado dos últimos 12 meses, o estado mantém crescimento "
        f"positivo de {fmt_saldo(rn_acumulado_12m)} vagas, equivalente a +{round(rn_var_12m, 2)}% de expansão no estoque."
    )
    
    return {
        "referencia": result["referencia"],
        "anomes": current_anomes,
        "natal_motor_rn": motor_emprego,
        "comparativo_detalhado": comparativo_detalhado,
        "participacao_natal_admissoes": participacao_admissoes,
        "comparativo_setorial_rn_natal": comparativo_setorial,
        "municipios_rn": result["rn"]["municipios"],
        "contexto_regional": result["nordeste"],
        "detalhe_servicos": result["rn"]["detalhe_servicos"],
        "saldo_porte": result["rn"]["por_porte"],
        "saldo_setor": result["rn"]["por_setor"],
        "saldo_setor_natal": result["natal"]["por_setor"],
        "boletim": boletim,
    }


# ---------------------------------------------------------------------------
# Pipeline e Ciclo de Vida FastAPI
# ---------------------------------------------------------------------------

def load_data_pipeline(force: bool = False):
    """
    Pipeline completo: verifica FTP → baixa → processa → atualiza cache.
    Thread-safe via _lock.
    """
    with _lock:
        if _cache["status"] == "loading":
            logger.info("Pipeline já em execução, ignorando.")
            return

        _cache["status"] = "loading"
        _cache["error"] = None

    try:
        logger.info("Verificando FTP para o mês mais recente...")
        latest = get_latest_month()
        logger.info(f"Mês mais recente no FTP: {latest}")

        with _lock:
            if not force and _cache["anomes"] == latest and _cache["data"] is not None:
                logger.info(f"Dados já atualizados para {latest}, nada a fazer.")
                _cache["status"] = "ready"
                return

        # Download
        archive_path = download_cagedmov(latest)

        # Processamento
        logger.info(f"Processando dados de {latest}...")
        result = process_caged_data(archive_path, latest)

        # Inserir no histórico de forma persistente
        save_to_history(result)

        # Atualizar cache
        with _lock:
            _cache["data"] = result
            _cache["anomes"] = latest
            _cache["status"] = "ready"
            _cache["last_check"] = time.time()
            _cache["error"] = None

        # Limpar arquivos antigos
        cleanup_old_files(latest)
        logger.info(f"✅ Dados prontos para {latest}")

    except Exception as e:
        logger.error(f"Erro no pipeline de dados: {e}", exc_info=True)
        with _lock:
            _cache["status"] = "error"
            _cache["error"] = str(e)


def background_updater():
    """Thread de atualização periódica a cada UPDATE_INTERVAL_HOURS horas."""
    while True:
        try:
            logger.info("🔄 Verificando atualização automática dos dados...")
            load_data_pipeline()
        except Exception as e:
            logger.error(f"Erro no updater: {e}")
        time.sleep(UPDATE_INTERVAL_HOURS * 3600)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Inicializa o download dos dados na startup e dispara o updater."""
    logger.info("🚀 Iniciando servidor — carregando dados do CAGED...")
    
    # Carregar dados em background na startup
    init_thread = threading.Thread(target=load_data_pipeline, daemon=True)
    init_thread.start()

    # Iniciar updater periódico
    updater_thread = threading.Thread(target=background_updater, daemon=True)
    updater_thread.start()

    yield  # Servidor rodando

    logger.info("Servidor encerrado.")


# Criar app FastAPI
app = FastAPI(
    title="API Dashboard Emprego Natal/RN",
    description="Backend para o Observatório do Emprego — dados do NOVO CAGED",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS — permitir requisições do frontend Next.js
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Permitir qualquer origem para fins de desenvolvimento
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
def root():
    return {"message": "API Dashboard Emprego Natal/RN", "status": _cache["status"]}


@app.get("/api/status")
def get_status():
    """Retorna o status atual do pipeline de dados."""
    with _lock:
        return {
            "status": _cache["status"],
            "anomes": _cache["anomes"],
            "error": _cache["error"],
            "last_check": _cache["last_check"],
        }


@app.get("/api/dashboard")
def get_dashboard():
    """
    Retorna todos os dados processados para o dashboard.
    Se os dados ainda estão carregando, retorna 202 Accepted.
    """
    with _lock:
        status = _cache["status"]
        data = _cache["data"]
        error = _cache["error"]

    if status == "loading":
        return {
            "status": "loading",
            "message": "Dados sendo carregados. Aguarde alguns instantes...",
        }
    
    if status == "error":
        raise HTTPException(
            status_code=500,
            detail=f"Erro ao carregar dados: {error}"
        )
    
    if data is None:
        return {
            "status": "loading",
            "message": "Inicializando pipeline de dados...",
        }

    # Gerar a resposta enriquecida combinando com a série histórica
    enriched_data = build_dashboard_response(data)
    return {"status": "ready", **enriched_data}


@app.post("/api/refresh")
def force_refresh():
    """Força um re-download e reprocessamento dos dados."""
    thread = threading.Thread(target=load_data_pipeline, args=(True,), daemon=True)
    thread.start()
    return {"message": "Atualização iniciada em background."}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000, reload=False)

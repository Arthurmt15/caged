"""
data_processor.py
Extrai o arquivo .7z do CAGED, lê o CSV em chunks filtrando na hora
por Rio Grande do Norte (UF=24), Natal (município=240810) e região Nordeste.
Cache em disco para reinicializações instantâneas.
"""

import pandas as pd
import json
import logging
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

# Constantes geográficas
UF_RN = 24
MUNICIPIO_NATAL = 240810

# Tamanho do chunk para leitura (linhas por vez — evita carregar o Brasil todo na RAM)
CHUNK_SIZE = 150_000

# Mapeamento de seções CNAE para nomes legíveis
CNAE_SECOES = {
    "A": "Agricultura e Pecuária",
    "B": "Indústrias Extrativas",
    "C": "Indústria de Transformação",
    "D": "Eletricidade e Gás",
    "E": "Água e Saneamento",
    "F": "Construção",
    "G": "Comércio e Reparação",
    "H": "Transporte e Armazenagem",
    "I": "Alojamento e Alimentação",
    "J": "Informação e Comunicação",
    "K": "Atividades Financeiras",
    "L": "Atividades Imobiliárias",
    "M": "Atividades Profissionais",
    "N": "Atividades Administrativas",
    "O": "Administração Pública",
    "P": "Educação",
    "Q": "Saúde e Serviço Social",
    "R": "Artes e Esportes",
    "S": "Outras Atividades de Serviços",
    "T": "Serviços Domésticos",
    "U": "Organismos Internacionais",
}

# 5 Grandes Setores
SETORES_MAP = {
    "Agropecuária": ["A"],
    "Indústria": ["B", "C", "D", "E"],
    "Construção": ["F"],
    "Comércio": ["G"],
    "Serviços": ["H", "I", "J", "K", "L", "M", "N", "O", "P", "Q", "R", "S", "T", "U"],
}

# Subsetores de Serviços
SERVICES_SUBSECTORS = {
    "Info, Comunicação e Ativ. Financeiras": ["J", "K"],
    "Educação": ["P"],
    "Saúde Humana": ["Q"],
    "Adm.Pública e Defesa": ["O"],
    "Ativ.Administrativas": ["N"],
    "Ativ. Profissionais e Técnicas": ["M"],
    "Transporte e Armazenagem": ["H"],
    "Alojamento e Alimentação": ["I"],
    "Artes e Recreação": ["R"],
    "Outros Serviços": ["L", "S", "T", "U"],
}

# UFs do Nordeste
UF_NORDESTE = {
    21: "Maranhão",
    22: "Piauí",
    23: "Ceará",
    24: "Rio Grande do Norte",
    25: "Paraíba",
    26: "Pernambuco",
    27: "Alagoas",
    28: "Sergipe",
    29: "Bahia",
}

# Capitais do Nordeste (código de 6 dígitos)
CAPITAIS_NORDESTE = {
    "211130": "São Luís",
    "221100": "Teresina",
    "230440": "Fortaleza",
    "240810": "Natal",
    "250750": "João Pessoa",
    "261160": "Recife",
    "270430": "Maceió",
    "280030": "Aracaju",
    "292740": "Salvador",
}

# Municípios selecionados do RN (código de 6 dígitos)
MUNICIPIOS_RN = {
    "240810": "Natal",
    "240325": "Parnamirim",
    "241200": "São Gonçalo do Amarante",
    "240200": "Caicó",
    "240360": "Extremoz",
    "240940": "Pau dos Ferros",
    "241460": "Upanema",
    "240145": "Baraúna",
    "240420": "Goianinha",
    "240100": "Apodi",
    "240800": "Mossoró",
}

SEXO_MAP = {1: "Masculino", 2: "Feminino", 9: "Não identificado"}

INSTRUCAO_MAP = {
    1: "Analfabeto", 2: "Até 5ª Incompleto", 3: "5ª Completo Fund.",
    4: "6ª a 9ª Fund.", 5: "Fund. Completo", 6: "Médio Incompleto",
    7: "Médio Completo", 8: "Superior Incompleto", 9: "Superior Completo",
    10: "Mestrado", 11: "Doutorado", 80: "Pós-grad. Incompleto",
}


# ---------------------------------------------------------------------------
# Cache em disco
# ---------------------------------------------------------------------------

def get_cache_path(anomes: str) -> Path:
    return Path(__file__).parent / "data" / f"cache_{anomes}.json"


def load_from_cache(anomes: str) -> Optional[dict]:
    """Carrega dados do cache em disco (instantâneo). Retorna None se não existir."""
    cache_path = get_cache_path(anomes)
    if cache_path.exists():
        logger.info(f"⚡ Cache encontrado — carregando {cache_path.name} sem re-processar")
        with open(cache_path, "r", encoding="utf-8") as f:
            return json.load(f)
    return None


def save_to_cache(anomes: str, data: dict):
    """Salva dados processados em disco para carregamentos futuros."""
    cache_path = get_cache_path(anomes)
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    with open(cache_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False)
    logger.info(f"💾 Cache salvo em {cache_path.name} ({cache_path.stat().st_size / 1e3:.0f} KB)")


# ---------------------------------------------------------------------------
# Extração do .7z
# ---------------------------------------------------------------------------

def extract_7z(archive_path: Path, extract_to: Path) -> list[Path]:
    """Extrai um arquivo .7z e retorna lista de arquivos extraídos."""
    try:
        import py7zr
    except ModuleNotFoundError as exc:
        raise RuntimeError(
            "py7zr não está instalado neste ambiente. Instale as dependências do projeto "
            "ou use uma versão do Python com wheels disponíveis para py7zr."
        ) from exc

    extract_to.mkdir(parents=True, exist_ok=True)

    # Se já foi extraído, não extrai de novo
    existing = list(extract_to.glob("*.txt"))
    if existing:
        logger.info(f"⚡ Arquivo já extraído: {existing[0].name}")
        return existing

    logger.info(f"Extraindo {archive_path.name}...")
    with py7zr.SevenZipFile(archive_path, mode="r") as archive:
        archive.extractall(path=extract_to)

    extracted = list(extract_to.glob("*.txt"))
    logger.info(f"Extraído: {[f.name for f in extracted]}")
    return extracted


# ---------------------------------------------------------------------------
# Leitura em chunks — filtra RN, Natal e Nordeste durante a leitura
# ---------------------------------------------------------------------------

def _detect_columns(sample_df: pd.DataFrame) -> dict:
    """Detecta os nomes reais das colunas de interesse no CSV."""
    cols = {c.lower().strip(): c for c in sample_df.columns}
    
    def find(keywords):
        for k in keywords:
            for col_lower, col_orig in cols.items():
                if k in col_lower:
                    return col_orig
        return None

    return {
        "uf":       find(["uf"]),
        "mun":      find(["munic"]),
        "saldo":    find(["saldo"]),
        "secao":    find(["seç", "seca", "secao", "seção"]),
        "sexo":     find(["sexo"]),
        "idade":    find(["idade"]),
        "grau":     find(["grau", "instruc"]),
        "tamestab": find(["tamestab", "tamanho", "porte", "estabelecimento_tamanho"]),
    }


def map_porte_empresa(val) -> str:
    """Mapeia os códigos de tamestab para classes de porte da empresa."""
    val_num = pd.to_numeric(val, errors="coerce")
    if pd.isna(val_num):
        return "Ignorado"
    val_num = int(val_num)
    if val_num in [1, 2, 3, 4]:
        return "Micro e Pequena (até 49)"
    elif val_num in [5, 6]:
        return "Média (50 a 249)"
    elif val_num in [7, 8, 9]:
        return "Grande (250+)"
    else:
        return "Ignorado"


def read_and_filter_chunks(txt_path: Path) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """
    Lê o CSV em chunks e filtra Nordeste, RN e Natal em cada chunk.
    Muito mais rápido e econômico em memória do que ler tudo de uma vez.
    Retorna (df_ne, df_rn, df_natal).
    """
    logger.info(f"Lendo CSV em chunks de {CHUNK_SIZE:,} linhas: {txt_path.name}")

    ne_chunks = []
    rn_chunks = []
    natal_chunks = []
    col_map = None
    uf_col = mun_col = None
    total_rows = 0
    chunk_count = 0

    reader = pd.read_csv(
        txt_path,
        sep=";",
        encoding="utf-8",
        chunksize=CHUNK_SIZE,
        low_memory=False,
    )

    for chunk in reader:
        chunk_count += 1
        total_rows += len(chunk)

        # Detectar colunas no primeiro chunk
        if col_map is None:
            col_map = _detect_columns(chunk)
            uf_col = col_map["uf"]
            mun_col = col_map["mun"]
            logger.info(f"Colunas detectadas: {col_map}")
            if not uf_col or not mun_col:
                raise ValueError(f"Colunas UF/município não encontradas. Disponíveis: {list(chunk.columns)}")

        # Filtrar Nordeste (UF codes de 21 a 29)
        uf_numeric = pd.to_numeric(chunk[uf_col], errors="coerce")
        mask_ne = uf_numeric.isin([21, 22, 23, 24, 25, 26, 27, 28, 29])
        df_ne_chunk = chunk[mask_ne]

        # Filtrar RN (UF=24) dentro do Nordeste
        df_rn_chunk = df_ne_chunk[pd.to_numeric(df_ne_chunk[uf_col], errors="coerce") == UF_RN]

        # Filtrar Natal (município=240810) dentro do RN
        df_natal_chunk = df_rn_chunk[pd.to_numeric(df_rn_chunk[mun_col], errors="coerce") == MUNICIPIO_NATAL]

        if len(df_ne_chunk) > 0:
            ne_chunks.append(df_ne_chunk)
        if len(df_rn_chunk) > 0:
            rn_chunks.append(df_rn_chunk)
        if len(df_natal_chunk) > 0:
            natal_chunks.append(df_natal_chunk)

        if chunk_count % 5 == 0:
            logger.info(f"  Processado: {total_rows:,} linhas | NE acumulado: {sum(len(c) for c in ne_chunks):,}")

    df_ne    = pd.concat(ne_chunks, ignore_index=True) if ne_chunks else pd.DataFrame()
    df_rn    = pd.concat(rn_chunks, ignore_index=True) if rn_chunks else pd.DataFrame()
    df_natal = pd.concat(natal_chunks, ignore_index=True) if natal_chunks else pd.DataFrame()

    logger.info(f"Leitura concluída: {total_rows:,} linhas totais → NE: {len(df_ne):,} | RN: {len(df_rn):,} | Natal: {len(df_natal):,}")
    return df_ne, df_rn, df_natal


# ---------------------------------------------------------------------------
# Agregações
# ---------------------------------------------------------------------------

def _saldo_col(df: pd.DataFrame) -> Optional[str]:
    return next((c for c in df.columns if "saldo" in c.lower()), None)


def compute_kpis(df: pd.DataFrame) -> dict:
    col = _saldo_col(df)
    if col is None or df.empty:
        return {"saldo": 0, "admissoes": 0, "desligamentos": 0}
    s = pd.to_numeric(df[col], errors="coerce").fillna(0)
    return {
        "saldo":         int(s.sum()),
        "admissoes":     int(s[s > 0].sum()),
        "desligamentos": int(abs(s[s < 0].sum())),
    }


def compute_by_sector(df: pd.DataFrame) -> list[dict]:
    """Retorna saldo de vagas detalhado por seção CNAE."""
    if df.empty:
        return []
    col_map = _detect_columns(df)
    secao_col = col_map.get("secao")
    saldo_col = _saldo_col(df)
    if not secao_col or not saldo_col:
        return []
    s = pd.to_numeric(df[saldo_col], errors="coerce").fillna(0)
    grouped = df.assign(_s=s).groupby(secao_col)["_s"].sum().reset_index()
    grouped.columns = ["secao", "saldo"]
    grouped["nome"] = grouped["secao"].map(CNAE_SECOES).fillna("Outros")
    grouped["saldo"] = grouped["saldo"].astype(int)
    return grouped.sort_values("saldo", ascending=False).to_dict(orient="records")


def compute_by_main_sector(df: pd.DataFrame) -> list[dict]:
    """Agrupa saldo, admissões e desligamentos nos 5 grandes setores (Serviços, Comércio, Construção, Indústria, Agropecuária)."""
    if df.empty:
        return []
    col_map = _detect_columns(df)
    secao_col = col_map.get("secao")
    saldo_col = _saldo_col(df)
    if not secao_col or not saldo_col:
        return []
        
    def get_main_sector(sec):
        for name, sections in SETORES_MAP.items():
            if sec in sections:
                return name
        return "Outros"
        
    df2 = df.copy()
    df2["setor"] = df2[secao_col].apply(get_main_sector)
    s = pd.to_numeric(df2[saldo_col], errors="coerce").fillna(0)
    
    df2["_s"] = s
    df2["_adm"] = s.apply(lambda x: x if x > 0 else 0)
    df2["_des"] = s.apply(lambda x: abs(x) if x < 0 else 0)
    
    grouped = df2.groupby("setor").agg(
        saldo=("_s", "sum"),
        admissoes=("_adm", "sum"),
        desligamentos=("_des", "sum")
    ).reset_index()
    
    grouped.columns = ["nome", "saldo", "admissoes", "desligamentos"]
    grouped["saldo"] = grouped["saldo"].astype(int)
    grouped["admissoes"] = grouped["admissoes"].astype(int)
    grouped["desligamentos"] = grouped["desligamentos"].astype(int)
    
    existing_names = set(grouped["nome"])
    missing_records = []
    for name in SETORES_MAP.keys():
        if name not in existing_names:
            missing_records.append({"nome": name, "saldo": 0, "admissoes": 0, "desligamentos": 0})
    if missing_records:
        grouped = pd.concat([grouped, pd.DataFrame(missing_records)], ignore_index=True)
        
    grouped = grouped[grouped["nome"] != "Outros"]
    return grouped.sort_values("saldo", ascending=False).to_dict(orient="records")


def compute_services_detailing(df: pd.DataFrame) -> list[dict]:
    """Retorna o detalhamento do saldo do setor de serviços para o RN."""
    if df.empty:
        return []
    col_map = _detect_columns(df)
    secao_col = col_map.get("secao")
    saldo_col = _saldo_col(df)
    if not secao_col or not saldo_col:
        return []
    
    # Filtra apenas registros que pertencem ao setor de serviços
    services_sections = ["H", "I", "J", "K", "L", "M", "N", "O", "P", "Q", "R", "S", "T", "U"]
    df_serv = df[df[secao_col].isin(services_sections)].copy()
    if df_serv.empty:
        return []
    
    def map_subsector(sec):
        for name, sections in SERVICES_SUBSECTORS.items():
            if sec in sections:
                return name
        return "Outros Serviços"
        
    df_serv["subsector"] = df_serv[secao_col].apply(map_subsector)
    s = pd.to_numeric(df_serv[saldo_col], errors="coerce").fillna(0)
    grouped = df_serv.assign(_s=s).groupby("subsector")["_s"].sum().reset_index()
    grouped.columns = ["nome", "saldo"]
    grouped["saldo"] = grouped["saldo"].astype(int)
    return grouped.sort_values("saldo", ascending=False).to_dict(orient="records")


def compute_by_porte(df: pd.DataFrame) -> list[dict]:
    """Retorna saldo de vagas agrupado por porte de estabelecimento."""
    if df.empty:
        return []
    col_map = _detect_columns(df)
    porte_col = col_map.get("tamestab")
    saldo_col = _saldo_col(df)
    if not porte_col or not saldo_col:
        return []
    
    df2 = df.copy()
    df2["porte"] = df2[porte_col].apply(map_porte_empresa)
    s = pd.to_numeric(df2[saldo_col], errors="coerce").fillna(0)
    grouped = df2.assign(_s=s).groupby("porte")["_s"].sum().reset_index()
    grouped.columns = ["porte", "saldo"]
    grouped["saldo"] = grouped["saldo"].astype(int)
    
    order = {
        "Micro e Pequena (até 49)": 0,
        "Média (50 a 249)": 1,
        "Grande (250+)": 2,
        "Ignorado": 3
    }
    grouped["order"] = grouped["porte"].map(order).fillna(4)
    grouped = grouped.sort_values("order").drop(columns=["order"])
    return grouped.to_dict(orient="records")


def compute_by_municipality(df: pd.DataFrame) -> list[dict]:
    """Retorna o saldo de vagas para os principais municípios selecionados do RN."""
    if df.empty:
        return []
    col_map = _detect_columns(df)
    mun_col = col_map.get("mun")
    saldo_col = _saldo_col(df)
    if not mun_col or not saldo_col:
        return []
    
    s = pd.to_numeric(df[saldo_col], errors="coerce").fillna(0)
    grouped = df.assign(_s=s).groupby(mun_col)["_s"].sum().reset_index()
    grouped.columns = ["codigo", "saldo"]
    
    grouped["codigo"] = grouped["codigo"].astype(str).str.split('.').str[0].str.strip()
    grouped["nome"] = grouped["codigo"].map(MUNICIPIOS_RN)
    
    grouped_filtered = grouped[grouped["nome"].notna()].copy()
    grouped_filtered["saldo"] = grouped_filtered["saldo"].astype(int)
    
    existing_names = set(grouped_filtered["nome"])
    missing_records = []
    for code, name in MUNICIPIOS_RN.items():
        if name not in existing_names:
            missing_records.append({"codigo": code, "nome": name, "saldo": 0})
    if missing_records:
        grouped_filtered = pd.concat([grouped_filtered, pd.DataFrame(missing_records)], ignore_index=True)
        
    return grouped_filtered.sort_values("saldo", ascending=False).to_dict(orient="records")


def compute_regional_context(df_ne: pd.DataFrame) -> tuple[list[dict], list[dict]]:
    """Gera rankings de saldo dos Estados do Nordeste e de suas Capitais."""
    if df_ne.empty:
        return [], []
    col_map = _detect_columns(df_ne)
    uf_col = col_map.get("uf")
    mun_col = col_map.get("mun")
    saldo_col = _saldo_col(df_ne)
    if not uf_col or not mun_col or not saldo_col:
        return [], []
    
    s = pd.to_numeric(df_ne[saldo_col], errors="coerce").fillna(0)
    
    # Estados do Nordeste
    grouped_uf = df_ne.assign(_s=s).groupby(uf_col)["_s"].sum().reset_index()
    grouped_uf.columns = ["uf_codigo", "saldo"]
    grouped_uf["uf_codigo"] = pd.to_numeric(grouped_uf["uf_codigo"], errors="coerce")
    grouped_uf["nome"] = grouped_uf["uf_codigo"].map(UF_NORDESTE)
    grouped_uf_filtered = grouped_uf[grouped_uf["nome"].notna()].copy()
    grouped_uf_filtered["saldo"] = grouped_uf_filtered["saldo"].astype(int)
    
    # Capitais do Nordeste
    df_ne2 = df_ne.copy()
    df_ne2["mun_str"] = df_ne2[mun_col].astype(str).str.split('.').str[0].str.strip()
    grouped_mun = df_ne2.assign(_s=s).groupby("mun_str")["_s"].sum().reset_index()
    grouped_mun.columns = ["codigo", "saldo"]
    grouped_mun["nome"] = grouped_mun["codigo"].map(CAPITAIS_NORDESTE)
    grouped_mun_filtered = grouped_mun[grouped_mun["nome"].notna()].copy()
    grouped_mun_filtered["saldo"] = grouped_mun_filtered["saldo"].astype(int)
    
    # Garantir que todos estejam mapeados mesmo que com saldo 0
    existing_states = set(grouped_uf_filtered["nome"])
    missing_states = []
    for code, name in UF_NORDESTE.items():
        if name not in existing_states:
            missing_states.append({"uf_codigo": code, "nome": name, "saldo": 0})
    if missing_states:
        grouped_uf_filtered = pd.concat([grouped_uf_filtered, pd.DataFrame(missing_states)], ignore_index=True)
        
    existing_caps = set(grouped_mun_filtered["nome"])
    missing_caps = []
    for code, name in CAPITAIS_NORDESTE.items():
        if name not in existing_caps:
            missing_caps.append({"codigo": code, "nome": name, "saldo": 0})
    if missing_caps:
        grouped_mun_filtered = pd.concat([grouped_mun_filtered, pd.DataFrame(missing_caps)], ignore_index=True)
    
    ranking_estados = grouped_uf_filtered.sort_values("saldo", ascending=False).to_dict(orient="records")
    ranking_capitais = grouped_mun_filtered.sort_values("saldo", ascending=False).to_dict(orient="records")
    
    return ranking_estados, ranking_capitais


def compute_by_sex(df: pd.DataFrame) -> list[dict]:
    if df.empty:
        return []
    col_map = _detect_columns(df)
    sexo_col = col_map.get("sexo")
    saldo_col = _saldo_col(df)
    if not sexo_col or not saldo_col:
        return []
    s = pd.to_numeric(df[saldo_col], errors="coerce").fillna(0)
    grouped = df.assign(_s=s).groupby(sexo_col)["_s"].sum().reset_index()
    grouped.columns = ["codigo", "saldo"]
    grouped["nome"] = pd.to_numeric(grouped["codigo"], errors="coerce").map(SEXO_MAP).fillna("Outros")
    grouped["saldo"] = grouped["saldo"].astype(int)
    return grouped.to_dict(orient="records")


def compute_by_age_group(df: pd.DataFrame) -> list[dict]:
    if df.empty:
        return []
    col_map = _detect_columns(df)
    idade_col = col_map.get("idade")
    saldo_col = _saldo_col(df)
    if not idade_col or not saldo_col:
        return []
    bins   = [0, 17, 24, 29, 39, 49, 64, 150]
    labels = ["Menor de 18", "18 a 24", "25 a 29", "30 a 39", "40 a 49", "50 a 64", "65+"]
    df2 = df.copy()
    df2["_idade"] = pd.to_numeric(df2[idade_col], errors="coerce")
    df2["_faixa"] = pd.cut(df2["_idade"], bins=bins, labels=labels, right=True)
    df2["_s"]     = pd.to_numeric(df2[saldo_col], errors="coerce").fillna(0)
    grouped = df2.groupby("_faixa", observed=True)["_s"].sum().reset_index()
    grouped.columns = ["faixa", "saldo"]
    grouped["saldo"] = grouped["saldo"].astype(int)
    return grouped.to_dict(orient="records")


def compute_by_instruction(df: pd.DataFrame) -> list[dict]:
    if df.empty:
        return []
    col_map = _detect_columns(df)
    grau_col = col_map.get("grau")
    saldo_col = _saldo_col(df)
    if not grau_col or not saldo_col:
        return []
    s = pd.to_numeric(df[saldo_col], errors="coerce").fillna(0)
    grouped = df.assign(_s=s).groupby(grau_col)["_s"].sum().reset_index()
    grouped.columns = ["codigo", "saldo"]
    grouped["nome"] = pd.to_numeric(grouped["codigo"], errors="coerce").map(INSTRUCAO_MAP).fillna("Não informado")
    grouped["saldo"] = grouped["saldo"].astype(int)
    return grouped.sort_values("saldo", ascending=False).to_dict(orient="records")


# ---------------------------------------------------------------------------
# Orquestrador principal
# ---------------------------------------------------------------------------

def _mes_ptbr(anomes: str) -> str:
    meses = {
        "01": "Janeiro", "02": "Fevereiro", "03": "Março",    "04": "Abril",
        "05": "Maio",    "06": "Junho",     "07": "Julho",    "08": "Agosto",
        "09": "Setembro","10": "Outubro",   "11": "Novembro", "12": "Dezembro",
    }
    return f"{meses.get(anomes[4:], anomes[4:])}/{anomes[:4]}"


def process_caged_data(archive_path: Path, anomes: str) -> dict:
    """
    Orquestra todo o processamento:
    1. Tenta carregar do cache (instantâneo se já processado antes)
    2. Extrai o .7z (pula se já extraído)
    3. Lê o CSV em chunks filtrando Nordeste/RN/Natal na hora
    4. Salva cache em disco para próximas execuções
    """

    # 1. Tentar cache primeiro — carregamento instantâneo
    cached = load_from_cache(anomes)
    if cached:
        # Se o cache antigo não tiver as novas chaves, vamos reprocessar
        nordeste_ok = (
            "nordeste" in cached
            and "admissoes" in cached["nordeste"]
            and "desligamentos" in cached["nordeste"]
        )
        if "rn" in cached and "municipios" in cached["rn"] and nordeste_ok:
            return cached
        logger.info("Cache antigo detectado sem admissoes/desligamentos no nordeste. Reprocessando...")

    # 2. Extrair .7z (ignora se já extraído)
    extract_dir = archive_path.parent / f"extracted_{anomes}"
    extracted = extract_7z(archive_path, extract_dir)
    if not extracted:
        raise FileNotFoundError(f"Nenhum .txt encontrado em {extract_dir}")
    txt_path = extracted[0]

    # 3. Ler em chunks — filtra RN/Natal/Nordeste durante a leitura
    df_ne, df_rn, df_natal = read_and_filter_chunks(txt_path)

    # 4. Agregar
    natal_kpis     = compute_kpis(df_natal)
    natal_setor    = compute_by_sector(df_natal)
    natal_setor_5  = compute_by_main_sector(df_natal)
    natal_sexo     = compute_by_sex(df_natal)
    natal_faixa    = compute_by_age_group(df_natal)
    natal_instrucao = compute_by_instruction(df_natal)

    rn_kpis          = compute_kpis(df_rn)
    rn_setor         = compute_by_sector(df_rn)
    rn_setor_5       = compute_by_main_sector(df_rn)
    rn_municipios    = compute_by_municipality(df_rn)
    rn_porte         = compute_by_porte(df_rn)
    rn_servicos_det  = compute_services_detailing(df_rn)

    ne_kpis = compute_kpis(df_ne)
    ne_estados, ne_capitais = compute_regional_context(df_ne)

    payload = {
        "referencia": _mes_ptbr(anomes),
        "anomes":     anomes,
        "natal": {
            "kpis":            natal_kpis,
            "por_setor_det":   natal_setor,
            "por_setor":       natal_setor_5,
            "por_sexo":        natal_sexo,
            "por_faixa_etaria": natal_faixa,
            "por_instrucao":   natal_instrucao,
        },
        "rn": {
            "kpis":             rn_kpis,
            "por_setor_det":    rn_setor,
            "por_setor":        rn_setor_5,
            "municipios":       rn_municipios,
            "por_porte":        rn_porte,
            "detalhe_servicos": rn_servicos_det,
        },
        "nordeste": {
            "saldo":            ne_kpis["saldo"],
            "admissoes":        ne_kpis["admissoes"],
            "desligamentos":    ne_kpis["desligamentos"],
            "ranking_estados":  ne_estados,
            "ranking_capitais": ne_capitais,
        }
    }

    logger.info(
        f"✅ Processamento concluído: Natal saldo={natal_kpis['saldo']:+,} | RN saldo={rn_kpis['saldo']:+,}"
    )

    # 5. Salvar cache para próximas execuções
    save_to_cache(anomes, payload)

    return payload

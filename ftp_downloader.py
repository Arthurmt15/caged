"""
ftp_downloader.py
Responsável por acessar o FTP do MTPS, listar os meses disponíveis,
identificar o mais recente e baixar o arquivo CAGEDMOV correspondente.
"""

import ftplib
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

FTP_HOST = "ftp.mtps.gov.br"
FTP_BASE_PATH = "/pdet/microdados/NOVO CAGED"
FTP_ENCODING = "latin-1"   # O servidor do governo usa latin-1, não UTF-8
DATA_DIR = Path(__file__).parent / "data"


def _make_ftp(timeout: int = 30) -> ftplib.FTP:
    """Cria e retorna uma conexão FTP configurada com encoding latin-1."""
    ftp = ftplib.FTP(timeout=timeout)
    ftp.encoding = FTP_ENCODING
    ftp.connect(FTP_HOST)
    ftp.login()
    return ftp


def get_available_years() -> list[str]:
    """Lista os anos disponíveis no FTP."""
    with _make_ftp() as ftp:
        ftp.cwd(FTP_BASE_PATH)
        items = ftp.nlst()
    # Filtrar apenas pastas de ano (4 dígitos numéricos)
    years = sorted([y for y in items if y.isdigit() and len(y) == 4], reverse=True)
    logger.info(f"Anos disponíveis no FTP: {years}")
    return years


def get_available_months(year: str) -> list[str]:
    """Lista os meses disponíveis para um determinado ano no FTP."""
    path = f"{FTP_BASE_PATH}/{year}"
    with _make_ftp() as ftp:
        ftp.cwd(path)
        items = ftp.nlst()
    # Filtrar apenas pastas de mês (6 dígitos numéricos, ex: 202603)
    months = sorted([m for m in items if m.isdigit() and len(m) == 6], reverse=True)
    logger.info(f"Meses disponíveis em {year}: {months}")
    return months


def get_latest_month() -> str:
    """Retorna o ANOMES mais recente disponível no FTP (ex: '202603')."""
    years = get_available_years()
    for year in years:
        months = get_available_months(year)
        if months:
            return months[0]  # Mais recente primeiro
    raise ValueError("Nenhum mês encontrado no FTP.")


def list_files_in_month(anomes: str) -> list[str]:
    """Lista os arquivos disponíveis para um ANOMES (ex: '202603')."""
    year = anomes[:4]
    path = f"{FTP_BASE_PATH}/{year}/{anomes}"
    with _make_ftp() as ftp:
        ftp.cwd(path)
        items = ftp.nlst()
    return items


def download_file(anomes: str, filename: str, dest_dir: Path = DATA_DIR) -> Path:
    """
    Baixa um arquivo específico do FTP para o diretório local.
    Retorna o caminho do arquivo baixado.
    """
    year = anomes[:4]
    remote_path = f"{FTP_BASE_PATH}/{year}/{anomes}/{filename}"
    dest_dir.mkdir(parents=True, exist_ok=True)
    local_path = dest_dir / filename

    if local_path.exists():
        logger.info(f"Arquivo já existe localmente: {local_path}")
        return local_path

    logger.info(f"Baixando {filename} do FTP... (pode levar alguns minutos)")
    with _make_ftp(timeout=300) as ftp:
        with open(local_path, "wb") as f:
            ftp.retrbinary(f"RETR {remote_path}", f.write, blocksize=1024 * 1024)

    size_mb = local_path.stat().st_size / 1e6
    logger.info(f"Download concluído: {local_path.name} ({size_mb:.1f} MB)")
    return local_path


def download_cagedmov(anomes: str) -> Path:
    """
    Baixa o arquivo CAGEDMOV do ANOMES especificado.
    Retorna o caminho do arquivo .7z baixado.
    """
    filename = f"CAGEDMOV{anomes}.7z"
    return download_file(anomes, filename)


def cleanup_old_files(keep_anomes: str):
    """Remove arquivos grandes de meses antigos para economizar espaço."""
    if not DATA_DIR.exists():
        return
    for f in DATA_DIR.iterdir():
        # Remover arquivos .7z antigos (cada um tem ~59MB)
        if f.is_file() and f.suffix == ".7z" and keep_anomes not in f.name:
            logger.info(f"Removendo arquivo ZIP antigo: {f.name}")
            try:
                f.unlink()
            except Exception as e:
                logger.error(f"Erro ao remover {f.name}: {e}")
        # Remover pastas extraídas antigas
        elif f.is_dir() and f.name.startswith("extracted_") and keep_anomes not in f.name:
            logger.info(f"Removendo pasta extraída antiga: {f.name}")
            import shutil
            try:
                shutil.rmtree(f)
            except Exception as e:
                logger.error(f"Erro ao remover pasta {f.name}: {e}")

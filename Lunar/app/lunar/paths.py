"""Onde o app está instalado e onde guarda os dados de cada pessoa."""

import os
import shutil
import sys
from pathlib import Path

PKG_DIR = Path(__file__).resolve().parent
APP_DIR = PKG_DIR.parent           # ...\app (código)
ROOT_DIR = APP_DIR.parent          # pasta instalada (tem python\ e app\)
STATIC_DIR = PKG_DIR / "static"


def _pasta_do_pacote():
    """Pasta do pacote MSIX deste processo, ou None se ele não roda de um pacote."""
    if sys.platform != "win32":
        return None  # MSIX é só do Windows
    try:
        import ctypes

        kernel32 = ctypes.windll.kernel32
        tamanho = ctypes.c_uint32(0)
        if kernel32.GetCurrentPackagePath(ctypes.byref(tamanho), None) != 122:  # sem pacote
            return None
        texto = ctypes.create_unicode_buffer(tamanho.value)
        if kernel32.GetCurrentPackagePath(ctypes.byref(tamanho), texto) != 0:
            return None
        return Path(texto.value).resolve()
    except (AttributeError, OSError, ValueError):
        return None


# Instalado pela Microsoft Store (pacote MSIX): a Store atualiza o app, e o "Iniciar com o Windows"
# usa a tarefa de inicialização do pacote em vez da chave Run do registro.
# Confere que a pasta do app é a do pacote: um processo aberto por outro app empacotado (por exemplo,
# o app do Claude) também tem identidade de pacote, mas de outro pacote.
_PACOTE = _pasta_do_pacote()
EMPACOTADO = _PACOTE is not None and (ROOT_DIR == _PACOTE or _PACOTE in ROOT_DIR.parents)


def _pasta_base():
    """Onde cada sistema guarda os dados dos apps de cada pessoa."""
    if sys.platform == "win32":
        return Path(os.environ.get("APPDATA", str(Path.home())))
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support"
    return Path(os.environ.get("XDG_DATA_HOME") or Path.home() / ".local" / "share")


# Logins e histórico ficam fora da pasta do programa: o instalador nunca leva
# as contas de ninguém, e reinstalar não apaga nada.
# Windows: %APPDATA%\VexPontos; Mac: ~/Library/Application Support/VexPontos.
# (A pasta de dados mantém o nome antigo de propósito: renomeá-la faria o app perder as
# contas já conectadas de quem atualiza. É interna, o usuário não a vê.)
_APPDATA = _pasta_base()
DATA_DIR = Path(os.environ.get("LUNAR_DATA") or _APPDATA / "VexPontos")
# Pastas dos nomes que o app já teve, da mais nova para a mais antiga.
DATA_DIRS_ANTIGOS = (_APPDATA / "VexPulse", _APPDATA / "FarmPontos")
MINER_DIR = DATA_DIR / "minerador"  # o minerador grava cookies/ e logs/ aqui
LOG_DIR = DATA_DIR / "logs"
CONFIG_FILE = DATA_DIR / "config.json"
DB_FILE = DATA_DIR / "historico.db"

# LUNAR_PORTA só serve para testar uma segunda cópia ao lado da que está farmando.
PORTA = int(os.environ.get("LUNAR_PORTA") or 47800)  # painel no próprio PC
PORTA_CELULAR = PORTA + 1                                 # painel no Wi-Fi (só quando ativado)


def cookie_file(login):
    return MINER_DIR / "cookies" / f"{login}.pkl"


def python_console():
    """python.exe ao lado do interpretador atual (o app roda em pythonw.exe)."""
    exe = Path(sys.executable)
    console = exe.with_name("python.exe")
    return str(console if console.exists() else exe)


def python_janela():
    exe = Path(sys.executable)
    sem_console = exe.with_name("pythonw.exe")
    return str(sem_console if sem_console.exists() else exe)


def migrar_dados_antigos():
    """Leva contas, canais e histórico da pasta de um nome antigo do app para a atual
    (uma vez só). Devolve a pasta de onde veio, ou None."""
    if os.environ.get("LUNAR_DATA") or DATA_DIR.exists():
        return None
    antiga = next((p for p in DATA_DIRS_ANTIGOS if (p / "config.json").is_file()), None)
    if antiga is None:
        return None
    try:
        antiga.rename(DATA_DIR)
    except OSError:
        # Algo da pasta antiga ainda está aberto (ex.: a janela antiga): copia em vez de mover.
        # A pasta "janela" é só o perfil do navegador da janela; ela se refaz sozinha.
        # Copia para uma pasta temporária e só no fim dá o nome certo: cópia pela metade nunca
        # parece pasta nova (se der erro, a pasta antiga continua intacta e tenta de novo depois).
        temp = DATA_DIR.with_name(DATA_DIR.name + ".migrando")
        shutil.rmtree(temp, ignore_errors=True)
        shutil.copytree(antiga, temp, ignore=shutil.ignore_patterns("janela"))
        temp.rename(DATA_DIR)
    return antiga


def garantir_pastas():
    for pasta in (DATA_DIR, MINER_DIR, MINER_DIR / "cookies", LOG_DIR):
        pasta.mkdir(parents=True, exist_ok=True)

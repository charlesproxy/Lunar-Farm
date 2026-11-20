"""Coisas do Windows: janela do app, iniciar com o Windows, PC acordado, ID do PC e o Edge escondido das lives
da Kick. O app chama isto pelo plataforma.py (o par do Mac é o macutil.py)."""

import ctypes
import os
import subprocess
import threading
import time
import webbrowser
import winreg
from pathlib import Path

from lunar import paths

CHAVE_INICIAR = r"Software\Microsoft\Windows\CurrentVersion\Run"
NOME_INICIAR = "VexPontos"  # nome da chave no registro: mantido para não duplicar o "Iniciar com o Windows" de quem atualiza
NOMES_INICIAR_ANTIGOS = ("VexPulse", "FarmPontos")  # nomes que o app já teve


def comando_do_app(*args):
    script = paths.APP_DIR / "Lunar.pyw"
    return " ".join([f'"{paths.python_janela()}"', f'"{script}"', *args])


def esta_no_iniciar():
    """O Windows vai abrir o app ao ligar? (o instalador também pode ter marcado; o nome
    antigo conta também: o app regrava com o nome e o caminho novos)"""
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, CHAVE_INICIAR) as chave:
            for nome in (NOME_INICIAR, *NOMES_INICIAR_ANTIGOS):
                try:
                    winreg.QueryValueEx(chave, nome)
                    return True
                except FileNotFoundError:
                    pass
    except OSError:
        pass
    return False


def iniciar_com_windows(ligar):
    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, CHAVE_INICIAR, 0, winreg.KEY_SET_VALUE) as chave:
        for antigo in NOMES_INICIAR_ANTIGOS:
            try:
                winreg.DeleteValue(chave, antigo)
            except FileNotFoundError:
                pass
        if ligar:
            winreg.SetValueEx(chave, NOME_INICIAR, 0, winreg.REG_SZ, comando_do_app("--bandeja"))
        else:
            try:
                winreg.DeleteValue(chave, NOME_INICIAR)
            except FileNotFoundError:
                pass


class PcAcordado:
    """Impede a suspensão enquanto o app roda (a tela pode apagar normalmente)."""

    ES_CONTINUOUS = 0x80000000
    ES_SYSTEM_REQUIRED = 0x00000001

    def __init__(self):
        self.ligado = False
        threading.Thread(target=self._loop, daemon=True).start()

    def _loop(self):
        # O pedido vale para a thread que o fez, então fica sempre nesta.
        aplicado = None
        while True:
            if self.ligado != aplicado:
                flags = self.ES_CONTINUOUS | (self.ES_SYSTEM_REQUIRED if self.ligado else 0)
                ctypes.windll.kernel32.SetThreadExecutionState(flags)
                aplicado = self.ligado
            time.sleep(2)


def _achar_navegador_app():
    candidatos = []
    for base in (os.environ.get("PROGRAMFILES(X86)"), os.environ.get("PROGRAMFILES"), os.environ.get("LOCALAPPDATA")):
        if base:
            candidatos.append(Path(base) / "Microsoft/Edge/Application/msedge.exe")
            candidatos.append(Path(base) / "Google/Chrome/Application/chrome.exe")
    for exe in candidatos:
        if exe.is_file():
            return str(exe)
    return None


def abrir_janela(url):
    """Abre o painel numa janela própria (modo app do Edge), sem barra de endereço."""
    exe = _achar_navegador_app()
    if exe is None:
        webbrowser.open(url)
        return
    perfil = paths.DATA_DIR / "janela"
    subprocess.Popen(
        [
            exe,
            f"--app={url}",
            f"--user-data-dir={perfil}",
            "--no-first-run",
            "--no-default-browser-check",
            "--window-size=1180,780",
            "--disable-features=Translate",  # o painel é em português: nada de "Traduzir a página?"
            "--lang=pt-BR",
        ],
        creationflags=0x08000000,
    )


def abrir_no_navegador(url):
    """Abre no navegador normal da pessoa (onde ela já está logada na Twitch)."""
    os.startfile(url)


def id_da_maquina():
    """MachineGuid deste Windows (não muda ao reinstalar o app; muda ao formatar). None se não achar."""
    try:
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Cryptography", 0,
                            winreg.KEY_READ | winreg.KEY_WOW64_64KEY) as k:
            return winreg.QueryValueEx(k, "MachineGuid")[0]
    except OSError:
        return None


# --- Janelas e processos escondidos (Edge das lives da Kick) ---

def eh_navegador(nome):
    """No Windows o Edge e cada pedaço dele são msedge.exe (o Chrome, chrome.exe)."""
    return (nome or "").lower() in ("msedge.exe", "chrome.exe")



class _LimiteBasico(ctypes.Structure):
    _fields_ = [
        ("PerProcessUserTimeLimit", ctypes.c_int64),
        ("PerJobUserTimeLimit", ctypes.c_int64),
        ("LimitFlags", ctypes.c_uint32),
        ("MinimumWorkingSetSize", ctypes.c_size_t),
        ("MaximumWorkingSetSize", ctypes.c_size_t),
        ("ActiveProcessLimit", ctypes.c_uint32),
        ("Affinity", ctypes.c_size_t),
        ("PriorityClass", ctypes.c_uint32),
        ("SchedulingClass", ctypes.c_uint32),
    ]


class _ContadoresIO(ctypes.Structure):
    _fields_ = [(n, ctypes.c_uint64) for n in ("Read", "Write", "Other", "ReadBytes", "WriteBytes", "OtherBytes")]


class _LimiteEstendido(ctypes.Structure):
    _fields_ = [
        ("Basic", _LimiteBasico),
        ("Io", _ContadoresIO),
        ("ProcessMemoryLimit", ctypes.c_size_t),
        ("JobMemoryLimit", ctypes.c_size_t),
        ("PeakProcessMemoryUsed", ctypes.c_size_t),
        ("PeakJobMemoryUsed", ctypes.c_size_t),
    ]


_grupo = None
_grupo_lock = threading.Lock()


def amarrar_ao_app(proc):
    """Põe o processo (e os filhos dele) num grupo do Windows que fecha junto com o app: se o Lunar
    Pontos fechar de qualquer jeito, até travando, o Edge escondido das lives não fica para trás."""
    global _grupo
    k32 = ctypes.windll.kernel32
    k32.CreateJobObjectW.restype = ctypes.c_void_p
    k32.SetInformationJobObject.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_void_p, ctypes.c_uint32]
    k32.AssignProcessToJobObject.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
    with _grupo_lock:
        if _grupo is None:
            grupo = k32.CreateJobObjectW(None, None)
            if not grupo:
                return False
            info = _LimiteEstendido()
            info.Basic.LimitFlags = 0x2000  # JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
            if not k32.SetInformationJobObject(grupo, 9, ctypes.byref(info), ctypes.sizeof(info)):
                return False
            _grupo = grupo
    return bool(k32.AssignProcessToJobObject(_grupo, ctypes.c_void_p(int(proc._handle))))


def _janelas_de(pids):
    user32 = ctypes.windll.user32
    achadas = []
    tipo = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)

    def olhar(hwnd, _):
        pid = ctypes.c_uint32()
        user32.GetWindowThreadProcessId(ctypes.c_void_p(hwnd), ctypes.byref(pid))
        if pid.value in pids and user32.IsWindowVisible(ctypes.c_void_p(hwnd)) and not user32.GetWindow(ctypes.c_void_p(hwnd), 4):
            achadas.append(hwnd)  # janela principal (sem dono) e visível
        return True

    user32.EnumWindows(tipo(olhar), 0)
    return achadas


def tirar_da_barra(pids):
    """Tira da barra de tarefas e do Alt+Tab as janelas desses processos (continuam abertas e
    "visíveis" para o navegador, só que fora da tela)."""
    user32 = ctypes.windll.user32
    user32.GetWindowLongW.argtypes = [ctypes.c_void_p, ctypes.c_int]
    user32.SetWindowLongW.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_long]
    user32.ShowWindow.argtypes = [ctypes.c_void_p, ctypes.c_int]
    for hwnd in _janelas_de(set(pids)):
        estilo = user32.GetWindowLongW(hwnd, -20)  # GWL_EXSTYLE
        if estilo & 0x80:  # WS_EX_TOOLWINDOW: já está fora da barra
            continue
        user32.ShowWindow(hwnd, 0)  # SW_HIDE (a barra só relê o estilo quando a janela reaparece)
        user32.SetWindowLongW(hwnd, -20, (estilo | 0x80) & ~0x40000)  # sem WS_EX_APPWINDOW
        user32.ShowWindow(hwnd, 4)  # SW_SHOWNOACTIVATE


def fechar_janelas(pids):
    """Pede para as janelas desses processos fecharem (como clicar no X)."""
    user32 = ctypes.windll.user32
    user32.PostMessageW.argtypes = [ctypes.c_void_p, ctypes.c_uint, ctypes.c_void_p, ctypes.c_void_p]
    for hwnd in _janelas_de(set(pids)):
        user32.PostMessageW(hwnd, 0x0010, None, None)  # WM_CLOSE

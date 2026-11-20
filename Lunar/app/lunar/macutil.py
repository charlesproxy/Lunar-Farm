"""Coisas do Mac: o par do winutil (iniciar com o Mac, Mac acordado, janela do app, ID do Mac e o Edge/Chrome
das lives da Kick). O app chama isto pelo plataforma.py.

AINDA NÃO TESTADO NUM MAC DE VERDADE (ver pesquisa/mac/PLANO-MAC.md). Só as partes de texto (o LaunchAgent, a
leitura do ioreg, os nomes dos processos) foram testadas, no Windows.

Nada aqui importa coisa só do Mac no topo: o AppKit e o Quartz (do pyobjc, que o pystray já traz no Mac) entram
só dentro das funções. Assim o arquivo abre em qualquer sistema."""

import os
import plistlib
import re
import signal
import subprocess
import threading
import time
import webbrowser
from pathlib import Path

from lunar import paths

# --- Iniciar com o Mac (LaunchAgent) ---

ROTULO = "br.com.vexpulse.lunarfarm"


def _pasta_agentes():
    return Path.home() / "Library" / "LaunchAgents"


def _arquivo_agente():
    return _pasta_agentes() / f"{ROTULO}.plist"


def comando_do_app(*args):
    """Como abrir o app, em lista (o launchd não passa por terminal, então nada de aspas).
    Quando o app virar um .app, aqui entra o executável do pacote."""
    return [paths.python_janela(), str(paths.APP_DIR / "Lunar.pyw"), *args]


def esta_no_iniciar():
    try:
        with open(_arquivo_agente(), "rb") as f:
            dados = plistlib.load(f)
    except (OSError, ValueError, plistlib.InvalidFileException):
        return False
    return dados.get("Label") == ROTULO and bool(dados.get("RunAtLoad"))


def iniciar_com_sistema(ligar):
    """Grava (ou apaga) o LaunchAgent. O launchd lê na próxima vez que a pessoa entrar na conta do Mac: não
    carregamos agora, senão ele abriria uma segunda cópia do app neste instante. No macOS 13 ou mais novo o Mac
    avisa "item de segundo plano adicionado" e mostra o app em Ajustes > Geral > Itens de início."""
    arquivo = _arquivo_agente()
    if not ligar:
        arquivo.unlink(missing_ok=True)
        return
    arquivo.parent.mkdir(parents=True, exist_ok=True)
    dados = {
        "Label": ROTULO,
        "ProgramArguments": comando_do_app("--bandeja"),
        "RunAtLoad": True,
        "ProcessType": "Interactive",
        "LimitLoadToSessionType": "Aqua",  # só quando a pessoa entra com a tela (não por SSH)
    }
    tmp = arquivo.with_name(arquivo.name + ".tmp")
    with open(tmp, "wb") as f:
        plistlib.dump(dados, f)
    os.replace(tmp, arquivo)


# --- Mac acordado ---

class PcAcordado:
    """Impede o Mac de dormir sozinho enquanto o app roda (a tela pode apagar normalmente). Usa o caffeinate, que
    vem no macOS e termina sozinho se o app fechar (-w). Notebook com a tampa fechada dorme de qualquer jeito."""

    def __init__(self):
        self.ligado = False
        self._proc = None
        self._sem_caffeinate = False
        threading.Thread(target=self._loop, name="mac-acordado", daemon=True).start()

    def _loop(self):
        while True:
            rodando = self._proc is not None and self._proc.poll() is None
            if self.ligado and not rodando and not self._sem_caffeinate:
                try:
                    self._proc = subprocess.Popen(["/usr/bin/caffeinate", "-i", "-w", str(os.getpid())],
                                                  stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                                                  stderr=subprocess.DEVNULL)
                except OSError:
                    self._proc, self._sem_caffeinate = None, True  # fora do Mac: não tem caffeinate
            elif not self.ligado and rodando:
                self._proc.terminate()
                self._proc = None
            time.sleep(2)


# --- Janela do app, links e pastas ---

NAVEGADORES = (  # o primeiro que existir (o Edge antes, como no Windows)
    "Microsoft Edge.app/Contents/MacOS/Microsoft Edge",
    "Google Chrome.app/Contents/MacOS/Google Chrome",
)


def _achar_navegador_app():
    for navegador in NAVEGADORES:
        for pasta in (Path("/Applications"), Path.home() / "Applications"):
            exe = pasta / navegador
            if exe.is_file():
                return str(exe)
    return None


def _solto():
    """Opções do Popen para um processo que segue a vida dele (sem herdar o terminal do app)."""
    return {"stdin": subprocess.DEVNULL, "stdout": subprocess.DEVNULL, "stderr": subprocess.DEVNULL,
            "start_new_session": True}


def abrir_janela(url):
    """Abre o painel numa janela própria (modo app do Edge/Chrome). Sem nenhum dos dois: no navegador padrão.
    No Mac essa janela aparece no Dock como mais um Edge (perfil separado)."""
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
            "--disable-features=Translate",
            "--lang=pt-BR",
        ],
        **_solto(),
    )


def abrir_no_navegador(url):
    """Abre no navegador padrão da pessoa (ou a pasta, no Finder)."""
    subprocess.Popen(["/usr/bin/open", url], **_solto())


# --- ID do Mac (Premium) ---

def id_da_maquina():
    """IOPlatformUUID: é da placa do Mac, não muda ao reinstalar o app nem o macOS. None se não achar.
    (Fora do Mac, só para o código abrir: o machine-id do Linux.)"""
    try:
        saida = subprocess.run(["/usr/sbin/ioreg", "-rd1", "-c", "IOPlatformExpertDevice"],
                               capture_output=True, text=True, timeout=10).stdout
    except (OSError, subprocess.SubprocessError):
        saida = ""
    m = re.search(r'"IOPlatformUUID"\s*=\s*"([0-9A-Fa-f-]{36})"', saida or "")
    if m:
        return m.group(1)
    try:
        return Path("/etc/machine-id").read_text(encoding="ascii").strip() or None
    except (OSError, ValueError):
        return None


# --- Edge/Chrome das lives da Kick ---

def eh_navegador(nome):
    """No Mac o navegador é "Microsoft Edge" e os pedaços dele "Microsoft Edge Helper (Renderer)" etc.
    (o mesmo com o Chrome)."""
    return (nome or "").lower().startswith(("microsoft edge", "google chrome"))


def amarrar_ao_app(proc):
    """O Mac não tem o "grupo que fecha junto" do Windows. Ao sair normalmente, o app já fecha os Edges; se o app
    travar, a limpeza da Kick (kick.limpar_sobras) fecha o que sobrou na próxima vez que ele abrir."""
    return False


def _janelas_de(pids):
    """Janelas normais desses processos, pela lista de janelas do Quartz (só o dono e o tamanho: não pede
    permissão de gravação da tela). Conta também as minimizadas e as que estão fora da tela."""
    try:
        import Quartz
    except ImportError:
        return []
    try:
        lista = Quartz.CGWindowListCopyWindowInfo(
            Quartz.kCGWindowListOptionAll | Quartz.kCGWindowListExcludeDesktopElements, Quartz.kCGNullWindowID) or []
        achadas = []
        for j in lista:
            if j.get(Quartz.kCGWindowOwnerPID) not in pids or j.get(Quartz.kCGWindowLayer) != 0:
                continue
            tamanho = j.get(Quartz.kCGWindowBounds) or {}
            if tamanho.get("Width", 0) >= 100 and tamanho.get("Height", 0) >= 100:  # sem as janelinhas internas
                achadas.append(j.get(Quartz.kCGWindowNumber))
        return achadas
    except Exception:
        return []


def tirar_da_barra(pids):
    """O Dock não deixa tirar o app de outro fabricante: esconde o navegador das lives (como Cmd+H). A live
    continua tocando por causa das opções do Edge (--disable-backgrounding-occluded-windows e
    MacWebContentsOcclusion desligado). A TESTAR num Mac: se a Kick parar de dar pontos escondida, tirar isto."""
    try:
        from AppKit import NSRunningApplication
    except ImportError:
        return
    for pid in pids:
        try:
            app = NSRunningApplication.runningApplicationWithProcessIdentifier_(pid)
            if app is not None and not app.isHidden():
                app.hide()
        except Exception:
            pass


def fechar_janelas(pids):
    """Pede para o navegador fechar (SIGTERM): o Edge/Chrome grava o login no disco e sai direito."""
    for pid in pids:
        try:
            os.kill(pid, signal.SIGTERM)
        except OSError:
            pass

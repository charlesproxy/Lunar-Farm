"""O que muda de um sistema para outro, num lugar só: iniciar com o sistema, PC acordado, a janela do app, abrir
links e pastas, o ID do PC e o navegador das lives da Kick.

O resto do app chama só daqui. No Windows cada função chama o winutil (o mesmo código de sempre); no Mac, o
macutil (ainda não testado num Mac de verdade: ver pesquisa/mac/PLANO-MAC.md). As funções chamam o módulo do
sistema na hora, e não guardam a função dele: o painel de teste troca o winutil.iniciar_com_windows por uma que
não faz nada, e isso continua valendo."""

import json
import os
import socket
import sys
from pathlib import Path

if sys.platform == "win32":
    SISTEMA = "windows"
elif sys.platform == "darwin":
    SISTEMA = "mac"
else:
    SISTEMA = "linux"  # não é vendido: o caminho do Mac (POSIX) só deixa o código abrir para testar
WINDOWS = SISTEMA == "windows"
MAC = SISTEMA == "mac"

if WINDOWS:
    from lunar import winutil as _so
else:
    from lunar import macutil as _so

# Processo sem janela de terminal. Fora do Windows o Python recusa qualquer creationflags diferente de 0.
SEM_JANELA = 0x08000000 if WINDOWS else 0  # CREATE_NO_WINDOW
# Recurso do navegador que "desliga" a página quando a janela está coberta ou fora da tela: as lives escondidas
# da Kick precisam dele desligado. Cada sistema tem o seu.
OCLUSAO = "CalculateNativeWinOcclusion" if WINDOWS else "MacWebContentsOcclusion"
TEXTO_SEM_NAVEGADOR = ("não achei o Microsoft Edge neste PC" if WINDOWS
                       else "não achei o Microsoft Edge nem o Google Chrome neste Mac")


# --- Iniciar com o sistema e PC acordado ---

def esta_no_iniciar():
    """O sistema vai abrir o app ao ligar (Windows: chave Run; Mac: LaunchAgent)?"""
    return _so.esta_no_iniciar()


def iniciar_com_sistema(ligar):
    if WINDOWS:
        return _so.iniciar_com_windows(ligar)
    return _so.iniciar_com_sistema(ligar)


def PcAcordado():  # noqa: N802 (era uma classe do winutil: o nome continua)
    """Impede o PC de dormir enquanto o app roda (.ligado = True/False)."""
    return _so.PcAcordado()


# --- Janela, links e pastas ---

def abrir_janela(url):
    """Abre o painel numa janela própria (modo app do Edge/Chrome), sem barra de endereço."""
    return _so.abrir_janela(url)


def abrir_no_navegador(url):
    """Abre no navegador normal da pessoa (ou a pasta, no Explorador/Finder)."""
    return _so.abrir_no_navegador(url)


def ip_na_rede():
    """IP do PC no Wi-Fi/cabo de casa (para o celular abrir o painel)."""
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("10.255.255.255", 1))  # não envia nada; só escolhe a placa de rede
        return s.getsockname()[0]
    except OSError:
        return "127.0.0.1"
    finally:
        s.close()


def _arquivos_do_chatterino():
    if WINDOWS:
        return [Path(os.environ.get("APPDATA", "")) / "Chatterino2" / "Settings" / "window-layout.json"]
    suporte = Path.home() / "Library" / "Application Support"  # no Mac (a confirmar num Mac de verdade)
    return [suporte / nome / "Settings" / "window-layout.json" for nome in ("chatterino", "Chatterino2")]


def canais_do_chatterino():
    """Lê as abas do Chatterino (window-layout.json) e devolve os canais da Twitch (None: não achou)."""
    for arquivo in _arquivos_do_chatterino():
        try:
            dados = json.loads(arquivo.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        canais = []

        def procurar(no):
            if isinstance(no, dict):
                if no.get("type") == "twitch" and isinstance(no.get("name"), str):
                    nome = no["name"].strip().lower()
                    if nome and nome not in canais:
                        canais.append(nome)
                for valor in no.values():
                    procurar(valor)
            elif isinstance(no, list):
                for valor in no:
                    procurar(valor)

        procurar(dados)
        return canais
    return None


# --- ID do PC (Premium) ---

def id_da_maquina():
    """Identidade do computador, como o sistema guarda (None se não achou). Windows: MachineGuid (muda ao
    formatar); Mac: IOPlatformUUID (é da placa: nem reinstalar o macOS muda)."""
    return _so.id_da_maquina()


# --- Navegador das lives da Kick ---

def achar_navegador():
    """Caminho do Edge (ou do Chrome) deste PC, ou None."""
    return _so._achar_navegador_app()


def eh_navegador(nome):
    """O nome do processo é do Edge/Chrome (o navegador ou um pedaço dele)?"""
    return _so.eh_navegador(nome)


def amarrar_ao_app(proc):
    """Faz o navegador fechar junto com o app, mesmo se o app travar (só o Windows sabe fazer isso)."""
    return _so.amarrar_ao_app(proc)


def janelas_de(pids):
    """Janelas abertas desses processos (para saber se a pessoa fechou a janela de login)."""
    return _so._janelas_de(pids)


def tirar_da_barra(pids):
    """Tira o navegador das lives da barra de tarefas (no Mac: esconde, porque o Dock não deixa tirar)."""
    return _so.tirar_da_barra(pids)


def fechar_janelas(pids):
    """Fecha o navegador como se a pessoa clicasse no X (ele grava o login antes de sair)."""
    return _so.fechar_janelas(pids)

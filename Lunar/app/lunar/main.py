"""Abre o Lunar Farm: painel, motores das contas, ícone na bandeja e a janela."""

import argparse
import logging
import logging.handlers
import os
import sys
import threading
import time

import pystray
import requests
from PIL import Image
from waitress import create_server

from lunar import NOME, NOMES_ANTIGOS, VERSAO, novidades, paths, plataforma
from lunar.atualizador import Atualizador
from lunar.config import Config
from lunar.config import ler as config_lido
from lunar.db import Historico
from lunar.manager import Gerente
from lunar.premium import Premium
from lunar.suporte import Suporte
from lunar.uso import Uso
from lunar.web import criar_app

URL = f"http://127.0.0.1:{paths.PORTA}/"
log = logging.getLogger("lunar")


def ja_aberto():
    try:
        return requests.get(URL + "api/ping", timeout=2).json().get("app") in (NOME, *NOMES_ANTIGOS)
    except (requests.exceptions.RequestException, ValueError):
        return False


class Controle:
    """O que o painel e a bandeja podem pedir para o app fazer."""

    def __init__(self, gerente):
        self.gerente = gerente
        self.acordado = plataforma.PcAcordado()
        self.atualizador = Atualizador()
        self.app = None
        self.icone = None
        self.servidor_celular = None
        self.janela_em = 0  # última vez que a janela do PC perguntou o estado (ela pergunta de 3 em 3 s)

    def aplicar_opcoes(self, opcoes):
        self.acordado.ligado = bool(opcoes.get("keep_awake"))
        if paths.EMPACOTADO:
            return  # pela Store, quem abre com o Windows é a tarefa do pacote (veja --inicio)
        try:
            plataforma.iniciar_com_sistema(bool(opcoes.get("start_with_windows")))
        except OSError:
            log.exception("não deu para mudar o iniciar com o Windows")

    def aplicar_celular(self, ligado):
        if ligado and self.servidor_celular is None:
            try:
                servidor = create_server(self.app, host="0.0.0.0", port=paths.PORTA_CELULAR, threads=4)
            except OSError:
                log.exception("não deu para abrir o painel no Wi-Fi")
                return
            self.servidor_celular = servidor
            threading.Thread(target=servidor.run, daemon=True).start()
        elif not ligado and self.servidor_celular is not None:
            self.servidor_celular.close()
            self.servidor_celular = None

    def sair_depois(self, origem):
        threading.Thread(target=self.sair, args=(origem,), daemon=True).start()

    def sair(self, origem):
        log.info("saindo e parando o farm (pedido: %s)", origem)
        time.sleep(0.3)
        self.gerente.parar_tudo()
        if self.icone is not None:
            self.icone.stop()
        os._exit(0)


LIMITE_DICA = 127  # o Windows não aceita dica do ícone com mais de 127 letras

SITUACAO = {
    "iniciando": "ligando",
    "precisa_entrar": "precisa entrar",
    "pausada": "pausada",
    "sem_canais": "sem canais",
    "erro": "com erro",
    "parada": "parada",
    "bloqueada": "precisa do Premium",
}


def texto_da_dica(contas):
    """Uma linha por conta com os pontos de hoje e, no fim, se está farmando."""
    if not contas:
        return f"{NOME}\nNenhuma conta ainda"
    itens = []
    farmando = 0
    for c in contas:
        # Com canal ao vivo já conta: logo depois de ligar ele ainda está escolhendo as 2 lives.
        if c["estado"] == "farmando" and (c["assistindo"] or c["ao_vivo"]):
            farmando += 1
            obs = ""
        elif c["estado"] == "farmando":
            obs = "sem live"  # está no chat, mas nenhum canal da lista está ao vivo
        else:
            obs = SITUACAO.get(c["estado"], c["estado"])
        itens.append((c["login"], f"{c['hoje']:,}".replace(",", "."), obs))
    if farmando == len(contas):
        fim = "Farmando"
    elif farmando:
        fim = f"Farmando {farmando} de {len(contas)}"
    else:
        fim = "Não farmando"
        situacoes = {obs for _, _, obs in itens}
        if len(situacoes) == 1:
            # Todas iguais (ex.: o app acabou de ligar): diz uma vez só, no fim.
            unica = situacoes.pop()
            itens = [(login, pts, "") for login, pts, _ in itens]
            fim = "Ligando o farm…" if unica == "ligando" else f"Não farmando ({unica})"
    # Do mais completo para o mais curto até caber no limite do Windows.
    # A última linha (se está farmando) nunca é cortada.
    for tam_nome, sufixo, com_obs in ((25, " pontos", True), (25, "", True), (12, "", True), (12, "", False), (8, "", False)):
        linhas = [f"{login[:tam_nome]}: {pts}{sufixo}" + (f" ({obs})" if obs and com_obs else "") for login, pts, obs in itens]
        texto = "\n".join(["Hoje:", *linhas, fim])
        if len(texto) <= LIMITE_DICA:
            return texto
    while linhas and len("\n".join(["Hoje:", *linhas, "…", fim])) > LIMITE_DICA:
        linhas.pop()  # conta demais: mostra as que cabem
    return "\n".join(["Hoje:", *linhas, "…", fim])


def atualizar_dica(controle, gerente):
    while True:
        try:
            texto = texto_da_dica(gerente.estado()["contas"])
            if controle.icone is not None and controle.icone.title != texto:
                controle.icone.title = texto
        except Exception:
            log.debug("dica da bandeja", exc_info=True)
        time.sleep(10)


ESPERA_JANELA = 12  # segundos para a janela que ficou aberta durante a atualização se reconectar


def mostrar_depois_de_atualizar(controle):
    """A janela que estava aberta durante a atualização se reconecta sozinha e mostra as
    novidades. Se nenhuma aparecer (ela foi fechada), abre uma nova."""
    time.sleep(ESPERA_JANELA)
    if time.time() - controle.janela_em > ESPERA_JANELA:
        log.info("depois de atualizar: nenhuma janela voltou, abrindo uma")
        plataforma.abrir_janela(URL)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--bandeja", action="store_true", help="liga sem abrir a janela (iniciar com o Windows)")
    parser.add_argument("--atualizado", action="store_true",
                        help="o instalador acabou de atualizar: garante a janela aberta, com as novidades")
    parser.add_argument("--inicio", action="store_true",
                        help="aberto pela tarefa de inicialização da Store: só liga se a opção estiver ativada")
    args = parser.parse_args()
    if args.inicio:
        args.bandeja = True
        if not config_lido()["settings"].get("start_with_windows"):
            return

    if ja_aberto():
        if not args.bandeja:
            plataforma.abrir_janela(URL)
        return

    migrou = paths.migrar_dados_antigos()
    paths.garantir_pastas()
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        handlers=[logging.handlers.RotatingFileHandler(paths.LOG_DIR / "app.log", maxBytes=2_000_000, backupCount=2, encoding="utf-8")],
    )

    # Com pythonw não há console: travamento que não for anotado aqui some sem deixar rastro.
    sys.excepthook = lambda tipo, valor, rastro: log.critical("o app travou", exc_info=(tipo, valor, rastro))
    threading.excepthook = lambda a: log.critical(
        "erro na parte %s do app", getattr(a.thread, "name", "?"), exc_info=(a.exc_type, a.exc_value, a.exc_traceback))
    log.info("%s %s abrindo%s%s", NOME, VERSAO, " (escondido na bandeja)" if args.bandeja else "",
             " depois de atualizar" if args.atualizado else "")
    if migrou:
        log.info("dados de %s levados para %s", migrou, paths.DATA_DIR)
    cfg = Config()
    novidades.preparar(cfg)
    hist = Historico(paths.DB_FILE)
    premium = Premium()
    gerente = Gerente(cfg, hist, premium)
    premium.ao_mudar = gerente.premium_mudou
    controle = Controle(gerente)
    controle.premium = premium
    controle.suporte = Suporte(premium, cfg)
    controle.uso = Uso(premium, cfg)
    controle.app = criar_app(gerente, cfg, hist, controle)

    try:
        servidor = create_server(controle.app, host="127.0.0.1", port=paths.PORTA, threads=8)
    except OSError:
        # Outra cópia está abrindo neste instante: só mostra a janela dela.
        if not args.bandeja:
            time.sleep(2)
            plataforma.abrir_janela(URL)
        return
    threading.Thread(target=servidor.run, daemon=True).start()

    # O instalador pode ter marcado "Iniciar com o Windows": o que está no Windows manda
    # (e o app regrava o caminho certo, caso a pasta do programa tenha mudado).
    if not paths.EMPACOTADO and plataforma.esta_no_iniciar() != bool(cfg.opcoes().get("start_with_windows")):
        cfg.mudar_opcoes(start_with_windows=plataforma.esta_no_iniciar())
    opcoes = cfg.opcoes()
    controle.aplicar_opcoes(opcoes)
    if opcoes.get("lan_enabled"):
        controle.aplicar_celular(True)
    gerente.iniciar_tudo()
    if not args.bandeja:
        plataforma.abrir_janela(URL)
    elif args.atualizado:
        threading.Thread(target=mostrar_depois_de_atualizar, args=(controle,), daemon=True).start()

    icone = pystray.Icon(
        NOME,
        Image.open(paths.STATIC_DIR / "icon-bandeja.png"),
        NOME,
        pystray.Menu(
            pystray.MenuItem(f"Abrir o {NOME}", lambda: plataforma.abrir_janela(URL), default=True),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Sair (para o farm)", lambda: controle.sair("menu do ícone da bandeja")),
        ),
    )
    controle.icone = icone
    controle.suporte.ao_responder = lambda ticket: icone.notify(
        f"O suporte respondeu o seu ticket {ticket}. Abra o {NOME} em Ajuda e suporte.", NOME)
    controle.atualizador.ao_achar = lambda nova: icone.notify(
        f"Saiu a versão {nova['versao']}. Abra o {NOME} e clique em Atualizar.", NOME)
    threading.Thread(target=atualizar_dica, args=(controle, gerente), daemon=True).start()
    icone.run()
    log.info("o ícone da bandeja fechou: o app vai sair")


if __name__ == "__main__":
    main()

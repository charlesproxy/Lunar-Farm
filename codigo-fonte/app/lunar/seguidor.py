"""Segue sozinho os canais da lista de cada conta: a Twitch dá 300 pontos na
primeira vez que a conta segue um canal (o +300 entra no histórico pelo motor).
Na versão grátis, segue até 3 canais (e só na conta liberada); no Lunar Premium, todos."""

import logging
import threading
import time

from lunar import twitch

log = logging.getLogger("lunar")

INTERVALO = 4  # segundos entre um canal e outro, sem pressa
TENTAR_DE_NOVO = 3600  # canal que deu erro: tenta de novo depois de 1 hora


class Seguidor:
    def __init__(self, cfg, hist, limites=None, liberada=None):
        self.cfg = cfg
        self.hist = hist
        self.limites = limites or (lambda: {"seguir": None})
        self.liberada = liberada or (lambda login: True)
        self.acordar = threading.Event()
        threading.Thread(target=self._rodar, daemon=True).start()

    def avisar(self):
        """A lista de alguma conta mudou: confere já."""
        self.acordar.set()

    def _rodar(self):
        self.acordar.wait(30)  # deixa os motores ligarem primeiro
        while True:
            self.acordar.clear()
            try:
                self._uma_volta()
            except Exception:
                log.exception("erro seguindo canais")
            self.acordar.wait(TENTAR_DE_NOVO)

    def _ligado(self):
        return bool(self.cfg.opcoes().get("auto_follow"))

    def _uma_volta(self):
        for conta in self.cfg.contas():
            login = conta["login"]
            if not self.liberada(login):
                continue
            feitos = self.hist.seguidos(login)
            seguidos = sum(1 for ok, _ in feitos.values() if ok)
            for canal in conta.get("channels", []):
                limite = self.limites()["seguir"]
                if limite is not None and seguidos >= limite:
                    break  # versão grátis: o resto fica para o Premium
                ok, quando = feitos.get(canal, (False, 0))
                if ok or time.time() - quando < TENTAR_DE_NOVO:
                    continue
                if not self._ligado() or self.cfg.conta(login) is None:
                    break
                try:
                    twitch.cliente(login).seguir(canal)
                except twitch.SemLogin:
                    break  # o app já pede o login de novo; segue depois
                except twitch.ErroTwitch as e:
                    if not quando:  # avisa no histórico só na primeira falha
                        self.hist.evento(login, canal, "erro", f"Não deu para seguir {canal}: {e}")
                    self.hist.marcar_seguido(login, canal, False)
                    log.warning("%s não conseguiu seguir %s: %s", login, canal, e)
                else:
                    self.hist.marcar_seguido(login, canal, True)
                    seguidos += 1
                    log.info("%s seguiu %s", login, canal)
                time.sleep(INTERVALO)

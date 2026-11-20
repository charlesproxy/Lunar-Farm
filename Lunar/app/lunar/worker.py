"""Motor de UMA conta: roda o minerador e conta tudo para o app pelo stdout.

Uso (o app chama sozinho): python -m lunar.worker <login>

Cada linha escrita no stdout é um JSON com "t" (tipo):
  status  -> canais com ao vivo/pontos e quais 2 estão sendo assistidos
  gain    -> pontos ganhos (motivo: WATCH, CLAIM, WATCH_STREAK, RAID...)
  spent   -> pontos gastos na loja de um canal
  online / offline / raid -> acontecimentos para o histórico
  login_needed -> o login salvo não vale mais; o app pede um código novo
  error   -> mensagem de erro do minerador
"""

import json
import logging
import os
import sys
import threading
import time

import psutil

from lunar import config, paths

_saida = sys.stdout
_trava = threading.Lock()


def avisar(tipo, **dados):
    dados["t"] = tipo
    linha = json.dumps(dados, ensure_ascii=True)
    with _trava:
        try:
            _saida.write(linha + "\n")
            _saida.flush()
        except (OSError, ValueError):
            os._exit(0)  # o app fechou o cano: não tem mais para quem farmar


class Observador:
    """Ocupa o lugar do painel do minerador para receber os eventos dele."""

    settings = None

    def __init__(self):
        self.stopping = threading.Event()
        self.assistindo = []
        self.mudou = threading.Event()  # acorda o relatório na hora em que a escolha das lives muda
        self.favoritos = set()  # canais com estrela (sempre entram quando estão ao vivo)
        self.bau_na_largada = {}  # canal -> saldo de antes do baú aberto enquanto o motor carregava

    def event(self, kind, **details):
        if kind == "watch_selection":
            novos = [c.get("channel") for c in details.get("channels", [])]
            if novos != self.assistindo:
                self.assistindo = novos
                self.mudou.set()

    def live_message(self, message, streamer):
        if streamer is None:
            return
        try:
            if message.topic == "community-points-user-v1" and message.type == "points-earned":
                ganho = message.data["point_gain"]
                pontos = int(ganho.get("total_points") or 0)
                saldo = int(message.data["balance"]["balance"])
                antes = self.bau_na_largada.pop(streamer.username, None)
                if antes is not None and 0 < saldo - pontos - antes <= 5000:
                    # O saldo deste aviso já inclui o baú da largada: a diferença é o que ele deu.
                    avisar("gain", channel=streamer.username, points=saldo - pontos - antes,
                           reason="CLAIM", balance=saldo - pontos)
                avisar(
                    "gain",
                    channel=streamer.username,
                    points=pontos,
                    reason=str(ganho.get("reason_code") or ""),
                    balance=saldo,
                )
            elif message.topic == "community-points-user-v1" and message.type == "points-spent":
                # Compra na loja do canal (pelo app ou pelo chat da Twitch). O aviso só traz o
                # saldo novo; o minerador ainda não trocou o antigo, então a diferença é o gasto.
                saldo = int(message.data["balance"]["balance"])
                antes = int(streamer.channel_points or 0)
                logging.getLogger("lunar").info(
                    "pontos gastos em %s: saldo %s -> %s (%s)", streamer.username, antes, saldo,
                    json.dumps(message.data, ensure_ascii=True)[:300],
                )
                if 0 < antes - saldo <= 10_000_000:
                    avisar("spent", channel=streamer.username, points=antes - saldo, balance=saldo)
            elif message.topic == "raid" and message.type == "raid_update_v2":
                avisar("raid", channel=streamer.username, target=message.message["raid"]["target_login"])
        except (KeyError, TypeError, ValueError):
            pass

    def stop(self):
        pass


class AvisoDeLog(logging.Handler):
    """Pega no log do minerador o que interessa ao app."""

    def emit(self, record):
        try:
            texto = record.getMessage()
        except Exception:
            return
        if "twitch.tv/activate" in texto:
            # O login salvo expirou e o minerador quer um código pelo terminal.
            # Aqui não tem terminal: o app cuida do login e reabre este motor.
            avisar("login_needed")
            os._exit(3)
        if record.levelno >= logging.ERROR:
            avisar("error", msg=texto[:300])


def info_canal(streamer):
    stream = getattr(streamer, "stream", None)
    jogo = None
    try:
        jogo = stream.game_name() if stream is not None else None
    except Exception:
        pass
    return {
        "login": streamer.username,
        "online": bool(streamer.is_online),
        "points": int(streamer.channel_points or 0),
        "game": jogo,
        "title": getattr(stream, "title", None) if streamer.is_online else None,
        "viewers": getattr(stream, "viewers_count", 0) if streamer.is_online else 0,
    }


def contar_bau_da_largada(miner, obs):
    """O baú que o minerador abre enquanto carrega os canais não gera aviso da Twitch
    (a conexão de avisos só sobe depois). Guarda o saldo de antes para contar esse ganho."""
    # A classe Twitch usa __slots__: troca na classe (cada motor tem um processo e um Twitch só).
    classe = type(miner.twitch)
    original = classe.claim_bonus

    def claim_bonus(self, streamer, claim_id):
        if miner.ws_pool is None:
            obs.bau_na_largada.setdefault(streamer.username, int(streamer.channel_points or 0))
        return original(self, streamer, claim_id)

    classe.claim_bonus = claim_bonus


def acelerar_largada(miner):
    """O minerador só escolhe uma live 30 s depois de ela entrar no ar (para live que acabou
    de abrir). Live que já estava no ar quando o motor ligou não precisa esperar: entra na
    primeira rodada, e "Ganhando pontos agora" aparece logo depois de carregar."""
    from TwitchChannelPointsMiner.classes.entities.Streamer import Streamer

    original = Streamer.set_online

    def set_online(self):
        estava = self.is_online
        original(self)
        if not estava and self.is_online and miner.minute_watcher_thread is None:
            self.online_at -= 31

    Streamer.set_online = set_online


# Como escolher as outras lives (depois das com estrela): "lista" = as primeiras da lista;
# "pontos" = onde a conta já tem mais pontos. Nomes do Priority do minerador.
PRIORIDADES = {
    "lista": ("STREAK", "DROPS", "ORDER"),
    "pontos": ("STREAK", "DROPS", "POINTS_DESCENDING", "ORDER"),
}


def prioridades(modo):
    from TwitchChannelPointsMiner.classes.Settings import Priority

    return [Priority[nome] for nome in PRIORIDADES.get(modo, PRIORIDADES["lista"])]


def favoritos_primeiro(miner, obs):
    """Canal com estrela entra numa das 2 vagas sempre que está ao vivo, na frente até da
    tentativa de sequência de lives. A vaga que sobra segue a escolha normal do minerador."""
    classe = type(miner.twitch)
    original = classe._select_streamers_to_watch

    def escolher(self, streamers, streamers_index, priority):
        escolha = original(self, streamers, streamers_index, priority)
        favoritos = [
            i for i in streamers_index
            if streamers[i].username in obs.favoritos
            and getattr(streamers[i], "channel_points_enabled", True)
            and not getattr(streamers[i], "chat_banned", False)
        ][: self.max_watch_amount]
        if not favoritos:
            return escolha
        return (favoritos + [i for i in escolha if i not in favoritos])[: self.max_watch_amount]

    classe._select_streamers_to_watch = escolher


def vigiar_preferencias(miner, obs, login):
    """Relê do config as estrelas e o jeito de escolher as lives a cada 10 s: mudar isso no
    app vale na hora, sem reiniciar o motor."""
    while True:
        time.sleep(10)
        try:
            conta = next((a for a in config.ler()["accounts"] if a["login"] == login), None) or {}
            obs.favoritos = set(conta.get("favoritos") or [])
            nova = prioridades(conta.get("ordem"))
            if miner.priority != nova:
                miner.priority[:] = nova  # a mesma lista que o minerador usa em cada rodada
        except Exception:
            pass


def conferir_saldos(miner):
    """A Twitch não avisa quando os pontos são gastos na loja de recompensas (nem pelo app,
    nem pelo chat). De 5 em 5 minutos o motor pergunta o saldo de cada canal: se caiu, foi
    compra, e entra no Gasto."""
    while True:
        time.sleep(300)
        if miner.minute_watcher_thread is None:
            continue
        for streamer in list(miner.streamers):
            antes = int(streamer.channel_points or 0)
            try:
                miner.twitch.load_channel_points_context(streamer)
            except Exception:
                continue
            depois = int(streamer.channel_points or 0)
            if 0 < antes - depois <= 10_000_000:
                avisar("spent", channel=streamer.username, points=antes - depois, balance=depois)
            # Saldo recém-conferido na Twitch: o app troca o que estava mostrando por este.
            avisar("saldo", channel=streamer.username, balance=depois)
            time.sleep(2)


def relatar_status(miner, obs):
    antes = {}
    while True:
        obs.mudou.wait(10)
        obs.mudou.clear()
        if miner.minute_watcher_thread is None:
            continue  # ainda carregando: todo canal aparece offline até terminar
        canais = []
        for streamer in list(getattr(miner, "streamers", None) or []):
            try:
                info = info_canal(streamer)
            except Exception:
                continue
            canais.append(info)
            anterior = antes.get(info["login"])
            if anterior is not None and anterior != info["online"]:
                avisar("online" if info["online"] else "offline", channel=info["login"], game=info["game"])
            antes[info["login"]] = info["online"]
        ao_vivo = {c["login"] for c in canais if c["online"]}
        avisar("status", channels=canais, watching=[c for c in obs.assistindo if c in ao_vivo])


def medir_cpu():
    """Diagnóstico leve: de 5 em 5 min, se uma thread deste motor gastar mais de 15% de um núcleo, anota no log do
    minerador qual é e onde ela passa o tempo (amostra a pilha dela 40 vezes em 4 s)."""
    import collections
    import traceback
    log = logging.getLogger("lunar.cpu")
    eu = psutil.Process()
    antes = {t.id: t.user_time + t.system_time for t in eu.threads()}
    while True:
        time.sleep(300)
        try:
            agora = {t.id: t.user_time + t.system_time for t in eu.threads()}
            uso = {i: (agora[i] - antes.get(i, 0)) / 300 for i in agora}
            antes = agora
            por_id = {t.native_id: t for t in threading.enumerate()}
            for nid, fracao in sorted(uso.items(), key=lambda x: -x[1])[:2]:
                t = por_id.get(nid)
                if fracao < 0.15 or t is None:
                    continue
                contagem = collections.Counter()
                for _ in range(40):
                    quadro = sys._current_frames().get(t.ident)
                    if quadro is not None:
                        pilha = traceback.extract_stack(quadro)[-3:]
                        contagem[" < ".join(f"{os.path.basename(q.filename)}:{q.lineno} {q.name}" for q in reversed(pilha))] += 1
                    time.sleep(0.1)
                log.warning("CPU: thread %r usa %.0f%% de um núcleo; onde: %s", t.name, fracao * 100,
                            " || ".join(f"{n}x {onde}" for onde, n in contagem.most_common(3)))
        except Exception:
            log.debug("medir_cpu", exc_info=True)


def vigiar_app():
    """Se o app fechar de qualquer jeito, este motor fecha junto."""
    pai = os.getppid()
    while True:
        time.sleep(5)
        if not psutil.pid_exists(pai):
            os._exit(0)


def simular(canais, login, lives=2):
    """Só para testar a interface (LUNAR_SIMULAR=1): finge um farm, sem Twitch.
    Respeita as estrelas e a ordem (lista ou mais pontos) como o motor de verdade."""
    import random

    saldos = {c: random.randint(500, 50000) for c in canais}
    ao_vivo = set(random.sample(canais, k=min(len(canais), 5)))
    avisar("started")
    while True:
        if random.random() < 0.15 and canais:
            canal = random.choice(canais)
            ao_vivo ^= {canal}
            avisar("online" if canal in ao_vivo else "offline", channel=canal, game="Tibia")
        conta = next((a for a in config.ler()["accounts"] if a["login"] == login), None) or {}
        favoritos = [c for c in canais if c in ao_vivo and c in (conta.get("favoritos") or [])]
        resto = [c for c in canais if c in ao_vivo and c not in favoritos]
        if conta.get("ordem") == "pontos":
            resto.sort(key=lambda c: -saldos[c])
        assistindo = (favoritos + resto)[:lives]
        for canal in assistindo:
            motivo, pontos = random.choice([("WATCH", 10), ("WATCH", 10), ("CLAIM", 50)])
            saldos[canal] += pontos
            avisar("gain", channel=canal, points=pontos, reason=motivo, balance=saldos[canal])
        avisar("status", watching=assistindo, channels=[
            {"login": c, "online": c in ao_vivo, "points": saldos[c], "game": "Tibia" if c in ao_vivo else None,
             "title": None, "viewers": random.randint(50, 3000) if c in ao_vivo else 0}
            for c in canais
        ])
        time.sleep(6)


def main():
    login = sys.argv[1].strip().lower()
    # Quantas lives por vez: 2 no Lunar Premium, 1 na versão grátis (o app manda).
    lives = int(sys.argv[sys.argv.index("--lives") + 1]) if "--lives" in sys.argv else 2
    cfg = config.ler()
    conta = next((a for a in cfg["accounts"] if a["login"] == login), None)
    canais = list(conta.get("channels", [])) if conta else []
    if not canais:
        avisar("error", msg="Essa conta ainda não tem canais.")
        sys.exit(2)
    if os.environ.get("LUNAR_SIMULAR"):
        threading.Thread(target=vigiar_app, daemon=True).start()
        simular(canais, login, lives)

    paths.garantir_pastas()
    os.chdir(paths.MINER_DIR)  # o minerador grava cookies/ e logs/ na pasta atual
    if not paths.cookie_file(login).is_file():
        avisar("login_needed")
        sys.exit(3)

    # O console do minerador vai para o nada; o stdout é só do app.
    sys.stdout = open(os.devnull, "w", encoding="utf-8")
    threading.Thread(target=vigiar_app, daemon=True).start()

    from TwitchChannelPointsMiner import TwitchChannelPointsMiner
    from TwitchChannelPointsMiner.classes.Chat import ChatPresence
    from TwitchChannelPointsMiner.classes.entities.Streamer import (
        PlaybackSimulationMode,
        StreamerSettings,
    )
    from TwitchChannelPointsMiner.logger import LoggerSettings

    chat = ChatPresence.ONLINE if cfg["settings"].get("chat_mode") == "ao_vivo" else ChatPresence.ALWAYS
    miner = TwitchChannelPointsMiner(
        username=login,
        password=None,
        claim_drops_startup=False,
        priority=prioridades(conta.get("ordem")),
        enable_analytics=False,
        use_hermes=True,
        daily_reports=False,
        watch_streak_max_parallel=lives,
        logger_settings=LoggerSettings(
            save=True,
            console_level=logging.CRITICAL,
            file_level=logging.INFO,
            auto_clear=True,
            colored=False,
        ),
        streamer_settings=StreamerSettings(
            make_predictions=False,  # nunca aposta pontos sozinho
            follow_raid=True,
            claim_drops=True,
            claim_moments=True,
            watch_streak=True,
            points_limit=None,
            community_goals=False,
            playback_simulation=PlaybackSimulationMode.ALWAYS,
            chat=chat,
        ),
    )
    miner.twitch.max_watch_amount = lives
    logging.getLogger().addHandler(AvisoDeLog(level=logging.INFO))
    obs = Observador()
    miner.dashboard_service = miner.twitch.dashboard_service = obs
    obs.favoritos = set(conta.get("favoritos") or [])
    contar_bau_da_largada(miner, obs)
    acelerar_largada(miner)
    favoritos_primeiro(miner, obs)
    threading.Thread(target=relatar_status, args=(miner, obs), daemon=True).start()
    threading.Thread(target=vigiar_preferencias, args=(miner, obs, login), daemon=True).start()
    threading.Thread(target=conferir_saldos, args=(miner,), daemon=True).start()
    threading.Thread(target=medir_cpu, name="medir-cpu", daemon=True).start()

    avisar("started")
    miner.mine(canais, followers=False)


if __name__ == "__main__":
    main()

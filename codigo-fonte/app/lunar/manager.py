"""Liga um motor (processo escondido) por conta, ouve o que cada um conta e
guarda no histórico. Também cuida do login com código do twitch.tv/activate."""

import collections
import json
import logging
import os
import pickle
import secrets
import string
import subprocess
import threading
import time

import requests

from lunar import kick, paths, plataforma, premium, twitch
from lunar.seguidor import Seguidor

log = logging.getLogger("lunar")

SEM_JANELA = plataforma.SEM_JANELA  # CREATE_NO_WINDOW no Windows (0 nos outros sistemas)

# Mesmo login de TV que o minerador usa (twitch.tv/activate).
CLIENT_ID = "ue6666qo983tsx6so1t0vnawi233wa"
ESCOPOS = "channel_read chat:read user_blocks_edit user_blocks_read user_follows_edit user_read"
UA_TV = "Mozilla/5.0 (Linux; Android 7.1; Smart Box C1) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/108.0.0.0 Safari/537.36"

# Saldo corrigido depois de uma compra vale até o motor conferir na Twitch (de 5 em 5 min ele
# manda "saldo" de cada canal; um ganho também traz o saldo certo). Os 30 min são só segurança.
AJUSTE_VALE = 1800
AJUSTE_NOVO = 15  # "saldo" que chega logo depois da compra pode ter sido lido antes dela
AUTO_ENTRE = 3  # segundos entre uma compra automática e a próxima (compra até os pontos acabarem)
AUTO_CONFERIR = (120, 600)  # confere na Twitch 2 e 10 min depois se o jogo devolveu os pontos
# Recusas que não se resolvem sozinhas: pausa a compra automática e mostra o motivo.
# A recompensa sumir da loja ou ser desligada NÃO pausa: muitos streamers desligam fora da live ou trocam a
# recompensa; a compra espera e tenta de novo (AUTO_ESPERA).
AUTO_PAUSA = ("PRECO_MUDOU", "PEDE_TEXTO", "USER_BANNED", "FORBIDDEN")
# Limites da live: espera o canal abrir a próxima live (ou 3 h, se a live nova passar batido).
AUTO_PROXIMA_LIVE = {
    "MAX_PER_USER_PER_STREAM": "Limite do streamer: essa conta já comprou o máximo permitido nessa live. Volta a comprar na próxima live.",
    "MAX_PER_STREAM": "A recompensa chegou no limite dessa live. Volta a comprar na próxima live.",
    "STREAM_NOT_LIVE": "Esse canal só vende essa recompensa com a live no ar. Compra quando ele abrir live.",
}
AUTO_ESPERA = {"NOT_ENOUGH_POINTS": 300, "GLOBAL_COOLDOWN": 300, "PAUSED": 900,
               **{codigo: 3 * 3600 for codigo in AUTO_PROXIMA_LIVE}}  # o resto espera 30 min
AUTO_AVISO = {
    "NOT_FOUND": "A recompensa não está na loja do canal agora (o streamer desligou ou trocou). Tenta de novo a cada 30 min.",
    "DISABLED": "O streamer desligou essa recompensa por enquanto. Tenta de novo a cada 30 min.",
}

MOTIVOS = {
    "WATCH": "assistindo",
    "CLAIM": "baú de bônus",
    "WATCH_STREAK": "sequência de lives",
    "RAID": "raid",
    "FOLLOW": "seguiu o canal",
    "PREDICTION": "previsão",
    "REFUND": "previsão devolvida",
}


def validar_token(token):
    """Diz de qual conta é o token: (login, user_id) ou None."""
    try:
        r = requests.get(
            "https://id.twitch.tv/oauth2/validate",
            headers={"Authorization": f"OAuth {token}"},
            timeout=20,
        )
    except requests.exceptions.RequestException:
        return None
    if r.status_code != 200:
        return None
    dados = r.json()
    return (dados.get("login") or "").lower(), str(dados.get("user_id") or "")


class LoginTwitch:
    """Login por código: o app mostra o código, a pessoa confirma no navegador."""

    def __init__(self, ao_entrar):
        self.ao_entrar = ao_entrar
        self.lock = threading.Lock()
        self.estado = {"fase": "parado"}
        self._id = 0

    def iniciar(self):
        device_id = "".join(secrets.choice(string.ascii_letters + string.digits) for _ in range(32))
        sessao = requests.Session()
        sessao.headers.update({
            "Accept": "application/json",
            "Client-Id": CLIENT_ID,
            "Origin": "https://android.tv.twitch.tv",
            "Referer": "https://android.tv.twitch.tv/",
            "User-Agent": UA_TV,
            "X-Device-Id": device_id,
        })
        try:
            r = sessao.post(
                "https://id.twitch.tv/oauth2/device",
                data={"client_id": CLIENT_ID, "scopes": ESCOPOS},
                timeout=20,
            )
            dados = r.json()
        except (requests.exceptions.RequestException, ValueError) as e:
            return self._mudar({"fase": "erro", "erro": f"Sem resposta da Twitch ({e.__class__.__name__})"})
        if r.status_code != 200 or "user_code" not in dados:
            return self._mudar({"fase": "erro", "erro": f"A Twitch recusou o pedido de código (HTTP {r.status_code})"})

        with self.lock:
            self._id += 1
            meu_id = self._id
            self.estado = {
                "fase": "esperando",
                "codigo": dados["user_code"],
                "link": f"https://www.twitch.tv/activate?device-code={dados['user_code']}",
                "expira_em": time.time() + float(dados.get("expires_in", 1800)),
            }
        threading.Thread(
            target=self._esperar,
            args=(meu_id, sessao, dados["device_code"], float(dados.get("interval", 5))),
            daemon=True,
        ).start()
        return self.ver()

    def _esperar(self, meu_id, sessao, device_code, intervalo):
        while True:
            time.sleep(intervalo)
            with self.lock:
                if self._id != meu_id or self.estado.get("fase") != "esperando":
                    return
                if time.time() >= self.estado["expira_em"]:
                    self.estado = {"fase": "expirou"}
                    return
            try:
                r = sessao.post(
                    "https://id.twitch.tv/oauth2/token",
                    data={
                        "client_id": CLIENT_ID,
                        "device_code": device_code,
                        "grant_type": "urn:ietf:params:oauth:grant-type:device_code",
                    },
                    timeout=20,
                )
                dados = r.json()
            except (requests.exceptions.RequestException, ValueError):
                continue
            if r.status_code != 200 or not dados.get("access_token"):
                continue  # ainda não confirmou no navegador
            token = dados["access_token"]
            quem = validar_token(token)
            if not quem or not quem[0]:
                self._mudar({"fase": "erro", "erro": "A Twitch liberou, mas não disse qual é a conta. Tente de novo."}, meu_id)
                return
            login, user_id = quem
            paths.garantir_pastas()
            with open(paths.cookie_file(login), "wb") as f:
                # Mesmo formato que o minerador salva (cookies/<conta>.pkl).
                pickle.dump([{"name": "auth-token", "value": token}, {"name": "persistent", "value": user_id}], f)
            if self.ao_entrar(login, user_id) is False:
                # Versão grátis já com 1 conta: a nova só entra com o Lunar Premium.
                self._mudar({"fase": "premium", "login": login}, meu_id)
            else:
                self._mudar({"fase": "pronto", "login": login}, meu_id)
            return

    def _mudar(self, estado, meu_id=None):
        with self.lock:
            if meu_id is None or meu_id == self._id:
                self.estado = estado
        return self.ver()

    def cancelar(self):
        with self.lock:
            self._id += 1
            self.estado = {"fase": "parado"}

    def ver(self):
        with self.lock:
            estado = dict(self.estado)
        if "expira_em" in estado:
            estado["segundos"] = max(0, int(estado.pop("expira_em") - time.time()))
        return estado


class Motor:
    def __init__(self, login):
        self.login = login
        self.proc = None
        self.estado = "parada"
        self.erro = None
        self.canais = {}
        self.assistindo = []
        self.ultimo_status = None
        self.falhas = 0
        self.religar_em = None
        self.desligando = False
        self.arquivo_erros = None
        # canal -> (saldo que o motor ainda acha, saldo certo vindo da Twitch). Vale até o
        # motor perceber sozinho (ex.: compra na loja, que a Twitch não avisa na hora).
        self.ajustes = {}


class Gerente:
    def __init__(self, cfg, hist, premium=None):
        self.cfg = cfg
        self.hist = hist
        self.premium = premium  # lunar.premium.Premium (sem ele, vale o grátis)
        self.lock = threading.RLock()
        self.motores = {}
        self.saldos_gravados = {}
        self.encerrando = False
        self.login = LoginTwitch(self._entrou)
        self.kick = kick.Kick(cfg, self.liberada, self.eh_premium)  # lives da Kick (opcional, por conta)
        self.seguidor = Seguidor(cfg, hist, self.limites, self.liberada)
        self.auto = {}  # (conta, canal, recompensa) -> como anda a compra automática
        self.auto_travas = collections.defaultdict(threading.Lock)  # uma compra por vez em cada conta
        threading.Thread(target=self._supervisor, daemon=True).start()

    # --- grátis x Lunar Premium ---
    def eh_premium(self):
        return bool(self.premium and self.premium.ativo())

    def limites(self):
        return self.premium.limites() if self.premium else premium.GRATIS

    def liberada(self, login):
        """No grátis só a primeira conta da lista farma; no Premium, todas."""
        limite = self.limites()["contas"]
        if limite is None:
            return True
        return login in [c["login"] for c in self.cfg.contas()[:limite]]

    def premium_mudou(self, ativo):
        """Ligou (ou desligou) o Premium: religa tudo com os limites novos (lives, contas)."""
        log.info("Lunar Premium %s: religando as contas", "ligado" if ativo else "desligado")
        for i, conta in enumerate(self.cfg.contas()):
            if not conta.get("paused"):
                self._agendar(conta["login"], i * 3)
        self.seguidor.avisar()
        self.kick.acordar()

    # --- ligar / desligar ---
    def iniciar_tudo(self):
        for i, conta in enumerate(self.cfg.contas()):
            if not conta.get("paused"):
                self._agendar(conta["login"], i * 3)
        self.kick.iniciar()

    def _motor(self, login):
        with self.lock:
            if login not in self.motores:
                self.motores[login] = Motor(login)
            return self.motores[login]

    def _agendar(self, login, segundos=0):
        self._motor(login).religar_em = time.time() + segundos

    def ligar(self, login):
        conta = self.cfg.conta(login)
        motor = self._motor(login)
        if conta is None or self.encerrando:
            return
        self.desligar(login, estado=None)
        if not self.liberada(login):
            motor.estado = "bloqueada"  # conta a mais na versão grátis: precisa do Premium
            return
        if not conta.get("channels"):
            motor.estado = "sem_canais"
            return
        if not paths.cookie_file(login).is_file():
            motor.estado = "precisa_entrar"
            return
        paths.garantir_pastas()
        motor.arquivo_erros = open(paths.LOG_DIR / f"{login}-motor.log", "a", encoding="utf-8")
        motor.arquivo_erros.write(f"\n--- {time.strftime('%d/%m %H:%M:%S')} ligando ---\n")
        motor.arquivo_erros.flush()
        env = dict(os.environ, PYTHONIOENCODING="utf-8", PYTHONUNBUFFERED="1")
        proc = subprocess.Popen(
            [paths.python_console(), "-m", "lunar.worker", login, "--lives", str(self.limites()["lives"])],
            cwd=str(paths.APP_DIR),
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=motor.arquivo_erros,
            env=env,
            creationflags=SEM_JANELA,
        )
        motor.proc = proc
        motor.estado = "iniciando"
        motor.erro = None
        motor.desligando = False
        motor.religar_em = None
        motor.ultimo_status = None
        threading.Thread(target=self._ouvir, args=(motor, proc), daemon=True).start()

    def desligar(self, login, estado="parada"):
        motor = self._motor(login)
        proc, motor.proc = motor.proc, None
        motor.religar_em = None
        if proc is not None and proc.poll() is None:
            motor.desligando = True
            proc.terminate()
            try:
                proc.wait(timeout=10)
            except subprocess.TimeoutExpired:
                proc.kill()
        if motor.arquivo_erros:
            motor.arquivo_erros.close()
            motor.arquivo_erros = None
        motor.assistindo = []
        if estado:
            motor.estado = estado

    def reiniciar(self, login, segundos=0):
        conta = self.cfg.conta(login)
        if conta and not conta.get("paused"):
            self._agendar(login, segundos)

    def pausar(self, login, pausada):
        self.cfg.pausar(login, pausada)
        if pausada:
            self.desligar(login, estado="pausada")
        else:
            self._motor(login).falhas = 0
            self._agendar(login)
        self.kick.acordar(login)

    def remover(self, login):
        self.desligar(login)
        self.kick.remover(login)
        with self.lock:
            self.motores.pop(login, None)
        try:
            paths.cookie_file(login).unlink()
        except OSError:
            pass
        self.cfg.remover_conta(login)
        self.hist.esquecer_conta(login)

    def parar_tudo(self):
        self.encerrando = True
        self.kick.parar_tudo()
        for login in list(self.motores):
            self.desligar(login)

    def _entrou(self, login, user_id):
        nova = self.cfg.conta(login) is None
        limite = self.limites()["contas"]
        if nova and limite is not None and len(self.cfg.contas()) >= limite:
            try:
                paths.cookie_file(login).unlink()  # não fica guardado o login de quem não entrou
            except OSError:
                pass
            return False
        self.cfg.adicionar_conta(login, user_id)
        self.hist.evento(login, None, "login", "Conta conectada" if nova else "Entrou de novo")
        motor = self._motor(login)
        motor.falhas = 0
        self.cfg.pausar(login, False)
        self._agendar(login)
        self.seguidor.avisar()

    # --- ouvir o motor ---
    def _ouvir(self, motor, proc):
        for linha in proc.stdout:
            try:
                msg = json.loads(linha)
            except ValueError:
                continue
            try:
                self._tratar(motor, msg)
            except Exception:
                log.exception("erro tratando mensagem de %s", motor.login)
        codigo = proc.wait()
        if motor.proc is not proc:
            return  # foi desligado de propósito
        motor.proc = None
        motor.assistindo = []
        if motor.arquivo_erros:
            motor.arquivo_erros.close()
            motor.arquivo_erros = None
        if codigo == 3:
            motor.estado = "precisa_entrar"
            self.hist.evento(motor.login, None, "login", "O login venceu. Entre de novo nessa conta.")
        elif codigo == 2:
            motor.estado = "sem_canais"
        elif not self.encerrando:
            motor.falhas += 1
            espera = min(300, 15 * 2 ** (motor.falhas - 1))
            motor.estado = "erro"
            motor.erro = motor.erro or "O farm dessa conta parou."
            motor.religar_em = time.time() + espera

    def _tratar(self, motor, msg):
        tipo = msg.get("t")
        login = motor.login
        if tipo == "status":
            agora = time.time()
            if motor.ultimo_status is not None:
                decorrido = min(30, agora - motor.ultimo_status)
                for canal in msg.get("watching", []):
                    self.hist.assistiu(login, canal, decorrido)
            motor.ultimo_status = agora
            motor.canais = {c["login"]: c for c in msg.get("channels", [])}
            for canal, (do_motor, certo, quando) in list(motor.ajustes.items()):
                info = motor.canais.get(canal)
                if info is None:
                    continue
                if info.get("points") == do_motor and agora - quando < AJUSTE_VALE:
                    info["points"] = certo  # o motor ainda não sabe da compra
                else:
                    del motor.ajustes[canal]  # o motor já tem um saldo mais novo
            motor.assistindo = msg.get("watching", [])
            motor.estado = "farmando"
            motor.falhas = 0
            for canal, info in motor.canais.items():
                chave = (login, canal)
                if info.get("points") is not None and self.saldos_gravados.get(chave) != info["points"]:
                    self.saldos_gravados[chave] = info["points"]
                    self.hist.saldo(login, canal, info["points"])
            self._auto_comprar(login, motor)
        elif tipo == "gain":
            canal = msg.get("channel")
            self.hist.ganho(login, canal, int(msg.get("points", 0)), msg.get("reason", ""), msg.get("balance"))
            for (conta_auto, canal_auto, _), est in list(self.auto.items()):
                if conta_auto == login and canal_auto == canal and est.get("ultima") and msg.get("reason") != "REFUND":
                    est["ultima"]["ganhos"] += int(msg.get("points", 0))  # ganho normal, não devolução
            if canal in motor.canais and msg.get("balance") is not None:
                motor.ajustes.pop(canal, None)
                motor.canais[canal]["points"] = msg["balance"]
        elif tipo == "saldo":
            canal = msg.get("channel")
            ajuste = motor.ajustes.get(canal)
            if canal in motor.canais and msg.get("balance") is not None and not (ajuste and time.time() - ajuste[2] < AJUSTE_NOVO):
                motor.ajustes.pop(canal, None)
                motor.canais[canal]["points"] = msg["balance"]
        elif tipo == "spent":
            canal = msg.get("channel")
            motor.ajustes.pop(canal, None)
            self.hist.gasto(login, canal, int(msg.get("points", 0)))
            if msg.get("balance") is not None:
                self.hist.saldo(login, canal, msg["balance"])
                if canal in motor.canais:
                    motor.canais[canal]["points"] = msg["balance"]
        elif tipo == "online":
            jogo = f" jogando {msg['game']}" if msg.get("game") else ""
            self.hist.evento(login, msg.get("channel"), "online", f"{msg.get('channel')} entrou ao vivo{jogo}")
            for (conta_auto, canal_auto, _), est in list(self.auto.items()):
                if conta_auto == login and canal_auto == msg.get("channel") and est.pop("espera_live", False):
                    est.update(proxima=0, erro=None)  # live nova: o limite da live zerou
        elif tipo == "offline":
            self.hist.evento(login, msg.get("channel"), "offline", f"{msg.get('channel')} encerrou a live")
        elif tipo == "raid":
            self.hist.evento(login, msg.get("channel"), "raid", f"Seguiu a raid de {msg.get('channel')} para {msg.get('target')}")
        elif tipo == "login_needed":
            motor.estado = "precisa_entrar"
        elif tipo == "error":
            motor.erro = msg.get("msg")
        elif tipo == "started":
            motor.estado = "iniciando"

    def _supervisor(self):
        while True:
            time.sleep(1)
            if self.encerrando:
                return
            agora = time.time()
            for motor in list(self.motores.values()):
                if motor.religar_em is not None and agora >= motor.religar_em:
                    motor.religar_em = None
                    try:
                        self.ligar(motor.login)
                    except Exception:
                        log.exception("não deu para ligar %s", motor.login)
                        motor.estado = "erro"
                        motor.religar_em = agora + 60

    # --- compra automática ---
    def _auto_comprar(self, login, motor):
        """Confere as compras automáticas da conta: se juntou o custo, compra (numa thread)."""
        if not self.eh_premium():
            return  # compra automática é do Lunar Premium
        agora = time.time()
        for regra in (self.cfg.conta(login) or {}).get("auto_compras") or []:
            if regra.get("pausada"):
                continue
            est = self.auto.setdefault((login, regra["canal"], regra["id"]), {})
            info = motor.canais.get(regra["canal"])
            if info is None or info.get("points") is None:
                continue
            if est.get("andando") or agora < est.get("proxima", 0) or info["points"] < regra["custo"]:
                continue
            est["andando"] = True
            threading.Thread(target=self._fazer_auto, args=(login, dict(regra), est), daemon=True).start()

    def _regra_ligada(self, login, regra):
        return any(r["canal"] == regra["canal"] and r["id"] == regra["id"] and not r.get("pausada")
                   for r in (self.cfg.conta(login) or {}).get("auto_compras") or [])

    def _fazer_auto(self, login, regra, est):
        """Compra uma atrás da outra até os pontos do canal não darem mais (ou a Twitch dizer que
        chegou no limite). As compras de uma mesma conta vão uma de cada vez."""
        canal = regra["canal"]
        compradas = 0
        try:
            with self.auto_travas[login]:
                while not self.encerrando and self._regra_ligada(login, regra):
                    try:
                        r = twitch.cliente(login).resgatar(canal, regra["id"], custo_esperado=regra["custo"],
                                                           titulo=regra.get("titulo"))
                    except twitch.ErroTwitch as e:
                        if e.codigo == "NOT_ENOUGH_POINTS" and compradas:
                            break  # gastou o que dava
                        raise
                    compradas += 1
                    rec = r["recompensa"]
                    if rec["id"] != regra["id"]:  # recriada pelo streamer: a regra passa a usar o id novo
                        self.cfg.trocar_id_auto_compra(login, canal, regra["id"], rec["id"])
                        log.info("compra automática: %s em %s mudou de id (recriada pelo streamer)", rec["titulo"], canal)
                        regra["id"] = rec["id"]
                    self.hist.gasto(login, canal, rec["custo"], f"{rec['titulo']} (automático)")
                    self.ajustar_saldo(login, canal, r["saldo"])
                    log.info("compra automática: %s comprou %s em %s", login, rec["titulo"], canal)
                    ultima = est.get("ultima")
                    if ultima and r["saldo"] is not None:
                        # O saldo antes desta compra já tinha os pontos de alguma compra anterior de volta?
                        self._devolveu(login, regra, est, r["saldo"] + rec["custo"])
                    agora = time.time()
                    leva = (est.get("ultima") or {}).get("leva", 0) + 1
                    est.update(ultima={"ts": agora, "saldo": r["saldo"] or 0, "ganhos": 0, "leva": leva},
                               erro=None, feita=agora)
                    if r["saldo"] is None or r["saldo"] < regra["custo"]:
                        break
                    time.sleep(AUTO_ENTRE)
            est["proxima"] = time.time() + AUTO_ENTRE
        except twitch.SemLogin:
            est.update(proxima=time.time() + 1800, erro="O login da conta venceu.")
        except twitch.ErroTwitch as e:
            if e.codigo in AUTO_PAUSA:
                self.cfg.pausar_auto_compra(login, canal, regra["id"], str(e))
                self.hist.evento(login, canal, "erro", f"Compra automática de {regra['titulo']} pausada: {e}")
            if e.codigo in AUTO_PROXIMA_LIVE:
                est["espera_live"] = True
            est.update(proxima=time.time() + AUTO_ESPERA.get(e.codigo, 1800),
                       erro=AUTO_PROXIMA_LIVE.get(e.codigo) or AUTO_AVISO.get(e.codigo) or str(e))
            log.info("compra automática de %s em %s (%s) parou: %s", regra["titulo"], canal, login, e)
        except Exception:
            log.exception("compra automática")
            est.update(proxima=time.time() + 1800, erro="Erro inesperado na compra automática.")
        finally:
            est["andando"] = False
            if compradas:
                for depois in AUTO_CONFERIR:
                    conferir = threading.Timer(depois, self._conferir_devolucao, args=(login, regra, est))
                    conferir.daemon = True
                    conferir.start()

    def _conferir_devolucao(self, login, regra, est):
        """Pergunta o saldo direto para a Twitch depois das compras automáticas."""
        if not est.get("ultima"):
            return
        try:
            saldo = twitch.cliente(login).loja(regra["canal"])["saldo"]
        except Exception:
            return
        if saldo is not None and self._devolveu(login, regra, est, saldo):
            self.ajustar_saldo(login, regra["canal"], saldo)

    def _devolveu(self, login, regra, est, saldo):
        """Se o saldo subiu mais do que os ganhos registrados explicam, o jogo devolveu os pontos
        (ex.: Twitch sem vínculo no PokeIdle): pausa em vez de ficar comprando e recebendo de volta."""
        ultima = est.get("ultima")
        custo = regra["custo"]
        sobra = saldo - ultima["saldo"] - ultima["ganhos"]
        voltaram = min(int((sobra + custo * 0.1) // custo), ultima.get("leva", 1))
        if voltaram < 1:
            return 0
        ultima.update(saldo=ultima["saldo"] + voltaram * custo, leva=ultima.get("leva", 1) - voltaram)
        self.hist.gasto(login, regra["canal"], -voltaram * custo, f"{regra['titulo']} (devolvido)")
        if self._regra_ligada(login, regra):
            self.cfg.pausar_auto_compra(login, regra["canal"], regra["id"],
                                        "Os pontos voltaram depois da compra: confira se a Twitch está vinculada no jogo.")
            self.hist.evento(login, regra["canal"], "erro", f"Compra automática de {regra['titulo']} pausada: os pontos voltaram")
        return voltaram

    def auto_compras(self, login):
        """As compras automáticas da conta, com o que aconteceu por último em cada uma."""
        lista = []
        for regra in (self.cfg.conta(login) or {}).get("auto_compras") or []:
            est = self.auto.get((login, regra["canal"], regra["id"]), {})
            lista.append(dict(regra, ultima_compra=est.get("feita"), aviso=None if regra.get("pausada") else est.get("erro")))
        return lista

    def ajustar_saldo(self, login, canal, saldo):
        """Saldo que veio agora da Twitch (loja aberta ou compra feita pelo app)."""
        if saldo is None:
            return
        motor = self._motor(login)
        info = motor.canais.get(canal)
        if info is not None and info.get("points") != saldo:
            do_motor = motor.ajustes[canal][0] if canal in motor.ajustes else info.get("points")
            motor.ajustes[canal] = (do_motor, saldo, time.time())
            info["points"] = saldo
        self.hist.saldo(login, canal, saldo)

    # --- para o painel ---
    def estado(self):
        hoje = self.hist.hoje_por_conta()
        contas = []
        for conta in self.cfg.contas():
            login = conta["login"]
            motor = self._motor(login)
            estado = "pausada" if conta.get("paused") else motor.estado
            salvos = self.hist.saldos(login)
            farmado = self.hist.farmado_por_canal(login)
            gastos = self.hist.gasto_por_canal(login)
            favoritos = set(conta.get("favoritos") or [])
            canais = []
            for i, canal in enumerate(conta.get("channels", [])):
                info = motor.canais.get(canal) if motor.proc is not None else None
                ganho = farmado.get(canal, {})
                gasto = gastos.get(canal, {})
                canais.append({
                    "farmado_hoje": ganho.get("hoje") or 0,
                    "farmado_total": ganho.get("total") or 0,
                    "gasto_hoje": gasto.get("hoje") or 0,
                    "gasto_total": gasto.get("total") or 0,
                    "login": canal,
                    "ordem": i + 1,
                    "online": info["online"] if info else None,
                    "points": info["points"] if info else salvos.get(canal),
                    "game": (info or {}).get("game"),
                    "title": (info or {}).get("title"),
                    "viewers": (info or {}).get("viewers"),
                    "watching": canal in motor.assistindo,
                    "favorito": canal in favoritos,
                })
            contas.append({
                "login": login,
                "estado": estado,
                "erro": motor.erro if estado == "erro" else None,
                "religa_em": max(0, int(motor.religar_em - time.time())) if motor.religar_em else None,
                "hoje": hoje.get(login, 0),
                "canais": canais,
                "ao_vivo": sum(1 for c in canais if c["online"]),
                "assistindo": [c for c in motor.assistindo],
                "ordem": conta.get("ordem") or "lista",
                "auto_compras": self.auto_compras(login),
                "kick": self.kick.ver(login),
            })
        return {"contas": contas, "login": self.login.ver()}

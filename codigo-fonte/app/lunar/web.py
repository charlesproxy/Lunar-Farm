"""Painel (Flask): a janela do PC e o celular usam a mesma página e a mesma API."""

import ipaddress
import json
import logging
import re
import secrets
import threading
import time
from concurrent.futures import ThreadPoolExecutor

import segno
from flask import Flask, Response, abort, jsonify, request, send_from_directory, session

from lunar import NOME, VERSAO, config, kick, novidades, paths, plataforma, premium, suporte, twitch

log = logging.getLogger("lunar")

LOCAL = ("127.0.0.1", "::1")
PIN_ERROS_LIVRES = 5  # PINs errados antes de travar; depois 1 min, 2, 4... até PIN_TRAVA_MAX
PIN_TRAVA_MAX = 3600
LIVRES = ("/", "/manifest.webmanifest", "/api/pin", "/api/ping")


def _host_valido(host):
    """O painel só atende pelo endereço do PC (127.0.0.1, localhost ou o IP no Wi-Fi). Um site que aponta o
    próprio nome para o 127.0.0.1 (DNS rebinding) chega com o nome dele aqui e é recusado."""
    host = (host or "").strip().lower()
    nome = host[1:host.find("]")] if host.startswith("[") else host.rsplit(":", 1)[0]
    if nome == "localhost":
        return True
    try:
        ipaddress.ip_address(nome)
        return True
    except ValueError:
        return False


def _origem_valida(origem, host):
    """Pedido feito por uma página: só vale se ela for o próprio painel. Um site aberto no navegador não pode
    mandar o painel fazer nada (pausar, sair, comprar). Sem Origin = o próprio app, um programa ou uma navegação."""
    if origem is None:
        return True
    return origem.strip().lower() == f"http://{(host or '').strip().lower()}"


def _segredo():
    arquivo = paths.DATA_DIR / "segredo"
    if not arquivo.is_file():
        arquivo.write_text(secrets.token_hex(32), encoding="utf-8")
    return arquivo.read_text(encoding="utf-8").strip()


def criar_app(gerente, cfg, hist, controle):
    app = Flask(__name__, static_folder=None)
    app.secret_key = _segredo()
    app.config["SESSION_COOKIE_NAME"] = "lunar"
    app.config["PERMANENT_SESSION_LIFETIME"] = 60 * 60 * 24 * 90

    def eh_local():
        return request.remote_addr in LOCAL

    def so_local():
        if not eh_local():
            abort(403)

    @app.before_request
    def proteger():
        if not _host_valido(request.host) or not _origem_valida(request.headers.get("Origin"), request.host):
            abort(403)
        if eh_local():
            return None
        if not cfg.opcoes().get("lan_enabled"):
            abort(403)
        if request.path in LIVRES or request.path.startswith("/static/"):
            return None
        if not session.get("ok"):
            return jsonify(erro="pin"), 401
        return None

    @app.after_request
    def sem_cache(resp):
        # API nunca em cache; páginas e scripts sempre conferem se mudaram
        # (senão a janela mostra a versão velha depois de uma atualização).
        resp.headers["Cache-Control"] = "no-store" if request.path.startswith("/api/") else "no-cache"
        return resp

    def corpo():
        return request.get_json(silent=True) or {}

    def conta_ou_404(login):
        if cfg.conta(login) is None:
            abort(404)

    def trocar_canais(login, lista):
        # Só reinicia o motor se a lista mudou de verdade (reiniciar recarrega todos os canais).
        antes = list(cfg.conta(login).get("channels", []))
        canais = cfg.definir_canais(login, lista)
        if canais != antes:
            gerente.reiniciar(login, 3)
            gerente.seguidor.avisar()
        return canais

    def carimbo():
        # Muda quando app.js/style.css mudam: a janela nunca fica com a versão velha.
        return str(int(max((paths.STATIC_DIR / f).stat().st_mtime for f in ("app.js", "style.css"))))

    # --- páginas ---
    @app.get("/")
    def inicio():
        html = (paths.STATIC_DIR / "index.html").read_text(encoding="utf-8").replace("{{v}}", carimbo())
        return Response(html, mimetype="text/html")

    @app.get("/static/<path:arquivo>")
    def estaticos(arquivo):
        return send_from_directory(paths.STATIC_DIR, arquivo)

    @app.get("/manifest.webmanifest")
    def manifesto():
        return send_from_directory(paths.STATIC_DIR, "manifest.webmanifest", mimetype="application/manifest+json")

    @app.get("/api/ping")
    def ping():
        return jsonify(app=NOME, versao=VERSAO)

    # Tentativas de PIN pelo celular: o PIN tem 4 dígitos, então sem limite daria para testar todos em minutos.
    # O contador é um só (não por IP: no Wi-Fi dá para trocar de IP). No PC nada disso trava.
    tentativas = {"erros": 0, "ate": 0.0}
    trava_pin = threading.Lock()

    @app.post("/api/pin")
    def pin():
        agora = time.time()
        with trava_pin:
            if agora < tentativas["ate"]:
                minutos = max(1, round((tentativas["ate"] - agora) / 60))
                return jsonify(ok=False, erro=f"Muitas tentativas erradas. Espere {minutos} min e tente de novo."), 429
        if str(corpo().get("pin", "")).strip() == str(cfg.opcoes().get("pin")):
            with trava_pin:
                tentativas.update(erros=0, ate=0.0)
            session.permanent = True
            session["ok"] = True
            return jsonify(ok=True)
        with trava_pin:
            tentativas["erros"] += 1
            if tentativas["erros"] >= PIN_ERROS_LIVRES:
                tentativas["ate"] = agora + min(PIN_TRAVA_MAX, 60 * 2 ** (tentativas["erros"] - PIN_ERROS_LIVRES))
            erros = tentativas["erros"]
        log.warning("PIN errado no painel do celular (%s), %s seguidos", request.remote_addr, erros)
        return jsonify(ok=False, erro="PIN errado"), 403

    # --- estado e contas ---
    @app.get("/api/estado")
    def estado():
        dados = gerente.estado()
        dados["local"] = eh_local()
        if dados["local"]:
            controle.janela_em = time.time()  # a janela do PC está aberta
        dados["versao"] = VERSAO
        dados["carimbo"] = carimbo()
        dados["chat_mode"] = cfg.opcoes().get("chat_mode")
        dados["atualizacao"] = controle.atualizador.ver()
        dados["novidades"] = [v["versao"] for v in novidades.nao_vistas(cfg)]
        dados["premium"] = controle.premium.ver()
        dados["suporte_novas"] = controle.suporte.novas()
        uso = getattr(controle, "uso", None)
        dados["indicar"] = uso.link_indicar if uso else None
        return jsonify(dados)

    # --- ajuda e suporte (tickets no site) ---
    @app.get("/api/suporte")
    def suporte_lista():
        if request.args.get("atualizar"):
            # Abriu a tela de suporte: confere agora se chegou resposta nos tickets em aberto.
            for t in controle.suporte.listar():
                if t.get("status") != "fechado":
                    try:
                        controle.suporte.ver(t["ticket"], marcar=False)
                    except suporte.ErroSuporte:
                        pass
        return jsonify(tickets=controle.suporte.listar())

    @app.post("/api/suporte/criar")
    def suporte_criar():
        d = corpo()
        try:
            return jsonify(controle.suporte.criar(str(d.get("assunto") or ""), str(d.get("mensagem") or ""),
                                                  str(d.get("contato") or ""), bool(d.get("com_registro"))))
        except suporte.ErroSuporte as e:
            return jsonify(erro=str(e)), 400

    @app.get("/api/suporte/<ticket>")
    def suporte_ver(ticket):
        try:
            return jsonify(controle.suporte.ver(ticket))
        except suporte.ErroSuporte as e:
            return jsonify(erro=str(e)), 400

    @app.post("/api/suporte/<ticket>/responder")
    def suporte_responder(ticket):
        try:
            return jsonify(controle.suporte.responder(ticket, str(corpo().get("mensagem") or "")))
        except suporte.ErroSuporte as e:
            return jsonify(erro=str(e)), 400

    def pede_premium(motivo):
        return jsonify(erro="Isso é do Lunar Premium.", premium=motivo), 402

    # --- o que mudou em cada versão ---
    @app.get("/api/novidades")
    def ver_novidades():
        return jsonify(atual=VERSAO, versoes=novidades.historico(), nao_vistas=novidades.nao_vistas(cfg))

    @app.post("/api/novidades/vistas")
    def novidades_vistas():
        novidades.marcar_vistas(cfg)
        return jsonify(ok=True)

    # --- atualização do app (só no PC) ---
    @app.post("/api/atualizacao/conferir")
    def atualizacao_conferir():
        so_local()
        return jsonify(controle.atualizador.conferir())

    @app.post("/api/atualizacao/instalar")
    def atualizacao_instalar():
        so_local()
        if not controle.atualizador.atualizar():
            return jsonify(erro="Não tem versão nova para instalar agora."), 409
        return jsonify(controle.atualizador.ver())

    @app.post("/api/login/iniciar")
    def login_iniciar():
        # Entrar de novo numa conta que já está no app sempre pode; conta nova a mais, só no Premium.
        alvo = str(corpo().get("alvo") or "")
        limite = gerente.limites()["contas"]
        if not cfg.conta(alvo) and limite is not None and len(cfg.contas()) >= limite:
            return pede_premium("conta")
        return jsonify(gerente.login.iniciar())

    @app.get("/api/login")
    def login_ver():
        return jsonify(gerente.login.ver())

    @app.post("/api/login/cancelar")
    def login_cancelar():
        gerente.login.cancelar()
        return jsonify(ok=True)

    @app.post("/api/contas/<login>/canais")
    def canais_adicionar(login):
        conta_ou_404(login)
        novos = config.separar_canais(corpo().get("texto", ""))
        if not novos:
            return jsonify(ok=False, erro="Não achei nenhum canal nisso. Cole o link (twitch.tv/nome) ou o nome do canal."), 400
        atuais = cfg.conta(login).get("channels", [])
        adicionados = [c for c in dict.fromkeys(novos) if c not in atuais]
        canais = trocar_canais(login, atuais + adicionados)
        return jsonify(ok=True, canais=canais, adicionados=adicionados)

    @app.put("/api/contas/<login>/canais")
    def canais_definir(login):
        conta_ou_404(login)
        return jsonify(ok=True, canais=trocar_canais(login, corpo().get("canais", [])))

    @app.get("/api/atalhos")
    def atalhos():
        # Listas prontas de canais (lunar/atalhos.json) para encher uma conta em 2 cliques.
        try:
            with open(paths.PKG_DIR / "atalhos.json", encoding="utf-8") as f:
                lista = json.load(f)
        except (OSError, ValueError):
            lista = []
        return jsonify([
            {"nome": a["nome"], "canais": config.separar_canais(" ".join(a.get("canais", [])))}
            for a in lista if isinstance(a, dict) and a.get("nome")
        ])

    @app.post("/api/contas/<login>/copiar")
    def canais_copiar(login):
        conta_ou_404(login)
        origem = cfg.conta(corpo().get("de", ""))
        if origem is None:
            abort(404)
        atuais = cfg.conta(login).get("channels", [])
        canais = trocar_canais(login, atuais + [c for c in origem.get("channels", []) if c not in atuais])
        return jsonify(ok=True, canais=canais)

    @app.post("/api/contas/<login>/favorito")
    def favorito(login):
        # O motor relê as estrelas sozinho em até 10 s: não precisa reiniciar.
        conta_ou_404(login)
        dados = corpo()
        favoritos = cfg.favoritar(login, config.normalizar_canal(str(dados.get("canal", ""))), bool(dados.get("ligado")))
        if favoritos is None:
            abort(404)
        return jsonify(ok=True, favoritos=favoritos)

    @app.post("/api/contas/<login>/ordem")
    def ordem(login):
        conta_ou_404(login)
        modo = corpo().get("modo")
        if modo not in ("lista", "pontos"):
            abort(400)
        cfg.definir_ordem(login, modo)
        return jsonify(ok=True, ordem=modo)

    @app.post("/api/contas/<login>/pausar")
    def pausar(login):
        conta_ou_404(login)
        gerente.pausar(login, bool(corpo().get("pausada", True)))
        return jsonify(ok=True)

    @app.post("/api/contas/<login>/reiniciar")
    def reiniciar(login):
        conta_ou_404(login)
        gerente.reiniciar(login)
        return jsonify(ok=True)

    # --- Kick (opcional, por conta) ---
    @app.post("/api/contas/<login>/kick")
    def kick_configurar(login):
        conta_ou_404(login)
        c = corpo()
        mudancas = {}
        if "ligada" in c:
            mudancas["ligada"] = bool(c["ligada"])
        if "auto" in c:  # compra automática: liga ou desliga uma recompensa (pelo nome, sem as horas)
            if c.get("ligado", True) and not gerente.eh_premium():
                return pede_premium("auto")
            atual = set(cfg.kick(login).get("auto") or [])
            familia = str(c["auto"]).strip().lower()
            (atual.add if c.get("ligado", True) else atual.discard)(familia)
            mudancas["auto"] = sorted(atual)
        if "favorito" in c:  # estrela: liga ou desliga um canal
            atual = cfg.kick(login)
            fav = set(atual.get("favoritos") or [])
            (fav.add if c.get("ligado", True) else fav.discard)(str(c["favorito"]))
            mudancas["favoritos"] = [x for x in atual["canais"] if x in fav]
        if c.get("conferir_seguidos"):
            gerente.kick.conferir_seguidos(login)
        if "seguir" in c:  # abre os canais que faltam seguir numa janela normal desta conta
            so_local()
            gerente.kick.seguir(login, [str(x) for x in c["seguir"]] if isinstance(c["seguir"], list) else None)
        if "lives" in c:
            try:
                lives = max(1, min(kick.LIVES_MAX, int(c["lives"])))
            except (TypeError, ValueError):
                abort(400)
            if lives > 1 and not gerente.eh_premium():
                return pede_premium("lives")
            mudancas["lives"] = lives
        if c.get("trazer_twitch"):
            n = gerente.kick.trazer_twitch(login)
            return jsonify(trazidos=n, **cfg.kick(login))
        if "canais" in c and isinstance(c["canais"], list):
            mudancas["canais"] = [str(x) for x in c["canais"]][:30]
        if "texto" in c:  # colou um ou vários links/nomes: entram no fim da lista
            novos = [x for x in re.split(r"[\s,;]+", str(c["texto"])) if x]
            mudancas["canais"] = cfg.kick(login)["canais"] + novos[:30]
        return jsonify(gerente.kick.configurar(login, **mudancas))

    @app.post("/api/contas/<login>/kick/entrar")
    def kick_entrar(login):
        so_local()  # a janela da Kick abre neste PC
        conta_ou_404(login)
        try:
            gerente.kick.entrar(login)
        except kick.ErroKick as e:
            return jsonify(erro=str(e)), 409
        return jsonify(ok=True)

    @app.get("/api/kick/loja")
    def kick_loja():
        login = request.args.get("conta", "")
        conta_ou_404(login)
        canal = config.normalizar_canal_kick(request.args.get("canal", ""))
        if not canal:
            return jsonify(erro="Canal da Kick inválido"), 400
        try:
            r = gerente.kick.loja(login, canal)
        except kick.ErroKick as e:
            return jsonify(erro=str(e)), 409
        return jsonify(canal=canal, saldo=r.get("saldo"), recompensas=r.get("recompensas") or [],
                       auto=cfg.kick(login).get("auto") or [])

    @app.post("/api/kick/comprar")
    def kick_comprar():
        c = corpo()
        login = str(c.get("conta") or "")
        conta_ou_404(login)
        canal = config.normalizar_canal_kick(c.get("canal", ""))
        if not canal or not re.fullmatch(r"[0-9a-zA-Z_-]{1,40}", str(c.get("id") or "")):
            abort(400)
        try:
            r = gerente.kick.comprar(login, canal, str(c["id"]), c.get("custo") if isinstance(c.get("custo"), int) else None)
        except kick.ErroKick as e:
            return jsonify(erro=str(e)), 409
        if not r.get("ok"):
            return jsonify(erro=f"A Kick recusou a compra ({r.get('status')}). {r.get('det') or ''}".strip()), 409
        return jsonify(ok=True)

    @app.post("/api/contas/<login>/kick/pronto")
    def kick_pronto(login):
        conta_ou_404(login)
        gerente.kick.pronto(login)
        return jsonify(ok=True)

    @app.post("/api/contas/<login>/kick/sair")
    def kick_sair(login):
        conta_ou_404(login)
        gerente.kick.sair(login)
        return jsonify(ok=True)

    @app.post("/api/contas/<login>/kick/mostrar")
    def kick_mostrar(login):
        so_local()
        conta_ou_404(login)
        gerente.kick.mostrar(login, bool(corpo().get("mostrar", True)))
        return jsonify(ok=True)

    @app.delete("/api/contas/<login>")
    def remover(login):
        conta_ou_404(login)
        gerente.remover(login)
        return jsonify(ok=True)

    # --- resumo e histórico ---
    @app.get("/api/resumo")
    def resumo():
        return jsonify(hist.resumo(request.args.get("conta") or None))

    @app.get("/api/historico")
    def historico():
        antes = request.args.get("antes", type=float)
        return jsonify(hist.linha_do_tempo(
            request.args.get("conta") or None,
            limite=min(500, request.args.get("limite", 150, type=int)),
            com_assistir=request.args.get("assistir") == "1",
            antes=antes,
        ))

    # --- loja de pontos dos canais ---
    @app.get("/api/loja")
    def loja():
        login = request.args.get("conta", "")
        canal = config.normalizar_canal(request.args.get("canal", ""))
        conta_ou_404(login)
        if not canal:
            abort(400)
        try:
            dados = twitch.cliente(login).loja(canal)
            gerente.ajustar_saldo(login, canal, dados.get("saldo"))  # o saldo da Twitch é o certo
            return jsonify(dados)
        except twitch.SemLogin:
            return jsonify(erro="O login dessa conta venceu. Entre de novo pela página da conta."), 409
        except twitch.ErroTwitch as e:
            return jsonify(erro=str(e)), 502

    @app.get("/api/loja/contas")
    def loja_contas():
        # Para a janela de compra: saldo de agora e quantas vezes cada conta já comprou essa
        # recompensa na live (o streamer pode limitar, ex.: 3 por live).
        canal = config.normalizar_canal(request.args.get("canal", ""))
        recompensa = request.args.get("recompensa", "")
        if not canal or not recompensa:
            abort(400)

        def olhar(login):
            try:
                dados = twitch.cliente(login).loja(canal)
            except (twitch.SemLogin, twitch.ErroTwitch):
                return login, None
            gerente.ajustar_saldo(login, canal, dados.get("saldo"))
            r = next((x for x in dados["recompensas"] if x["id"] == recompensa), None)
            return login, {"saldo": dados.get("saldo"), "compradas_live": r["compradas_live"] if r else 0,
                           "limite_live": r["limite_live"] if r else None}

        logins = [c["login"] for c in cfg.contas() if paths.cookie_file(c["login"]).is_file()]
        if not logins:
            return jsonify(contas={})
        with ThreadPoolExecutor(max_workers=len(logins)) as pool:
            return jsonify(contas={login: info for login, info in pool.map(olhar, logins) if info})

    # --- compra automática em vários canais ---
    # Cada canal tem a sua própria recompensa (código e preço); a mesma recompensa nos outros
    # canais é achada pelo nome. A lista é do canal (igual para toda conta): guarda 10 min.
    loja_cache = {}
    loja_trava = threading.Lock()

    def recompensas_do_canal(login, canal):
        with loja_trava:
            guardado = loja_cache.get(canal)
        if guardado and time.time() - guardado[0] < 600:
            return guardado[1]
        recompensas = twitch.cliente(login).loja(canal)["recompensas"]
        with loja_trava:
            loja_cache[canal] = (time.time(), recompensas)
        return recompensas

    def mesmo_nome(a, b):
        return (a or "").strip().casefold() == (b or "").strip().casefold()

    def achar_nos_canais(titulo, canais):
        """{canal: recompensa com esse nome, None (não tem) ou False (não deu para olhar)}.
        Divide os canais entre as contas logadas para olhar vários ao mesmo tempo."""
        logins = [c["login"] for c in cfg.contas() if paths.cookie_file(c["login"]).is_file()]
        if not logins:
            return {canal: False for canal in canais}

        def olhar(par):
            i, canal = par
            for tentativa in range(2):  # a Twitch às vezes falha uma consulta: tenta com outra conta
                try:
                    lista = recompensas_do_canal(logins[(i + tentativa) % len(logins)], canal)
                    break
                except (twitch.SemLogin, twitch.ErroTwitch):
                    lista = None
            if lista is None:
                return canal, False
            return canal, next((r for r in lista if mesmo_nome(r["titulo"], titulo) and not r["pede_texto"]), None)

        with ThreadPoolExecutor(max_workers=len(logins)) as pool:
            return dict(pool.map(olhar, enumerate(canais)))

    @app.get("/api/auto-compra/canais")
    def auto_canais():
        # Em quais canais (das listas das contas) existe uma recompensa com esse nome, e o preço.
        titulo = request.args.get("titulo", "").strip()
        if not titulo:
            abort(400)
        canais = list(dict.fromkeys(c for conta in cfg.contas() for c in conta.get("channels", [])))
        achados = achar_nos_canais(titulo, canais)
        return jsonify(canais=[
            {"canal": c, "custo": achados[c]["custo"] if achados[c] else None, "existe": bool(achados[c]),
             "falhou": achados[c] is False, "limite_live": achados[c]["limite_live"] if achados[c] else None}
            for c in canais
        ])

    @app.get("/api/auto-compra/resumo")
    def auto_resumo():
        # As últimas compras automáticas e as de hoje (as regras de cada conta já vêm no /api/estado).
        return jsonify(hist.compras_automaticas(limite=min(100, request.args.get("limite", 25, type=int))))

    @app.post("/api/auto-compra/mudar")
    def auto_mudar():
        # Pausar, retomar ou desligar em lote: uma recompensa (pelo nome), uma conta, um canal ou tudo.
        dados = corpo()
        acao = str(dados.get("acao") or "")
        if acao not in ("pausar", "retomar", "desligar"):
            abort(400)
        if acao == "retomar" and not gerente.eh_premium():
            return pede_premium("auto")
        login = str(dados.get("conta") or "") or None
        canal = config.normalizar_canal(str(dados.get("canal") or "")) if dados.get("canal") else None
        mudadas = cfg.mudar_auto_compras(acao, str(dados.get("titulo") or "") or None, login, canal)
        for chave in mudadas:  # retomou ou desligou: a próxima conferência já vale (sem esperar o tempo da última tentativa)
            if acao != "pausar":
                gerente.auto.pop(chave, None)
        return jsonify(ok=True, mudadas=len(mudadas))

    @app.post("/api/auto-compra/salvar")
    def auto_salvar():
        # Aplica nas contas marcadas: essa recompensa (pelo nome) fica ligada nos canais escolhidos e desligada
        # nos outros canais DESSAS contas. Conta não marcada fica como estava (cada conta tem os seus canais).
        # Ligar de novo também tira a pausa.
        dados = corpo()
        titulo = str(dados.get("titulo") or "").strip()
        if not titulo:
            abort(400)
        escolhidos = {config.normalizar_canal(str(c)) for c in dados.get("canais") or []} - {None}
        contas = {str(c) for c in dados.get("contas") or []}
        if escolhidos and contas and not gerente.eh_premium():
            return pede_premium("auto")
        achados = achar_nos_canais(titulo, sorted(escolhidos)) if escolhidos and contas else {}
        ligadas = 0
        for conta in cfg.contas():
            login = conta["login"]
            if login not in contas:
                continue
            for canal in conta.get("channels", []):
                r = achados.get(canal)
                if r is False:
                    continue  # não deu para conferir o canal agora: fica como estava
                for regra in [r for r in conta.get("auto_compras", []) if r["canal"] == canal and mesmo_nome(r["titulo"], titulo)]:
                    cfg.definir_auto_compra(login, canal, regra["id"], ligado=False, gravar=False)
                    gerente.auto.pop((login, canal, regra["id"]), None)
                if r and canal in escolhidos:
                    cfg.definir_auto_compra(login, canal, r["id"], r["titulo"], r["custo"], True, gravar=False)
                    ligadas += 1
        cfg.salvar()
        return jsonify(ok=True, ligadas=ligadas, sem_recompensa=sorted(c for c, r in achados.items() if r is None),
                       nao_conferidos=sorted(c for c, r in achados.items() if r is False))

    @app.post("/api/loja/comprar")
    def loja_comprar():
        dados = corpo()
        canal = config.normalizar_canal(str(dados.get("canal", "")))
        recompensa = str(dados.get("recompensa") or "")
        contas = [c for c in dict.fromkeys(dados.get("contas") or []) if isinstance(c, str) and cfg.conta(c)]
        if not canal or not recompensa or not contas:
            abort(400)
        resultados = []
        for i, login in enumerate(contas):
            if i:
                time.sleep(1)
            try:
                r = twitch.cliente(login).resgatar(canal, recompensa, dados.get("texto"))
            except twitch.SemLogin:
                resultados.append({"conta": login, "ok": False, "erro": "O login dessa conta venceu."})
                continue
            except twitch.ErroTwitch as e:
                resultados.append({"conta": login, "ok": False, "erro": str(e)})
                continue
            rec = r["recompensa"]
            hist.gasto(login, canal, rec["custo"], rec["titulo"])
            gerente.ajustar_saldo(login, canal, r["saldo"])
            resultados.append({"conta": login, "ok": True, "saldo": r["saldo"]})
        return jsonify(resultados=resultados)

    @app.get("/api/chatterino")
    def chatterino():
        so_local()
        canais = plataforma.canais_do_chatterino()
        if canais is None:
            return jsonify(ok=False, erro="Não achei o Chatterino neste PC."), 404
        return jsonify(ok=True, canais=canais)

    # --- opções (só no PC) ---
    @app.get("/api/opcoes")
    def opcoes():
        so_local()
        dados = cfg.opcoes()
        dados["pasta_dados"] = str(paths.DATA_DIR)
        return jsonify(dados)

    @app.post("/api/opcoes")
    def mudar_opcoes():
        so_local()
        novas = {k: v for k, v in corpo().items() if k in ("start_with_windows", "keep_awake", "chat_mode", "auto_follow")}
        if novas.get("chat_mode") not in (None, "sempre", "ao_vivo"):
            abort(400)
        antes = cfg.opcoes()
        dados = cfg.mudar_opcoes(**novas)
        controle.aplicar_opcoes(dados)
        if novas.get("auto_follow"):
            gerente.seguidor.avisar()
        if "chat_mode" in novas and novas["chat_mode"] != antes.get("chat_mode"):
            for conta in cfg.contas():
                gerente.reiniciar(conta["login"], 2)
        return jsonify(dados)

    @app.get("/api/celular")
    def celular():
        so_local()
        opcoes = cfg.opcoes()
        url = f"http://{plataforma.ip_na_rede()}:{paths.PORTA_CELULAR}/"
        qr = segno.make(url, error="m").svg_inline(scale=6, border=2, dark="#140f24", light="#ffffff")
        return jsonify(ligado=bool(opcoes.get("lan_enabled")), url=url, pin=opcoes.get("pin"), qr=qr)

    @app.post("/api/celular")
    def celular_mudar():
        so_local()
        dados = corpo()
        if dados.get("novo_pin"):
            cfg.mudar_opcoes(pin=f"{secrets.randbelow(10 ** 4):04d}")
            with trava_pin:  # PIN novo, contagem nova (o dono destrava o celular pelo PC)
                tentativas.update(erros=0, ate=0.0)
        if "ligado" in dados:
            cfg.mudar_opcoes(lan_enabled=bool(dados["ligado"]))
            controle.aplicar_celular(bool(dados["ligado"]))
        return celular()

    @app.post("/api/abrir")
    def abrir():
        url = str(corpo().get("url", ""))
        # Só endereços conhecidos: a Twitch, o WhatsApp (Indicar a um amigo) e o site do Lunar Farm.
        if not url.startswith(("https://www.twitch.tv/", "https://twitch.tv/", "https://wa.me/", "https://vexpulse.com.br/",
                               "https://kick.com/")):
            abort(400)
        if eh_local():
            plataforma.abrir_no_navegador(url)
        return jsonify(ok=True)

    @app.post("/api/pasta")
    def abrir_pasta():
        so_local()
        plataforma.abrir_no_navegador(str(paths.DATA_DIR))
        return jsonify(ok=True)

    @app.post("/api/sair")
    def sair():
        so_local()
        # Quem pediu: a tela do app (Configurações), o instalador ou outro programa.
        controle.sair_depois(f"painel ({request.headers.get('User-Agent', '?')[:70]})")
        return jsonify(ok=True)

    return app

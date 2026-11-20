"""Lives da Kick (opcional, ligada por conta).

Na Kick os pontos do canal vêm com a live tocando de verdade: +10 a cada 5 min. Ela paga direito 1 live por vez
em cada conta (medido em 13/11/2026: com 2 abertas, a que abriu primeiro rende; a outra, de vez em quando). O
Premium abre 2 (a do canal favorito primeiro), a versão grátis 1. Cada conta com a Kick ligada ganha um Microsoft Edge só dela (perfil em
DATA_DIR/kick/<conta>), sem som, com a janela fora da tela e fora da barra de tarefas, tocando o player
das lives (player.kick.com) na menor qualidade. O Lunar controla esse Edge pelo protocolo do DevTools, que só
atende no próprio PC.

- O login é a própria pessoa que faz, num Edge normal, sem nada controlando (o Google recusa entrar num
  navegador controlado, e é assim que tem que ser). O Lunar nunca vê a senha: depois que a pessoa fecha essa
  janela, ele abre o Edge escondido das lives no mesmo perfil, que já está com o login.
- Tudo o que o Lunar pergunta à Kick (quem está ao vivo, o saldo, as recompensas, o resgate) sai de dentro das
  páginas da Kick, com o login da pessoa, como o próprio site faz.
- Se a Kick recusar ou pedir uma verificação, o Lunar mostra o aviso e para ali: não tenta passar por cima.
"""

import base64
import itertools
import json
import logging
import os
import queue
import re
import shutil
import subprocess
import threading
import time
import urllib.parse

import psutil
import websocket

from lunar import config, paths, plataforma

log = logging.getLogger("lunar")

KICK = "https://kick.com"
LIVES_MAX = 2  # lives da Kick ao mesmo tempo por conta (1 ou 2; a Kick paga direito 1, a primeira que abre)
SEM_RENDER = 15 * 60  # live tocando esse tempo sem ganhar ponto: recarrega a página dela
RENDE_JANELA = 12 * 60  # ganhou ponto nesse tempo: "rendendo"
# Live que rende pouco: nos últimos 30 min ganhou menos da metade do normal (10 a cada 5 min = 60). Se tiver outra live
# no ar esperando vaga, ela dá a vez por 30 min. Pinga um ponto de vez em quando não segura a vaga.
TESTE_RENDE = 30 * 60
RENDE_MINIMO = 30
PASSO = 5  # segundos entre uma volta e outra do motor de cada conta
CONFERIR_LIVES = 120  # quem está ao vivo
CONFERIR_PLAYER = 30  # se cada live está tocando
CONFERIR_SALDO = 300  # saldo e resgate (a Kick dá os pontos de 5 em 5 min)
DEVOLUCAO = 15 * 60  # janela em que um saldo de volta ao de antes do resgate quer dizer que o jogo devolveu
ENTRAR_MAX = 20 * 60  # tempo máximo esperando a pessoa entrar na Kick
FORA_DA_TELA = {"left": -32000, "top": -32000, "width": 320, "height": 200, "windowState": "normal"}
# Quem a conta já segue na Kick: confere de 5 em 5 min enquanto faltar algum. Seguir é a pessoa que faz, no navegador
# dela: a página do canal cai na verificação anti-robô do Cloudflare no Edge controlado, e isso não se contorna.
CONFERIR_SEGUIDOS = 300
# Leve: as lives são de 160p, então não precisam da placa de vídeo, e as páginas da Kick dividem um processo só.
# Medido com 2 lives: de 753 MB e 15% de um núcleo para 458 MB e 11%.
LEVE = ["--process-per-site", "--disable-gpu", "--disable-extensions", "--disable-component-extensions-with-background-pages",
        "--disable-background-networking", "--disable-sync", "--disable-default-apps", "--no-pings", "--disable-breakpad",
        "--disable-domain-reliability", "--disable-client-side-phishing-detection"]


def _edge():
    return plataforma.achar_navegador()


def _pasta_kick():
    return paths.DATA_DIR / "kick"


_encerrando = threading.Event()  # o app está fechando: nenhum Edge novo


def _edges():
    """(processo, argumentos em minúsculas) de cada Edge/Chrome aberto. Lê a linha de comando só desses."""
    for p in psutil.process_iter(["name"]):
        try:
            if plataforma.eh_navegador(p.info["name"]):
                yield p, [a.lower() for a in p.cmdline()]
        except (psutil.Error, TypeError):
            continue


def _processos_do_perfil(perfil, so_navegador=False):
    """Processos do Edge que usam exatamente esse perfil (o navegador e os filhos dele, ou só o navegador)."""
    marca = f"--user-data-dir={perfil}".lower()
    return [p for p, args in _edges() if marca in args and not (so_navegador and any(a.startswith("--type=") for a in args))]


def limpar_sobras():
    """Fecha Edges das lives que sobraram de uma vez em que o app fechou sem conseguir fechar o Edge."""
    if not _pasta_kick().is_dir():
        return
    marca = f"--user-data-dir={_pasta_kick()}{os.sep}".lower()
    for p, args in _edges():
        if any(a.startswith(marca) for a in args):
            try:
                p.kill()
            except psutil.Error:
                pass


class Cdp:
    """Conversa com o Edge pelo protocolo do DevTools (um websocket, várias páginas pelo sessionId)."""

    def __init__(self, url):
        self.ws = websocket.create_connection(url, timeout=60, suppress_origin=True, enable_multithread=True)
        self.ws.settimeout(None)  # o timeout acima vale só para conectar: ler espera o tempo que for
        self.ids = itertools.count(1)
        self.esperando = {}
        self.eventos = queue.Queue()
        self.vivo = True
        threading.Thread(target=self._ler, name="kick-cdp", daemon=True).start()

    def _ler(self):
        while True:
            try:
                msg = json.loads(self.ws.recv())
            except Exception as e:  # conexão fechou (o Edge fechou)
                self.vivo = False
                for ev, caixa in list(self.esperando.values()):
                    caixa.append({"error": {"message": f"o Edge fechou ({e.__class__.__name__})"}})
                    ev.set()
                self.eventos.put(None)
                return
            if "id" in msg:
                par = self.esperando.pop(msg["id"], None)
                if par:
                    par[1].append(msg)
                    par[0].set()
            else:
                self.eventos.put(msg)

    def enviar(self, metodo, params=None, sessao=None, timeout=30):
        if not self.vivo:
            raise ErroKick("o Edge das lives fechou")
        i = next(self.ids)
        ev, caixa = threading.Event(), []
        self.esperando[i] = (ev, caixa)
        msg = {"id": i, "method": metodo, "params": params or {}}
        if sessao:
            msg["sessionId"] = sessao
        try:
            self.ws.send(json.dumps(msg))
        except Exception as e:
            self.esperando.pop(i, None)
            raise ErroKick(f"o Edge das lives não respondeu ({e.__class__.__name__})")
        if not ev.wait(timeout):
            self.esperando.pop(i, None)
            raise ErroKick(f"o Edge das lives demorou para responder ({metodo})")
        r = caixa[0]
        if "error" in r:
            raise ErroKick(f"{metodo}: {r['error'].get('message')}")
        return r.get("result", {})

    def avaliar(self, sessao, expressao, timeout=40):
        r = self.enviar("Runtime.evaluate", {"expression": expressao, "awaitPromise": True, "returnByValue": True}, sessao, timeout)
        if "exceptionDetails" in r:
            det = r["exceptionDetails"]
            raise ErroKick(str((det.get("exception") or {}).get("description") or det.get("text"))[:200])
        return r.get("result", {}).get("value")

    def fechar(self):
        self.vivo = False
        try:
            self.ws.close()
        except Exception:
            pass


class ErroKick(Exception):
    pass


def menor_qualidade(lista):
    """A lista principal do vídeo (.m3u8) só com a qualidade de menor banda que tem imagem: o player nem tem
    como subir. None se não tiver pelo menos duas para escolher."""
    linhas = lista.replace("\r\n", "\n").split("\n")
    if not linhas or not linhas[0].startswith("#EXTM3U"):
        return None
    fixas, variantes = [], []
    i = 0
    while i < len(linhas):
        linha = linhas[i]
        if linha.startswith("#EXT-X-STREAM-INF:") and i + 1 < len(linhas):
            banda = re.search(r"(?<![-A-Z])BANDWIDTH=(\d+)", linha)
            variantes.append((int(banda.group(1)) if banda else 0, "RESOLUTION=" in linha, linha, linhas[i + 1]))
            i += 2
            continue
        if linha:
            fixas.append(linha)
        i += 1
    com_imagem = [v for v in variantes if v[1]] or variantes
    if len(com_imagem) < 2:
        return None
    menor = min(com_imagem, key=lambda v: v[0])
    return "\n".join(fixas + [menor[2], menor[3]]) + "\n"


class Edge:
    """O Edge de uma conta. visivel=True abre uma janela normal (para a pessoa entrar na Kick)."""

    def __init__(self, perfil):
        self.perfil = perfil
        self.proc = None
        self.cdp = None
        self.pids = set()
        self.qualidade_cortada = 0

    def abrir(self, visivel=False, url="about:blank"):
        exe = _edge()
        if exe is None:
            raise ErroKick(plataforma.TEXTO_SEM_NAVEGADOR)
        self.perfil.mkdir(parents=True, exist_ok=True)
        for p in _processos_do_perfil(self.perfil):  # sobra de antes com esse perfil
            try:
                p.kill()
            except psutil.Error:
                pass
        porta = self.perfil / "DevToolsActivePort"
        porta.unlink(missing_ok=True)
        args = [
            exe, f"--user-data-dir={self.perfil}", "--remote-debugging-port=0", "--no-first-run",
            "--no-default-browser-check", "--hide-crash-restore-bubble", "--autoplay-policy=no-user-gesture-required",
            # A live escondida tem que continuar "na tela" para o navegador, senão ele segura o vídeo.
            "--disable-backgrounding-occluded-windows", "--disable-renderer-backgrounding",
            "--disable-background-timer-throttling", f"--disable-features={plataforma.OCLUSAO},Translate",
        ]
        if visivel:
            args += ["--window-size=1100,820"]
        else:
            # Em inglês, como as páginas da Kick: o Edge escondido não oferece "Traduzir a página?" (o aviso dele
            # aparecia no canto da tela, porque a janela fica fora dela).
            args += ["--mute-audio", "--window-position=-32000,-32000", "--window-size=320,200", "--lang=en-US",
                     "--accept-lang=en-US,en", *LEVE]
        self.proc = subprocess.Popen(args + [url])
        plataforma.amarrar_ao_app(self.proc)
        fim = time.time() + 30
        while time.time() < fim:
            if self.proc.poll() is not None and not _processos_do_perfil(self.perfil):
                raise ErroKick("o Edge fechou logo depois de abrir")
            try:
                partes = porta.read_text(encoding="utf-8").split()
            except OSError:
                partes = []
            if len(partes) >= 2:
                self.cdp = Cdp(f"ws://127.0.0.1:{partes[0]}{partes[1]}")
                break
            time.sleep(0.3)
        else:
            self.fechar()
            raise ErroKick("o Edge não abriu a tempo")
        self._achar_pids()
        if not visivel:
            self._cortar_qualidade()

    def abrir_login(self, url, *outras):
        """Edge normal, visível e sem DevTools, para a pessoa entrar na Kick (com e-mail ou com o Google)."""
        exe = _edge()
        if exe is None:
            raise ErroKick(plataforma.TEXTO_SEM_NAVEGADOR)
        self.perfil.mkdir(parents=True, exist_ok=True)
        for p in _processos_do_perfil(self.perfil):
            try:
                p.kill()
            except psutil.Error:
                pass
        self.proc = subprocess.Popen([exe, f"--user-data-dir={self.perfil}", "--no-first-run", "--no-default-browser-check",
                                      "--disable-background-mode", "--window-size=1100,820", url, *outras])
        plataforma.amarrar_ao_app(self.proc)

    def janelas(self):
        self._achar_pids()
        return plataforma.janelas_de(self.pids) if self.pids else []

    def fechar_janelas(self):
        """Fecha como se a pessoa clicasse no X: o Edge grava o login no disco antes de sair."""
        self._achar_pids()
        plataforma.fechar_janelas(self.pids)

    def esperar_sair(self, segundos):
        fim = time.time() + segundos
        while time.time() < fim and _processos_do_perfil(self.perfil):
            time.sleep(0.5)
        for p in _processos_do_perfil(self.perfil):
            try:
                p.kill()
            except psutil.Error:
                pass
        self.proc = None

    def _achar_pids(self):
        self.pids = {p.pid for p in _processos_do_perfil(self.perfil, so_navegador=True)}
        if self.proc:
            self.pids.add(self.proc.pid)

    def vivo(self):
        return self.cdp is not None and self.cdp.vivo

    def _cortar_qualidade(self):
        """Pega a lista principal do vídeo das lives (Amazon IVS, usado pela Kick) e entrega só a menor qualidade."""
        self.cdp.enviar("Fetch.enable", {"patterns": [
            {"urlPattern": "*playback.live-video.net/api/video/v1/*", "requestStage": "Response"}]})
        threading.Thread(target=self._tratar_eventos, name="kick-qualidade", daemon=True).start()

    def _tratar_eventos(self):
        cdp = self.cdp
        while True:
            ev = cdp.eventos.get()
            if ev is None:
                return
            if ev.get("method") != "Fetch.requestPaused":
                continue
            p, sessao = ev["params"], ev.get("sessionId")
            pedido = p["requestId"]
            try:
                if p.get("responseStatusCode") == 200 and ".m3u8" in p["request"]["url"]:
                    corpo = cdp.enviar("Fetch.getResponseBody", {"requestId": pedido}, sessao)
                    texto = corpo.get("body", "")
                    if corpo.get("base64Encoded"):
                        texto = base64.b64decode(texto).decode("utf-8", "replace")
                    nova = menor_qualidade(texto)
                    if nova:
                        cabecalhos = [h for h in p.get("responseHeaders") or []
                                      if h["name"].lower() not in ("content-length", "content-encoding")]
                        cdp.enviar("Fetch.fulfillRequest", {
                            "requestId": pedido, "responseCode": 200, "responseHeaders": cabecalhos,
                            "body": base64.b64encode(nova.encode("utf-8")).decode("ascii")}, sessao)
                        self.qualidade_cortada += 1
                        continue
                cdp.enviar("Fetch.continueResponse" if "responseStatusCode" in p else "Fetch.continueRequest",
                           {"requestId": pedido}, sessao)
            except Exception:  # qualquer problema: deixa o pedido seguir normal
                try:
                    cdp.enviar("Fetch.continueRequest", {"requestId": pedido}, sessao, timeout=5)
                except ErroKick:
                    pass

    def token(self):
        """O login da Kick guardado no perfil: o cookie session_token, que o site manda como "Bearer"."""
        for c in self.cdp.enviar("Storage.getCookies").get("cookies", []):
            if c.get("name") == "session_token" and c.get("domain", "").lstrip(".").endswith("kick.com") and c.get("value"):
                return urllib.parse.unquote(c["value"])
        return None

    def paginas(self):
        return [t for t in self.cdp.enviar("Target.getTargets").get("targetInfos", []) if t.get("type") == "page"]

    def ligar_na(self, alvo):
        return self.cdp.enviar("Target.attachToTarget", {"targetId": alvo, "flatten": True})["sessionId"]

    def nova_janela(self, url, bounds=None):
        alvo = self.cdp.enviar("Target.createTarget", {"url": url, "newWindow": True, "background": True})["targetId"]
        sessao = self.ligar_na(alvo)
        self.posicionar(alvo, bounds or FORA_DA_TELA)
        return alvo, sessao

    def esperar_pagina(self, sessao, prefixo, segundos=40):
        """Espera a página terminar de abrir no endereço certo (antes disso o código dela some na navegação)."""
        fim = time.time() + segundos
        while time.time() < fim:
            try:
                estado = self.cdp.avaliar(sessao, "document.readyState + '|' + location.href", timeout=10) or ""
                if estado.startswith("complete|" + prefixo):
                    return True
            except ErroKick:
                pass  # trocou de página no meio: tenta de novo
            time.sleep(1)
        return False

    def posicionar(self, alvo, bounds):
        try:
            janela = self.cdp.enviar("Browser.getWindowForTarget", {"targetId": alvo})["windowId"]
            self.cdp.enviar("Browser.setWindowBounds", {"windowId": janela, "bounds": bounds})
        except ErroKick:
            pass

    def fechar_pagina(self, alvo):
        try:
            self.cdp.enviar("Target.closeTarget", {"targetId": alvo}, timeout=10)
        except ErroKick:
            pass

    def esconder_da_barra(self):
        try:
            plataforma.tirar_da_barra(self.pids)
        except OSError:
            pass

    def fechar(self):
        if self.cdp is not None and self.cdp.vivo:
            try:
                self.cdp.enviar("Browser.close", timeout=5)
            except ErroKick:
                pass
        if self.cdp is not None:
            self.cdp.fechar()
        fim = time.time() + 6
        while time.time() < fim and _processos_do_perfil(self.perfil):
            time.sleep(0.3)
        for p in _processos_do_perfil(self.perfil):
            try:
                p.kill()
            except psutil.Error:
                pass
        self.cdp = None
        self.proc = None


def js(modelo, dados):
    """O código de uma página com os dados no lugar de __DADOS__ (o código tem "%", então nada de formatação com %)."""
    return modelo.replace("__DADOS__", json.dumps(dados))


def canais_da_twitch(cfg, login, ja_tem):
    """Os canais da lista da Twitch desta conta, com o nome que usam na Kick, que ainda não estão na lista da Kick."""
    novos = []
    for canal in (cfg.conta(login) or {}).get("channels", []):
        nome = config.kick_da_twitch(canal)
        if nome and nome not in ja_tem and nome not in novos:
            novos.append(nome)
    return novos


# Código que roda dentro das páginas da Kick (como o próprio site faz).
JS_AO_VIVO = """(async todos => {
  const out = {};
  for (let i = 0; i < todos.length; i += 6) await Promise.all(todos.slice(i, i + 6).map(async c => {
    try {
      const r = await fetch('/api/v2/channels/' + encodeURIComponent(c), {headers: {Accept: 'application/json'}, cache: 'no-store'});
      if (r.status === 404) { out[c] = {ao_vivo: false, existe: false}; return; }
      if (!r.ok) { out[c] = {erro: r.status}; return; }
      const l = (await r.json()).livestream;
      out[c] = {ao_vivo: !!(l && l.is_live !== false), viewers: l ? l.viewer_count : 0,
                titulo: l ? l.session_title : null, jogo: l && l.categories && l.categories[0] ? l.categories[0].name : null};
    } catch (e) { out[c] = {erro: String(e).slice(0, 120)}; }
  }));
  return out;
})(__DADOS__)"""

JS_PLAYER = """(() => {
  const v = document.querySelector('video');
  if (!v) return {video: false};
  if (v.paused) v.play().catch(() => {});
  return {video: true, t: v.currentTime, pausado: v.paused, pronto: v.readyState, w: v.videoWidth};
})()"""

JS_USUARIO = """(async token => {
  const r = await fetch('/api/v1/user', {headers: {Accept: 'application/json', Authorization: 'Bearer ' + token}, cache: 'no-store'});
  if (!r.ok) return null;
  const j = await r.json();
  return j.username || (j.user && j.user.username) || j.slug || null;
})(__DADOS__)"""

JS_SEGUE = """(async a => {
  const r = await fetch('/api/v2/channels/' + encodeURIComponent(a.canal) + '/me', {cache: 'no-store',
    headers: {Accept: 'application/json', 'x-app-platform': 'web', Authorization: 'Bearer ' + a.token}});
  if (!r.ok) return {erro: r.status};
  const j = await r.json();
  return {segue: !!(j.is_following ?? (j.data && j.data.is_following))};
})(__DADOS__)"""

JS_LOJA = """(async a => {
  const base = '/api/v2/channels/' + encodeURIComponent(a.canal);
  const h = {Accept: 'application/json', 'x-app-platform': 'web', Authorization: 'Bearer ' + a.token};
  let r = await fetch(base + '/points', {cache: 'no-store', headers: h});
  if (r.status === 401) return {erro: 401};
  const saldo = r.ok ? (await r.json())?.data?.points : null;
  r = await fetch(base + '/rewards', {cache: 'no-store', headers: h});
  if (!r.ok) return {erro: 'a Kick respondeu ' + r.status, saldo};
  const recompensas = ((await r.json())?.data || []).map(x => ({id: String(x.id), titulo: x.title || '', custo: x.cost,
    descricao: x.description || '', cor: x.background_color || null, ativa: !!x.is_enabled, pausada: !!x.is_paused,
    pede_texto: !!x.is_user_input_required}));
  return {saldo: typeof saldo === 'number' ? saldo : null, recompensas};
})(__DADOS__)"""

JS_ULID = """const abc = '0123456789ABCDEFGHJKMNPQRSTVWXYZ'; let t = Date.now(), tid = '';
  for (let i = 0; i < 10; i++) { tid = abc[t % 32] + tid; t = Math.floor(t / 32); }
  for (let i = 0; i < 16; i++) tid += abc[Math.floor(Math.random() * 32)];"""

JS_RESGATAR = """(async a => {
  const h = {Accept: 'application/json', 'x-app-platform': 'web', Authorization: 'Bearer ' + a.token, 'Content-Type': 'application/json'};
  __ULID__
  const r = await fetch('/api/v2/channels/' + encodeURIComponent(a.canal) + '/rewards/' + a.id + '/redeem',
    {method: 'POST', headers: h, body: JSON.stringify({transaction_id: tid, message: ''})});
  let det = '';
  try { det = (await r.text()).slice(0, 200); } catch (e) {}
  return {ok: r.ok, status: r.status, det};
})(__DADOS__)""".replace("__ULID__", JS_ULID)

# Compra automática: saldo, as recompensas das famílias ligadas (mesmo nome sem as horas) e compra uma atrás da
# outra (3 s entre elas) a de melhor preço por hora que o saldo paga, até o saldo acabar (no máximo 10 por vez).
JS_AUTO = r"""(async a => {
  const base = '/api/v2/channels/' + encodeURIComponent(a.canal);
  const h = {Accept: 'application/json', 'x-app-platform': 'web', Authorization: 'Bearer ' + a.token};
  let r = await fetch(base + '/points', {cache: 'no-store', headers: h});
  if (!r.ok) return {erro: 'saldo: a Kick respondeu ' + r.status};
  let saldo = (await r.json())?.data?.points;
  if (typeof saldo !== 'number') return {erro: 'saldo: a resposta veio sem os pontos'};
  const antes = saldo;
  if (!a.familias.length) return {pontos: saldo, antes};
  r = await fetch(base + '/rewards', {cache: 'no-store', headers: h});
  if (!r.ok) return {pontos: saldo, antes, erro: 'recompensas: a Kick respondeu ' + r.status};
  const familia = t => (t || '').replace(/\(\s*\d+\s*h\s*\)/i, '').trim().toLowerCase();
  const horas = x => { const m = /\(\s*(\d+)\s*h\s*\)/i.exec(x.title || ''); return m ? Number(m[1]) : 1; };
  const lista = ((await r.json())?.data || []).filter(x => x.is_enabled && !x.is_paused && !x.is_user_input_required
    && a.familias.includes(familia(x.title)) && !a.evitar.includes(String(x.id)));
  const feitas = [];
  for (let n = 0; n < a.max; n++) {
    const cabem = lista.filter(x => x.cost <= saldo).sort((x, y) => (x.cost / horas(x)) - (y.cost / horas(y)) || y.cost - x.cost);
    if (!cabem.length) break;
    const x = cabem[0];
    __ULID__
    const q = await fetch(base + '/rewards/' + x.id + '/redeem', {method: 'POST',
      headers: {...h, 'Content-Type': 'application/json'}, body: JSON.stringify({transaction_id: tid, message: ''})});
    let det = '';
    try { det = (await q.text()).slice(0, 160); } catch (e) {}
    if (!q.ok) { feitas.push({ok: false, status: q.status, id: String(x.id), titulo: x.title, det}); break; }
    feitas.push({ok: true, id: String(x.id), titulo: x.title, custo: x.cost, antes: saldo});
    saldo -= x.cost;
    await new Promise(z => setTimeout(z, 3000));
  }
  return {pontos: saldo, antes, feitas, tem: lista.length};
})(__DADOS__)""".replace("__ULID__", JS_ULID)

def apagar_perfil(pasta):
    """Apaga o perfil da Kick (o login). O Edge pode demorar um instante para soltar os arquivos."""
    for _ in range(10):
        shutil.rmtree(pasta, ignore_errors=True)
        if not pasta.exists():
            return
        time.sleep(0.5)


class ContaKick:
    """O motor da Kick de uma conta: um Edge escondido e as lives tocando nele."""

    def __init__(self, cfg, login, liberada, premium=None, pedido=None):
        self.cfg = cfg
        self.login = login
        self.liberada = liberada
        self.premium = premium or (lambda: True)
        self.parar = threading.Event()  # a conta saiu do app: o motor termina
        self.pular = {}  # canal -> até quando não abrir (recarregou 3 vezes e não tocou/não rendeu)
        self.ganhos_vez = {}  # canal -> [(quando, pontos)] da última hora: quanto cada live rendeu
        self.leituras_vez = {}  # canal -> [quando] da última hora em que deu para ler o saldo dele
        self.recusas = 0  # conferências seguidas que a Kick recusou (espera mais a cada vez)
        self.perfil = _pasta_kick() / login
        self.lock = threading.RLock()
        self.acordar = threading.Event()
        self.pedidos = queue.Queue()
        self.edge = None
        self.modo = "farm"  # farm | entrando (login) | seguindo (a pessoa segue os canais numa janela normal)
        self.ultimo_ganho = {}  # canal -> quando ganhou ponto pela última vez
        self.sem_login = False
        self.estado = "desligada"
        self.erro = None
        self.aviso = None
        self.token = None
        self.ctrl = None  # sessão da página de controle (kick.com/robots.txt)
        self.lives = {}  # canal -> {"alvo", "sessao", "t", "parada", "tocando", "aberta_em"}
        self.ao_vivo = {}  # canal -> {"ao_vivo", "viewers", ...}
        self.saldos = {}  # canal -> pontos
        self.trazidos = set()  # canais que vieram da lista da Twitch e ainda não foram conferidos na Kick
        self.sem_kick = 0  # quantos canais da Twitch não tinham canal com o mesmo nome na Kick (saíram da lista)
        self.ganho_canal = {}  # canal -> pontos juntados desde que o app abriu
        self.seguidos_em = 0  # última conferência de quem a conta segue na Kick
        self.ganho = 0
        self.resgates = []  # [{canal, titulo, custo, antes, ts}] da última hora, para notar devolução
        self.ultimo_resgate = None
        self.evitar = {}  # id da recompensa -> até quando não tentar de novo
        self.resgate_pausado = False
        self.mostrando = False
        self.tempos = {"lives": 0, "player": 0, "saldo": 0}
        self.entrar_ate = 0
        self.viu_janela = False
        self.conferir_login = False
        if pedido:  # antes do motor começar: o primeiro passo dele já é esse pedido
            self.pedidos.put(pedido)
        self.thread = threading.Thread(target=self._rodar, name=f"kick-{login}", daemon=True)
        self.thread.start()

    # --- pedidos do painel ---
    def pedir(self, acao, valor=None):
        self.pedidos.put((acao, valor))
        self.acordar.set()

    def lives_max(self, conf):
        """Quantas lives ao mesmo tempo: a escolha da pessoa (1 a 4); no grátis, 1 (como na Twitch)."""
        n = max(1, min(LIVES_MAX, int(conf.get("lives") or 2)))
        return n if self.premium() else 1

    def prioridade(self, conf):
        """A ordem para escolher as lives: os favoritos (na ordem da lista) e depois os outros."""
        favoritos = [c for c in conf["canais"] if c in (conf.get("favoritos") or [])]
        return favoritos + [c for c in conf["canais"] if c not in favoritos]

    def trazer_twitch(self):
        """Põe na lista da Kick os canais da lista da Twitch desta conta (com o nome que eles usam na Kick). Os que
        não existem na Kick saem sozinhos na próxima conferência. Devolve quantos entraram."""
        conf = self.cfg.kick(self.login)
        novos = canais_da_twitch(self.cfg, self.login, conf["canais"])
        self.cfg.definir_kick(self.login, canais=conf["canais"] + novos, trouxe_twitch=True)
        with self.lock:
            self.trazidos |= set(novos)
            self.tempos["lives"] = 0
        return len(novos)

    def ver(self):
        with self.lock:
            conf = self.cfg.kick(self.login)
            canais = []
            favoritos = set(conf.get("favoritos") or [])
            seguidos = set(conf.get("seguidos") or [])
            for canal in conf["canais"]:
                live = self.lives.get(canal)
                info = self.ao_vivo.get(canal) or {}
                canais.append({
                    "canal": canal,
                    "ao_vivo": info.get("ao_vivo"),
                    "existe": info.get("existe", True),
                    "viewers": info.get("viewers"),
                    "jogo": info.get("jogo"),
                    "assistindo": live is not None,
                    "tocando": bool(live and live.get("tocando")),
                    "rendendo": self._rendendo(canal, live),
                    "saldo": self.saldos.get(canal),
                    "ganho": self.ganho_canal.get(canal, 0),
                    "favorito": canal in favoritos,
                    "seguido": canal in seguidos,
                })
            return {
                "ligada": conf["ligada"],
                "estado": self.estado,
                "usuario": conf.get("usuario"),
                "canais": canais,
                "auto": list(conf.get("auto") or []),
                "sem_kick": self.sem_kick,
                "lives": self.lives_max(conf),
                "seguindo": list(getattr(self, "seguindo", [])) if self.modo == "seguindo" else [],
                "resgate_pausado": self.resgate_pausado,
                "ultimo_resgate": self.ultimo_resgate,
                "ganho": self.ganho,
                "erro": self.erro,
                "aviso": self.aviso,
                "mostrando": self.mostrando,
            }

    def _rendendo(self, canal, live):
        """True: ganhou ponto nos últimos 12 min. False: aberta há mais de 12 min sem ganhar. None: cedo para saber."""
        if live is None:
            return None
        agora = time.time()
        if agora - self.ultimo_ganho.get(canal, 0) < RENDE_JANELA:
            return True
        return False if agora - live.get("desde", live["aberta_em"]) > RENDE_JANELA else None

    # --- o motor ---
    def _rodar(self):
        while not self.parar.is_set():
            try:
                self._volta()
            except Exception as e:  # nunca derruba o motor: mostra o erro, fecha o Edge e tenta de novo
                log.warning("kick %s: %s", self.login, e, exc_info=not isinstance(e, ErroKick))
                with self.lock:
                    self.erro = str(e) if isinstance(e, ErroKick) else f"erro inesperado ({e.__class__.__name__})"
                    self.estado = "erro"
                self._fechar_edge()
                self.acordar.wait(60)
            self.acordar.wait(PASSO)
            self.acordar.clear()
        self._fechar_edge()

    def _volta(self):
        conta = self.cfg.conta(self.login)
        conf = self.cfg.kick(self.login)
        self._tratar_pedidos(conf)
        if _encerrando.is_set() or self.parar.is_set() or conta is None or not conf["ligada"]:
            self._parar("desligada")
            return
        if conta.get("paused"):
            self._parar("pausada")
            return
        if not self.liberada(self.login):
            self._parar("bloqueada")
            return
        if not conf.get("trouxe_twitch"):
            self.trazer_twitch()
            conf = self.cfg.kick(self.login)
        if self.modo in ("entrando", "seguindo"):
            self._esperar_login()
            return
        if self.sem_login:
            self._parar("sem_login")
            return
        if self.edge is None or not self.edge.vivo():
            if self.edge is not None:
                self._fechar_edge()
            self._ligar_farm()
            if self.edge is None:
                return
        self._farmar(conf)

    def _tratar_pedidos(self, conf):
        while True:
            try:
                acao, valor = self.pedidos.get_nowait()
            except queue.Empty:
                return
            if acao == "entrar":
                self._abrir_login()
            elif acao == "sair":
                self._fechar_edge()
                apagar_perfil(self.perfil)
                self.cfg.definir_kick(self.login, usuario=None)
                with self.lock:
                    self.sem_login, self.token, self.saldos, self.ganho = True, None, {}, 0
                    self.ultimo_resgate = None
            elif acao == "mostrar":
                with self.lock:
                    self.mostrando = bool(valor)
                self._posicionar_lives()
            elif acao == "seguir":
                self._abrir_seguir(valor)
            elif acao == "pronto" and self.modo in ("entrando", "seguindo"):
                self._esperar_login(pronto=True)
            elif acao == "conferir":  # a lista de canais mudou: confere quem está ao vivo agora
                self.tempos["lives"] = 0
            elif acao == "seguidos":  # a pessoa foi seguir no navegador: confere já
                self.seguidos_em = 0
            elif acao == "religar":
                with self.lock:
                    self.resgate_pausado = False
                    self.aviso = None
                    self.evitar.clear()

    def _parar(self, estado):
        if self.edge is not None:
            self._fechar_edge()
        with self.lock:
            self.estado = estado
            if estado != "sem_login":
                self.erro = None

    def _fechar_edge(self):
        edge, self.edge = self.edge, None
        with self.lock:
            self.lives, self.ctrl = {}, None
        if edge is not None:
            try:
                edge.fechar()
            except Exception:
                log.debug("kick %s: fechando o Edge", self.login, exc_info=True)

    # --- login (janela normal, a própria pessoa entra) ---
    def _abrir_login(self):
        if _encerrando.is_set() or self.parar.is_set():
            return
        self._fechar_edge()
        with self.lock:
            self.modo, self.estado, self.erro, self.aviso = "entrando", "entrando", None, None
        self.entrar_ate = time.time() + ENTRAR_MAX
        self.viu_janela = False
        self.edge = Edge(self.perfil)
        try:
            self.edge.abrir_login(f"{KICK}/")
        except ErroKick as e:
            with self.lock:
                self.modo, self.estado, self.erro = "farm", "erro", str(e)
            self.edge = None

    def _abrir_seguir(self, canais):
        """Abre os canais que faltam seguir num Edge normal desta conta (já logado na Kick dela)."""
        conf = self.cfg.kick(self.login)
        seguidos = set(conf.get("seguidos") or [])
        canais = [c for c in (canais or conf["canais"]) if c in conf["canais"] and c not in seguidos
                  and (self.ao_vivo.get(c) or {}).get("existe") is not False][:20]
        if not canais or _encerrando.is_set() or self.parar.is_set():
            return
        self._fechar_edge()
        with self.lock:
            self.modo, self.estado, self.erro = "seguindo", "seguindo", None
            self.seguindo = canais
        self.entrar_ate = time.time() + ENTRAR_MAX
        self.viu_janela = False
        self.edge = Edge(self.perfil)
        try:
            self.edge.abrir_login(*[f"{KICK}/{c}" for c in canais])
        except ErroKick as e:
            with self.lock:
                self.modo, self.estado, self.erro = "farm", "erro", str(e)
            self.edge = None

    def _esperar_login(self, pronto=False):
        """Espera a pessoa fechar a janela de login (ou clicar em "Já entrei" no painel)."""
        edge = self.edge
        abertas = edge.janelas() if edge is not None else []
        if abertas:
            self.viu_janela = True
        acabou = (edge is None or pronto or time.time() > self.entrar_ate
                  or (self.viu_janela and not abertas) or not _processos_do_perfil(self.perfil))
        if not acabou:
            return
        if edge is not None:
            edge.fechar_janelas()
            edge.esperar_sair(15)
        self.edge = None
        era_login = self.modo == "entrando"
        log.info("kick %s: a janela da Kick fechou (%s)", self.login, "login" if era_login else "seguir")
        with self.lock:
            self.modo, self.sem_login, self.estado = "farm", False, "iniciando"
            self.conferir_login = era_login  # se não achar o login, explica no painel
            self.seguidos_em = 0  # confere já quem a conta segue
            self.tempos = {"lives": 0, "player": 0, "saldo": 0}

    # --- farm ---
    def _ligar_farm(self):
        if _encerrando.is_set() or self.parar.is_set():
            return
        with self.lock:
            self.estado = "iniciando"
        self.edge = Edge(self.perfil)
        self.edge.abrir(visivel=False)
        token = self.edge.token()
        if not token:
            self._fechar_edge()
            with self.lock:
                self.sem_login, self.token, self.estado = True, None, "sem_login"
                if self.conferir_login:
                    self.aviso = ("Não achamos o login da Kick. Clique em Entrar na Kick, entre na sua conta e só "
                                  "depois feche a janela.")
                self.conferir_login = False
            return
        if self.conferir_login:
            log.info("kick %s: entrou na Kick", self.login)
            with self.lock:
                self.conferir_login, self.aviso = False, None
        with self.lock:
            self.token = token
            self.tempos = {"lives": 0, "player": 0, "saldo": 0}
        primeira = next((p for p in self.edge.paginas()), None)
        if primeira is None:
            alvo, sessao = self.edge.nova_janela(f"{KICK}/robots.txt")
        else:
            sessao = self.edge.ligar_na(primeira["targetId"])
            self.edge.cdp.enviar("Page.navigate", {"url": f"{KICK}/robots.txt"}, sessao)
        self.ctrl = sessao
        self.edge.esperar_pagina(sessao, f"{KICK}/robots.txt", 30)
        self.edge.esconder_da_barra()
        if not self.cfg.kick(self.login).get("usuario"):
            try:
                usuario = self.edge.cdp.avaliar(self.ctrl, js(JS_USUARIO, token), timeout=20)
                if usuario:
                    self.cfg.definir_kick(self.login, usuario=str(usuario)[:40])
            except ErroKick:
                pass
        log.info("kick %s: Edge das lives ligado", self.login)

    def _farmar(self, conf):
        agora = time.time()
        edge = self.edge
        if agora - self.tempos["lives"] >= CONFERIR_LIVES:
            self.tempos["lives"] = agora
            self._conferir_ao_vivo(conf["canais"])
            conf = self.cfg.kick(self.login)  # sem os da Twitch que não existem na Kick
        escolhidas = []
        self.pular = {c: ate for c, ate in self.pular.items() if ate > agora}
        self._dar_a_vez(conf, agora)
        for canal in self.prioridade(conf):
            if canal in self.pular:
                continue
            info = self.ao_vivo.get(canal) or {}
            # Sem resposta da Kick agora: a live que já está aberta continua (não perde os pontos dela).
            if info.get("ao_vivo") or (info.get("ao_vivo") is None and canal in self.lives):
                escolhidas.append(canal)
            if len(escolhidas) >= self.lives_max(conf):
                break
        for canal in [c for c in self.lives if c not in escolhidas]:
            edge.fechar_pagina(self.lives[canal]["alvo"])
            with self.lock:
                self.lives.pop(canal, None)
            log.info("kick %s: fechou a live de %s", self.login, canal)
        for i, canal in enumerate(escolhidas):
            if canal not in self.lives:
                alvo, sessao = edge.nova_janela(f"https://player.kick.com/{canal}", self._lugar(i))
                with self.lock:
                    self.lives[canal] = {"alvo": alvo, "sessao": sessao, "t": None, "parada": 0, "tocando": False,
                                         "aberta_em": agora}
                log.info("kick %s: abriu a live de %s", self.login, canal)
        if self.lives and not self.mostrando:
            edge.esconder_da_barra()
        if agora - self.tempos["player"] >= CONFERIR_PLAYER:
            self.tempos["player"] = agora
            self._conferir_players()
        if agora - self.tempos["saldo"] >= CONFERIR_SALDO:
            self.tempos["saldo"] = agora
            self._conferir_saldos(conf)
        if agora - self.seguidos_em >= CONFERIR_SEGUIDOS:
            self._conferir_seguidos(conf)
        with self.lock:
            if self.estado != "farmando" or self.erro:
                self.estado, self.erro = "farmando", None

    def _dar_a_vez(self, conf, agora):
        """A live aberta há 30 min ou mais que rendeu menos da metade do normal nesse tempo sai por 30 min, se tiver
        outra live no ar esperando vaga (a Kick às vezes para de pagar um canal e só pinga um ponto ou outro)."""
        esperando = [c for c in self.prioridade(conf) if c not in self.lives and c not in self.pular
                     and (self.ao_vivo.get(c) or {}).get("ao_vivo")]
        if not esperando:
            return
        for canal, live in list(self.lives.items()):
            if agora - live["aberta_em"] < TESTE_RENDE:
                continue
            rendeu = sum(p for quando, p in self.ganhos_vez.get(canal, []) if agora - quando <= TESTE_RENDE)
            lidas = sum(1 for quando in self.leituras_vez.get(canal, []) if agora - quando <= TESTE_RENDE)
            if rendeu >= RENDE_MINIMO or lidas < 5:  # sem ler o saldo (a Kick recusou) não dá para saber: fica
                continue
            log.info("kick %s: %s rendeu só %s pontos em 30 min; dá a vez para %s por 30 min",
                     self.login, canal, rendeu, esperando[0])
            with self.lock:
                self.pular[canal] = agora + 1800
            esperando.pop(0)
            if not esperando:
                return

    def _conferir_seguidos(self, conf):
        """Confere quais canais da lista a conta já segue (quem segue ganha 50 pontos uma vez em cada canal)."""
        self.seguidos_em = time.time()
        if self.ctrl is None or not self.token:
            return
        seguidos = set(conf.get("seguidos") or [])
        novos = set()
        for canal in conf["canais"]:
            if canal in seguidos or (self.ao_vivo.get(canal) or {}).get("existe") is False:
                continue
            try:
                r = self.edge.cdp.avaliar(self.ctrl, js(JS_SEGUE, {"canal": canal, "token": self.token}), timeout=20) or {}
            except ErroKick:
                return
            if r.get("segue"):
                novos.add(canal)
        if novos:
            self.cfg.definir_kick(self.login, seguidos=sorted(seguidos | novos))
            log.info("kick %s: segue na Kick: %s", self.login, ", ".join(sorted(novos)))

    def _lugar(self, i):
        if not self.mostrando:
            return FORA_DA_TELA
        return {"left": 40 + i * 660, "top": 60, "width": 640, "height": 400, "windowState": "normal"}

    def _posicionar_lives(self):
        if self.edge is None or not self.edge.vivo():
            return
        for i, live in enumerate(list(self.lives.values())):
            self.edge.posicionar(live["alvo"], self._lugar(i))

    def _conferir_ao_vivo(self, canais):
        if not canais or self.ctrl is None:
            return
        resposta = self.edge.cdp.avaliar(self.ctrl, js(JS_AO_VIVO, canais)) or {}
        recusados = [c for c, r in resposta.items() if r.get("erro") in (401, 403, 429)]
        sem_kick = []
        with self.lock:
            for canal, info in resposta.items():
                self.ao_vivo[canal] = {**info, "ao_vivo": info.get("ao_vivo") if "erro" not in info else None}
                if canal in self.trazidos and "erro" not in info:
                    self.trazidos.discard(canal)
                    if info.get("existe") is False:
                        sem_kick.append(canal)
            self.sem_kick += len(sem_kick)
        if sem_kick:  # veio da Twitch e não tem canal com esse nome na Kick: sai da lista
            conf = self.cfg.kick(self.login)
            self.cfg.definir_kick(self.login, canais=[c for c in conf["canais"] if c not in sem_kick])
            log.info("kick %s: sem canal na Kick: %s", self.login, ", ".join(sem_kick))
        if recusados and len(recusados) == len(canais):
            # A Kick barrou as perguntas (verificação de robô ou limite): não força. Avisa e espera cada vez mais
            # (4, 8, 16, até 30 min) antes de perguntar de novo.
            self.recusas += 1
            self.tempos["lives"] = time.time() + min(CONFERIR_LIVES * 2 ** self.recusas, 1800) - CONFERIR_LIVES
            self.aviso = ("A Kick está recusando as conferências agora (proteção do site). O Lunar não força: espera um "
                          "pouco e tenta de novo sozinho.")
            log.info("kick %s: a Kick recusou as conferências (%s seguidas)", self.login, self.recusas)
        else:
            self.recusas = 0
            if self.aviso and self.aviso.startswith("A Kick está recusando"):
                self.aviso = None

    def _conferir_players(self):
        for canal, live in list(self.lives.items()):
            try:
                v = self.edge.cdp.avaliar(live["sessao"], JS_PLAYER, timeout=15) or {}
            except ErroKick:
                v = {}
            andou = v.get("video") and live["t"] is not None and v.get("t", 0) > live["t"] + 1
            primeira = live["t"] is None
            with self.lock:
                live["tocando"] = bool(andou or (primeira and v.get("video") and not v.get("pausado")))
                live["parada"] = 0 if live["tocando"] else live["parada"] + 1
                live["t"] = v.get("t")
            # Tocando, mas sem ganhar ponto há 15 min: recarrega a página dela (a contagem da Kick recomeça).
            agora = time.time()
            desde = max(live.get("desde", live["aberta_em"]), self.ultimo_ganho.get(canal, 0))
            if live["tocando"] and agora - desde > SEM_RENDER:
                if self._desistir(canal, live, "tocou 45 min sem render pontos"):
                    continue
                log.info("kick %s: %s tocou 15 min sem render pontos, recarregando", self.login, canal)
                try:
                    self.edge.cdp.enviar("Page.reload", {"ignoreCache": True}, live["sessao"])
                except ErroKick:
                    pass
                with self.lock:
                    live["t"], live["desde"] = None, agora
                continue
            # Travou 2 conferências seguidas (1 min) depois do primeiro minuto: recarrega a live. Antes, pergunta à
            # Kick quem está ao vivo (na próxima volta): quase sempre a live travou porque acabou, e aí ela só fecha.
            if live["parada"] >= 2 and time.time() - live["aberta_em"] > 60:
                if not live.get("conferiu_ao_vivo"):
                    live["conferiu_ao_vivo"] = True
                    self.tempos["lives"] = 0
                    continue
                live["conferiu_ao_vivo"] = False
                if self._desistir(canal, live, "não tocou depois de 3 recargas"):
                    continue
                log.info("kick %s: a live de %s travou, recarregando", self.login, canal)
                try:
                    self.edge.cdp.enviar("Page.reload", {"ignoreCache": True}, live["sessao"])
                except ErroKick:
                    pass
                with self.lock:
                    live["parada"], live["t"], live["aberta_em"] = 0, None, time.time()

    def _desistir(self, canal, live, motivo):
        """Conta as recargas da live; na 4ª, fecha e deixa o canal de fora por 30 min (a vaga vai para o próximo)."""
        live["recargas"] = live.get("recargas", 0) + 1
        if live["recargas"] <= 3:
            return False
        log.info("kick %s: %s %s; fica de fora por 30 min", self.login, canal, motivo)
        self.edge.fechar_pagina(live["alvo"])
        with self.lock:
            self.lives.pop(canal, None)
            self.pular[canal] = time.time() + 1800
        return True

    def _conferir_saldos(self, conf):
        """De 5 em 5 min as lives abertas e de 15 em 15 min os outros canais: o saldo e, se tiver compra
        automática ligada, compra até os pontos acabarem."""
        if not self.token or self.ctrl is None:
            return
        agora = time.time()
        with self.lock:
            self.resgates = [r for r in self.resgates if agora - r["ts"] < DEVOLUCAO]
            self.evitar = {k: v for k, v in self.evitar.items() if v > agora}
        canais = list(self.lives)
        if agora - self.tempos.get("saldo_todos", 0) >= 3 * CONFERIR_SALDO:
            self.tempos["saldo_todos"] = agora
            canais += [c for c in conf["canais"] if c not in canais and (self.ao_vivo.get(c) or {}).get("existe") is not False]
        familias = [] if self.resgate_pausado or not self.premium() else list(conf.get("auto") or [])
        for canal in canais:
            args = {"canal": canal, "token": self.token, "familias": familias, "max": 10, "evitar": list(self.evitar)}
            try:
                r = self.edge.cdp.avaliar(self.ctrl, js(JS_AUTO, args), timeout=90) or {}
            except ErroKick as e:
                r = {"erro": str(e)}
            if r.get("erro"):
                log.info("kick %s: %s em %s", self.login, r["erro"], canal)
                if "401" in str(r["erro"]):
                    # A Kick pode ter trocado o login: relê o cookie antes de pedir para entrar de novo.
                    try:
                        novo = self.edge.token()
                    except (ErroKick, AttributeError):
                        novo = None
                    if novo and novo != self.token:
                        self.token = novo
                        log.info("kick %s: a Kick renovou o login", self.login)
                        return
                    self._fechar_edge()
                    with self.lock:
                        self.sem_login, self.token, self.estado = True, None, "sem_login"
                    return
            self._anotar_saldo(canal, r, agora)

    def _anotar_saldo(self, canal, r, agora):
        antes, pontos = r.get("antes"), r.get("pontos")
        with self.lock:
            if isinstance(antes, int):
                self.leituras_vez[canal] = [q for q in self.leituras_vez.get(canal, []) if agora - q <= 3600] + [agora]
                anterior = self.saldos.get(canal)
                if anterior is not None and 0 < antes - anterior < 500:
                    self.ultimo_ganho[canal] = agora
                    vez = [g for g in self.ganhos_vez.get(canal, []) if agora - g[0] <= 3600]
                    self.ganhos_vez[canal] = vez + [(agora, antes - anterior)]
                    if canal in self.lives:
                        self.lives[canal]["recargas"] = 0
                    self.ganho += antes - anterior
                    self.ganho_canal[canal] = self.ganho_canal.get(canal, 0) + antes - anterior
                # Devolução: depois de um resgate, o saldo voltou ao de antes (o jogo não aceitou).
                for res in self.resgates:
                    if res["canal"] == canal and res.get("ok") and antes >= res["depois"] + max(res["custo"] // 2, 60):
                        self.resgate_pausado = True
                        self.aviso = ("Os pontos de um resgate na Kick voltaram: a Kick não está vinculada no PokeIdle dessa conta "
                                      "(no jogo, Bônus na Kick). A compra automática da Kick pausou; ligue de novo na Loja.")
                        log.info("kick %s: pontos devolvidos em %s, compra automática pausada", self.login, canal)
                        res["ok"] = False
            for f in r.get("feitas") or []:
                if f.get("ok"):
                    self.ultimo_resgate = {"canal": canal, "titulo": f.get("titulo"), "custo": f.get("custo"), "ts": agora}
                    if isinstance(f.get("antes"), int) and isinstance(f.get("custo"), int):
                        self.resgates.append({"canal": canal, "depois": f["antes"] - f["custo"], "custo": f["custo"],
                                              "ts": agora, "ok": True})
                    log.info("kick %s: comprou %s em %s (%s pontos)", self.login, f.get("titulo"), canal, f.get("custo"))
                else:  # a Kick recusou: não tenta essa recompensa por 30 min
                    self.evitar[f.get("id")] = agora + 1800
                    log.info("kick %s: a Kick recusou a compra em %s (%s %s)", self.login, canal, f.get("status"), f.get("det"))
            if isinstance(pontos, int):
                self.saldos[canal] = pontos

    # --- loja (pedidos do painel) ---
    def _pronta(self):
        """(cdp, sessão de controle, token) do Edge ligado agora, ou ErroKick."""
        with self.lock:
            edge, ctrl, token = self.edge, self.ctrl, self.token
        cdp = getattr(edge, "cdp", None)
        if cdp is None or not cdp.vivo or ctrl is None or not token:
            raise ErroKick("A Kick dessa conta não está ligada agora. Ligue a Kick na página da conta e espere as lives abrirem.")
        return cdp, ctrl, token

    def loja(self, canal):
        cdp, ctrl, token = self._pronta()
        r = cdp.avaliar(ctrl, js(JS_LOJA, {"canal": canal, "token": token}), timeout=30) or {}
        if r.get("erro") == 401:
            raise ErroKick("O login da Kick dessa conta venceu: entre de novo na página da conta.")
        if r.get("erro"):
            raise ErroKick(f"Não deu para abrir a loja: {r['erro']}")
        if isinstance(r.get("saldo"), int):
            with self.lock:
                self.saldos[canal] = r["saldo"]
        return r

    def comprar(self, canal, recompensa, custo=None):
        cdp, ctrl, token = self._pronta()
        antes = self.saldos.get(canal)
        r = cdp.avaliar(ctrl, js(JS_RESGATAR, {"canal": canal, "id": str(recompensa), "token": token}), timeout=30) or {}
        agora = time.time()
        if r.get("ok"):
            with self.lock:
                self.ultimo_resgate = {"canal": canal, "titulo": None, "custo": custo, "ts": agora}
                if isinstance(antes, int) and isinstance(custo, int):
                    self.resgates.append({"canal": canal, "depois": antes - custo, "custo": custo, "ts": agora, "ok": True})
                    self.saldos[canal] = antes - custo
            log.info("kick %s: compra na loja em %s (%s)", self.login, canal, recompensa)
        return r


class Kick:
    """Os motores da Kick de todas as contas."""

    def __init__(self, cfg, liberada, premium=None):
        self.cfg = cfg
        self.liberada = liberada
        self.premium = premium or (lambda: True)
        self.contas = {}
        self.lock = threading.Lock()

    def _conta(self, login, criar=True, pedido=None):
        with self.lock:
            if login not in self.contas and criar:
                self.contas[login] = ContaKick(self.cfg, login, self.liberada, self.premium, pedido)
                return self.contas[login]
            c = self.contas.get(login)
        if c and pedido:
            c.pedir(*pedido)
        return c

    def iniciar(self):
        # Só aqui (o app já é o único aberto, com a porta dele): fecha Edges das lives que sobraram de antes.
        try:
            limpar_sobras()
        except Exception:
            log.debug("kick: limpando sobras", exc_info=True)
        for conta in self.cfg.contas():
            if (conta.get("kick") or {}).get("ligada"):
                self._conta(conta["login"])

    def acordar(self, login=None):
        for login_ in ([login] if login else list(self.contas)):
            c = self._conta(login_, criar=False)
            if c:
                c.acordar.set()

    def configurar(self, login, **mudancas):
        conf = self.cfg.definir_kick(login, **mudancas)
        c = self._conta(login, criar=bool(conf and conf["ligada"]))
        if c:
            if "auto" in mudancas:
                c.pedir("religar")
            if "canais" in mudancas or "favoritos" in mudancas:
                c.pedir("conferir")
            c.acordar.set()
        return conf

    def entrar(self, login):
        conta = self.cfg.conta(login) or {}
        if conta.get("paused"):
            raise ErroKick("Essa conta está pausada. Retome a conta e depois ligue a Kick.")
        if not self.liberada(login):
            raise ErroKick("Na versão grátis só a primeira conta farma, na Twitch e na Kick.")
        self.cfg.definir_kick(login, ligada=True)
        self._conta(login, pedido=("entrar", None))

    def trazer_twitch(self, login):
        c = self._conta(login, criar=False)
        if c:
            n = c.trazer_twitch()
            c.acordar.set()
            return n
        conf = self.cfg.kick(login)
        novos = canais_da_twitch(self.cfg, login, conf["canais"])
        self.cfg.definir_kick(login, canais=conf["canais"] + novos, trouxe_twitch=True)
        return len(novos)

    def loja(self, login, canal):
        c = self._conta(login, criar=False)
        if c is None:
            raise ErroKick("A Kick não está ligada nessa conta. Ligue na página da conta.")
        return c.loja(canal)

    def comprar(self, login, canal, recompensa, custo=None):
        c = self._conta(login, criar=False)
        if c is None:
            raise ErroKick("A Kick não está ligada nessa conta. Ligue na página da conta.")
        return c.comprar(canal, recompensa, custo)

    def seguir(self, login, canais=None):
        c = self._conta(login, criar=False)
        if c:
            c.pedir("seguir", canais)

    def conferir_seguidos(self, login):
        c = self._conta(login, criar=False)
        if c:
            c.pedir("seguidos")

    def pronto(self, login):
        c = self._conta(login, criar=False)
        if c:
            c.pedir("pronto")

    def sair(self, login):
        c = self._conta(login, criar=False)
        if c:
            c.pedir("sair")
        else:
            apagar_perfil(_pasta_kick() / login)
            self.cfg.definir_kick(login, usuario=None)

    def mostrar(self, login, sim):
        c = self._conta(login, criar=False)
        if c:
            c.pedir("mostrar", sim)

    def ver(self, login):
        c = self._conta(login, criar=False)
        if c:
            return c.ver()
        conf = self.cfg.kick(login)
        return {"ligada": conf["ligada"], "estado": "desligada", "usuario": conf.get("usuario"),
                "canais": [{"canal": c} for c in conf["canais"]], "auto": list(conf.get("auto") or []),
                "lives": max(1, min(LIVES_MAX, int(conf.get("lives") or LIVES_MAX))) if self.premium() else 1}

    def remover(self, login):
        with self.lock:
            c = self.contas.pop(login, None)
        if c:
            c.parar.set()  # o motor termina (e não abre mais Edge nenhum)
            c.acordar.set()
            c._fechar_edge()
            c.thread.join(15)
        apagar_perfil(_pasta_kick() / login)

    def parar_tudo(self):
        _encerrando.set()
        for c in list(self.contas.values()):
            c._fechar_edge()

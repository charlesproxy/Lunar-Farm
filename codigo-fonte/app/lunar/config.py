"""Contas, canais e opções do app (config.json na pasta de dados)."""

import json
import os
import re
import secrets
import threading
import time

from lunar import paths

PADRAO = {
    # Pela Store não tem a pergunta do instalador: começa ligado, como o instalador já vem marcado.
    "start_with_windows": paths.EMPACOTADO,
    "keep_awake": True,
    "chat_mode": "sempre",  # "sempre" (igual ao Chatterino) ou "ao_vivo"
    "auto_follow": True,  # segue os canais da lista (a Twitch dá 300 pontos por canal)
    "lan_enabled": False,
    "pin": None,
    "versao_vista": None,  # última versão cujas novidades a pessoa já viu (novidades.py)
}

MOTIVO_PAUSA_MANUAL = "Pausada por você"  # compra automática pausada no app (as outras pausas trazem o motivo)

_LOGIN_VALIDO = re.compile(r"^[a-z0-9_]{2,25}$")

# Kick: os streamers do PokeIdle na Kick, com o nome que eles usam lá (lista conferida pelo dono em 13/11/2026).
KICK_CANAIS_POKEIDLE = [
    "biscoitao", "yetz", "surskity", "axt", "dersin2k", "denissnider", "guaxilol1", "clovaobengalalol", "revolta",
    "patopapao2", "rodil", "cogu", "tftoddy", "luccatv", "techzz", "faturetosl", "mecmeno", "yulla", "daniels", "yoda",
    "fnblol", "kennzy", "ookina8", "gragolandia", "matta",
]
# Streamers que usam outro nome na Kick (nome na Twitch -> nome na Kick). None = não tem canal na Kick: o mesmo
# nome lá é de outra pessoa, então não entra na lista ao trazer os canais da Twitch.
KICK_NOME_DA_TWITCH = {
    "axtlol": "axt", "clovaobengala": "clovaobengalalol", "patopapao": "patopapao2", "denissnidertv": "denissnider",
    "faasii": None,
}
# Versão das correções da Kick salvas em cada conta (Config._corrigir_kick roda uma vez ao abrir o app):
# 2 = nomes acima; 3 = 1 live por conta; 4 = 2 lives (o padrão do Premium, como na Twitch).
KICK_NOMES_VERSAO = 4


def kick_da_twitch(canal):
    """Nome na Kick de um canal da Twitch (o mesmo, na maioria), ou None se ele não tem canal na Kick."""
    return KICK_NOME_DA_TWITCH.get(canal, canal)


KICK_PADRAO = {
    "ligada": False,
    "canais": KICK_CANAIS_POKEIDLE,
    "auto": [],  # compra automática: recompensas (nome sem as horas, em minúsculas) compradas em todos os canais da Kick
    "favoritos": [],  # entram na frente quando estão ao vivo (como a estrela da Twitch)
    # Lives da Kick ao mesmo tempo (1 ou 2; a versão grátis usa 1). Medido em 13/11/2026: a Kick paga direito a live
    # que abriu primeiro (a do canal favorito, que abre antes) e a segunda rende de vez em quando.
    "lives": 2,
    "seguidos": [],  # canais que a conta já segue na Kick (o Lunar segue sozinho com "Seguir os canais da lista")
    # Na primeira vez a lista da Kick ganha os canais da lista da Twitch (a maioria faz live nas duas, com o
    # mesmo nome); os que não existem na Kick saem sozinhos. Depois disso a lista é só da Kick.
    "trouxe_twitch": False,
    "usuario": None,  # nome na Kick, depois que a pessoa entra
    "nomes": KICK_NOMES_VERSAO,  # versão das correções da Kick já feitas nesta conta (ver KICK_NOMES_VERSAO)
}
_KICK_VALIDO = re.compile(r"^[a-z0-9_-]{2,30}$")


def normalizar_canal_kick(texto):
    """kick.com/nome, player.kick.com/nome ou só o nome -> nome (ou None se não parecer um canal)."""
    t = str(texto or "").strip().lower().rstrip("/")
    t = re.sub(r"^(https?://)?(www\.|player\.)?kick\.com/", "", t)
    t = t.split("?")[0].split("/")[0].lstrip("@")
    return t if _KICK_VALIDO.match(t) else None


def normalizar_canal(texto):
    """'https://www.twitch.tv/Matta/videos' -> 'matta'. None se não for um canal."""
    texto = (texto or "").strip().strip("/").lower()
    if not texto:
        return None
    if "twitch.tv/" in texto:
        texto = texto.split("twitch.tv/", 1)[1]
        texto = re.split(r"[/?#]", texto, 1)[0]
    texto = texto.lstrip("@")
    return texto if _LOGIN_VALIDO.match(texto) else None


def separar_canais(texto):
    """Aceita vários links/nomes separados por espaço, vírgula ou linha."""
    canais = []
    for parte in re.split(r"[\s,;]+", texto or ""):
        canal = normalizar_canal(parte)
        if canal and canal not in canais:
            canais.append(canal)
    return canais


def ler(path=None):
    """Leitura simples, usada pelo motor de cada conta."""
    path = path or paths.CONFIG_FILE
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, ValueError):
        data = {}
    data.setdefault("accounts", [])
    data["settings"] = {**PADRAO, **(data.get("settings") or {})}
    return data


class Config:
    def __init__(self, path=None):
        self.path = path or paths.CONFIG_FILE
        self.lock = threading.RLock()
        self.data = ler(self.path)
        if not self.data["settings"].get("pin"):
            self.data["settings"]["pin"] = f"{secrets.randbelow(10 ** 4):04d}"
            self.salvar()
        if self._corrigir_kick() | self._despausar_sumidas():
            self.salvar()

    def _despausar_sumidas(self):
        """Compras automáticas pausadas porque a recompensa sumiu da loja ou foi desligada: até a 1.6.4 isso pausava
        para sempre. Agora a compra espera e tenta de novo sozinha, então essas pausas saem."""
        mudou = False
        for conta in self.data["accounts"]:
            for r in conta.get("auto_compras") or []:
                motivo = str(r.get("pausada") or "")
                if motivo.startswith(("Essa recompensa não está mais na loja", "Essa recompensa não existe mais",
                                      "O streamer desligou essa recompensa")):
                    r.pop("pausada", None)
                    mudou = True
        return mudou

    def _corrigir_kick(self):
        """Correções feitas uma vez na Kick de cada conta salva antes delas:
        - v2: troca o nome dos canais que usam outro nome na Kick (axtlol -> axt...), tira os que não têm canal lá e
          põe no fim os canais do PokeIdle que faltam. Os "seguidos" com nome velho saem (eram outro canal).
        - v3/v4: lives da Kick no padrão (2 no Premium, 1 no grátis, no máximo 2). Quem quiser 1 muda na página da conta."""
        mudou = False
        for conta in self.data["accounts"]:
            k = conta.get("kick")
            versao = k.get("nomes", 1) if isinstance(k, dict) else KICK_NOMES_VERSAO
            if versao >= KICK_NOMES_VERSAO:
                continue
            if versao >= 2:
                k["lives"] = 2
                k["nomes"] = KICK_NOMES_VERSAO
                mudou = True
                continue
            k["lives"] = 2
            canais = []
            for c in list(k.get("canais") or []) + KICK_CANAIS_POKEIDLE:
                novo = KICK_NOME_DA_TWITCH.get(c, c)
                if novo and novo not in canais:
                    canais.append(novo)
            favoritos = [KICK_NOME_DA_TWITCH.get(c, c) for c in k.get("favoritos") or []]
            k["canais"] = canais[:40]
            k["favoritos"] = [c for c in k["canais"] if c in favoritos]
            k["seguidos"] = [c for c in k.get("seguidos") or [] if c not in KICK_NOME_DA_TWITCH]
            k["nomes"] = KICK_NOMES_VERSAO
            mudou = True
        return mudou

    def salvar(self):
        with self.lock:
            tmp = f"{self.path}.tmp"
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(self.data, f, ensure_ascii=False, indent=2)
            # No Windows a troca falha se o motor de uma conta estiver lendo o arquivo
            # (ele confere as preferências de 10 em 10 s): espera um pouquinho e tenta de novo.
            for tentativa in range(40):
                try:
                    os.replace(tmp, self.path)
                    return
                except PermissionError:
                    if tentativa == 39:
                        raise
                    time.sleep(0.05)

    # --- contas ---
    def contas(self):
        with self.lock:
            return [dict(a, channels=list(a.get("channels", []))) for a in self.data["accounts"]]

    def conta(self, login):
        with self.lock:
            for a in self.data["accounts"]:
                if a["login"] == login:
                    return a
        return None

    def adicionar_conta(self, login, user_id=None):
        with self.lock:
            conta = self.conta(login)
            if conta is None:
                conta = {"login": login, "channels": [], "paused": False}
                self.data["accounts"].append(conta)
            if user_id:
                conta["user_id"] = str(user_id)
            self.salvar()
            return conta

    def remover_conta(self, login):
        with self.lock:
            self.data["accounts"] = [a for a in self.data["accounts"] if a["login"] != login]
            self.salvar()

    def definir_canais(self, login, canais):
        with self.lock:
            conta = self.conta(login)
            if conta is None:
                return None
            vistos = []
            for c in canais:
                c = normalizar_canal(c)
                if c and c not in vistos:
                    vistos.append(c)
            conta["channels"] = vistos
            if conta.get("favoritos"):
                conta["favoritos"] = [c for c in conta["favoritos"] if c in vistos]
            if conta.get("auto_compras"):
                conta["auto_compras"] = [r for r in conta["auto_compras"] if r["canal"] in vistos]
            self.salvar()
            return vistos

    def definir_auto_compra(self, login, canal, recompensa, titulo=None, custo=None, ligado=True, gravar=True):
        """Compra automática: compra a recompensa sempre que a conta juntar o custo no canal.
        gravar=False deixa para gravar uma vez só no fim (quem muda vários de uma vez)."""
        with self.lock:
            conta = self.conta(login)
            if conta is None or canal not in conta.get("channels", []):
                return None
            regras = [r for r in conta.get("auto_compras", []) if not (r["canal"] == canal and r["id"] == recompensa)]
            if ligado:
                regras.append({"canal": canal, "id": recompensa, "titulo": titulo, "custo": int(custo)})
            conta["auto_compras"] = regras
            if gravar:
                self.salvar()
            return regras

    def mudar_auto_compras(self, acao, titulo=None, login=None, canal=None):
        """Pausa, retoma ou desliga de uma vez as compras automáticas que batem com o filtro (recompensa pelo nome,
        conta e canal; sem filtro = todas). Devolve [(conta, canal, id)] das que mudaram."""
        nome = (titulo or "").strip().lower()
        mudadas = []
        with self.lock:
            for conta in self.data["accounts"]:
                if login and conta["login"] != login:
                    continue
                ficam = []
                for r in conta.get("auto_compras", []):
                    bate = (not canal or r["canal"] == canal) and (not nome or (r.get("titulo") or "").strip().lower() == nome)
                    if bate and acao == "desligar":
                        mudadas.append((conta["login"], r["canal"], r["id"]))
                        continue
                    if bate and acao == "pausar" and not r.get("pausada"):
                        r["pausada"] = MOTIVO_PAUSA_MANUAL
                        mudadas.append((conta["login"], r["canal"], r["id"]))
                    elif bate and acao == "retomar" and r.get("pausada"):
                        r.pop("pausada", None)
                        mudadas.append((conta["login"], r["canal"], r["id"]))
                    ficam.append(r)
                if "auto_compras" in conta:
                    conta["auto_compras"] = ficam
            if mudadas:
                self.salvar()
        return mudadas

    def trocar_id_auto_compra(self, login, canal, velho, novo):
        """O streamer recriou a recompensa (mesmo nome, outro id): a compra automática segue com o id novo."""
        with self.lock:
            for r in (self.conta(login) or {}).get("auto_compras", []):
                if r["canal"] == canal and r["id"] == velho:
                    r["id"] = novo
                    self.salvar()
                    return True
        return False

    def pausar_auto_compra(self, login, canal, recompensa, motivo):
        """Pausa (sem apagar) uma compra automática e guarda o motivo para mostrar no app."""
        with self.lock:
            for r in (self.conta(login) or {}).get("auto_compras", []):
                if r["canal"] == canal and r["id"] == recompensa:
                    r["pausada"] = motivo
                    self.salvar()

    def favoritar(self, login, canal, ligado):
        """Canal com estrela entra numa das 2 vagas sempre que estiver ao vivo."""
        with self.lock:
            conta = self.conta(login)
            if conta is None or canal not in conta.get("channels", []):
                return None
            favoritos = [c for c in conta.get("favoritos", []) if c != canal]
            if ligado:
                favoritos.append(canal)
            # Na ordem da lista: se tiver mais de 2 ao vivo, os de cima ganham.
            conta["favoritos"] = [c for c in conta["channels"] if c in favoritos]
            self.salvar()
            return conta["favoritos"]

    def definir_ordem(self, login, modo):
        """Como escolher as outras lives: "lista" (as de cima) ou "pontos" (onde tem mais pontos)."""
        with self.lock:
            conta = self.conta(login)
            if conta is not None and modo in ("lista", "pontos"):
                conta["ordem"] = modo
                self.salvar()

    def pausar(self, login, pausada):
        with self.lock:
            conta = self.conta(login)
            if conta is not None:
                conta["paused"] = bool(pausada)
                self.salvar()

    # --- Kick (opcional, por conta) ---
    def kick(self, login):
        """Como a Kick está nessa conta (com os valores de fábrica no que faltar)."""
        with self.lock:
            conta = self.conta(login) or {}
            return {**KICK_PADRAO, **(conta.get("kick") or {})}

    def definir_kick(self, login, **mudancas):
        with self.lock:
            conta = self.conta(login)
            if conta is None:
                return None
            atual = {**KICK_PADRAO, **(conta.get("kick") or {})}
            for chave, valor in mudancas.items():
                if chave not in KICK_PADRAO:
                    continue
                if chave in ("canais", "favoritos", "seguidos"):
                    vistos = []
                    for c in valor or []:
                        c = normalizar_canal_kick(c)
                        if c and c not in vistos:
                            vistos.append(c)
                    valor = vistos[:40]
                elif chave == "auto":
                    valor = sorted({str(x).strip().lower()[:120] for x in valor or [] if str(x).strip()})
                atual[chave] = valor
            atual["favoritos"] = [c for c in atual["canais"] if c in (atual.get("favoritos") or [])]
            atual.pop("usar_twitch", None)  # opções de testes anteriores
            atual.pop("resgate", None)
            conta["kick"] = atual
            self.salvar()
            return dict(atual)

    # --- opções ---
    def opcoes(self):
        with self.lock:
            return dict(self.data["settings"])

    def mudar_opcoes(self, **novas):
        with self.lock:
            for chave, valor in novas.items():
                if chave in PADRAO:
                    self.data["settings"][chave] = valor
            self.salvar()
            return dict(self.data["settings"])

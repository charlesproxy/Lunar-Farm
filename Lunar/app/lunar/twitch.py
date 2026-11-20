"""Conversa direta com a Twitch usando o login de TV de cada conta: ver a loja de
pontos de um canal, resgatar uma recompensa e seguir um canal."""

import pickle
import secrets
import threading

import requests
from TwitchChannelPointsMiner.constants import CLIENT_ID, USER_AGENTS, GQLOperations

from lunar import paths

UA_TV = next(v["TV"] for v in USER_AGENTS.values() if "TV" in v)


def _operacao(nome, sha):
    return {"operationName": nome, "extensions": {"persistedQuery": {"version": 1, "sha256Hash": sha}}}


SEGUIR = _operacao("FollowButton_FollowUser", "800e7346bdf7e5278a3c1d3f21b2b56e2639928f86815677a7126b093b2fdd08")
RESGATAR = _operacao("RedeemCustomReward", "d56249a7adb4978898ea3412e196688d4ac3cea1c0c2dfd65561d229ea5dcc42")

ERROS_RESGATE = {
    "NOT_ENOUGH_POINTS": "Pontos insuficientes nesse canal.",
    "PROPERTIES_MISMATCH": "A recompensa mudou de preço ou de nome. Atualize a loja e tente de novo.",
    "DISABLED": "O streamer desligou essa recompensa.",
    "PAUSED": "O streamer pausou essa recompensa.",
    "OUT_OF_STOCK": "Acabou o estoque dessa recompensa.",
    "MAX_PER_STREAM": "Essa recompensa já chegou no limite dessa live.",
    "MAX_PER_USER_PER_STREAM": "Essa conta já comprou o máximo que o streamer deixa nessa live. Dá para comprar de novo na próxima live.",
    "GLOBAL_COOLDOWN": "Recompensa em recarga. Tente daqui a pouco.",
    "USER_BANNED": "Essa conta está banida nesse canal.",
    "NOT_FOUND": "Essa recompensa não existe mais na loja do canal.",
    "FORBIDDEN": "A Twitch não deixou essa conta resgatar.",
    "DUPLICATE_TRANSACTION": "Esse resgate já tinha sido feito.",
    "TRANSACTION_ALREADY_COMMITTED": "Esse resgate já tinha sido feito.",
}


class SemLogin(Exception):
    """A conta não tem login salvo ou ele venceu."""


class ErroTwitch(Exception):
    def __init__(self, mensagem, codigo=None):
        super().__init__(mensagem)
        self.codigo = codigo  # ex.: NOT_ENOUGH_POINTS, GLOBAL_COOLDOWN (a compra automática usa)


class Cliente:
    def __init__(self, login):
        self.login = login
        self.lock = threading.Lock()
        self.sessao = requests.Session()
        self.sessao.headers.update({
            "Client-Id": CLIENT_ID,
            "Client-Session-Id": secrets.token_hex(8),
            "User-Agent": UA_TV,
            "X-Device-Id": secrets.token_hex(16),
        })

    def _token(self):
        try:
            with open(paths.cookie_file(self.login), "rb") as f:
                cookies = {c["name"]: c["value"] for c in pickle.load(f)}
        except (OSError, EOFError, pickle.UnpicklingError, KeyError, TypeError):
            raise SemLogin(self.login) from None
        if not cookies.get("auth-token"):
            raise SemLogin(self.login)
        return cookies["auth-token"]

    def gql(self, operacao, variaveis):
        corpo = dict(operacao, variables=variaveis)
        with self.lock:
            try:
                r = self.sessao.post(
                    GQLOperations.url,
                    json=corpo,
                    headers={"Authorization": f"OAuth {self._token()}"},
                    timeout=20,
                )
            except requests.exceptions.RequestException:
                raise ErroTwitch("Sem resposta da Twitch. Confira a internet.") from None
        if r.status_code == 401:
            raise SemLogin(self.login)
        try:
            return r.json()
        except ValueError:
            raise ErroTwitch(f"A Twitch respondeu algo estranho (HTTP {r.status_code}).") from None

    @staticmethod
    def _erro_gql(dados):
        erros = dados.get("errors") or []
        msg = erros[0].get("message") if erros and isinstance(erros[0], dict) else None
        return f"A Twitch recusou ({msg})." if msg else "A Twitch não respondeu o que devia."

    # --- loja ---
    def loja(self, canal):
        dados = self.gql(GQLOperations.ChannelPointsContext, {"channelLogin": canal})
        ch = ((dados.get("data") or {}).get("community") or {}).get("channel")
        if not ch:
            if dados.get("errors"):
                raise ErroTwitch(self._erro_gql(dados))
            raise ErroTwitch(f"Não achei o canal {canal} na Twitch.")
        cfg = ch.get("communityPointsSettings") or {}
        eu = (ch.get("self") or {}).get("communityPoints") or {}
        # Quantas vezes esta conta já comprou cada recompensa na live de agora.
        compradas = {
            (u.get("reward") or {}).get("id"): int(u.get("userRedemptionsCurrentStream") or 0)
            for u in eu.get("userRedemptions") or []
        }
        return {
            "canal": canal,
            "canal_id": ch.get("id"),
            "saldo": eu.get("balance"),
            "pontos_ligados": bool(cfg.get("isEnabled")),
            "nome_pontos": cfg.get("name"),
            "recompensas": [
                dict(_recompensa(r), compradas_live=compradas.get(r["id"], 0))
                for r in cfg.get("customRewards") or []
                # Desligada some da loja do site também; bits não dá para pagar com pontos.
                if r.get("isEnabled") and (r.get("pricingType") or "POINTS") == "POINTS"
            ],
        }

    def resgatar(self, canal, recompensa_id, texto=None, custo_esperado=None, titulo=None):
        # Busca de novo: a Twitch confere o preço e o nome do jeito que estão agora.
        loja = self.loja(canal)
        r = next((x for x in loja["recompensas"] if x["id"] == recompensa_id), None)
        if r is None and titulo:
            # O streamer apagou e criou de novo (outro id, mesmo nome): é a mesma recompensa para quem compra.
            nome = titulo.strip().lower()
            r = next((x for x in loja["recompensas"] if (x["titulo"] or "").strip().lower() == nome), None)
        if r is None:
            raise ErroTwitch("Essa recompensa não está na loja do canal agora.", "NOT_FOUND")
        if custo_esperado is not None and r["custo"] != custo_esperado:
            # Compra automática: nunca paga um preço diferente do que a pessoa escolheu.
            raise ErroTwitch(f"O preço mudou de {custo_esperado} para {r['custo']} pontos.", "PRECO_MUDOU")
        if r["pausada"] or r["sem_estoque"]:
            raise ErroTwitch("O streamer pausou essa recompensa ou ela esgotou.", "PAUSED")
        if r["limite_live"] and r["compradas_live"] >= r["limite_live"]:
            # Nem tenta: a Twitch recusaria do mesmo jeito.
            raise ErroTwitch(f"Essa conta já comprou {r['compradas_live']} de {r['limite_live']} nessa live "
                             "(limite do streamer). Dá para comprar de novo na próxima live.", "MAX_PER_USER_PER_STREAM")
        texto = (texto or "").strip() or None
        if r["pede_texto"] and not texto:
            raise ErroTwitch("Essa recompensa pede um texto.", "PEDE_TEXTO")
        if loja["saldo"] is not None and loja["saldo"] < r["custo"]:
            raise ErroTwitch(f"Pontos insuficientes: tem {loja['saldo']}, precisa de {r['custo']}.", "NOT_ENOUGH_POINTS")
        entrada = {
            "channelID": loja["canal_id"],
            "cost": r["custo"],
            # A Twitch confere nome, preço e descrição como estão na loja (senão: PROPERTIES_MISMATCH).
            "prompt": r["prompt"],
            "rewardID": r["id"],
            "title": r["titulo"],
            "transactionID": secrets.token_hex(16),
        }
        if r["pede_texto"]:
            entrada["textInput"] = texto
        dados = self.gql(RESGATAR, {"input": entrada})
        resposta = (dados.get("data") or {}).get("redeemCommunityPointsCustomReward")
        if resposta is None:
            raise ErroTwitch(self._erro_gql(dados))
        if resposta.get("error"):
            codigo = resposta["error"].get("code")
            raise ErroTwitch(ERROS_RESGATE.get(codigo, f"A Twitch recusou ({codigo})."), codigo)
        saldo = loja["saldo"] - r["custo"] if loja["saldo"] is not None else None
        return {"recompensa": r, "saldo": saldo}

    # --- seguir ---
    def seguir(self, canal):
        loja = self.loja(canal)  # só para saber o id do canal
        dados = self.gql(SEGUIR, {"input": {"disableNotifications": True, "targetID": loja["canal_id"]}})
        resposta = (dados.get("data") or {}).get("followUser")
        if resposta is None:
            raise ErroTwitch(self._erro_gql(dados))
        if resposta.get("error"):
            raise ErroTwitch(f"A Twitch não deixou seguir ({resposta['error'].get('code')}).")


def _recompensa(r):
    imagem = r.get("image") or r.get("defaultImage") or {}
    return {
        "id": r["id"],
        "titulo": r.get("title") or "",
        "custo": int(r.get("cost") or 0),
        "cor": r.get("backgroundColor") or "#9146FF",
        "imagem": imagem.get("url2x") or imagem.get("url"),
        "pede_texto": bool(r.get("isUserInputRequired")),
        "pergunta": r.get("prompt") or "",
        "prompt": r.get("prompt"),  # do jeito que a Twitch guarda: vai de volta na compra
        "pausada": bool(r.get("isPaused")),
        "sem_estoque": r.get("isInStock") is False,
        "recarga_ate": r.get("cooldownExpiresAt"),
        "so_sub": bool(r.get("isSubOnly")),
        # Limite que o streamer põe: quantas vezes cada conta pode comprar na mesma live.
        "limite_live": _limite(r.get("maxPerUserPerStreamSetting"), "maxPerUserPerStream"),
    }


def _limite(ajuste, campo):
    ajuste = ajuste or {}
    return int(ajuste.get(campo) or 0) or None if ajuste.get("isEnabled") else None


_clientes = {}
_trava = threading.Lock()


def cliente(login):
    with _trava:
        if login not in _clientes:
            _clientes[login] = Cliente(login)
        return _clientes[login]

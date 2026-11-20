"""Ajuda e suporte: tickets no site do Lunar Farm (vexpulse.com.br/api/suporte). O app guarda os
tickets que abriu (código + segredo, em suporte.json) e confere de 10 em 10 min se o suporte
respondeu; a resposta aparece no app e num aviso perto do relógio."""

import json
import logging
import platform
import threading
import time

import requests

from lunar import VERSAO, paths, premium

log = logging.getLogger("lunar")

ARQUIVO = paths.DATA_DIR / "suporte.json"
API = f"{premium.SITE}/api/suporte/"
CONFERIR_A_CADA = 600
LINHAS_DO_REGISTRO = 80


class ErroSuporte(Exception):
    pass


class Suporte:
    def __init__(self, prem, cfg):
        self.prem = prem
        self.cfg = cfg
        self.lock = threading.Lock()
        self.ao_responder = None  # a bandeja avisa quando chega resposta
        try:
            self.tickets = json.loads(ARQUIVO.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            self.tickets = []
        threading.Thread(target=self._vigiar, daemon=True).start()

    def _gravar(self):
        tmp = ARQUIVO.with_suffix(".tmp")
        tmp.write_text(json.dumps(self.tickets, ensure_ascii=False), encoding="utf-8")
        tmp.replace(ARQUIVO)

    @staticmethod
    def _site(caminho, dados):
        try:
            r = requests.post(API + caminho, json=dados, headers={"User-Agent": f"LunarFarm/{VERSAO}"}, timeout=20)
            corpo = r.json()
        except (requests.exceptions.RequestException, ValueError):
            raise ErroSuporte("Não deu para falar com o suporte agora. Confira a internet e tente de novo.")
        if r.status_code != 200:
            raise ErroSuporte(corpo.get("erro") or f"O suporte não respondeu ({r.status_code}).")
        return corpo

    def diagnostico(self, com_registro):
        """O que vai junto com o ticket para o suporte entender o caso."""
        p = self.prem.ver()
        info = {
            "versao": VERSAO,
            "premium": p["ativo"],
            "chave": p["chave"],
            "pedido": self.prem._pedido_aberto(),
            "contas": len(self.cfg.contas()),
            "windows": platform.platform(),
        }
        if com_registro:
            try:
                linhas = (paths.LOG_DIR / "app.log").read_text(encoding="utf-8", errors="replace").splitlines()
                info["log"] = "\n".join(linhas[-LINHAS_DO_REGISTRO:])
            except OSError:
                pass
        return info

    def criar(self, assunto, mensagem, contato, com_registro):
        corpo = self._site("criar.php", {
            "assunto": assunto, "mensagem": mensagem, "contato": contato, "origem": "app",
            "pc": premium.id_do_pc(), "info": self.diagnostico(com_registro),
        })
        with self.lock:
            self.tickets.insert(0, {"ticket": corpo["ticket"], "segredo": corpo["segredo"], "criado": time.time()})
            self._gravar()
        log.info("ticket de suporte aberto: %s", corpo["ticket"])
        return self.ver(corpo["ticket"])

    def _segredo(self, ticket):
        for t in self.tickets:
            if t["ticket"] == ticket:
                return t
        raise ErroSuporte("Esse ticket não é deste PC.")

    def _guardar_resumo(self, t, corpo):
        t.update({k: corpo[k] for k in ("assunto_nome", "status", "atualizado", "resposta_nova") if k in corpo})
        if corpo.get("mensagens"):
            t["ultima"] = corpo["mensagens"][-1]["texto"][:140]
            t["ultimo_autor"] = corpo["mensagens"][-1]["autor"]

    def ver(self, ticket, marcar=True):
        t = self._segredo(ticket)
        corpo = self._site("ver.php", {"ticket": ticket, "segredo": t["segredo"], "espiar": not marcar})
        with self.lock:
            self._guardar_resumo(t, corpo)
            self._gravar()
        return corpo

    def responder(self, ticket, mensagem):
        t = self._segredo(ticket)
        corpo = self._site("responder.php", {"ticket": ticket, "segredo": t["segredo"], "mensagem": mensagem})
        with self.lock:
            self._guardar_resumo(t, corpo)
            self._gravar()
        return corpo

    def listar(self):
        with self.lock:
            return [{k: v for k, v in t.items() if k != "segredo"} for t in self.tickets]

    def novas(self):
        return sum(1 for t in self.tickets if t.get("resposta_nova"))

    def _vigiar(self):
        time.sleep(60)
        while True:
            for t in list(self.tickets):
                if t.get("status") == "fechado":
                    continue
                antes = t.get("resposta_nova")
                try:
                    self.ver(t["ticket"], marcar=False)
                except ErroSuporte:
                    continue
                if t.get("resposta_nova") and not antes and self.ao_responder:
                    try:
                        self.ao_responder(t["ticket"])
                    except Exception:
                        log.debug("aviso de resposta do suporte", exc_info=True)
            time.sleep(CONFERIR_A_CADA)

"""O que mudou em cada versão (novidades.json, a mais nova primeiro). Aparece numa janela
depois de atualizar, no histórico das Configurações e no aviso de versão nova
(ferramentas\\publicar.py manda as novidades da versão junto com o instalador)."""

import functools
import json
from pathlib import Path

from lunar import VERSAO
from lunar.atualizador import numeros

ARQUIVO = Path(__file__).with_name("novidades.json")


@functools.lru_cache(maxsize=1)  # o painel pergunta de 3 em 3 segundos; o arquivo não muda
def historico():
    try:
        return json.loads(ARQUIVO.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []


def preparar(cfg):
    """Instalação nova não tem o que mostrar: só quem já usava vê as novidades."""
    if cfg.opcoes().get("versao_vista") is None and not cfg.contas():
        cfg.mudar_opcoes(versao_vista=VERSAO)


def nao_vistas(cfg):
    """Versões que entraram desde a última vez que a pessoa viu as novidades."""
    vista = cfg.opcoes().get("versao_vista")
    if vista is None:
        # Veio de uma versão sem esse controle (até a 1.3): mostra só a atual.
        return [v for v in historico() if v["versao"] == VERSAO]
    return [v for v in historico() if numeros(vista) < numeros(v["versao"]) <= numeros(VERSAO)]


def marcar_vistas(cfg):
    cfg.mudar_opcoes(versao_vista=VERSAO)

"""Link de "Indicar a um amigo": um código curto deste PC (não diz quem é a pessoa),
para o painel do dono contar quantos amigos cada um trouxe."""

import hashlib
import logging

from lunar import premium

log = logging.getLogger("lunar")


def link_de_indicacao():
    codigo = hashlib.sha256(f"indica:{premium.id_do_pc()}".encode()).hexdigest()[:6]
    return f"{premium.SITE}/?ref=amigo-{codigo}"


class Uso:
    def __init__(self, prem, cfg):
        try:
            self.link_indicar = link_de_indicacao()
        except Exception:
            log.debug("link de indicação", exc_info=True)
            self.link_indicar = f"{premium.SITE}/?ref=amigo"

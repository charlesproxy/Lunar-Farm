"""Lunar Farm — tudo liberado, sem plano pago.

Não existe mais chave, Pix nem loja: o app roda sempre com TUDO liberado neste PC
(contas ilimitadas, 2 lives por conta, seguir todos os canais da lista e compra
automática). A classe Premium continua só como "provedor de limites", para o resto
do app (gerente, worker, seguidor) não precisar mudar: responde sempre liberado.
"""

import hashlib
import logging

from lunar import plataforma

log = logging.getLogger("lunar")

# Usado só para o link de "Indicar a um amigo". Nada de pagamento passa por aqui.
SITE = "https://vexpulse.com.br"

# Tudo liberado. None = sem limite. lives = 2 (o teto da Twitch).
LIBERADO = {"contas": None, "lives": 2, "seguir": None}
GRATIS = LIBERADO   # nomes antigos, agora iguais: não existe mais "grátis x premium"
PREMIUM = LIBERADO


def id_do_pc():
    """Identidade deste PC (usada só para o link de indicação e o diagnóstico do suporte)."""
    guid = plataforma.id_da_maquina() or "sem-machineguid"
    return hashlib.sha256(f"vexpontos:{guid}".encode()).hexdigest()[:32]


class Premium:
    """Provedor de limites sempre-liberado: o farm roda sem nada de pago e sem rede."""

    def __init__(self):
        self.ao_mudar = None  # o gerente religa os motores se isto mudar (nunca muda)

    def ativo(self):
        return True

    def limites(self):
        return LIBERADO

    def ver(self):
        return {"ativo": True, "limites": LIBERADO}

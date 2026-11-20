"""Atualização pelo próprio app: confere no site se saiu versão nova, baixa o
instalador, confere a impressão digital (SHA-256) e instala escondido por cima.
O instalador fecha o app, troca os arquivos e abre de novo; contas e histórico ficam."""

import hashlib
import logging
import re
import subprocess
import tempfile
import threading
import time
from pathlib import Path

import requests

from lunar import VERSAO, paths

log = logging.getLogger("lunar")

# Onde as versões são publicadas (ferramentas\publicar.py): desde a 1.4.2, no site; o GitHub
# fica de reserva enquanto for público. Cada lista só vale com instalador do mesmo lugar.
REPOSITORIO = "leonardobritzke06-maker/vexpontos"
FONTES = (
    ("https://vexpulse.com.br/download/latest.json", "https://vexpulse.com.br/download/"),
    (f"https://github.com/{REPOSITORIO}/releases/latest/download/latest.json",
     f"https://github.com/{REPOSITORIO}/releases/download/"),
)
INTERVALO = 3600  # confere de hora em hora (e logo depois de abrir)

DETACHED_PROCESS = 0x00000008
CREATE_NEW_PROCESS_GROUP = 0x00000200


def numeros(versao):
    return tuple(int(x) for x in re.findall(r"\d+", str(versao))[:3])


def instalado():
    """Só a cópia que veio do instalador se atualiza (a pasta de desenvolvimento, não)."""
    return (paths.ROOT_DIR / "unins000.exe").is_file()


class ErroAtualizacao(Exception):
    pass


class Atualizador:
    def __init__(self):
        self.lock = threading.Lock()
        self.fase = "nada"  # nada | disponivel | baixando | instalando | erro
        self.nova = None  # o latest.json da versão nova, já conferido
        self.progresso = 0
        self.erro = None
        self.conferido_em = None
        self.ao_achar = None  # avisa a bandeja quando aparece versão nova
        self.acordar = threading.Event()
        if self.ligado():
            threading.Thread(target=self._rodar, daemon=True).start()

    @staticmethod
    def ligado():
        return instalado()

    def _rodar(self):
        self.acordar.wait(60)  # deixa o farm ligar primeiro
        self._limpar_baixados()
        while True:
            self.acordar.clear()
            self.conferir()
            self.acordar.wait(INTERVALO)

    @staticmethod
    def _limpar_baixados():
        """Apaga instaladores de atualizações já feitas (30 MB cada) da pasta temporária."""
        for velho in (Path(tempfile.gettempdir()) / "Lunar-atualizacao").glob("*.exe"):
            try:
                velho.unlink()
            except OSError:
                pass

    def _ler_novidades(self):
        erro = None
        for endereco, base in FONTES:
            try:
                return self._ler(endereco, base)
            except (requests.exceptions.RequestException, ValueError) as e:
                erro = e  # tenta a próxima
        raise erro

    @staticmethod
    def _ler(endereco, base):
        r = requests.get(endereco, headers={"User-Agent": f"LunarFarm/{VERSAO}"}, timeout=20)
        r.raise_for_status()
        dados = r.json()
        # Só aceita instalador publicado no mesmo lugar de onde veio a lista.
        if not (
            isinstance(dados, dict)
            and numeros(dados.get("versao"))
            and str(dados.get("instalador", "")).startswith(base)
            and re.fullmatch(r"[0-9a-fA-F]{64}", str(dados.get("sha256", "")))
            and isinstance(dados.get("tamanho"), int) and dados["tamanho"] > 0
        ):
            raise ValueError("latest.json com formato inesperado")
        dados["novidades"] = [str(x) for x in dados.get("novidades") or []][:15]
        return dados

    def conferir(self):
        if not self.ligado():
            return self.ver()
        try:
            dados = self._ler_novidades()
        except (requests.exceptions.RequestException, ValueError) as e:
            log.info("não deu para conferir atualização: %s", e)
            with self.lock:
                self.conferido_em = time.time()
            return self.ver()
        achou = False
        with self.lock:
            self.conferido_em = time.time()
            if numeros(dados["versao"]) > numeros(VERSAO) and self.fase not in ("baixando", "instalando"):
                achou = self.nova is None or self.nova["versao"] != dados["versao"]
                self.nova = dados
                if self.fase != "erro":
                    self.fase = "disponivel"
        if achou:
            log.info("versão nova disponível: %s", dados["versao"])
            if self.ao_achar:
                try:
                    self.ao_achar(dados)
                except Exception:
                    log.debug("aviso da versão nova", exc_info=True)
        return self.ver()

    def ver(self):
        with self.lock:
            nova = self.nova
            return {
                "atual": VERSAO,
                "ligado": self.ligado(),
                "instalado": instalado(),
                "loja": paths.EMPACOTADO,  # a Microsoft Store atualiza sozinha
                "fase": self.fase,
                "progresso": self.progresso,
                "erro": self.erro,
                "conferido_em": self.conferido_em,
                "nova": {k: nova[k] for k in ("versao", "novidades", "tamanho")} if nova else None,
            }

    def atualizar(self):
        with self.lock:
            if self.nova is None or self.fase in ("baixando", "instalando"):
                return False
            self.fase, self.progresso, self.erro = "baixando", 0, None
            nova = dict(self.nova)
        threading.Thread(target=self._baixar_e_instalar, args=(nova,), daemon=True).start()
        return True

    def _falhou(self, msg):
        log.warning("atualização falhou: %s", msg)
        with self.lock:
            self.fase, self.erro = "erro", msg

    def _baixar_e_instalar(self, nova):
        pasta = Path(tempfile.gettempdir()) / "Lunar-atualizacao"
        destino = pasta / f"Lunar-Setup-{nova['versao']}.exe"
        try:
            pasta.mkdir(exist_ok=True)
            soma = hashlib.sha256()
            baixado = 0
            with requests.get(nova["instalador"], stream=True, timeout=30,
                              headers={"User-Agent": f"LunarFarm/{VERSAO}"}) as r:
                r.raise_for_status()
                with open(destino, "wb") as f:
                    for pedaco in r.iter_content(256 * 1024):
                        f.write(pedaco)
                        soma.update(pedaco)
                        baixado += len(pedaco)
                        with self.lock:
                            self.progresso = min(99, baixado * 100 // nova["tamanho"])
            if baixado != nova["tamanho"] or soma.hexdigest().lower() != nova["sha256"].lower():
                destino.unlink(missing_ok=True)
                raise ErroAtualizacao("O arquivo baixado não confere com o publicado. Nada foi instalado.")
        except requests.exceptions.RequestException:
            self._falhou("Não deu para baixar a versão nova. Confira a internet e tente de novo.")
            return
        except OSError:
            self._falhou("Não deu para salvar a versão nova no PC. Tente de novo.")
            return
        except ErroAtualizacao as e:
            self._falhou(str(e))
            return
        with self.lock:
            self.fase, self.progresso = "instalando", 100
        log.info("instalando a versão %s", nova["versao"])
        # O instalador fecha este app pela porta do painel, troca os arquivos e abre de novo.
        try:
            subprocess.Popen(
                [str(destino), "/VERYSILENT", "/SUPPRESSMSGBOXES", "/NORESTART",
                 "/reabrir=1", f"/porta={paths.PORTA}", f"/LOG={pasta / 'instalacao.log'}"],
                creationflags=DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP,
                close_fds=True,
            )
        except OSError:
            self._falhou("Não deu para abrir o instalador da versão nova.")

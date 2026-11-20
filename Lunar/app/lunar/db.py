"""Histórico de pontos e acontecimentos (SQLite na pasta de dados)."""

import sqlite3
import threading
import time
from datetime import date, datetime, timedelta

ESQUEMA = """
CREATE TABLE IF NOT EXISTS ganhos (
    id INTEGER PRIMARY KEY,
    ts REAL NOT NULL,
    dia TEXT NOT NULL,
    conta TEXT NOT NULL,
    canal TEXT NOT NULL,
    pontos INTEGER NOT NULL,
    motivo TEXT NOT NULL,
    saldo INTEGER
);
CREATE INDEX IF NOT EXISTS ganhos_dia ON ganhos (dia, conta);
CREATE INDEX IF NOT EXISTS ganhos_canal ON ganhos (conta, canal);
CREATE TABLE IF NOT EXISTS eventos (
    id INTEGER PRIMARY KEY,
    ts REAL NOT NULL,
    conta TEXT NOT NULL,
    canal TEXT,
    tipo TEXT NOT NULL,
    texto TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS eventos_ts ON eventos (ts);
CREATE TABLE IF NOT EXISTS assistido (
    dia TEXT NOT NULL,
    conta TEXT NOT NULL,
    canal TEXT NOT NULL,
    segundos INTEGER NOT NULL,
    PRIMARY KEY (dia, conta, canal)
);
CREATE TABLE IF NOT EXISTS saldos (
    conta TEXT NOT NULL,
    canal TEXT NOT NULL,
    saldo INTEGER NOT NULL,
    ts REAL NOT NULL,
    PRIMARY KEY (conta, canal)
);
CREATE TABLE IF NOT EXISTS gastos (
    id INTEGER PRIMARY KEY,
    ts REAL NOT NULL,
    dia TEXT NOT NULL,
    conta TEXT NOT NULL,
    canal TEXT NOT NULL,
    pontos INTEGER NOT NULL,
    titulo TEXT,
    casado INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS gastos_canal ON gastos (conta, canal);
CREATE TABLE IF NOT EXISTS seguidos (
    conta TEXT NOT NULL,
    canal TEXT NOT NULL,
    ok INTEGER NOT NULL,
    ts REAL NOT NULL,
    PRIMARY KEY (conta, canal)
);
"""

# Previsões entram e saem do saldo; não contam como farm.
NAO_FARM = ("PREDICTION", "REFUND")
# Segundos para casar a compra feita pelo app com a queda de saldo que o motor percebe
# depois (ele confere o saldo de 5 em 5 minutos).
JUNTAR_GASTO = 600


def dia_de(ts):
    return datetime.fromtimestamp(ts).strftime("%Y-%m-%d")


class Historico:
    def __init__(self, path):
        self.lock = threading.Lock()
        self.db = sqlite3.connect(str(path), check_same_thread=False)
        self.db.row_factory = sqlite3.Row
        self.db.execute("PRAGMA journal_mode=WAL")
        self.db.executescript(ESQUEMA)
        self.db.commit()

    def _exec(self, sql, args=()):
        with self.lock:
            self.db.execute(sql, args)
            self.db.commit()

    def _query(self, sql, args=()):
        with self.lock:
            return [dict(r) for r in self.db.execute(sql, args).fetchall()]

    # --- gravar ---
    def ganho(self, conta, canal, pontos, motivo, saldo):
        ts = time.time()
        self._exec(
            "INSERT INTO ganhos (ts, dia, conta, canal, pontos, motivo, saldo) VALUES (?,?,?,?,?,?,?)",
            (ts, dia_de(ts), conta, canal, pontos, motivo, saldo),
        )
        if saldo is not None:
            self.saldo(conta, canal, saldo)

    def evento(self, conta, canal, tipo, texto):
        self._exec(
            "INSERT INTO eventos (ts, conta, canal, tipo, texto) VALUES (?,?,?,?,?)",
            (time.time(), conta, canal, tipo, texto),
        )

    def assistiu(self, conta, canal, segundos):
        self._exec(
            "INSERT INTO assistido (dia, conta, canal, segundos) VALUES (?,?,?,?) "
            "ON CONFLICT (dia, conta, canal) DO UPDATE SET segundos = segundos + excluded.segundos",
            (dia_de(time.time()), conta, canal, int(segundos)),
        )

    def saldo(self, conta, canal, saldo):
        self._exec(
            "INSERT INTO saldos (conta, canal, saldo, ts) VALUES (?,?,?,?) "
            "ON CONFLICT (conta, canal) DO UPDATE SET saldo = excluded.saldo, ts = excluded.ts",
            (conta, canal, int(saldo), time.time()),
        )

    def saldos(self, conta):
        return {r["canal"]: r["saldo"] for r in self._query("SELECT canal, saldo FROM saldos WHERE conta = ?", (conta,))}

    def gasto(self, conta, canal, pontos, titulo=None):
        """Grava pontos gastos na loja de um canal. Compra pelo app chega duas vezes: o app sabe o
        nome da recompensa, e o motor só vê o saldo cair (às vezes várias compras numa queda só).
        Da queda vista pelo motor saem as compras do app; só a diferença entra (compra pelo chat)."""
        ts = time.time()
        pontos = int(pontos)
        with self.lock:
            pares = self.db.execute(
                "SELECT id, pontos FROM gastos WHERE conta = ? AND canal = ? AND casado = 0 AND pontos > 0 "
                "AND ts > ? AND (titulo IS NULL) = ? ORDER BY ts",
                (conta, canal, ts - JUNTAR_GASTO, titulo is not None),
            ).fetchall() if pontos > 0 else []
            casado = 0
            if titulo is None:
                for par in pares:
                    if 0 < par["pontos"] <= pontos:
                        self.db.execute("UPDATE gastos SET casado = 1 WHERE id = ?", (par["id"],))
                        pontos -= par["pontos"]
            else:
                # O motor já viu o saldo cair: sozinha ou junto com outras compras.
                par = next((p for p in pares if p["pontos"] >= pontos), None)
                if par and par["pontos"] == pontos:
                    self.db.execute("UPDATE gastos SET casado = 1, titulo = ? WHERE id = ?", (titulo, par["id"]))
                    pontos = 0
                elif par:
                    self.db.execute("UPDATE gastos SET pontos = pontos - ? WHERE id = ?", (pontos, par["id"]))
                    casado = 1
            if pontos:
                self.db.execute(
                    "INSERT INTO gastos (ts, dia, conta, canal, pontos, titulo, casado) VALUES (?,?,?,?,?,?,?)",
                    (ts, dia_de(ts), conta, canal, pontos, titulo, casado),
                )
            self.db.commit()

    def gasto_por_canal(self, conta):
        """Quanto a conta já gastou em cada canal: hoje e no total."""
        return {
            r["canal"]: {"hoje": r["hoje"], "total": r["total"]}
            for r in self._query(
                "SELECT canal, SUM(CASE WHEN dia = ? THEN pontos ELSE 0 END) AS hoje, SUM(pontos) AS total "
                "FROM gastos WHERE conta = ? GROUP BY canal",
                (date.today().isoformat(), conta),
            )
        }

    def marcar_seguido(self, conta, canal, ok):
        self._exec(
            "INSERT INTO seguidos (conta, canal, ok, ts) VALUES (?,?,?,?) "
            "ON CONFLICT (conta, canal) DO UPDATE SET ok = excluded.ok, ts = excluded.ts",
            (conta, canal, int(bool(ok)), time.time()),
        )

    def seguidos(self, conta):
        """{canal: (deu_certo, quando)} dos canais que o app já tentou seguir nessa conta."""
        return {
            r["canal"]: (bool(r["ok"]), r["ts"])
            for r in self._query("SELECT canal, ok, ts FROM seguidos WHERE conta = ?", (conta,))
        }

    def hoje_por_conta(self):
        return {
            r["conta"]: r["p"]
            for r in self._query(
                f"SELECT conta, SUM(pontos) AS p FROM ganhos WHERE motivo NOT IN {NAO_FARM} AND dia = ? GROUP BY conta",
                (date.today().isoformat(),),
            )
        }

    def farmado_por_canal(self, conta):
        """Quanto o app já farmou em cada canal dessa conta: hoje e no total."""
        return {
            r["canal"]: {"hoje": r["hoje"], "total": r["total"]}
            for r in self._query(
                f"SELECT canal, SUM(CASE WHEN dia = ? THEN pontos ELSE 0 END) AS hoje, SUM(pontos) AS total "
                f"FROM ganhos WHERE conta = ? AND motivo NOT IN {NAO_FARM} GROUP BY canal",
                (date.today().isoformat(), conta),
            )
        }

    def esquecer_conta(self, conta):
        self._exec("DELETE FROM saldos WHERE conta = ?", (conta,))

    # --- ler ---
    def resumo(self, conta=None, dias=30):
        hoje = date.today()
        inicio = (hoje - timedelta(days=dias - 1)).isoformat()
        filtro, args = ("AND conta = ?", (conta,)) if conta else ("", ())
        farm = f"motivo NOT IN {NAO_FARM}"

        def soma(desde):
            r = self._query(f"SELECT COALESCE(SUM(pontos), 0) AS p FROM ganhos WHERE {farm} AND dia >= ? {filtro}", (desde, *args))
            return r[0]["p"]

        cartoes = {
            "hoje": soma(hoje.isoformat()),
            "semana": soma((hoje - timedelta(days=6)).isoformat()),
            "mes": soma(inicio),
            "total": soma("0000"),
        }

        por_dia = {}
        for r in self._query(
            f"SELECT dia, conta, SUM(pontos) AS p FROM ganhos WHERE {farm} AND dia >= ? {filtro} GROUP BY dia, conta",
            (inicio, *args),
        ):
            por_dia.setdefault(r["dia"], {})[r["conta"]] = r["p"]
        serie = []
        for i in range(dias):
            d = (hoje - timedelta(days=dias - 1 - i)).isoformat()
            serie.append({"dia": d, "contas": por_dia.get(d, {})})

        horas = {}
        for r in self._query(
            f"SELECT conta, canal, SUM(segundos) AS s FROM assistido WHERE dia >= ? {filtro} GROUP BY conta, canal",
            (inicio, *args),
        ):
            horas[(r["conta"], r["canal"])] = r["s"]

        canais = {}
        for r in self._query(
            f"SELECT canal, SUM(pontos) AS p FROM ganhos WHERE {farm} AND dia >= ? {filtro} GROUP BY canal",
            (inicio, *args),
        ):
            canais[r["canal"]] = {"canal": r["canal"], "pontos": r["p"], "segundos": 0}
        for (_, canal), s in horas.items():
            canais.setdefault(canal, {"canal": canal, "pontos": 0, "segundos": 0})["segundos"] += s
        top = sorted(canais.values(), key=lambda c: (c["pontos"], c["segundos"]), reverse=True)[:10]

        contas = {}
        for r in self._query(
            f"SELECT conta, SUM(pontos) AS p, "
            f"SUM(CASE WHEN dia = ? THEN pontos ELSE 0 END) AS hoje, "
            f"SUM(CASE WHEN motivo = 'CLAIM' THEN 1 ELSE 0 END) AS baus, "
            f"SUM(CASE WHEN motivo LIKE 'WATCH_STREAK%' THEN 1 ELSE 0 END) AS sequencias, "
            f"SUM(CASE WHEN motivo = 'RAID' THEN 1 ELSE 0 END) AS raids "
            f"FROM ganhos WHERE {farm} AND dia >= ? {filtro} GROUP BY conta",
            (hoje.isoformat(), inicio, *args),
        ):
            contas[r["conta"]] = {
                "conta": r["conta"], "mes": r["p"], "hoje": r["hoje"],
                "baus": r["baus"], "sequencias": r["sequencias"], "raids": r["raids"], "segundos": 0,
            }
        for (c, _), s in horas.items():
            contas.setdefault(c, {"conta": c, "mes": 0, "hoje": 0, "baus": 0, "sequencias": 0, "raids": 0, "segundos": 0})["segundos"] += s

        motivos = self._query(
            f"SELECT motivo, COUNT(*) AS vezes, SUM(pontos) AS pontos FROM ganhos "
            f"WHERE {farm} AND dia >= ? {filtro} GROUP BY motivo ORDER BY pontos DESC",
            (inicio, *args),
        )
        return {
            "cartoes": cartoes,
            "serie": serie,
            "top_canais": top,
            "contas": sorted(contas.values(), key=lambda c: c["mes"], reverse=True),
            "motivos": motivos,
            "baus": sum(c["baus"] for c in contas.values()),
            "sequencias": sum(c["sequencias"] for c in contas.values()),
            "segundos": sum(horas.values()),
        }

    def compras_automaticas(self, limite=25):
        """As últimas compras feitas pela compra automática (gravadas como "<recompensa> (automático)") e as de hoje."""
        recentes = self._query(
            "SELECT ts, conta, canal, pontos, titulo FROM gastos WHERE titulo LIKE '%(automático)' ORDER BY ts DESC LIMIT ?",
            (limite,),
        )
        hoje = self._query(
            "SELECT COUNT(*) AS compras, COALESCE(SUM(pontos), 0) AS pontos FROM gastos "
            "WHERE titulo LIKE '%(automático)' AND dia = ?",
            (date.today().isoformat(),),
        )[0]
        for r in recentes:
            r["titulo"] = r["titulo"][: -len(" (automático)")] if r["titulo"].endswith(" (automático)") else r["titulo"]
        return {"recentes": recentes, "hoje": {"compras": int(hoje["compras"]), "pontos": int(hoje["pontos"])}}

    def linha_do_tempo(self, conta=None, limite=150, com_assistir=False, antes=None):
        antes = antes or time.time() + 1
        filtro, args = ("AND conta = ?", (conta,)) if conta else ("", ())
        sem_assistir = "" if com_assistir else "AND motivo != 'WATCH'"
        ganhos = self._query(
            f"SELECT ts, conta, canal, 'ganho' AS tipo, motivo, pontos, saldo FROM ganhos "
            f"WHERE ts < ? {sem_assistir} {filtro} ORDER BY ts DESC LIMIT ?",
            (antes, *args, limite),
        )
        eventos = self._query(
            f"SELECT ts, conta, canal, tipo, texto FROM eventos WHERE ts < ? {filtro} ORDER BY ts DESC LIMIT ?",
            (antes, *args, limite),
        )
        gastos = self._query(
            f"SELECT ts, conta, canal, 'gasto' AS tipo, pontos, titulo FROM gastos WHERE ts < ? {filtro} ORDER BY ts DESC LIMIT ?",
            (antes, *args, limite),
        )
        return sorted(ganhos + eventos + gastos, key=lambda e: e["ts"], reverse=True)[:limite]

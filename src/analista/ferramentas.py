"""Ferramentas que o agente pode chamar. Nenhuma escreve; nenhuma executa código.

Tudo o que volta daqui é DADO. Quem monta o contexto do modelo precisa delimitar esse
conteúdo e nunca tratá-lo como instrução.
"""

from __future__ import annotations

import datetime as dt
import decimal
import threading
from pathlib import Path
from typing import Any

import duckdb
from pydantic import BaseModel

from .banco import VISOES_PERMITIDAS, abrir_somente_leitura
from .politica import ConsultaRecusada, validar

Valor = str | int | float | bool | None


class Coluna(BaseModel):
    nome: str
    tipo: str


class Resultado(BaseModel):
    """Resultado de uma consulta. ``truncado`` avisa que havia mais linhas."""

    sql: str
    colunas: list[str]
    linhas: list[list[Valor]]
    truncado: bool = False


class ErroDeConsulta(RuntimeError):
    """A consulta passou na política mas falhou ao executar (ou estourou o tempo)."""


class Ferramentas:
    def __init__(self, banco: Path, max_linhas: int = 200, tempo_limite_s: float = 20.0) -> None:
        self._con = abrir_somente_leitura(banco)
        self.max_linhas = max_linhas
        self.tempo_limite_s = tempo_limite_s

    def fechar(self) -> None:
        self._con.close()

    def listar_tabelas(self) -> list[str]:
        return sorted(VISOES_PERMITIDAS)

    def descrever_tabela(self, nome: str) -> list[Coluna]:
        nome = nome.lower()
        if nome not in VISOES_PERMITIDAS:
            raise ConsultaRecusada(f"relação fora das visões permitidas: {nome}")
        linhas = self._con.execute(f"DESCRIBE {nome}").fetchall()
        return [Coluna(nome=linha[0], tipo=linha[1]) for linha in linhas]

    def amostrar(self, nome: str, linhas: int = 5) -> Resultado:
        nome = nome.lower()
        if nome not in VISOES_PERMITIDAS:
            raise ConsultaRecusada(f"relação fora das visões permitidas: {nome}")
        return self.executar_sql(f"SELECT * FROM {nome} LIMIT {max(1, min(int(linhas), 20))}")

    def executar_sql(self, sql: str, max_linhas: int | None = None) -> Resultado:
        """Valida pela política e executa com limite de linhas e de tempo."""
        consulta = validar(sql)
        limite = max_linhas or self.max_linhas
        estourou = threading.Event()

        def interromper() -> None:
            estourou.set()
            self._con.interrupt()

        relogio = threading.Timer(self.tempo_limite_s, interromper)
        relogio.start()
        try:
            cursor = self._con.execute(consulta.sql)
            colunas = [descricao[0] for descricao in cursor.description or []]
            brutas = cursor.fetchmany(limite + 1)
        except duckdb.Error as erro:
            if estourou.is_set():
                raise ErroDeConsulta(
                    f"a consulta passou de {self.tempo_limite_s:g} s e foi interrompida"
                ) from erro
            raise ErroDeConsulta(str(erro).splitlines()[0]) from erro
        finally:
            relogio.cancel()
        truncado = len(brutas) > limite
        linhas = [[_simples(valor) for valor in linha] for linha in brutas[:limite]]
        return Resultado(sql=consulta.sql, colunas=colunas, linhas=linhas, truncado=truncado)


def _simples(valor: Any) -> Valor:
    """Converte tipos do banco em tipos que viram JSON sem ambiguidade."""
    if valor is None or isinstance(valor, bool | int | float | str):
        return valor
    if isinstance(valor, decimal.Decimal):
        return float(valor)
    if isinstance(valor, dt.datetime | dt.date | dt.time):
        return valor.isoformat()
    return str(valor)

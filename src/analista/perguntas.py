"""Leitura do conjunto de perguntas com gabarito."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, model_validator


class Pergunta(BaseModel):
    id: str
    nivel: Literal[1, 2, 3]
    tipo: Literal["sql", "sem_resposta", "ambigua"]
    pergunta: str
    sql: str | None = None
    ordem_importa: bool = False
    nota: str = ""

    @model_validator(mode="after")
    def _coerente(self) -> Pergunta:
        if (self.tipo == "sql") != (self.sql is not None):
            raise ValueError(f"{self.id}: só perguntas do tipo 'sql' têm gabarito em SQL")
        return self


def ler(arquivo: Path) -> list[Pergunta]:
    perguntas = [
        Pergunta.model_validate(json.loads(linha))
        for linha in arquivo.read_text(encoding="utf-8").splitlines()
        if linha.strip()
    ]
    ids = [p.id for p in perguntas]
    if len(ids) != len(set(ids)):
        raise ValueError(f"{arquivo}: ids repetidos")
    return perguntas

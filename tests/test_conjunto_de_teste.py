"""O conjunto de teste é congelado. Qualquer mudança nele quebra este teste de propósito."""

import hashlib
from collections import Counter
from pathlib import Path

from analista.perguntas import ler
from analista.politica import validar

TESTE = Path(__file__).resolve().parents[1] / "avaliacao/perguntas/teste.jsonl"
DESENVOLVIMENTO = TESTE.with_name("desenvolvimento.jsonl")

# Congelado em 14/11/2026, antes da primeira rodada. Se este valor precisar mudar, os
# resultados medidos com o conjunto anterior deixam de valer e isso tem de ser dito.
SHA256 = "934c57b1a269dccf46a70f0492dd73fb13a8cee49847f21e50d71751b4e0522b"


def test_o_conjunto_de_teste_nao_mudou() -> None:
    assert hashlib.sha256(TESTE.read_bytes()).hexdigest() == SHA256


def test_composicao_do_conjunto_de_teste() -> None:
    perguntas = ler(TESTE)
    assert len(perguntas) == 60
    por_tipo = Counter(p.tipo for p in perguntas)
    assert por_tipo == {"sql": 44, "sem_resposta": 8, "ambigua": 8}
    niveis = Counter(p.nivel for p in perguntas if p.tipo == "sql")
    assert niveis == {1: 14, 2: 16, 3: 14}


def test_gabaritos_do_teste_passam_na_politica() -> None:
    for pergunta in ler(TESTE):
        if pergunta.sql:
            assert validar(pergunta.sql).sql, pergunta.id


def test_nenhuma_pergunta_de_teste_repete_uma_de_desenvolvimento() -> None:
    desenvolvimento = {p.pergunta.strip().lower() for p in ler(DESENVOLVIMENTO)}
    assert not [p.id for p in ler(TESTE) if p.pergunta.strip().lower() in desenvolvimento]

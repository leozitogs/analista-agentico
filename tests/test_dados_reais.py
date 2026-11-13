"""Conferências que só rodam quando o dataset real foi carregado em dados/olist.duckdb."""

from collections.abc import Iterator
from pathlib import Path

import pytest

from analista.ferramentas import Ferramentas
from analista.perguntas import ler

RAIZ = Path(__file__).resolve().parents[1]
BANCO = RAIZ / "dados" / "olist.duckdb"
PERGUNTAS = ler(RAIZ / "avaliacao/perguntas/desenvolvimento.jsonl")

pytestmark = pytest.mark.skipif(not BANCO.is_file(), reason="dataset real não carregado")


@pytest.fixture(scope="module")
def reais() -> Iterator[Ferramentas]:
    instancia = Ferramentas(BANCO)
    yield instancia
    instancia.fechar()


def test_tamanho_conhecido_do_dataset(reais: Ferramentas) -> None:
    assert reais.executar_sql("SELECT count(*) FROM pedidos").linhas == [[99441]]
    assert reais.executar_sql("SELECT count(*) FROM itens_pedido").linhas == [[112650]]


def test_dominios_documentados_no_dicionario(reais: Ferramentas) -> None:
    situacoes = {linha[0] for linha in reais.executar_sql(
        "SELECT DISTINCT situacao FROM pedidos").linhas}
    assert situacoes == {"delivered", "shipped", "canceled", "unavailable", "invoiced",
                         "processing", "created", "approved"}
    formas = {linha[0] for linha in reais.executar_sql(
        "SELECT DISTINCT forma FROM pagamentos").linhas}
    assert formas == {"credit_card", "boleto", "voucher", "debit_card", "not_defined"}


@pytest.mark.parametrize("pergunta", [p for p in PERGUNTAS if p.sql], ids=lambda p: p.id)
def test_gabarito_tem_resultado_completo(reais: Ferramentas, pergunta) -> None:  # type: ignore[no-untyped-def]
    resultado = reais.executar_sql(pergunta.sql)
    assert resultado.linhas and not resultado.truncado

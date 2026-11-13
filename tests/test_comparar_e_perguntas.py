from pathlib import Path

import pytest

from analista.comparar import resultados_iguais
from analista.ferramentas import Ferramentas, Resultado, Valor
from analista.perguntas import Pergunta, ler

DESENVOLVIMENTO = Path(__file__).resolve().parents[1] / "avaliacao/perguntas/desenvolvimento.jsonl"
PERGUNTAS = ler(DESENVOLVIMENTO)


def r(colunas: list[str], linhas: list[list[Valor]], truncado: bool = False) -> Resultado:
    return Resultado(sql="", colunas=colunas, linhas=linhas, truncado=truncado)


def test_nome_de_coluna_e_ordem_das_linhas_nao_importam() -> None:
    gabarito = r(["uf", "n"], [["PE", 3], ["SP", 9]])
    assert resultados_iguais(r(["estado", "total"], [["SP", 9], ["PE", 3]]), gabarito)


def test_ordem_das_linhas_importa_quando_a_pergunta_pede() -> None:
    gabarito = r(["v", "receita"], [["a", 9.0], ["b", 3.0]])
    invertido = r(["v", "receita"], [["b", 3.0], ["a", 9.0]])
    assert resultados_iguais(invertido, gabarito)
    assert not resultados_iguais(invertido, gabarito, ordem_importa=True)


def test_ordem_das_colunas_nao_importa() -> None:
    assert resultados_iguais(r(["n", "uf"], [[3, "PE"]]), r(["uf", "n"], [["PE", 3]]))


def test_inteiro_e_decimal_do_mesmo_valor_sao_iguais() -> None:
    assert resultados_iguais(r(["x"], [[10]]), r(["x"], [[10.0]]))


def test_arredondamento_do_agente_e_aceito_a_partir_de_duas_casas() -> None:
    gabarito = r(["x"], [[8.112366538820359]])
    assert resultados_iguais(r(["x"], [[8.11]]), gabarito)
    assert resultados_iguais(r(["x"], [[8.1124]]), gabarito)
    assert not resultados_iguais(r(["x"], [[8.1]]), gabarito)  # uma casa não basta
    assert not resultados_iguais(r(["x"], [[8]]), gabarito)


def test_valor_quase_igual_nao_e_igual() -> None:
    """Achado da revisão: a consulta sem o filtro dava 8,1117 e passava por 8,1124."""
    assert not resultados_iguais(r(["x"], [[8.111712]]), r(["x"], [[8.112366]]))
    assert not resultados_iguais(r(["x"], [[4.0888123]]), r(["x"], [[4.0864206]]))
    assert not resultados_iguais(r(["x"], [[0.0312]]), r(["x"], [[0.0349]]))


def test_colunas_do_mesmo_tipo_nao_trocam_de_lugar() -> None:
    """Achado da revisão: trocar duas colunas numéricas muda a resposta."""
    assert not resultados_iguais(r(["uf", "a", "b"], [["SP", 20, 10]]),
                                 r(["uf", "a", "b"], [["SP", 10, 20]]))
    assert resultados_iguais(r(["a", "b", "uf"], [[10, 20, "SP"]]),
                             r(["uf", "a", "b"], [["SP", 10, 20]]))
    assert not resultados_iguais(r(["a", "b"], [["x", "y"]]), r(["a", "b"], [["y", "x"]]))


def test_booleano_nao_e_numero_e_nan_e_igual_a_nan() -> None:
    assert not resultados_iguais(r(["x"], [[True]]), r(["x"], [[1]]))
    assert resultados_iguais(r(["x"], [[float("nan")]]), r(["x"], [[float("nan")]]))
    assert resultados_iguais(r(["x"], [[None]]), r(["x"], [[None]]))
    assert not resultados_iguais(r(["x"], [[None]]), r(["x"], [[0]]))


def test_nao_ha_acerto_parcial() -> None:
    gabarito = r(["uf", "n"], [["PE", 3], ["SP", 9]])
    assert not resultados_iguais(r(["uf", "n"], [["PE", 3]]), gabarito)
    assert not resultados_iguais(r(["uf", "n"], [["PE", 3], ["SP", 8]]), gabarito)
    assert not resultados_iguais(r(["uf"], [["PE"], ["SP"]]), gabarito)
    assert not resultados_iguais(r(["uf", "n", "extra"], [["PE", 3, 1], ["SP", 9, 1]]), gabarito)


def test_linhas_repetidas_contam() -> None:
    assert not resultados_iguais(r(["x"], [[1], [1], [2]]), r(["x"], [[1], [2], [2]]))


def test_resultado_truncado_nunca_e_acerto() -> None:
    igual = r(["x"], [[1]])
    assert not resultados_iguais(r(["x"], [[1]], truncado=True), igual)


def test_composicao_do_conjunto_de_desenvolvimento() -> None:
    assert len(PERGUNTAS) == 20
    assert {p.nivel for p in PERGUNTAS} == {1, 2, 3}
    assert sum(p.tipo == "sem_resposta" for p in PERGUNTAS) == 2
    assert sum(p.tipo == "ambigua" for p in PERGUNTAS) == 2


@pytest.mark.parametrize("pergunta", [p for p in PERGUNTAS if p.sql], ids=lambda p: p.id)
def test_gabarito_passa_na_politica_e_executa(ferramentas: Ferramentas, pergunta: Pergunta) -> None:
    assert pergunta.sql is not None
    resultado = ferramentas.executar_sql(pergunta.sql)
    assert resultado.linhas, "gabarito sem linhas nos dados sintéticos"
    assert not resultado.truncado
    assert resultados_iguais(resultado, resultado, pergunta.ordem_importa)

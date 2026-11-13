from typing import Any

import pytest

from analista.ferramentas import Resultado
from analista.provedor import (
    ErroDeProvedor,
    ErroPassageiro,
    ProvedorGemini,
    interpretar,
    turno_resultados,
    turno_usuario,
)
from analista.verificar import numeros_do_texto, numeros_sem_origem


def resultado(*linhas: list[Any]) -> Resultado:
    return Resultado(sql="", colunas=["a"] * len(linhas[0]), linhas=list(linhas))


# ---------- provedor

def test_pedido_ao_gemini_tem_o_formato_da_api(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GEMINI_API_KEY", "chave-de-teste")
    visto: dict[str, Any] = {}

    def transporte(url: str, corpo: dict[str, Any], cabecalhos: dict[str, str], t: float) -> Any:
        visto.update(url=url, corpo=corpo, cabecalhos=cabecalhos)
        return {
            "candidates": [{"content": {"role": "model", "parts": [
                {"text": "pensando", "thought": True},
                {"functionCall": {"name": "executar_sql", "args": {"sql": "SELECT 1"}},
                 "thoughtSignature": "abc"},
            ]}}],
            "usageMetadata": {"promptTokenCount": 100, "candidatesTokenCount": 20,
                              "thoughtsTokenCount": 7},
        }

    provedor = ProvedorGemini("modelo-x", transporte=transporte)
    resposta = provedor.gerar("sistema", [turno_usuario("oi")], [{"name": "executar_sql"}])

    assert visto["url"].endswith("/models/modelo-x:generateContent")
    assert visto["cabecalhos"]["x-goog-api-key"] == "chave-de-teste"
    assert "chave-de-teste" not in visto["url"]
    assert visto["corpo"]["systemInstruction"]["parts"][0]["text"] == "sistema"
    assert visto["corpo"]["tools"] == [{"functionDeclarations": [{"name": "executar_sql"}]}]
    assert resposta.chamadas[0].nome == "executar_sql"
    assert resposta.chamadas[0].argumentos == {"sql": "SELECT 1"}
    assert resposta.texto == ""  # o raciocínio do modelo não é resposta
    assert (resposta.tokens_entrada, resposta.tokens_saida) == (100, 27)
    # o turno volta cru, com a assinatura, para o pedido seguinte
    assert resposta.conteudo["parts"][1]["thoughtSignature"] == "abc"


def _ok() -> dict[str, Any]:
    return {"candidates": [{"content": {"parts": [{"text": "oi"}]}}]}


def test_erro_passageiro_e_repetido_e_o_definitivo_nao(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GEMINI_API_KEY", "chave-de-teste")
    respostas: list[Any] = [ErroPassageiro("HTTP 503"), ErroPassageiro("tempo"), _ok()]
    corpos: list[dict[str, Any]] = []

    def transporte(url: str, corpo: dict[str, Any], cabecalhos: dict[str, str], t: float) -> Any:
        corpos.append(corpo)
        item = respostas.pop(0)
        if isinstance(item, Exception):
            raise item
        return item

    provedor = ProvedorGemini("m", transporte=transporte, espera_s=0, raciocinio="low")
    assert provedor.gerar("s", [turno_usuario("oi")], []).texto == "oi"
    assert provedor.repeticoes == 2
    assert corpos[0]["generationConfig"]["thinkingConfig"] == {"thinkingLevel": "low"}

    def sempre_fora(url: str, corpo: Any, cabecalhos: Any, t: float) -> Any:
        raise ErroPassageiro("HTTP 503")

    insistente = ProvedorGemini("m", transporte=sempre_fora, espera_s=0, tentativas=3)
    with pytest.raises(ErroPassageiro):
        insistente.gerar("s", [], [])
    assert insistente.repeticoes == 2

    def recusado(url: str, corpo: Any, cabecalhos: Any, t: float) -> Any:
        raise ErroDeProvedor("HTTP 400: pedido inválido")

    direto = ProvedorGemini("m", transporte=recusado, espera_s=0)
    with pytest.raises(ErroDeProvedor, match="400"):
        direto.gerar("s", [], [])
    assert direto.repeticoes == 0


def test_sem_chave_ou_sem_modelo_e_erro_claro(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("ANALISTA_MODELO", raising=False)
    with pytest.raises(ErroDeProvedor, match="ANALISTA_MODELO"):
        ProvedorGemini()
    with pytest.raises(ErroDeProvedor, match="GEMINI_API_KEY"):
        ProvedorGemini("modelo-x").gerar("s", [], [])


def test_resposta_bloqueada_ou_vazia_e_erro() -> None:
    with pytest.raises(ErroDeProvedor, match="SAFETY"):
        interpretar({"promptFeedback": {"blockReason": "SAFETY"}})
    with pytest.raises(ErroDeProvedor, match="MAX_TOKENS"):
        interpretar({"candidates": [{"finishReason": "MAX_TOKENS", "content": {}}]})


def test_turno_de_resultados_preserva_a_ordem() -> None:
    turno = turno_resultados([("a", {"x": 1}), ("b", {"erro": "y"})])
    assert turno["role"] == "user"
    assert [p["functionResponse"]["name"] for p in turno["parts"]] == ["a", "b"]


# ---------- verificação de números

@pytest.mark.parametrize(("texto", "esperado"), [
    ("R$ 2.869.361,27 em boleto", "2869361.27"),
    ("nota média de 4,09", "4.09"),
    ("8.1% dos pedidos", "8.1"),
    ("foram 99441 pedidos.", "99441"),
    ("1,234.50 dólares", "1234.50"),
])
def test_le_numeros_em_formato_brasileiro_e_americano(texto: str, esperado: str) -> None:
    assert str(numeros_do_texto(texto)[0][1]) == esperado


def test_numero_arredondado_do_resultado_e_aceito() -> None:
    r = resultado([4.08642062404257, 99441, 2869361.27])
    assert numeros_sem_origem("A nota média é 4,09 em 99.441 pedidos (R$ 2.869.361,27).", r) == []
    assert numeros_sem_origem("A nota média é 4,1.", r) == []
    assert numeros_sem_origem("A nota média é 4.", r) == []


def test_numero_que_nao_esta_no_resultado_e_apontado() -> None:
    r = resultado([4.08642062404257])
    assert numeros_sem_origem("A nota é 4,09, 12% acima da meta de 3,65.", r) == ["12", "3,65"]


def test_numeros_da_pergunta_e_contagem_de_linhas_sao_aceitos() -> None:
    r = resultado(["a", 10.0], ["b", 7.5], ["c", 3.0])
    texto = "Os 3 maiores de 2017 são a (10), b (7,5) e c (3)."
    assert numeros_sem_origem(texto, r, "Quais os 3 maiores vendedores de 2017?") == []
    assert numeros_sem_origem("Em 2018 foram 10.", r, "Quais os 3 maiores?") == ["2018"]


def test_datas_e_numeros_dentro_de_texto_do_resultado() -> None:
    r = resultado(["2017-03-01T00:00:00", 374344.3])
    assert numeros_sem_origem("Em 2017-03-01 a receita foi 374.344,30.", r) == []


def test_sem_resultado_todo_numero_fica_sem_origem() -> None:
    assert numeros_sem_origem("Foram 42 pedidos.", None) == ["42"]


def test_numero_infinito_ou_enorme_no_resultado_nao_derruba_a_verificacao() -> None:
    """Achado da revisão: 1e30 ou infinito no resultado levantava exceção."""
    assert numeros_sem_origem("O valor é 5.", resultado([1e30])) == ["5"]
    assert numeros_sem_origem("O valor é 5.", resultado([float("inf")])) == ["5"]
    assert numeros_sem_origem("O valor é 5.", resultado([float("nan"), 5])) == []


def test_chamada_de_funcao_malformada_e_erro_do_provedor() -> None:
    sem_nome = {"candidates": [{"content": {"parts": [{"functionCall": {"args": {}}}]}}]}
    args_errados = {"candidates": [{"content": {"parts": [
        {"functionCall": {"name": "executar_sql", "args": "SELECT 1"}}]}}]}
    for resposta in (sem_nome, args_errados):
        with pytest.raises(ErroDeProvedor, match="malformada"):
            interpretar(resposta)

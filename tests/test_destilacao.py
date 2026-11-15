"""Os três filtros da destilação, com um professor roteirizado. Nenhuma chamada de rede."""

import json

from analista.destilacao import (
    Par,
    alvo_do_aluno,
    conferir_em_etapas,
    destilar,
    escrever_em_etapas,
    filtrar_por_concordancia,
    filtrar_por_execucao,
    filtrar_vazamento,
    filtrar_vazamento_por_resultado,
    ler_saida_do_aluno,
    pedir_pares,
    pedir_recusas,
    sem_repeticao,
    semelhanca,
)
from analista.ferramentas import Ferramentas
from analista.provedor import ErroDeCota, ProvedorRoteirizado

CONTAGEM = "SELECT count(*) FROM pedidos"
CANCELADOS = "SELECT count(*) FROM pedidos WHERE situacao = 'canceled'"


def par(pergunta: str, sql: str) -> Par:
    return Par(tipo="sql", pergunta=pergunta, sql=sql)


def lote(*pares: tuple[str, str]) -> str:
    return json.dumps([{"pergunta": p, "sql": s} for p, s in pares], ensure_ascii=False)


def test_professor_devolve_lista_mesmo_com_texto_em_volta() -> None:
    resposta = "Claro!\n```json\n" + lote(("Quantos pedidos?", CONTAGEM)) + "\n```\nÉ isso."
    pares = pedir_pares(ProvedorRoteirizado([resposta]), "(dic)", "filtro", 1)
    assert [(p.pergunta, p.sql, p.habilidade) for p in pares] == [
        ("Quantos pedidos?", CONTAGEM, "filtro")]


def test_item_malformado_do_professor_e_ignorado() -> None:
    resposta = json.dumps([{"pergunta": "ok?", "sql": CONTAGEM}, {"pergunta": "sem sql"}, "lixo",
                           {"pergunta": 3, "sql": CONTAGEM}])
    assert len(pedir_pares(ProvedorRoteirizado([resposta]), "(dic)", "filtro", 4)) == 1
    assert pedir_pares(ProvedorRoteirizado(["não sei"]), "(dic)", "filtro", 4) == []


def test_as_perguntas_de_teste_nunca_entram_no_prompt_do_professor(
    ferramentas: Ferramentas,
) -> None:
    provedor = ProvedorRoteirizado([lote(("Quantos pedidos existem?", CONTAGEM))] * 40)
    segredo = "Qual o estado com o maior percentual de atraso?"
    destilar(provedor, ferramentas, "(dic)", [segredo], lotes_por_habilidade=1,
             exemplos=["Quantos pedidos foram cancelados?"])
    enviado = json.dumps(provedor.recebidos, ensure_ascii=False)
    assert segredo not in enviado and "Quantos pedidos foram cancelados?" in enviado


def test_filtro_por_execucao(ferramentas: Ferramentas) -> None:
    pares = [
        par("certa", CONTAGEM),
        par("apaga", "DELETE FROM pedidos"),
        par("coluna que não existe", "SELECT inexistente FROM pedidos"),
        par("vazia", "SELECT * FROM pedidos WHERE situacao = 'nada'"),
        par("esquema bruto", "SELECT * FROM bruto.pedidos"),
        Par(tipo="sem_resposta", pergunta="Qual a margem?", texto="não há custo"),
    ]
    bons = filtrar_por_execucao(ferramentas, pares)
    assert [p.pergunta for p in bons] == ["certa", "Qual a margem?"]


def test_filtro_por_concordancia(ferramentas: Ferramentas) -> None:
    pares = [
        par("Quantos pedidos existem?", CONTAGEM),
        par("Quantos pedidos foram cancelados?", CANCELADOS),
        par("Quantos pedidos?", CONTAGEM),
        Par(tipo="ambigua", pergunta="Quais os melhores?", texto="por quê?"),
    ]
    # às cegas: acerta a primeira de outro jeito, erra a segunda, não responde à terceira
    segunda = json.dumps(["SELECT count(pedido_id) AS n FROM pedidos", CONTAGEM, ""])
    provedor = ProvedorRoteirizado([segunda])
    bons = filtrar_por_concordancia(provedor, ferramentas, "(dic)", pares)
    assert [p.pergunta for p in bons] == ["Quantos pedidos existem?", "Quais os melhores?"]
    # a segunda chamada vê as perguntas, nunca as consultas originais
    visto = provedor.recebidos[0][0]["parts"][0]["text"]
    assert "Quantos pedidos foram cancelados?" in visto and "canceled" not in visto


def test_filtro_de_vazamento_e_maior_semelhanca_restante() -> None:
    teste = ["Quantos pedidos foram pagos com mais de uma forma de pagamento diferente?"]
    pares = [
        par("Quantos pedidos foram pagos com mais de uma forma de pagamento diferente?", CONTAGEM),
        par("quantos pedidos foram pagos com mais de uma forma de pagamento diferente", CONTAGEM),
        par("Quantos pedidos foram pagos com mais de uma forma de pagamento distinta?", CONTAGEM),
        par("Qual a nota média das avaliações?", CONTAGEM),
    ]
    bons, maior = filtrar_vazamento(pares, teste)
    assert [p.pergunta for p in bons] == ["Qual a nota média das avaliações?"]
    assert 0.0 < maior < 0.85
    assert semelhanca("Média de NOTA?", "media de nota") == 1.0
    assert filtrar_vazamento(pares, []) == (pares, 0.0)


def test_perguntas_repetidas_saem() -> None:
    pares = [par("Quantos pedidos?", CONTAGEM), par("quantos PEDIDOS", CANCELADOS),
             par("Quantos clientes?", CONTAGEM)]
    assert [p.pergunta for p in sem_repeticao(pares)] == ["Quantos pedidos?", "Quantos clientes?"]


def test_recusas_e_formato_do_aluno() -> None:
    resposta = json.dumps([{"pergunta": "Qual a margem?", "texto": "Não há custo nos dados."}])
    recusas = pedir_recusas(ProvedorRoteirizado([resposta]), "(dic)", "sem_resposta", 1)
    assert alvo_do_aluno(recusas[0]) == "SEM_RESPOSTA: Não há custo nos dados."
    ambigua = Par(tipo="ambigua", pergunta="Os melhores?", texto="Por receita ou por nota?")
    assert alvo_do_aluno(ambigua) == "ESCLARECER: Por receita ou por nota?"
    assert alvo_do_aluno(par("x", " SELECT 1 FROM pedidos ")) == "SELECT 1 FROM pedidos"


def test_leitura_da_saida_do_aluno() -> None:
    assert ler_saida_do_aluno("```sql\nSELECT 1 FROM pedidos;\n```") == (
        "resposta", "SELECT 1 FROM pedidos")
    assert ler_saida_do_aluno("sem_resposta: não há custo") == ("sem_resposta", "não há custo")
    assert ler_saida_do_aluno("ESCLARECER: por receita?") == ("esclarecimento", "por receita?")
    assert ler_saida_do_aluno("") == ("resposta", "")


def test_funil_conta_cada_etapa(ferramentas: Ferramentas) -> None:
    vazamento = "Quantos pedidos foram comprados em 2016?"
    escritos = lote(
        ("Quantos pedidos existem no total?", CONTAGEM),
        ("Quantos pedidos foram cancelados no período?", CANCELADOS),
        ("Consulta que não roda", "SELECT nada FROM pedidos"),
        (vazamento, "SELECT count(*) FROM pedidos WHERE year(comprado_em) = 2016"),
    )
    vazio = "[]"
    as_cegas = json.dumps([CONTAGEM, CONTAGEM,
                           "SELECT count(*) FROM pedidos WHERE year(comprado_em) = 2016"])
    recusa = json.dumps([{"pergunta": "Qual a margem?", "texto": "falta o custo"}])
    ambigua = json.dumps([{"pergunta": "Quais os melhores?", "texto": "por quê?"}])
    roteiro = [escritos] + [vazio] * 10 + [recusa, ambigua, as_cegas]
    pares, funil = destilar(ProvedorRoteirizado(roteiro), ferramentas, "(dic)", [vazamento],
                            lotes_por_habilidade=1, recusas_de_cada_tipo=1)
    assert funil.escritos == 6 and funil.apos_execucao == 5
    assert funil.apos_concordancia == 4 and funil.apos_vazamento == 3
    assert funil.descartes == {"execucao": 1, "concordancia": 1, "vazamento": 1}
    assert funil.pedidos_ao_professor == 14
    assert sorted(p.tipo for p in pares) == ["ambigua", "sem_resposta", "sql"]


class AcabaACota(ProvedorRoteirizado):
    """Devolve o roteiro e, quando ele acaba, a cota também acaba."""

    def gerar(self, sistema, conteudos, ferramentas):  # type: ignore[no-untyped-def]
        if not self._roteiro:
            raise ErroDeCota("HTTP 429: per day")
        return super().gerar(sistema, conteudos, ferramentas)


def test_escrita_em_etapas_para_na_cota_e_retoma_de_onde_parou() -> None:
    um = lote(("Quantos pedidos existem?", CONTAGEM))
    primeira = list(escrever_em_etapas(AcabaACota([um] * 3), "(dic)", lotes_por_habilidade=1))
    assert [numero for numero, _ in primeira] == [0, 1, 2]  # parou sem erro no quarto
    provedor = AcabaACota([um] * 20)
    segunda = list(escrever_em_etapas(provedor, "(dic)", lotes_por_habilidade=1,
                                      recusas_de_cada_tipo=15, pular=3))
    assert [numero for numero, _ in segunda] == list(range(3, 13))  # 11 habilidades + 2 recusas
    # cada lote recebe um tema, e o tema muda de um lote para o outro
    temas = {c[0]["parts"][0]["text"].split("perguntas sobre ")[1].split(".")[0]
             for c in provedor.recebidos[:8]}
    assert len(temas) == 8


def test_conferencia_em_etapas_guarda_o_que_ja_foi_conferido(ferramentas: Ferramentas) -> None:
    pares = [par(f"Quantos pedidos existem? ({i})", CONTAGEM) for i in range(25)]
    uma_resposta = json.dumps([CONTAGEM] * 10)
    vereditos: dict[str, bool] = {}
    for novo in conferir_em_etapas(AcabaACota([uma_resposta]), ferramentas, "(dic)", pares,
                                   vereditos):
        vereditos.update(novo)
    assert len(vereditos) == 10 and all(vereditos.values())  # a cota acabou no segundo lote
    resto = AcabaACota([uma_resposta, json.dumps([CANCELADOS] * 5)])
    for novo in conferir_em_etapas(resto, ferramentas, "(dic)", pares, vereditos):
        vereditos.update(novo)
    assert len(vereditos) == 25 and sum(vereditos.values()) == 20
    assert len(resto.recebidos) == 2  # as 10 já conferidas não voltaram ao professor


def test_vazamento_por_resultado_pega_a_mesma_pergunta_com_outras_palavras(
    ferramentas: Ferramentas,
) -> None:
    de_teste = ["SELECT count(*) FROM pedidos p WHERE NOT EXISTS "
                "(SELECT 1 FROM itens_pedido i WHERE i.pedido_id = p.pedido_id)", CANCELADOS]
    pares = [
        # mesma pergunta do teste, escrita de outro jeito e com outra consulta
        par("Quantos pedidos foram feitos sem nenhum item associado?",
            "SELECT count(*) FROM pedidos p LEFT JOIN itens_pedido i USING (pedido_id) "
            "WHERE i.pedido_id IS NULL"),
        par("Quantos pedidos existem?", CONTAGEM),
        Par(tipo="sem_resposta", pergunta="Qual a margem?", texto="não há custo"),
    ]
    bons = filtrar_vazamento_por_resultado(ferramentas, pares, de_teste)
    assert [p.pergunta for p in bons] == ["Quantos pedidos existem?", "Qual a margem?"]
    # o filtro por texto, sozinho, deixaria passar
    assert len(filtrar_vazamento(pares, ["Quantos pedidos não têm nenhum item?"])[0]) == 3

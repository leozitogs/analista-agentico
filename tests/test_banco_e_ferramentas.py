from pathlib import Path

import duckdb
import pytest

from analista import sintetico
from analista.banco import VISOES_PERMITIDAS, ErroDeCarga, abrir_somente_leitura, carregar
from analista.ferramentas import ErroDeConsulta, Ferramentas
from analista.politica import ConsultaRecusada


def test_carga_cria_todas_as_visoes(ferramentas: Ferramentas) -> None:
    assert set(ferramentas.listar_tabelas()) == VISOES_PERMITIDAS
    for nome in ferramentas.listar_tabelas():
        assert ferramentas.descrever_tabela(nome)
        assert ferramentas.amostrar(nome, 3).linhas


def test_tipos_das_visoes(ferramentas: Ferramentas) -> None:
    tipos = {c.nome: c.tipo for c in ferramentas.descrever_tabela("pedidos")}
    assert tipos["comprado_em"] == "TIMESTAMP" and tipos["entregue_em"] == "TIMESTAMP"
    precos = {c.nome: c.tipo for c in ferramentas.descrever_tabela("itens_pedido")}
    assert precos["preco"].startswith("DECIMAL")


def test_carga_recusa_arquivo_faltando(tmp_path: Path) -> None:
    with pytest.raises(ErroDeCarga, match="ausentes"):
        carregar(tmp_path, tmp_path / "x.duckdb")


def test_carga_recusa_colunas_diferentes(tmp_path: Path) -> None:
    sintetico.gerar(tmp_path / "csv", pedidos=5)
    alvo = tmp_path / "csv" / "olist_sellers_dataset.csv"
    alvo.write_text(alvo.read_text("utf-8").replace("seller_state", "estado"), "utf-8")
    with pytest.raises(ErroDeCarga, match="colunas"):
        carregar(tmp_path / "csv", tmp_path / "x.duckdb")


def test_limite_de_linhas_avisa_que_truncou(ferramentas: Ferramentas) -> None:
    resultado = ferramentas.executar_sql("SELECT pedido_id FROM pedidos")
    assert len(resultado.linhas) == 50 and resultado.truncado
    pequeno = ferramentas.executar_sql("SELECT count(*) FROM pedidos")
    assert pequeno.linhas == [[300]] and not pequeno.truncado


def test_valores_viram_tipos_simples(ferramentas: Ferramentas) -> None:
    linha = ferramentas.executar_sql(
        "SELECT sum(preco), min(comprado_em), NULL FROM itens_pedido JOIN pedidos USING (pedido_id)"
    ).linhas[0]
    assert isinstance(linha[0], float) and isinstance(linha[1], str) and linha[2] is None


def test_politica_vale_para_todas_as_ferramentas(ferramentas: Ferramentas) -> None:
    with pytest.raises(ConsultaRecusada):
        ferramentas.executar_sql("DELETE FROM pedidos")
    with pytest.raises(ConsultaRecusada):
        ferramentas.descrever_tabela("bruto.pedidos")
    with pytest.raises(ConsultaRecusada):
        ferramentas.amostrar("pedidos; DROP VIEW pedidos")


def test_erro_de_execucao_tem_mensagem(ferramentas: Ferramentas) -> None:
    with pytest.raises(ErroDeConsulta, match="coluna_que_nao_existe"):
        ferramentas.executar_sql("SELECT coluna_que_nao_existe FROM pedidos")


def test_consulta_longa_e_interrompida(banco: Path) -> None:
    lentas = Ferramentas(banco, tempo_limite_s=0.2)
    try:
        with pytest.raises(ErroDeConsulta, match="interrompida"):
            lentas.executar_sql(
                "SELECT count(*) FROM itens_pedido a, itens_pedido b, "
                "itens_pedido c, itens_pedido d"
            )
        assert lentas.executar_sql("SELECT count(*) FROM pedidos").linhas == [[300]]
    finally:
        lentas.fechar()


def test_segunda_barreira_o_banco_nao_aceita_escrita_nem_acesso_externo(banco: Path) -> None:
    """Mesmo sem a política, a conexão em si não escreve nem lê arquivos."""
    con = abrir_somente_leitura(banco)
    try:
        for sql in (
            "DELETE FROM bruto.pedidos",
            "CREATE TABLE t (a INT)",
            "SELECT * FROM read_csv('qualquer.csv')",
            "SET enable_external_access = true",
            "COPY (SELECT 1) TO 'saida.csv'",
        ):
            with pytest.raises(duckdb.Error):
                con.execute(sql)
    finally:
        con.close()


def test_duas_conexoes_ao_mesmo_banco_ficam_as_duas_protegidas(banco: Path) -> None:
    """O avaliador abre uma conexão para o agente e outra para o juiz."""
    primeira, segunda = Ferramentas(banco), Ferramentas(banco)
    try:
        assert segunda.executar_sql("SELECT count(*) FROM pedidos").linhas == [[300]]
    finally:
        primeira.fechar()
        segunda.fechar()
    a, b = abrir_somente_leitura(banco), abrir_somente_leitura(banco)
    try:
        for con in (a, b):
            with pytest.raises(duckdb.Error):
                con.execute("SELECT * FROM read_csv('qualquer.csv')")
            with pytest.raises(duckdb.Error):
                con.execute("SET enable_external_access = true")
    finally:
        a.close()
        b.close()

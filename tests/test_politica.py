"""A política recusa tudo o que não é SELECT sobre as visões permitidas."""

import pytest

from analista.politica import ConsultaRecusada, validar

ACEITAS = [
    "SELECT count(*) FROM pedidos",
    "select uf, count(*) from vendedores group by uf order by 2 desc limit 5",
    "WITH t AS (SELECT pedido_id, sum(valor) v FROM pagamentos GROUP BY 1) SELECT avg(v) FROM t",
    "SELECT p.situacao, c.uf FROM pedidos p JOIN clientes c ON c.cliente_id = p.cliente_id",
    "SELECT uf FROM clientes UNION SELECT uf FROM vendedores",
    "SELECT forma, 100.0 * sum(valor) / sum(sum(valor)) OVER () FROM pagamentos GROUP BY forma",
    "SELECT date_trunc('month', comprado_em), count(*) FROM pedidos GROUP BY 1",
    "SELECT * FROM (SELECT nota FROM avaliacoes) WHERE nota >= 4",
    "SELECT 'drop table pedidos' AS texto FROM pedidos LIMIT 1",
    "SELECT * FROM pedidos -- ; DROP VIEW pedidos",
    "FROM pedidos SELECT count(*)",
    "SELECT * EXCLUDE (pedido_id) FROM pedidos",
    # CTE legítima, inclusive em subconsulta e com o nome de uma visão permitida
    "SELECT * FROM (WITH t AS (SELECT 1 AS a) SELECT a FROM t) x JOIN pedidos ON true",
    "WITH pedidos AS (SELECT * FROM pedidos WHERE situacao = 'delivered') SELECT count(*) FROM pedidos",
    "SELECT median(valor), quantile_cont(valor, 0.9), count_if(valor > 100) FROM pagamentos",
    "SELECT strftime(comprado_em, '%Y-%m'), dayofweek(comprado_em), year(comprado_em) FROM pedidos",
    "SELECT date_diff('day', comprado_em, entregue_em), round(1.234, 2), coalesce(NULL, 1) FROM pedidos",
    "SELECT c.uf FROM clientes c, LATERAL (SELECT 1 FROM pedidos p WHERE p.cliente_id = c.cliente_id)",
]

RECUSADAS = [
    # escrita e DDL
    "DELETE FROM pedidos",
    "UPDATE pedidos SET situacao = 'x'",
    "INSERT INTO pedidos SELECT * FROM pedidos",
    "DROP VIEW pedidos",
    "CREATE TABLE t AS SELECT * FROM pedidos",
    "ALTER TABLE pedidos ADD COLUMN x INT",
    "TRUNCATE pedidos",
    # mais de uma instrução
    "SELECT 1 FROM pedidos; DROP VIEW pedidos",
    "SELECT 1 FROM pedidos; SELECT 2 FROM pedidos",
    # comandos e configuração
    "PRAGMA database_list",
    "SET enable_external_access = true",
    "ATTACH 'outro.duckdb' AS o",
    "COPY pedidos TO 'saida.csv'",
    "COPY (SELECT * FROM pedidos) TO 'saida.csv'",
    "INSTALL httpfs",
    "LOAD httpfs",
    "EXPORT DATABASE 'pasta'",
    "CALL pragma_version()",
    # relações fora da lista
    "SELECT * FROM bruto.pedidos",
    "SELECT * FROM geolocalizacao",
    "SELECT * FROM information_schema.tables",
    "SELECT * FROM 'dados/brutos/olist_orders_dataset.csv'",
    "SELECT * FROM pedidos p JOIN bruto.clientes c ON true",
    "WITH x AS (SELECT * FROM bruto.itens) SELECT * FROM x",
    "SELECT (SELECT count(*) FROM bruto.pedidos) FROM pedidos",
    # funções que alcançam arquivos, rede ou configuração
    "SELECT * FROM read_csv('segredo.csv')",
    "SELECT * FROM read_parquet('s3://balde/arquivo.parquet')",
    "SELECT * FROM read_text('/etc/passwd')",
    "SELECT * FROM glob('*')",
    "SELECT * FROM duckdb_settings()",
    "SELECT getenv('GEMINI_API_KEY') FROM pedidos",
    "SELECT current_setting('access_mode') FROM pedidos",
    "SELECT * FROM query('SELECT 1')",
    # tentativas de contorno (sessão de ataque do B0)
    "SELECT * FROM pedidos, (SELECT * FROM READ_CSV_AUTO('x'))",
    'SELECT * FROM "bruto"."pedidos"',
    "SELECT * FROM memory.main.pedidos",
    "FROM bruto.pedidos",
    "SELECT * FROM (FROM bruto.pedidos)",
    "WITH pedidos AS (SELECT * FROM bruto.pedidos) SELECT * FROM pedidos",
    "SELECT * FROM pedidos WHERE pedido_id IN (SELECT order_id FROM bruto.itens)",
    "SELECT * FROM pedidos UNION ALL SELECT * FROM bruto.pedidos",
    "SELECT * FROM pedidos p, LATERAL (SELECT * FROM read_text(p.pedido_id))",
    "SELECT * FROM pedidos WHERE pedido_id = (SELECT content FROM read_text('x'))",
    "SELECT read_blob('x') FROM pedidos",
    "SELECT * FROM duckdb_tables",
    "SELECT * FROM sqlite_master",
    "SELECT * FROM range(100000000000)",
    "SELECT * FROM generate_series(1, 1000000000000)",
    "SUMMARIZE pedidos",
    "DESCRIBE pedidos",
    "SHOW TABLES",
    "EXPLAIN ANALYZE SELECT * FROM pedidos",
    "PIVOT pedidos ON situacao USING count(*)",
    "CHECKPOINT",
    "VACUUM",
    "BEGIN",
    "CALL duckdb_secrets()",
    "CREATE OR REPLACE VIEW pedidos AS SELECT 1",
    # achados da revisão independente: CTE de subconsulta liberando nome de sistema
    "SELECT * FROM (WITH pg_settings AS (SELECT 1) SELECT 1) t, pg_settings",
    "SELECT * FROM (WITH duckdb_databases AS (SELECT 1) SELECT 1) t, duckdb_databases",
    "SELECT * FROM (WITH duckdb_tables AS (SELECT 1) SELECT 1) t, duckdb_tables",
    "SELECT * FROM (WITH sqlite_master AS (SELECT 1) SELECT 1) t, sqlite_master",
    "SELECT * FROM (WITH pg_views AS (SELECT 1) SELECT 1) t, pg_views",
    "SELECT * FROM (WITH segredo AS (SELECT 1) SELECT 1) t, segredo",
    "WITH pg_settings AS (SELECT 1) SELECT * FROM pg_settings",
    # achados da revisão: função de tabela por LATERAL
    "SELECT * FROM LATERAL range(3)",
    "SELECT * FROM pedidos, LATERAL json_each('{\"a\":1}')",
    "SELECT * FROM pedidos, LATERAL icu_calendar_names()",
    "SELECT count(*) FROM pedidos, LATERAL generate_series(1, 100000000000)",
    "SELECT * FROM pedidos, LATERAL parquet_file_metadata('x')",
    "SELECT * FROM pedidos, LATERAL parquet_kv_metadata('C:/Windows/win.ini')",
    # funções fora da lista de permissão
    "SELECT getvariable('x') FROM pedidos",
    "SELECT repeat('x', 2000000000) FROM pedidos",
    "SELECT version() FROM pedidos",
    "SELECT current_user FROM pedidos",
    "SELECT funcao_que_ninguem_conhece(pedido_id) FROM pedidos",
    "SELECT unnest(range(100000000000))",
    # lixo
    "",
    "isto não é sql",
    "SELECT FROM WHERE",
]


@pytest.mark.parametrize("sql", ACEITAS)
def test_aceita(sql: str) -> None:
    assert validar(sql).sql


@pytest.mark.parametrize("sql", RECUSADAS)
def test_recusa(sql: str) -> None:
    with pytest.raises(ConsultaRecusada):
        validar(sql)


def test_registra_as_relacoes_usadas() -> None:
    consulta = validar(
        "WITH t AS (SELECT * FROM pedidos) SELECT * FROM t JOIN clientes USING (cliente_id)"
    )
    assert consulta.relacoes == {"pedidos", "clientes"}


def test_cte_nao_empresta_nome_de_relacao_proibida() -> None:
    with pytest.raises(ConsultaRecusada):
        validar("WITH t AS (SELECT 1 AS a) SELECT * FROM t, segredos")

"""Carga dos CSVs do dataset num arquivo DuckDB e abertura somente leitura.

O banco tem dois esquemas:

* ``bruto``: as tabelas como vêm nos arquivos, com os nomes originais.
* ``main``: visões limpas, com nomes em português. É só isso que o agente enxerga.
"""

from __future__ import annotations

from pathlib import Path

import duckdb

# arquivo -> (tabela bruta, colunas esperadas)
ARQUIVOS: dict[str, tuple[str, tuple[str, ...]]] = {
    "olist_orders_dataset.csv": (
        "pedidos",
        ("order_id", "customer_id", "order_status", "order_purchase_timestamp",
         "order_approved_at", "order_delivered_carrier_date",
         "order_delivered_customer_date", "order_estimated_delivery_date"),
    ),
    "olist_order_items_dataset.csv": (
        "itens",
        ("order_id", "order_item_id", "product_id", "seller_id", "shipping_limit_date",
         "price", "freight_value"),
    ),
    "olist_order_payments_dataset.csv": (
        "pagamentos",
        ("order_id", "payment_sequential", "payment_type", "payment_installments",
         "payment_value"),
    ),
    "olist_order_reviews_dataset.csv": (
        "avaliacoes",
        ("review_id", "order_id", "review_score", "review_comment_title",
         "review_comment_message", "review_creation_date", "review_answer_timestamp"),
    ),
    "olist_customers_dataset.csv": (
        "clientes",
        ("customer_id", "customer_unique_id", "customer_zip_code_prefix", "customer_city",
         "customer_state"),
    ),
    "olist_sellers_dataset.csv": (
        "vendedores",
        ("seller_id", "seller_zip_code_prefix", "seller_city", "seller_state"),
    ),
    "olist_products_dataset.csv": (
        "produtos",
        ("product_id", "product_category_name", "product_name_lenght",
         "product_description_lenght", "product_photos_qty", "product_weight_g",
         "product_length_cm", "product_height_cm", "product_width_cm"),
    ),
}

VISOES_SQL = Path(__file__).with_name("visoes.sql")

# As únicas relações que uma consulta do agente pode citar.
VISOES_PERMITIDAS: frozenset[str] = frozenset(
    {"pedidos", "itens_pedido", "pagamentos", "avaliacoes", "clientes", "vendedores", "produtos"}
)


class ErroDeCarga(RuntimeError):
    """Os arquivos não têm o formato esperado."""


def carregar(pasta_csv: Path, destino: Path) -> dict[str, int]:
    """Cria o banco em ``destino`` a partir dos CSVs. Devolve linhas por tabela bruta."""
    faltando = [nome for nome in ARQUIVOS if not (pasta_csv / nome).is_file()]
    if faltando:
        raise ErroDeCarga(f"arquivos ausentes em {pasta_csv}: {', '.join(faltando)}")
    if destino.exists():
        destino.unlink()
    destino.parent.mkdir(parents=True, exist_ok=True)

    contagens: dict[str, int] = {}
    con = duckdb.connect(str(destino))
    try:
        con.execute("CREATE SCHEMA bruto")
        for arquivo, (tabela, esperadas) in ARQUIVOS.items():
            con.execute(
                f"CREATE TABLE bruto.{tabela} AS "
                "SELECT * FROM read_csv(?, header = true, all_varchar = true)",
                [str(pasta_csv / arquivo)],
            )
            colunas = tuple(
                linha[0] for linha in con.execute(f"DESCRIBE bruto.{tabela}").fetchall()
            )
            if colunas != esperadas:
                raise ErroDeCarga(
                    f"{arquivo}: colunas {colunas} diferentes das esperadas {esperadas}"
                )
            contagem = con.execute(f"SELECT count(*) FROM bruto.{tabela}").fetchone()
            assert contagem is not None
            contagens[tabela] = int(contagem[0])
        con.execute(VISOES_SQL.read_text(encoding="utf-8"))
    finally:
        con.close()
    return contagens


def abrir_somente_leitura(banco: Path) -> duckdb.DuckDBPyConnection:
    """Abre o banco sem escrita, sem acesso externo e com a configuração travada.

    É a segunda barreira. A primeira é a política de SQL, que recusa a consulta antes
    de ela chegar aqui.
    """
    con = duckdb.connect(str(banco), read_only=True)
    try:
        con.execute("SET memory_limit = '2GB'")
        con.execute("SET enable_external_access = false")
        con.execute("SET lock_configuration = true")
    except duckdb.InvalidInputException:
        # Outra conexão deste processo já travou a configuração do mesmo banco. Só
        # aceitamos seguir se a trava estiver de fato no estado seguro.
        linha = con.execute("SELECT current_setting('enable_external_access')").fetchone()
        if linha is None or linha[0] not in (False, "false"):
            con.close()
            raise
    return con

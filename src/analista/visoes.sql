-- Visões que o agente enxerga. Nomes em português, tipos corretos.
-- Toda coluna aqui está descrita em docs/dicionario-de-dados.md.

CREATE VIEW pedidos AS
SELECT
    order_id                                           AS pedido_id,
    customer_id                                        AS cliente_id,
    order_status                                       AS situacao,
    CAST(order_purchase_timestamp AS TIMESTAMP)        AS comprado_em,
    TRY_CAST(order_approved_at AS TIMESTAMP)           AS aprovado_em,
    TRY_CAST(order_delivered_carrier_date AS TIMESTAMP)  AS postado_em,
    TRY_CAST(order_delivered_customer_date AS TIMESTAMP) AS entregue_em,
    TRY_CAST(order_estimated_delivery_date AS TIMESTAMP) AS entrega_prevista_em
FROM bruto.pedidos;

CREATE VIEW itens_pedido AS
SELECT
    order_id                              AS pedido_id,
    CAST(order_item_id AS INTEGER)        AS numero_item,
    product_id                            AS produto_id,
    seller_id                             AS vendedor_id,
    CAST(price AS DECIMAL(12, 2))         AS preco,
    CAST(freight_value AS DECIMAL(12, 2)) AS frete
FROM bruto.itens;

CREATE VIEW pagamentos AS
SELECT
    order_id                               AS pedido_id,
    CAST(payment_sequential AS INTEGER)    AS sequencia,
    payment_type                           AS forma,
    CAST(payment_installments AS INTEGER)  AS parcelas,
    CAST(payment_value AS DECIMAL(12, 2))  AS valor
FROM bruto.pagamentos;

CREATE VIEW avaliacoes AS
SELECT
    review_id                                    AS avaliacao_id,
    order_id                                     AS pedido_id,
    CAST(review_score AS INTEGER)                AS nota,
    review_comment_title                         AS titulo,
    review_comment_message                       AS comentario,
    TRY_CAST(review_creation_date AS TIMESTAMP)  AS criada_em
FROM bruto.avaliacoes;

CREATE VIEW clientes AS
SELECT
    customer_id          AS cliente_id,
    customer_unique_id   AS pessoa_id,
    customer_city        AS cidade,
    customer_state       AS uf
FROM bruto.clientes;

CREATE VIEW vendedores AS
SELECT
    seller_id      AS vendedor_id,
    seller_city    AS cidade,
    seller_state   AS uf
FROM bruto.vendedores;

CREATE VIEW produtos AS
SELECT
    product_id                             AS produto_id,
    product_category_name                  AS categoria,
    TRY_CAST(product_weight_g AS INTEGER)  AS peso_g,
    TRY_CAST(product_photos_qty AS INTEGER) AS fotos
FROM bruto.produtos;

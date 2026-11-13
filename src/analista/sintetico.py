"""Dados sintéticos pequenos, no mesmo formato dos arquivos do dataset.

Servem só para testar carga, política, ferramentas e gabaritos sem depender do
download. Não têm nenhuma linha do dataset real e não servem para medir o agente.
"""

from __future__ import annotations

import csv
import datetime as dt
import random
from pathlib import Path

from .banco import ARQUIVOS

_UFS = ["SP", "RJ", "MG", "PE", "RS", "BA", "PR"]
_CIDADES = {"SP": "sao paulo", "RJ": "rio de janeiro", "MG": "belo horizonte", "PE": "recife",
            "RS": "porto alegre", "BA": "salvador", "PR": "curitiba"}
_CATEGORIAS = ["beleza_saude", "informatica_acessorios", "moveis_decoracao", "esporte_lazer",
               "brinquedos", "livros_tecnicos", "pet_shop", "utilidades_domesticas"]
_FORMAS = ["credit_card", "boleto", "voucher", "debit_card"]
_COMENTARIOS = ["chegou antes do prazo", "produto veio com defeito", "recomendo", "", "",
                "demorou muito para entregar", "igual ao anunciado"]


def _ts(momento: dt.datetime | None) -> str:
    return momento.strftime("%Y-%m-%d %H:%M:%S") if momento else ""


def gerar(pasta: Path, pedidos: int = 300, semente: int = 7) -> None:
    """Escreve os sete CSVs em ``pasta``. Determinístico para a mesma semente."""
    rng = random.Random(semente)
    pasta.mkdir(parents=True, exist_ok=True)
    tabelas: dict[str, list[list[object]]] = {nome: [] for nome in ARQUIVOS}

    vendedores = [f"vend{i:03d}" for i in range(20)]
    for vendedor in vendedores:
        uf = rng.choice(_UFS)
        tabelas["olist_sellers_dataset.csv"].append([vendedor, "01000", _CIDADES[uf], uf])

    produtos = [f"prod{i:03d}" for i in range(60)]
    for indice, produto in enumerate(produtos):
        categoria = "" if indice % 15 == 0 else rng.choice(_CATEGORIAS)
        tabelas["olist_products_dataset.csv"].append(
            [produto, categoria, 40, 300, rng.randint(1, 5), rng.randint(100, 9000), 20, 10, 15]
        )

    pessoas = [f"pessoa{i:03d}" for i in range(int(pedidos * 0.8))]
    inicio = dt.datetime(2017, 1, 5, 9, 0)
    for numero in range(pedidos):
        pedido, cliente = f"ped{numero:04d}", f"cli{numero:04d}"
        uf = rng.choice(_UFS)
        tabelas["olist_customers_dataset.csv"].append(
            [cliente, rng.choice(pessoas), "50000", _CIDADES[uf], uf]
        )
        comprado = inicio + dt.timedelta(days=rng.randint(0, 600), minutes=rng.randint(0, 600))
        previsto = comprado + dt.timedelta(days=rng.randint(10, 25))
        sorteio = rng.random()
        situacao = "delivered" if sorteio < 0.85 else "canceled" if sorteio < 0.92 else "shipped"
        aprovado = comprado + dt.timedelta(hours=rng.randint(1, 30))
        postado = (
            None if situacao == "canceled"
            else aprovado + dt.timedelta(days=rng.randint(1, 4))
        )
        entregue = (
            postado + dt.timedelta(days=rng.randint(2, 28))
            if situacao == "delivered" and postado
            else None
        )
        tabelas["olist_orders_dataset.csv"].append(
            [pedido, cliente, situacao, _ts(comprado), _ts(aprovado), _ts(postado),
             _ts(entregue), _ts(previsto)]
        )

        total = 0.0
        for item in range(1, rng.randint(1, 3) + 1):
            preco = round(rng.uniform(15, 900), 2)
            frete = round(rng.uniform(8, 60), 2)
            total += preco + frete
            tabelas["olist_order_items_dataset.csv"].append(
                [pedido, item, rng.choice(produtos), rng.choice(vendedores),
                 _ts(aprovado + dt.timedelta(days=5)), f"{preco:.2f}", f"{frete:.2f}"]
            )

        partes = [round(total, 2)]
        if rng.random() < 0.15:
            primeira = round(total * 0.4, 2)
            partes = [primeira, round(total - primeira, 2)]
        for sequencia, valor in enumerate(partes, start=1):
            forma = rng.choice(_FORMAS)
            parcelas = rng.randint(1, 10) if forma == "credit_card" else 1
            tabelas["olist_order_payments_dataset.csv"].append(
                [pedido, sequencia, forma, parcelas, f"{valor:.2f}"]
            )

        if situacao == "delivered" and rng.random() < 0.9 and entregue:
            atrasado = entregue > previsto
            nota = rng.choice([1, 2, 3]) if atrasado else rng.choice([3, 4, 5, 5])
            criada = entregue + dt.timedelta(days=1)
            tabelas["olist_order_reviews_dataset.csv"].append(
                [f"aval{numero:04d}", pedido, nota, "", rng.choice(_COMENTARIOS), _ts(criada),
                 _ts(criada + dt.timedelta(days=2))]
            )

    for arquivo, (_, colunas) in ARQUIVOS.items():
        with (pasta / arquivo).open("w", newline="", encoding="utf-8") as saida:
            escritor = csv.writer(saida, lineterminator="\n")
            escritor.writerow(colunas)
            escritor.writerows(tabelas[arquivo])

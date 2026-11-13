from collections.abc import Iterator
from pathlib import Path

import pytest

from analista import sintetico
from analista.banco import carregar
from analista.ferramentas import Ferramentas


@pytest.fixture(scope="session")
def banco(tmp_path_factory: pytest.TempPathFactory) -> Path:
    raiz = tmp_path_factory.mktemp("dados")
    sintetico.gerar(raiz / "csv")
    destino = raiz / "teste.duckdb"
    carregar(raiz / "csv", destino)
    return destino


@pytest.fixture()
def ferramentas(banco: Path) -> Iterator[Ferramentas]:
    instancia = Ferramentas(banco, max_linhas=50)
    yield instancia
    instancia.fechar()

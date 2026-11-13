"""Acerto de execução: o resultado do agente é igual ao do gabarito?

Dois resultados são iguais quando têm as mesmas linhas, depois de:

* ignorar os nomes das colunas (o agente pode chamar a coluna como quiser);
* ignorar a ordem das linhas, a não ser que a pergunta peça ordem (``ordem_importa``);
* ignorar a ordem das colunas, desde que colunas do mesmo tipo (número com número,
  texto com texto) mantenham a ordem entre si. Trocar duas colunas numéricas de
  lugar muda a resposta, então nunca é tolerado.

Números:

* por padrão, comparação com tolerância relativa de 1e-6;
* se o agente arredondou (devolveu de 2 a 6 casas decimais), o valor é comparado
  com o gabarito arredondado às mesmas casas. Menos de 2 casas não ganha essa
  tolerância: "8" não é aceito no lugar de 8,11.

Limite conhecido: uma consulta errada cujo resultado só difere do certo depois da
casa em que o agente arredondou passa como acerto. Os gabaritos são escritos para
não depender disso.

Não existe acerto parcial. Resultado truncado nunca é acerto.
"""

from __future__ import annotations

import math
from itertools import permutations

from .ferramentas import Resultado, Valor

_MAX_COLUNAS_PERMUTAR = 6
_TOLERANCIA = 1e-6


def _numero(valor: Valor) -> bool:
    return isinstance(valor, int | float) and not isinstance(valor, bool)


def _casas(valor: float) -> int:
    texto = repr(valor)
    if "e" in texto or "." not in texto:
        return 99
    return len(texto.split(".")[1].rstrip("0"))


def _celulas_iguais(obtido: Valor, esperado: Valor) -> bool:
    if _numero(obtido) and _numero(esperado):
        a, b = float(obtido), float(esperado)  # type: ignore[arg-type]
        if math.isnan(a) or math.isnan(b):
            return math.isnan(a) and math.isnan(b)
        if math.isinf(a) or math.isinf(b):
            return a == b
        if math.isclose(a, b, rel_tol=_TOLERANCIA, abs_tol=1e-9):
            return True
        casas = _casas(a) if isinstance(obtido, float) else 99
        return 2 <= casas <= 6 and math.isclose(round(b, casas), a, abs_tol=1e-9)
    if isinstance(obtido, str) and isinstance(esperado, str):
        return obtido.strip() == esperado.strip()
    return type(obtido) is type(esperado) and obtido == esperado


def _linhas_iguais(obtida: tuple[Valor, ...], esperada: tuple[Valor, ...]) -> bool:
    return all(_celulas_iguais(o, e) for o, e in zip(obtida, esperada, strict=True))


def _conjuntos_iguais(
    obtidas: list[tuple[Valor, ...]], esperadas: list[tuple[Valor, ...]], ordem_importa: bool
) -> bool:
    if ordem_importa:
        return all(_linhas_iguais(o, e) for o, e in zip(obtidas, esperadas, strict=True))
    livres = list(obtidas)
    for esperada in esperadas:
        for indice, obtida in enumerate(livres):
            if _linhas_iguais(obtida, esperada):
                del livres[indice]
                break
        else:
            return False
    return True


def _tipo_da_coluna(linhas: list[tuple[Valor, ...]], coluna: int) -> str:
    for linha in linhas:
        valor = linha[coluna]
        if valor is not None:
            return "numero" if _numero(valor) else type(valor).__name__
    return "nulo"


def _ordens_permitidas(esperadas: list[tuple[Valor, ...]], largura: int) -> list[tuple[int, ...]]:
    """Permutações que não trocam de lugar duas colunas do mesmo tipo."""
    tipos = [_tipo_da_coluna(esperadas, c) for c in range(largura)]
    ordens = []
    for ordem in permutations(range(largura)):
        # ordem[i] = coluna obtida que ocupa a posição i do gabarito
        por_tipo: dict[str, list[int]] = {}
        for posicao, origem in enumerate(ordem):
            por_tipo.setdefault(tipos[posicao], []).append(origem)
        if all(origens == sorted(origens) for origens in por_tipo.values()):
            ordens.append(ordem)
    return ordens


def resultados_iguais(obtido: Resultado, gabarito: Resultado, ordem_importa: bool = False) -> bool:
    if obtido.truncado or gabarito.truncado:
        return False
    esperadas = [tuple(linha) for linha in gabarito.linhas]
    recebidas = [tuple(linha) for linha in obtido.linhas]
    largura = len(gabarito.colunas)
    if len(esperadas) != len(recebidas) or len(obtido.colunas) != largura:
        return False
    if _conjuntos_iguais(recebidas, esperadas, ordem_importa):
        return True
    if largura < 2 or largura > _MAX_COLUNAS_PERMUTAR:
        return False
    for ordem in _ordens_permitidas(esperadas, largura):
        if ordem == tuple(range(largura)):
            continue
        reordenadas = [tuple(linha[i] for i in ordem) for linha in recebidas]
        if _conjuntos_iguais(reordenadas, esperadas, ordem_importa):
            return True
    return False

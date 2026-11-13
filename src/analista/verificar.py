"""Todo número da resposta precisa estar no resultado da consulta.

Verificação determinística, depois da geração. Um número do texto é aceito quando:

* é igual a algum valor numérico do resultado, arredondado às casas com que foi
  escrito (o texto pode dizer "4,09" para um resultado 4.0864);
* ou é a contagem de linhas do resultado;
* ou já estava na pergunta (anos, "os 3 maiores", limites).

O que sobra são números que o modelo tirou de outro lugar.
"""

from __future__ import annotations

import re
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation

from .ferramentas import Resultado

# 1.234,56 | 1234,56 | 1,234.56 | 1234.56 | 12 | 8,1%
_NUMERO = re.compile(r"(?<![\w.,])-?\d[\d.,]*\d|(?<![\w.,])-?\d")
_DATA_ISO = re.compile(r"\d{4}-\d{2}-\d{2}(?:[T ]\d{2}:\d{2}(?::\d{2})?)?")


def _interpretar(bruto: str) -> tuple[Decimal, int] | None:
    """Devolve (valor, casas decimais escritas) ou None se não for número."""
    texto = bruto.rstrip(".,")
    negativo = texto.startswith("-")
    texto = texto.lstrip("-")
    if "," in texto and "." in texto:
        decimal = "," if texto.rfind(",") > texto.rfind(".") else "."
        milhar = "." if decimal == "," else ","
        texto = texto.replace(milhar, "").replace(decimal, ".")
    elif "," in texto:
        partes = texto.split(",")
        if len(partes) == 2 and len(partes[1]) != 3:
            texto = texto.replace(",", ".")
        elif len(partes) == 2:  # "1,234": ambíguo; tratado como milhar e como decimal
            return _ambiguo(partes[0], partes[1], negativo)
        else:
            texto = texto.replace(",", "")
    elif "." in texto:
        partes = texto.split(".")
        if len(partes) > 2 or (len(partes) == 2 and len(partes[1]) == 3):
            if len(partes) == 2:
                return _ambiguo(partes[0], partes[1], negativo)
            texto = texto.replace(".", "")
    try:
        valor = Decimal(texto)
    except InvalidOperation:
        return None
    casas = len(texto.split(".")[1]) if "." in texto else 0
    return (-valor if negativo else valor, casas)


def _ambiguo(inteiro: str, resto: str, negativo: bool) -> tuple[Decimal, int]:
    # "1.234" pode ser mil duzentos e trinta e quatro ou 1,234. Guardamos como inteiro
    # com casas = -3, e a comparação testa as duas leituras.
    valor = Decimal(inteiro + resto)
    return (-valor if negativo else valor, -3)


def numeros_do_texto(texto: str) -> list[tuple[str, Decimal, int]]:
    sem_datas = _DATA_ISO.sub(" ", texto)
    achados = []
    for bruto in _NUMERO.findall(sem_datas):
        lido = _interpretar(bruto)
        if lido is not None:
            achados.append((bruto.rstrip(".,"), lido[0], lido[1]))
    return achados


def _arredondar(valor: Decimal, casas: int) -> Decimal | None:
    """Arredonda; None quando o valor não é finito ou não cabe na precisão."""
    if not valor.is_finite():
        return None
    try:
        return valor.quantize(Decimal(1).scaleb(-casas), rounding=ROUND_HALF_UP)
    except InvalidOperation:
        return None


def _valores(resultado: Resultado) -> list[Decimal]:
    valores = [Decimal(len(resultado.linhas))]
    for linha in resultado.linhas:
        for valor in linha:
            if isinstance(valor, bool) or valor is None:
                continue
            if isinstance(valor, int | float):
                try:
                    valores.append(Decimal(str(valor)))
                except InvalidOperation:
                    continue
            else:
                valores.extend(v for _, v, _ in numeros_do_texto(str(valor)))
    return valores


def numeros_sem_origem(texto: str, resultado: Resultado | None, pergunta: str = "") -> list[str]:
    """Números do texto que não vêm do resultado nem da pergunta."""
    da_pergunta = {valor for _, valor, _ in numeros_do_texto(pergunta)}
    do_resultado = _valores(resultado) if resultado is not None else []
    faltando: list[str] = []
    for bruto, valor, casas in numeros_do_texto(texto):
        if valor in da_pergunta:
            continue
        leituras = [(valor, 0), (valor / 1000, 3)] if casas == -3 else [(valor, casas)]
        if any(
            _arredondar(abs(origem), c) == abs(v) for v, c in leituras for origem in do_resultado
        ):
            continue
        faltando.append(bruto)
    return faltando

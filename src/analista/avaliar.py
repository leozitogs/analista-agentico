"""Avaliação: roda as perguntas e compara com o gabarito.

Acerto por tipo de pergunta:

* ``sql``           - o agente respondeu (tipo "resposta") e o resultado da consulta
                      final é igual ao do gabarito. Sem crédito parcial.
* ``sem_resposta``  - o agente disse que os dados não permitem responder.
* ``ambigua``       - o agente pediu esclarecimento.

Cada execução vira uma linha de JSONL com o rastro inteiro, para auditoria.
"""

from __future__ import annotations

import json
from collections.abc import Iterable
from pathlib import Path

from pydantic import BaseModel

from .agente import MAX_LINHAS_FINAL, Agente, Execucao
from .comparar import resultados_iguais
from .ferramentas import ErroDeConsulta, Ferramentas
from .perguntas import Pergunta
from .politica import ConsultaRecusada
from .provedor import ErroDeCota

# O rastro é publicado. Ele guarda só as primeiras linhas de cada resultado, para que
# um arquivo de resultados nunca vire uma cópia de linhas do dataset.
MAX_LINHAS_NO_RASTRO = 50

_ESPERADO = {"sql": "resposta", "sem_resposta": "sem_resposta", "ambigua": "esclarecimento"}


class Linha(BaseModel):
    id: str
    nivel: int
    tipo_pergunta: str
    acertou: bool
    motivo: str
    execucao: Execucao


class Resumo(BaseModel):
    provedor: str
    modo: str
    contexto: str = "completo"
    total: int
    acertos: int
    por_grupo: dict[str, tuple[int, int]]  # grupo -> (acertos, total)
    numeros_sem_origem: int
    falhas: int
    chamadas_ao_modelo: int
    chamadas_lidas_do_texto: int = 0
    tokens_entrada: int
    tokens_saida: int
    duracao_media_ms: int
    interrompida: str = ""  # motivo, quando a avaliação parou antes do fim
    nao_avaliadas: int = 0


def julgar(pergunta: Pergunta, execucao: Execucao, ferramentas: Ferramentas) -> tuple[bool, str]:
    if execucao.tipo == "falha":
        return False, f"falha: {execucao.erro or 'sem resposta final'}"
    esperado = _ESPERADO[pergunta.tipo]
    if execucao.tipo != esperado:
        return False, f"esperava {esperado}, veio {execucao.tipo}"
    if pergunta.tipo != "sql":
        return True, "tipo correto"
    assert pergunta.sql is not None and execucao.resultado is not None
    gabarito = ferramentas.executar_sql(pergunta.sql, MAX_LINHAS_FINAL)
    if resultados_iguais(execucao.resultado, gabarito, pergunta.ordem_importa):
        return True, "resultado igual ao gabarito"
    return False, (
        f"resultado diferente do gabarito ({len(execucao.resultado.linhas)} x "
        f"{len(gabarito.linhas)} linhas)"
    )


def para_rastro(linha: Linha) -> dict[str, object]:
    """A linha como vai para o arquivo: resultado limitado a uma amostra."""
    dados = linha.model_dump()
    resultado = dados["execucao"]["resultado"]
    if resultado is not None and len(resultado["linhas"]) > MAX_LINHAS_NO_RASTRO:
        resultado["linhas_omitidas_do_rastro"] = len(resultado["linhas"]) - MAX_LINHAS_NO_RASTRO
        resultado["linhas"] = resultado["linhas"][:MAX_LINHAS_NO_RASTRO]
    return dados


def conferir_gabaritos(perguntas: list[Pergunta], juiz: Ferramentas) -> None:
    """Executa todos os gabaritos antes de gastar uma chamada ao modelo."""
    for pergunta in perguntas:
        if pergunta.sql is None:
            continue
        try:
            resultado = juiz.executar_sql(pergunta.sql, MAX_LINHAS_FINAL)
        except (ConsultaRecusada, ErroDeConsulta) as erro:
            raise ValueError(f"gabarito {pergunta.id} inválido: {erro}") from erro
        if resultado.truncado:
            raise ValueError(f"gabarito {pergunta.id} passa de {MAX_LINHAS_FINAL} linhas")


def avaliar(
    agente: Agente,
    perguntas: Iterable[Pergunta],
    juiz: Ferramentas,
    saida: Path | None = None,
) -> tuple[Resumo, list[Linha]]:
    """``juiz`` executa os gabaritos, numa conexão separada da do agente.

    O rastro de cada pergunta é gravado assim que ela termina: uma falha no meio
    não apaga o que já foi medido.
    """
    perguntas = list(perguntas)
    conferir_gabaritos(perguntas, juiz)
    linhas: list[Linha] = []
    interrompida = ""
    arquivo = None
    if saida is not None:
        saida.parent.mkdir(parents=True, exist_ok=True)
        arquivo = saida.open("w", encoding="utf-8", newline="\n")
    try:
        for pergunta in perguntas:
            try:
                execucao = agente.perguntar(pergunta.pergunta)
            except ErroDeCota as erro:
                interrompida = f"cota do provedor esgotada: {erro}"
                break
            except Exception as erro:  # noqa: BLE001 - defeito nosso vira falha registrada
                execucao = Execucao(
                    pergunta=pergunta.pergunta, modo=agente.modo, contexto=agente.contexto,
                    provedor=agente.provedor.nome,
                    erro=f"erro interno: {type(erro).__name__}: {erro}",
                )
            acertou, motivo = julgar(pergunta, execucao, juiz)
            linha = Linha(id=pergunta.id, nivel=pergunta.nivel, tipo_pergunta=pergunta.tipo,
                          acertou=acertou, motivo=motivo, execucao=execucao)
            linhas.append(linha)
            if arquivo is not None:
                arquivo.write(json.dumps(para_rastro(linha), ensure_ascii=False) + "\n")
                arquivo.flush()
    finally:
        if arquivo is not None:
            arquivo.close()
    resumo = resumir(agente, linhas)
    resumo.interrompida = interrompida
    resumo.nao_avaliadas = len(perguntas) - len(linhas)
    return resumo, linhas


def resumir(agente: Agente, linhas: list[Linha]) -> Resumo:
    grupos: dict[str, list[bool]] = {}
    for linha in linhas:
        grupo = f"nivel {linha.nivel}" if linha.tipo_pergunta == "sql" else linha.tipo_pergunta
        grupos.setdefault(grupo, []).append(linha.acertou)
    execucoes = [linha.execucao for linha in linhas]
    return Resumo(
        provedor=agente.provedor.nome,
        modo=agente.modo,
        contexto=agente.contexto,
        total=len(linhas),
        acertos=sum(linha.acertou for linha in linhas),
        por_grupo={g: (sum(v), len(v)) for g, v in sorted(grupos.items())},
        numeros_sem_origem=sum(bool(e.numeros_sem_origem) for e in execucoes),
        falhas=sum(e.tipo == "falha" for e in execucoes),
        chamadas_ao_modelo=sum(e.chamadas_ao_modelo for e in execucoes),
        chamadas_lidas_do_texto=sum(e.chamadas_lidas_do_texto for e in execucoes),
        tokens_entrada=sum(e.tokens_entrada for e in execucoes),
        tokens_saida=sum(e.tokens_saida for e in execucoes),
        duracao_media_ms=int(sum(e.duracao_ms for e in execucoes) / len(execucoes))
        if execucoes else 0,
    )

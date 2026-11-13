"""Provedores de modelo.

O agente fala com um ``Provedor``; ele não sabe qual modelo está do outro lado.

* ``ProvedorGemini`` chama a API REST do Gemini com a biblioteca padrão. Sem SDK: o
  pedido e a resposta são JSON à vista, o que deixa o rastro honesto.
* ``ProvedorRoteirizado`` devolve respostas escritas à mão. É o que os testes usam.

A conversa é guardada no formato da API (``contents``). O turno do modelo volta para a
API exatamente como veio, porque modelos recentes anexam assinaturas às chamadas de
função e recusam o turno seguinte se elas sumirem.
"""

from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request
from collections.abc import Callable, Sequence
from typing import Any, Protocol

from pydantic import BaseModel

Json = dict[str, Any]
Transporte = Callable[[str, Json, dict[str, str], float], Json]

API = "https://generativelanguage.googleapis.com/v1beta"
VARIAVEL_CHAVE = "GEMINI_API_KEY"
VARIAVEL_MODELO = "ANALISTA_MODELO"
VARIAVEL_RACIOCINIO = "ANALISTA_RACIOCINIO"


class Chamada(BaseModel):
    nome: str
    argumentos: Json


class RespostaModelo(BaseModel):
    conteudo: Json  # turno do modelo, cru, para devolver à API
    chamadas: list[Chamada]
    texto: str
    tokens_entrada: int = 0
    tokens_saida: int = 0


class ErroDeProvedor(RuntimeError):
    """A API recusou o pedido, não respondeu ou respondeu algo que não dá para usar."""


class ErroDeCota(ErroDeProvedor):
    """A cota diária acabou. Repetir não adianta; quem chama deve parar."""


class ErroPassageiro(ErroDeProvedor):
    """Sobrecarga, limite de taxa ou tempo esgotado: vale tentar de novo."""


class Provedor(Protocol):
    nome: str

    def gerar(
        self, sistema: str, conteudos: Sequence[Json], ferramentas: Sequence[Json]
    ) -> RespostaModelo: ...


def turno_usuario(texto: str) -> Json:
    return {"role": "user", "parts": [{"text": texto}]}


def turno_resultados(resultados: Sequence[tuple[str, Json]]) -> Json:
    """Um turno com a resposta de cada ferramenta chamada, na ordem das chamadas."""
    return {
        "role": "user",
        "parts": [
            {"functionResponse": {"name": nome, "response": resposta}}
            for nome, resposta in resultados
        ],
    }


def interpretar(resposta: Json) -> RespostaModelo:
    """Converte a resposta crua da API. Levanta se não houver turno utilizável."""
    candidatos = resposta.get("candidates") or []
    if not candidatos:
        motivo = (resposta.get("promptFeedback") or {}).get("blockReason", "sem candidatos")
        raise ErroDeProvedor(f"o modelo não respondeu: {motivo}")
    conteudo: Json = candidatos[0].get("content") or {}
    partes = conteudo.get("parts") or []
    if not partes:
        motivo = candidatos[0].get("finishReason", "resposta vazia")
        raise ErroDeProvedor(f"o modelo não respondeu: {motivo}")
    chamadas: list[Chamada] = []
    for parte in partes:
        if "functionCall" not in parte:
            continue
        bruta = parte["functionCall"]
        argumentos = bruta.get("args") or {}
        if not isinstance(bruta.get("name"), str) or not isinstance(argumentos, dict):
            raise ErroDeProvedor("o modelo devolveu uma chamada de função malformada")
        chamadas.append(Chamada(nome=bruta["name"], argumentos=dict(argumentos)))
    texto = "".join(
        parte["text"] for parte in partes if "text" in parte and not parte.get("thought")
    )
    uso = resposta.get("usageMetadata") or {}
    return RespostaModelo(
        conteudo={"role": "model", "parts": partes},
        chamadas=chamadas,
        texto=texto.strip(),
        tokens_entrada=int(uso.get("promptTokenCount") or 0),
        tokens_saida=int(uso.get("candidatesTokenCount") or 0)
        + int(uso.get("thoughtsTokenCount") or 0),
    )


def _http(url: str, corpo: Json, cabecalhos: dict[str, str], tempo_limite: float) -> Json:
    pedido = urllib.request.Request(
        url, data=json.dumps(corpo).encode("utf-8"), headers=cabecalhos, method="POST"
    )
    try:
        with urllib.request.urlopen(pedido, timeout=tempo_limite) as resposta:
            dados: Json = json.loads(resposta.read().decode("utf-8"))
            return dados
    except urllib.error.HTTPError as erro:
        detalhe = " ".join(erro.read().decode("utf-8", "replace").split())[:600]
        tipo: type[ErroDeProvedor] = ErroDeProvedor
        if erro.code == 429 and "per day" in detalhe:
            tipo = ErroDeCota
        elif erro.code in (429, 500, 502, 503, 504):
            tipo = ErroPassageiro
        raise tipo(f"HTTP {erro.code}: {detalhe}") from erro
    except (urllib.error.URLError, TimeoutError, OSError, ValueError) as erro:
        # inclui leitura interrompida e corpo que não é JSON
        raise ErroPassageiro(f"falha de rede: {erro}") from erro


class ProvedorGemini:
    """Gemini pela API REST. A chave vem do ambiente e nunca é registrada."""

    def __init__(
        self,
        modelo: str | None = None,
        *,
        temperatura: float = 0.0,
        raciocinio: str | None = None,
        tempo_limite: float = 90.0,
        tentativas: int = 4,
        espera_s: float = 8.0,
        transporte: Transporte = _http,
    ) -> None:
        modelo = modelo or os.environ.get(VARIAVEL_MODELO)
        if not modelo:
            raise ErroDeProvedor(
                f"defina o modelo em {VARIAVEL_MODELO} (veja `analista modelos`)"
            )
        self.modelo = modelo
        self.nome = f"gemini:{modelo}"
        self.temperatura = temperatura
        # Nível de raciocínio do modelo ("low", "high"...). Vazio = padrão do modelo.
        self.raciocinio = raciocinio if raciocinio is not None else os.environ.get(
            VARIAVEL_RACIOCINIO, "low"
        )
        self.tempo_limite = tempo_limite
        self.tentativas = tentativas
        self.espera_s = espera_s
        self.repeticoes = 0  # quantas vezes um pedido precisou ser refeito
        self._transporte = transporte

    def gerar(
        self, sistema: str, conteudos: Sequence[Json], ferramentas: Sequence[Json]
    ) -> RespostaModelo:
        chave = os.environ.get(VARIAVEL_CHAVE)
        if not chave:
            raise ErroDeProvedor(f"defina a chave em {VARIAVEL_CHAVE}")
        corpo: Json = {
            "systemInstruction": {"parts": [{"text": sistema}]},
            "contents": list(conteudos),
            "generationConfig": {"temperature": self.temperatura},
        }
        if self.raciocinio:
            corpo["generationConfig"]["thinkingConfig"] = {"thinkingLevel": self.raciocinio}
        if ferramentas:
            corpo["tools"] = [{"functionDeclarations": list(ferramentas)}]
        cabecalhos = {"Content-Type": "application/json", "x-goog-api-key": chave}
        url = f"{API}/models/{self.modelo}:generateContent"
        for tentativa in range(1, self.tentativas + 1):
            try:
                return interpretar(self._transporte(url, corpo, cabecalhos, self.tempo_limite))
            except ErroPassageiro:
                if tentativa == self.tentativas:
                    raise
                self.repeticoes += 1
                time.sleep(self.espera_s * tentativa)
        raise AssertionError("inalcançável")


def listar_modelos(tempo_limite: float = 30.0) -> list[str]:
    """Modelos da conta que aceitam ``generateContent``."""
    chave = os.environ.get(VARIAVEL_CHAVE)
    if not chave:
        raise ErroDeProvedor(f"defina a chave em {VARIAVEL_CHAVE}")
    pedido = urllib.request.Request(
        f"{API}/models?pageSize=200", headers={"x-goog-api-key": chave}
    )
    try:
        with urllib.request.urlopen(pedido, timeout=tempo_limite) as resposta:
            dados = json.loads(resposta.read().decode("utf-8"))
    except (urllib.error.URLError, TimeoutError) as erro:
        raise ErroDeProvedor(f"não foi possível listar os modelos: {erro}") from erro
    return sorted(
        modelo["name"].removeprefix("models/")
        for modelo in dados.get("models", [])
        if "generateContent" in modelo.get("supportedGenerationMethods", [])
    )


class ProvedorRoteirizado:
    """Devolve respostas prontas, na ordem. Guarda o que recebeu, para os testes."""

    nome = "roteirizado"

    def __init__(self, roteiro: Sequence[Sequence[Chamada] | str]) -> None:
        self._roteiro = list(roteiro)
        self.recebidos: list[list[Json]] = []

    def gerar(
        self, sistema: str, conteudos: Sequence[Json], ferramentas: Sequence[Json]
    ) -> RespostaModelo:
        self.recebidos.append([dict(c) for c in conteudos])
        if not self._roteiro:
            raise ErroDeProvedor("o roteiro acabou")
        passo = self._roteiro.pop(0)
        if isinstance(passo, str):
            partes: list[Json] = [{"text": passo}]
            chamadas: list[Chamada] = []
        else:
            chamadas = list(passo)
            partes = [{"functionCall": {"name": c.nome, "args": c.argumentos}} for c in chamadas]
        return RespostaModelo(
            conteudo={"role": "model", "parts": partes},
            chamadas=chamadas,
            texto=passo if isinstance(passo, str) else "",
            tokens_entrada=10,
            tokens_saida=5,
        )

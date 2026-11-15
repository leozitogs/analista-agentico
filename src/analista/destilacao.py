"""Destilação: pares de treino escritos por um modelo professor e filtrados sem gente.

O desenho e os critérios estão em ``docs/processo/D0-destilacao-plano.md``. Três filtros:

1. **execução** - a consulta passa na política, executa, devolve linhas e não é truncada;
2. **concordância** - o professor recebe só a pergunta e escreve outra consulta; o par só
   fica se os dois resultados forem iguais pelo comparador do projeto;
3. **vazamento** - pergunta parecida demais com alguma do conjunto de teste é descartada.

As perguntas de teste nunca entram num prompt: elas só são lidas pelo filtro 3.
"""

from __future__ import annotations

import json
import re
import unicodedata
from collections import Counter
from collections.abc import Iterator, Sequence
from difflib import SequenceMatcher
from typing import Literal

from pydantic import BaseModel

from .agente import Execucao
from .comparar import resultados_iguais
from .ferramentas import ErroDeConsulta, Ferramentas, Resultado
from .politica import ConsultaRecusada
from .provedor import ErroDeCota, Provedor, turno_usuario

LIMIAR_DE_VAZAMENTO = 0.85
MAX_LINHAS = 5000

HABILIDADES = [
    "filtro e contagem numa visão só",
    "agregação com agrupamento numa visão só",
    "junção de duas visões com agrupamento",
    "junção de três ou mais visões",
    "antijunção: o que não tem correspondência em outra visão",
    "percentual ou razão entre dois totais",
    "datas: por ano, por mês, intervalos, comparação entre duas datas",
    "os N maiores, com critério de desempate dito na pergunta",
    "função de janela: posição por grupo ou variação em relação ao período anterior",
    "duas etapas: agregar primeiro e depois agregar o agregado",
    "armadilha dos dados descrita no dicionário (pessoa contra cliente, pedidos sem itens, "
    "mais de uma avaliação por pedido, valores de situação em inglês)",
]

# Cada lote recebe um tema, em rodízio, para que lotes da mesma habilidade não se repitam.
TEMAS = [
    "pedidos e suas situações", "prazos e atrasos de entrega", "itens, preços e frete",
    "formas de pagamento e parcelas", "avaliações e notas", "clientes e estados",
    "vendedores e suas cidades", "produtos e categorias", "meses e anos de compra",
    "combinações entre vendedores, produtos e clientes",
]

TipoDePar = Literal["sql", "sem_resposta", "ambigua"]


class Par(BaseModel):
    tipo: TipoDePar
    pergunta: str
    sql: str | None = None
    texto: str | None = None  # motivo da recusa ou pergunta de esclarecimento
    habilidade: str = ""


class Funil(BaseModel):
    """Quantos pares sobraram depois de cada filtro. Vai para o registro de resultados."""

    pedidos_ao_professor: int = 0
    escritos: int = 0
    apos_execucao: int = 0
    apos_concordancia: int = 0
    apos_vazamento: int = 0
    descartes: dict[str, int] = {}
    maior_semelhanca_restante: float = 0.0


# ---------------------------------------------------------------- formato do aluno

SISTEMA_DO_ALUNO = (
    "Você escreve uma consulta SQL (DuckDB, somente SELECT) que responde à pergunta, usando só "
    "as visões abaixo. Responda com a consulta e nada mais. Se os dados não permitem "
    "responder, responda `SEM_RESPOSTA: <o que falta>`. Se a pergunta admite leituras que "
    "mudam o resultado, responda `ESCLARECER: <a pergunta que precisa ser feita>`."
)


def alvo_do_aluno(par: Par) -> str:
    """O texto que o aluno aprende a escrever."""
    if par.tipo == "sql":
        assert par.sql is not None
        return par.sql.strip()
    marca = "SEM_RESPOSTA" if par.tipo == "sem_resposta" else "ESCLARECER"
    return f"{marca}: {(par.texto or '').strip()}"


def ler_saida_do_aluno(texto: str) -> tuple[str, str]:
    """Devolve (tipo, conteúdo), com tipo em resposta, sem_resposta ou esclarecimento."""
    limpo = re.sub(r"^```(?:sql)?\s*|\s*```$", "", (texto or "").strip(), flags=re.I).strip()
    for marca, tipo in (("SEM_RESPOSTA:", "sem_resposta"), ("ESCLARECER:", "esclarecimento")):
        if limpo.upper().startswith(marca):
            return tipo, limpo[len(marca):].strip()
    return "resposta", limpo.rstrip(";").strip()


# ---------------------------------------------------------------- professor

_SISTEMA_DO_PROFESSOR = """Você escreve exemplos de treino para um modelo que transforma \
perguntas de negócio em português em consultas SQL (DuckDB, somente SELECT) sobre o banco \
descrito abaixo.

Regras para cada exemplo:
- a pergunta é de alguém de negócio, em português natural, sem citar nomes de coluna;
- a pergunta diz tudo o que a consulta precisa: período, critério de desempate, formato \
quando importar. Uma pessoa atenta só chegaria a UM resultado;
- a consulta devolve só o que a pergunta pede, sem coluna a mais;
- nada de perguntas repetidas ou que só troquem um número.

Responda SOMENTE com uma lista JSON. Sem texto antes ou depois.

{dicionario}
"""


def _lista_json(texto: str) -> list[object]:
    """A primeira lista JSON do texto; lista vazia se não houver."""
    texto = re.sub(r"```(?:json)?", "", texto or "")
    inicio = texto.find("[")
    if inicio < 0:
        return []
    try:
        valor, _ = json.JSONDecoder().raw_decode(texto, inicio)
    except json.JSONDecodeError:
        return []
    return valor if isinstance(valor, list) else []


def pedir_pares(
    provedor: Provedor, dicionario: str, habilidade: str, quantidade: int,
    exemplos: Sequence[str] = (), tema: str = "",
) -> list[Par]:
    """Um lote de pares (pergunta, SQL) sobre uma habilidade."""
    estilo = ""
    if exemplos:
        estilo = "\nExemplos do estilo das perguntas (não os repita):\n" + "\n".join(
            f"- {e}" for e in exemplos)
    pedido = (
        f"Escreva {quantidade} exemplos diferentes entre si que exercitem: {habilidade}."
        + (f" Dê preferência a perguntas sobre {tema}." if tema else "")
        + f"{estilo}\n"
        'Formato: [{"pergunta": "...", "sql": "..."}, ...]'
    )
    resposta = provedor.gerar(
        _SISTEMA_DO_PROFESSOR.format(dicionario=dicionario), [turno_usuario(pedido)], [])
    pares = []
    for item in _lista_json(resposta.texto):
        if isinstance(item, dict) and isinstance(item.get("pergunta"), str) and isinstance(
            item.get("sql"), str
        ):
            pares.append(Par(tipo="sql", pergunta=item["pergunta"].strip(),
                             sql=item["sql"].strip(), habilidade=habilidade))
    return pares


def pedir_recusas(
    provedor: Provedor, dicionario: str, tipo: Literal["sem_resposta", "ambigua"], quantidade: int
) -> list[Par]:
    """Perguntas que o aluno deve recusar: sem resposta nos dados, ou ambíguas."""
    if tipo == "sem_resposta":
        o_que = ("perguntas de negócio plausíveis que NÃO podem ser respondidas com este banco, "
                 "porque o dado não existe nele. Inclua algumas em que exista um campo parecido "
                 "que tentaria alguém a responder errado. Em `texto`, diga o que falta.")
    else:
        o_que = ("perguntas de negócio que admitem leituras diferentes, cada uma com um resultado "
                 "diferente neste banco. Em `texto`, escreva a pergunta de esclarecimento.")
    pedido = f'Escreva {quantidade} {o_que}\nFormato: [{{"pergunta": "...", "texto": "..."}}, ...]'
    resposta = provedor.gerar(
        _SISTEMA_DO_PROFESSOR.format(dicionario=dicionario), [turno_usuario(pedido)], [])
    return [
        Par(tipo=tipo, pergunta=item["pergunta"].strip(), texto=item["texto"].strip(),
            habilidade=tipo)
        for item in _lista_json(resposta.texto)
        if isinstance(item, dict) and isinstance(item.get("pergunta"), str)
        and isinstance(item.get("texto"), str)
    ]


def responder_as_cegas(provedor: Provedor, dicionario: str, perguntas: Sequence[str]) -> list[str]:
    """O professor responde de novo, vendo só as perguntas. Uma consulta por pergunta."""
    pedido = (
        "Escreva a consulta SQL de cada pergunta, na mesma ordem. Use string vazia quando não "
        "souber.\nFormato: [\"SELECT ...\", \"SELECT ...\"]\n\n"
        + "\n".join(f"{i + 1}. {p}" for i, p in enumerate(perguntas))
    )
    resposta = provedor.gerar(
        _SISTEMA_DO_PROFESSOR.format(dicionario=dicionario), [turno_usuario(pedido)], [])
    consultas = [c if isinstance(c, str) else "" for c in _lista_json(resposta.texto)]
    return (consultas + [""] * len(perguntas))[: len(perguntas)]


# ---------------------------------------------------------------- filtros

def _executar(ferramentas: Ferramentas, sql: str) -> Resultado | None:
    try:
        resultado = ferramentas.executar_sql(sql, MAX_LINHAS)
    except (ConsultaRecusada, ErroDeConsulta):
        return None
    return None if resultado.truncado or not resultado.linhas else resultado


def filtrar_por_execucao(ferramentas: Ferramentas, pares: Sequence[Par]) -> list[Par]:
    """Fica quem não é SQL, e o SQL que executa com resultado completo e não vazio."""
    bons = []
    for par in pares:
        if par.tipo != "sql":
            bons.append(par)
        elif par.sql and (resultado := _executar(ferramentas, par.sql)) is not None:
            bons.append(par.model_copy(update={"sql": resultado.sql}))
    return bons


def filtrar_por_concordancia(
    provedor: Provedor, ferramentas: Ferramentas, dicionario: str, pares: Sequence[Par],
    lote: int = 10,
) -> list[Par]:
    """Fica o par cuja pergunta, respondida às cegas, dá o mesmo resultado."""
    de_sql = [p for p in pares if p.tipo == "sql"]
    aprovados: set[int] = set()
    for inicio in range(0, len(de_sql), lote):
        grupo = de_sql[inicio:inicio + lote]
        segundas = responder_as_cegas(provedor, dicionario, [p.pergunta for p in grupo])
        for par, segunda in zip(grupo, segundas, strict=True):
            assert par.sql is not None
            original, outra = _executar(ferramentas, par.sql), _executar(ferramentas, segunda)
            if original is not None and outra is not None and resultados_iguais(outra, original):
                aprovados.add(id(par))
    return [p for p in pares if p.tipo != "sql" or id(p) in aprovados]


def _normalizar(texto: str) -> str:
    sem_acento = "".join(
        c for c in unicodedata.normalize("NFKD", texto) if not unicodedata.combining(c))
    return " ".join(re.sub(r"[^a-z0-9 ]+", " ", sem_acento.casefold()).split())


def semelhanca(a: str, b: str) -> float:
    return SequenceMatcher(None, _normalizar(a), _normalizar(b)).ratio()


def filtrar_vazamento(
    pares: Sequence[Par], perguntas_de_teste: Sequence[str], limiar: float = LIMIAR_DE_VAZAMENTO
) -> tuple[list[Par], float]:
    """Descarta o que parece demais com o teste. Devolve também a maior semelhança que sobrou."""
    bons, maior = [], 0.0
    for par in pares:
        proximidade = max((semelhanca(par.pergunta, t) for t in perguntas_de_teste), default=0.0)
        if proximidade >= limiar:
            continue
        bons.append(par)
        maior = max(maior, proximidade)
    return bons, maior


def filtrar_vazamento_por_resultado(
    ferramentas: Ferramentas, pares: Sequence[Par], consultas_de_teste: Sequence[str]
) -> list[Par]:
    """Descarta o par cuja consulta devolve o mesmo resultado que um gabarito de teste.

    A semelhança de texto não pega a mesma pergunta escrita com outras palavras
    ("produtos que nunca foram vendidos" e "produtos que nunca apareceram em nenhum item").
    O resultado pega. É um filtro conservador: uma coincidência de resultado também
    descarta o par, e isso é aceitável.
    """
    gabaritos = [r for r in (_executar(ferramentas, sql) for sql in consultas_de_teste) if r]
    bons = []
    for par in pares:
        if par.tipo == "sql" and par.sql:
            resultado = _executar(ferramentas, par.sql)
            if resultado is not None and any(resultados_iguais(resultado, g) for g in gabaritos):
                continue
        bons.append(par)
    return bons


def sem_repeticao(pares: Sequence[Par]) -> list[Par]:
    """Uma só ocorrência de cada pergunta (depois de normalizar)."""
    vistos: set[str] = set()
    unicos = []
    for par in pares:
        chave = _normalizar(par.pergunta)
        if chave and chave not in vistos:
            vistos.add(chave)
            unicos.append(par)
    return unicos


def destilar(
    provedor: Provedor, ferramentas: Ferramentas, dicionario: str,
    perguntas_de_teste: Sequence[str], *, lotes_por_habilidade: int, pares_por_lote: int = 10,
    recusas_de_cada_tipo: int = 0, exemplos: Sequence[str] = (),
) -> tuple[list[Par], Funil]:
    """Gera, filtra e devolve os pares com o funil de descartes."""
    funil = Funil()
    escritos: list[Par] = []
    for habilidade in HABILIDADES:
        for _ in range(lotes_por_habilidade):
            escritos += pedir_pares(provedor, dicionario, habilidade, pares_por_lote, exemplos)
            funil.pedidos_ao_professor += 1
    for tipo in ("sem_resposta", "ambigua"):
        restantes = recusas_de_cada_tipo
        while restantes > 0:
            escritos += pedir_recusas(provedor, dicionario, tipo, min(restantes, 15))
            funil.pedidos_ao_professor += 1
            restantes -= 15
    escritos = sem_repeticao(escritos)
    funil.escritos = len(escritos)

    executam = filtrar_por_execucao(ferramentas, escritos)
    funil.apos_execucao = len(executam)
    de_sql = sum(p.tipo == "sql" for p in executam)
    funil.pedidos_ao_professor += -(-de_sql // 10)
    concordam = filtrar_por_concordancia(provedor, ferramentas, dicionario, executam)
    funil.apos_concordancia = len(concordam)
    finais, funil.maior_semelhanca_restante = filtrar_vazamento(concordam, perguntas_de_teste)
    funil.apos_vazamento = len(finais)
    funil.descartes = {
        "execucao": funil.escritos - funil.apos_execucao,
        "concordancia": funil.apos_execucao - funil.apos_concordancia,
        "vazamento": funil.apos_concordancia - funil.apos_vazamento,
    }
    return finais, funil


def escrever_em_etapas(
    provedor: Provedor, dicionario: str, *, lotes_por_habilidade: int, pares_por_lote: int = 10,
    recusas_de_cada_tipo: int = 0, exemplos: Sequence[str] = (), pular: int = 0,
) -> Iterator[tuple[int, list[Par]]]:
    """Entrega um lote por vez, numerado, para quem chama gravar antes do próximo.

    ``pular`` retoma uma geração interrompida: os primeiros lotes não são pedidos de novo.
    Para quando a cota do professor acaba, sem levantar erro.
    """
    plano: list[tuple[str, str, int]] = []
    for indice in range(lotes_por_habilidade):
        for posicao, habilidade in enumerate(HABILIDADES):
            plano.append(("sql", habilidade, indice * len(HABILIDADES) + posicao))
    for tipo in ("sem_resposta", "ambigua"):
        for parte in range(-(-recusas_de_cada_tipo // 15)):
            plano.append((tipo, tipo, parte))
    for numero, (tipo, habilidade, ordem) in enumerate(plano):
        if numero < pular:
            continue
        try:
            if tipo == "sql":
                lote = pedir_pares(provedor, dicionario, habilidade, pares_por_lote, exemplos,
                                   tema=TEMAS[ordem % len(TEMAS)])
            else:
                lote = pedir_recusas(provedor, dicionario, tipo, 15)  # type: ignore[arg-type]
        except ErroDeCota:
            return
        yield numero, lote


def conferir_em_etapas(
    provedor: Provedor, ferramentas: Ferramentas, dicionario: str, pares: Sequence[Par],
    ja_conferidas: dict[str, bool], lote: int = 10,
) -> Iterator[dict[str, bool]]:
    """Concordância com ponto de retomada: entrega o veredito de cada lote de perguntas."""
    pendentes = [p for p in pares if p.tipo == "sql" and p.pergunta not in ja_conferidas]
    for inicio in range(0, len(pendentes), lote):
        grupo = pendentes[inicio:inicio + lote]
        try:
            segundas = responder_as_cegas(provedor, dicionario, [p.pergunta for p in grupo])
        except ErroDeCota:
            return
        veredito = {}
        for par, segunda in zip(grupo, segundas, strict=True):
            assert par.sql is not None
            original, outra = _executar(ferramentas, par.sql), _executar(ferramentas, segunda)
            veredito[par.pergunta] = bool(
                original is not None and outra is not None and resultados_iguais(outra, original)
            )
        yield veredito


def contagem_por_tipo(pares: Sequence[Par]) -> dict[str, int]:
    return dict(Counter(p.tipo for p in pares))


# ---------------------------------------------------------------- medir o aluno

def mensagens_do_aluno(pergunta: str, esquema: str) -> tuple[str, str]:
    """(sistema, usuário) exatamente como o aluno vê, no treino e na medição."""
    return f"{SISTEMA_DO_ALUNO}\n\n{esquema}", pergunta


def execucao_do_aluno(
    pergunta: str, saida: str, ferramentas: Ferramentas, nome_do_modelo: str
) -> Execucao:
    """Transforma o texto que o aluno escreveu numa execução julgável como as outras."""
    execucao = Execucao(pergunta=pergunta, modo="direto", contexto="esquema",
                        provedor=nome_do_modelo, chamadas_ao_modelo=1)
    tipo, conteudo = ler_saida_do_aluno(saida)
    if tipo != "resposta":
        execucao.tipo, execucao.texto = tipo, conteudo  # type: ignore[assignment]
        return execucao
    try:
        resultado = ferramentas.executar_sql(conteudo, MAX_LINHAS)
    except (ConsultaRecusada, ErroDeConsulta) as erro:
        execucao.erro = f"consulta do aluno recusada ou com erro: {erro}"
        execucao.texto = conteudo[:500]
        return execucao
    execucao.tipo, execucao.sql, execucao.resultado = "resposta", resultado.sql, resultado
    return execucao

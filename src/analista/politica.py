"""Política de SQL: o que uma consulta do agente pode ser.

Regras, todas verificadas na árvore sintática (nunca por busca de palavra):

1. Exatamente uma instrução.
2. A instrução é uma consulta (SELECT, com ou sem CTE e operações de conjunto).
3. Nenhum nó de escrita, DDL, comando, PRAGMA, COPY, ATTACH ou SET em lugar nenhum.
4. Toda relação citada é uma visão permitida ou uma CTE **visível naquele escopo**.
   Isso barra ``FROM 'arquivo.csv'``, o esquema ``bruto`` e as visões de sistema.
   Nomes de sistema (``pg_*``, ``duckdb_*``, ``sqlite_*``, ``information_schema``)
   são recusados mesmo como nome de CTE.
5. Nenhuma função no lugar de tabela, com ou sem LATERAL (a exceção é ``unnest``).
6. Funções por lista de permissão: o que o analisador não conhece e não está na
   lista é recusado. As que ele conhece passam, menos as que leem arquivos ou
   geram linhas sem limite.

A política recusa; não conserta. Uma consulta recusada volta ao agente com o motivo.
Ela é a primeira barreira; a segunda é a conexão (ver ``banco.abrir_somente_leitura``).
"""

from __future__ import annotations

from dataclasses import dataclass

import sqlglot
from sqlglot import exp
from sqlglot.errors import SqlglotError
from sqlglot.optimizer.scope import Scope, traverse_scope

from .banco import VISOES_PERMITIDAS

_PROIBIDOS: tuple[type[exp.Expression], ...] = (
    exp.Insert, exp.Update, exp.Delete, exp.Merge, exp.Create, exp.Drop, exp.Alter,
    exp.TruncateTable, exp.Command, exp.Copy, exp.Attach, exp.Detach, exp.Pragma, exp.Set,
    exp.Use, exp.Transaction, exp.Commit, exp.Rollback, exp.Into, exp.Lock,
)

_PREFIXOS_DE_SISTEMA = ("pg_", "duckdb_", "sqlite_", "information_schema", "pragma_")

# Funções que o analisador conhece mas que leem arquivos ou geram linhas sem limite.
_CONHECIDAS_PROIBIDAS_PREFIXOS = ("read_", "scan_", "sniff_", "duckdb_", "pragma_", "pg_")
_CONHECIDAS_PROIBIDAS = frozenset({
    "generate_series", "generate_date_array", "generate_timestamp_array", "explode",
    "explode_outer", "posexplode", "current_user", "current_schema", "current_database",
    "current_catalog", "session_user", "version", "current_version", "repeat", "uuid",
    "rand", "random",
})

# Funções que o analisador NÃO conhece e que são seguras: escalares e de agregação.
_DESCONHECIDAS_PERMITIDAS = frozenset({
    # datas
    "isodow", "dayname", "monthname", "weekofyear", "yearweek", "weekday", "dayofmonth",
    "epoch", "epoch_ms", "last_day", "make_date", "make_timestamp", "date_part", "datepart",
    "datesub", "date_sub", "datediff", "date_diff", "age", "today", "time_bucket", "century",
    "decade", "era", "julian", "isoyear",
    # texto
    "contains", "starts_with", "ends_with", "prefix", "suffix", "strpos", "instr", "lpad",
    "rpad", "reverse", "split_part", "regexp_matches", "regexp_replace", "regexp_extract",
    "regexp_full_match", "strip_accents", "lcase", "ucase", "strlen", "char_length",
    "array_length", "len", "list_count",
    # números
    "trunc", "sign", "greatest", "least", "ifnull", "log2", "log10", "cbrt", "pi", "isnan",
    "isinf", "isfinite", "divide", "fdiv", "fmod", "gcd", "lcm", "even",
    # agregação e janela
    "quantile_cont", "quantile_disc", "quantile", "arg_max", "arg_min", "max_by", "min_by",
    "count_if", "countif", "bool_and", "bool_or", "mode", "any_value", "product", "kurtosis",
    "skewness", "approx_count_distinct", "approx_quantile", "stddev_samp", "stddev_pop",
    "var_samp", "var_pop", "regr_slope", "regr_intercept", "regr_r2", "covar_pop",
    "covar_samp", "entropy", "mad", "fsum", "favg", "sumkahan", "percent_rank", "cume_dist",
    "ntile", "nth_value", "first", "last", "string_agg", "group_concat", "listagg",
    "histogram",
})


class ConsultaRecusada(ValueError):
    """A consulta viola a política. A mensagem diz qual regra."""


@dataclass(frozen=True)
class ConsultaValidada:
    sql: str
    relacoes: frozenset[str]


def _de_sistema(nome: str) -> bool:
    return nome.startswith(_PREFIXOS_DE_SISTEMA)


def validar(sql: str, permitidas: frozenset[str] = VISOES_PERMITIDAS) -> ConsultaValidada:
    """Devolve a consulta normalizada ou levanta ``ConsultaRecusada``."""
    try:
        instrucoes = [s for s in sqlglot.parse(sql, read="duckdb") if s is not None]
    except SqlglotError as erro:
        raise ConsultaRecusada(f"SQL inválido: {str(erro).splitlines()[0]}") from erro
    if len(instrucoes) != 1:
        raise ConsultaRecusada("envie exatamente uma instrução SQL")
    raiz = instrucoes[0]
    if not isinstance(raiz, exp.Query):
        raise ConsultaRecusada("só consultas SELECT são permitidas")

    for no in raiz.walk():
        if isinstance(no, _PROIBIDOS):
            raise ConsultaRecusada(f"operação não permitida: {type(no).__name__.upper()}")

    for cte in raiz.find_all(exp.CTE):
        if _de_sistema(cte.alias_or_name.lower()):
            raise ConsultaRecusada(f"nome reservado ao sistema: {cte.alias_or_name}")

    for lateral in raiz.find_all(exp.Lateral):
        if not isinstance(lateral.this, exp.Subquery | exp.Unnest):
            raise ConsultaRecusada("funções de tabela não são permitidas (LATERAL)")

    relacoes = _conferir_relacoes(raiz, permitidas)
    _conferir_funcoes(raiz)
    return ConsultaValidada(sql=raiz.sql(dialect="duckdb"), relacoes=frozenset(relacoes))


def _conferir_relacoes(raiz: exp.Query, permitidas: frozenset[str]) -> set[str]:
    """Cada tabela é conferida no escopo em que aparece.

    Uma CTE só libera o próprio nome onde ela é visível. Sem isso, uma CTE declarada
    numa subconsulta liberaria o mesmo nome no escopo de fora, onde ele poderia
    resolver para uma visão de sistema.
    """
    try:
        escopos = list(traverse_scope(raiz))
    except SqlglotError as erro:
        raise ConsultaRecusada("não foi possível analisar o escopo da consulta") from erro

    relacoes: set[str] = set()
    conferidas: set[int] = set()
    for escopo in escopos:
        for tabela in escopo.tables:
            conferidas.add(id(tabela))
            if isinstance(tabela.this, exp.Func) or not isinstance(tabela.this, exp.Identifier):
                raise ConsultaRecusada("funções de tabela não são permitidas")
            nome = tabela.name.lower()
            if tabela.db or tabela.catalog:
                raise ConsultaRecusada(f"relação fora das visões permitidas: {tabela.sql()}")
            if _de_sistema(nome):
                raise ConsultaRecusada(f"relação fora das visões permitidas: {nome}")
            if isinstance(escopo.sources.get(tabela.alias_or_name), Scope):
                continue  # CTE visível neste escopo
            if nome not in permitidas:
                raise ConsultaRecusada(f"relação fora das visões permitidas: {nome}")
            relacoes.add(nome)

    # Nenhuma tabela pode ter ficado fora da análise de escopo.
    for tabela in raiz.find_all(exp.Table):
        if id(tabela) not in conferidas:
            raise ConsultaRecusada(f"relação em posição não analisável: {tabela.sql()}")
    return relacoes


def _conferir_funcoes(raiz: exp.Query) -> None:
    for funcao in raiz.find_all(exp.Func):
        if isinstance(funcao, exp.Anonymous):
            nome = funcao.name.lower()
            if nome not in _DESCONHECIDAS_PERMITIDAS:
                raise ConsultaRecusada(f"função não permitida: {nome}")
            continue
        nome = funcao.sql_name().lower()
        if nome in _CONHECIDAS_PROIBIDAS or nome.startswith(_CONHECIDAS_PROIBIDAS_PREFIXOS):
            raise ConsultaRecusada(f"função não permitida: {nome}")

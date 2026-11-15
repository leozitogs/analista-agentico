"""Linha de comando: carregar o banco, rodar uma consulta, conferir os gabaritos."""

from __future__ import annotations

import argparse
import json
from collections.abc import Sequence
from pathlib import Path

from . import sintetico
from .agente import Agente, dicionario_resumido
from .avaliar import avaliar
from .banco import carregar
from .destilacao import destilar
from .ferramentas import ErroDeConsulta, Ferramentas
from .perguntas import ler
from .politica import ConsultaRecusada
from .provedor import ErroDeProvedor, criar_provedor, listar_modelos

BANCO_PADRAO = Path("dados/olist.duckdb")


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="analista", description=__doc__)
    comandos = parser.add_subparsers(dest="comando", required=True)

    c = comandos.add_parser("carregar", help="cria o banco a partir dos CSVs")
    c.add_argument("--csv", type=Path, default=Path("dados/brutos"))
    c.add_argument("--banco", type=Path, default=BANCO_PADRAO)

    s = comandos.add_parser("sintetico", help="gera CSVs sintéticos para teste")
    s.add_argument("pasta", type=Path)

    q = comandos.add_parser("sql", help="executa uma consulta pela política")
    q.add_argument("consulta")
    q.add_argument("--banco", type=Path, default=BANCO_PADRAO)

    g = comandos.add_parser("conferir-gabarito", help="executa o SQL de cada pergunta")
    g.add_argument("arquivo", type=Path)
    g.add_argument("--banco", type=Path, default=BANCO_PADRAO)

    comandos.add_parser("modelos", help="lista os modelos do Gemini disponíveis para a chave")

    pe = comandos.add_parser("perguntar", help="faz uma pergunta ao agente")
    pe.add_argument("pergunta")
    pe.add_argument("--modo", choices=["agente", "direto"], default="agente")
    pe.add_argument("--contexto", choices=["completo", "esquema", "nenhum"], default="completo")
    pe.add_argument("--modelo", default=None)
    pe.add_argument("--banco", type=Path, default=BANCO_PADRAO)

    av = comandos.add_parser("avaliar", help="roda um conjunto de perguntas e mede o acerto")
    av.add_argument("arquivo", type=Path)
    av.add_argument("--modo", choices=["agente", "direto"], default="agente")
    av.add_argument("--contexto", choices=["completo", "esquema", "nenhum"], default="completo")
    av.add_argument("--modelo", default=None)
    av.add_argument("--saida", type=Path, default=None, help="JSONL com os rastros")
    av.add_argument("--banco", type=Path, default=BANCO_PADRAO)

    gp = comandos.add_parser("gerar-pares", help="gera pares de treino com o modelo professor")
    gp.add_argument("--saida", type=Path, required=True, help="JSONL com os pares aprovados")
    gp.add_argument("--lotes", type=int, default=1, help="lotes por habilidade")
    gp.add_argument("--recusas", type=int, default=0, help="exemplos de cada tipo de recusa")
    gp.add_argument("--modelo", default=None)
    gp.add_argument("--banco", type=Path, default=BANCO_PADRAO)
    gp.add_argument("--teste", type=Path, default=Path("avaliacao/perguntas/teste.jsonl"))
    gp.add_argument(
        "--exemplos", type=Path, default=Path("avaliacao/perguntas/desenvolvimento.jsonl")
    )

    args = parser.parse_args(argv)

    if args.comando == "carregar":
        for tabela, linhas in carregar(args.csv, args.banco).items():
            print(f"{tabela:12} {linhas:>9}")
        return 0
    if args.comando == "sintetico":
        sintetico.gerar(args.pasta)
        return 0

    if args.comando == "modelos":
        try:
            print("\n".join(listar_modelos()))
        except ErroDeProvedor as erro:
            print(erro)
            return 1
        return 0

    ferramentas = Ferramentas(args.banco)
    try:
        if args.comando == "gerar-pares":
            # As perguntas de teste só são lidas para o filtro de vazamento; nunca vão ao modelo.
            de_teste = [p.pergunta for p in ler(args.teste)]
            de_estilo = [p.pergunta for p in ler(args.exemplos) if p.sql][:8]
            try:
                pares, funil = destilar(
                    criar_provedor(args.modelo), ferramentas, dicionario_resumido(), de_teste,
                    lotes_por_habilidade=args.lotes, recusas_de_cada_tipo=args.recusas,
                    exemplos=de_estilo,
                )
            except ErroDeProvedor as erro:
                print(f"interrompido: {erro}")
                return 2
            args.saida.parent.mkdir(parents=True, exist_ok=True)
            args.saida.write_text(
                "\n".join(json.dumps(p.model_dump(), ensure_ascii=False) for p in pares) + "\n",
                encoding="utf-8",
            )
            args.saida.with_suffix(".funil.json").write_text(
                json.dumps(funil.model_dump(), ensure_ascii=False, indent=2), encoding="utf-8"
            )
            print(json.dumps(funil.model_dump(), ensure_ascii=False, indent=2))
            return 0
        if args.comando in ("perguntar", "avaliar"):
            try:
                agente = Agente(
                    criar_provedor(args.modelo), ferramentas, modo=args.modo,
                    contexto=args.contexto,
                )
            except ErroDeProvedor as erro:
                print(erro)
                return 1
            if args.comando == "perguntar":
                try:
                    execucao = agente.perguntar(args.pergunta)
                except ErroDeProvedor as erro:
                    print(erro)
                    return 1
                for passo in execucao.passos:
                    marca = "ok  " if passo.ok else "ERRO"
                    detalhe = passo.argumentos.get("sql") or passo.argumentos.get("nome") or ""
                    print(f"  [{marca}] {passo.ferramenta}: {detalhe} -> {passo.resumo}")
                print(f"\n[{execucao.tipo}] {execucao.texto}")
                if execucao.sql:
                    print(f"\nSQL: {execucao.sql}")
                if execucao.numeros_sem_origem:
                    print(f"números sem origem no resultado: {execucao.numeros_sem_origem}")
                if execucao.erro:
                    print(f"erro: {execucao.erro}")
                return 0 if execucao.tipo != "falha" else 1
            juiz = Ferramentas(args.banco)
            try:
                resumo, avaliadas = avaliar(agente, ler(args.arquivo), juiz, args.saida)
            finally:
                juiz.fechar()
            for linha in avaliadas:
                print(f"{linha.id}  {'ACERTOU' if linha.acertou else 'errou  '}  {linha.motivo}")
            print(json.dumps(resumo.model_dump(), ensure_ascii=False, indent=2))
            return 2 if resumo.interrompida else 0
        if args.comando == "sql":
            try:
                resultado = ferramentas.executar_sql(args.consulta)
            except (ConsultaRecusada, ErroDeConsulta) as erro:
                print(f"recusada: {erro}")
                return 1
            print(json.dumps(resultado.model_dump(), ensure_ascii=False, indent=2))
            return 0

        falhas = 0
        for pergunta in ler(args.arquivo):
            if pergunta.sql is None:
                print(f"{pergunta.id}  {pergunta.tipo}")
                continue
            try:
                resultado = ferramentas.executar_sql(pergunta.sql)
            except (ConsultaRecusada, ErroDeConsulta) as erro:
                falhas += 1
                print(f"{pergunta.id}  FALHOU: {erro}")
                continue
            aviso = "  TRUNCADO" if resultado.truncado else ""
            vazio = "  VAZIO" if not resultado.linhas else ""
            print(f"{pergunta.id}  {len(resultado.linhas)} linha(s){aviso}{vazio}")
            falhas += bool(aviso or vazio)
        return 1 if falhas else 0
    finally:
        ferramentas.fechar()


if __name__ == "__main__":
    raise SystemExit(main())

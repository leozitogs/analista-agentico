"""Linha de comando: carregar o banco, rodar uma consulta, conferir os gabaritos."""

from __future__ import annotations

import argparse
import json
from collections.abc import Sequence
from pathlib import Path

from . import sintetico
from .agente import Agente, contexto_do_banco, dicionario_resumido
from .avaliar import Linha, avaliar, julgar, para_rastro, resumir_linhas
from .banco import carregar
from .destilacao import (
    Funil,
    Par,
    alvo_do_aluno,
    conferir_em_etapas,
    contagem_por_tipo,
    destilar,
    escrever_em_etapas,
    execucao_do_aluno,
    filtrar_por_execucao,
    filtrar_vazamento,
    filtrar_vazamento_por_resultado,
    mensagens_do_aluno,
    sem_repeticao,
)
from .ferramentas import ErroDeConsulta, Ferramentas
from .perguntas import ler
from .politica import ConsultaRecusada
from .provedor import ErroDeProvedor, ProvedorGemini, criar_provedor, listar_modelos

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

    ee = comandos.add_parser("escrever-pares", help="etapa 1: o professor escreve os pares")
    ee.add_argument("--saida", type=Path, required=True, help="JSONL, um lote por linha")
    ee.add_argument("--lotes", type=int, default=1, help="lotes por habilidade")
    ee.add_argument("--recusas", type=int, default=0, help="exemplos de cada tipo de recusa")
    ee.add_argument("--modelo", default=None)
    ee.add_argument("--temperatura", type=float, default=1.0)
    ee.add_argument("--banco", type=Path, default=BANCO_PADRAO)
    ee.add_argument(
        "--exemplos", type=Path, default=Path("avaliacao/perguntas/desenvolvimento.jsonl")
    )

    fp = comandos.add_parser("filtrar-pares", help="etapa 2: execução, concordância e vazamento")
    fp.add_argument("escritos", type=Path)
    fp.add_argument("--saida", type=Path, required=True)
    fp.add_argument("--modelo", default=None)
    fp.add_argument("--banco", type=Path, default=BANCO_PADRAO)
    fp.add_argument("--teste", type=Path, default=Path("avaliacao/perguntas/teste.jsonl"))

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

    ep = comandos.add_parser("exportar-prompts", help="escreve os prompts do aluno em JSONL")
    ep.add_argument("perguntas", type=Path)
    ep.add_argument("--saida", type=Path, required=True)
    ep.add_argument("--banco", type=Path, default=BANCO_PADRAO)

    et = comandos.add_parser("exportar-treino", help="pares aprovados viram exemplos de treino")
    et.add_argument("pares", type=Path)
    et.add_argument("--saida", type=Path, required=True)
    et.add_argument("--banco", type=Path, default=BANCO_PADRAO)

    aa = comandos.add_parser("avaliar-aluno", help="julga as saídas de um modelo aluno")
    aa.add_argument("perguntas", type=Path)
    aa.add_argument("saidas", type=Path, help='JSONL com {"id": ..., "saida": ...}')
    aa.add_argument("--nome", required=True, help="nome do modelo, para o rastro")
    aa.add_argument("--saida", type=Path, default=None, help="JSONL com os rastros")
    aa.add_argument("--banco", type=Path, default=BANCO_PADRAO)

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
        if args.comando == "exportar-prompts":
            esquema = contexto_do_banco("esquema", ferramentas)
            linhas_de_prompt = []
            for pergunta in ler(args.perguntas):
                sistema, usuario = mensagens_do_aluno(pergunta.pergunta, esquema)
                prompt = {"id": pergunta.id, "sistema": sistema, "usuario": usuario}
                linhas_de_prompt.append(json.dumps(prompt, ensure_ascii=False))
            args.saida.parent.mkdir(parents=True, exist_ok=True)
            args.saida.write_text("\n".join(linhas_de_prompt) + "\n", encoding="utf-8")
            print(f"{len(linhas_de_prompt)} prompts em {args.saida}")
            return 0
        if args.comando == "exportar-treino":
            esquema = contexto_do_banco("esquema", ferramentas)
            exemplos_de_treino = []
            for bruta in args.pares.read_text(encoding="utf-8").splitlines():
                if not bruta.strip():
                    continue
                par = Par.model_validate_json(bruta)
                sistema, usuario = mensagens_do_aluno(par.pergunta, esquema)
                exemplo = {"sistema": sistema, "usuario": usuario, "alvo": alvo_do_aluno(par)}
                exemplos_de_treino.append(json.dumps(exemplo, ensure_ascii=False))
            args.saida.parent.mkdir(parents=True, exist_ok=True)
            args.saida.write_text("\n".join(exemplos_de_treino) + "\n", encoding="utf-8")
            print(f"{len(exemplos_de_treino)} exemplos de treino em {args.saida}")
            return 0
        if args.comando == "avaliar-aluno":
            saidas = {
                json.loads(x)["id"]: json.loads(x)["saida"]
                for x in args.saidas.read_text(encoding="utf-8").splitlines() if x.strip()
            }
            juiz = Ferramentas(args.banco)
            julgadas: list[Linha] = []
            try:
                for pergunta in ler(args.perguntas):
                    # pergunta sem saída do modelo conta como falha, não some
                    execucao = execucao_do_aluno(
                        pergunta.pergunta, saidas.get(pergunta.id, ""), ferramentas, args.nome)
                    acertou, motivo = julgar(pergunta, execucao, juiz)
                    julgadas.append(Linha(
                        id=pergunta.id, nivel=pergunta.nivel, tipo_pergunta=pergunta.tipo,
                        acertou=acertou, motivo=motivo, execucao=execucao))
            finally:
                juiz.fechar()
            if args.saida is not None:
                args.saida.parent.mkdir(parents=True, exist_ok=True)
                args.saida.write_text(
                    "\n".join(json.dumps(para_rastro(x), ensure_ascii=False) for x in julgadas)
                    + "\n", encoding="utf-8")
            for linha in julgadas:
                marca = "ACERTOU" if linha.acertou else "errou  "
                print(f"{linha.id}  {marca}  {linha.motivo[:90]}")
            resumo_do_aluno = resumir_linhas(args.nome, "direto", "esquema", julgadas)
            print(json.dumps(resumo_do_aluno.model_dump(), ensure_ascii=False, indent=2))
            return 0
        if args.comando == "escrever-pares":
            de_estilo = [p.pergunta for p in ler(args.exemplos) if p.sql][:8]
            feitos = 0
            if args.saida.exists():
                feitos = sum(1 for x in args.saida.read_text(encoding="utf-8").splitlines() if x)
            try:
                professor = ProvedorGemini(args.modelo, temperatura=args.temperatura)
            except ErroDeProvedor as erro:
                print(erro)
                return 1
            args.saida.parent.mkdir(parents=True, exist_ok=True)
            escritos_agora = 0
            with args.saida.open("a", encoding="utf-8", newline="\n") as arquivo:
                for numero, lote in escrever_em_etapas(
                    professor, dicionario_resumido(), lotes_por_habilidade=args.lotes,
                    recusas_de_cada_tipo=args.recusas, exemplos=de_estilo, pular=feitos,
                ):
                    registro = {"lote": numero, "pares": [p.model_dump() for p in lote]}
                    arquivo.write(json.dumps(registro, ensure_ascii=False) + "\n")
                    arquivo.flush()
                    escritos_agora += len(lote)
            total_de_lotes = sum(
                1 for x in args.saida.read_text(encoding="utf-8").splitlines() if x)
            previstos = args.lotes * 11 + 2 * -(-args.recusas // 15)
            print(f"{escritos_agora} pares escritos agora; {total_de_lotes} de {previstos} lotes")
            return 0 if total_de_lotes >= previstos else 2
        if args.comando == "filtrar-pares":
            escritos = [
                Par.model_validate(p)
                for linha_bruta in args.escritos.read_text(encoding="utf-8").splitlines()
                if linha_bruta.strip()
                for p in json.loads(linha_bruta)["pares"]
            ]
            funil = Funil(pedidos_ao_professor=0, escritos=len(escritos))
            unicos = sem_repeticao(escritos)
            executam = filtrar_por_execucao(ferramentas, unicos)
            funil.apos_execucao = len(executam)
            marcas = args.saida.with_suffix(".concordancia.json")
            vereditos: dict[str, bool] = (
                json.loads(marcas.read_text(encoding="utf-8")) if marcas.exists() else {}
            )
            try:
                revisor = criar_provedor(args.modelo)
            except ErroDeProvedor as erro:
                print(erro)
                return 1
            args.saida.parent.mkdir(parents=True, exist_ok=True)
            for novo in conferir_em_etapas(
                revisor, ferramentas, dicionario_resumido(), executam, vereditos
            ):
                vereditos.update(novo)
                funil.pedidos_ao_professor += 1
                marcas.write_text(json.dumps(vereditos, ensure_ascii=False), encoding="utf-8")
            faltam = sum(p.tipo == "sql" and p.pergunta not in vereditos for p in executam)
            concordam = [p for p in executam if p.tipo != "sql" or vereditos.get(p.pergunta)]
            funil.apos_concordancia = len(concordam)
            perguntas_de_teste = ler(args.teste)
            de_teste = [p.pergunta for p in perguntas_de_teste]
            sem_texto_igual, funil.maior_semelhanca_restante = filtrar_vazamento(
                concordam, de_teste)
            finais = filtrar_vazamento_por_resultado(
                ferramentas, sem_texto_igual, [p.sql for p in perguntas_de_teste if p.sql])
            funil.apos_vazamento = len(finais)
            funil.descartes = {
                "repetidos": len(escritos) - len(unicos),
                "execucao": len(unicos) - len(executam),
                "concordancia": len(executam) - len(concordam) - faltam,
                "ainda_sem_conferir": faltam,
                "vazamento_por_texto": len(concordam) - len(sem_texto_igual),
                "vazamento_por_resultado": len(sem_texto_igual) - len(finais),
            }
            args.saida.write_text(
                "\n".join(json.dumps(p.model_dump(), ensure_ascii=False) for p in finais) + "\n",
                encoding="utf-8",
            )
            relatorio = {**funil.model_dump(), "por_tipo": contagem_por_tipo(finais)}
            args.saida.with_suffix(".funil.json").write_text(
                json.dumps(relatorio, ensure_ascii=False, indent=2), encoding="utf-8")
            print(json.dumps(relatorio, ensure_ascii=False, indent=2))
            return 2 if faltam else 0
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

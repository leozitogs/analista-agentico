# Resultados

## Conjunto de teste · 14/11/2026

60 perguntas, congeladas por hash antes da primeira rodada
([como foram feitas e quais os limites](../docs/processo/B1-conjunto-de-teste.md)).
Uma rodada por configuração, temperatura 0. O intervalo é o de Wilson a 95%.

### Acerto de execução (44 perguntas com gabarito em SQL)

| | Agente | Linha de base (uma consulta, sem ferramentas) |
|---|---:|---:|
| `gemini-3.5-flash-lite` | **39 / 44 = 88,6%** (76 a 95%) | **41 / 44 = 93,2%** (82 a 98%) |
| `qwen3:4b-instruct` local | 8 / 44 = 18,2% (10 a 32%) | 4 / 44 = 9,1% (4 a 21%) |

Por nível, no Gemini lite:

| Nível | Agente | Linha de base |
|---|---:|---:|
| 1 (uma tabela) | 14 / 14 | 14 / 14 |
| 2 (junções e agrupamentos) | 14 / 16 | 15 / 16 |
| 3 (janelas, duas etapas, armadilhas) | 11 / 14 | 12 / 14 |

### Perguntas sem resposta e ambíguas

| | Gemini agente | Gemini linha de base | Qwen agente | Qwen linha de base |
|---|---:|---:|---:|---:|
| Sem resposta: disse que não dá para responder | 6 / 8 | 6 / 8 | 3 / 8 | 6 / 8 |
| Sem resposta: recusou ou pediu esclarecimento | 6 / 8 | 7 / 8 | 3 / 8 | 8 / 8 |
| Ambíguas: pediu esclarecimento | 4 / 8 | 6 / 8 | 0 / 8 | 8 / 8 |

### Custo e operação

| | Gemini agente | Gemini linha de base | Qwen agente | Qwen linha de base |
|---|---:|---:|---:|---:|
| Chamadas ao modelo | 140 | 85 | 442 | 69 |
| Tokens de entrada | 270.894 | 133.049 | 1.193.319 | 114.545 |
| Tokens de saída | 14.727 | 10.241 | 39.736 | 7.480 |
| Duração média por pergunta | 7,0 s | 5,7 s | 29,0 s | 4,8 s |
| Falhas (sem resposta final) | 0 | 0 | 38 | 0 |
| Respostas com número sem origem no resultado | 1 | 23 | 5 | 3 |

### Contra os critérios do plano

Os critérios foram escritos antes de existir código. Valem para o agente com o Gemini lite.

| # | Critério | Meta | Medido | |
|---|---|---|---|---|
| C1 | Acerto de execução | ≥ 75% | 88,6% (intervalo de 76 a 95%) | Atingido |
| C2 | Sem resposta nos dados: recusa ou pede esclarecimento | ≥ 90% | 6 / 8 = 75% | **Não atingido** |
| C3 | Ataques de injeção pelos dados | Nenhuma ação fora da política | Não medido | Pendente (marco B2) |
| C4 | Escrita no banco impossível | Provado por teste | Testes da política e da conexão | Atingido |
| C5 | Toda resposta mostra a consulta executada | Sempre | Por construção: a consulta final é executada pelo agente e gravada | Atingido |
| C6 | Custo e latência por pergunta | Medidos | Tabela acima (tokens e duração; sem preço) | Atingido |

### O que os números dizem

1. **O agente não foi melhor que a linha de base.** No Gemini lite, 39 contra 41 em 44. A
   diferença está dentro do ruído, mas não há nada aqui que justifique o agente: ele gasta
   o dobro de tokens e não acerta mais. O plano dizia que esta comparação era a que
   justificaria o agente existir; com estes dados, ela não justifica.
2. **Por quê, provavelmente:** o dicionário de dados entra no prompt nos dois modos e já
   descreve as armadilhas. Com isso, inspecionar o banco acrescenta pouco. O agente fez em
   média 1,25 chamada de ferramenta por pergunta antes de responder. É uma hipótese; não
   foi testada (o teste seria rodar os dois modos sem o dicionário).
3. **O agente é pior em pedir esclarecimento** (4 de 8 contra 6 de 8). Com ferramentas à
   mão, ele tende a escolher uma leitura e seguir. Também é hipótese.
4. **Em duas perguntas sem resposta, os dois modos responderam mesmo assim:** `s02`
   (devoluções: usaram os cancelados) e `s04` (nome do produto: devolveram a categoria ou o
   identificador). Eram as duas armadilhas desenhadas para isso, e funcionaram.
5. **O modelo local de 4 bilhões de parâmetros não dá conta.** Como agente, 38 das 60
   perguntas terminaram sem resposta: 33 no teto de 10 chamadas e 5 por erro do Ollama.
   Como linha de base, ele pede esclarecimento para quase tudo (37 das 44 respondíveis), o
   que lhe dá 8 de 8 nas ambíguas sem mérito nenhum.
6. **A verificação de números pegou o que devia:** na linha de base, que escreve o texto
   antes de ver o resultado, 23 respostas ficaram com número sem origem. No agente, 1.

### Divergências olhadas uma a uma (Gemini lite)

O conjunto de teste não foi alterado depois das rodadas. O que segue é leitura dos erros.

| Pergunta | Modo | O que aconteceu | Erro de quem |
|---|---|---|---|
| `t19` | Agente | Agrupou por pedido e devolveu uma linha por pedido, em vez da contagem | Do modelo |
| `t29`, `t40`, `t41` | Agente | Valor certo, com colunas a mais | Do modelo, pelo critério estrito: a pergunta pedia só um valor |
| `t32` | Agente | Valores certos, com colunas a mais e arredondados a 2 casas; 1,50 voltou como 1,5 e o comparador não aceita uma casa só | Colunas a mais são do modelo; o 1,5 é limite do comparador |
| `t32` | Linha de base | Valores certos, com colunas a mais | Do modelo, pelo critério estrito |
| `t24` | Linha de base | Valores certos, com o ano como texto ("2016") em vez de número | Do modelo, pelo critério estrito |
| `t40` | Linha de base | Não chegou a uma consulta válida e disse que não dava para responder | Do modelo |

Nenhuma divergência apontou gabarito errado.

**Leitura posterior, não pré-registrada:** se coluna a mais e ano como texto não contassem
como erro, o agente teria 42 de 44 e a linha de base 43 de 44. O critério oficial continua
sendo o estrito, que era o do plano. Esta leitura só serve para dizer onde os erros estão:
quase todos são de forma, e não de lógica. Ela não muda a conclusão 1.

### Limites desta medição

- Uma rodada por configuração. A variação entre rodadas existe e não foi medida.
- 44 perguntas com SQL: os intervalos são largos, e 8 perguntas por grupo nas sem
  resposta e ambíguas não sustentam percentual nenhum.
- Quem escreveu as perguntas escreveu o agente, e o revisor humano não conferiu o SQL
  dos gabaritos.
- Só o modelo lite do Gemini foi medido; a camada gratuita não comporta um Flash.
- Os rastros do Gemini não registram chamadas lidas do texto (não se aplica a ele).

Rastros: `teste-agente-lite.jsonl`, `teste-direto-lite.jsonl`,
`teste-agente-qwen3-4b.jsonl`, `teste-direto-qwen3-4b.jsonl`.

---

# Conjunto de desenvolvimento

> **Só conjunto de desenvolvimento.** São 20 perguntas usadas para construir e ajustar o
> agente; os gabaritos de duas delas foram corrigidos depois da primeira rodada. Estes
> números servem para achar defeitos, **não** para dizer quão bom o agente é. A medida que
> conta é a do conjunto de teste, que ainda não existe.

## 13/11/2026 · `gemini-3.5-flash-lite`, raciocínio baixo, temperatura 0, uma rodada

| | Agente | Linha de base (uma consulta, sem ferramentas) |
|---|---:|---:|
| Acerto geral | 17 / 20 | 14 / 20 |
| Nível 1 | 6 / 6 | 6 / 6 |
| Nível 2 | 5 / 6 | 3 / 6 |
| Nível 3 | 2 / 4 | 3 / 4 |
| Sem resposta nos dados | 2 / 2 | 2 / 2 |
| Ambíguas | 2 / 2 | 0 / 2 |
| Chamadas ao modelo | 44 | 29 |
| Tokens de entrada / saída | 83.582 / 4.892 | 45.378 / 3.258 |
| Duração média por pergunta | 6 s | 4 s |

Rastros completos: `dev-agente-lite.jsonl` e `dev-direto-lite.jsonl`.

Depois da revisão independente o comparador ficou mais rigoroso (tolerância numérica e
ordem de colunas). Os rastros foram rejulgados com ele, sem novas chamadas ao modelo, e
nenhum acerto mudou.

### Leitura

- Com 20 perguntas, a diferença de 3 acertos não separa os dois modos. Não dá para
  afirmar que o agente é melhor.
- **Erros do agente:**
  - `d12`: contou a avaliação uma vez por item, e não por pedido. Erro real.
  - `d13`: filtrou 2017 antes de calcular a variação (janeiro ficou sem mês anterior) e
    devolveu uma coluna a mais.
  - `d16`: os números estão certos, mas devolveu uma coluna a mais (o total em reais). O
    comparador não dá crédito a coluna extra. Se isso deve ser erro é uma decisão em aberto.
- **O agente quase não inspeciona:** em 15 das 16 perguntas com SQL ele executou uma
  consulta e respondeu, sem olhar tabelas nem amostras. O dicionário de dados no prompt já dá o que ele precisa, então a
  vantagem das ferramentas de inspeção não aparece neste conjunto.
- **Linha de base e números:** no modo direto o modelo escreve o texto antes de ver o
  resultado, então inventa os números. Em 8 respostas eles continuaram sem origem mesmo
  depois da chance de correção, e ficaram marcados. O acerto mede só o resultado da
  consulta, então essas respostas contam como acerto com texto errado. No modo agente,
  nenhuma resposta teve número sem origem.
- Uma falha da linha de base (`d19`) foi do provedor: o modelo devolveu resposta vazia.

## 13 e 14/11/2026 · modelo local `qwen3:4b-instruct` (Ollama, Q4_K_M, contexto de 8k), temperatura 0, uma rodada

Mesmo conjunto de desenvolvimento, mesmo prompt, mesma avaliação. Roda numa placa de 6 GB,
sem cota e sem custo por chamada.

| | Agente | Linha de base |
|---|---:|---:|
| Acerto geral | 6 / 20 | 5 / 20 |
| Nível 1 | 4 / 6 | 2 / 6 |
| Nível 2 | 0 / 6 | 0 / 6 |
| Nível 3 | 0 / 4 | 0 / 4 |
| Sem resposta nos dados | 2 / 2 | 1 / 2 |
| Ambíguas | 0 / 2 | 2 / 2 |
| Chamadas ao modelo | 139 | 22 |
| Tokens de entrada / saída | 402.262 / 28.124 | 36.398 / 2.814 |
| Duração média por pergunta | 46 s | 5 s |

Rastros: `dev-agente-qwen3-4b.jsonl` e `dev-direto-qwen3-4b.jsonl`.

### Leitura

- **O modelo de 4 bilhões de parâmetros não dá conta da tarefa além do nível 1.** Nenhum
  acerto em junções nem em consultas de nível 3, nos dois modos.
- **Como o agente falha:** em 8 das 20 perguntas ele bate no teto de 10 chamadas sem
  encerrar. O modelo executa consultas, mas não consegue fechar com a chamada `responder`.
  Uma falha foi do provedor (HTTP 400 do Ollama).
- **Como a linha de base falha:** em 12 perguntas respondíveis ela pede esclarecimento em
  vez de responder. Por isso "acerta" as duas ambíguas: não é discernimento, é o
  comportamento padrão dela. É um exemplo de por que o acerto por tipo de pergunta precisa
  ser lido junto com os erros.
- **Chamada escrita como texto:** este modelo muitas vezes escreve `responder({...})` como
  texto em vez de usar a chamada estruturada. O provedor local reconhece essa forma (só
  quando o texto inteiro é a chamada, de uma ferramenta declarada, com JSON válido). Sem
  isso, o acerto do agente seria ainda menor.
- **Variação entre rodadas:** uma rodada anterior da linha de base, interrompida na
  penúltima pergunta, tinha 3 acertos em 19; esta teve 5 em 20. Mesmo com temperatura 0 há
  variação, e uma rodada só não a mede.

### Comparação entre os dois modelos (só desenvolvimento)

| | `gemini-3.5-flash-lite` | `qwen3:4b-instruct` local |
|---|---:|---:|
| Agente | 17 / 20 | 6 / 20 |
| Linha de base | 14 / 20 | 5 / 20 |

A diferença entre os modelos é muito maior que a diferença entre os modos. Com estas 20
perguntas, é a única conclusão que os números sustentam.

### O que não está aqui

- Rodada com um modelo Flash: a camada gratuita limita a 20 pedidos por dia, e a tentativa
  esgotou a cota no meio. Os dados parciais foram descartados.
- Repetições: é uma rodada só; não há medida de variação entre execuções.

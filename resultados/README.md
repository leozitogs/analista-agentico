# Resultados

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

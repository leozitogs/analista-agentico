# Pares de treino da destilação

`pares.jsonl` tem 1.283 exemplos escritos por um modelo professor (Gemini 3.5 Flash Lite) e aprovados por filtros automáticos. **Nenhuma pessoa conferiu estes pares.** O desenho está em [D0](../../docs/processo/D0-destilacao-plano.md).

| Tipo | Exemplos |
|---|---:|
| Pergunta com consulta SQL | 1.004 |
| Pergunta sem resposta nos dados, com o que falta | 155 |
| Pergunta ambígua, com a pergunta de esclarecimento | 124 |

## O funil (`funil.json`)

| Etapa | Sobram | Saem |
|---|---:|---:|
| Escritos pelo professor (196 pedidos de escrita) | 2.189 | — |
| Sem perguntas repetidas | 2.020 | 169 |
| A consulta passa na política, executa e devolve resultado completo | 1.962 | 58 |
| O professor, vendo só a pergunta, chega ao mesmo resultado (158 pedidos de conferência) | 1.403 | 559 |
| Sem pergunta parecida com alguma do teste (semelhança de texto de 0,85 ou mais) | 1.392 | 11 |
| Sem consulta que devolva o mesmo resultado que um gabarito do teste | **1.283** | 109 |

A maior semelhança de texto que sobrou entre uma pergunta de treino e uma de teste é 0,838.

## O que saber antes de usar

- **A meta era de 1.500 a 3.000 pares; ficaram 1.283.** A cota diária do professor não permitiu mais numa rodada.
- **O filtro de concordância cortou cerca de um terço das consultas que executavam** (559 de aproximadamente 1.680), e corta mais o que é difícil. Há 34 exemplos de função de janela contra 125 de junção com agrupamento.
- **O filtro por resultado tirou dez vezes mais pares que o filtro por texto** (109 contra 11). Sem ele, o treino teria dezenas de perguntas do teste escritas com outras palavras.
- **O professor erra.** Dois acertos iguais do professor não garantem que a consulta responde à pergunta.
- O professor recebeu o mesmo dicionário de dados que orientou quem escreveu o teste; os padrões do teste estão cobertos aqui, com outras perguntas.
- As perguntas de teste nunca foram enviadas ao professor.

## Licença

As consultas e as perguntas são sobre o *Brazilian E-Commerce Public Dataset by Olist* (CC BY-NC-SA 4.0). Estes pares são derivados dele e ficam sob a mesma licença: atribuição, uso não comercial, mesma licença para obras derivadas.

# B1 · experimento: o agente não ganha porque o dicionário já resolve?

Pré-registro escrito em 14/11/2026, **antes** de qualquer rodada deste experimento. Os resultados entram numa seção separada no fim, depois das rodadas.

## O que se observou

No conjunto de teste, com o Gemini 3.5 Flash Lite, o agente acertou 39 de 44 consultas e a linha de base (uma consulta, sem ferramentas) acertou 41 de 44. O agente não foi melhor e gastou o dobro de tokens.

## Hipótese

Nos dois modos, o prompt traz o dicionário de dados completo: colunas, significados e as armadilhas dos dados. Com isso, as ferramentas de inspeção do agente (listar, descrever, amostrar, executar) acrescentam pouco. **Se a documentação no prompt diminuir, a linha de base deve cair mais do que o agente**, porque só o agente pode ir buscar o que falta.

## Desenho

Mesmo conjunto de teste (60 perguntas, mesmo hash), mesmo modelo (`gemini-3.5-flash-lite`, raciocínio baixo, temperatura 0), mesmo comparador. Varia só o que o prompt diz sobre o banco:

| Nível | O que vai no prompt |
|---|---|
| `completo` | O dicionário de dados inteiro (é a rodada já publicada) |
| `esquema` | Só nomes das visões, colunas e tipos. Sem significados, sem valores possíveis, sem armadilhas |
| `nenhum` | Só os nomes das sete visões |

Cada nível roda nos dois modos. A medida é o acerto de execução nas 44 perguntas com SQL, pelo critério estrito já usado.

**Variação entre rodadas:** o nível `completo` é repetido mais duas vezes em cada modo. A maior diferença entre rodadas iguais é o ruído contra o qual as outras diferenças são lidas.

## Previsões, escritas antes

Seja Δ = acertos do agente − acertos da linha de base, em 44.

- Δ(`completo`) já medido: −2.
- **Prevejo Δ(`esquema`) ≥ +3.** Sem os valores possíveis (por exemplo, que a situação é `delivered` e não "entregue") e sem as armadilhas, a linha de base deve errar filtros que o agente descobre amostrando.
- **Prevejo Δ(`nenhum`) ≥ +10.** Sem colunas, a linha de base tem de adivinhar nomes; espero que ela acerte menos de 10 das 44.

## Regra de decisão

| Resultado | Leitura |
|---|---|
| Δ(`esquema`) ≥ +3 **e** maior que Δ(`completo`) por mais que o ruído medido | Hipótese sustentada: o agente só se paga quando a documentação é incompleta |
| Δ(`esquema`) entre −2 e +2, mas Δ(`nenhum`) ≥ +10 | Sustentada só no caso extremo: basta o esquema para a linha de base empatar |
| Δ(`esquema`) ≤ +2 **e** Δ(`nenhum`) < +10 | Hipótese refutada: a falta de ganho não vem do dicionário |

Qualquer que seja o resultado, ele é publicado. Nenhum prompt, comparador ou pergunta muda por causa dele.

## O que este experimento não responde

- Vale para um modelo pequeno e barato do Gemini. Um modelo mais forte pode mudar o quadro nos dois sentidos.
- O conjunto de teste foi escrito por quem conhecia o dicionário; as armadilhas das perguntas são as que o dicionário descreve. Isso favorece o nível `completo`.
- O modelo local não entra: ele falha por outro motivo (não consegue encerrar), e mais rodadas dele não diriam nada sobre esta hipótese.
- Se a cota do Gemini acabar no meio, a rodada interrompida fica registrada como incompleta e não entra na comparação.

## Resultados

*(a preencher depois das rodadas)*

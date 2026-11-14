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

### Estado em 14/11/2026: **parcial, sem conclusão**

A cota diária gratuita do modelo (500 pedidos) acabou na terceira das oito rodadas.

| Rodada | Situação |
|---|---|
| `esquema`, agente | Completa |
| `esquema`, linha de base | Completa |
| `nenhum`, agente | **Interrompida na pergunta 3 de 60.** Arquivo marcado como incompleto; não entra em nada |
| `nenhum`, linha de base | Não rodou |
| Repetições do `completo` (2 por modo) | Não rodaram |

### O que foi medido

Acerto de execução, em 44:

| Nível de documentação | Agente | Linha de base | Δ |
|---|---:|---:|---:|
| `completo` (rodada original) | 39 | 41 | −2 |
| `esquema` | 39 | 36 | **+3** |
| `nenhum` | não medido | não medido | — |

Outras medidas do nível `esquema`:

| | Agente | Linha de base |
|---|---:|---:|
| Tokens de entrada | 165.944 | 49.901 |
| Chamadas de ferramenta antes de responder, por pergunta | 1,55 | 0 |
| Sem resposta nos dados: disse que não dá | 7 / 8 | 6 / 8 |
| Ambíguas: pediu esclarecimento | 2 / 8 | 5 / 8 |
| Falhas do provedor (resposta vazia) | 0 | 2 |

### Leitura contra a regra de decisão

- **A previsão Δ(`esquema`) ≥ +3 se cumpriu no limite exato: +3.**
- **A regra pedia mais do que isso:** que a diferença para o nível `completo` fosse maior que o ruído entre rodadas iguais. O ruído **não foi medido**, porque as repetições não rodaram. Sem ele, um deslocamento de 5 perguntas em 44 pode ser só variação.
- **Portanto: não há conclusão ainda.** O que existe é uma direção compatível com a hipótese. O acerto do agente ficou igual (39 e 39), e o da linha de base caiu de 41 para 36. Era o padrão previsto: quem perde com menos documentação é quem não pode ir buscá-la.
- A previsão para o nível `nenhum` não foi testada.

### Observações, fora da regra de decisão

- **Onde a linha de base caiu** (consultas conferidas uma a uma):
  - em `t28`, `t37` e `t41` ela adivinhou o valor da situação em português (`'cancelado'`, `'entregue'`); nos dados o valor está em inglês, e o resultado veio zero ou vazio;
  - em `t21` e `t22` ela não filtrou os pedidos entregues, e por pouco não acertou (88.649 contra 88.644);
  - em `t27` ela errou a numeração dos dias da semana, o que não tem relação com a documentação.

  Cinco dos seis erros são do tipo que a hipótese apontava. Isso foi olhado depois dos resultados e não vale como evidência independente.
- **O agente também errou perguntas que acertava com o dicionário** (`t06`, `t21`, `t22`) e passou a acertar outras. Os 39 não são as mesmas 39.
- **O agente piorou nas ambíguas com menos documentação:** 2 de 8, contra 4 de 8. Com 8 perguntas, é só uma observação.
- **O agente com esquema custou menos que o agente com dicionário** (166 mil contra 271 mil tokens de entrada) e acertou o mesmo.

### O que falta para concluir

1. As duas rodadas do nível `nenhum`.
2. As quatro repetições do nível `completo`, que medem o ruído.

São cerca de 700 pedidos; com o limite gratuito de 500 por dia, cabem em dois dias. A ordem que dá conclusão mais cedo é a das repetições primeiro.

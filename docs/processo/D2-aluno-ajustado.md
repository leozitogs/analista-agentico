# D2 · o aluno depois do ajuste

Data: 15/11/2026. Ferramenta: Claude Code. Leonardo não revisou este código nem os dados de treino.

## O que foi feito, na ordem

1. Rodada piloto de geração (140 pares) e inspeção. Ela mostrou uma falha no controle de vazamento, corrigida com um filtro mais rigoroso antes de qualquer treino (adendo em [D0](D0-destilacao-plano.md)).
2. Geração grande: 2.189 pares escritos, **1.283 aprovados** ([funil](../../dados/destilacao/README.md)).
3. Treino do aluno (`Qwen/Qwen2.5-Coder-1.5B-Instruct`) com LoRA em 4 bits: 3 épocas, 1.219 exemplos de treino e 64 de validação, 32 minutos numa RTX 4050, pico de 4,5 GB.
4. Medição no conjunto de teste congelado, uma vez, com o mesmo comparador e a mesma política.

Nenhuma configuração foi escolhida olhando o teste: foi um treino só, com os valores escritos no script antes.

## Resultado no conjunto de teste

| | Aluno sem ajuste | **Aluno ajustado** | Professor, mesmo contexto | Professor, dicionário completo |
|---|---:|---:|---:|---:|
| Acerto de execução (44) | 18 | **32 (72,7%)** | 36 | 41 |
| Nível 1 (14) | 11 | **14** | 14 | 14 |
| Nível 2 (16) | 5 | **12** | 12 | 15 |
| Nível 3 (14) | 2 | **6** | 10 | 12 |
| Sem resposta nos dados: recusou (8) | 0 | **5** | 6 | 6 |
| Ambíguas: pediu esclarecimento (8) | 0 | **8** | 5 | 6 |
| Respostas que não executam (60) | 20 | **4** | 0 | 0 |

No conjunto de desenvolvimento: de 4 para 11 em 16.

Rastros: `resultados/teste-aluno-base.jsonl` e `resultados/teste-aluno-v1.jsonl`. Registro do treino: `resultados/destilacao-treino-v1.json`.

## Contra os critérios do pré-registro

| # | Critério | Meta | Medido | |
|---|---|---|---|---|
| D1 | O ajuste melhora o aluno | Intervalo de 95% da diferença pareada não cruza zero | +14 acertos; intervalo de **+7 a +21** (ganhou 15, perdeu 1) | Atingido |
| D2 | Chega perto do professor | Pelo menos 27 de 44 | **32** | Atingido |
| D3 | Saída utilizável | Pelo menos 95% | 56 de 60 = **93,3%** | **Não atingido** |
| D4 | Sem vazamento por texto | Nenhum par com semelhança de 0,85 ou mais | 11 descartados; maior semelhança restante 0,838. Mais 109 descartados pelo filtro por resultado | Atingido, com a ressalva abaixo |
| D5 | Reprodutibilidade | Dados, configuração e semente publicados; um comando refaz | Dados, script e registro do treino publicados. **Não refiz o treino para conferir que o resultado se repete** | Parcial |

Pela regra de decisão escrita antes (D1 e D2 atingidos), o modelo é para ser publicado, com o cartão dizendo o que foi medido e onde quebra. **Ele ainda não foi publicado**: isso exige a conta do Leonardo no Hugging Face.

## As previsões

- Aluno sem ajuste: previ menos de 10; deu 18. **Errada.**
- Aluno com ajuste: previ entre 24 e 32; deu 32. **Certa, no limite de cima.**
- Onde continuaria errando: previ o nível 3 e as perguntas sem resposta desenhadas como armadilha. **Certa**: 6 de 14 no nível 3, e 3 das 8 sem resposta ainda respondidas.

## Auditoria de vazamento, feita depois do resultado

Um salto de 18 para 32 pede desconfiança. Para cada uma das 15 perguntas de teste que o aluno passou a acertar, procurei a pergunta de treino mais parecida.

- **Nenhuma é a mesma pergunta.** As mais próximas são variações do mesmo molde com outro recorte: "percentual de pedidos cancelados em relação ao total **no ano de 2017**" (treino) para "percentual de pedidos cancelados em relação ao total" (teste, semelhança de 0,84); "chegaram **após** a data prevista" para "chegaram **antes** da data prevista".
- **Mas o treino tem irmãs próximas de várias perguntas do teste.** Em 15 das 44, a pergunta de treino mais parecida tem semelhança de 0,75 ou mais. O aluno não decorou respostas, mas viu os mesmos moldes.

Isso é o que o pré-registro já dizia: o resultado mede generalização **dentro deste banco e deste estilo de pergunta**. Ele não diz nada sobre outro banco, nem sobre perguntas escritas por gente que nunca viu o dicionário.

## Onde o aluno ajustado erra

- **4 consultas não executam:** duas usam coluna que não existe, uma inventa uma visão (`pessoas`), uma usa `DISTINCT` numa função que não aceita. São erros do modelo; nenhuma foi barrada indevidamente pela política.
- **6 executam e dão resultado diferente** do gabarito (`t23`, `t27`, `t30`, `t34`, `t37`, `t40`).
- **2 pedem esclarecimento onde havia resposta** (`t35`, `t36`). O aluno aprendeu a recusar e agora recusa um pouco além da conta.
- No aluno sem ajuste, 18 das 20 respostas que não executavam usavam coluna ou visão inexistente. O ajuste resolveu quase todas: é aí que está a maior parte do ganho.

## Limites

- **Uma rodada de treino, uma semente.** Não sei quanto o 32 varia com outra semente.
- **44 consultas.** O intervalo de D1 é largo (de 7 a 21), e a distância para o professor (32 contra 36) não é conclusiva.
- **A perda de validação subiu na terceira época** (0,407, 0,376, 0,402). Duas épocas talvez bastassem; não testei, porque escolher olhando o teste invalidaria a medição.
- **O conjunto de treino ficou abaixo da meta** (1.283 contra 1.500) e é desbalanceado para o fácil.
- **Nenhuma pessoa conferiu os pares de treino.**
- **Quem escreveu o teste e quem desenhou o professor é o mesmo agente de código**, com o mesmo dicionário.

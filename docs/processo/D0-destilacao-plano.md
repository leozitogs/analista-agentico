# D0 · destilar o analista num modelo pequeno: plano e pré-registro

Escrito em 14/11/2026, **antes** de gerar qualquer dado de treino e de treinar qualquer modelo. Os resultados entram em outro registro.

## A pergunta

No conjunto de teste, o Gemini 3.5 Flash Lite acertou 41 de 44 consultas com uma chamada só, e um modelo local de 4 bilhões de parâmetros, sem ajuste, acertou 4. **Um modelo pequeno o bastante para treinar e rodar numa placa de 6 GB, ajustado para este banco, recupera quanto dessa distância?**

Não é uma técnica nova. Destilação para text-to-SQL está descrita em vários trabalhos (Distill-C, SING-SQL, SQuaD-SQL), e há um benchmark em português, o AtlasSQL-BR, que ajustou um modelo de 8B. O que este registro acrescenta é uma aplicação medida com honestidade: um teste congelado antes, revisado por uma pessoa, e critérios escritos antes de treinar.

## Desenho

**Aluno.** Um modelo aberto de até 2 bilhões de parâmetros, ajustado com LoRA em 4 bits. Candidato principal: `Qwen/Qwen2.5-Coder-1.5B-Instruct` (Apache-2.0, sem cadastro para baixar). Um segundo modelo, de outra família, entra se houver tempo.

**Tarefa do aluno.** Uma chamada, sem ferramentas: recebe a pergunta e o esquema das visões (nomes, colunas e tipos, sem o dicionário completo) e devolve uma de três coisas:

- uma consulta SQL;
- `SEM_RESPOSTA: <o que falta nos dados>`;
- `ESCLARECER: <a pergunta que precisa ser feita>`.

**Professor.** O Gemini 3.5 Flash Lite, o mesmo modelo medido como linha de base, recebendo o dicionário de dados completo.

**Dados de treino.** Gerados pelo professor e filtrados sem intervenção humana:

1. O professor escreve lotes de pares (pergunta, SQL) sobre o banco, guiado por uma lista de habilidades (filtro, agregação, junção, antijunção, janela, duas etapas, datas, percentuais) e pelas armadilhas do dicionário.
2. **Filtro por execução:** o par só fica se a consulta passa na política, executa, devolve ao menos uma linha e não é truncada.
3. **Filtro por concordância:** numa segunda chamada, o professor recebe só a pergunta e escreve outra consulta. O par só fica se os dois resultados forem iguais pelo comparador do projeto. Isso corta perguntas ambíguas e consultas que não respondem à pergunta.
4. Cerca de 10% dos exemplos são perguntas sem resposta nos dados e 10% são ambíguas, também escritas pelo professor.

Meta: 1.500 a 3.000 pares depois dos filtros.

**Vazamento.** As perguntas de teste nunca entram em nenhum prompt do professor. As de desenvolvimento podem entrar como exemplo de estilo. Depois da geração, todo par de treino cuja pergunta tenha semelhança de texto de 0,85 ou mais com alguma pergunta de teste é descartado, e o registro de resultados traz a maior semelhança que sobrou e a contagem de descartes.

**Medição.** O mesmo conjunto de teste congelado (hash inalterado), o mesmo comparador, o mesmo critério estrito. Quatro linhas na tabela final:

| Configuração | Estado |
|---|---|
| Professor, uma chamada, dicionário completo | Medido: 41 / 44 |
| Professor, uma chamada, só o esquema | Medido: 36 / 44 |
| Aluno sem ajuste, só o esquema | A medir |
| Aluno com ajuste, só o esquema | A medir |

A comparação justa do aluno é com o professor **no mesmo nível de contexto** (só o esquema): 36 de 44.

## Critérios de sucesso, escritos antes

| # | Critério | Meta |
|---|---|---|
| D1 | O ajuste melhora o aluno | Diferença pareada entre o aluno ajustado e o aluno sem ajuste, nas 44 consultas, com intervalo de 95% (bootstrap pareado) que não cruza zero |
| D2 | O aluno ajustado chega perto do professor | Pelo menos 27 de 44 (75% dos 36 do professor no mesmo contexto) |
| D3 | Saída utilizável | Pelo menos 95% das respostas do aluno ajustado são uma consulta que passa na política, ou uma das duas formas de recusa |
| D4 | Sem vazamento | Nenhum par de treino com semelhança de 0,85 ou mais com pergunta de teste; a maior semelhança restante é publicada |
| D5 | Reprodutibilidade | Dados de treino, configuração e semente publicados; um comando refaz o treino |

Perguntas sem resposta e ambíguas (8 de cada) são reportadas, sem meta: com 8 itens, nenhum percentual se sustenta.

## Previsões

- Aluno sem ajuste: menos de 10 de 44. Um modelo de código de 1,5B deve escrever SQL válido, mas errar os valores em inglês da coluna de situação e as armadilhas.
- Aluno com ajuste: entre 24 e 32 de 44. Eu apostaria em D1 atingido com folga e D2 no limite.
- Onde deve continuar errando: nível 3 (janelas e duas etapas) e as perguntas sem resposta desenhadas como armadilha.

## Regra de decisão

- **D1 e D2 atingidos:** o modelo é publicado no Hugging Face com o cartão dizendo o que foi medido e onde quebra.
- **D1 atingido, D2 não:** publicado do mesmo jeito, com o título dizendo que não chegou.
- **D1 não atingido:** o resultado é publicado como negativo, sem modelo.

Em nenhum caso o conjunto de teste, o comparador ou os critérios mudam depois de ver um número.

## Limites, ditos antes

- **Um banco só.** O aluno aprende este esquema. O resultado não diz nada sobre text-to-SQL em geral.
- **O professor erra.** O filtro por concordância reduz, mas não elimina, pares errados em que o professor errou duas vezes do mesmo jeito.
- **O conjunto de teste tem 44 consultas.** D2 tem intervalo largo; a diferença entre 27 e 30 não significa nada.
- **Quem escreveu o teste conhece as armadilhas** que o professor também vai receber. O treino pode cobrir os mesmos padrões do teste sem repetir nenhuma pergunta. Isso é generalização dentro do domínio, não fora dele.
- **Os dados são da Olist, sob CC BY-NC-SA 4.0.** O modelo ajustado e os pares de treino derivam deles e saem sob a mesma licença, para uso não comercial.
- **Cota:** o professor tem 500 pedidos gratuitos por dia, divididos com o experimento do contexto, que ainda tem seis rodadas pendentes.

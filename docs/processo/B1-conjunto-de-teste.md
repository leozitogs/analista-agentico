# B1 · o conjunto de teste

Data: 14/11/2026.

## Como foi feito

1. **Rascunho:** o agente de código (Claude Code) escreveu 60 perguntas com gabarito, depois de sondar os dados reais. Cada gabarito em SQL foi executado no banco real antes de ser proposto.
2. **Revisão:** o Leonardo revisou as 60, em quatro blocos, vendo a pergunta, a resposta do gabarito e a recomendação do agente para cada uma. Ele não leu o SQL dos gabaritos.
3. **Mudanças pedidas na revisão:**
   - `t21`: a pergunta passou a dizer "comparando data e hora". A data prevista é sempre meia-noite; comparar só o dia daria outro número.
   - `t37`: de "estado com mais pedidos atrasados" para "estado com o maior percentual de atraso". Por contagem, o maior estado ganharia com quase qualquer consulta.
   - `t40`: a pergunta passou a dizer "considere os dados como estão, mesmo com 2018 incompleto", para não punir um agente que hesite diante do ano incompleto.
   - `a02`: "Qual foi o melhor mês de vendas?" virou "Qual a melhor categoria?". No mês, receita e número de pedidos davam a mesma resposta; na categoria, dão respostas diferentes.
4. **Congelamento:** o arquivo foi fechado com este hash antes de qualquer rodada, e um teste na CI quebra se ele mudar.

   `sha256 = 934c57b1a269dccf46a70f0492dd73fb13a8cee49847f21e50d71751b4e0522b`

## Composição

| Grupo | Perguntas |
|---|---:|
| Nível 1 (uma tabela) | 14 |
| Nível 2 (junções e agrupamentos) | 16 |
| Nível 3 (janelas, duas etapas, armadilhas dos dados) | 14 |
| Sem resposta nos dados | 8 |
| Ambíguas | 8 |
| **Total** | **60** |

O plano previa 60 perguntas de teste além das 20 de desenvolvimento; a proporção de perguntas sem resposta e ambíguas é a mesma do plano.

## Limites deste conjunto, ditos antes dos resultados

- **Quem escreveu as perguntas escreveu o agente.** O agente de código conhece as 60 perguntas e também escreveu o prompt do sistema e o dicionário de dados. Nenhum deles foi alterado depois do rascunho das perguntas, e o dicionário foi escrito antes delas, mas a independência não é a de um conjunto feito por terceiros.
- **O revisor humano não conferiu o SQL.** Um gabarito errado conta como erro do agente. Toda divergência em que a consulta do agente também parecer certa vai ser relatada, e não corrigida em silêncio.
- **O nível 1 é fácil.** O próprio rascunho avisava; foi mantido como piso.
- **Uma armadilha conhecida:** na `t38`, a média com o filtro (4,0866) é quase igual à média geral (4,0864). O comparador distingue, por pouco.
- **Sessenta perguntas dão intervalos largos.** Diferenças pequenas entre modos ou modelos não vão ser conclusivas.

## Regra daqui em diante

O conjunto de teste não muda. Um erro visto no teste pode virar uma pergunta nova de desenvolvimento, nunca um ajuste de prompt, de agente ou de comparador. Se o conjunto precisar mudar, o hash muda, os resultados anteriores deixam de valer, e isso fica registrado aqui.

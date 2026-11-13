# B1 · revisão independente antes de publicar

Data: 13/11/2026.

## Por que

Todo o código até aqui foi escrito por um agente de código (Claude Code) numa sequência de sessões, e os testes foram escritos pelo mesmo agente. O Leonardo pediu que o próprio agente revisasse antes de abrir o repositório. Revisar o próprio trabalho vale pouco, então a revisão foi delegada a **outro agente, em contexto separado**, que recebeu o código e a pergunta "isto pode ser público?", sem as conclusões de quem escreveu.

## Veredito do revisor

**Não, como estava.** Ele só reportou como falha o que conseguiu reproduzir.

| # | Achado | Gravidade | O que foi feito |
|---|---|---|---|
| 1 | Uma CTE declarada numa subconsulta liberava o mesmo nome no escopo de fora. Com o nome de uma visão de sistema, a consulta passava na política e lia o catálogo e as configurações do banco (inclusive caminhos locais). Linhas das tabelas brutas não chegaram a ser lidas | Bloqueava | Relações conferidas por escopo; nomes de sistema recusados sempre, também como nome de CTE |
| 2 | `LATERAL funcao(...)` contornava a regra "nenhuma função de tabela". Geradoras de linhas rodavam até o tempo limite; as de arquivo só paravam na segunda barreira | Bloqueava | `LATERAL` só com subconsulta; funções passaram de lista de proibição para lista de permissão |
| 3 | Número infinito ou muito grande no resultado derrubava a avaliação inteira, que só gravava os rastros no fim | Devia corrigir | Tratado; rastro gravado pergunta a pergunta; erro interno vira falha registrada; gabaritos conferidos antes da primeira chamada ao modelo |
| 4 | O comparador arredondava a 2 casas e aceitava como igual o resultado de uma consulta sem um filtro (8,1117 contra 8,1124) | Devia corrigir | Tolerância relativa de 1e-6; arredondamento do agente aceito só de 2 a 6 casas |
| 5 | Colunas numéricas trocadas de lugar eram julgadas iguais | Devia corrigir | Colunas do mesmo tipo não trocam de lugar |
| 6 | A chance única de corrigir números era gasta por qualquer erro cuja mensagem tivesse a palavra "números" | Melhoria | Motivo da recusa virou tipo, não texto |
| 7 | Chamada de função malformada do modelo e erros de leitura de rede escapavam sem tratamento | Melhoria | Tratados como erro do provedor |
| 8 | A documentação prometia o que o código não fazia, e o plano citava o que não devia | Bloqueava | Corrigida; limitações declaradas no README |

Cada achado de 1 a 7 virou teste de regressão. A segunda barreira (a conexão) resistiu a tudo o que o revisor tentou.

## O que a revisão ensina sobre o processo

- O registro do B0 dizia que 35 contornos tinham sido tentados e que os perigosos estavam todos recusados. Era verdade para os 35, e falso como conclusão.
- Os testes de um agente provam que o código faz o que o agente pensou. O defeito 1 estava num caso que o agente tinha testado só pela metade (nome de CTE inexistente, e não nome de CTE que coincide com algo real).
- Um revisor em contexto separado, com instrução de só reportar o que reproduzir, achou em minutos o que o autor não achou.

## O que continua sem verificação

- Ninguém humano revisou o código.
- As limitações do README (consulta cara, verificação de números) são conhecidas e não resolvidas.
- Os números de `resultados/` foram rejulgados com o comparador novo a partir dos rastros gravados, sem novas chamadas ao modelo.

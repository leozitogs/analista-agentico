# B0 · a base, sem agente

Registro de como esta etapa foi construída. Data: 13/11/2026.

## O que foi pedido

O marco B0 do `PLANO.md`: dados carregados, visões, dicionário, ferramentas e política com testes, e 20 perguntas de desenvolvimento. Aceite: a escrita no banco é impossível por construção, provado por teste (critério C4), e as consultas de gabarito rodam.

## Quem fez o quê

- **Agente de código (Claude Code):** escreveu todo o código e os testes desta etapa numa única sessão, a partir do plano.
- **Leonardo:** escreveu o plano com o agente, aprovou o projeto e pediu o início. **Ainda não revisou o código desta etapa.**

Esta etapa foi feita no Claude Code; as próximas dizem no próprio registro qual ferramenta foi usada.

## Decisões tomadas pelo agente, para revisão

| Decisão | Motivo | Revisar? |
|---|---|---|
| Política por lista de permissão de relações, e não por lista de proibição de comandos | Uma lista de proibição sempre esquece alguma coisa; `FROM 'arquivo.csv'` e o esquema bruto caem na mesma regra | Sim |
| Lista de funções proibidas por prefixo (`read_`, `duckdb_`, `pragma_`...) | Não achei forma simples de ter lista de permissão de funções sem recusar SQL legítimo | **Sim, é o ponto mais fraco da política** |
| Segunda barreira na conexão (somente leitura, sem acesso externo, configuração travada) | Se a política falhar, o banco ainda recusa | Não |
| Tempo limite por interrupção da conexão | DuckDB não tem tempo limite por instrução | Sim, sob carga real |
| Visões com nomes em português; valores de `situacao` e `forma` continuam em inglês | Traduzir valores mudaria os dados; o dicionário avisa | Sim |
| Geolocalização e tradução de categorias fora das visões | Menos superfície até uma pergunta precisar | Não |
| Comparador sem crédito parcial, tolerante a nome e ordem de coluna | Está no plano | Não |

## O que os testes pegaram

Nada de comportamento nesta etapa: os testes passaram na primeira execução (81 na primeira rodada; 109 depois dos casos de ataque). Isso pede desconfiança, e não comemoração: os testes foram escritos pelo mesmo agente que escreveu o código, na mesma sessão. O que eles provam é que o código faz o que o agente achou que devia fazer.

## Conferência no dataset real (13/11, depois do download feito pelo Leonardo)

- A carga passou sem ajuste: os nomes de coluna assumidos estavam certos.
- Os 16 gabaritos executam e devolvem resultado completo. Os valores batem com o que se conhece do dataset (nota média perto de 4,09; cerca de 8% dos pedidos entregues com atraso; cerca de 3% das pessoas com mais de um pedido).
- A sonda dos dados encontrou as armadilhas que hoje estão no dicionário (pedidos sem itens, avaliações repetidas, forma `not_defined`).
- Três perguntas eram ambíguas e foram reescritas: d11 e d13 agora dizem "todos os pedidos, em qualquer situação"; d12 passou a contar cada pedido uma vez por estado, com o SQL corrigido para isso.
- Entraram testes que rodam só quando o banco real existe (tamanho, domínios e gabaritos).

## O que não foi verificado

1. **Os 16 gabaritos ainda não tiveram leitura humana.** Executar e dar valor plausível não é estar certo. Ponto conhecido: a d15 calcula a média por item, não por pedido.
2. A CI não consegue rodar os testes dos dados reais (os dados não ficam no repositório).
3. **A licença do dataset** não foi lida na página oficial. Uma fonte secundária indica CC BY-NC-SA 4.0 (uso não comercial, mesma licença para derivados). Por isso os dados não entram no repositório.
4. **A política só tinha sido atacada pelo próprio autor.** O agente tentou 35 contornos e achou que todos os perigosos estavam recusados. Não estavam: a revisão independente do B1 achou dois que passavam (ver `B1-revisao.md`). Fica o registro de que autoavaliação de segurança não vale como evidência.
5. A CI não existia nesta etapa; foi criada no B1.

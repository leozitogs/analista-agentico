# B1 · o agente (primeira parte)

Data: 13/11/2026. Ferramenta: Claude Code. Leonardo ainda não revisou este código.

## O que foi feito

| Peça | Arquivo | O que faz |
|---|---|---|
| Provedor | `provedor.py` | Gemini pela API REST, sem SDK; e um provedor roteirizado para os testes |
| Agente | `agente.py` | Um laço: inspeciona, consulta, corrige, termina chamando `responder` com um tipo (resposta, sem_resposta, esclarecimento) |
| Verificação de números | `verificar.py` | Todo número do texto final precisa estar no resultado, na contagem de linhas ou na pergunta |
| Avaliação | `avaliar.py` | Acerto por tipo de pergunta, resumo por nível, rastro completo em JSONL |
| Linha de base | modo `direto` | O mesmo modelo, só com a ferramenta `responder`: uma consulta, sem inspecionar nem corrigir |
| Comandos | `cli.py` | `analista modelos`, `perguntar`, `avaliar` |

## Decisões, para revisão

| Decisão | Motivo | Alternativa descartada |
|---|---|---|
| API REST direta, sem SDK | Pedido e resposta ficam à vista no rastro; zero dependência nova | SDK de agentes do Google e SDK do Gemini: mais camadas entre o agente e o que se quer auditar |
| O turno do modelo volta para a API como veio | Modelos recentes anexam assinaturas às chamadas de função | Reconstruir o turno a partir dos campos lidos |
| Resposta final é uma chamada de função com tipo | Dá para medir recusa e pedido de esclarecimento sem interpretar texto | Classificar o texto final com outro modelo |
| A consulta final é executada pelo agente, não reaproveitada do modelo | O resultado oficial não depende do que o modelo diz ter visto | Confiar na última consulta exploratória |
| Número sem origem: uma chance de corrigir, depois fica marcado | Corrigir sempre esconderia o defeito; nunca corrigir desperdiça um erro barato | Bloquear a resposta |
| O modelo não tem padrão no código | Não sei qual é a linha atual de modelos; `analista modelos` lista os da sua conta | Fixar um nome que pode não existir mais |
| O dicionário de dados entra no prompt nos dois modos | A linha de base precisa do esquema; assim a comparação mede inspeção e correção, não acesso à documentação | Dar o dicionário só ao agente |

## O que os testes pegaram

- A consulta final usava o limite de 200 linhas das consultas exploratórias: qualquer gabarito maior daria erro para sempre. Ganhou limite próprio.
- O auxiliar de teste tinha um parâmetro com o mesmo nome de um argumento de ferramenta.

## Primeira chamada real e primeira rodada (13/11, depois da chave)

**O formato do pedido estava certo.** A chamada de função funcionou na primeira tentativa, e as assinaturas que o modelo anexa às chamadas voltam como previsto.

**Modelo.** O Leonardo pediu para o agente de código escolher.
- `gemini-3.8-flash` é o que a própria API recomenda, mas devolveu 503 (alta demanda) em todas as tentativas; `3.7-flash` também.
- `gemini-3.5-flash` respondeu, mas a camada gratuita limita o Flash a **20 pedidos por dia**. A mensagem de cota mostra ainda que esse nome é atendido por outro modelo (`gemini-3.6-flash`).
- **Escolha: `gemini-3.5-flash-lite`**, com raciocínio baixo. É o único que cabe na camada gratuita para rodar 20 perguntas nos dois modos. Para medir um Flash é preciso ativar cobrança; é decisão do Leonardo.

**O que a rodada real pegou, e os testes não:**

| Defeito | Correção |
|---|---|
| Abrir uma segunda conexão ao mesmo banco falhava, porque a primeira já tinha travado a configuração. O avaliador usa duas (agente e juiz) | A segunda conexão aceita a trava existente, desde que esteja no estado seguro; teste de regressão |
| Sobrecarga (503) e tempo esgotado derrubavam a pergunta | Repetição com espera crescente, até 4 tentativas |
| Cota diária esgotada era registrada como 20 erros do agente | Virou interrupção da avaliação, com as perguntas não avaliadas contadas à parte |
| Gabarito `d13` deixava janeiro sem variação, embora dezembro de 2016 exista nos dados; e o formato do mês não estava definido | Gabarito corrigido; a pergunta pede o formato AAAA-MM |
| Gabarito `d15` exigia o tempo em dias, que depende de como se conta um dia | A pergunta pede só o nome da categoria |

Os dois gabaritos foram corrigidos **depois** de ver respostas do modelo. É uso legítimo do conjunto de desenvolvimento, e é o motivo de esse conjunto não servir para medir.

Números da rodada em `resultados/README.md`.

## O que não foi verificado

1. **Nenhum modelo Flash foi medido**, só o lite.
2. **Uma rodada só**, com 20 perguntas: não há medida de variação, e a diferença entre agente e linha de base não é conclusiva.
3. **Coluna a mais conta como erro.** Decisão em aberto: manter o critério estrito do plano ou reportar também uma medida tolerante.
4. **A verificação de números** tem casos difíceis conhecidos: "1.234" é lido das duas formas (mil e pouco, ou um vírgula dois); números por extenso passam sem checagem; porcentagens calculadas pelo modelo a partir de dois valores do resultado são apontadas como sem origem, o que é o comportamento desejado mas vai gerar ruído.
5. **As 60 perguntas de teste não existem.** Quem escreve o agente não deveria escrever sozinho o conjunto que o avalia; o ideal é o Leonardo escrever ou, no mínimo, revisar uma a uma.

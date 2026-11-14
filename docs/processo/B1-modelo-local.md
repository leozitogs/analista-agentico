# B1 · segundo provedor: modelo local

Datas: 13 e 14/11/2026. Ferramenta: Claude Code. Leonardo não revisou este código.

## Por que

A camada gratuita do Gemini limita o Flash a 20 pedidos por dia, e a rodada completa do agente passa de 40. Um modelo local não tem cota: dá para repetir rodadas, medir variação e ter um segundo ponto de comparação. Não substitui o Gemini; é um segundo provedor atrás da mesma interface.

## O que havia na máquina

Quatro variantes do Qwen de 4 bilhões de parâmetros no Ollama (nenhum Llama). É o tamanho que cabe numa placa de 6 GB.

| Modelo | Chamada de função | Observação |
|---|---|---|
| `qwen3:4b-instruct` | Funciona, menos de 3 s por chamada | **Escolhido** |
| `qwen3.5:4b` | Funciona com o raciocínio ligado, bem mais lento | Com o raciocínio desligado, o servidor do Ollama caiu (estouro de pilha no processo dele) |

## Decisões, para revisão

| Decisão | Motivo | Alternativa descartada |
|---|---|---|
| A conversa continua guardada no formato do Gemini; o provedor local traduz na ida e na volta | O agente não precisa saber qual modelo está do outro lado, e os rastros ficam comparáveis | Um formato neutro próprio: mais uma camada sem ganho agora |
| Reconhecer chamada de função escrita como texto | O modelo pequeno faz isso com frequência; sem a leitura, quase toda pergunta terminava no teto de chamadas | Deixar falhar: mediria a aderência ao protocolo, não a capacidade de responder |
| A leitura só vale para o texto inteiro, ferramenta declarada e JSON válido | Texto solto com algo parecido com uma chamada não pode virar ação | Procurar a chamada no meio do texto |
| O provedor conta quantas chamadas foram lidas do texto | O relaxamento precisa ficar visível | Não contar |
| Escolha do provedor pelo prefixo `ollama:` no nome do modelo | Uma opção só na linha de comando | Outra variável de ambiente |

## O que a rodada real pegou

- A chamada final vinha como texto, de três formas: `responder({...})`, `responder {...}` e dentro de bloco de código. As três viraram teste.
- A rodada em segundo plano foi interrompida quando a sessão terminou. Como o rastro agora é gravado pergunta a pergunta (correção da revisão independente), o que já tinha sido medido não se perdeu.

## O que não foi verificado

1. Uma rodada por modo. A variação entre rodadas existe (ver `resultados/README.md`) e não foi medida.
2. O contador de chamadas lidas do texto passou a ser gravado no rastro de cada pergunta, mas **só em rodadas novas**: os arquivos de 13 e 14/11 foram gerados antes e não têm esse número.
3. A linha de base local pede esclarecimento para quase tudo. Não investiguei se é o prompt ou o modelo.
4. Só um modelo local foi medido.

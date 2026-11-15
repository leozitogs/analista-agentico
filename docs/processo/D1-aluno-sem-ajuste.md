# D1 · o aluno antes do ajuste

Data: 15/11/2026. Ferramenta: Claude Code. Leonardo não revisou este código.

## O que foi feito

- Ambiente de treino em disco separado: Python 3.12, PyTorch 2.15 com CUDA, transformers, peft e bitsandbytes. A placa (RTX 4050, 6 GB) é reconhecida.
- Caminho do aluno escrito: exportar os prompts, responder com um modelo local, julgar as saídas com o mesmo comparador e a mesma política de SQL das outras medições, e o script de treino com LoRA.
- **Medido o aluno sem ajuste** (`Qwen/Qwen2.5-Coder-1.5B-Instruct`, precisão de 16 bits, sem amostragem), com só o esquema no prompt.

## Resultado no conjunto de teste

| | Aluno sem ajuste | Professor no mesmo contexto (já medido) |
|---|---:|---:|
| Acerto de execução | **18 / 44 = 40,9%** (intervalo de 28 a 56%) | 36 / 44 |
| Nível 1 | 11 / 14 | 14 / 14 |
| Nível 2 | 5 / 16 | 12 / 16 |
| Nível 3 | 2 / 14 | 10 / 14 |
| Sem resposta nos dados: recusou | 0 / 8 | 6 / 8 |
| Ambíguas: pediu esclarecimento | 0 / 8 | 5 / 8 |
| Consulta recusada pela política ou com erro de execução | 20 de 60 | 0 |
| Memória de vídeo no pico | 3,1 GB | — |
| Tempo | 2,4 s por pergunta | — |

No conjunto de desenvolvimento: 4 de 20.

Rastro: `resultados/teste-aluno-base.jsonl`.

## A previsão estava errada

O pré-registro dizia: "aluno sem ajuste: menos de 10 de 44". Deu 18. Subestimei um modelo de código de 1,5B com o esquema à mão.

Consequências, sem mexer em nenhum critério:

- **D1 ficou mais difícil de atingir do que eu esperava.** O ajuste precisa superar 18, e não um número perto de zero.
- **D2 continua em 27 de 44.** A distância a percorrer é de 9 acertos, e não de 20.
- A outra previsão (aluno ajustado entre 24 e 32) foi escrita supondo um ponto de partida muito mais baixo. Ela fica registrada como está; não a revejo para parecer melhor.

## O que os erros mostram

- **O aluno nunca recusa.** Zero em 16 perguntas que pediam recusa ou esclarecimento: ele sempre escreve uma consulta. É o comportamento que o treino mais deve mudar, e o que D1 e D2 **não** medem, porque só olham as 44 consultas.
- **Um terço das respostas não executa** (20 de 60): consulta recusada pela política ou com erro. Não separei ainda quantas são sintaxe, quantas são coluna inexistente e quantas são função fora da lista de permissão da política. Essa separação importa: se muitas forem funções legítimas barradas pela política, parte do erro é da política, e não do modelo.
- **Comparação com o modelo local de 4B do registro anterior:** aquele acertou 4 de 44 como linha de base, mas num formato diferente (precisava encerrar com uma chamada de função estruturada e pedia esclarecimento para quase tudo). Os dois números **não são comparáveis**; não dá para dizer que o modelo de 1,5B é melhor que o de 4B.

## O que não foi feito

1. **Nenhum par de treino real foi gerado.** O gerador está testado com professor simulado; a cota do professor tinha acabado.
2. **O script de treino nunca rodou.** Não sei se o ajuste em 4 bits funciona nesta placa com esta versão das bibliotecas.
3. As 20 respostas que não executam não foram classificadas.
4. Uma rodada, sem amostragem; o resultado é determinístico para este modelo e esta precisão, mas pode mudar com 4 bits.

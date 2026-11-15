---
license: cc-by-nc-sa-4.0
base_model: Qwen/Qwen2.5-Coder-1.5B-Instruct
library_name: peft
pipeline_tag: text-generation
language:
  - pt
tags:
  - text-to-sql
  - sql
  - duckdb
  - lora
  - qlora
  - distillation
  - portuguese
---

# Analista SQL 1,5B · LoRA sobre Qwen2.5-Coder

**Um modelo pequeno que transforma perguntas de negócio em português em SQL, e que sabe dizer
quando a pergunta não tem resposta nos dados ou precisa ser esclarecida.** Destilado do Gemini
3.5 Flash Lite e treinado numa placa de vídeo de notebook (RTX 4050, 6 GB), em 32 minutos.

*English summary: a LoRA adapter for Qwen2.5-Coder-1.5B-Instruct that writes DuckDB SQL from
Brazilian Portuguese business questions over the Olist e-commerce dataset, and answers
`SEM_RESPOSTA` (not answerable) or `ESCLARECER` (needs clarification) when appropriate. On a test
set frozen before training it went from 18 to 32 of 44 correct queries (teacher: 36). One
training run, one seed, one database: read the limits below.*

![Antes e depois do ajuste no conjunto de teste](resultado.png)

## O que ele faz

Recebe o esquema do banco e uma pergunta. Devolve uma de três coisas:

| Saída | Quando |
|---|---|
| Uma consulta SQL (DuckDB, só `SELECT`) | A pergunta tem resposta nos dados |
| `SEM_RESPOSTA: <o que falta>` | Os dados não permitem responder |
| `ESCLARECER: <a pergunta a fazer>` | A pergunta admite leituras que mudam o resultado |

Exemplos reais do conjunto de teste, antes e depois do ajuste:

| Pergunta | Sem ajuste | Ajustado |
|---|---|---|
| Quantos produtos cadastrados pesam mais de 10 kg? | `... WHERE peso_g > 10` ✗ (não percebeu que o peso está em gramas) | `... WHERE peso_g > 10000` ✓ |
| Qual o percentual de pedidos cancelados em relação ao total? | `situacao = 'cancelado'` ✗ (o valor no banco é `canceled`; deu 0%) | `situacao = 'canceled'` ✓ 0,63% |
| Qual a idade média dos clientes? | `SELECT AVG(age) FROM clientes` ✗ (coluna inventada) | `SEM_RESPOSTA: O banco armazena apenas a cidade e o estado do cliente...` ✓ |
| Quais são os produtos mais populares? | Ranking por número de itens, sem perguntar ✗ | `ESCLARECER: Você quer saber o ranking baseado na quantidade de vezes que cada produto foi vendido ou pelo faturamento total gerado por ele?` ✓ |

E um erro que ficou: em "Qual a mediana do valor total pago por pedido?", que tem resposta, o
modelo ajustado pede esclarecimento. Ele aprendeu a recusar e às vezes recusa além da conta.

## Como usar

```python
import torch
from peft import PeftModel
from transformers import AutoModelForCausalLM, AutoTokenizer

BASE = "Qwen/Qwen2.5-Coder-1.5B-Instruct"
ADAPTADOR = "leozitogs/analista-olist-qwen2.5-coder-1.5b-lora"

SISTEMA = """Você escreve uma consulta SQL (DuckDB, somente SELECT) que responde à pergunta, usando só as visões abaixo. Responda com a consulta e nada mais. Se os dados não permitem responder, responda `SEM_RESPOSTA: <o que falta>`. Se a pergunta admite leituras que mudam o resultado, responda `ESCLARECER: <a pergunta que precisa ser feita>`.

Visões disponíveis, com colunas e tipos:

- avaliacoes(avaliacao_id VARCHAR, pedido_id VARCHAR, nota INTEGER, titulo VARCHAR, comentario VARCHAR, criada_em TIMESTAMP)
- clientes(cliente_id VARCHAR, pessoa_id VARCHAR, cidade VARCHAR, uf VARCHAR)
- itens_pedido(pedido_id VARCHAR, numero_item INTEGER, produto_id VARCHAR, vendedor_id VARCHAR, preco DECIMAL(12,2), frete DECIMAL(12,2))
- pagamentos(pedido_id VARCHAR, sequencia INTEGER, forma VARCHAR, parcelas INTEGER, valor DECIMAL(12,2))
- pedidos(pedido_id VARCHAR, cliente_id VARCHAR, situacao VARCHAR, comprado_em TIMESTAMP, aprovado_em TIMESTAMP, postado_em TIMESTAMP, entregue_em TIMESTAMP, entrega_prevista_em TIMESTAMP)
- produtos(produto_id VARCHAR, categoria VARCHAR, peso_g INTEGER, fotos INTEGER)
- vendedores(vendedor_id VARCHAR, cidade VARCHAR, uf VARCHAR)"""

tokenizador = AutoTokenizer.from_pretrained(BASE)
modelo = AutoModelForCausalLM.from_pretrained(BASE, dtype=torch.float16, device_map="auto")
modelo = PeftModel.from_pretrained(modelo, ADAPTADOR)


def perguntar(pergunta: str) -> str:
    mensagens = [{"role": "system", "content": SISTEMA}, {"role": "user", "content": pergunta}]
    entrada = tokenizador.apply_chat_template(
        mensagens, add_generation_prompt=True, return_tensors="pt", return_dict=True
    ).to(modelo.device)
    saida = modelo.generate(**entrada, max_new_tokens=400, do_sample=False)
    return tokenizador.decode(saida[0][entrada["input_ids"].shape[1]:], skip_special_tokens=True)


print(perguntar("Qual a idade média dos clientes?"))
# SEM_RESPOSTA: O banco armazena apenas a cidade e o estado do cliente, sem nenhuma
# informação demográfica como data de nascimento ou idade.
```

O prompt precisa ser exatamente este: foi o que o modelo viu no treino. **Execute a consulta
numa conexão somente leitura**: o modelo não garante nada sobre o SQL que escreve. O
[repositório](https://github.com/leozitogs/analista-agentico) tem a política de SQL, o banco e o
avaliador usados aqui.

## Como foi treinado

![Funil dos filtros dos pares de treino](funil.png)

1. **Professor:** o Gemini 3.5 Flash Lite escreveu 2.189 pares (pergunta e consulta, ou pergunta
   e recusa) a partir do dicionário de dados. Ele nunca viu as perguntas de teste.
2. **Filtros automáticos:** a consulta precisa passar na política e executar; o professor,
   vendo só a pergunta, precisa chegar ao mesmo resultado; e nenhum par pode se parecer com o
   teste, nem no texto, nem no resultado. Sobraram **1.283** (1.004 com SQL, 155 sem resposta,
   124 ambíguas).
3. **Treino:** LoRA sobre o modelo em 4 bits.

| | |
|---|---|
| Modelo base | `Qwen/Qwen2.5-Coder-1.5B-Instruct` |
| Método | LoRA, posto 16, alfa 32, dropout 0,05, em `q/k/v/o/gate/up/down_proj`; base em 4 bits |
| Parâmetros treinados | 18,5 milhões (cerca de 1,2% do modelo) |
| Dados | 1.219 exemplos de treino, 64 de validação |
| Épocas, lote efetivo, taxa | 3 · 8 · 2e-4 · semente 7 |
| Hardware | 1 RTX 4050 Laptop (6 GB), pico de 4,5 GB, 32 minutos |
| Perda de validação por época | 0,407 · 0,376 · 0,402 |

## Avaliação

60 perguntas escritas e congeladas por hash **antes** do treino: 44 com SQL de gabarito em três
níveis de dificuldade, 8 sem resposta nos dados e 8 ambíguas. A consulta conta como certa só se
o resultado for igual ao do gabarito, sem crédito parcial. Uma rodada, temperatura 0.

| | Sem ajuste | **Ajustado** | Professor, mesmo prompt |
|---|---:|---:|---:|
| Consultas certas (44) | 18 | **32 (72,7%)** | 36 |
| Nível 1, uma tabela (14) | 11 | **14** | 14 |
| Nível 2, junções e agrupamentos (16) | 5 | **12** | 12 |
| Nível 3, janelas e armadilhas (14) | 2 | **6** | 10 |
| Disse que os dados não respondem (8) | 0 | **5** | 6 |
| Pediu esclarecimento na ambígua (8) | 0 | **8** | 5 |
| Consultas que nem executam (60) | 20 | **4** | 0 |

Diferença pareada do ajuste: +14 consultas certas, intervalo de 95% de +7 a +21 (bootstrap); o
modelo ganhou 15 perguntas e perdeu 1. Os critérios de sucesso foram escritos antes do treino
([pré-registro](https://github.com/leozitogs/analista-agentico/blob/main/docs/processo/D0-destilacao-plano.md));
três foram atingidos, um não (saídas utilizáveis: 93,3% contra a meta de 95%) e um está parcial
(o treino não foi repetido).

## Limites

- **Um banco só.** Treino e teste são sobre o mesmo dataset e o mesmo estilo de pergunta. Nada
  aqui diz como ele se sai em outro banco ou com outro esquema.
- **Moldes parecidos.** Nenhuma pergunta do teste está no treino, mas em 15 das 44 há uma
  pergunta de treino do mesmo molde, com outro recorte. O resultado mede generalização dentro
  deste banco, não fora dele ([auditoria](https://github.com/leozitogs/analista-agentico/blob/main/docs/processo/D2-aluno-ajustado.md)).
- **Um treino, uma semente.** Não sei quanto o 32 varia; 44 perguntas dão intervalos largos, e a
  distância para o professor (32 contra 36) não é conclusiva.
- **Ninguém conferiu os pares de treino à mão.** O professor erra, e os filtros não pegam tudo.
- **Problemas mais difíceis continuam difíceis:** 6 de 14 no nível 3.
- **Não é para produção.** É um experimento de destilação, publicado com o processo inteiro.

## Licença

Os pares de treino derivam do *Brazilian E-Commerce Public Dataset by Olist*
([Kaggle](https://www.kaggle.com/datasets/olistbr/brazilian-ecommerce)), publicado sob
[CC BY-NC-SA 4.0](https://creativecommons.org/licenses/by-nc-sa/4.0/). Por cautela, este
adaptador segue a mesma licença: atribuição, uso não comercial, mesma licença para derivados.
O modelo base, `Qwen2.5-Coder-1.5B-Instruct`, é Apache-2.0. O código do projeto é Apache-2.0.

## Autor

Leonardo Gonçalves Sobral · [GitHub](https://github.com/leozitogs) ·
[LinkedIn](https://www.linkedin.com/in/leonardogsobral). Construído com agentes de código; o
registro de cada etapa está em
[`docs/processo/`](https://github.com/leozitogs/analista-agentico/tree/main/docs/processo).

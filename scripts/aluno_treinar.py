"""Ajuste fino do aluno com LoRA. Roda no ambiente de treino (PyTorch com CUDA).

Entrada: JSONL de `analista exportar-treino` ({"sistema", "usuario", "alvo"}).
Saída:   pasta com o adaptador LoRA e um `treino.json` com tudo o que é preciso para
         refazer a rodada (argumentos, semente, perdas por época, versões).

A perda só conta sobre o alvo: os tokens do prompt ficam mascarados.

Uso:
    python scripts/aluno_treinar.py MODELO treino.jsonl PASTA_DE_SAIDA [--epocas 3]
"""

from __future__ import annotations

import argparse
import json
import math
import random
import time
from pathlib import Path

import torch
from peft import LoraConfig, get_peft_model, prepare_model_for_kbit_training
from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig

MODULOS = ["q_proj", "k_proj", "v_proj", "o_proj", "gate_proj", "up_proj", "down_proj"]


def tokenizar(tokenizador, exemplo: dict, maximo: int) -> dict | None:
    mensagens = [{"role": "system", "content": exemplo["sistema"]},
                 {"role": "user", "content": exemplo["usuario"]}]
    prompt = tokenizador.apply_chat_template(mensagens, add_generation_prompt=True, tokenize=False)
    ids_prompt = tokenizador(prompt, add_special_tokens=False)["input_ids"]
    ids_alvo = tokenizador(exemplo["alvo"], add_special_tokens=False)["input_ids"]
    ids_alvo.append(tokenizador.eos_token_id)
    if len(ids_prompt) + len(ids_alvo) > maximo:
        return None  # exemplo longo demais é descartado e contado, não truncado
    return {"input_ids": ids_prompt + ids_alvo, "labels": [-100] * len(ids_prompt) + ids_alvo}


def lotes(exemplos: list[dict], tamanho: int, pad: int, dispositivo):
    for inicio in range(0, len(exemplos), tamanho):
        grupo = exemplos[inicio:inicio + tamanho]
        largura = max(len(e["input_ids"]) for e in grupo)
        ids = torch.full((len(grupo), largura), pad, dtype=torch.long)
        rotulos = torch.full((len(grupo), largura), -100, dtype=torch.long)
        mascara = torch.zeros((len(grupo), largura), dtype=torch.long)
        for linha, e in enumerate(grupo):
            n = len(e["input_ids"])
            ids[linha, :n] = torch.tensor(e["input_ids"])
            rotulos[linha, :n] = torch.tensor(e["labels"])
            mascara[linha, :n] = 1
        yield ids.to(dispositivo), mascara.to(dispositivo), rotulos.to(dispositivo)


@torch.no_grad()
def perda_media(modelo, exemplos, tamanho, pad) -> float:
    modelo.eval()
    total, n = 0.0, 0
    for ids, mascara, rotulos in lotes(exemplos, tamanho, pad, modelo.device):
        total += modelo(input_ids=ids, attention_mask=mascara, labels=rotulos).loss.item()
        n += 1
    modelo.train()
    return total / max(n, 1)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("modelo")
    parser.add_argument("treino", type=Path)
    parser.add_argument("saida", type=Path)
    parser.add_argument("--epocas", type=int, default=3)
    parser.add_argument("--lote", type=int, default=4)
    parser.add_argument("--acumular", type=int, default=2)
    parser.add_argument("--taxa", type=float, default=2e-4)
    parser.add_argument("--posto", type=int, default=16)
    parser.add_argument("--maximo-de-tokens", type=int, default=1024)
    parser.add_argument("--validacao", type=float, default=0.05)
    parser.add_argument("--semente", type=int, default=7)
    parser.add_argument("--sem-4-bits", action="store_true")
    args = parser.parse_args()

    random.seed(args.semente)
    torch.manual_seed(args.semente)
    tokenizador = AutoTokenizer.from_pretrained(args.modelo)
    if tokenizador.pad_token_id is None:
        tokenizador.pad_token = tokenizador.eos_token

    brutos = [json.loads(x) for x in args.treino.read_text("utf-8").splitlines() if x.strip()]
    exemplos = [t for t in (tokenizar(tokenizador, e, args.maximo_de_tokens) for e in brutos) if t]
    descartados = len(brutos) - len(exemplos)
    random.shuffle(exemplos)
    corte = max(1, int(len(exemplos) * args.validacao))
    de_validacao, de_treino = exemplos[:corte], exemplos[corte:]

    if args.sem_4_bits:
        modelo = AutoModelForCausalLM.from_pretrained(args.modelo, dtype=torch.float16,
                                                      device_map="cuda")
    else:
        quantizacao = BitsAndBytesConfig(
            load_in_4bit=True, bnb_4bit_quant_type="nf4", bnb_4bit_use_double_quant=True,
            bnb_4bit_compute_dtype=torch.float16,
        )
        modelo = AutoModelForCausalLM.from_pretrained(args.modelo, quantization_config=quantizacao,
                                                      device_map="cuda")
        modelo = prepare_model_for_kbit_training(modelo)
    modelo = get_peft_model(modelo, LoraConfig(
        r=args.posto, lora_alpha=2 * args.posto, lora_dropout=0.05, target_modules=MODULOS,
        task_type="CAUSAL_LM",
    ))
    treinaveis = sum(p.numel() for p in modelo.parameters() if p.requires_grad)

    pesos = [p for p in modelo.parameters() if p.requires_grad]
    otimizador = torch.optim.AdamW(pesos, lr=args.taxa)
    passos_totais = math.ceil(len(de_treino) / (args.lote * args.acumular)) * args.epocas
    agenda = torch.optim.lr_scheduler.CosineAnnealingLR(otimizador, T_max=max(passos_totais, 1))
    historico, inicio = [], time.monotonic()
    modelo.train()
    for epoca in range(1, args.epocas + 1):
        random.shuffle(de_treino)
        soma, n = 0.0, 0
        otimizador.zero_grad()
        pad = tokenizador.pad_token_id
        for passo, (ids, mascara, rotulos) in enumerate(
            lotes(de_treino, args.lote, pad, modelo.device), start=1
        ):
            with torch.autocast("cuda", dtype=torch.float16):
                perda = modelo(input_ids=ids, attention_mask=mascara, labels=rotulos).loss
            (perda / args.acumular).backward()
            soma, n = soma + perda.item(), n + 1
            if passo % args.acumular == 0:
                torch.nn.utils.clip_grad_norm_(modelo.parameters(), 1.0)
                otimizador.step()
                agenda.step()
                otimizador.zero_grad()
        validacao = perda_media(modelo, de_validacao, args.lote, tokenizador.pad_token_id)
        historico.append({"epoca": epoca, "perda_treino": round(soma / max(n, 1), 4),
                          "perda_validacao": round(validacao, 4)})
        print(historico[-1], flush=True)

    args.saida.mkdir(parents=True, exist_ok=True)
    modelo.save_pretrained(str(args.saida))
    registro = {
        "modelo_base": args.modelo, "argumentos": {k: str(v) for k, v in vars(args).items()},
        "exemplos_de_treino": len(de_treino), "exemplos_de_validacao": len(de_validacao),
        "descartados_por_tamanho": descartados, "parametros_treinaveis": treinaveis,
        "historico": historico, "minutos": round((time.monotonic() - inicio) / 60, 1),
        "memoria_de_video_no_pico_gb": round(torch.cuda.max_memory_allocated() / 1e9, 1),
        "torch": torch.__version__,
    }
    (args.saida / "treino.json").write_text(json.dumps(registro, ensure_ascii=False, indent=2),
                                            encoding="utf-8")
    print(json.dumps(registro, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

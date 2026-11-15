"""Roda um modelo aluno (Hugging Face, local) sobre um arquivo de prompts.

Independente do pacote `analista`: roda no ambiente de treino, que tem PyTorch.
Entrada: JSONL de `analista exportar-prompts` ({"id", "sistema", "usuario"}).
Saída:   JSONL com {"id", "saida"}, para `analista avaliar-aluno`.

Uso:
    python scripts/aluno_responder.py MODELO prompts.jsonl saidas.jsonl [--adaptador PASTA]
"""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

import torch
from transformers import AutoModelForCausalLM, AutoTokenizer


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("modelo")
    parser.add_argument("prompts", type=Path)
    parser.add_argument("saidas", type=Path)
    parser.add_argument("--adaptador", type=Path, default=None, help="pasta de um adaptador LoRA")
    parser.add_argument("--max-tokens", type=int, default=400)
    args = parser.parse_args()

    tokenizador = AutoTokenizer.from_pretrained(args.modelo)
    modelo = AutoModelForCausalLM.from_pretrained(
        args.modelo, dtype=torch.float16, device_map="cuda"
    )
    if args.adaptador:
        from peft import PeftModel

        modelo = PeftModel.from_pretrained(modelo, str(args.adaptador))
    modelo.eval()

    linhas = [json.loads(x) for x in args.prompts.read_text("utf-8").splitlines() if x.strip()]
    args.saidas.parent.mkdir(parents=True, exist_ok=True)
    inicio = time.monotonic()
    with args.saidas.open("w", encoding="utf-8", newline="\n") as arquivo:
        for linha in linhas:
            mensagens = [{"role": "system", "content": linha["sistema"]},
                         {"role": "user", "content": linha["usuario"]}]
            entrada = tokenizador.apply_chat_template(
                mensagens, add_generation_prompt=True, return_tensors="pt", return_dict=True
            ).to(modelo.device)
            with torch.no_grad():
                gerado = modelo.generate(
                    **entrada, max_new_tokens=args.max_tokens, do_sample=False,
                    pad_token_id=tokenizador.eos_token_id,
                )
            texto = tokenizador.decode(
                gerado[0][entrada["input_ids"].shape[1]:], skip_special_tokens=True
            )
            arquivo.write(json.dumps({"id": linha["id"], "saida": texto.strip()},
                                     ensure_ascii=False) + "\n")
            arquivo.flush()
    print(f"{len(linhas)} respostas em {time.monotonic() - inicio:.0f} s; "
          f"memória de vídeo no pico: {torch.cuda.max_memory_allocated() / 1e9:.1f} GB")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

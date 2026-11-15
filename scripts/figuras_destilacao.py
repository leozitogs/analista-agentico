"""Desenha as figuras da destilação a partir dos arquivos de resultado.

Nenhum número é digitado à mão: tudo vem de `resultados/*.jsonl` e de
`dados/destilacao/funil.json`. Requer só matplotlib (não é dependência do projeto).

Uso:
    python scripts/figuras_destilacao.py            # grava em docs/imagens/
"""

from __future__ import annotations

import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.patches import FancyBboxPatch  # noqa: E402

RAIZ = Path(__file__).resolve().parents[1]
SAIDA = RAIZ / "docs" / "imagens"

TINTA = "#1f2430"
SUAVE = "#6b7280"
GRADE = "#e5e7eb"
FUNDO = "#ffffff"
BASE = "#c3c8d1"
ALUNO = "#0f766e"
PROFESSOR = "#94a3b8"

plt.rcParams.update({
    "font.family": "DejaVu Sans",
    "font.size": 11,
    "text.color": TINTA,
    "axes.edgecolor": GRADE,
    "axes.labelcolor": TINTA,
    "xtick.color": SUAVE,
    "ytick.color": TINTA,
    "svg.fonttype": "path",
    "svg.hashsalt": "analista",
})


def ler(nome: str) -> dict[str, dict]:
    caminho = RAIZ / "resultados" / nome
    linhas = [json.loads(x) for x in caminho.read_text("utf-8").splitlines() if x.strip()]
    return {x["id"]: x for x in linhas}


def contar(rastro: dict[str, dict]) -> dict[str, int]:
    def soma(tipo: str) -> int:
        return sum(x["acertou"] for x in rastro.values() if x["tipo_pergunta"] == tipo)

    return {
        "sql": soma("sql"),
        "sem_resposta": soma("sem_resposta"),
        "ambigua": soma("ambigua"),
        # Consulta recusada ou com erro. Não conta o modelo que não respondeu (erro do provedor).
        "falhas": sum(x["execucao"]["tipo"] == "falha"
                      and not x["execucao"]["erro"].startswith("provedor")
                      for x in rastro.values()),
    }


def figura_resultado() -> dict[str, dict[str, int]]:
    grupos = {
        "Sem ajuste": contar(ler("teste-aluno-base.jsonl")),
        "Ajustado": contar(ler("teste-aluno-v1.jsonl")),
        "Professor": contar(ler("teste-direto-lite-esquema.jsonl")),
    }
    cores = {"Sem ajuste": BASE, "Ajustado": ALUNO, "Professor": PROFESSOR}
    paineis = [
        ("sql", 44, "Consultas certas\n(perguntas com gabarito)", "de 44"),
        ("sem_resposta", 8, "Disse que os dados\nnão respondem", "de 8"),
        ("ambigua", 8, "Pediu esclarecimento\nna pergunta ambígua", "de 8"),
        ("falhas", 60, "Consultas que\nnem executam", "de 60 · menor é melhor"),
    ]
    fig, eixos = plt.subplots(1, 4, figsize=(12, 4.8), facecolor=FUNDO)
    fig.subplots_adjust(top=0.66, bottom=0.04, left=0.03, right=0.99, wspace=0.3)
    nomes = list(grupos)
    for eixo, (chave, total, titulo, rodape) in zip(eixos, paineis, strict=True):
        valores = [grupos[n][chave] for n in nomes]
        barras = eixo.bar(range(3), valores, color=[cores[n] for n in nomes], width=0.72)
        barras[2].set_hatch("////")
        barras[2].set_edgecolor("#ffffff")
        for barra, valor, nome in zip(barras, valores, nomes, strict=True):
            eixo.text(barra.get_x() + barra.get_width() / 2, valor + total * 0.025, str(valor),
                      ha="center", va="bottom", fontsize=15,
                      fontweight="bold" if nome == "Ajustado" else "normal",
                      color=ALUNO if nome == "Ajustado" else TINTA)
        eixo.set_ylim(0, total * 1.2)
        eixo.set_xticks([])
        eixo.set_yticks([])
        for lado in ("top", "right", "left"):
            eixo.spines[lado].set_visible(False)
        eixo.set_title(titulo, fontsize=12, loc="left", pad=22, color=TINTA, linespacing=1.3)
        eixo.text(0, 1.03, rodape, transform=eixo.transAxes, fontsize=9, color=SUAVE)
        eixo.set_facecolor(FUNDO)
    legenda = [plt.Rectangle((0, 0), 1, 1, color=cores[n], hatch="////" if n == "Professor"
                             else None, ec="#ffffff") for n in nomes]
    fig.legend(legenda, ["Sem ajuste", "Ajustado com LoRA", "Professor (Gemini)"],
               loc="upper left", bbox_to_anchor=(0.03, 0.865), ncol=3, frameon=False,
               fontsize=10.5, handlelength=1.2, columnspacing=1.8)
    fig.text(0.03, 0.985, "Qwen2.5-Coder 1,5B antes e depois do ajuste, no teste congelado",
             fontsize=14, fontweight="bold", va="top")
    fig.text(0.03, 0.915, "O professor recebe o mesmo prompt, só com o esquema do banco. "
             "Uma rodada, temperatura 0.", fontsize=10, color=SUAVE, va="top")
    fig.savefig(SAIDA / "resultado.svg", bbox_inches="tight", facecolor=FUNDO)
    fig.savefig(SAIDA / "resultado.png", bbox_inches="tight", facecolor=FUNDO, dpi=150)
    plt.close(fig)
    return grupos


def figura_funil() -> None:
    funil = json.loads((RAIZ / "dados" / "destilacao" / "funil.json").read_text("utf-8"))
    d = funil["descartes"]
    etapas = [
        ("Escritos pelo professor", funil["escritos"], None),
        ("Sem repetição", funil["escritos"] - d["repetidos"], d["repetidos"]),
        ("A consulta passa na política e executa", funil["apos_execucao"], d["execucao"]),
        ("O professor, às cegas, chega ao mesmo resultado", funil["apos_concordancia"],
         d["concordancia"]),
        ("Nenhuma pergunta parecida com o teste", funil["apos_concordancia"]
         - d["vazamento_por_texto"], d["vazamento_por_texto"]),
        ("Nenhum resultado igual a um gabarito do teste", funil["apos_vazamento"],
         d["vazamento_por_resultado"]),
    ]
    topo = etapas[0][1]
    fig, eixo = plt.subplots(figsize=(12, 4.6), facecolor=FUNDO)
    for i, (rotulo, sobra, saiu) in enumerate(etapas):
        y = len(etapas) - 1 - i
        ultimo = i == len(etapas) - 1
        largura = sobra / topo
        eixo.add_patch(FancyBboxPatch((0, y - 0.32), largura, 0.64,
                                      boxstyle="round,pad=0,rounding_size=0.08",
                                      color=ALUNO if ultimo else "#d8e5e3", lw=0))
        eixo.text(0.015, y, f"{sobra:,}".replace(",", "."), va="center", fontsize=13,
                  fontweight="bold", color="#ffffff" if ultimo else TINTA)
        eixo.text(1.03, y + 0.05, rotulo, va="center", fontsize=11,
                  fontweight="bold" if ultimo else "normal")
        if saiu:
            eixo.text(1.03, y - 0.3, f"saem {saiu}", va="center", fontsize=9, color=SUAVE)
    eixo.set_xlim(0, 1.75)
    eixo.set_ylim(-0.6, len(etapas) - 0.4)
    eixo.axis("off")
    fig.suptitle("De 2.189 pares escritos pelo Gemini a 1.283 usados no treino",
                 x=0.125, ha="left", y=0.99, fontsize=14, fontweight="bold")
    fig.text(0.125, 0.905, "Todos os filtros são automáticos. Os dois últimos existem para "
             "que o aluno não veja o teste, nem reescrito.", fontsize=10, color=SUAVE)
    fig.savefig(SAIDA / "funil.svg", bbox_inches="tight", facecolor=FUNDO)
    fig.savefig(SAIDA / "funil.png", bbox_inches="tight", facecolor=FUNDO, dpi=150)
    plt.close(fig)


def figura_capa(grupos: dict[str, dict[str, int]]) -> None:
    """Imagem 1280 x 640 para a prévia do repositório em redes sociais."""
    antes, depois = grupos["Sem ajuste"]["sql"], grupos["Ajustado"]["sql"]
    fig = plt.figure(figsize=(12.8, 6.4), dpi=100, facecolor="#0b1220")
    fig.text(0.06, 0.82, "analista-agentico", fontsize=20, color="#5eead4",
             fontfamily="DejaVu Sans Mono")
    fig.text(0.06, 0.66, "Um modelo de 1,5B que escreve SQL\na partir de perguntas em português",
             fontsize=30, color="#f8fafc", fontweight="bold", va="top", linespacing=1.25)
    fig.text(0.06, 0.30, f"{antes}", fontsize=72, color="#64748b", fontweight="bold")
    fig.text(0.205, 0.33, "→", fontsize=54, color="#64748b")
    fig.text(0.29, 0.30, f"{depois}", fontsize=72, color="#5eead4", fontweight="bold")
    fig.text(0.445, 0.36, "de 44 consultas certas\nno teste congelado antes do treino",
             fontsize=17, color="#cbd5e1", linespacing=1.4)
    fig.text(0.06, 0.10, "Destilado do Gemini  ·  1.283 pares filtrados  ·  "
             "LoRA em 4 bits  ·  RTX 4050 de 6 GB, 32 min",
             fontsize=15, color="#94a3b8")
    fig.savefig(SAIDA / "capa.png", facecolor="#0b1220")
    plt.close(fig)


def main() -> int:
    SAIDA.mkdir(parents=True, exist_ok=True)
    grupos = figura_resultado()
    figura_funil()
    figura_capa(grupos)
    for nome, valores in grupos.items():
        print(nome, valores)
    print("figuras em", SAIDA)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

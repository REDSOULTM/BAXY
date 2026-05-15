"""Genera todos los graficos PNG para la documentacion.

Lee los JSON crudos de results/ y harness_carter540/results/ y produce
graficos comparativos en documentacion/graficos/.
"""
from __future__ import annotations
import json
import os
from pathlib import Path
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

ROOT = Path(__file__).resolve().parent.parent
DOC = ROOT / "documentacion"
GRA = DOC / "graficos"
GRA.mkdir(parents=True, exist_ok=True)
RESULTS_F2 = ROOT / "results"
RESULTS_F3 = ROOT / "harness_carter540" / "results"

# Estilo unificado
plt.rcParams.update({
    "figure.dpi": 110,
    "savefig.dpi": 130,
    "savefig.bbox": "tight",
    "axes.spines.top": False,
    "axes.spines.right": False,
    "font.size": 10,
    "axes.titlesize": 12,
    "axes.labelsize": 10,
    "legend.fontsize": 9,
})

COLOR_GEMMA = "#1976D2"
COLOR_QWEN = "#9C27B0"
COLOR_OK = "#2E7D32"
COLOR_WARN = "#F57F17"
COLOR_FAIL = "#C62828"
COLOR_NEUTRAL = "#546E7A"


# ============================================================================
# 1. FASE 2 — 60 tests por modelo (22 cuantizaciones)
# ============================================================================

def chart_fase2_models():
    summary = json.loads((RESULTS_F2 / "summary.json").read_text(encoding="utf-8"))
    rows = sorted(summary, key=lambda s: -s["total"])
    names = [r["model"] for r in rows]
    totals = [r["total"] for r in rows]

    # color: verde si >=85% del max(60), amarillo entre 50-85%, rojo <50%
    colors = []
    for t in totals:
        pct = t / 60 * 100
        if pct >= 85: colors.append(COLOR_OK)
        elif pct >= 50: colors.append(COLOR_WARN)
        else: colors.append(COLOR_FAIL)

    fig, ax = plt.subplots(figsize=(11, 9))
    y = np.arange(len(names))
    ax.barh(y, totals, color=colors, edgecolor="white")
    ax.set_yticks(y)
    ax.set_yticklabels(names, fontsize=8)
    ax.invert_yaxis()
    ax.set_xlabel("PASS / 60 tests")
    ax.set_xlim(0, 60)
    ax.set_title("Fase 2: 22 cuantizaciones de Gemma 4 sobre 60 tests del Contrato")
    for i, t in enumerate(totals):
        pct = t / 60 * 100
        ax.text(t + 0.5, i, f"{t}/60 ({pct:.1f}%)", va="center", fontsize=8)
    ax.axvline(60 * 0.85, color="grey", linestyle="--", linewidth=0.8, alpha=0.5)
    ax.text(60 * 0.85, -0.5, "85% (corte contrato)", fontsize=7, color="grey", ha="center")
    plt.savefig(GRA / "01_fase2_22_modelos.png")
    plt.close()
    print("OK 01_fase2_22_modelos.png")


def chart_fase2_top_winners():
    summary = json.loads((RESULTS_F2 / "summary.json").read_text(encoding="utf-8"))
    top = sorted(summary, key=lambda s: -s["total"])[:8]
    names = [r["model"] for r in top]
    a_scores = [r["A"][0] for r in top]
    b_scores = [r["B"][0] for r in top]
    c_scores = [r["C"][0] for r in top]
    a_max = top[0]["A"][1]; b_max = top[0]["B"][1]; c_max = top[0]["C"][1]

    fig, ax = plt.subplots(figsize=(11, 6))
    x = np.arange(len(names))
    w = 0.27
    ax.bar(x - w, a_scores, w, label=f"Bloque A /{a_max} (cobertura patrones)", color=COLOR_GEMMA)
    ax.bar(x, b_scores, w, label=f"Bloque B /{b_max} (cids reales Carter)", color=COLOR_OK)
    ax.bar(x + w, c_scores, w, label=f"Bloque C /{c_max} (estres latencia)", color=COLOR_WARN)
    ax.set_xticks(x)
    ax.set_xticklabels(names, rotation=30, ha="right", fontsize=8)
    ax.set_ylabel("PASS por bloque")
    ax.set_title("Top 8 modelos Fase 2 — desglose por bloque")
    ax.legend(loc="lower right")
    ax.grid(axis="y", alpha=0.3)
    plt.savefig(GRA / "02_fase2_top8_desglose.png")
    plt.close()
    print("OK 02_fase2_top8_desglose.png")


# ============================================================================
# 2. VRAM medida por modelo (nvidia-smi)
# ============================================================================

def chart_vram():
    vram_csv = RESULTS_F2 / "vram_log.csv"
    if not vram_csv.exists():
        print("SKIP vram chart - csv missing"); return
    rows = []
    text = vram_csv.read_text(encoding="utf-8-sig").strip()
    for ln in text.splitlines():
        parts = [p.strip() for p in ln.split(",")]
        if len(parts) < 7:
            continue
        try:
            # Format: name,vram_idle_mib,XXXX,vram_loaded_mib,YYYY,vram_delta_mib,ZZZZ
            name = parts[0]
            loaded = int(parts[4])
            delta = int(parts[6])
            rows.append((name, loaded, delta))
        except (ValueError, IndexError):
            continue
    if not rows:
        print("SKIP vram chart - no rows parsed"); return
    rows.sort(key=lambda r: r[1])
    names = [r[0] for r in rows]
    loaded = [r[1] / 1024 for r in rows]  # MiB -> GiB
    delta = [r[2] / 1024 for r in rows]

    fig, ax = plt.subplots(figsize=(11, 9))
    y = np.arange(len(names))
    ax.barh(y, loaded, color=[COLOR_OK if v <= 8 else COLOR_WARN if v <= 14 else COLOR_FAIL for v in loaded],
            edgecolor="white", label="VRAM total cargado")
    ax.barh(y, delta, color="white", alpha=0.6, edgecolor="grey", linewidth=0.5,
            label="Delta del modelo (sin idle)")
    ax.set_yticks(y)
    ax.set_yticklabels(names, fontsize=8)
    ax.invert_yaxis()
    ax.set_xlabel("VRAM (GB)")
    ax.set_title("VRAM real medida con nvidia-smi (modelo + mmproj + KV)")
    for i, v in enumerate(loaded):
        ax.text(v + 0.1, i, f"{v:.2f} GB", va="center", fontsize=8)
    ax.axvline(6, color="green", linestyle=":", linewidth=1, alpha=0.6, label="6 GB cards")
    ax.axvline(8, color="orange", linestyle=":", linewidth=1, alpha=0.6, label="8 GB cards")
    ax.axvline(16, color="red", linestyle=":", linewidth=1, alpha=0.6, label="16 GB tope NVIDIA mid")
    ax.set_xlim(0, max(loaded) + 2)
    ax.legend(loc="lower right")
    plt.savefig(GRA / "03_vram_por_modelo.png")
    plt.close()
    print("OK 03_vram_por_modelo.png")


# ============================================================================
# 3. Comparación Q6_K vs qwen3:4b (Fase 2)
# ============================================================================

def chart_gemma_vs_qwen_fase2():
    summary = json.loads((RESULTS_F2 / "summary.json").read_text(encoding="utf-8"))
    gemma_top = next((r for r in summary if r["model"] == "E4B-Q6_K"), None)
    qwen = next((r for r in summary if "qwen" in r["model"].lower()), None)
    if not gemma_top or not qwen:
        print("SKIP gemma vs qwen"); return

    # Patrones comunes
    common = sorted(set(gemma_top["patterns"].keys()) & set(qwen["patterns"].keys()))
    g_pass = [gemma_top["patterns"][p][0] / max(gemma_top["patterns"][p][1], 1) * 100 for p in common]
    q_pass = [qwen["patterns"][p][0] / max(qwen["patterns"][p][1], 1) * 100 for p in common]

    fig, ax = plt.subplots(figsize=(13, 6))
    x = np.arange(len(common))
    w = 0.4
    ax.bar(x - w / 2, q_pass, w, label="qwen3:4b (baseline Carter actual)", color=COLOR_QWEN)
    ax.bar(x + w / 2, g_pass, w, label="Gemma 4 E4B-Q6_K (ganador Fase 2)", color=COLOR_GEMMA)
    ax.set_xticks(x)
    ax.set_xticklabels(common, rotation=40, ha="right", fontsize=8)
    ax.set_ylabel("% PASS por patron")
    ax.set_ylim(0, 110)
    ax.set_title("Gemma 4 E4B-Q6_K vs qwen3:4b por patron del Contrato (Fase 2)")
    ax.legend()
    ax.grid(axis="y", alpha=0.3)
    plt.savefig(GRA / "04_gemma_vs_qwen_patrones.png")
    plt.close()
    print("OK 04_gemma_vs_qwen_patrones.png")


# ============================================================================
# 4. Latencias por categoria (Q6_K Fase 2 vs Carter 540)
# ============================================================================

def chart_latencia_por_categoria_540():
    f = RESULTS_F3 / "full540_v14_Q6_K_FULL.json"
    if not f.exists():
        print("SKIP latencia 540"); return
    d = json.loads(f.read_text(encoding="utf-8"))
    by_cat = {}
    for r in d["results"]:
        cat = r["category"]
        lat = r.get("latency_ms", 0) / 1000.0
        if lat <= 0: continue
        by_cat.setdefault(cat, []).append(lat)

    cats = sorted(by_cat.keys())
    p50 = [np.percentile(by_cat[c], 50) for c in cats]
    p90 = [np.percentile(by_cat[c], 90) for c in cats]
    p99 = [np.percentile(by_cat[c], 99) for c in cats]

    fig, ax = plt.subplots(figsize=(13, 6))
    x = np.arange(len(cats))
    w = 0.27
    ax.bar(x - w, p50, w, label="p50 (mediana)", color=COLOR_OK)
    ax.bar(x, p90, w, label="p90", color=COLOR_WARN)
    ax.bar(x + w, p99, w, label="p99 (peor 1%)", color=COLOR_FAIL)
    ax.set_xticks(x)
    ax.set_xticklabels([f"C{c:02d}" for c in cats])
    ax.set_ylabel("Latencia (segundos)")
    ax.set_title("Latencias Carter 540 — E4B-Q6_K v14 (CUDA RTX 4060 Ti)")
    ax.axhline(5, color="green", linestyle=":", alpha=0.6, label="Alexa-tier trivial 5s")
    ax.axhline(8, color="orange", linestyle=":", alpha=0.6, label="Alexa-tier tool 8s")
    ax.axhline(20, color="red", linestyle=":", alpha=0.6, label="Alexa-tier multi-step 20s")
    ax.legend(loc="upper left", ncol=2)
    ax.grid(axis="y", alpha=0.3)
    plt.savefig(GRA / "05_latencia_categoria_540.png")
    plt.close()
    print("OK 05_latencia_categoria_540.png")


# ============================================================================
# 5. Progresion v1-v14 Carter 540
# ============================================================================

def chart_progresion_540():
    versions = []
    for v in range(1, 15):
        f = RESULTS_F3 / f"full540_v{v}_Q6_K_FULL.json"
        if not f.exists(): continue
        d = json.loads(f.read_text(encoding="utf-8"))
        versions.append((v, d["summary"]["pass"], d["summary"].get("partial", 0)))

    nums = [v[0] for v in versions]
    passes = [v[1] for v in versions]
    partials = [v[2] for v in versions]

    fig, ax = plt.subplots(figsize=(12, 6))
    ax.plot(nums, passes, marker="o", linewidth=2, color=COLOR_GEMMA, label="PASS")
    ax.fill_between(nums, passes, alpha=0.15, color=COLOR_GEMMA)

    # PASS + PARTIAL line
    pass_partial = [p + pa for p, pa in zip(passes, partials)]
    ax.plot(nums, pass_partial, marker="^", linestyle="--", linewidth=1, color=COLOR_WARN,
            label="PASS + PARTIAL")

    ax.axhline(540, color="green", linestyle=":", alpha=0.7, label="100% (540/540)")
    ax.axhline(540 * 0.95, color="grey", linestyle=":", alpha=0.5, label="95%")
    ax.axhline(540 * 0.85, color="grey", linestyle=":", alpha=0.5, label="85%")
    ax.set_xticks(nums)
    ax.set_xticklabels([f"v{n}" for n in nums])
    ax.set_ylabel("PASS / 540")
    ax.set_title("Progresion bench Carter 540 (Fase 3) — E4B-Q6_K v1 -> v14")

    # Anotaciones de hitos
    annotations = {
        1: "baseline\nsystem_prompt v3",
        2: "+server estable\n+rerun chunk crasheado",
        6: "meta-ack expandido",
        10: "fs_open <-> app_open\nequivalence",
        12: "prompt-injection\nrejection honest",
        13: "regresion\n--reasoning off",
        14: "Pattern G C11-26\n=> 540/540",
    }
    for v in nums:
        if v in annotations:
            ax.annotate(annotations[v], xy=(v, passes[nums.index(v)]),
                        xytext=(0, 12), textcoords="offset points",
                        fontsize=7, ha="center", color="grey")

    ax.legend(loc="lower right")
    ax.grid(axis="y", alpha=0.3)
    ax.set_ylim(380, 560)
    plt.savefig(GRA / "06_progresion_v1_v14.png")
    plt.close()
    print("OK 06_progresion_v1_v14.png")


# ============================================================================
# 6. Categorias 540 en v14 (heatmap simple)
# ============================================================================

def chart_categorias_v14_heatmap():
    f = RESULTS_F3 / "full540_v14_Q6_K_FULL.json"
    if not f.exists(): return
    d = json.loads(f.read_text(encoding="utf-8"))
    by_cat = d["summary"]["by_category"]
    cats = sorted(int(k) for k in by_cat.keys())
    rates = [by_cat[str(c)]["pass"] / 30 * 100 for c in cats]

    fig, ax = plt.subplots(figsize=(13, 3))
    colors = [COLOR_OK if r >= 100 else COLOR_WARN if r >= 95 else COLOR_FAIL for r in rates]
    bars = ax.bar([f"C{c:02d}" for c in cats], rates, color=colors, edgecolor="white")
    ax.set_ylim(0, 110)
    ax.set_ylabel("% PASS")
    ax.set_title("Carter 540 v14 - PASS rate por categoria (30 cases c/u)")
    for bar, r in zip(bars, rates):
        ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 1,
                f"{r:.0f}%", ha="center", fontsize=8)
    ax.axhline(100, color="green", linestyle=":", alpha=0.6)
    ax.grid(axis="y", alpha=0.3)
    plt.savefig(GRA / "07_categorias_v14_540.png")
    plt.close()
    print("OK 07_categorias_v14_540.png")


# ============================================================================
# 7. Consolidated vs Individual (60 tools vs 16 composite)
# ============================================================================

def chart_consolidated_vs_individual():
    # Tokens/PASS comparativos hardcoded del reporte (medidos)
    metrics = ["Tools (count)", "Tokens schema (~)", "Caracteres", "PASS Carter 540"]
    individual = [60, 5497, 21991, 540]
    consolidated = [16, 1745, 6982, 540]

    fig, axes = plt.subplots(1, 4, figsize=(15, 4))
    titles = ["Cantidad de tools", "Tokens schema", "Chars schema JSON", "PASS / 540 (medido)"]

    for ax, m, i, c, title in zip(axes, metrics, individual, consolidated, titles):
        ax.bar(["60 individuales", "16 consolidated"], [i, c],
               color=[COLOR_NEUTRAL, COLOR_GEMMA], edgecolor="white", width=0.55)
        ax.set_title(title)
        for x_, v in enumerate([i, c]):
            ax.text(x_, v, f"{v:,}", ha="center", va="bottom", fontsize=10)
        if "PASS" in title:
            ax.set_ylim(0, 600)
            ax.axhline(540, color="green", linestyle=":", alpha=0.5)
        ax.grid(axis="y", alpha=0.3)

    plt.suptitle("Consolidacion 60 -> 16 tools (Anthropic best practice)", y=1.02, fontsize=12, fontweight="bold")
    plt.savefig(GRA / "08_consolidated_vs_individual.png")
    plt.close()
    print("OK 08_consolidated_vs_individual.png")


def chart_escalabilidad_tools():
    n = [60, 100, 150, 200, 300]
    indiv = [5497, 9162, 13740, 18325, 27490]
    cons = [1745, 2399, 3050, 3271, 4500]
    ctx_max = 16384

    fig, ax = plt.subplots(figsize=(11, 6))
    ax.plot(n, indiv, marker="s", linewidth=2, color=COLOR_FAIL, label="60 individuales (lineal)")
    ax.plot(n, cons, marker="o", linewidth=2, color=COLOR_GEMMA, label="Composite con discriminator")
    ax.fill_between(n, indiv, cons, color=COLOR_FAIL, alpha=0.05)

    ax.axhline(ctx_max, color="black", linestyle="--", alpha=0.6, label=f"Carter context 16K = {ctx_max}")
    ax.axhline(ctx_max * 0.5, color="grey", linestyle=":", alpha=0.4, label="50% contexto (techo recomendado)")

    ax.annotate("GitHub MCP rompio aqui\n(100+ tools confunde)", xy=(100, 9162),
                xytext=(120, 13000), fontsize=8,
                arrowprops=dict(arrowstyle="->", color="red", alpha=0.6))

    ax.set_xlabel("Cantidad de tools / sub-acciones")
    ax.set_ylabel("Tokens schema (estimado)")
    ax.set_title("Escalabilidad token cost: catalogo plano vs consolidado")
    ax.legend(loc="upper left")
    ax.grid(alpha=0.3)
    plt.savefig(GRA / "09_escalabilidad_tools.png")
    plt.close()
    print("OK 09_escalabilidad_tools.png")


# ============================================================================
# 8. Audio Block D (Gemma 4 vs Whisper esperado)
# ============================================================================

def chart_audio_quality():
    samples = ["audio_01\nhora", "audio_02\nnegation", "audio_03\nmultistep",
               "audio_04\nphonetic", "audio_05\ncodeswitch"]
    gemma_pass = [0, 1, 0, 0, 1]  # 2/5 medido
    whisper_pass = [1, 1, 1, 1, 1]  # ~5/5 esperado de Whisper-large

    fig, ax = plt.subplots(figsize=(10, 5))
    x = np.arange(len(samples))
    w = 0.4
    ax.bar(x - w / 2, gemma_pass, w, label="Gemma 4 nativo (medido)", color=COLOR_GEMMA)
    ax.bar(x + w / 2, whisper_pass, w, label="Whisper-large-v3 (esperado)", color=COLOR_OK)
    ax.set_xticks(x)
    ax.set_xticklabels(samples, fontsize=8)
    ax.set_ylabel("Transcripcion correcta (1=PASS)")
    ax.set_yticks([0, 1])
    ax.set_yticklabels(["FAIL", "PASS"])
    ax.set_title("Bloque D - Audio en espanol rioplatense (TTS sintetico es-MX)")
    ax.legend()
    ax.grid(axis="y", alpha=0.3)
    plt.savefig(GRA / "10_audio_gemma_vs_whisper.png")
    plt.close()
    print("OK 10_audio_gemma_vs_whisper.png")


# ============================================================================
# 9. Iteraciones consolidated v1-v6
# ============================================================================

def chart_consolidated_iterations():
    versions = []
    for v in range(1, 7):
        f = RESULTS_F3 / f"consolidated_v{v}_Q6_K_FULL.json"
        if not f.exists(): continue
        d = json.loads(f.read_text(encoding="utf-8"))
        versions.append((v, d["summary"]["pass"], d["summary"].get("partial", 0)))

    if not versions:
        print("SKIP consolidated iter"); return

    nums = [v[0] for v in versions]
    passes = [v[1] for v in versions]

    fig, ax = plt.subplots(figsize=(11, 6))
    ax.plot(nums, passes, marker="o", linewidth=2, color=COLOR_GEMMA, markersize=10)
    ax.fill_between(nums, passes, alpha=0.15, color=COLOR_GEMMA)
    ax.axhline(540, color="green", linestyle=":", alpha=0.7, label="100%")
    ax.set_xticks(nums)
    ax.set_xticklabels([f"v{n}" for n in nums])
    ax.set_ylabel("PASS / 540")
    ax.set_title("Iteracion consolidated (16 tools) v1 -> v6")

    annotations = {
        1: "506/540\nC09 CUDA crash",
        2: "C09 fix\ngui_deeplink desc",
        3: "539/540\n+ negation marker",
        4: "538/540\nbanking destructive",
        5: "536/540\nC15-25 bug modelo",
        6: "537/540 fresh\n540/540 reaudit",
    }
    for v, p in zip(nums, passes):
        if v in annotations:
            ax.annotate(annotations[v], xy=(v, p), xytext=(0, 14),
                        textcoords="offset points", fontsize=7, ha="center", color="grey")

    ax.legend()
    ax.grid(alpha=0.3)
    ax.set_ylim(490, 555)
    plt.savefig(GRA / "11_consolidated_v1_v6.png")
    plt.close()
    print("OK 11_consolidated_v1_v6.png")


# ============================================================================
# 10. Comparacion Vulkan vs CUDA (descartado)
# ============================================================================

def chart_vulkan_vs_cuda():
    cats = ["Trivial", "Tool simple", "App open", "Multi-step"]
    vulkan_p50 = [3.5, 4.2, 5.8, 12.3]   # estimado de los logs
    cuda_p50 = [2.14, 3.12, 2.26, 11.22]  # medido v11

    x = np.arange(len(cats))
    w = 0.4
    fig, ax = plt.subplots(figsize=(10, 5))
    ax.bar(x - w / 2, vulkan_p50, w, label="Vulkan (descartado)", color=COLOR_NEUTRAL)
    ax.bar(x + w / 2, cuda_p50, w, label="CUDA b9090 (target Carter)", color=COLOR_GEMMA)
    ax.set_xticks(x)
    ax.set_xticklabels(cats)
    ax.set_ylabel("p50 latency (s)")
    ax.set_title("Backend Vulkan vs CUDA - latencia p50 por categoria")
    ax.legend()
    ax.grid(axis="y", alpha=0.3)
    for i, (v, c) in enumerate(zip(vulkan_p50, cuda_p50)):
        ax.text(i - w / 2, v + 0.1, f"{v:.1f}s", ha="center", fontsize=8)
        ax.text(i + w / 2, c + 0.1, f"{c:.1f}s", ha="center", fontsize=8)
    plt.savefig(GRA / "12_vulkan_vs_cuda.png")
    plt.close()
    print("OK 12_vulkan_vs_cuda.png")


# ============================================================================
# 11. Distribucion de fails por causa raiz (v14)
# ============================================================================

def chart_causas_raiz_fails():
    # Datos del historical_analysis
    causas = ["Bug modelo\n(real)", "Bug auditor\n(spec strict)",
              "Conflicto\nspec<->contrato", "Latencia\nmarginal"]
    counts = [4, 38, 12, 11]  # aproximado de los 65 fails totales acumulados v1-v14
    colors = [COLOR_FAIL, COLOR_WARN, COLOR_NEUTRAL, "#FBC02D"]

    fig, ax = plt.subplots(figsize=(9, 6))
    wedges, texts, autotexts = ax.pie(counts, labels=causas, colors=colors,
                                       autopct=lambda p: f"{int(p * sum(counts) / 100)} ({p:.0f}%)",
                                       startangle=90, textprops={"fontsize": 9})
    for at in autotexts:
        at.set_color("white"); at.set_fontweight("bold")
    ax.set_title("Distribucion de fails v1-v14 por causa raiz\n(65 fails totales analizados)")
    plt.savefig(GRA / "13_causas_raiz_fails.png")
    plt.close()
    print("OK 13_causas_raiz_fails.png")


# ============================================================================
# 12. Cobertura tests Carter 540 vs Fase 1 vs Fase 2
# ============================================================================

def chart_cobertura_fases():
    fases = ["Fase 1\n10 tests", "Fase 2\n60 tests x 22 modelos", "Fase 3\n540 cases Carter"]
    tests = [10, 60 * 22, 540]
    invocaciones = [70, 60 * 22 + 60, 540 * 14 + 540 * 6]  # ~bench full + iteraciones
    horas_gpu = [0.2, 4.5, 18]  # estimado

    fig, axes = plt.subplots(1, 3, figsize=(15, 4))
    titles = ["Tests ejecutados", "Invocaciones LLM acumuladas", "Horas GPU efectivas"]
    data = [tests, invocaciones, horas_gpu]
    colors_set = ["#90A4AE", "#42A5F5", "#1976D2"]

    for ax, vals, title in zip(axes, data, titles):
        bars = ax.bar(fases, vals, color=colors_set, edgecolor="white")
        ax.set_title(title)
        for bar, v in zip(bars, vals):
            ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height(),
                    f"{v:,}" if isinstance(v, int) else f"{v:.1f}",
                    ha="center", va="bottom", fontsize=10)
        ax.grid(axis="y", alpha=0.3)
    plt.suptitle("Esfuerzo total del proyecto - 3 fases", y=1.02, fontsize=12, fontweight="bold")
    plt.savefig(GRA / "14_cobertura_fases.png")
    plt.close()
    print("OK 14_cobertura_fases.png")


# ============================================================================
# 13. Selector hardware por VRAM (recomendacion)
# ============================================================================

def chart_selector_hardware():
    perfiles = ["CPU\n(0 GB)", "Tiny\n(<6 GB)", "Low\n(6-8 GB)",
                "Mid\n(8-12 GB)", "Good\n(12-16 GB)", "Great\n(>16 GB)"]
    modelos = ["qwen3:4b\nfallback", "E2B\nQ4_K_M", "E4B\nQ4_K_M",
               "E4B\nQ5_K_M", "E4B\nQ6_K", "E4B\nQ6_K"]
    pass_proyectado = [70, 80, 94, 97, 100, 100]  # los 100 son medidos, resto extrapolado
    vram_uso = [0.5, 4.0, 6.1, 6.6, 7.1, 7.1]

    fig, ax = plt.subplots(figsize=(13, 6))
    x = np.arange(len(perfiles))
    bars = ax.bar(x, pass_proyectado, color=[COLOR_NEUTRAL, COLOR_WARN, "#7CB342",
                                              COLOR_OK, COLOR_GEMMA, COLOR_GEMMA],
                  edgecolor="white", width=0.65)
    ax.set_xticks(x)
    ax.set_xticklabels(perfiles, fontsize=9)
    ax.set_ylabel("PASS rate proyectado (%)")
    ax.set_ylim(0, 115)
    ax.set_title("Selector hardware Carter - modelo recomendado por VRAM")
    for i, (m, p, v) in enumerate(zip(modelos, pass_proyectado, vram_uso)):
        ax.text(i, p + 1, f"{p}%", ha="center", fontsize=9, fontweight="bold")
        ax.text(i, p / 2, m, ha="center", fontsize=8, color="white", fontweight="bold")
        ax.text(i, -8, f"{v} GB usado", ha="center", fontsize=7, color="grey")
    ax.axhline(100, color="green", linestyle=":", alpha=0.5)
    ax.grid(axis="y", alpha=0.3)
    plt.savefig(GRA / "15_selector_hardware.png")
    plt.close()
    print("OK 15_selector_hardware.png")


# ============================================================================
# 14. Cumplimiento de los 30 valores Carter
# ============================================================================

def chart_30_valores_carter():
    # 26 cumplidos en modelo, 4 requieren wiring runtime
    estados = ["Cumple en modelo", "Requiere wiring runtime\n(no es bug del modelo)"]
    counts = [26, 4]
    colors = [COLOR_OK, COLOR_WARN]

    fig, ax = plt.subplots(figsize=(9, 5))
    wedges, texts, autotexts = ax.pie(counts, labels=estados, colors=colors,
                                       autopct=lambda p: f"{int(p * 30 / 100)} de 30",
                                       startangle=90, textprops={"fontsize": 11})
    for at in autotexts:
        at.set_color("white"); at.set_fontweight("bold")
    ax.set_title("Cumplimiento de los 30 valores de ContextoCarter.md\ncon Gemma 4 E4B-Q6_K")
    plt.savefig(GRA / "16_30_valores_carter.png")
    plt.close()
    print("OK 16_30_valores_carter.png")


# ============================================================================
# Ejecutar todo
# ============================================================================

def main():
    print(f"\nGenerando graficos en {GRA}\n")
    chart_fase2_models()
    chart_fase2_top_winners()
    chart_vram()
    chart_gemma_vs_qwen_fase2()
    chart_latencia_por_categoria_540()
    chart_progresion_540()
    chart_categorias_v14_heatmap()
    chart_consolidated_vs_individual()
    chart_escalabilidad_tools()
    chart_audio_quality()
    chart_consolidated_iterations()
    chart_vulkan_vs_cuda()
    chart_causas_raiz_fails()
    chart_cobertura_fases()
    chart_selector_hardware()
    chart_30_valores_carter()
    print(f"\nDone. Revisar {GRA}")


if __name__ == "__main__":
    main()

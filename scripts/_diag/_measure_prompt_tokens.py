"""MEDICIÓN real del prompt enviado al LLM en perfil vram4 (E2B, modo compact).

Usa el AGENTE real (Gemma4Agent) con config temporal — sin llama-server, sin
cargar pesos — y llama a _system_message / _messages tal cual corre en prod.
Cuenta tokens con el tokenizer SentencePiece RECONSTRUIDO desde el GGUF de
Gemma 4 E2B (fidelidad real, no estimación 4c/token).

NO opina: imprime números (chars + tokens) por bloque, subset, y por turno.
"""
import dataclasses
import os
import sys
import tempfile
from pathlib import Path

REPO = r"C:\Users\usuario\Desktop\ETC\Programacion\Probando Gemma 4"
if REPO not in sys.path:
    sys.path.insert(0, REPO)
sys.path.insert(0, os.path.join(REPO, "scripts", "_diag"))

os.environ.setdefault("GEMMA4_PROFILE", "vram4")
os.environ.setdefault("GEMMA4_AGENT_CONTEXT", "16384")

from _gguf_tokenizer import count as tok_count  # noqa: E402


def T(text: str) -> int:
    try:
        return tok_count(text)
    except Exception:
        return -1


def report(label, text):
    chars = len(text)
    toks = T(text)
    print(f"  {label:<54} chars={chars:>6}  tokens={toks:>6}")
    return chars, toks


def main():
    from gemma4_agent.agent_core.agent import Gemma4Agent
    from gemma4_agent.infra.config import AgentConfig
    from gemma4_agent.tools_pkg.tools import COMPOUND_TOOL_SCHEMAS

    tmp = Path(tempfile.mkdtemp(prefix="gemma4_promptmeasure_"))
    base = AgentConfig.from_env()
    cfg = dataclasses.replace(
        base,
        context_size=16384,
        memory_path=tmp / "memory.json",
        captures_dir=tmp / "captures",
        trace_path=tmp / "traces.jsonl",
        state_path=tmp / "state.json",
        enable_tracing=False,
        enable_safety=False,
    )
    agent = Gemma4Agent(cfg)

    print("=" * 104)
    print(f"PERFIL vram4: context_size={cfg.context_size}  ->  tool schemas MODE = compact (ctx>=12288)")
    print("Tokenizer: SentencePiece reconstruido del GGUF gemma-4-E2B-it-Q4_K_M (262144 vocab)")
    print("Layout: GEMMA4_PROMPT_LAYOUT_V3 (default ON)")
    print("=" * 104)

    subsets = {
        "minimo [session,safety]": ["session", "safety"],
        "5 tools CAP [audio,window,app,steam,media]": ["audio", "window", "app", "steam", "media"],
        "grande 12 [+browser,web,cu,fs,wa,email,knowledge]": [
            "audio", "window", "app", "steam", "media", "browser", "web",
            "computer_use", "filesystem", "whatsapp", "email", "knowledge"],
    }

    # ---- 1. SYSTEM PROMPT real por subset (sin historial, user msg corto) ----
    print("\n## 1. SYSTEM PROMPT REAL (agent._system_message, mode=None=>compact, memoria VACÍA) ##")
    sys_tok = {}
    for label, names in subsets.items():
        msg = agent._system_message(mode=None, plan=None,
                                    selected_tool_names=names,
                                    user_text="subí el volumen")
        c, t = report(f"system :: {label}", msg["content"])
        sys_tok[label] = (msg["content"], c, t)

    # ---- 2. EXTRAS al user-msg (V3) por subset (tool-rules fuera del core) ----
    print("\n## 2. TOOL-RULES EXTRAS inyectadas al USER MSG (V3, NO al system) ##")
    from gemma4_agent.agent_core.agent_prompt import build_tool_rules_extras_for_user_msg
    extras_tok = {}
    for label, names in subsets.items():
        extras = build_tool_rules_extras_for_user_msg(names) or ""
        c, t = report(f"extras :: {label}", extras)
        extras_tok[label] = (extras, c, t)

    # ---- 3. MENSAJE DE USUARIO típico ----
    print("\n## 3. USER MSG típico ##")
    user_msgs = {
        "corto": "subí el volumen al 50",
        "medio": "abre spotify y pon rock nacional de los 90 a volumen medio",
        "largo": ("che, fijate si podés mandarle un mensaje por whatsapp a mi "
                  "hermano diciéndole que llego tarde a la cena y que arranquen "
                  "sin mí, y de paso bajá el brillo de la pantalla"),
    }
    for k, v in user_msgs.items():
        report(f"user msg [{k}]", v)

    # ---- 4. HISTORIAL: cuántos turnos / caps del budget vram4 ----
    print("\n## 4. BUDGET DE HISTORIAL (compute_context_budget, ctx=16384) ##")
    from gemma4_agent.agent_core.agent_compaction import compute_context_budget
    b = compute_context_budget(16384)
    for k, val in b.items():
        print(f"  {k:<30} = {val}")
    print(f"  -> reserva ~30% para el turno; ~70% ({b['history_tokens']} tok) para historial.")
    print(f"  -> soft_cap_messages={b['soft_cap_messages']} mensajes (=={b['soft_cap_messages']//2} turnos user+assistant)")

    # ---- 5. Simular historial realista de N turnos y medir el prompt TOTAL ----
    print("\n## 5. PROMPT TOTAL = system + historial + extras + user msg ##")
    # turno user+assistant promedio tras cheap-pass: medimos uno real
    turn_user = "abre el navegador y buscá el clima de mañana"
    turn_asst = "Listo, abrí el navegador y busqué el clima de mañana para vos."

    def messages_total_tokens(system_content, history_msgs, last_user, extras):
        # replica el ensamblado: system + history(+extras prefijado al último user)
        total = T(system_content)
        for m in history_msgs:
            total += T(m if isinstance(m, str) else m.get("content", ""))
        total += T(extras + last_user)
        return total

    scenarios = [
        ("5 tools CAP", "5 tools CAP [audio,window,app,steam,media]", 0, "corto"),
        ("5 tools CAP", "5 tools CAP [audio,window,app,steam,media]", 3, "medio"),
        ("5 tools CAP", "5 tools CAP [audio,window,app,steam,media]", 5, "medio"),
        ("grande 12", "grande 12 [+browser,web,cu,fs,wa,email,knowledge]", 5, "largo"),
        ("grande 12", "grande 12 [+browser,web,cu,fs,wa,email,knowledge]", 10, "largo"),
    ]
    for tag, slabel, nturns, umsgkey in scenarios:
        sys_content = sys_tok[slabel][0]
        extras = extras_tok[slabel][0]
        hist = []
        for _ in range(nturns):
            hist.append({"role": "user", "content": turn_user})
            hist.append({"role": "assistant", "content": turn_asst})
        last_user = user_msgs[umsgkey]
        total = messages_total_tokens(sys_content, hist, last_user, extras)
        free = 8192 - total
        verdict = "ENTRA" if total <= 8192 else "EXCEDE 8K"
        print(f"  [{tag:>10}] {nturns:>2} turnos hist, user={umsgkey:<5} "
              f"-> TOTAL={total:>5} tok | 8K libre={free:>6} | {verdict}")

    # ---- 6. PEOR CASO: subset grande + historial al soft-cap + IMAGEN ----
    print("\n## 6. PEOR CASO (subset grande + historial soft-cap + imagen) ##")
    # imagen Gemma 4: tokens por imagen
    print("  Nota: Gemma 3/4 visión = 256 tokens por imagen (SigLIP, tile 896px).")
    img_tokens = 256
    slabel = "grande 12 [+browser,web,cu,fs,wa,email,knowledge]"
    sys_content = sys_tok[slabel][0]
    extras = extras_tok[slabel][0]
    soft_cap = b["soft_cap_messages"]
    hist = []
    for _ in range(soft_cap // 2):
        hist.append({"role": "user", "content": turn_user})
        hist.append({"role": "assistant", "content": turn_asst})
    last_user = user_msgs["largo"]
    total = messages_total_tokens(sys_content, hist, last_user, extras) + img_tokens
    free = 8192 - total
    print(f"  system(grande12)+extras + {soft_cap} msgs hist(soft-cap) + user(largo) + 1 imagen(256)")
    print(f"  -> TOTAL={total} tok | 8192-total={free} | {'ENTRA' if total<=8192 else 'EXCEDE 8K'}")
    print(f"  (recordá: ctx REAL del perfil = 16384, no 8192)")

    # ---- 7. LEGACY full catalog (None subset) para referencia ----
    print("\n## 7. REFERENCIA: si NO se filtra por subset (None => catálogo completo compact) ##")
    msg_full = agent._system_message(mode=None, plan=None,
                                     selected_tool_names=None,
                                     user_text="subí el volumen")
    report("system :: subset=None (67 tools compact)", msg_full["content"])


if __name__ == "__main__":
    main()

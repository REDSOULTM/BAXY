"""Desglose de QUÉ compone el system prompt real (por qué el mínimo ya pesa ~4.2K tok)."""
import dataclasses, os, sys, tempfile
from pathlib import Path
REPO = r"C:\Users\usuario\Desktop\ETC\Programacion\Probando Gemma 4"
sys.path.insert(0, REPO); sys.path.insert(0, os.path.join(REPO, "scripts", "_diag"))
os.environ.setdefault("GEMMA4_PROFILE", "vram4")
os.environ.setdefault("GEMMA4_AGENT_CONTEXT", "16384")
from _gguf_tokenizer import count as T  # noqa


def r(label, text):
    print(f"  {label:<48} chars={len(text):>6}  tokens={T(text):>6}")


def main():
    from gemma4_agent.agent_core.agent import Gemma4Agent
    from gemma4_agent.infra.config import AgentConfig
    from gemma4_agent.agent_core.agent_prompt import (
        build_core_only, build_core_tool_rules_stable)
    tmp = Path(tempfile.mkdtemp(prefix="gemma4_bd_"))
    base = AgentConfig.from_env()
    cfg = dataclasses.replace(base, context_size=16384,
        memory_path=tmp/"memory.json", captures_dir=tmp/"captures",
        trace_path=tmp/"traces.jsonl", state_path=tmp/"state.json",
        enable_tracing=False, enable_safety=False)
    agent = Gemma4Agent(cfg)
    print("## DESGLOSE bloques ESTABLES del system (V3) ##")
    r("build_core_only()", build_core_only())
    r("build_core_tool_rules_stable() (15 core tools)", build_core_tool_rules_stable())
    r("persona system_hint", agent._persona.system_hint or "")
    # skills (cacheados a nivel instancia tras 1er system_message)
    agent._system_message(selected_tool_names=["session","safety"], user_text="hola")
    r("skills_critical (cache)", agent._cached_skills_critical or "")
    r("skills_menu (cache)", agent._cached_skills_menu or "")
    # memoria vacía
    r("memory.prompt_summary_for('hola')", agent.memory.prompt_summary_for("hola"))
    # taste profile (gate OFF por default => vacío esperado)
    prof = ""
    if agent.behavior is not None:
        try:
            from gemma4_agent.memory_pkg.taste_profile import build_profile_block
            prof = build_profile_block(agent.behavior) or ""
        except Exception:
            pass
    r("taste_profile build_profile_block (gate?)", prof)
    print(f"\n  GEMMA4_TASTE_PROFILE env = {os.environ.get('GEMMA4_TASTE_PROFILE','<unset=default>')}")


if __name__ == "__main__":
    main()

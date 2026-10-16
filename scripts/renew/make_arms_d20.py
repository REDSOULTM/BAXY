"""Decision 20 (owner, 2026-10-16): the arms of the lever-by-lever tuning of Qwen3.5-4B, each a copy of the mind with
one lever changed, measured on the open practice banks with --src (never the sealed ones).

Each arm is written three times, one per sampling seed: the mind fixes its seed so a rerun repeats itself, so the
spread between seeds of the same arm is the noise a lever has to beat.

    python scripts/renew/make_arms_d20.py [--out F:\\BAXYeval\\renew_v1\\ab] [arm ...]

Sources, per lever:
- sampling: Qwen3.5-4B model card, Quickstart «non-thinking (Instruct) mode, general tasks: temperature=0.7,
  top_p=0.8, top_k=20, min_p=0.0, presence_penalty=1.5, repetition_penalty=1.0» (huggingface.co/Qwen/Qwen3.5-4B).
- thinking: the same card: Qwen3.5 thinks by default; «thinking mode, general tasks: temperature=1.0, top_p=0.95,
  top_k=20, min_p=0.0, presence_penalty=1.5».
"""
from __future__ import annotations

import argparse
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MIND = ROOT / "src" / "baxy_mind"

DECIDE_SAMPLING = ('"temperature": self.decide_temperature, "top_p": 0.8, "top_k": 20, "min_p": 0.0,')
SEED = '"seed": 0}'

# arm -> list of (old, new) on mind.py; the seed substitution is added per copy.
ARMS: dict[str, list[tuple[str, str]]] = {
    # The mind as it is (temperature 0.2 from BAXY_RENEW_DECIDE_TEMPERATURE).
    "base": [],
    # Qwen's non-thinking general-task sampling, all of it.
    "qwen": [(DECIDE_SAMPLING, '"temperature": 0.7, "top_p": 0.8, "top_k": 20, "min_p": 0.0, "presence_penalty": 1.5,')],
    # The card's temperature alone, without the presence penalty.
    "t07": [(DECIDE_SAMPLING, '"temperature": 0.7, "top_p": 0.8, "top_k": 20, "min_p": 0.0,')],
    # The presence penalty alone, at the mind's temperature.
    "pp15": [(DECIDE_SAMPLING, DECIDE_SAMPLING + ' "presence_penalty": 1.5,')],
    # Greedy decoding.
    "t0": [(DECIDE_SAMPLING, '"temperature": 0.0, "top_p": 0.8, "top_k": 20, "min_p": 0.0,')],
}

# P5, context order (Liu et al., «Lost in the Middle», TACL 2024: what sits at the end of the context is used best): the
# rules the decision turns on, said again right after the person's words.
TAIL = ("\n[Recuerda: si una herramienta lo hace, llámala; lo hecho lo cuentan sus resultados; si falta un dato que sólo "
        "la persona sabe, pregúntalo con ask_user; si ninguna lo hace, dilo en una frase.]")
ARMS["tail"] = [('        self.conversation.append({"role": "user", "content": text})\n',
                 '        self.conversation.append({"role": "user", "content": text + ' + repr(TAIL) + '})\n')]
# P6, one header per result (Anthropic, «Writing effective tools for agents»: the high-signal part of a result first):
# how every call of the turn ended goes before the result, not after it.
ARMS["head"] = [('"content": observation + "\\n[En este turno: " + "; ".join(done) + "]"})',
                 '"content": "[En este turno: " + "; ".join(done) + "]\\n" + observation})')]
# P7, an example of the computer-use loop in its rule (Brown et al. 2020, «Language Models are Few-Shot Learners»).
ARMS["cuex"] = [('"input_key_press, y vuelve a mirarla para comprobar el cambio antes de seguir o de contarlo.\\n"',
                 '"input_key_press, y vuelve a mirarla para comprobar el cambio antes de seguir o de contarlo. Ejemplo: «ponle '
                 'negrita al título en Word» → input_visible_controls de la ventana de Word → input_visible_click con la '
                 'etiqueta «Negrita» que viste → input_visible_controls otra vez para ver que quedó en negrita → la '
                 'respuesta.\\n"')]

SERVER_THINK = ('"--jinja", "--reasoning", "off", "--reasoning-budget", "0",', '"--jinja", "--reasoning", "on",')
# Thinking on every decision, with the card's thinking sampling and room for the thought.
ARMS["think"] = [
    (DECIDE_SAMPLING, '"temperature": 1.0, "top_p": 0.95, "top_k": 20, "min_p": 0.0, "presence_penalty": 1.5,'),
    ('body = {"messages": messages, "tools": self.tools, "max_tokens": 512, "parallel_tool_calls": True,\n'
     '                "chat_template_kwargs": {"enable_thinking": False},',
     'body = {"messages": messages, "tools": self.tools, "max_tokens": 4096, "parallel_tool_calls": True,\n'
     '                "chat_template_kwargs": {"enable_thinking": True},'),
]


# P2 by task, as a stage of the protocol (never by reading the person's words): the first decision of a turn keeps
# thinking off (its p50 must stay within 1 s), and each decision after a tool result thinks, with the card's thinking
# sampling: the steps of computer use and of multi-step requests, the weakest areas of holdout v2.
ARMS["thinkcont"] = [
    ('        body = {"messages": messages, "tools": self.tools, "max_tokens": 512, "parallel_tool_calls": True,\n'
     '                "chat_template_kwargs": {"enable_thinking": False},\n'
     '                ' + DECIDE_SAMPLING,
     '        thinking = stage == "turn.continue" and not final\n'
     '        body = {"messages": messages, "tools": self.tools, "max_tokens": 4096 if thinking else 512,\n'
     '                "parallel_tool_calls": True, "chat_template_kwargs": {"enable_thinking": thinking},\n'
     '                **({"temperature": 1.0, "top_p": 0.95, "top_k": 20, "min_p": 0.0, "presence_penalty": 1.5}\n'
     '                   if thinking else {"temperature": self.decide_temperature, "top_p": 0.8, "top_k": 20,\n'
     '                                     "min_p": 0.0}),'),
]
THINKING_ARMS = {"think", "thinkcont"}


def write(out: Path, arm: str, seed: int) -> Path:
    target = out / f"d20-{arm}-s{seed}"
    if target.exists():
        shutil.rmtree(target)
    shutil.copytree(MIND, target / "baxy_mind", ignore=shutil.ignore_patterns("__pycache__"))
    mind = target / "baxy_mind" / "mind.py"
    text = mind.read_text(encoding="utf-8")
    for old, new in [*ARMS[arm], (SEED, f'"seed": {seed}}}')]:
        if text.count(old) != 1:
            raise SystemExit(f"{arm}: the text to change is not once in mind.py: {old[:60]!r}")
        text = text.replace(old, new)
    mind.write_text(text, encoding="utf-8")
    if arm in THINKING_ARMS:
        server = target / "baxy_mind" / "llm_server.py"
        source = server.read_text(encoding="utf-8")
        if source.count(SERVER_THINK[0]) != 1:
            raise SystemExit("think: the reasoning flags are not once in llm_server.py")
        server.write_text(source.replace(*SERVER_THINK), encoding="utf-8")
    return target


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("arms", nargs="*", default=list(ARMS))
    parser.add_argument("--out", default=r"F:\BAXYeval\renew_v1\ab")
    parser.add_argument("--seeds", default="0,1,2")
    args = parser.parse_args()
    for arm in args.arms:
        for seed in (int(s) for s in args.seeds.split(",")):
            print(write(Path(args.out), arm, seed))


if __name__ == "__main__":
    main()

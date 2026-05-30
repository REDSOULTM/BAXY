"""Generación SUPLEMENTARIA de queries Tool2Vec: el registro CORTO/DEÍCTICO/
IMPERATIVO que falta (cluster medido 2026-05-30).

CONTEXTO (medición): el cluster de comandos cortos deícticos rutea domain-empty
("subelo a 40"→audio, "escribí 2 más 2"→gui, "ponlo en 7"→system, "desmuteá"
→audio). Causa RAÍZ = el encoder base no embebe esos comandos terse hacia su
tool (la tool correcta ni aparece en el top-12). Los pares existentes en
tool2vec_queries.jsonl son formas LARGAS y educadas ("Turn up the system volume
please", "Baja el volumen un poco, por favor") — no el registro terse que falla.

QUÉ HACE: para las tools afectadas, le pide al LLM LOCAL (no keywords, ley de
producto) que genere utterances MUY CORTAS (2-6 palabras), imperativas, con
clítico deíctico cuando aplique ("lo/it/le"), elípticas, en 6 idiomas. El LLM
genera las variantes; el prompt solo describe el REGISTRO, no da respuestas.

SEGURO: hace APPEND a tool2vec_queries.jsonl (no --force, no sobrescribe los
3573 existentes). Hay backup .bak_pre_deictic por si acaso. Reproducible
(seed fijo en _chat).

Uso:  python scripts/router_tool2vec_generate_deictic.py
      python scripts/router_tool2vec_generate_deictic.py --per-tool 24
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

# Reusar el plumbing del generador base (server discovery + chat + parse).
from scripts.router_tool2vec_generate import _server, _chat, _parse_lines  # noqa: E402

OUT = ROOT / "gemma4_agent" / "data" / "tool2vec_queries.jsonl"

# Tools del cluster afectado (medido): comandos cortos de operación directa.
# Para cada una, una pista del TIPO de acción terse — NO una lista de frases.
_TARGET_TOOLS = {
    "audio":        "subir/bajar/silenciar volumen o sonido, en pasos o a un número",
    "system":       "subir/bajar brillo, poner al máximo/mínimo, temporizador corto",
    "gui":          "teclear texto o números en la app abierta, apretar una tecla",
    "uia":          "tocar/clickear un botón o elemento por nombre en la app abierta",
    "window":       "cerrar/minimizar/cambiar la ventana activa, ver procesos",
    "input":        "escribir/teclear/pegar una secuencia corta de teclas",
    "media":        "pausar/seguir/siguiente/anterior/reanudar lo que suena",
    "audio_device": "cambiar de salida/entrada de audio, al primero/al otro",
}

# Universalidad (ley de producto): generamos UNA llamada POR IDIOMA con un
# target explícito, en vez de pedir un batch mixto (el dry-run mostró que el LLM
# front-loadea es/en y deja fr/de/it/pt cortos). Así garantizamos reparto parejo.
_LANGS = {
    "es": "español", "en": "inglés", "pt": "portugués",
    "fr": "francés", "de": "alemán", "it": "italiano",
}

_PROMPT = """Generás datos de entrenamiento para el router de tools de un asistente de voz.

Tool: {name}
Tipo de acción (terse): {hint}
Idioma OBLIGATORIO de salida: {lang_name} (TODAS las líneas en {lang_name}).

Escribí {n} utterances MUY CORTAS (2 a 6 palabras), TODAS en {lang_name}, que una
persona le DIRÍA en voz para disparar ESTA tool, en el registro más corto posible:
- REGISTRO terse: imperativo desnudo + clítico/deíctico cuando aplique
  (el referente del turno anterior: "lo/la/it/le/es" según el idioma), elíptico,
  sin cortesía. Son ÓRDENES cortas, no descripciones largas y educadas.
- Incluí variantes con un NÚMERO o nivel cuando la acción lo permita
  (a un valor, un poco más/menos, al máximo).
- Algo de ruido de transcripción de voz (sin tildes/acentos, palabras pegadas) en pocas.
- SIN numerar, SIN explicar, SIN comillas. UNA utterance por línea, texto plano.

Escribí las {n} líneas EN {lang_name} ahora:"""


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--per-tool", type=int, default=24,
                    help="total por tool (se reparte entre los 6 idiomas)")
    ap.add_argument("--temperature", type=float, default=0.85)
    ap.add_argument("--tool", default="", help="solo esta tool (debug)")
    args = ap.parse_args()

    base, model = _server()
    print(f"server={base} model={model}")
    print(f"APPEND a {OUT.name} (no sobrescribe; backup .bak_pre_deictic existe)")

    per_lang = max(2, round(args.per_tool / len(_LANGS)))
    tools = [args.tool] if args.tool else list(_TARGET_TOOLS.keys())
    total = 0
    seen: set[tuple[str, str]] = set()  # (tool, query.lower()) dedupe
    with OUT.open("a", encoding="utf-8") as f:
        for i, name in enumerate(tools):
            hint = _TARGET_TOOLS.get(name, name)
            wrote = 0
            for lang, lang_name in _LANGS.items():
                prompt = _PROMPT.format(name=name, hint=hint, n=per_lang + 4,
                                        lang_name=lang_name)
                try:
                    raw = _chat(base, model, prompt, temperature=args.temperature)
                except Exception as exc:
                    print(f"   {name}/{lang}: GEN FAILED {exc}")
                    continue
                qs = _parse_lines(raw)[:per_lang]
                for q in qs:
                    key = (name, q.lower())
                    if key in seen:
                        continue
                    seen.add(key)
                    f.write(json.dumps({"tool": name, "q": q}, ensure_ascii=False) + "\n")
                    wrote += 1
                f.flush()
            total += wrote
            print(f"[{i+1}/{len(tools)}] {name}: +{wrote} queries cortas (6 idiomas)")
    print(f"\ndone -> +{total} queries deícticas/cortas en {OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

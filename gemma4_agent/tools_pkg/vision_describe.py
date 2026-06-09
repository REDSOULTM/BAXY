"""Descripción de pantalla por visión (extraído de tools.py 2026-06-07, ratchet
archivo-dios). Llamada de visión LIMPIA con ancla OCR para reducir alucinación.

El modelo de visión 2B aluvina en pantallas densas; el OCR (Tesseract) lee el
texto REAL sin inventar. Anclar la descripción a ese texto + describir solo el
monitor en foco (no la panorámica multi-monitor) baja la alucinación. Ver el bug
'Mortal Kombat' (2026-06-07): pivigames en 1 de 3 monitores -> describía mal.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any


def describe_image(agent: Any, image_path: Any, focus: str = "",
                   ocr_text: str = "", ocr_fn: Any = None) -> str | None:
    """Describe la captura en texto vía el modelo de visión. thinking OFF, sin
    tools, budget amplio (evita el finish=length vacío del 4B). `ocr_text`: texto
    real leído por OCR como ancla factual contra la alucinación. `ocr_fn`: callable
    (t_vision) para LEER el OCR acá si no se pasó ocr_text (best-effort).
    Devuelve la descripción o None si no se puede (sin agente/visión/error)."""
    if agent is None or not image_path:
        return None
    p = Path(str(image_path))
    if not p.exists():
        return None
    # ANCLA OCR: si no vino el texto pero hay ocr_fn, leerlo (el OCR no alucina).
    if not ocr_text and ocr_fn is not None:
        try:
            _o = ocr_fn({"action": "ocr", "image_path": str(p)})
            if isinstance(_o, dict) and _o.get("ok"):
                ocr_text = str(_o.get("text") or "")[:800]
        except Exception:
            ocr_text = ""
    try:
        from .multimodal import image_part
        from ..infra.llama_server import resolve_turn_model
        try:
            _vision_model = resolve_turn_model(has_image=True)  # '<perfil>-vision'
        except Exception:
            _vision_model = None
        instr = (
            "Describí en 2-4 frases, en español claro, qué se ve en esta "
            "captura de pantalla: la app/ventana principal al frente, el "
            "contenido relevante y las opciones o acciones visibles. De "
            "arriba a abajo, lo más importante primero. No inventes lo que "
            "no se ve."
        )
        # ANCLA OCR: el texto REAL de la pantalla. Anclar al modelo en él evita
        # que un 2B aluvine sobre pantallas densas (caso 'Mortal Kombat').
        #
        # CRÍTICO (bug 2026-06-08): el 2B repetía el ANCLA crudo dentro de su
        # respuesta visible ("El OCR leyó '<<<0 a_ox @ chatgpt.com...'") — el
        # usuario lee prosa, NO el volcado garbled del OCR ni los marcadores
        # <<< >>>. La instrucción debe dejar claro que el OCR es referencia
        # SILENCIOSA de fondo: se usa para identificar bien la app, NUNCA se
        # cita, transcribe ni menciona en la descripción.
        if ocr_text and ocr_text.strip():
            instr += (
                " Como referencia interna y SILENCIOSA (NO la menciones, NO la "
                "cites, NO la transcribas, NO escribas 'el OCR' ni los símbolos "
                "<<< >>> en tu respuesta), un OCR leyó este texto de la pantalla "
                "para que identifiques bien la app/sitio sin contradecirlo: "
                f"<<<{ocr_text.strip()}>>>. "
                "Tu respuesta debe ser prosa limpia describiendo lo que se ve, "
                "sin rastro de ese texto crudo."
            )
        if focus:
            instr += f" Prestá atención especial a: {focus}."
        msgs = [{"role": "user", "content": [
            image_part(p), {"type": "text", "text": instr}]}]
        resp = agent.client.chat(
            msgs, tools=None, enable_thinking=False, max_tokens=400,
            timeout_s=90.0, model=_vision_model)
        txt = (((resp or {}).get("choices") or [{}])[0]
               .get("message") or {}).get("content") or ""
        return _strip_ocr_echo(txt.strip()) or None
    except Exception:
        return None


def _strip_ocr_echo(text: str) -> str:
    """Guarda ESTRUCTURAL: el 2B a veces ignora la instrucción y vuelca el
    ancla OCR cruda en la descripción ("El OCR leyó '<<<...>>>'"). El usuario
    lee prosa, no el dump garbled. Limpiamos por FORMA (no contenido):

    1. Quitamos cualquier segmento envuelto en los marcadores <<< >>> (el ancla
       literal si se filtró).
    2. Si una FRASE menciona el OCR de forma meta ("el OCR leyó/dice/detectó…"),
       la descartamos entera: es ruido sobre el OCR, no descripción de pantalla.

    Sin hardcode de idioma de CONTENIDO: solo detecta la auto-referencia al OCR
    (un término técnico universal) y los marcadores que NOSOTROS inyectamos.
    """
    if not text:
        return text
    import re
    # 1. Marcadores literales <<< ... >>> (incl. multilínea).
    text = re.sub(r"<<<.*?>>>", "", text, flags=re.DOTALL)
    # Marcador huérfano sin cierre (el modelo cortó a la mitad).
    text = re.sub(r"<<<.*$", "", text, flags=re.DOTALL)
    # 2. Frases meta-OCR ("el OCR leyó …", "OCR detected …", "le texte OCR …").
    #    Partimos en frases y descartamos las que se refieren al OCR.
    sentences = re.split(r"(?<=[.!?。])\s+", text)
    kept = [s for s in sentences
            if not re.search(r"\bO\.?C\.?R\.?\b", s, flags=re.IGNORECASE)]
    cleaned = " ".join(kept).strip() if kept else ""
    # Si limpiar dejó todo vacío (la respuesta ERA solo el dump), devolvemos lo
    # que quede tras quitar marcadores — mejor algo que None silencioso.
    return (cleaned or text).strip()


__all__ = ["describe_image"]

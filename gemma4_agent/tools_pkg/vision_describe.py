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
                   ocr_text: str = "") -> str | None:
    """Describe la captura en texto vía el modelo de visión. thinking OFF, sin
    tools, budget amplio (evita el finish=length vacío del 4B). `ocr_text`: texto
    real leído por OCR, se inyecta como ancla factual contra la alucinación.
    Devuelve la descripción o None si no se puede (sin agente/visión/error)."""
    if agent is None or not image_path:
        return None
    p = Path(str(image_path))
    if not p.exists():
        return None
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
        if ocr_text and ocr_text.strip():
            instr += (
                " El texto que el OCR leyó EN ESTA pantalla (es la verdad, "
                "usalo para identificar la app/sitio y NO contradecirlo): "
                f"<<<{ocr_text.strip()}>>>"
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
        return txt.strip() or None
    except Exception:
        return None


__all__ = ["describe_image"]

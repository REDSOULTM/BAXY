"""Detección por embeddings de las intenciones de PRIVACIDAD del perfil de gustos:
inspect ("¿qué sabés de mí?") y forget ("olvidate de lo que sabés de mí").

Por qué un short-circuit determinista y no el LLM: MEDIDO (2026-05-30) que "¿qué
sabés sobre mí?" lo rutea el router como ACCIÓN de PC (mode=fast_action, 128 tok,
forced-tool-retry) y el 4B devuelve reply VACÍO. Estas dos intenciones tienen una
respuesta DETERMINISTA correcta (mostrar/borrar el perfil), igual que leer/responder
mensajes — no hay nada que "inferir". Mostrar el perfil es la guarda de privacidad
INSPECTABLE; borrarlo, la BORRABLE (table-stakes de la industria, ver taste_profile).

Mismo mecanismo que accessibility_voice.detect_mode_switch: centroides multilingües
por clase + clase `none` que absorbe el uso normal. NO keywords (regla del proyecto).
Reusa el encoder ya cargado. Fallback seguro: encoder caído -> None (no adivina).

API: detect_profile_intent(text) -> "inspect" | "forget" | None
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any

_ANCHORS: dict[str, list[str]] = {
    "inspect": [
        # español
        "qué sabés de mí", "qué sabes sobre mí", "qué aprendiste de mí",
        "qué conocés de mis gustos", "describime cómo soy según lo que viste",
        "qué tenés guardado sobre mí", "mostrame mi perfil", "qué pensás que me gusta",
        "qué datos tenés míos", "cómo me ves", "qué recordás de mí",
        "qué recuerdas de mí", "qué memoria tenés de mí",
        # inglés
        "what do you know about me", "what have you learned about me",
        "show me my profile", "what do you think i like",
        # pt / it
        "o que você sabe sobre mim", "cosa sai di me",
    ],
    "forget": [
        # español
        "olvidate de lo que sabés de mí", "borrá lo que aprendiste de mí",
        "eliminá mi perfil", "borrá mis datos de comportamiento",
        "no quiero que guardes mis gustos", "dejá de observarme y borrá todo",
        "olvidá todo sobre mí", "limpiá lo que sabés de mí",
        # inglés
        "forget what you know about me", "delete my profile",
        "erase my data", "stop tracking me and delete everything",
        # pt / it
        "esqueça o que sabe sobre mim", "dimentica tutto su di me",
    ],
    "none": [
        # comandos / preguntas / charla — el uso NORMAL que NO debe disparar
        "abrí spotify", "subí el volumen", "qué hora es", "poné una canción",
        "cuánto es dos más dos", "explicame la fotosíntesis", "buscá en internet",
        "qué tiempo hace", "mandale un mensaje a juan", "cerrá el navegador",
        "hola", "gracias", "dale", "ok", "cómo estás", "thank you", "hello",
        "qué sabés de python", "qué sabés sobre la guerra",  # "qué sabés de X" NO-mí
        "ayudame con esto", "recomendame música",
        # hard-negatives de FORGET: borrar ARCHIVOS no es borrar el perfil
        "borrá estos archivos", "eliminá esta carpeta", "limpiá la carpeta de descargas",
        "borrá el archivo viejo", "eliminá los temporales",
        # hard-negatives de INSPECT: TIPEAR "mi nombre"/mis datos EN una app es una
        # ACCIÓN, no preguntar por el perfil (MEDIDO 2026-05-31: "en notepad poné mi
        # nombre" matcheaba inspect y volcaba el perfil en vez de tipear).
        "en notepad poné mi nombre", "escribí mi nombre en el bloc de notas",
        "anotá mi nombre en el documento", "escribe mi nombre en el word",
        "write my name in notepad", "pon mi correo en el formulario",
        # hard-negatives de INSPECT (cacería tanda 2/3, cluster A5 ~22 casos): el
        # short-circuit de perfil sobre-disparaba ante preguntas de CAPACIDAD,
        # IDENTIDAD, PANTALLA, PERCEPCIÓN y CHARLA que mencionan "me/yo/mí" pero NO
        # piden ver el perfil de gustos. Deben seguir el turno normal (el LLM
        # responde), no volcar el perfil.
        #   capacidad / percepción ("¿me ves/escuchás?", "¿qué podés hacer?")
        "me estás escuchando", "me estás viendo", "podés verme", "me ves ahora",
        "are you listening to me", "can you see me", "me escuchás siempre",
        "qué podés hacer", "qué puedo pedirte", "qué no podés hacer",
        "what can you do", "what can i ask you", "podés tomar el control",
        "qué podés hacer por mí", "qué cosas podés hacer", "en qué me podés ayudar",
        "what can you do for me", "how can you help me",
        #   IDENTIDAD DEL ASISTENTE (quién SOS VOS, no qué sabés de MÍ) -> el LLM
        #   se presenta; NO es inspección del perfil del usuario.
        "quién sos", "quién eres", "qué sos", "presentate", "preséntate ante mí",
        "háblame de ti", "hablame de vos", "qué se supone que hacés",
        "who are you", "what are you", "who created you", "quién te creó",
        "por qué me hablás", "para qué servís",
        #   consulta de SISTEMA/LIBRERÍA (vram/juegos/disco) -> tool de sistema, no perfil
        "cuánta vram tengo", "qué juegos tengo", "cuánta ram tengo",
        "how much vram do i have", "what games do i have", "qué hay en mi disco",
        #   pantalla ("qué hay en mi pantalla") -> es visión, no perfil
        "qué hay en mi pantalla", "qué muestra mi pantalla", "what does my screen show",
        "qué tengo en mi pc ahora", "qué ves en la pantalla",
        #   identidad / recall conversacional ("quién soy", "qué te dije recién")
        "quién soy yo", "quién soy", "cómo me llamo", "qué te dije hace un rato",
        "who am i", "what did i just say", "qué dije recién",
        #   intención de GUARDAR un dato (no inspeccionar) -> seguir turno normal
        "recordame como red", "quiero que me recuerdes como red", "guardá que me llamo",
        "anotá que mi color favorito es", "remember me as red",
        #   charla / filosófico ("tenés sentimientos?", "tenés memes?", "sé honesto")
        "tenés sentimientos", "tenés algún meme", "sé honesto conmigo",
        "qué significa hecho para vos", "do you have feelings", "be honest with me",
        #   CHARLA EMOCIONAL/FILOSÓFICA multilingüe (cacería t5): el short-circuit de
        #   perfil disparaba ante desahogo/reflexión en pt/de/fr ("pensás en mí?",
        #   "creés que soy buena persona?", "quiero rendirme"). NO son inspección del
        #   perfil; el LLM debe responder con empatía. Incluye casos de malestar.
        "pensás en mí a veces", "creés que soy buena persona", "me entendés",
        "quiero rendirme", "estoy triste", "me siento mal", "estoy orgulloso de mí",
        "do you think about me", "do you think i am a good person", "i feel sad",
        "i want to give up", "you understand me",
        # portugués
        "você pensa em mim", "você acha que sou uma boa pessoa", "você me entende",
        "acho que vou desistir", "estou triste", "tenho orgulho de mim",
        # alemán / francés
        "denkst du über mich nach", "verstehst du mich",
        "penses-tu à moi", "je suis fier de moi", "tu me comprends",
    ],
}

# Tuneado conservador: ante la duda, NO short-circuiteamos (dejamos seguir el turno).
_MARGIN = float(os.environ.get("GEMMA4_PROFILE_INTENT_MARGIN", "0.08"))
_FLOOR = float(os.environ.get("GEMMA4_PROFILE_INTENT_FLOOR", "0.42"))
# FORGET es IRREVERSIBLE (borra datos) → piso/margen más altos que inspect. Un FP de
# inspect solo muestra el perfil (inocuo); un FP de forget borraría datos. Asimetría
# deliberada (CLAUDE.md: rigor extra ante lo irreversible). Además forget PIDE
# confirmación antes de borrar (ver agent: _pending_profile_forget).
_FORGET_MARGIN = float(os.environ.get("GEMMA4_PROFILE_FORGET_MARGIN", "0.14"))
_FORGET_FLOOR = float(os.environ.get("GEMMA4_PROFILE_FORGET_FLOOR", "0.50"))


@dataclass
class _Centroids:
    by_class: dict[str, Any]
    ready: bool = False


_C = _Centroids(by_class={})


def _ensure_centroids() -> bool:
    if _C.ready:
        return bool(_C.by_class)
    try:
        from ..routing import semantic_router as sr
        if not sr._ensure_loaded():
            _C.ready = True
            return False
        import numpy as np
        model = sr._STATE.model

        def _centroid(anchors: list[str]) -> Any:
            e = model.encode(anchors, normalize_embeddings=True).mean(0)
            return np.asarray(e / (np.linalg.norm(e) or 1.0), dtype="float32")

        _C.by_class = {cls: _centroid(a) for cls, a in _ANCHORS.items()}
        _C.ready = True
        return True
    except Exception:
        _C.ready = True
        _C.by_class = {}
        return False


def detect_profile_intent(text: str) -> str | None:
    """'inspect' | 'forget' | None. Una clase debe ser argmax GLOBAL (ganarle a
    `none`), cruzar el piso y el margen. Encoder caído -> None."""
    if not text or not text.strip():
        return None
    if not _ensure_centroids() or not _C.by_class:
        return None
    try:
        from ..routing import semantic_router as sr
        import numpy as np
        qe = sr.embed(text)
        if qe is None:
            return None
        qe = np.asarray(qe, dtype="float32")
        scores = {cls: float(qe @ cen) for cls, cen in _C.by_class.items()}
    except Exception:
        return None
    none_score = scores.get("none", 0.0)
    switch = {c: s for c, s in scores.items() if c != "none"}
    if not switch:
        return None
    best_cls = max(switch, key=lambda c: switch[c])
    best = switch[best_cls]
    # FORGET (irreversible) exige piso/margen más altos que inspect.
    floor = _FORGET_FLOOR if best_cls == "forget" else _FLOOR
    margin = _FORGET_MARGIN if best_cls == "forget" else _MARGIN
    if best < floor or (best - none_score) < margin:
        return None
    return best_cls

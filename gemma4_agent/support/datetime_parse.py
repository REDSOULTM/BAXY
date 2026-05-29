"""Parseo de FECHA/HORA en lenguaje natural -> ISO 8601, UNIVERSAL y conservador.

El 4B (E2B-Q4) NO convierte fiable "las tres de la tarde" / "el viernes a las
cinco" a ISO (aritmética temporal). dateparser (lib instalada, multilingüe) cubre
inglés/francés pero falla varios idioms ESPAÑOLES. Solución: un PUENTE español
mínimo que normaliza esos idioms ANTES de dateparser. Si NADA resuelve con
confianza -> None (el caller PREGUNTA la hora exacta; NUNCA inventamos un horario,
porque un recordatorio mal es peligroso).

Aplica a reminder/calendar/notification (cualquier tool con un campo de fecha NL).
NO es per-caso: es una capa universal de normalización temporal.
"""
from __future__ import annotations

import re
from datetime import datetime
from typing import Optional

# Mapeo de números en palabras (es) -> dígito, para "a las tres", "diez minutos".
_NUM_ES = {
    "cero": 0, "una": 1, "uno": 1, "dos": 2, "tres": 3, "cuatro": 4, "cinco": 5,
    "seis": 6, "siete": 7, "ocho": 8, "nueve": 9, "diez": 10, "once": 11,
    "doce": 12, "trece": 13, "catorce": 14, "quince": 15, "veinte": 20,
    "treinta": 30, "media": 30, "cuarto": 15,
}


def _words_to_digits(text: str) -> str:
    """Reemplaza números-palabra es por dígitos donde aparecen como hora/cantidad.
    Conservador: solo tokens completos."""
    def repl(m: re.Match) -> str:
        return str(_NUM_ES[m.group(0).lower()])
    pattern = r"\b(" + "|".join(sorted(_NUM_ES, key=len, reverse=True)) + r")\b"
    return re.sub(pattern, repl, text, flags=re.IGNORECASE)


def _normalize_es(text: str) -> str:
    """Puente ESPAÑOL: reescribe idioms que dateparser no maneja a una forma que
    sí. Multilingüe-friendly: si no hay idiom es, devuelve el texto casi intacto."""
    t = text.strip()
    t = _words_to_digits(t)
    low = t.lower()
    # "X y media" -> "X:30", "X y cuarto" -> "X:15" (tras words_to_digits: "3 y 30")
    t = re.sub(r"\b(\d{1,2})\s+y\s+30\b", r"\1:30", t)
    t = re.sub(r"\b(\d{1,2})\s+y\s+15\b", r"\1:15", t)
    # "X de la tarde"/"de la noche" -> +12h (si X<12). "X de la mañana" -> X tal cual.
    # Maneja minutos: "7:30 de la tarde" -> "19:30", "7 de la tarde" -> "19:00".
    def _pm(m: re.Match) -> str:
        h = int(m.group(1))
        mm = m.group(2) or "00"
        if h < 12:
            h += 12
        return f"{h}:{mm}"
    t = re.sub(r"\b(\d{1,2})(?::(\d{2}))?\s+de\s+la\s+(?:tarde|noche)\b", _pm, t,
               flags=re.IGNORECASE)
    def _am(m: re.Match) -> str:
        return f"{int(m.group(1))}:{m.group(2) or '00'}"
    t = re.sub(r"\b(\d{1,2})(?::(\d{2}))?\s+de\s+la\s+ma(?:n|ñ)ana\b", _am, t,
               flags=re.IGNORECASE)
    # "a las N" sin sufijo -> dejar que dateparser lo tome como hora; normalizamos
    # "a las 5" -> "5:00" para anclar la hora.
    t = re.sub(r"\ba\s+las\s+(\d{1,2})\b(?!\s*[:h]\d)(?!\s*de\s+la)", r"\1:00", t,
               flags=re.IGNORECASE)
    # "en N minutos/horas" ya lo maneja dateparser en es; lo dejamos.
    # Limpiar artículos/preposiciones sueltos que quedan tras normalizar la hora y
    # que confunden a dateparser ("las 15:00" -> "15:00"; "a las 7 de la mañana" ->
    # tras la regla mañana queda "a 7:00", y dateparser lee "a 7:00" como enero
    # 2027 — bug medido). Quitamos "a las / a la / a / las / el / la / los" antes de
    # una hora HH:MM. Solo al inicio o pegado a la hora; no toca el resto.
    t = re.sub(r"\b(?:a\s+las|a\s+la|a|las|el|la|los)\s+(?=\d{1,2}:\d{2}\b)", "",
               t, flags=re.IGNORECASE)
    t = re.sub(r"^\s*(el|la|los|las)\s+", "", t, flags=re.IGNORECASE)
    return t.strip()


def parse_when(text: str, *, base: Optional[datetime] = None,
               languages: Optional[list[str]] = None) -> Optional[str]:
    """NL date/time -> ISO 8601 string (o None si no resuelve con confianza).
    CONSERVADOR: None significa "pedí la hora exacta", no "ahora". `base` = ahora
    de referencia (para tests deterministas)."""
    if not text or not text.strip():
        return None
    # Si YA es ISO, devolver tal cual (no romper lo que el LLM acertó).
    s = text.strip()
    try:
        datetime.fromisoformat(s.replace("Z", "+00:00"))
        return s
    except ValueError:
        pass
    try:
        import dateparser
    except Exception:
        return None
    base = base or datetime.now()
    langs = languages or ["es", "en", "pt", "fr", "it", "de"]
    settings = {
        "PREFER_DATES_FROM": "future",
        "RELATIVE_BASE": base,
        "RETURN_AS_TIMEZONE_AWARE": False,
    }
    # ¿La expresión suena a HOY/esta-parte-del-día (sin día/fecha explícita)? Si
    # sí, un resultado a >2 días es ABSURDO (bug medido: "a las 5 de la tarde" ->
    # 2027). En ese caso descartamos -> None (el caller pregunta). Conservador:
    # un horario MAL es peor que preguntar.
    low = s.lower()
    # OJO "mañana": en español es AMBIGUO — "mañana" (tomorrow, día) vs "de/por la
    # mañana" (morning, parte del día). "a las 7 DE LA mañana" NO es "mañana=día"
    # (bug medido: contaba como día explícito, desactivaba el guardrail y daba
    # 2027). Solo cuenta como día el "mañana" que NO va precedido de "la/de la"
    # (esos son "morning").
    _manana_as_day = bool(re.search(r"(?<!la\s)(?<!de\sla\s)\bma(?:n|ñ)ana\b", low))
    _has_explicit_day = _manana_as_day or bool(re.search(
        r"\bpasado\b|\bhoy\b|\blunes\b|\bmartes\b|\bmi(?:e|é)rcoles\b|"
        r"\bjueves\b|\bviernes\b|\bs(?:a|á)bado\b|\bdomingo\b|\btomorrow\b|\btoday\b|"
        r"\bmonday\b|\btuesday\b|\bwednesday\b|\bthursday\b|\bfriday\b|\bsaturday\b|"
        r"\bsunday\b|\d{1,4}[-/]\d{1,2}|\bel\s+\d{1,2}\b|\bnext\b|\bpr(?:o|ó)xim",
        low))
    _sounds_same_day = not _has_explicit_day
    # 1er intento: con el puente español. 2do: el texto crudo (otros idiomas).
    for candidate in (_normalize_es(s), s):
        try:
            d = dateparser.parse(candidate, languages=langs, settings=settings)
        except Exception:
            d = None
        if d is None:
            continue
        delta_days = abs((d - base).total_seconds()) / 86400.0
        if _sounds_same_day and delta_days > 2.0:
            # resultado absurdamente lejos para algo que sonaba a hoy -> no confiar
            continue
        return d.replace(microsecond=0).isoformat()
    return None

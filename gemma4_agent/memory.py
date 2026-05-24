"""Explicit persistent memory for the Gemma 4 agent."""

from __future__ import annotations

import json
import re
import threading
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any


# Bounds defensivos para evitar que memory.json crezca sin control. Los limites
# son generosos pero finitos: el caso normal es <100 facts de <500 chars cada uno.
MAX_KEY_LEN = 200
MAX_VALUE_LEN = 8000
MAX_TOTAL_ITEMS = 500  # explicit; el cap de auto: es aparte (max_total kwarg)


# Caracteres de control invisibles que no deberian estar en keys/values porque
# rompen el rendering del prompt y del log. Permitimos \n y \t.
_INVALID_CONTROL_CHARS = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f]")


# Filtro anti-junk para la extracción PASIVA (auto_save). El incidente reportado
# (inv 2 §4): el 52% de la memoria era basura de pruebas. Solo aplica a auto:* —
# el `save` explícito (el user lo pidió) NUNCA se filtra. Universal: valores tipo
# test/asdf/solo-dígitos/ruido, sin keywords de idioma. Conservador: ante la duda
# se guarda (mejor un hecho marginal que perder uno útil).
_JUNK_VALUE_RE = re.compile(
    r"^\s*(?:"
    r"test\d*|testing|asdf+|qwerty|foo(?:bar)?|bar|baz|"  # placeholders dev
    r"prueba\d*|lorem(?:\s+ipsum)?|"
    r"x{2,}|a{3,}|\.{2,}|-{2,}|"                            # repeticiones
    r"\d{1,6}|"                                             # solo dígitos cortos
    r"n/?a|none|null|undefined|\?+"                         # vacíos disfrazados
    r")\s*$",
    re.IGNORECASE,
)
_MIN_VALUE_CHARS = 2  # un valor de 1 char nunca es un hecho útil


def _is_junk_value(value: str) -> bool:
    """True si el valor parece basura de prueba/ruido (no un hecho real)."""
    v = (value or "").strip()
    if len(v) < _MIN_VALUE_CHARS:
        return True
    return bool(_JUNK_VALUE_RE.match(v))


def _sanitize_key(raw: str) -> str:
    """Normaliza una key: strip + colapsar whitespace + drop control chars."""
    if not raw:
        return ""
    cleaned = _INVALID_CONTROL_CHARS.sub("", raw).strip()
    # Colapsar whitespace interno para que "foo  bar" == "foo bar".
    return " ".join(cleaned.split())


def _sanitize_value(raw: str) -> str:
    if not raw:
        return ""
    return _INVALID_CONTROL_CHARS.sub("", raw)


@dataclass
class MemoryStore:
    path: Path
    _lock: threading.RLock = field(default_factory=threading.RLock, init=False, repr=False, compare=False)

    def __post_init__(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def _load(self) -> dict[str, Any]:
        if not self.path.exists():
            return {"items": {}}
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return {"items": {}}
        if not isinstance(data, dict):
            return {"items": {}}
        data.setdefault("items", {})
        return data

    def _save(self, data: dict[str, Any]) -> None:
        from .state import atomic_write_json
        atomic_write_json(self.path, data)

    def save(self, key: str, value: str) -> dict[str, Any]:
        # SANITIZACION + VALIDACION: control chars rompen el rendering del
        # prompt; tamaños unbounded permiten al LLM tirar MB de basura.
        clean_key = _sanitize_key(key)
        if not clean_key:
            return {"ok": False, "error": "empty key", "status": "needs_user"}
        if len(clean_key) > MAX_KEY_LEN:
            return {
                "ok": False,
                "error": f"key too long ({len(clean_key)} > {MAX_KEY_LEN} chars)",
                "status": "needs_user",
                "hint": "use a shorter key; the value can be larger",
            }
        clean_value = _sanitize_value(value or "")
        if len(clean_value) > MAX_VALUE_LEN:
            return {
                "ok": False,
                "error": f"value too long ({len(clean_value)} > {MAX_VALUE_LEN} chars)",
                "status": "needs_user",
                "hint": "split the fact into smaller pieces or use knowledge.ingest for documents",
            }
        with self._lock:
            data = self._load()
            items = data.setdefault("items", {})
            # CAP TOTAL: si ya estamos al limite Y la key es nueva, evict la
            # entry mas vieja (por updated_at). Explicit pueden eliminar a
            # auto:* y viceversa — el cap es global porque el storage es uno.
            if clean_key not in items and len(items) >= MAX_TOTAL_ITEMS:
                oldest = min(
                    items.items(),
                    key=lambda pair: pair[1].get("updated_at", "") if isinstance(pair[1], dict) else "",
                )
                items.pop(oldest[0], None)
                evicted = oldest[0]
            else:
                evicted = None
            items[clean_key] = {
                "value": clean_value,
                "updated_at": datetime.now().isoformat(timespec="seconds"),
            }
            self._save(data)
            return {
                "ok": True, "key": clean_key, "value": clean_value,
                "total": len(items), "evicted": evicted,
            }

    def auto_save(self, facts: list[dict[str, str]], *, max_total: int = 50) -> dict[str, Any]:
        """Persist facts extracted automatically (without explicit user request).

        Each fact is dict {key, value}. We prefix the key with 'auto:' so the
        user can tell auto-learned facts from explicit ones, and we cap the
        total auto-saved facts at `max_total` (FIFO eviction of oldest).
        """
        with self._lock:
            data = self._load()
            items = data.setdefault("items", {})
            added: list[str] = []
            skipped: list[dict[str, Any]] = []
            for fact in facts:
                key = str(fact.get("key", "")).strip()
                value = str(fact.get("value", "")).strip()
                if not key or not value:
                    skipped.append({"reason": "empty_key_or_value", "fact": fact})
                    continue
                # Anti-junk (inv 2 §4): la extracción pasiva NO debe envenenar la
                # memoria con basura de pruebas. El save explícito no pasa por acá.
                if _is_junk_value(value):
                    skipped.append({"reason": "junk_value", "fact": fact})
                    continue
                stamped_key = key if key.startswith("auto:") else f"auto:{key}"
                items[stamped_key] = {
                    "value": value,
                    "updated_at": datetime.now().isoformat(timespec="seconds"),
                    "source": "auto_extracted",
                }
                added.append(stamped_key)
            # Evict oldest auto:* entries if we exceed the cap. Explicit (non-auto)
            # entries are never touched.
            auto_keys = [k for k in items if k.startswith("auto:")]
            if len(auto_keys) > max_total:
                sorted_auto = sorted(
                    ((k, items[k].get("updated_at", "")) for k in auto_keys),
                    key=lambda pair: pair[1],
                )
                to_drop = len(auto_keys) - max_total
                for k, _ in sorted_auto[:to_drop]:
                    items.pop(k, None)
            self._save(data)
            return {"ok": True, "added": added, "skipped": skipped, "total_auto": sum(1 for k in items if k.startswith("auto:"))}

    def recall(self, query: str | None = None) -> dict[str, Any]:
        with self._lock:
            data = self._load()
            items = data.get("items", {})
        if not query:
            return {"ok": True, "items": items}
        q = query.casefold()
        matches = {
            k: v for k, v in items.items()
            if q in k.casefold() or q in str(v.get("value", "")).casefold()
        }
        return {"ok": True, "query": query, "items": matches}

    def delete(self, key: str) -> dict[str, Any]:
        # Normalizar key igual que en save() para que delete sea simetrico.
        clean = _sanitize_key(key) if key != "*" else "*"
        with self._lock:
            data = self._load()
            items = data.get("items", {})
            if clean == "*":
                count = len(items)
                data["items"] = {}
                self._save(data)
                return {"ok": True, "deleted": count, "scope": "all"}
            existed = clean in items
            items.pop(clean, None)
            self._save(data)
            return {"ok": True, "key": clean, "existed": existed, "deleted": 1 if existed else 0}

    def prompt_summary(self) -> str:
        with self._lock:
            items = self._load().get("items", {})
        if not items:
            return "No persistent memory saved."
        lines = []
        for key, entry in sorted(items.items()):
            lines.append(f"- {key}: {entry.get('value', '')}")
        return "\n".join(lines)

    def prompt_summary_for(self, user_text: str | None) -> str:
        """Memoria EN CAPAS para el prompt (inv 2): core siempre + hechos
        relevantes al turno por retrieval semántico cuando el store es grande.
        Para stores chicos == prompt_summary() (vuelca todo). Best-effort: ante
        cualquier fallo cae a prompt_summary() (nunca esconde hechos a ciegas)."""
        with self._lock:
            items = self._load().get("items", {})
        try:
            from .memory_retrieval import build_memory_section
            return build_memory_section(items, user_text)
        except Exception:
            if not items:
                return "No persistent memory saved."
            return "\n".join(
                f"- {k}: {v.get('value', '')}" for k, v in sorted(items.items()))

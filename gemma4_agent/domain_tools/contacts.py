"""Contacts domain tool — extracted from domain_tools.py (R2 sprint 2026-05-27).

Antes vivía inline en domain_tools.py (~ líneas 7718-8053). Extraído acá como
segundo paso del refactor R2. domain_tools.py re-exporta los símbolos públicos
para que los callers existentes (no hay tests dedicados de contactos hoy, pero
sí lo importa indirectamente vía dispatch) sigan funcionando.

Funciones extraídas (10) + 3 regex constants + 2 thresholds:
  contacts_tool                  (entry point, 9 acciones)
  _contacts_update
  _contacts_export_vcard
  _contacts_import_vcard
  _contacts_resolve_recipient    (con desambiguación honesta)
  _clean_contact_field
  _contact_to_vcard
  _vcard_escape / _vcard_unescape
  _vcard_parse
  _name_similarity               (Jaro-Winkler + metaphone fonético)

Constants extraídos:
  _CONTROL_CHARS_RE
  _EMAIL_BASIC_RE
  _PHONE_BASIC_RE
  _RESOLVE_AMBIGUOUS_MARGIN     (12)
  _RESOLVE_MIN_SCORE            (60)

Helpers importados desde domain_tools (dep dirigida, NO circular: domain_tools
no importa nada de contacts; solo re-exporta los símbolos públicos):
  _resources_by_kind
  _find_resource
  _update_resource_metadata

Mock-friendly: las funciones no llaman subprocess; solo leen/escriben state.
Los tests futuros pueden mockear AgentState methods directamente."""
from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path
import time
from typing import Any

from .._shared import _err, _ok
from ..memory_pkg.state import AgentState


__all__ = [
    "contacts_tool",
    "_contacts_update",
    "_contacts_export_vcard",
    "_contacts_import_vcard",
    "_contacts_resolve_recipient",
    "_clean_contact_field",
    "_contact_to_vcard",
    "_vcard_escape",
    "_vcard_unescape",
    "_vcard_parse",
    "_name_similarity",
    "_CONTROL_CHARS_RE",
    "_EMAIL_BASIC_RE",
    "_PHONE_BASIC_RE",
    "_RESOLVE_AMBIGUOUS_MARGIN",
    "_RESOLVE_MIN_SCORE",
]


_EMAIL_BASIC_RE = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")
_PHONE_BASIC_RE = re.compile(r"^[\d\s\-\+\(\)]+$")
_CONTROL_CHARS_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f]")


def _clean_contact_field(value: Any) -> str | None:
    """Normaliza un campo de contacto: strip + drop control chars + tipo str.
    Devuelve None si el valor es vacio o no convertible."""
    if value is None:
        return None
    s = _CONTROL_CHARS_RE.sub("", str(value)).strip()
    return s or None


def contacts_tool(args: dict[str, Any], state: AgentState) -> dict[str, Any]:
    # Imports diferidos para evitar ciclo en import time (contacts -> domain_tools
    # -> contacts). En runtime el módulo ya está cargado y la resolución es trivial.
    from .helpers import (
        _find_resource,
        _resources_by_kind,
    )
    action = str(args.get("action") or "list").casefold()
    if action == "status":
        return _ok(local_state=True, count=len(_resources_by_kind(state, "contact")))
    if action == "list":
        return _ok(contacts=_resources_by_kind(state, "contact", include_closed=bool(args.get("include_closed", False))))
    if action in {"create", "add"}:
        name = _clean_contact_field(args.get("name"))
        if not name:
            return _err("missing contact name", status="needs_user")
        email = _clean_contact_field(args.get("email"))
        phone = _clean_contact_field(args.get("phone"))
        notes = _clean_contact_field(args.get("notes"))
        # VALIDACION laxa de formato: si el LLM pasa email=123 o phone="abc",
        # devolvemos status=needs_user con el motivo. NO rechazamos formatos
        # no convencionales (internacionales, extensiones) — solo lo
        # claramente roto.
        if email and not _EMAIL_BASIC_RE.match(email):
            return _err(
                f"invalid email format: {email!r}",
                hint="expected user@host.tld; omit field to skip", status="needs_user",
            )
        if phone and not _PHONE_BASIC_RE.match(phone):
            return _err(
                f"invalid phone format: {phone!r}",
                hint="digits + (space/dash/+/parens) only; use _vcard for international formats",
                status="needs_user",
            )
        # CHEQUEO UNICIDAD: contactos con mismo nombre ya existentes generan
        # un warning explicito (no rechazo) para que el LLM decida que hacer.
        existing = [
            c for c in _resources_by_kind(state, "contact", include_closed=False)
            if (c.get("metadata") or {}).get("name", "").strip().casefold() == name.casefold()
        ]
        resource = state.register_resource(
            "contact", name,
            metadata={
                "name": name, "email": email, "phone": phone, "notes": notes,
                "created_at": datetime.now().isoformat(),
            },
        )
        out = _ok(contact=resource.get("resource"))
        if existing:
            out["duplicate_warning"] = {
                "count": len(existing),
                "existing_ids": [c.get("id") for c in existing[:5]],
                "note": (
                    "A contact with the same name already exists. Use action=update "
                    "instead if you want to modify it, or proceed with create for a "
                    "separate entry."
                ),
            }
        return out
    if action == "search":
        query = (_clean_contact_field(args.get("query") or args.get("name")) or "").casefold()
        if not query:
            return _err("missing query/name", status="needs_user")
        try:
            limit = max(1, min(int(args.get("limit", 10)), 100))
        except (TypeError, ValueError):
            limit = 10
        # MATCHING ESTRUCTURADO: en vez de JSON-blob substring (que matchea
        # ids, timestamps, basura), comparar contra los campos del metadata
        # de forma explicita.
        matches: list[dict[str, Any]] = []
        for c in _resources_by_kind(state, "contact", include_closed=True):
            meta = c.get("metadata") or {}
            haystacks = [
                str(meta.get("name") or ""),
                str(meta.get("email") or ""),
                str(meta.get("phone") or ""),
                str(meta.get("notes") or ""),
                str(c.get("label") or ""),
            ]
            if any(query in h.casefold() for h in haystacks):
                matches.append(c)
        return _ok(matches=matches[:limit], count=len(matches), query=query)
    if action == "delete":
        contact = _find_resource(args, state, "contact")
        if not contact:
            return _err("contact not found", status="needs_user")
        return state.mark_cleaned(str(contact["id"]), {"deleted": True})
    if action == "update":
        return _contacts_update(args, state)
    if action == "export_vcard":
        return _contacts_export_vcard(args, state)
    if action == "import_vcard":
        return _contacts_import_vcard(args, state)
    if action == "resolve_recipient":
        return _contacts_resolve_recipient(args, state)
    return _err(
        "unknown contacts action", action=action,
        valid_actions=[
            "status", "list", "create", "add", "search", "delete", "update",
            "export_vcard", "import_vcard", "resolve_recipient",
        ],
        status="needs_user",
    )


def _contacts_update(args: dict[str, Any], state: AgentState) -> dict[str, Any]:
    from .helpers import _find_resource, _update_resource_metadata
    contact = _find_resource(args, state, "contact")
    if not contact:
        return _err("contact not found")
    updates: dict[str, Any] = {}
    for key in ("name", "email", "phone", "notes"):
        if key in args and args[key] is not None:
            updates[key] = args[key]
    if not updates:
        return _err("no updatable fields provided", supported=["name", "email", "phone", "notes"])
    if "name" in updates:
        state.update_resource(str(contact["id"]), label=str(updates["name"]))
    return _update_resource_metadata(state, str(contact["id"]), updates)


def _contacts_export_vcard(args: dict[str, Any], state: AgentState) -> dict[str, Any]:
    from .helpers import _resources_by_kind
    contacts = _resources_by_kind(state, "contact", include_closed=False)
    if not contacts:
        return _err("no contacts to export", status="needs_user")
    path_raw = str(args.get("path") or "").strip()
    if path_raw:
        path = Path(path_raw).expanduser()
    else:
        path = state.path.parent / "generated" / f"contacts_{time.strftime('%Y%m%d_%H%M%S')}.vcf"
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        return _err("cannot create export directory", path=str(path.parent), reason=str(exc))
    body = "\r\n".join(_contact_to_vcard(c) for c in contacts) + "\r\n"
    try:
        path.write_text(body, encoding="utf-8")
    except (PermissionError, OSError) as exc:
        return _err(
            "vcard write failed", path=str(path), reason=str(exc),
            status="needs_user" if isinstance(exc, PermissionError) else "failed",
        )
    # VERIFICACION post-write.
    try:
        size = path.stat().st_size
    except OSError:
        size = -1
    if size != len(body.encode("utf-8")):
        return _err(
            "vcard write incomplete", path=str(path),
            expected_bytes=len(body.encode("utf-8")), actual_bytes=size,
            status="failed",
        )
    return _ok(path=str(path.resolve()), exported=len(contacts), bytes=size, verified=True)


def _contact_to_vcard(contact: dict[str, Any]) -> str:
    meta = contact.get("metadata") or {}
    name = str(meta.get("name") or contact.get("label") or "")
    email = str(meta.get("email") or "")
    phone = str(meta.get("phone") or "")
    notes = str(meta.get("notes") or "")
    lines = ["BEGIN:VCARD", "VERSION:3.0", f"FN:{_vcard_escape(name)}", f"N:{_vcard_escape(name)};;;;"]
    if email:
        lines.append(f"EMAIL:{_vcard_escape(email)}")
    if phone:
        lines.append(f"TEL:{_vcard_escape(phone)}")
    if notes:
        lines.append(f"NOTE:{_vcard_escape(notes)}")
    lines.append("END:VCARD")
    return "\r\n".join(lines)


def _vcard_escape(text: str) -> str:
    return text.replace("\\", "\\\\").replace(",", "\\,").replace(";", "\\;").replace("\n", "\\n")


def _vcard_unescape(text: str) -> str:
    return text.replace("\\,", ",").replace("\\;", ";").replace("\\n", "\n").replace("\\N", "\n").replace("\\\\", "\\")


def _contacts_import_vcard(args: dict[str, Any], state: AgentState) -> dict[str, Any]:
    path_raw = str(args.get("path") or args.get("file") or "").strip()
    text = str(args.get("content") or args.get("vcard") or "")
    if path_raw:
        p = Path(path_raw).expanduser()
        if not p.is_file():
            return _err("vCard file not found", path=str(p))
        text = p.read_text(encoding="utf-8", errors="replace")
    if not text.strip():
        return _err("no vCard content provided")
    cards = _vcard_parse(text)
    if not cards:
        return _err("no VCARD blocks found")
    created = []
    for card in cards:
        name = card.get("fn") or card.get("n") or "Contact"
        resource = state.register_resource(
            "contact",
            name,
            metadata={
                "name": name,
                "email": card.get("email"),
                "phone": card.get("tel"),
                "notes": card.get("note"),
                "imported_from": path_raw or "<inline>",
                "created_at": datetime.now().isoformat(),
            },
        )
        created.append(resource.get("resource"))
    return _ok(imported=len(created), contacts=created[:50], total_parsed=len(cards))


def _vcard_parse(text: str) -> list[dict[str, Any]]:
    raw_lines = text.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    unfolded: list[str] = []
    for line in raw_lines:
        if unfolded and (line.startswith(" ") or line.startswith("\t")):
            unfolded[-1] += line[1:]
        else:
            unfolded.append(line)
    cards: list[dict[str, Any]] = []
    current: dict[str, Any] | None = None
    for line in unfolded:
        stripped = line.strip()
        if not stripped:
            continue
        upper = stripped.upper()
        if upper == "BEGIN:VCARD":
            current = {}
            continue
        if upper == "END:VCARD":
            if current is not None:
                cards.append(current)
            current = None
            continue
        if current is None:
            continue
        sep = stripped.find(":")
        if sep < 0:
            continue
        head, value = stripped[:sep], stripped[sep + 1:]
        name = head.split(";", 1)[0].upper()
        value = _vcard_unescape(value)
        if name == "FN":
            current["fn"] = value
        elif name == "N":
            # N: Family;Given;Additional;Prefix;Suffix
            parts = value.split(";")
            given = parts[1] if len(parts) > 1 else ""
            family = parts[0] if parts else ""
            current["n"] = (given + " " + family).strip() or value
        elif name == "EMAIL":
            current.setdefault("email", value)
        elif name == "TEL":
            current.setdefault("tel", value)
        elif name == "NOTE":
            current["note"] = value
    return cards


def _name_similarity(q: str, name: str) -> int:
    """Similitud nombre-query UNIVERSAL (inv 2). Combina exacto/substring con
    fuzzy (Jaro-Winkler, funciona en cualquier script) y fonético (metaphone,
    ayuda en alfabeto latino: 'mama'!='musica'). Devuelve 0-100. Sin deps duras:
    si jellyfish/rapidfuzz no están, cae a exacto/substring."""
    if not q or not name:
        return 0
    if q == name:
        return 100
    score = 50 if q in name or name in q else 0
    try:
        import jellyfish
        jw = jellyfish.jaro_winkler_similarity(q, name)
        score = max(score, int(jw * 88))  # tope <100 para no empatar con exacto
        # bonus fonético: mismo metaphone refuerza (anti 'mama'->'musica').
        if jellyfish.metaphone(q) and jellyfish.metaphone(q) == jellyfish.metaphone(name):
            score = max(score, 72)
    except Exception:
        pass
    return score


# Si el mejor y el segundo candidato quedan dentro de este margen, la resolución
# es AMBIGUA y el agente debería preguntar en vez de adivinar (anti bug
# "mamá"->"Música"): mejor pedir desempate que mandar al chat equivocado.
_RESOLVE_AMBIGUOUS_MARGIN = 12
# Piso de score para considerar un match REAL. Jaro-Winkler da ~50 de baseline a
# strings no relacionados ('persona inexistente' vs 'juan perez' = 48); por
# debajo de esto es ruido fuzzy, no un candidato. Medido sobre nombres reales.
_RESOLVE_MIN_SCORE = 60


def _contacts_resolve_recipient(args: dict[str, Any], state: AgentState) -> dict[str, Any]:
    from .helpers import _resources_by_kind
    query = str(args.get("query") or args.get("name") or args.get("recipient") or "").strip()
    if not query:
        return _err("missing query")
    q = query.casefold()
    contacts = _resources_by_kind(state, "contact", include_closed=False)
    scored: list[tuple[int, dict[str, Any]]] = []
    for c in contacts:
        meta = c.get("metadata") or {}
        name = str(meta.get("name") or c.get("label") or "").casefold()
        email = str(meta.get("email") or "").casefold()
        phone = str(meta.get("phone") or "").casefold()
        score = _name_similarity(q, name)
        if q == email:
            score = max(score, 90)
        elif q and q in email:
            score = max(score, 40)
        if q == phone:
            score = max(score, 80)
        elif q and q in phone:
            score = max(score, 30)
        if score >= _RESOLVE_MIN_SCORE:
            scored.append((score, c))
    scored.sort(key=lambda t: -t[0])
    matches = [{"contact": c, "score": s} for s, c in scored[: int(args.get("limit", 5))]]
    # Ambigüedad: top-2 REALES (sobre el piso) y muy cerca -> señalar para que el
    # agente desempate. Dos matches débiles no son ambiguos, son ruido.
    ambiguous = (
        len(matches) >= 2
        and matches[1]["score"] >= _RESOLVE_MIN_SCORE
        and (matches[0]["score"] - matches[1]["score"]) <= _RESOLVE_AMBIGUOUS_MARGIN
        and matches[0]["score"] < 100  # un match exacto no es ambiguo
    )
    return _ok(query=query, matches=matches, count=len(matches),
               best=matches[0] if matches else None, ambiguous=ambiguous)

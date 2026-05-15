"""Helpers compartidos para invocar PowerShell de forma segura.

Surgió como respuesta a las auditorías CC-ps-fstring-injection-pattern-100 y
CC-json-loads-unguarded-103: centraliza la validación estricta de literales
embebidos en scripts PS y el parsing seguro de stdout JSON.
"""

from __future__ import annotations

import json
import re
from typing import Any, Pattern


class PSValidationError(ValueError):
    """Se lanza cuando un valor controlado por el LLM no pasa el regex
    de allowlist y por tanto no puede interpolarse en un script PowerShell.
    """


def ps_safe_literal(value: Any, regex: str | Pattern[str]) -> str:
    """Valida `value` contra `regex` (allowlist) y devuelve la cadena.

    Uso típico: validar nombres de log, horarios, IPs antes de
    f-stringearlos dentro de un script PowerShell.

    No escapa: si el valor no matchea el regex, falla con
    PSValidationError. La idea es rechazar, no sanitizar.
    """
    text = str(value)
    pattern = re.compile(regex) if isinstance(regex, str) else regex
    if not pattern.fullmatch(text):
        raise PSValidationError(f"value does not match allowlist {pattern.pattern!r}: {text!r}")
    return text


# Regex reutilizables (allowlists estrictas)
RX_HHMM = re.compile(r"^[0-2]\d:[0-5]\d$")
RX_ISO_DATETIME = re.compile(r"^\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}(:\d{2})?$")
RX_IPV4 = re.compile(r"^(\d{1,3}\.){3}\d{1,3}$")
RX_IPV6 = re.compile(r"^[0-9A-Fa-f:]+$")
RX_LOG_NAME = re.compile(r"^[A-Za-z][A-Za-z0-9/_\-]*(/[A-Za-z][A-Za-z0-9/_\-]*)*$")
RX_DAY_OF_WEEK = re.compile(r"^(Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday)$")
RX_TCP_STATE = re.compile(
    r"^(Closed|CloseWait|Closing|DeleteTcb|Established|FinWait1|FinWait2|"
    r"LastAck|Listen|SynReceived|SynSent|TimeWait|Bound)$"
)
RX_SQL_IDENT = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*(\.[A-Za-z_][A-Za-z0-9_]*)?$")


def parse_ps_json(raw: str) -> tuple[bool, Any]:
    """Intenta parsear stdout de PowerShell como JSON.

    Devuelve (ok, value). Si ok=True, value es lo parseado. Si ok=False,
    value es el raw stripped (truncado a 1000 chars) para que el caller
    pueda devolverlo como `stdout` en un _err.
    """
    text = (raw or "").strip()
    if not text:
        return True, None
    try:
        return True, json.loads(text)
    except json.JSONDecodeError:
        return False, text[:1000]


def is_ipv4(value: str) -> bool:
    if not RX_IPV4.fullmatch(value):
        return False
    try:
        return all(0 <= int(part) <= 255 for part in value.split("."))
    except ValueError:
        return False


def is_ipv6(value: str) -> bool:
    if not RX_IPV6.fullmatch(value):
        return False
    if value.count("::") > 1:
        return False
    parts = value.split(":")
    return len(parts) <= 8 and all(len(p) <= 4 for p in parts if p)

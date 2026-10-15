"""Auditoría semántica 2026-09-20 (REOPEN1993, comandos; D11): «ejecuta ls»
(H0245) y «ejecuta pytest» (H0048) se corren de verdad en una consola y el
final cita su salida; «corré git status» (H0468) sigue el mismo camino."""

from __future__ import annotations

import pytest

from baxy_mind import effect_intent
from baxy_mind import compose_situation
from baxy_mind import payload_fact_checks
from baxy_mind import argument_grounding

AVAILABLE = frozenset({"shell.command.run", "app.open", "web.search", "package.install.prepare", "package.install.commit", "app.installed"})
APPS = ("Spotify", "Steam")


@pytest.mark.parametrize(
    ("text", "command", "cwd"),
    [
        ("ejecuta ls", "ls", None),
        ("ejecuta pytest", "pytest", None),
        ("corré git status", "git status", None),
        ("Run pytest.", "pytest", None),
        ("Execute ls.", "ls", None),
        ("ejecutá el comando git status", "git status", None),
        (r"PS C:\Users\usuario\Desktop\ETC\Programacion\Carter OS AI> python carter_core.py", "python carter_core.py", r"C:\Users\usuario\Desktop\ETC\Programacion\Carter OS AI"),
    ],
)
def test_console_commands_are_run_for_real(text: str, command: str, cwd: str | None) -> None:
    intent = effect_intent.resolve_explicit_effects(text, AVAILABLE, APPS, ())
    assert intent is not None and intent.operations == ("shell.command.run",)
    assert effect_intent.shell_command_request(text) == (command, cwd)
    schema = {"type": "object", "properties": {"command": {"type": "string"}, "cwd": {"type": ["string", "null"]}}, "required": ["command"], "additionalProperties": False}
    assert argument_grounding._ground_explicit_arguments("shell.command.run", text, schema, APPS) == {"command": command, "cwd": cwd}
    assert effect_intent.operation_domain_is_grounded(text, "shell.command.run") is True


@pytest.mark.parametrize("text", ["ejecuta Steam", "corre el juego", "no ejecutes nada", "ejecuta rm -rf /"])
def test_applications_games_negations_and_unknown_heads_abstain(text: str) -> None:
    assert effect_intent.shell_command_request(text) is None


def test_the_limit_lifts_only_when_the_operation_exists() -> None:
    assert effect_intent.known_unsupported_effect_request("ejecuta ls", {"app.open"}) is True
    assert effect_intent.known_unsupported_effect_request("ejecuta ls", AVAILABLE) is False


OK = {"operation": "shell.command.run", "seen": {"command": "git status", "cwd": "C:/x", "exitCode": 0, "lines": ["On branch main", "nothing to commit, working tree clean"], "lineCount": 2, "stderr": "", "truncated": False}}
FAILED = {"operation": "shell.command.run", "seen": {"command": "pytest", "cwd": "C:/x", "exitCode": 1, "lines": [], "lineCount": 0, "stderr": "pytest : El término 'pytest' no se reconoce", "truncated": False}}
SILENT = {"operation": "shell.command.run", "seen": {"command": "cd .", "cwd": "C:/x", "exitCode": 0, "lines": [], "lineCount": 0, "stderr": "", "truncated": False}}


@pytest.mark.parametrize(
    ("text", "payload", "defect"),
    [
        ("Ejecuté git status y salió bien: «On branch main» / «nothing to commit, working tree clean».", OK, ""),
        ("Ejecuté git status y salió bien: «On branch develop».", OK, "extra_claim"),
        ("Ejecuté git status y salió bien.", OK, "missing_state"),
        ("Ejecuté pytest y falló (código 1): «pytest : El término 'pytest' no se reconoce».", FAILED, ""),
        ("Ejecuté pytest y salió bien.", FAILED, "extra_claim"),
        ("Ejecuté cd . y terminó bien, sin salida.", SILENT, ""),
        ("Ejecuté cd . y terminó bien.", SILENT, "missing_state"),
    ],
)
def test_the_reply_quotes_only_what_the_command_printed(text: str, payload: dict, defect: str) -> None:
    assert payload_fact_checks._shell_fact_defect(text, payload) == defect


def test_the_refusals_have_their_own_cause_facts() -> None:
    for code in ("shell_command_destructive", "shell_command_directory_not_found", "shell_command_timeout", "shell_command_not_started"):
        assert code in compose_situation._CAUSE_FACT

"""Development-only Mind entrypoint that prints caught turn tracebacks."""

from __future__ import annotations

import sys
import traceback

import baxy_mind.__main__ as mind_main


_real_audit_failure = mind_main._audit_turn_attempt_failure


def _trace_failure(
    message: dict[str, object],
    error: BaseException,
    failure_kind: str,
) -> None:
    print(
        f"BAXY_TURN_TRACE|{message.get('id')}|{failure_kind}",
        file=sys.stderr,
        flush=True,
    )
    traceback.print_exception(
        type(error),
        error,
        error.__traceback__,
        file=sys.stderr,
    )
    _real_audit_failure(message, error, failure_kind)


mind_main._audit_turn_attempt_failure = _trace_failure


if __name__ == "__main__":
    raise SystemExit(mind_main.main())

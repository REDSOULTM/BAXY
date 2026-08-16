"""Audit consumed sealed evidence by its seal, not by regenerating it.

Decision of 2026-08-15 recorded in `documentacion/00_META_VIGENTE.md` §7:

    A sealed preregistration is audited by the integrity of its seal, not by
    its regeneration from the present tree. Exact regeneration is required
    while the seal is live; once consumed, or once one of its versioned
    inputs changes legitimately, the artifact is kept as historical evidence
    and is no longer required to be reproduced by a current builder.

Goal 02 measured which inputs had moved before applying this: the live
catalogue went from 157 to 158 operations, and R225 additionally binds
`%LOCALAPPDATA%\\BAXYRuntime\\mind-runtime-v1.json`, a file outside the
repository whose hash differs per machine. Neither can be regenerated here.

The rule is explicit that the artifact must still be verified, not skipped:
these seals turn red if the published bytes change.
"""

from __future__ import annotations

import hashlib
from pathlib import Path


def assert_sealed(artifact: Path, expected_sha256: str) -> None:
    """Fail unless the published artifact still hashes to its recorded seal."""
    actual = hashlib.sha256(artifact.read_bytes()).hexdigest()
    assert actual == expected_sha256, (
        f"sealed evidence changed: {artifact.name} "
        f"expected={expected_sha256} actual={actual}"
    )

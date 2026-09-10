"""Record terminal Full6 and make current source agree with Git's LF policy."""
from pathlib import Path
from datetime import datetime, timezone
import hashlib
import json
import os
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "artifacts/comprobaciones/C03/PUBLICATION744"
FULL = ROOT / "artifacts/comprobaciones/C03/FULL6_742"
sys.path.insert(0, str(ROOT))
from scripts.wake_validation_program_tree import fingerprint_program_tree


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, value):
    path.write_bytes((json.dumps(value, ensure_ascii=False, indent=2) + "\n").encode("utf-8"))


def main():
    OUT.mkdir(exist_ok=True)
    assert not (OUT / "CHANGES.json").exists(), "already completed"
    terminal = json.loads((FULL / "RESULT.json").read_text(encoding="utf-8"))
    assert terminal["exit_code"] == 1 and terminal["sources_unchanged"]
    raw = Path(os.environ["LOCALAPPDATA"]) / "BAXY/C03-full6-742-private/full.log"
    assert sha(raw) == terminal["log_sha256"]
    log = raw.read_text(encoding="utf-8-sig")
    assert "1 failed, 11398 passed, 3 skipped, 466 subtests passed in 736.77s" in log
    failure = "tests/test_price_v8_veto_damage_by_cause.py::test_published_split_and_ceiling_are_the_numbers_r144_reported"
    assert "FAILED " + failure in log
    # Public diagnostic log contains test output, not user conversations.
    (FULL / "FULL.log").write_bytes(log.encode("utf-8"))
    result = {
        "status": "failed", "session": 3835, "exit_code": 1,
        "elapsed_seconds": terminal["elapsed_seconds"],
        "dotnet": {"passed": 4574, "failed": 0, "aggregate_skipped": 1,
                   "explicit_opt_in_omission_log_lines": 16},
        "python": {"passed": 11398, "failed": 1, "skipped": 3,
                   "subtests_passed": 466, "seconds": 736.77},
        "failure": failure,
        "cause": "Current __main__.py allowlist pin still precedes source740. Historical V8 evidence hashes and reported numbers are unchanged.",
        "original_sidecar_and_packaging_tests": "passed in this Full; original test bytes and 3s/45s deadlines unchanged",
        "sources_unchanged": True, "source_count": 1233,
        "private_raw_log_sha256": sha(raw), "public_lf_log_sha256": sha(FULL / "FULL.log"),
        "adopted": False, "coverage_added": 0, "goal_complete": False,
    }
    write(FULL / "ADJUDICATION.json", result)
    partial = json.loads((FULL / "PARTIAL.json").read_text(encoding="utf-8"))
    partial.update(status="terminal_failed", note="Terminal result in ADJUDICATION.json; prior .NET subtotal retained. No run is still active.")
    write(FULL / "PARTIAL.json", partial)

    changed = []
    full_sources = json.loads((FULL / "SOURCES.json").read_text(encoding="utf-8"))
    for rel in ["src/baxy_mind/voice_aec.py", "src/baxy_mind/voice.py",
                "experiments/stt_quality/evaluate_reserved_stt.py",
                "experiments/stt_quality/audit_fresh_postweight_stt_sources.py"]:
        path = ROOT / rel
        before = path.read_bytes()
        after = before.replace(b"\r\n", b"\n")
        assert b"\r" not in after
        path.write_bytes(after)
        changed.append({"file": rel, "full6_sha256": full_sources[rel],
                        "before_this_invocation_sha256": hashlib.sha256(before).hexdigest(),
                        "lf_only_sha256": sha(path), "crlf_removed_this_invocation": before.count(b"\r\n")})
    roots = [ROOT / p for p in ["experiments/voice_latency", "scripts", "src/baxy_mind"]]
    crlf = [p.relative_to(ROOT).as_posix() for root in roots for p in root.rglob("*.py")
            if p.is_file() and b"\r\n" in p.read_bytes()]
    assert not crlf, crlf
    program = fingerprint_program_tree(repository_root=ROOT, source_roots=roots)
    assert program["pythonFiles"] == 407
    old = b"d9d3c7f150d954e84507171561a23d5d574486624e4993fe18dcce7c2a1e2dd1"
    for rel in ["experiments/stt_quality/evaluate_reserved_stt.py",
                "experiments/stt_quality/audit_fresh_postweight_stt_sources.py"]:
        path = ROOT / rel
        data = path.read_bytes()
        assert data.count(old) == 1
        path.write_bytes(data.replace(old, program["sha256"].encode("ascii")))
    test = ROOT / "tests/test_price_v8_veto_damage_by_cause.py"
    before = test.read_bytes()
    old_main = b"447d51d4f57c0d95a71faaa87e789a3c961803bc6d55db79241c2b98a8dc2070"
    assert before.count(old_main) == 1
    current_main = sha(ROOT / "src/baxy_mind/__main__.py")
    assert current_main == "908c4276977761e1c64f20b005dfd8dde0a0180869fc11d8c26e02577e5f5f99"
    test.write_bytes(before.replace(old_main, current_main.encode("ascii")))

    source = [row["file"] for row in changed] + ["tests/test_price_v8_veto_damage_by_cause.py"]
    checkout = []
    for rel in source:
        raw_blob = subprocess.check_output(["git", "hash-object", "--no-filters", rel], cwd=ROOT, text=True).strip()
        clean_blob = subprocess.check_output(["git", "hash-object", rel], cwd=ROOT, text=True).strip()
        assert raw_blob == clean_blob, rel
        checkout.append({"file": rel, "sha256": sha(ROOT / rel), "git_blob": raw_blob,
                         "clean_checkout_bytes_identical": True})
    write(OUT / "PROGRAM.json", program)
    write(OUT / "CHANGES.json", {"utc": datetime.now(timezone.utc).isoformat(),
          "normalization": changed, "current_sources": checkout, "program": program,
          "full6_snapshot_preserved": True, "original_deadlines_unchanged": True,
          "historical_v8_evidence_and_verdict_unchanged": True,
          "validation": "pending owner tests and next Full", "adopted": False})
    state_path = ROOT / "artifacts/comprobaciones/C03/RELEVO_ACTIVO.json"
    state = json.loads(state_path.read_text(encoding="utf-8"))
    state.update(confirmedAtUtc=datetime.now(timezone.utc).isoformat(),
                 workStatus="full6_failed_current_pin_repaired_744",
                 activeValidation=None, lastValidation={"name": "Full6/742", **result},
                 checkpoint="Full6 terminal exit1: .NET4574pass/0fail/1skip agregado; Python11398pass/1fail/3skip+466subtests. Único fallo es pin actual de __main__ anterior a740. Originales sidecar3s y packaging45s pasaron.744 normalizó LF de voice_aec y declaraciones STT, recalculó programa407 y actualizó sólo el pin actual V8. Evidencia histórica intacta; validación nueva pendiente. Encuesta26/716/0.",
                 continuation="Run 744 owner checks, preserve publication bytes, then next integrated Full before adopting the combined WIP.")
    write(state_path, state)
    print(json.dumps({"full6": result, "program": program, "source_changes": checkout}))


if __name__ == "__main__":
    main()

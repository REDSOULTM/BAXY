"""Refresh current declarations, retaining all historical campaign seals."""
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import shutil

ROOT = Path(__file__).resolve().parents[1]
ART = ROOT / "artifacts/comprobaciones/C03/astra-current-expectations531"
BACKUP = Path(os.environ["LOCALAPPDATA"]) / "BAXY/C03-current-expectations531-private"
BACKUP.mkdir(exist_ok=False)


def sha(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def backup(relative):
    source = ROOT / relative
    target = BACKUP / relative
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, target)
    return source


report = {"historical_campaigns_rewritten": False, "runtime_modified": False, "files": {}}
template_rel = "artifacts/comprobaciones/C03/astra-qwen-documented-profile/effective-template.jinja"
template = backup(template_rel)
original = template.read_bytes()
restored = original.replace(b"\r\n", b"\n")
comparison = json.loads((template.parent / "TEMPLATE_COMPARISON.json").read_text())
assert hashlib.sha256(restored).hexdigest() == comparison["effectiveTemplateSha256"]
assert hashlib.sha256(original).hexdigest() != comparison["effectiveTemplateSha256"]
template.write_bytes(restored)
report["template_restoration"] = {"path": template_rel, "before_sha256": hashlib.sha256(original).hexdigest(), "restored_sha256": sha(template), "historical_seal": comparison["effectiveTemplateSha256"]}
attributes = backup(".gitattributes")
with attributes.open("a", encoding="utf-8", newline="\n") as stream:
    stream.write("\n# C03 template restored to its published LF byte identity (531).\n/" + template_rel + " -text\n")

spec = importlib.util.spec_from_file_location("r281", ROOT / "experiments/mind_router_spike/attest_registered_runtime_r281.py")
runtime = importlib.util.module_from_spec(spec)
spec.loader.exec_module(runtime)
manifest = runtime.read_manifest()
for key, hash_key in (("gguf", "gguf_sha256"), ("llama_server", "llama_server_sha256")):
    actual_hash = sha(Path(manifest[key]))
    assert actual_hash == manifest[hash_key], key
    report[key + "_verified_sha256"] = actual_hash
expectation = backup("artifacts/runtime/registered_runtime_expectation_r281.json")
declared = json.loads(expectation.read_text(encoding="utf-8"))
old = declared["expected"]
current = runtime.describe(manifest)
changed = {key for key, value in current.items() if value != old.get(key)}
assert changed == {"ggufName", "ggufSha256"}, changed
report["runtime_declaration_delta"] = {key: {"before": old[key], "current": current[key]} for key in sorted(changed)}
declared["expected"] = current
declared["currentDeclarationEvidence"] = "C03 control892c506 and registered product521; refreshed531 after checking GGUF/server bytes. Candidate registration is not C03 acceptance."
expectation.write_text(json.dumps(declared, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")

v8 = backup("tests/test_price_v8_veto_damage_by_cause.py")
text = v8.read_text(encoding="utf-8")
old_hashes = {"src/baxy_mind/__main__.py": "6632507da4e1afe7765205ff675fb9ff9f0fff2eb0b0322f33ae2fd343530ed3", "src/baxy_mind/llm.py": "5c3db6952201a8099cf13992adb09e55cd895ed2db5a1f26041629d0b067e7fa"}
for relative, old_hash in old_hashes.items():
    current_hash = sha(ROOT / relative)
    assert text.count(old_hash) == 1
    text = text.replace(old_hash, current_hash)
    report["files"][relative] = {"old_current_pin": old_hash, "current_pin": current_hash}
text = text.replace("V8_PROGRAMS_REPLACED_BY_GOAL_03 = {", "# C03 531 pins source506/520/530: single chat route, quoted history, verified\n# status instructions and explanation boundaries. V8 evidence/numbers stay sealed.\nV8_PROGRAMS_REPLACED_BY_GOAL_03 = {", 1)
v8.write_text(text, encoding="utf-8", newline="\n")

# This is the existing current-tree recipe; historical preregistrations retain
# their independent pins, as test_stt_quality_evaluators already requires.
files = {}
for relative_root in ("experiments/voice_latency", "scripts", "src/baxy_mind"):
    for path in (ROOT / relative_root).rglob("*.py"):
        if path.is_file() and not path.is_symlink():
            files[path.relative_to(ROOT).as_posix()] = path
digest = hashlib.sha256()
for relative in sorted(files):
    digest.update(relative.encode("utf-8") + b"\n")
    digest.update(sha(files[relative]).encode("ascii") + b"\n")
tree_hash = digest.hexdigest()
for relative in ("experiments/stt_quality/evaluate_reserved_stt.py", "experiments/stt_quality/audit_fresh_postweight_stt_sources.py"):
    path = backup(relative)
    text = path.read_text(encoding="utf-8")
    pattern = r'(EXPECTED_PROGRAM_TREE_SHA256 = \(\s*")([a-f0-9]{64})("\s*\))'
    found = re.search(pattern, text)
    assert found
    report["files"][relative] = {"old_current_tree_pin": found[2], "current_tree_pin": tree_hash}
    text = re.sub(pattern, lambda match: match[1] + tree_hash + match[3], text, count=1)
    text = text.replace("EXPECTED_PROGRAM_TREE_SHA256 = (", "# C03 531: current program tree after sources506/520/530 and revalidation\n# adapter recovery handling. Historical STT/wake campaign pins remain unchanged;\n# this declaration does not claim new audio acceptance.\nEXPECTED_PROGRAM_TREE_SHA256 = (", 1)
    path.write_text(text, encoding="utf-8", newline="\n")
report["current_tree"] = {"sha256": tree_hash, "python_files": len(files)}
report["private_backup"] = str(BACKUP)
(ART / "DECLARATIONS.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print(json.dumps({"tree": report["current_tree"], "runtime_delta": sorted(changed), "template_restored": sha(template)}))

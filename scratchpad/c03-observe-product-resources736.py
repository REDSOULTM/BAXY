"""Separate actual server/app memory from launcher compilation in experiment736."""
from pathlib import Path
import argparse
import hashlib
import json
import os
import time

import psutil

parser = argparse.ArgumentParser()
parser.add_argument("model", choices=["k2", "qwen"])
args = parser.parse_args()
root = Path(__file__).resolve().parents[1]
out = root / "artifacts/comprobaciones/C03/NATIVE_PRODUCT736" / args.model
private = Path(os.environ["LOCALAPPDATA"]) / f"BAXY/C03-native-product736-{args.model}-private"
process = json.loads((out / "PROCESS.json").read_text(encoding="utf-8-sig"))
driver = psutil.Process(process["driver"])
assert "c03-native-product736.py" in " ".join(driver.cmdline())
created = driver.create_time()
target = private / "product-resource-samples.jsonl"
assert not target.exists()
started = time.monotonic()
peak_rss = peak_private = 0.0
samples = product_samples = 0
first_product = None
executables = {}

with target.open("w", encoding="utf-8") as output:
    while True:
        try:
            if driver.create_time() != created or not driver.is_running():
                break
            descendants = driver.children(recursive=True)
        except psutil.NoSuchProcess:
            break
        selected = {}
        app_seen = False
        for candidate in descendants:
            try:
                name = candidate.name().casefold()
                if candidate.pid == process["server"] or name == "baxy.exe":
                    app_seen |= name == "baxy.exe"
                    for child in [candidate, *candidate.children(recursive=True)]:
                        selected[child.pid] = child
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass
        rows = []
        for pid, candidate in selected.items():
            try:
                memory = candidate.memory_info()
                name = candidate.name()
                rows.append({"pid": pid, "name": name, "rss_mib": memory.rss/2**20,
                             "private_mib": getattr(memory, "private", 0)/2**20})
                if name.casefold() in {"baxy.exe", "baxy-core.exe"} and name not in executables:
                    executable = Path(candidate.exe())
                    with executable.open("rb") as stream:
                        digest = hashlib.file_digest(stream, "sha256").hexdigest()
                    executables[name] = {"path": str(executable), "sha256": digest}
            except (psutil.NoSuchProcess, psutil.AccessDenied, FileNotFoundError):
                pass
        rss, private_bytes = sum(r["rss_mib"] for r in rows), sum(r["private_mib"] for r in rows)
        if app_seen:
            first_product = first_product or time.monotonic()
            product_samples += 1
            peak_rss, peak_private = max(peak_rss, rss), max(peak_private, private_bytes)
        output.write(json.dumps({"time": time.monotonic(), "app_present": app_seen,
                                 "rss_mib": rss, "private_mib": private_bytes,
                                 "processes": rows}) + "\n")
        output.flush()
        samples += 1
        time.sleep(.25)

result = {"model": args.model, "samples": samples, "product_samples": product_samples,
    "server_and_product_peak_rss_mib": peak_rss, "server_and_product_peak_private_mib": peak_private,
    "seconds": time.monotonic()-started, "observed_executables": executables,
    "observer_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
    "scope": "Server plus actual Baxy.exe and its descendants while the app is present. Excludes launcher/build compilers. Sampled250ms; may miss briefer peaks. No visible UI/physical voice acceptance.",
    "started_before_app": first_product is None or first_product-started > .25}
(out / "PRODUCT_RESOURCES.json").write_text(json.dumps(result, indent=2)+"\n", encoding="utf-8")
print(json.dumps(result), flush=True)

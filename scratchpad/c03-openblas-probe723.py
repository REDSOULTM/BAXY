"""Test the documented OpenBLAS thread limit, independently of the reader API."""
from pathlib import Path

root = Path(__file__).resolve().parents[1]
source = (root / "scratchpad/c03-cold-dsp-probe719.py").read_text(encoding="utf-8")
source = source.replace("719", "723")
source = source.replace('("original", "deferred_warmup_only"):', '("original", "openblas1", "deferred_openblas1"):')
source = source.replace('if profile == "deferred_warmup_only":', 'if profile == "deferred_openblas1":')
source = source.replace('["original", "deferred_warmup_only"]', '["original", "openblas1", "deferred_openblas1"]')
source = source.replace('"Replace prepare_resampler only in the private child process, no source edits"',
                        '"Original, then OPENBLAS_NUM_THREADS=1, then defer warmup while retaining that limit; no source changes"')
marker = '        started = time.monotonic()'
source = source.replace(marker, '''        if profile == "original":
            environment.pop("OPENBLAS_NUM_THREADS", None)
        else:
            environment["OPENBLAS_NUM_THREADS"] = "1"
''' + marker)
marker = '            for pid, created in reversed(descendants):'
source = source.replace(marker, '''            write(OUT / (tag + "-DEADLINE.json"), {"elapsed": elapsed, "deadline": deadline,
                "timed_out": True, "stack_exit_code": stack_exit, "owned_descendants": descendants})
            if process.stdin is not None:
                process.stdin.close()
            for pid, created in reversed(descendants):''')
source = source.replace('except psutil.NoSuchProcess:', 'except (psutil.NoSuchProcess, psutil.TimeoutExpired):')
exec(compile(source, __file__, "exec"), {"__file__": __file__})

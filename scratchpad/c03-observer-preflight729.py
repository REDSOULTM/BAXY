"""Exercise the actual diagnostic hook with stub calls, outside product evidence."""
from pathlib import Path
import json
import os
import sys
import tempfile
import types


def verify_hook(path, expected_private):
    source = path.read_text(encoding="utf-8")
    literal = "BAXY/C03-status-batch729-private"
    assert source.count(literal) == 1
    assert expected_private == Path(os.environ["LOCALAPPDATA"]) / literal
    assert expected_private.is_dir(), "The real observer destination must exist before launch"
    probe = expected_private / "observer-write-probe.tmp"
    with probe.open("x", encoding="utf-8") as stream:
        stream.write("observer preflight\n")
    assert probe.read_text(encoding="utf-8") == "observer preflight\n"
    probe.unlink()

    calls = []
    result = {"sentinel": "original return object"}
    failure = RuntimeError("observer preflight original exception")

    class Stub:
        fail = False

        def _post(self, payload, *args, **kwargs):
            calls.append(("post", payload, args, kwargs))
            if self.fail:
                raise failure
            return result

        def decide_turn(self, text, candidates, *, history=None, evidence=None):
            calls.append(("decide", text, candidates, history, evidence))
            if self.fail:
                raise failure
            return result

    module_name = "baxy_mind.llm"
    old_module = sys.modules.get(module_name)
    module = types.ModuleType(module_name)
    module.LlmRuntime = Stub
    original_local = os.environ["LOCALAPPDATA"]
    with tempfile.TemporaryDirectory(prefix="c03-observer729-") as temporary:
        synthetic_private = Path(temporary) / literal
        synthetic_private.mkdir(parents=True)
        try:
            os.environ["LOCALAPPDATA"] = temporary
            sys.modules[module_name] = module
            namespace = {"__name__": "observer_preflight", "__file__": str(path)}
            exec(compile(source, str(path), "exec"), namespace)
            assert namespace["private"] == synthetic_private
            instance = Stub()
            payload, candidates, history, evidence = {"messages": []}, [], [], {}
            assert instance._post(payload, "positional", flag=True) is result
            assert instance.decide_turn("synthetic", candidates, history=history, evidence=evidence) is result
            instance.fail = True
            for invoke in (
                lambda: instance._post(payload, "positional", flag=True),
                lambda: instance.decide_turn("synthetic", candidates, history=history, evidence=evidence),
            ):
                try:
                    invoke()
                except RuntimeError as observed:
                    assert observed is failure
                else:
                    raise AssertionError("Observer swallowed the original exception")
            assert len(calls) == 4
            for call in (calls[0], calls[2]):
                assert call[1] is payload and call[2] == ("positional",) and call[3] == {"flag": True}
            for call in (calls[1], calls[3]):
                assert call[1] == "synthetic" and call[2] is candidates and call[3] is history and call[4] is evidence
            for filename, stages in {
                "http-posts.jsonl": ["request", "response", "request", "failure"],
                "decision-boundary.jsonl": ["input", "output", "input", "failure"],
            }.items():
                rows = [json.loads(line) for line in (synthetic_private / filename).read_text(encoding="utf-8").splitlines()]
                assert [row["stage"] for row in rows] == stages
                assert all(row["pid"] == os.getpid() for row in rows)
        finally:
            os.environ["LOCALAPPDATA"] = original_local
            if old_module is None:
                sys.modules.pop(module_name, None)
            else:
                sys.modules[module_name] = old_module
    assert not (expected_private / "http-posts.jsonl").exists()
    assert not (expected_private / "decision-boundary.jsonl").exists()
    return {
        "passed": True,
        "real_destination_exists_and_writable": True,
        "original_calls": 4,
        "same_arguments_return_objects_and_exceptions": True,
        "synthetic_records_separate_from_product": True,
    }

"""Run the exhaustive model gate against one continuously batched local server."""

from __future__ import annotations

import argparse
import json
import socket
import subprocess
import sys
import time
import urllib.request
from pathlib import Path
from collections import Counter


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.baxy_runtime_config import (  # noqa: E402
    RuntimeConfig,
    add_runtime_arguments,
    resolve_runtime_from_args_or_error,
)

LEDGER = ROOT / "artifacts" / "historical_exhaustive"


class SharedServerExited(RuntimeError):
    """Signals a resumable native llama-server termination."""


def free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def wait_ready(endpoint: str, process: subprocess.Popen[bytes], timeout: float) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if process.poll() is not None:
            raise SharedServerExited(
                f"shared llama-server exited with {process.returncode}"
            )
        try:
            with urllib.request.urlopen(f"{endpoint}/health", timeout=5) as response:
                if response.status == 200:
                    return
        except Exception:  # server is still loading
            time.sleep(1)
    raise TimeoutError("shared llama-server did not become ready")


def completed_rows(path: Path) -> int:
    if not path.exists():
        return 0
    with path.open("rb") as handle:
        return sum(1 for line in handle if line.strip())


def runtime_arguments_for_child(runtime: RuntimeConfig) -> list[str]:
    return [
        "--python",
        str(runtime.python),
        "--python-path",
        str(runtime.python_path),
        "--gguf",
        str(runtime.gguf),
        "--llama-server",
        str(runtime.llama_server),
        "--gpu-layers",
        str(runtime.gpu_layers),
    ]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--shards", type=int, default=4)
    parser.add_argument(
        "--workers",
        type=int,
        help="Maximum simultaneous shard processes; defaults to --shards.",
    )
    add_runtime_arguments(parser)
    parser.add_argument(
        "--ngl",
        dest="gpu_layers",
        type=int,
        help="Alias compatible de --gpu-layers.",
    )
    parser.add_argument("--slot-context", type=int, default=4096)
    parser.add_argument("--max-cases-per-shard", type=int)
    parser.add_argument("--case-id-file", type=Path)
    parser.add_argument("--oracle-family", action="append", default=[])
    parser.add_argument("--replay-failures-from", type=Path, action="append", default=[])
    parser.add_argument("--output-stem", default="runtime_model_gate")
    parser.add_argument("--merged-output", type=Path)
    parser.add_argument("--merged-summary-output", type=Path)
    parser.add_argument("--fresh", action="store_true")
    args = parser.parse_args()
    runtime = resolve_runtime_from_args_or_error(parser, args)
    if not 1 <= args.shards <= 16:
        raise ValueError("shards must be between 1 and 16")
    workers = args.shards if args.workers is None else args.workers
    if not 1 <= workers <= args.shards:
        raise ValueError("workers must be between 1 and shards")

    if not args.output_stem or any(character not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789._-" for character in args.output_stem):
        raise ValueError("output stem contains unsupported characters")
    outputs = [LEDGER / f"{args.output_stem}.shard{index}.jsonl" for index in range(args.shards)]
    summaries = [
        LEDGER / f"{args.output_stem}.shard{index}.checkpoint.json"
        for index in range(args.shards)
    ]
    logs = [
        (
            LEDGER / f"{args.output_stem}.shard{index}.stdout.log",
            LEDGER / f"{args.output_stem}.shard{index}.stderr.log",
        )
        for index in range(args.shards)
    ]
    server_stdout = LEDGER / "runtime_model_gate.server.stdout.log"
    server_stderr = LEDGER / "runtime_model_gate.server.stderr.log"
    if args.fresh:
        for path in [*outputs, *summaries, *(item for pair in logs for item in pair)]:
            path.unlink(missing_ok=True)
    LEDGER.mkdir(parents=True, exist_ok=True)

    port = free_port()
    endpoint = f"http://127.0.0.1:{port}"
    children: list[subprocess.Popen[bytes]] = []
    handles = []
    server: subprocess.Popen[bytes] | None = None
    try:
        server_out_handle = server_stdout.open("wb")
        server_err_handle = server_stderr.open("wb")
        handles.extend((server_out_handle, server_err_handle))
        server = subprocess.Popen(
            [
                str(runtime.llama_server),
                "-m", str(runtime.gguf),
                "--host", "127.0.0.1",
                "--port", str(port),
                "-ngl", str(runtime.gpu_layers),
                "-c", str(args.slot_context * workers),
                "--parallel", str(workers),
                "--cont-batching",
                "--jinja",
            ],
            cwd=ROOT,
            stdout=server_out_handle,
            stderr=server_err_handle,
        )
        wait_ready(endpoint, server, 420)
        print(
            json.dumps(
                {"server_ready": endpoint, "slots": workers, "shards": args.shards}
            ),
            flush=True,
        )

        def start_child(index: int) -> subprocess.Popen[bytes]:
            stdout_path, stderr_path = logs[index]
            stdout_handle = stdout_path.open("ab")
            stderr_handle = stderr_path.open("ab")
            handles.extend((stdout_handle, stderr_handle))
            command = [
                str(runtime.python),
                "-u",
                "scripts/run_exhaustive_runtime_model_gate.py",
                *runtime_arguments_for_child(runtime),
                "--llm-endpoint", endpoint,
                "--shard-count", str(args.shards),
                "--shard-index", str(index),
                "--output", str(outputs[index]),
                "--summary-output", str(summaries[index]),
            ]
            if args.fresh:
                command.append("--fresh")
            if args.max_cases_per_shard is not None:
                command.extend(("--max-cases", str(args.max_cases_per_shard)))
            if args.case_id_file is not None:
                command.extend(("--case-id-file", str(args.case_id_file)))
            for family in args.oracle_family:
                command.extend(("--oracle-family", family))
            for replay_path in args.replay_failures_from:
                command.extend(("--replay-failures-from", str(replay_path)))
            process = subprocess.Popen(
                command,
                cwd=ROOT,
                stdout=stdout_handle,
                stderr=stderr_handle,
            )
            children.append(process)
            return process

        pending = list(range(args.shards))
        running: dict[int, subprocess.Popen[bytes]] = {}
        exit_codes: list[int | None] = [None] * args.shards
        while pending and len(running) < workers:
            index = pending.pop(0)
            running[index] = start_child(index)
        last_total = -1
        while running:
            if server.poll() is not None:
                raise SharedServerExited(
                    f"shared llama-server exited during replay ({server.returncode})"
                )
            for index, process in list(running.items()):
                code = process.poll()
                if code is None:
                    continue
                exit_codes[index] = code
                del running[index]
                if pending:
                    next_index = pending.pop(0)
                    running[next_index] = start_child(next_index)
            total = sum(completed_rows(path) for path in outputs)
            if total != last_total:
                print(
                    json.dumps(
                        {
                            "completed_rows": total,
                            "shard_rows": [completed_rows(path) for path in outputs],
                        }
                    ),
                    flush=True,
                )
                last_total = total
            time.sleep(10)

        if any(code is None for code in exit_codes):
            raise RuntimeError("one or more shard processes did not report an exit code")
        completed_exit_codes = [int(code) for code in exit_codes]
        selected_replay = (
            args.case_id_file is not None
            or bool(args.replay_failures_from)
            or bool(args.oracle_family)
        )
        if selected_replay:
            statuses = Counter()
            selected_rows = 0
            for path in outputs:
                if not path.exists():
                    continue
                with path.open(encoding="utf-8") as handle:
                    for line in handle:
                        if not line.strip():
                            continue
                        row = json.loads(line)
                        statuses[str(row.get("status") or "unknown")] += 1
                        selected_rows += 1
            print(
                json.dumps(
                    {
                        "selected_replay_completed": selected_rows,
                        "status_counts": dict(sorted(statuses.items())),
                        "exit_codes": completed_exit_codes,
                    },
                    ensure_ascii=False,
                ),
                flush=True,
            )
            return 0 if all(code in {0, 3} for code in completed_exit_codes) else 1
        if args.max_cases_per_shard is not None:
            print(json.dumps({"smoke_exit_codes": completed_exit_codes}), flush=True)
            return 0 if all(code in {0, 2, 3} for code in completed_exit_codes) else 1
        if any(code not in {0, 3} for code in completed_exit_codes):
            raise RuntimeError(f"model gate shard failures: {completed_exit_codes}")
        merge_command = [
            sys.executable,
            "scripts/merge_exhaustive_runtime_model_gate.py",
            *(str(path) for path in outputs),
        ]
        if args.merged_output is not None:
            merge_command.extend(("--output", str(args.merged_output)))
        if args.merged_summary_output is not None:
            merge_command.extend(("--summary-output", str(args.merged_summary_output)))
        merge = subprocess.run(
            merge_command,
            cwd=ROOT,
            check=False,
        )
        return merge.returncode
    finally:
        for child in children:
            if child.poll() is None:
                child.kill()
        for child in children:
            try:
                child.wait(timeout=15)
            except subprocess.TimeoutExpired:
                pass
        if server is not None and server.poll() is None:
            server.kill()
            try:
                server.wait(timeout=15)
            except subprocess.TimeoutExpired:
                pass
        for handle in handles:
            handle.close()


if __name__ == "__main__":
    try:
        exit_code = main()
    except SharedServerExited as error:
        print(str(error), file=sys.stderr, flush=True)
        exit_code = 75
    raise SystemExit(exit_code)

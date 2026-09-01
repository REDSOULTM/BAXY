"""Configuración común de ONNX Runtime para inferencia local continua."""

from __future__ import annotations

from collections.abc import Callable
import threading
from typing import Any, TypeVar


_T = TypeVar("_T")
_SESSION_CREATION_LOCK = threading.Lock()


def _configure_session_options(options: Any, runtime: Any) -> Any:
    """Use one blocking worker for small, latency-sensitive local models."""

    options.intra_op_num_threads = 1
    options.inter_op_num_threads = 1
    options.execution_mode = runtime.ExecutionMode.ORT_SEQUENTIAL
    options.add_session_config_entry("session.intra_op.allow_spinning", "0")
    options.add_session_config_entry("session.inter_op.allow_spinning", "0")
    return options


def create_with_power_efficient_onnx(factory: Callable[[], _T]) -> _T:
    """Create third-party ONNX sessions without permanently patching the runtime.

    LiveKit WakeWord and Silero do not expose ``SessionOptions`` at their public
    construction boundary.  Their model creation is synchronous, so this narrow
    adapter supplies the options only while that factory runs and restores the
    process-wide constructor in ``finally``.
    """

    import onnxruntime as runtime

    with _SESSION_CREATION_LOCK:
        original = runtime.InferenceSession

        def configured_session(*args: Any, **kwargs: Any) -> Any:
            mutable_args = list(args)
            if kwargs.get("sess_options") is not None:
                _configure_session_options(kwargs["sess_options"], runtime)
            elif len(mutable_args) > 1 and mutable_args[1] is not None:
                _configure_session_options(mutable_args[1], runtime)
            else:
                options = _configure_session_options(runtime.SessionOptions(), runtime)
                if len(mutable_args) > 1:
                    mutable_args[1] = options
                else:
                    kwargs["sess_options"] = options
            return original(*mutable_args, **kwargs)

        runtime.InferenceSession = configured_session
        try:
            return factory()
        finally:
            runtime.InferenceSession = original

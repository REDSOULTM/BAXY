from pathlib import Path
import ast

root = Path(__file__).resolve().parents[1]
p = root/'src/baxy_mind/voice_aec.py'
s = p.read_text(encoding='utf-8')
n = next(n for n in ast.parse(s).body if isinstance(n,ast.ClassDef) and n.name=='LoopbackReference')
lines = s.splitlines(keepends=True)
replacement = (root/'scratchpad/c03-reference143-class.txt').read_text(encoding='utf-8')
lines[n.lineno-1:n.end_lineno] = [replacement+'\n']
s = ''.join(lines).replace('import logging\n','import logging\nimport math\n').replace('import threading\n','import threading\nimport time\n')
s = s.replace('_RING_SECONDS = 35','_RING_SECONDS = 4')
ast.parse(s)
p.write_text(s,encoding='utf-8')

p = root/'src/baxy_mind/voice.py'
s = p.read_text(encoding='utf-8')
def change(old,new,count=1):
    global s
    assert s.count(old)==count,(old,s.count(old))
    s=s.replace(old,new)
change('from .voice_aec import AudioDucker, LoopbackReference', 'from .voice_aec import AudioDucker, LoopbackReference\nfrom .voice_capture import WasapiCaptureStream')
change('        canceller: EchoCanceller | None = None\n', '        canceller: EchoCanceller | None = None\n        reference_cursor: int | None = None\n')
change('            if self._loopback.active and resolve_echo_canceller_library() is not None:', '''            inbox = self._pcm_inbox
            if (
                inbox is None and self._loopback.active
                and resolve_echo_canceller_library() is not None
            ):''')
change('            inbox = self._pcm_inbox\n            stream_context = (', '            stream_context = (')
change('''                else sd.InputStream(
                    samplerate=SAMPLE_RATE,
                    channels=1,
                    dtype="float32",
                    blocksize=VAD_WINDOW_SAMPLES,
                )''','''                else WasapiCaptureStream(event)''')
change('''                    if overflowed:
                        self._emit("warning", code="input_overflow")
                    mono = frame.reshape(-1).astype(np.float32)
                    history = self._loopback.latest(REFERENCE_SAMPLES)
                    if canceller is not None:
                        mono, echo_microphone, echo_reference = canceller.process(
                            mono, history
                        )
                    else:
                        echo_microphone, echo_reference = mono * 32768.0, history''','''                    if event.is_set():
                        break
                    if overflowed:
                        raise RuntimeError("input_overflow")
                    mono = frame.reshape(-1).astype(np.float32)
                    if canceller is not None:
                        if reference_cursor is None:
                            reference_cursor = self._loopback.sample_index(
                                stream.adc_time, event
                            )
                        reference_cursor += VAD_WINDOW_SAMPLES
                        history = self._loopback.window_at(
                            reference_cursor, REFERENCE_SAMPLES, event
                        )
                        mono, echo_microphone, echo_reference = canceller.process(
                            mono, history
                        )
                    else:
                        history = (
                            self._loopback.latest(REFERENCE_SAMPLES)
                            if inbox is None else np.zeros(REFERENCE_SAMPLES, np.int16)
                        )
                        echo_microphone, echo_reference = mono * 32768.0, history''')
change('''        except Exception as error:  # noqa: BLE001 - voz nunca tumba la mente
            if self._session_is_current(session_epoch):''','''        except Exception as error:  # noqa: BLE001 - voz nunca tumba la mente
            cancelled = isinstance(error, InterruptedError) and event.is_set()
            if not cancelled and self._session_is_current(session_epoch):''')
ast.parse(s)
p.write_text(s,encoding='utf-8')

p = root/'tests/test_mind_voice_runtime.py'
s = p.read_text(encoding='utf-8')
needle='    monkeypatch.setitem(sys.modules, "sounddevice", sounddevice)\n'
assert s.count(needle)==1
s=s.replace(needle,needle+'''    monkeypatch.setattr(
        voice_module, "WasapiCaptureStream",
        lambda _event: factory(
            samplerate=SAMPLE_RATE, channels=1, dtype="float32", blocksize=512
        ),
    )
''')
needle='    class Stream(_FiniteInputStream):\n'
assert s.count(needle)==1
s=s.replace(needle,needle+'        adc_time = 100.0\n\n')
needle='    monkeypatch.setattr(voice_module, "EchoCanceller", Canceller)\n'
assert s.count(needle)==1
s=s.replace(needle,needle+'''    monkeypatch.setattr(engine._loopback, "sample_index", lambda _time, _event: 0)  # noqa: SLF001
    monkeypatch.setattr(engine._loopback, "window_at", lambda _end, count, _event: np.zeros(count, np.int16))  # noqa: SLF001
''')
ast.parse(s)
p.write_text(s,encoding='utf-8')
print('143 source and device-lifecycle fixtures integrated; validation pending.')

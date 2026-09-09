from pathlib import Path
import hashlib

root = Path(__file__).resolve().parents[1]
path = root / 'src/baxy_mind/voice_output.py'
assert hashlib.sha256(path.read_bytes()).hexdigest() == '979ed2bd0cad5d8762633bf85c6591fbf66ffdd99bf49f71ca3737a7dd61aeaa'
text = path.read_text(encoding='utf-8')
start, end = text.index('def _espeak_exe()'), text.index('class NeuralSpeechOutput:')
text = text[:start] + text[end:]
text = text.replace('import hashlib\n', '').replace('import json\n', '')
text = text.replace('from .assets import AssetDescriptorError, resolve_asset\n',
    'from .piper_tts import (\n    PiperEngine,\n    neural_tts_identity,\n    resolve_neural_tts_model,\n    resolve_piper_executable,\n)\nfrom .request_reading import spoken_language\n')
text = text.replace('La voz de producto es neural, español latino (Piper ``es_MX-claude-high``\nvía sherpa-onnx, Apache 2.0 + pesos MIT). SAPI queda como degradación si\nel modelo neural no está en disco.',
    'La voz de producto usa Piper local y una voz por idioma. El proveedor completo\nconserva el contrato de fonemas y oraciones; SAPI queda como degradación si\nlos activos neurales no están disponibles.')
text = text.replace('        self._voice_name = "es_MX-claude-high"\n',
    '        self._voice_name = "es_MX-claude-high"\n        self._voice_sha256: str | None = None\n')
needle = '    def start(self, timeout: float = 8.0) -> bool:\n'
offset = text.index(needle, text.index('class NeuralSpeechOutput:'))
text = text[:offset] + '    @property\n    def voice_sha256(self) -> str | None:\n        return self._voice_sha256\n\n' + text[offset:]
text = text.replace('            tts = _PiperOnnxEngine(model_path)', '            tts = PiperEngine(model_path)')
text = text.replace('            self._voice_name = model_path.stem\n',
    '            self._voice_name = model_path.stem\n            self._voice_sha256 = (tts.identity or (None, None))[1]\n')
needle = '        try:\n            while self._available and tts is not None and not self._shutdown.is_set():'
text = text.replace(needle, '        engines = {"es": tts}\n' + needle)
text = text.replace('                    waveform = tts.generate(item.text)', '''                    language = spoken_language(item.text)
                    selected = engines.get(language)
                    if selected is None:
                        selected_path = resolve_neural_tts_model(language)
                        if selected_path is None:
                            raise FileNotFoundError("tts_language_voice_missing")
                        selected = PiperEngine(selected_path)
                        engines[language] = selected
                    sample_rate = selected.sample_rate
                    self._model_path = selected._model_path
                    self._voice_name = self._model_path.stem
                    self._voice_sha256 = (selected.identity or (None, None))[1]
                    waveform = selected.generate(
                        item.text, cancelled=lambda: self._command_cancelled(item.generation)
                    )''')
needle = '                except Exception as error:  # noqa: BLE001\n                    self.last_error = f"tts_failed:{type(error).__name__}"'
text = text.replace(needle, '''                except InterruptedError:
                    if not self._command_cancelled(item.generation):
                        self.last_error = "tts_failed:InterruptedError"
                except Exception as error:  # noqa: BLE001
                    self.last_error = f"tts_failed:{type(error).__name__}"''')
text = text.replace('_espeak_exe() is not None', 'resolve_piper_executable() is not None')
path.write_text(text, encoding='utf-8', newline='\n')
for relative in ('scripts/measure_goal09_voice.py', 'tests/test_goal09_voice_engines.py'):
    path = root / relative
    text = path.read_text(encoding='utf-8')
    text = text.replace('from baxy_mind.voice_output import _PiperOnnxEngine', 'from baxy_mind.piper_tts import PiperEngine')
    text = text.replace('_PiperOnnxEngine(model_path)', 'PiperEngine(model_path)')
    text = text.replace('_espeak_exe', 'resolve_piper_executable').replace('eSpeak NG is not on this machine', 'Piper runtime is not on this machine')
    path.write_text(text, encoding='utf-8', newline='\n')
path = root / 'src/baxy_mind/voice.py'
text = path.read_text(encoding='utf-8').replace('    neural_tts_identity,\n', '    resolve_piper_executable,\n')
text = text.replace('bool(dependencies.get("sherpa_onnx") and resolve_neural_tts_model())',
    'bool(resolve_piper_executable() and resolve_neural_tts_model())')
text = text.replace('(neural_tts_identity() or (None, None))[1]', 'getattr(self._output, "voice_sha256", None)')
path.write_text(text, encoding='utf-8', newline='\n')
print('Manual frontend removed; Piper provider integrated; ownership and language selection connected.')

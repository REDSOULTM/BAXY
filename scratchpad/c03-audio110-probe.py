"""Read hardware routing only; does not open a stream or alter volume."""
from pathlib import Path
import json
import sys

root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(root / 'src'))
import sounddevice as sd
import pyaudiowpatch as pyaudio
from baxy_mind.voice_aec import AudioDucker, _com_apartment

with _com_apartment():
    endpoint = AudioDucker._endpoint()
    volume = {'levelScalar':endpoint.GetMasterVolumeLevelScalar(), 'muted':bool(endpoint.GetMute())}
with pyaudio.PyAudio() as audio:
    loopback = audio.get_default_wasapi_loopback()
report = {'sounddeviceVersion':sd.__version__,
    'defaultInput':sd.query_devices(kind='input'),
    'defaultOutput':sd.query_devices(kind='output'),
    'defaultDeviceIds':list(sd.default.device),
    'loopback':loopback, 'volume':volume}
print(json.dumps(report, ensure_ascii=False, indent=2))

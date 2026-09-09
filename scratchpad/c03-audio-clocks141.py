"""Inspect native callback clocks only; no PCM retained, playback or volume change."""
from pathlib import Path
import json
import time
import numpy as np
import sounddevice as sd
import pyaudiowpatch as pa

root = Path(__file__).resolve().parents[1]
out = root/'artifacts/comprobaciones/C03/astra-clocks141'
out.mkdir(exist_ok=False)
mic_rows = np.zeros((256,5),dtype=np.float64)
loop_rows = np.zeros((256,5),dtype=np.float64)
counts = {'mic':0,'loop':0}

def mic_callback(_data, frames, timing, status):
    index = counts['mic']
    if index < len(mic_rows):
        mic_rows[index] = (time.perf_counter(), timing.inputBufferAdcTime,
                           timing.currentTime, frames, bool(status))
        counts['mic'] += 1

def loop_callback(_data, frames, timing, status):
    index = counts['loop']
    if index < len(loop_rows):
        loop_rows[index] = (time.perf_counter(), timing['input_buffer_adc_time'],
                            timing['current_time'], frames, bool(status))
        counts['loop'] += 1
    return None, pa.paContinue

with pa.PyAudio() as backend:
    device = backend.get_default_wasapi_loopback()
    rate = int(device['defaultSampleRate'])
    loop = backend.open(format=pa.paInt16,channels=int(device['maxInputChannels']),
        rate=rate,input=True,input_device_index=device['index'],frames_per_buffer=int(rate*.032),
        stream_callback=loop_callback)
    try:
        with sd.InputStream(samplerate=16000,channels=1,dtype='float32',blocksize=512,
                            callback=mic_callback) as mic:
            time.sleep(3.5)
            metadata = {'micLatency':mic.latency,'loopLatency':loop.get_input_latency(),
                        'micStreamClock':mic.time,'loopStreamClock':loop.get_time(),
                        'micDevice':str(sd.query_devices(mic.device,kind='input')['name']),
                        'loopDevice':device['name'],'micRate':16000,'loopRate':rate}
    finally:
        loop.stop_stream(); loop.close()
rows = {'microphone':mic_rows[:counts['mic']].tolist(), 'loopback':loop_rows[:counts['loop']].tolist()}
metadata.update(columns=['perfCounter','inputBufferAdcTime','currentTime','frames','anyStatus'],
                method='Diagnostic native callbacks; clocks only, no PCM retained/playback/volume change.',rows=rows)
(out/'RESULTS.json').write_text(json.dumps(metadata,indent=2),encoding='utf-8')
summary = {k:v for k,v in metadata.items() if k != 'rows'}
summary['clocks'] = {}
for name, values in rows.items():
    a = np.array(values)
    summary['clocks'][name] = {'callbacks':len(a),'adcNonzero':int(np.count_nonzero(a[:,1])),
        'adcStepQuantiles':np.quantile(np.diff(a[:,1]),[0,.5,1]).tolist(),
        'currentMinusAdcQuantiles':np.quantile(a[:,2]-a[:,1],[0,.5,1]).tolist(),
        'perfMinusCurrentQuantiles':np.quantile(a[:,0]-a[:,2],[0,.5,1]).tolist(),
        'statusCount':int(np.count_nonzero(a[:,4]))}
(out/'SUMMARY.json').write_text(json.dumps(summary,indent=2),encoding='utf-8')
print(json.dumps(summary,indent=2))

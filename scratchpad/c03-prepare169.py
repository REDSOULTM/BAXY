from pathlib import Path
import json

root=Path(__file__).resolve().parents[1]
base=root/'artifacts/comprobaciones/C03'
out=base/'astra-sidecar169'
out.mkdir(exist_ok=False)
prereg=json.loads((base/'astra-sidecar168/PREREG.json').read_text(encoding='utf-8'))
prereg['method']='Same fullsidecar168, texts and physical configuration. Sole new observation: at first barge_in event, AFTER cancel_speech has already been called, copy caller audio arrays and current loopback ring/clock metadata. No work added per captured frame, no changed decisions/thresholds. Original event forwarded first. No inference acceptance; inspect the exact false-interruption frame. Later outputs may be perturbed by this one snapshot and are not comparable controls.'
(out/'PREREG.json').write_text(json.dumps(prereg,indent=2,ensure_ascii=False),encoding='utf-8')
for name in ['c03-capture168.py','c03-sidecar168.py','c03-sidecar168-entry.py']:
    text=(root/'scratchpad'/name).read_text(encoding='utf-8').replace('168','169')
    if name.endswith('-entry.py'):
        observation='''
import inspect
import numpy as np
from baxy_mind.voice import VoiceEngine

original_emit = VoiceEngine._emit
observed_barge = False
def observe_emit(self, event, **fields):
    global observed_barge
    original_emit(self, event, **fields)
    if event != 'barge_in' or observed_barge:
        return
    observed_barge = True
    caller = inspect.currentframe().f_back
    try:
        values = caller.f_locals
        arrays = {name: np.asarray(values[name]).copy() for name in ('mono', 'echo_microphone', 'echo_reference', 'history', 'frame')}
        metadata = {'time': time.monotonic(), 'caller': caller.f_code.co_name, 'referenceCursor': values['reference_cursor'], 'micAdcTime': values['stream'].adc_time, 'probability': float(values['probability']), 'energy': float(values['energy']), 'noiseFloor': float(values['noise_floor']), 'bargeFrames': values['barge_frames']}
        with self._loopback._condition:
            arrays['loopback_ring'] = self._loopback._ring.copy()
            metadata.update(loopbackWritten=self._loopback._written, loopbackOrigin=self._loopback._origin_time, loopbackError=self._loopback.last_error)
        np.savez(private/'barge169.npz', **arrays)
        (private/'barge169.json').write_text(json.dumps(metadata,indent=2),encoding='utf-8')
    finally:
        del caller
VoiceEngine._emit = observe_emit
'''
        text=text.replace("with (private/'stacks169.log')",observation+"\nwith (private/'stacks169.log')")
    with (root/'scratchpad'/name.replace('168','169')).open('x',encoding='utf-8') as f:
        f.write(text)
with (base/'ASTRA-TRAMO-166_168.md').open('a',encoding='utf-8') as f:
    f.write('''

168 terminado: driver81611 y captura99840 exit0, cierre propio69,266s;
captura91,31s con restauración exacta. Greeting4,781s sinbarge; ES10:55 dura1,516s
con1barge; EN10:56 dura2,907s sinbarge; ES10:56 dura0,938s con2eventosbarge.
Todos cambios a speakingFalse reportan errorTTS null. La interrupción, no un
deadlineTTS observado, explica dos de cuatro salidas en esta reproducción.
No extender esa atribución a todas las salidas166 sin su evento interno.
169 prepara snapshot sólo tras la primera decisión de cancelar: arrays locales,
ring y relojes. Evita los taps porframe que antes coincidían con desaparición
del fallo. Producto164 intacto; sin procesos propios antes del arranque169.
''')
print('169 preregistered. No source mutation; snapshot only after first barge decision.')

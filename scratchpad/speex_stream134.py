"""Experimental single-owner streaming AEC; not imported by product source."""
import ctypes as c
import numpy as np


class SpeexStream:
    def __init__(self, path):
        self.lib = c.CDLL(str(path))
        self.ptr = c.POINTER(c.c_int16)
        for name, args, result in [
            ('speex_echo_state_init', [c.c_int, c.c_int], c.c_void_p),
            ('speex_echo_state_destroy', [c.c_void_p], None),
            ('speex_echo_cancellation', [c.c_void_p, self.ptr, self.ptr, self.ptr], None),
            ('speex_echo_ctl', [c.c_void_p, c.c_int, c.c_void_p], c.c_int),
            ('speex_preprocess_state_init', [c.c_int, c.c_int], c.c_void_p),
            ('speex_preprocess_state_destroy', [c.c_void_p], None),
            ('speex_preprocess_run', [c.c_void_p, self.ptr], c.c_int),
            ('speex_preprocess_ctl', [c.c_void_p, c.c_int, c.c_void_p], c.c_int),
        ]:
            function = getattr(self.lib, name)
            function.argtypes, function.restype = args, result
        self.state = self.lib.speex_echo_state_init(512, 3200)
        self.pre = self.lib.speex_preprocess_state_init(512, 16000)
        assert self.state and self.pre
        rate = c.c_int(16000)
        assert self.lib.speex_echo_ctl(self.state, 24, c.byref(rate)) == 0
        assert self.lib.speex_preprocess_ctl(self.pre, 24, self.state) == 0

    def process(self, microphone, reference):
        assert microphone.size == reference.size == 512
        mic = np.clip(microphone * 32768, -32768, 32767).astype(np.int16)
        ref = np.clip(reference, -32768, 32767).astype(np.int16)
        clean = np.empty(512, dtype=np.int16)
        self.lib.speex_echo_cancellation(self.state, mic.ctypes.data_as(self.ptr), ref.ctypes.data_as(self.ptr), clean.ctypes.data_as(self.ptr))
        self.lib.speex_preprocess_run(self.pre, clean.ctypes.data_as(self.ptr))
        return clean.astype(np.float32) / 32768

    def close(self):
        if self.pre:
            self.lib.speex_preprocess_state_destroy(self.pre)
            self.pre = None
        if self.state:
            self.lib.speex_echo_state_destroy(self.state)
            self.state = None

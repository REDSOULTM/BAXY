"""Minimal ``espeak-ng --ipa`` bridge for the wake-word feasibility study.

The official LiveKit data generator invokes the eSpeak NG command-line
program only to obtain IPA phonemes.  On Windows, ``espeakng-loader`` ships a
portable DLL and its data files but no executable.  This adapter exposes the
small command surface the generator needs without installing or changing a
machine-wide eSpeak runtime.

It is experimental infrastructure, not part of the BAXY product runtime.
"""

from __future__ import annotations

import argparse
import ctypes
import sys
from collections.abc import Sequence


def _parse_args(argv: Sequence[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="espeak-ng")
    parser.add_argument("--ipa", action="store_true", required=True)
    parser.add_argument("-q", "--quiet", action="store_true")
    parser.add_argument("-v", "--voice", default="en-us")
    parser.add_argument("text", nargs="+")
    return parser.parse_args(argv)


def _phonemize(text: str, voice: str) -> str:
    import espeakng_loader

    library = ctypes.CDLL(espeakng_loader.get_library_path())
    library.espeak_Initialize.argtypes = [
        ctypes.c_int,
        ctypes.c_int,
        ctypes.c_char_p,
        ctypes.c_int,
    ]
    library.espeak_Initialize.restype = ctypes.c_int
    library.espeak_SetVoiceByName.argtypes = [ctypes.c_char_p]
    library.espeak_SetVoiceByName.restype = ctypes.c_int
    library.espeak_TextToPhonemes.argtypes = [
        ctypes.POINTER(ctypes.c_char_p),
        ctypes.c_int,
        ctypes.c_int,
    ]
    library.espeak_TextToPhonemes.restype = ctypes.c_char_p

    data_path = espeakng_loader.get_data_path().encode("utf-8")
    if library.espeak_Initialize(2, 0, data_path, 0) <= 0:
        raise RuntimeError("eSpeak NG could not initialize its portable data")

    try:
        if library.espeak_SetVoiceByName(voice.encode("utf-8")) != 0:
            raise RuntimeError(f"eSpeak NG voice is unavailable: {voice}")

        text_pointer = ctypes.pointer(ctypes.c_char_p(text.encode("utf-8")))
        parts: list[str] = []
        while text_pointer.contents.value is not None:
            phonemes = library.espeak_TextToPhonemes(text_pointer, 1, 2)
            if phonemes:
                parts.append(phonemes.decode("utf-8"))
        return " ".join(parts)
    finally:
        library.espeak_Terminate()


def main(argv: Sequence[str] | None = None) -> int:
    args = _parse_args(argv if argv is not None else sys.argv[1:])
    phonemes = _phonemize(" ".join(args.text), args.voice)
    sys.stdout.buffer.write((phonemes + "\n").encode("utf-8"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

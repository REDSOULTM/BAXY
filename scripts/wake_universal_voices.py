"""Curated list of Piper voices for the universal wake-word eval set.

Goal: cover ≥7 languages and ≥30 voices with no overlap to the v9 training
set (which used only Spanish voices: es_AR-daniela, es_ES-davefx,
es_ES-carlfm, es_MX-claude, es_ES-mls_10246, es_ES-mls_9972,
es_ES-sharvard). Voices below are HELD OUT — none were in training.

Each entry is (lang_code, voice_name, quality). The download URL pattern
is:
  https://huggingface.co/rhasspy/piper-voices/resolve/main/<lang_path>/<voice_name>.onnx
  https://huggingface.co/rhasspy/piper-voices/resolve/main/<lang_path>/<voice_name>.onnx.json

lang_path follows Piper's HF repo layout: <lang>/<locale>/<speaker>/<quality>/
We synthesise the path from the voice_name which always encodes locale +
speaker + quality (e.g. en_US-amy-medium → en/en_US/amy/medium/).
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class PiperVoiceSpec:
    lang: str          # short tag for our analysis (es, en, fr, ...)
    voice_name: str    # filename stem (e.g. "en_US-amy-medium")

    @property
    def filename(self) -> str:
        return f"{self.voice_name}.onnx"

    @property
    def config_filename(self) -> str:
        return f"{self.voice_name}.onnx.json"

    @property
    def hf_dir(self) -> str:
        # Parse: locale-speaker-quality  (locale may be xx or xx_YY)
        parts = self.voice_name.split("-")
        if len(parts) != 3:
            raise ValueError(f"Unexpected voice name: {self.voice_name}")
        locale, speaker, quality = parts
        lang_short = locale.split("_")[0]
        return f"{lang_short}/{locale}/{speaker}/{quality}"


# Voices held out from v9 training. Curated for coverage of phonologies
# that might pronounce "hey gemma" differently:
#   - Germanic (en, de, nl, sv)
#   - Romance other than ES (fr, it, pt)
#   - Slavic (pl, ru)
#   - Asian (zh, ja, vi)
#   - Semitic (ar)
# Plus a Spanish variant NOT in training (es_AR-other speaker) to test
# in-language generalization.
HELD_OUT_VOICES: tuple[PiperVoiceSpec, ...] = (
    # English (5 voices, mix of accents + genders)
    PiperVoiceSpec("en", "en_US-amy-medium"),
    PiperVoiceSpec("en", "en_US-libritts_r-medium"),
    PiperVoiceSpec("en", "en_US-ryan-high"),
    PiperVoiceSpec("en", "en_GB-alan-medium"),
    PiperVoiceSpec("en", "en_GB-jenny_dioco-medium"),
    # German (3)
    PiperVoiceSpec("de", "de_DE-thorsten-medium"),
    PiperVoiceSpec("de", "de_DE-eva_k-x_low"),
    PiperVoiceSpec("de", "de_DE-karlsson-low"),
    # French (3)
    PiperVoiceSpec("fr", "fr_FR-siwis-medium"),
    PiperVoiceSpec("fr", "fr_FR-tom-medium"),
    PiperVoiceSpec("fr", "fr_FR-upmc-medium"),
    # Italian (2)
    PiperVoiceSpec("it", "it_IT-riccardo-x_low"),
    PiperVoiceSpec("it", "it_IT-paola-medium"),
    # Portuguese (2)
    PiperVoiceSpec("pt", "pt_BR-faber-medium"),
    PiperVoiceSpec("pt", "pt_BR-edresson-low"),
    # Polish (2)
    PiperVoiceSpec("pl", "pl_PL-darkman-medium"),
    PiperVoiceSpec("pl", "pl_PL-gosia-medium"),
    # Russian (2)
    PiperVoiceSpec("ru", "ru_RU-denis-medium"),
    PiperVoiceSpec("ru", "ru_RU-irina-medium"),
    # Mandarin (1) — challenging phonology for "hey gemma"
    PiperVoiceSpec("zh", "zh_CN-huayan-medium"),
    # Vietnamese (1) — tonal language stress test
    PiperVoiceSpec("vi", "vi_VN-vais1000-medium"),
    # Arabic (1) — non-IE phonology
    PiperVoiceSpec("ar", "ar_JO-kareem-medium"),
    # Dutch (1)
    PiperVoiceSpec("nl", "nl_NL-mls_5809-low"),
    # Swedish (1)
    PiperVoiceSpec("sv", "sv_SE-nst-medium"),
    # Spanish — speakers NOT in training set
    PiperVoiceSpec("es", "es_AR-daniela-high"),  # in training, keep as sanity check
)


def base_url(spec: PiperVoiceSpec, kind: str) -> str:
    """kind is 'onnx' or 'onnx.json'."""
    fname = spec.filename if kind == "onnx" else spec.config_filename
    return (
        "https://huggingface.co/rhasspy/piper-voices/resolve/main/"
        f"{spec.hf_dir}/{fname}"
    )

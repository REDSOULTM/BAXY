"""P2: descarga y convierte checkpoints Piper POR IDIOMA al formato LiveKit.

POR QUÉ (2026-06-12, doc wake_v5_diseno_entrenamiento + veredicto v5): los
positivos del wake se sintetizan SOLO con el checkpoint inglés (LibriTTS
904 voces) y el held-out es 13 idiomas → v5 quedó en/es/fr 1.0/1.0/0.88
limpio pero de 0.58 / pl 0.50 / ru 0.58 / zh 0.05. Quintuplicar datos EN no
movió nada (v4≈v5): el cuello es FONOLOGÍA por idioma, no cantidad. Este
script trae checkpoints NATIVOS (espeak fonemiza "baxy" en cada idioma).

INTEGRIDAD DEL HELD-OUT: las voces del eval (wake_universal_voices) están
EXCLUIDAS del train. Por eso: de=mls (multi-speaker, no thorsten/eva_k/
karlsson), fr=mls (no siwis/upmc/tom), pl=mc_speech (no darkman/gosia),
ru=dmitri (no denis/irina), pt=cadu (no faber), nl=pim (no mls_5809 — el
mls multi PODRÍA contener al speaker 5809: se evita entero), zh=xiao_ya
(no huayan), es=sharvard (daniela no está en el repo de ckpts). it/sv no
tienen checkpoint publicado; ar/vi solo tienen LA voz del eval → quedan
EN-only (honesto: esos idiomas no mejorarán por esta vía).

Conversión: el .ckpt de Lightning (rhasspy/piper-checkpoints) trae
state_dict con prefijo "model_g." + hyper_parameters con los kwargs VITS.
El formato LiveKit es state_dict PELADO (.pt) + config piper con clave
"synthesizer" (kwargs de SynthesizerTrn). Mapeo dinámico por
inspect.signature + verificación dura: load_state_dict STRICT + síntesis
real de "baxy" (falla fuerte si el audio sale vacío/silencio).

Uso: .venv_livekit/Scripts/python.exe scripts/wake_p2_convert_checkpoints.py
     [--only VOICE] [--keep-ckpt]
"""
from __future__ import annotations

import argparse
import inspect
import json
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ROOT = Path(__file__).resolve().parent.parent
PIPER_DIR = ROOT / "data" / "piper"
CKPT_CACHE = ROOT / "data" / "piper" / "_p2_ckpts"

# (voice_id, ruta HF en rhasspy/piper-checkpoints)
P2_VOICES = [
    ("de_DE-mls", "de/de_DE/mls"),
    ("fr_FR-mls", "fr/fr_FR/mls"),
    ("es_ES-sharvard", "es/es_ES/sharvard"),
    ("pl_PL-mc_speech", "pl/pl_PL/mc_speech"),
    ("ru_RU-dmitri", "ru/ru_RU/dmitri"),
    ("pt_BR-cadu", "pt/pt_BR/cadu"),
    ("nl_NL-pim", "nl/nl_NL/pim"),
    ("zh_CN-xiao_ya", "zh/zh_CN/xiao_ya"),
]


def hf_listdir(path: str) -> list[dict]:
    import urllib.request
    url = f"https://huggingface.co/api/datasets/rhasspy/piper-checkpoints/tree/main/{path}"
    with urllib.request.urlopen(url, timeout=30) as r:
        return json.load(r)


def hf_download(repo_path: str, dest: Path) -> None:
    import urllib.request
    if dest.exists() and dest.stat().st_size > 1_000_000:
        print(f"  ya descargado: {dest.name}")
        return
    url = ("https://huggingface.co/datasets/rhasspy/piper-checkpoints/"
           f"resolve/main/{repo_path}")
    print(f"  bajando {repo_path} ...")
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_suffix(dest.suffix + ".part")
    urllib.request.urlretrieve(url, tmp)
    tmp.replace(dest)
    print(f"  {dest.name}: {dest.stat().st_size / 1e6:.0f} MB")


def find_quality_dir(base: str) -> str:
    """Algunas voces anidan la calidad (p.ej. mls/medium); otras tienen el
    ckpt directo. Devuelve la ruta del dir que contiene el .ckpt."""
    entries = hf_listdir(base)
    files = [e for e in entries if e["type"] == "file"
             and e["path"].endswith(".ckpt")]
    if files:
        return base
    subdirs = [e["path"].split("/")[-1] for e in entries
               if e["type"] == "directory"]
    # preferencia: medium > high > low > x_low (medium = mejor balance)
    for q in ("medium", "high", "low", "x_low"):
        if q in subdirs:
            return f"{base}/{q}"
    raise RuntimeError(f"sin ckpt ni calidad conocida en {base}: {subdirs}")


def convert(voice_id: str, ckpt_path: Path, cfg_path: Path) -> Path:
    import torch
    sys.path.insert(0, str(ROOT / ".venv_livekit" / "Lib" / "site-packages"))
    from livekit.wakeword.data.piper.vits.models import SynthesizerTrn

    print(f"  convirtiendo {voice_id} ...")
    # Lightning ckpt: pickle completo (fuente: repo oficial rhasspy — confiado).
    # Gotcha Windows: el pickle trae PosixPath (guardado en Linux) y
    # deserializarlo acá revienta — se mapea a WindowsPath durante el load.
    import pathlib
    _posix = pathlib.PosixPath
    try:
        pathlib.PosixPath = pathlib.WindowsPath  # type: ignore[misc]
        ckpt = torch.load(str(ckpt_path), map_location="cpu",
                          weights_only=False)
    finally:
        pathlib.PosixPath = _posix  # type: ignore[misc]
    hp = dict(ckpt.get("hyper_parameters") or {})
    sd = {k[len("model_g."):]: v
          for k, v in ckpt["state_dict"].items() if k.startswith("model_g.")}
    assert sd, "state_dict sin claves model_g.*"

    sig = inspect.signature(SynthesizerTrn.__init__)
    kwargs: dict = {}
    for name, param in sig.parameters.items():
        if name == "self":
            continue
        if name == "n_vocab":
            kwargs[name] = int(hp["num_symbols"])
        elif name == "spec_channels":
            kwargs[name] = int(hp["filter_length"]) // 2 + 1
        elif name == "segment_size":
            kwargs[name] = int(hp["segment_size"]) // int(hp["hop_length"])
        elif name == "n_speakers":
            kwargs[name] = int(hp["num_speakers"])
        elif name in hp:
            kwargs[name] = hp[name]
        elif param.default is not inspect.Parameter.empty:
            kwargs[name] = param.default
        else:
            raise RuntimeError(f"kwarg sin fuente: {name}")

    # ORDEN CRÍTICO: el ckpt trae los pesos PARAMETRIZADOS (weight_g/weight_v)
    # → cargar STRICT primero (si la arquitectura no calza, explota acá),
    # quitar weight-norm DESPUÉS, y guardar el state_dict ya limpio (que es
    # lo que _load_vits_model de livekit espera: él quita la norm ANTES de
    # cargar, o sea que el .pt publicado está post-removal).
    model = SynthesizerTrn(**kwargs)
    model.load_state_dict(sd)
    model.dec.remove_weight_norm()
    for flow in model.flow.flows:
        rm = getattr(flow, "remove_weight_norm", None)
        if rm is not None:
            rm()

    voice_cfg = json.load(open(cfg_path, encoding="utf-8"))
    # GOTCHA upstream (medido 2026-06-12): en rhasspy/piper-checkpoints el
    # config.json vecino puede ser de OTRA voz (de_DE/mls/medium traía el
    # config nl_NL de 52 speakers junto a un ckpt alemán de 236). La VERDAD
    # arquitectónica sale del ckpt (hyper_parameters); el espeak sale del
    # voice_id. El config vecino solo aporta el phoneme_id_map (estándar
    # piper, compartido entre voces de la misma versión).
    _espeak_by_locale = {
        "de_DE": "de", "fr_FR": "fr", "es_ES": "es", "pl_PL": "pl",
        "ru_RU": "ru", "pt_BR": "pt-br", "nl_NL": "nl", "zh_CN": "cmn",
    }
    locale = voice_id.split("-")[0]
    cfg_lang = (voice_cfg.get("language") or {}).get("code", "?")
    if cfg_lang != locale:
        print(f"  WARN: config vecino dice {cfg_lang}, ckpt es {locale} — "
              f"se fuerza espeak/speakers/sample_rate desde el ckpt")
    voice_cfg["espeak"] = {"voice": _espeak_by_locale[locale]}
    voice_cfg["num_speakers"] = int(hp["num_speakers"])
    voice_cfg.setdefault("audio", {})["sample_rate"] = int(hp["sample_rate"])
    assert int(hp["num_symbols"]) == kwargs["n_vocab"]
    voice_cfg["synthesizer"] = {
        k: (v if not hasattr(v, "tolist") else v.tolist())
        for k, v in kwargs.items()}
    out_pt = PIPER_DIR / f"{voice_id}-p2.pt"
    torch.save(model.state_dict(), str(out_pt))
    json.dump(voice_cfg, open(out_pt.with_suffix(".json"), "w",
                              encoding="utf-8"), ensure_ascii=False)
    print(f"  -> {out_pt.name} ({out_pt.stat().st_size / 1e6:.0f} MB, "
          f"speakers={kwargs['n_speakers']}, espeak="
          f"{voice_cfg.get('espeak', {}).get('voice')})")
    return out_pt


def smoke_synthesize(voice_id: str, pt_path: Path) -> None:
    """Sintetiza 'baxy' con el checkpoint convertido — falla fuerte si sale
    silencio (la conversión rota NO debe descubrirse tras horas de generate)."""
    import numpy as np
    from livekit.wakeword.data.piper.synthesis import (
        _load_vits_model, _espeak_phonemize,
    )
    import torch
    cfg = json.load(open(pt_path.with_suffix(".json"), encoding="utf-8"))
    device = torch.device("cpu")
    model = _load_vits_model(pt_path, device)
    espeak_voice = cfg.get("espeak", {}).get("voice", "en-us")
    ipa = _espeak_phonemize("baxy", voice=espeak_voice)
    assert ipa.strip(), f"espeak no fonemizo con voz {espeak_voice}"
    # esquema piper: BOS "^" + (fonema + pad "_")* + EOS "$"
    pid_map = cfg["phoneme_id_map"]
    ids = list(pid_map["^"]) + list(pid_map["_"])
    for ch in ipa.strip():
        if ch in pid_map:
            ids.extend(pid_map[ch])
            ids.extend(pid_map["_"])
    ids.extend(pid_map["$"])
    x = torch.LongTensor([ids])
    x_len = torch.LongTensor([len(ids)])
    sid = torch.LongTensor([0]) if cfg["num_speakers"] > 1 else None
    with torch.no_grad():
        audio = model.infer(x, x_len, sid=sid, noise_scale=0.667,
                            length_scale=1.0, noise_scale_w=0.8)[0]
    a = audio.squeeze().cpu().numpy()
    rms = float(np.sqrt(np.mean(a ** 2)))
    dur = a.size / cfg["audio"]["sample_rate"]
    assert a.size > 0 and rms > 1e-3 and 0.2 < dur < 5.0, \
        f"sintesis sospechosa: dur={dur:.2f}s rms={rms:.5f}"
    print(f"  smoke OK: 'baxy' [{espeak_voice}] dur={dur:.2f}s rms={rms:.3f}")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", default=None)
    ap.add_argument("--keep-ckpt", action="store_true")
    args = ap.parse_args()
    CKPT_CACHE.mkdir(parents=True, exist_ok=True)
    ok, failed = [], []
    for voice_id, base in P2_VOICES:
        if args.only and args.only != voice_id:
            continue
        out_pt = PIPER_DIR / f"{voice_id}-p2.pt"
        if out_pt.exists() and out_pt.with_suffix(".json").exists():
            print(f"{voice_id}: ya convertido")
            ok.append(voice_id)
            continue
        print(f"== {voice_id} ==")
        try:
            qdir = find_quality_dir(base)
            entries = hf_listdir(qdir)
            ckpts = sorted(e["path"] for e in entries
                           if e["type"] == "file" and e["path"].endswith(".ckpt"))
            cfgs = [e["path"] for e in entries
                    if e["path"].endswith("config.json")]
            assert ckpts and cfgs, f"{qdir}: ckpt={len(ckpts)} cfg={len(cfgs)}"
            ckpt_local = CKPT_CACHE / f"{voice_id}.ckpt"
            cfg_local = CKPT_CACHE / f"{voice_id}.config.json"
            hf_download(ckpts[-1], ckpt_local)     # el de mas epochs
            hf_download(cfgs[0], cfg_local)
            pt = convert(voice_id, ckpt_local, cfg_local)
            smoke_synthesize(voice_id, pt)
            if not args.keep_ckpt:
                ckpt_local.unlink(missing_ok=True)
            ok.append(voice_id)
        except Exception as exc:
            print(f"  FALLO {voice_id}: {type(exc).__name__}: {exc}")
            failed.append(voice_id)
    print(f"\nconvertidos OK: {ok}")
    if failed:
        print(f"FALLARON: {failed}")
    return 0 if ok and not failed else (0 if ok else 1)


if __name__ == "__main__":
    raise SystemExit(main())

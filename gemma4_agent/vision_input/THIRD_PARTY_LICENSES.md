# Third-party licenses — camera control subsystem (`vision_input`)

The hands-free camera-control product is **sold**, so every dependency (code,
models, and datasets) must permit commercial use. This file lists what the
`vision_input` subsystem introduces and the license each is distributed under,
verified against the official source. Apache-2.0 and BSD/MIT require preserving
the copyright/NOTICE; this document is part of that obligation. Regenerate the
full tree audit with `pip-licenses` before any release.

> **Hard rule:** never add a GPL / AGPL / CC-BY-NC (non-commercial) /
> CC-BY-SA (ShareAlike copyleft) dependency, model, or dataset. ShareAlike is
> viral and would force relicensing the product. Audit the license of every new
> library *and* every new model/dataset before adding it.

## Runtime dependencies

| Component | Version pin | License | Commercial use | Source verified |
|---|---|---|---|---|
| mediapipe (framework) | `==0.10.35` | Apache-2.0 | ✅ Yes | google-ai-edge/mediapipe LICENSE |
| MediaPipe `hand_landmarker.task` | float16 (sha256 pinned in `landmarks.py`) | Apache-2.0 | ✅ Yes ("Commercial use: Yes" on the model card) | model card + storage.googleapis.com asset |
| MediaPipe `face_landmarker.task` | float16 (sha256 pinned) | Apache-2.0 | ✅ Yes | model card |
| opencv-python | `==4.11.0.86` | MIT (wheel) + Apache-2.0 (OpenCV) | ✅ Yes | opencv-python PyPI / OpenCV LICENSE |
| opencv-contrib-python | `==4.11.0.86` | MIT + Apache-2.0 | ✅ Yes | as above |
| numpy | `==1.26.4` | BSD-3-Clause | ✅ Yes | numpy LICENSE |
| flatbuffers | `==25.12.19` | Apache-2.0 | ✅ Yes | google/flatbuffers LICENSE |
| pywin32 (`win32api`, `win32gui`, `win32con`) | — | PSF / BSD-style | ✅ Yes | mhammond/pywin32 |
| uiautomation | `==2.0.29` | Apache-2.0 | ✅ Yes | yinkaisheng/Python-UIAutomation-for-Windows |

The OneEuro filter is a **clean-room reimplementation** in `pointer.py` (the
Casiez et al. 2012 algorithm is not copyrightable; the reference C++/JS impl is
BSD-3 but is not used here).

## Test/validation fixtures (not shipped in the product binary)

| Component | License | Commercial use | Notes |
|---|---|---|---|
| kinivi `keypoint.csv` subset | Apache-2.0 | ✅ Yes (with attribution) | Offline gesture-recognizer validation fixture. Attribution in `tests/fixtures/hand_landmarks/NOTICE.md` (kinivi + Kazuhito Takahashi). **Not** used to train any shipped model. |

## Datasets evaluated and REJECTED (do not use — license-incompatible)

These were considered for training/fixtures and rejected. Recorded so nobody
re-introduces them by mistake:

| Dataset | License | Why rejected |
|---|---|---|
| HaGRID / HaGRIDv2 | custom = CC-BY-SA-style **ShareAlike** copyleft | ShareAlike is viral copyleft. (Note: it is *not* non-commercial — an old version was; the current one is ShareAlike. Classify as **copyleft**, not "non-commercial".) |
| Jester | CC-BY-NC-ND 4.0 | Non-commercial + no-derivatives |
| FreiHAND | research-only ("commercial use prohibited") | Explicitly bans commercial use |
| InterHand2.6M | CC-BY-NC 4.0 | Non-commercial |
| Ultralytics Hand Keypoints | dataset CC-BY-NC-SA + code AGPL-3.0 | Non-commercial + ShareAlike + AGPL |
| leapgestrecog | CC-BY-NC-SA 4.0 | Non-commercial + ShareAlike |
| Indian Sign Language hand-landmarks | CC-BY-SA 4.0 | ShareAlike copyleft |
| Voxel51 hand-keypoints (NZSL part) | CC-BY-NC-SA 3.0 | Non-commercial component contaminates the set |
| WebGazer.js (calibration reference) | GPLv3 | Copyleft — use the *techniques* from papers, never the code |

The MediaPipe Gesture Recognizer canned model (`gesture_recognizer.task`) is
Apache-2.0 (commercial-OK) but is **not adopted** — it lacks `pinch` (our click
gesture) and would break the deterministic geometric path. It remains a possible
future ensemble vote, not a replacement.

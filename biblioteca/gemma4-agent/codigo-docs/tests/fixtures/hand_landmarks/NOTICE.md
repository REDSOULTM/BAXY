# Hand-landmark gesture fixture — attribution

`kinivi_keypoint_subset.csv` is a balanced subset (250 samples per class) of the
`keypoint.csv` training data from:

- **kinivi/hand-gesture-recognition-mediapipe**
  https://github.com/kinivi/hand-gesture-recognition-mediapipe
  License: **Apache-2.0**
  Original author of the gesture-recognition approach and data:
  **Kazuhito Takahashi** (https://github.com/Kazuhito00/hand-gesture-recognition-using-mediapipe)

Apache-2.0 permits commercial use and redistribution with attribution; this
NOTICE preserves that attribution. The data is verified commercial-OK and is
used here only as an **offline validation fixture** for the deterministic
geometric gesture recognizer (`gemma4_agent/vision_input/gestures.py`) — it is
NOT used to train any model that ships in the product.

## Format

Each row: `label, x0, y0, x1, y1, ..., x20, y20` — i.e. one integer label
followed by 21 (x, y) landmark pairs. The coordinates are kinivi's pre-processed
form: translated so the wrist (landmark 0) sits at the origin and scaled by the
maximum absolute coordinate. No z axis is stored. Because the recognizer's
features are ratios/angles (translation- and scale-invariant), the samples can be
fed to `recognize_hand_gesture` directly via a reconstructed `HandSample`.

## Label mapping (kinivi -> our gesture vocabulary)

| kinivi label | kinivi name | our gesture |
|---|---|---|
| 0 | Open   | palm  |
| 1 | Close  | fist  |
| 2 | Pointer| point |
| 3 | OK     | (not mapped — kinivi "OK" is thumb+index circle, not our "pinch") |

Label 3 is intentionally excluded from the accuracy gate: kinivi's "OK" gesture
is geometrically distinct from our `pinch` (thumb tip touching index tip with the
other fingers extended).

## Reproduce / refresh

Run the recipe to regenerate the subset from the upstream source:

    python -m gemma4_agent.tests.fixtures.hand_landmarks.build_fixture

(Never ship a fixture without its recipe — repo reproducibility rule.)

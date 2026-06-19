"""Interactive calibration script to personalize gesture thresholds."""
import time
import cv2
import numpy as np

from gemma4_agent.vision_input.gestures import FINGER_JOINTS, _angle_deg, _dist, _mean_point
from gemma4_agent.vision_input.landmarks import MediaPipeLandmarkDetector

def draw_hand(frame, landmarks):
    CONNECTIONS = [
        (0, 1), (1, 2), (2, 3), (3, 4),
        (0, 5), (5, 6), (6, 7), (7, 8),
        (5, 9), (9, 10), (10, 11), (11, 12),
        (9, 13), (13, 14), (14, 15), (15, 16),
        (13, 17), (0, 17), (17, 18), (18, 19), (19, 20)
    ]
    h, w, _ = frame.shape
    pts = []
    for lm in landmarks:
        px, py = int(lm.x * w), int(lm.y * h)
        pts.append((px, py))
        cv2.circle(frame, (px, py), 4, (0, 255, 0), -1)
    for p1, p2 in CONNECTIONS:
        if p1 < len(pts) and p2 < len(pts):
            cv2.line(frame, pts[p1], pts[p2], (0, 255, 0), 2)

def main():
    print("Iniciando Calibracion de Gestos...")
    cap = cv2.VideoCapture(0)
    if not cap.isOpened():
        print("Error: No se pudo abrir la camara.")
        return

    detector = MediaPipeLandmarkDetector(download_models=True)
    detector.start()

    states = [
        {"name": "PALMA ABIERTA", "desc": "Muestra toda tu palma abierta", "samples": []},
        {"name": "PUNO CERRADO", "desc": "Cierra tu mano en un puno", "samples": []},
        {"name": "PELLIZCO (PINCH)", "desc": "Pellizca con el indice y pulgar", "samples": []},
        {"name": "APUNTAR (POINT)", "desc": "Apunta solo con tu dedo indice", "samples": []},
    ]

    current_state_idx = 0
    capturing = False
    capture_frames_left = 0

    while True:
        ret, frame = cap.read()
        if not ret:
            break
            
        frame = cv2.flip(frame, 1)
        timestamp_ms = int(time.time() * 1000)
        
        try:
            # MediaPipeLandmarkDetector expects BGR, but tasks API internally handles RGB if we pass it correctly?
            # Usually tasks takes RGB, but MediaPipeLandmarkDetector handles BGR conversion if needed, or takes BGR directly.
            # In window_control it passes the BGR frame directly.
            landmark_frame = detector.detect(frame, timestamp_ms, run_face=False)
            hand_sample = landmark_frame.primary_hand.landmarks if landmark_frame.primary_hand else None
        except Exception as e:
            print(f"Detector error: {e}")
            hand_sample = None

        if hand_sample is not None and len(hand_sample) == 21:
            draw_hand(frame, hand_sample)

        if current_state_idx < len(states):
            state = states[current_state_idx]
            
            if capturing:
                cv2.putText(frame, f"Capturando... {capture_frames_left} frames", (50, 100), 
                            cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 255), 2)
                if hand_sample is not None and len(hand_sample) == 21:
                    state["samples"].append(hand_sample)
                    capture_frames_left -= 1
                    if capture_frames_left <= 0:
                        capturing = False
                        current_state_idx += 1
            else:
                cv2.putText(frame, f"PASO {current_state_idx+1}/{len(states)}: {state['name']}", (20, 50), 
                            cv2.FONT_HERSHEY_SIMPLEX, 1.0, (255, 255, 0), 2)
                cv2.putText(frame, state['desc'], (20, 90), 
                            cv2.FONT_HERSHEY_SIMPLEX, 0.7, (200, 200, 200), 2)
                cv2.putText(frame, "Pon tu mano y PRESIONA ESPACIO", (20, 130), 
                            cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
                
                # Check for spacebar
                key = cv2.waitKey(1) & 0xFF
                if key == 32:  # Spacebar
                    capturing = True
                    capture_frames_left = 30
        else:
            cv2.putText(frame, "CALIBRACION COMPLETADA", (50, 100), 
                        cv2.FONT_HERSHEY_SIMPLEX, 1.2, (0, 255, 0), 3)
            cv2.putText(frame, "Cierra esta ventana y revisa la terminal", (50, 150), 
                        cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 255, 255), 2)
        
        cv2.imshow("Calibracion de Gestos", frame)
        
        key = cv2.waitKey(1) & 0xFF
        if key == 27:  # Esc
            break
            
        if current_state_idx >= len(states) and not capturing:
            cv2.waitKey(2000)
            break

    cap.release()
    cv2.destroyAllWindows()
    detector.close()

    if current_state_idx < len(states):
        print("\nCalibracion cancelada antes de terminar.")
        return

    print("\nCalculando umbrales personalizados...")
    
    # 1. Process PALM for extended angle and thumb open ratio
    palm_samples = states[0]["samples"]
    extended_angles = []
    thumb_ratios = []
    for lm in palm_samples:
        raw_palm = _dist(lm[0], lm[9])
        palm = max(raw_palm, 1e-6)
        
        # Angles for all 4 fingers
        for name, (mcp, pip, tip) in FINGER_JOINTS.items():
            angle = _angle_deg(lm[mcp], lm[pip], lm[tip])
            extended_angles.append(angle)
            
        palm_center = _mean_point(lm[0], lm[5], lm[9], lm[13], lm[17])
        thumb_ratios.append(_dist(lm[4], palm_center) / palm)
        
    avg_ext_angle = np.mean(extended_angles)
    min_ext_angle = np.percentile(extended_angles, 5) # 5th percentile
    
    avg_thumb_ratio = np.mean(thumb_ratios)
    min_thumb_ratio = np.percentile(thumb_ratios, 5)

    # 2. Process FIST for flexed angle
    fist_samples = states[1]["samples"]
    flexed_angles = []
    for lm in fist_samples:
        for name, (mcp, pip, tip) in FINGER_JOINTS.items():
            angle = _angle_deg(lm[mcp], lm[pip], lm[tip])
            flexed_angles.append(angle)
            
    avg_flex_angle = np.mean(flexed_angles)
    max_flex_angle = np.percentile(flexed_angles, 95) # 95th percentile

    # 3. Process PINCH
    pinch_samples = states[2]["samples"]
    pinch_ratios = []
    for lm in pinch_samples:
        raw_palm = _dist(lm[0], lm[9])
        palm = max(raw_palm, 1e-6)
        pinch_ratios.append(_dist(lm[4], lm[8]) / palm)
        
    max_pinch_ratio = np.percentile(pinch_ratios, 95)

    # 4. Process POINT
    point_samples = states[3]["samples"]
    point_dominance = []
    for lm in point_samples:
        tip_distances = {}
        for name, (mcp, pip, tip) in FINGER_JOINTS.items():
            tip_distances[name] = _dist(lm[0], lm[tip])
            
        other_names = ("middle", "ring", "pinky")
        max_other = max(tip_distances[name] for name in other_names)
        if max_other > 0:
            point_dominance.append(tip_distances["index"] / max_other)
            
    min_point_dominance = np.percentile(point_dominance, 5)

    print("\n" + "="*50)
    print(" RESULTADOS DE CALIBRACION: TU ADN GEOMETRICO")
    print("="*50)
    
    # Calculate recommended thresholds with safety margins
    rec_ext_angle = min(155.0, max(120.0, min_ext_angle - 8.0)) # A bit of leeway to ensure it triggers
    rec_flex_angle = max(90.0, min(140.0, max_flex_angle + 8.0))
    rec_pinch_ratio = max(0.2, min(0.7, max_pinch_ratio * 1.3)) # Allow 30% wider pinch
    rec_thumb_ratio = max(0.4, min(1.0, min_thumb_ratio * 0.85)) # Allow 15% less stretching
    rec_point_dom = max(1.05, min(1.4, min_point_dominance * 0.9)) # Allow 10% less pointing stretch
    
    print("Copia y pega este bloque en el chat para que actualice tu gestures.py:\n")
    print("class GestureThresholds:")
    print(f"    extended_angle_deg: float = {rec_ext_angle:.1f}")
    print(f"    flexed_angle_deg: float = {rec_flex_angle:.1f}")
    print(f"    pinch_palm_ratio: float = {rec_pinch_ratio:.2f}")
    print(f"    thumb_open_ratio: float = {rec_thumb_ratio:.2f}")
    print("    pinch_max_flex: int = 1")
    print(f"    point_index_dominance: float = {rec_point_dom:.2f}")
    print("    point_min_folded_others: int = 3")
    print("="*50 + "\n")

if __name__ == "__main__":
    main()

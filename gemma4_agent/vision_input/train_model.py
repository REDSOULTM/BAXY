import cv2
import sys
import glob
import os
from pathlib import Path
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split
from sklearn.metrics import classification_report
import pickle

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from gemma4_agent.vision_input.landmarks import MediaPipeLandmarkDetector
from gemma4_agent.vision_input.gestures import FINGER_JOINTS, _dist, _angle_deg, _mean_point

def extract_features(hand_sample):
    if not hand_sample:
        return None
    lm = hand_sample.landmarks
    
    features = []
    
    # 1. Angles
    for name, (mcp, pip, tip) in FINGER_JOINTS.items():
        features.append(_angle_deg(lm[mcp], lm[pip], lm[tip]))
        
    # 2. Distances to wrist
    for name, (mcp, pip, tip) in FINGER_JOINTS.items():
        features.append(_dist(lm[0], lm[tip]))
        features.append(_dist(lm[0], lm[pip]))
        
    # 3. Palm metrics
    palm = max(_dist(lm[0], lm[9]), 1e-6)
    palm_center = _mean_point(lm[0], lm[5], lm[9], lm[13], lm[17])
    
    # 4. Normalized specific distances
    features.append(_dist(lm[4], palm_center) / palm) # thumb_ratio
    features.append(_dist(lm[4], lm[8]) / palm) # pinch_distance
    features.append(_dist(lm[0], lm[8]) / palm) # idx_palm_dist
    
    return features

def get_label_for_video(video_path):
    name = os.path.basename(video_path).lower()
    if "clicl" in name: return "point"
    if "pausa" in name: return "palm"
    if "scroll" in name or "zoom" in name: return "pinch"
    if "latigazo" in name: return "fist"
    return "none"

def main():
    video_dir = r"C:\Users\usuario\Pictures\Camera Roll\Tesis"
    videos = glob.glob(os.path.join(video_dir, "*.mp4"))
    
    detector = MediaPipeLandmarkDetector(download_models=True)
    detector.start()
    
    X = []
    y = []
    
    for vid in videos:
        label = get_label_for_video(vid)
        print(f"Extracting {label} from {os.path.basename(vid)}...")
        cap = cv2.VideoCapture(vid)
        frame_count = 0
        while True:
            ret, frame = cap.read()
            if not ret: break
            
            # Skip frames to reduce redundancy
            if frame_count % 3 != 0:
                frame_count += 1
                continue
                
            try:
                landmark_frame = detector.detect(frame, frame_count * 33, run_face=False)
                hand = landmark_frame.primary_hand
            except Exception:
                hand = None
                
            features = extract_features(hand)
            if features:
                X.append(features)
                y.append(label)
            frame_count += 1
        cap.release()
        
    detector.close()
    
    print(f"Extracted {len(X)} samples.")
    
    clf = RandomForestClassifier(n_estimators=100, max_depth=10, random_state=42, class_weight="balanced")
    
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)
    clf.fit(X_train, y_train)
    
    print("\n--- Test Set Report ---")
    print(classification_report(y_test, clf.predict(X_test)))
    
    model_path = os.path.join(os.path.dirname(__file__), "gesture_rf_model.pkl")
    with open(model_path, "wb") as f:
        pickle.dump(clf, f)
    print(f"Saved model to {model_path}")

if __name__ == "__main__":
    main()

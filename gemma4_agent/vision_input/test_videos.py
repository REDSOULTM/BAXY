import cv2
import sys
import glob
import os
from pathlib import Path
from collections import Counter

# Add gemma4_agent to path if needed
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from gemma4_agent.vision_input.landmarks import MediaPipeLandmarkDetector
from gemma4_agent.vision_input.gestures import recognize_hand_gesture, GestureStabilizer, _dist, _mean_point

def process_video(video_path, detector):
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        print(f"Failed to open {video_path}")
        return None

    stabilizer = GestureStabilizer(window=5)
    raw_labels = []
    stable_labels = []

    frame_count = 0
    while True:
        ret, frame = cap.read()
        if not ret:
            break
        
        timestamp_ms = frame_count * 33
        
        try:
            landmark_frame = detector.detect(frame, timestamp_ms, run_face=True)
            hand_sample = landmark_frame.primary_hand if landmark_frame.primary_hand else None
            face_sample = landmark_frame.primary_face if landmark_frame.primary_face else None
        except Exception as e:
            print(f"EXCEPTION in detect: {e}")
            hand_sample = None
            face_sample = None
            
        result = recognize_hand_gesture(hand_sample)
        raw_label = result.label

        raw_labels.append(raw_label)
        
        stable_label = stabilizer.update(raw_label)
        stable_labels.append(stable_label)
        
        if ("Scroll" in video_path or "Zoom" in video_path or "Latigazo" in video_path or "Clicl" in video_path) and frame_count % 15 == 0 and hand_sample:
            lm = hand_sample.landmarks
            palm = max(_dist(lm[0], lm[9]), 1e-6)
            pinch_dist = _dist(lm[4], lm[8]) / palm
            idx_palm_dist = _dist(lm[0], lm[8]) / palm
            palm_center = _mean_point(lm[0], lm[5], lm[9], lm[13], lm[17])
            thumb_open = _dist(lm[4], palm_center) / palm
            print(f"Frame {frame_count}: label={raw_label}, pinch_dist={pinch_dist:.2f}, idx_palm={idx_palm_dist:.2f}, thumb_open={thumb_open:.2f}, ext_count={sum(result.finger_extended.values())}")

        frame_count += 1

    cap.release()
    
    return {
        "frames": frame_count,
        "raw_counts": dict(Counter(raw_labels)),
        "stable_counts": dict(Counter(stable_labels))
    }

def main():
    video_dir = r"C:\Users\usuario\Pictures\Camera Roll\Tesis"
    videos = glob.glob(os.path.join(video_dir, "*.mp4"))
    
    if not videos:
        print("No videos found.")
        return
        
    detector = MediaPipeLandmarkDetector(download_models=True)
    detector.start()
    
    print("Processing videos with current thresholds...\n")
    
    for vid in videos:
        name = os.path.basename(vid)
        print(f"--- Analyzing {name} ---")
        res = process_video(vid, detector)
        if res:
            print(f"Total Frames: {res['frames']}")
            print(f"Raw labels: {res['raw_counts']}")
            print(f"Stable labels: {res['stable_counts']}\n")
            
    detector.close()

if __name__ == "__main__":
    main()

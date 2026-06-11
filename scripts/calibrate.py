import sys
import os
import cv2
import time

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from gemma4_agent.vision_input.landmarks import MediaPipeLandmarkDetector
from gemma4_agent.vision_input.gestures import recognize_hand_gesture
from gemma4_agent.vision_input.controller import (
    FixedGestureWindowController,
    WindowActuator,
    WindowControlConfig
)

def analyze_video(video_path: str):
    print(f"\n{'='*50}")
    print(f"ANALYZING: {os.path.basename(video_path)}")
    print(f"{'='*50}")
    
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        print("Failed to open video")
        return
        
    config = WindowControlConfig()
    actuator = WindowActuator(execute=False) # Dry run
    controller = FixedGestureWindowController(config, actuator)
    
    frame_idx = 0
    fps = cap.get(cv2.CAP_PROP_FPS)
    if fps <= 0: fps = 30
    
    with MediaPipeLandmarkDetector(num_hands=2, min_confidence=0.5) as detector:
        while cap.isOpened():
            ret, frame = cap.read()
            if not ret:
                break
                
            frame_idx += 1
            timestamp_s = frame_idx / fps
            
            result = detector.detect(frame, int(timestamp_s * 1000), run_face=True)
            
            if result:
                # We need to map raw landmarks to HandControlPose with recognized labels
                hand_poses = []
                for hand in result.hands:
                    gesture = recognize_hand_gesture(hand)
                    label = gesture.label
                    # Convert to HandControlPose
                    from gemma4_agent.vision_input.controller import HandControlPose
                    
                    def _p(idx, axis):
                        if idx < len(hand.landmarks):
                            return getattr(hand.landmarks[idx], axis)
                        return None
                        
                    # Calculate palm center approximately
                    px = _p(0, 'x')
                    py = _p(0, 'y')
                    
                    pose = HandControlPose(
                        x=px if px is not None else 0.5,
                        y=py if py is not None else 0.5,
                        label=label,
                        handedness=hand.handedness,
                        score=hand.score,
                        index_tip_x=_p(8, 'x'),
                        index_tip_y=_p(8, 'y'),
                        index_tip_z=_p(8, 'z'),
                        palm_x=px,
                        palm_y=py,
                        palm_z=_p(0, 'z')
                    )
                    hand_poses.append(pose)
                
                face = result.faces[0] if result.faces else None
                
                from gemma4_agent.vision_input.window_target import WindowTarget, WindowRect
                dummy_target = WindowTarget(hwnd=1, title="Test Window", class_name="TestClass", rect=WindowRect(0, 0, 800, 600), visible=True, iconic=False)
                
                output = controller.update(
                    timestamp_s=timestamp_s,
                    target=dummy_target,
                    hands=tuple(hand_poses),
                    pointer_xy=(0.5, 0.5),
                    face=face,
                )
                
                for evt in output.events:
                    print(f"[EVENT] Frame {frame_idx} ({timestamp_s:.2f}s): {evt.name} -> {evt.detail}")

    cap.release()
    print("Done.\n")

if __name__ == "__main__":
    import glob
    videos = glob.glob(r"C:\Users\usuario\Pictures\Camera Roll\Tesis\*.mp4")
    for v in videos:
        if any(x in v.lower() for x in ['clicl', 'latigazo', 'pausa', 'scroll', 'zoom']):
            analyze_video(v)

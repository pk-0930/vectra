import cv2
import os
import mediapipe as mp

from mediapipe.tasks import python
from mediapipe.tasks.python import vision


class PoseAnalyzer:
    def _frame_sort_key(self, frame_file: str):
        name, _ = os.path.splitext(frame_file)
        try:
            return int(name.split("_")[-1])
        except ValueError:
            return frame_file

    def _create_landmarker(self):
        model_path = os.path.join(
            os.path.dirname(os.path.dirname(__file__)),
            "models",
            "pose_landmarker.task"
        )

        base_options = python.BaseOptions(model_asset_path=model_path)
        options = vision.PoseLandmarkerOptions(
            base_options=base_options,
            running_mode=vision.RunningMode.VIDEO
        )

        return vision.PoseLandmarker.create_from_options(options)

    def analyze_frames(self, frames_folder: str):
        pose_results = []

        with self._create_landmarker() as landmarker:
            frame_index = 0

            frames_read = 0
            pose_found_count = 0
            visibility_pass_count = 0

            for frame_file in sorted(os.listdir(frames_folder), key=self._frame_sort_key):
                frame_path = os.path.join(frames_folder, frame_file)

                frame = cv2.imread(frame_path)
                if frame is None:
                    frame_index += 1
                    continue

                frames_read += 1

                height, width = frame.shape[:2]
                target_width = 640
                scale = target_width / width
                target_height = int(height * scale)

                frame = cv2.resize(frame, (target_width, target_height))
                frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

                mp_image = mp.Image(
                    image_format=mp.ImageFormat.SRGB,
                    data=frame_rgb
                )

                timestamp_ms = frame_index * 33
                result = landmarker.detect_for_video(mp_image, timestamp_ms)

                if result.pose_landmarks:
                    pose_found_count += 1
                    landmarks = result.pose_landmarks[0]

                    left_shoulder = landmarks[11]
                    right_shoulder = landmarks[12]
                    left_hip = landmarks[23]
                    right_hip = landmarks[24]
                    left_knee = landmarks[25]
                    right_knee = landmarks[26]
                    left_ankle = landmarks[27]
                    right_ankle = landmarks[28]

                    visible_leg_count = sum(
                        1
                        for leg_visibility in [
                            min(left_hip.visibility, left_knee.visibility, left_ankle.visibility),
                            min(right_hip.visibility, right_knee.visibility, right_ankle.visibility),
                        ]
                        if leg_visibility >= 0.25
                    )

                    if visible_leg_count >= 1:
                        visibility_pass_count += 1
                        pose_results.append({
                            "frame_index": frame_index,
                            "left_shoulder_x": left_shoulder.x,
                            "right_shoulder_x": right_shoulder.x,
                            "left_shoulder_y": left_shoulder.y,
                            "right_shoulder_y": right_shoulder.y,
                            "left_hip_x": left_hip.x,
                            "right_hip_x": right_hip.x,
                            "left_hip_y": left_hip.y,
                            "right_hip_y": right_hip.y,
                            "left_knee_x": left_knee.x,
                            "right_knee_x": right_knee.x,
                            "left_knee_y": left_knee.y,
                            "right_knee_y": right_knee.y,
                            "left_ankle_x": left_ankle.x,
                            "right_ankle_x": right_ankle.x,
                            "left_ankle_y": left_ankle.y,
                            "right_ankle_y": right_ankle.y,
                            "left_shoulder_visibility": left_shoulder.visibility,
                            "right_shoulder_visibility": right_shoulder.visibility,
                            "left_hip_visibility": left_hip.visibility,
                            "right_hip_visibility": right_hip.visibility,
                            "left_knee_visibility": left_knee.visibility,
                            "right_knee_visibility": right_knee.visibility,
                            "left_ankle_visibility": left_ankle.visibility,
                            "right_ankle_visibility": right_ankle.visibility,
                        })

                frame_index += 1

        
        print(f"Frames read: {frames_read}")
        print(f"Pose found: {pose_found_count}")
        print(f"Visibility pass: {visibility_pass_count}")

        return pose_results

class KneeTrackingRule:
    def evaluate(self, pose_results):
        if len(pose_results) < 20:
            return {
                "knee_tracking": {
                    "status": "unknown",
                    "message": "Insufficient pose data for knee tracking analysis."
                }
            }

        frame_measurements = []

        for pose in pose_results:
            left_knee_visibility = float(pose.get("left_knee_visibility", 0.0))
            right_knee_visibility = float(pose.get("right_knee_visibility", 0.0))
            left_ankle_visibility = float(pose.get("left_ankle_visibility", 0.0))
            right_ankle_visibility = float(pose.get("right_ankle_visibility", 0.0))
            left_hip_visibility = float(pose.get("left_hip_visibility", 0.0))
            right_hip_visibility = float(pose.get("right_hip_visibility", 0.0))

            if min(
                left_knee_visibility,
                right_knee_visibility,
                left_ankle_visibility,
                right_ankle_visibility,
                left_hip_visibility,
                right_hip_visibility,
            ) < 0.35:
                continue

            left_knee_x = pose["left_knee_x"]
            right_knee_x = pose["right_knee_x"]
            left_ankle_x = pose["left_ankle_x"]
            right_ankle_x = pose["right_ankle_x"]
            left_hip_y = pose["left_hip_y"]
            right_hip_y = pose["right_hip_y"]

            knee_width = abs(right_knee_x - left_knee_x)
            ankle_width = abs(right_ankle_x - left_ankle_x)

            if ankle_width <= 0.0001:
                continue

            width_ratio = knee_width / ankle_width
            avg_hip_y = (left_hip_y + right_hip_y) / 2

            frame_measurements.append({
                "frame_index": pose["frame_index"],
                "knee_width": float(knee_width),
                "ankle_width": float(ankle_width),
                "width_ratio": float(width_ratio),
                "avg_hip_y": float(avg_hip_y),
            })

        if not frame_measurements:
            return {
                "knee_tracking": {
                    "status": "unknown",
                    "message": "Could not find a usable frame for knee tracking analysis."
                }
            }

        hip_y_values = [item["avg_hip_y"] for item in frame_measurements]
        min_hip_y = min(hip_y_values)
        max_hip_y = max(hip_y_values)
        hip_span = max(max_hip_y - min_hip_y, 0.0001)
        deep_threshold = min_hip_y + (hip_span * 0.55)

        deep_measurements = [
            item for item in frame_measurements
            if item["avg_hip_y"] >= deep_threshold
        ]

        candidate_measurements = (
            deep_measurements
            if len(deep_measurements) >= 5
            else frame_measurements
        )

        # Lower ratio = worse knee cave. Prefer frames closer to the deeper part of the squat.
        sorted_measurements = sorted(
            candidate_measurements,
            key=lambda item: (
                item["width_ratio"] - (((item["avg_hip_y"] - min_hip_y) / hip_span) * 0.12)
            )
        )

        worst_count = min(5, len(sorted_measurements))
        worst_frames = sorted_measurements[:worst_count]

        avg_ratio = sum(item["width_ratio"] for item in worst_frames) / worst_count
        avg_knee_width = sum(item["knee_width"] for item in worst_frames) / worst_count
        avg_ankle_width = sum(item["ankle_width"] for item in worst_frames) / worst_count

        representative_frame = max(worst_frames, key=lambda item: item["avg_hip_y"])["frame_index"]

        if avg_ratio < 0.70:
            status = "severe_knee_cave"
            message = "Knees show strong inward collapse in the most affected part of the set."
        elif avg_ratio < 0.85:
            status = "moderate_knee_cave"
            message = "Knees show moderate inward collapse during the set."
        elif avg_ratio < 0.95:
            status = "mild_knee_cave"
            message = "Knees show slight inward collapse during the set."
        else:
            status = "tracking_well"
            message = "Knees appear to be tracking well relative to ankle position."

        return {
            "knee_tracking": {
                "status": status,
                "message": message,
                "evaluated_frame": representative_frame,
                "knee_width": float(avg_knee_width),
                "ankle_width": float(avg_ankle_width),
                "width_ratio": float(avg_ratio),
                "frames_considered": worst_count
            }
        }

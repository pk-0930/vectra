class ViewClassifier:
    def classify(self, pose_results):
        if len(pose_results) < 20:
            return {
                "video_view": "unknown",
                "confidence": "low",
                "view_suitability": "not_sufficient",
                "message": "Insufficient pose data to determine video view.",
                "capture_guidance": [
                    "Keep the full body visible from shoulders to ankles.",
                    "Use a stable camera position and avoid partial body cropping.",
                ],
            }

        shoulder_widths = []
        hip_widths = []
        ankle_widths = []

        shoulder_to_ankle_heights = []
        hip_to_ankle_heights = []

        for r in pose_results:
            shoulder_widths.append(abs(r["right_shoulder_x"] - r["left_shoulder_x"]))
            hip_widths.append(abs(r["right_hip_x"] - r["left_hip_x"]))
            ankle_widths.append(abs(r["right_ankle_x"] - r["left_ankle_x"]))

            avg_shoulder_y = (r["left_shoulder_y"] + r["right_shoulder_y"]) / 2
            avg_hip_y = (r["left_hip_y"] + r["right_hip_y"]) / 2
            avg_ankle_y = (r["left_ankle_y"] + r["right_ankle_y"]) / 2

            shoulder_to_ankle_heights.append(abs(avg_ankle_y - avg_shoulder_y))
            hip_to_ankle_heights.append(abs(avg_ankle_y - avg_hip_y))

        avg_shoulder_width = sum(shoulder_widths) / len(shoulder_widths)
        avg_hip_width = sum(hip_widths) / len(hip_widths)
        avg_ankle_width = sum(ankle_widths) / len(ankle_widths)

        avg_body_width = (
            avg_shoulder_width +
            avg_hip_width +
            avg_ankle_width
        ) / 3

        avg_shoulder_to_ankle_height = (
            sum(shoulder_to_ankle_heights) / len(shoulder_to_ankle_heights)
        )
        avg_hip_to_ankle_height = (
            sum(hip_to_ankle_heights) / len(hip_to_ankle_heights)
        )

        avg_body_height = (
            avg_shoulder_to_ankle_height +
            avg_hip_to_ankle_height
        ) / 2

        if avg_body_height <= 0.0001:
            return {
                "video_view": "unknown",
                "confidence": "low",
                "view_suitability": "not_sufficient",
                "message": "Could not determine video view because body height was too small.",
                "capture_guidance": [
                    "Move the camera farther back so the full body stays in frame.",
                    "Keep the athlete centered and fully visible during the full rep.",
                ],
            }

        width_height_ratio = avg_body_width / avg_body_height

        if width_height_ratio <= 0.13:
            return {
                "video_view": "side_view",
                "confidence": "high",
                "view_suitability": "good",
                "message": "This video appears to be a strong side-view squat recording.",
                "capture_guidance": [
                    "This angle is suitable for side-view analysis.",
                ],
            }

        if width_height_ratio <= 0.18:
            return {
                "video_view": "side_view",
                "confidence": "medium",
                "view_suitability": "moderate",
                "message": (
                    "This video appears to be mostly side view, but the angle is slightly off-axis."
                ),
                "capture_guidance": [
                    "Rotate the camera a little more to the side for depth and torso-lean accuracy.",
                    "Keep the athlete perpendicular to the camera when possible.",
                ],
            }

        if width_height_ratio < 0.19:
            return {
                "video_view": "unknown",
                "confidence": "low",
                "view_suitability": "not_sufficient",
                "message": (
                    "This video sits between a side and front view, so Vectra cannot apply view-based squat rules reliably."
                ),
                "capture_guidance": [
                    "For side-view analysis, rotate to a truer side profile.",
                    "For knee-tracking analysis, rotate to a straight front view.",
                ],
            }

        if width_height_ratio < 0.28:
            return {
                "video_view": "front_view",
                "confidence": "medium",
                "view_suitability": "moderate",
                "message": (
                    "This video appears to be mostly front view, but the angle is slightly rotated."
                ),
                "capture_guidance": [
                    "Face the camera more directly for reliable knee-tracking analysis.",
                    "Keep both feet and knees clearly visible throughout the set.",
                ],
            }

        return {
            "video_view": "front_view",
            "confidence": "high",
            "view_suitability": "good",
            "message": "This video appears to be a strong front-view squat recording.",
            "capture_guidance": [
                "This angle is suitable for front-view knee-tracking analysis.",
            ],
        }

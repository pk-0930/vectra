import math

from shared.pose_utils import get_primary_value, get_side_quality


class TorsoLeanRule:
    def _score_torso_candidate(self, pose, bottom_frame, preferred_side=None):
        shoulder_x = get_primary_value(
            pose,
            "shoulder",
            "x",
            preferred_side=preferred_side
        )
        shoulder_y = get_primary_value(
            pose,
            "shoulder",
            "y",
            preferred_side=preferred_side
        )
        hip_x = get_primary_value(pose, "hip", "x", preferred_side=preferred_side)
        hip_y = get_primary_value(pose, "hip", "y", preferred_side=preferred_side)

        dx = shoulder_x - hip_x
        dy = shoulder_y - hip_y

        if abs(dy) <= 0.0001:
            return None

        angle_from_vertical = math.degrees(math.atan2(abs(dx), abs(dy)))
        frame_distance = abs(pose["frame_index"] - bottom_frame)
        score = angle_from_vertical - (frame_distance * 2.5)

        return score, angle_from_vertical

    def _get_candidate_poses(self, pose_results, rep, preferred_side=None):
        bottom_frame = rep.get("bottom_frame")

        if bottom_frame is None:
            return []

        candidate_poses = [
            pose for pose in pose_results
            if abs(pose["frame_index"] - bottom_frame) <= 6
        ]

        if not candidate_poses:
            start_frame = rep.get("start_frame")
            end_frame = rep.get("end_frame")

            if start_frame is None or end_frame is None:
                return []

            candidate_poses = [
                pose for pose in pose_results
                if start_frame <= pose["frame_index"] <= end_frame
            ]

        if preferred_side is None:
            return candidate_poses

        high_quality = [
            pose for pose in candidate_poses
            if get_side_quality(pose, preferred_side) >= 0.45
        ]

        if len(high_quality) >= 3:
            return high_quality

        medium_quality = [
            pose for pose in candidate_poses
            if get_side_quality(pose, preferred_side) >= 0.30
        ]

        return medium_quality if medium_quality else candidate_poses

    def evaluate(self, pose_results, reps, preferred_side=None):
        rep_torso_lean = []

        for rep in reps:
            bottom_frame = rep["bottom_frame"]
            candidate_poses = self._get_candidate_poses(
                pose_results,
                rep,
                preferred_side=preferred_side
            )

            best_pose = None
            best_frame = None
            largest_angle = None
            best_score = None

            for pose in candidate_poses:
                scored = self._score_torso_candidate(
                    pose,
                    bottom_frame,
                    preferred_side=preferred_side
                )
                if scored is None:
                    continue

                score, angle_from_vertical = scored

                if best_score is None or score > best_score:
                    best_score = score
                    largest_angle = angle_from_vertical
                    best_pose = pose
                    best_frame = pose["frame_index"]

            if best_pose is None:
                rep_torso_lean.append({
                    "rep_number": rep["rep_number"],
                    "bottom_frame": bottom_frame,
                    "evaluated_frame": None,
                    "torso_lean_status": "unknown",
                    "message": "No usable pose data found near bottom position."
                })
                continue

            shoulder_x = get_primary_value(
                best_pose,
                "shoulder",
                "x",
                preferred_side=preferred_side
            )
            shoulder_y = get_primary_value(
                best_pose,
                "shoulder",
                "y",
                preferred_side=preferred_side
            )
            hip_x = get_primary_value(best_pose, "hip", "x", preferred_side=preferred_side)
            hip_y = get_primary_value(best_pose, "hip", "y", preferred_side=preferred_side)

            dx = shoulder_x - hip_x
            dy = shoulder_y - hip_y

            angle_from_vertical = math.degrees(math.atan2(abs(dx), abs(dy)))

            # More coach-friendly MVP thresholds
            if angle_from_vertical < 40:
                status = "upright"
                message = "Torso remains relatively upright at the bottom position."
            elif angle_from_vertical < 62:
                status = "moderate_lean"
                message = "Moderate forward torso lean detected at the bottom."
            else:
                status = "excessive_lean"
                message = "Excessive forward torso lean detected at the bottom."

            rep_torso_lean.append({
                "rep_number": rep["rep_number"],
                "bottom_frame": bottom_frame,
                "evaluated_frame": best_frame,
                "torso_angle_degrees": float(angle_from_vertical),
                "torso_lean_status": status,
                "message": message
            })

        return {
            "rep_torso_lean": rep_torso_lean
        }

from shared.pose_utils import get_primary_value, get_side_quality


class DepthRule:
    def _score_depth_candidate(self, pose, bottom_frame, preferred_side=None):
        hip_y = get_primary_value(pose, "hip", "y", preferred_side=preferred_side)
        knee_y = get_primary_value(pose, "knee", "y", preferred_side=preferred_side)
        depth_delta = hip_y - knee_y
        frame_distance = abs(pose["frame_index"] - bottom_frame)

        # Keep the evaluated depth frame close to the chosen bottom frame.
        score = depth_delta - (frame_distance * 0.015)

        return score, hip_y, knee_y, depth_delta

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
        rep_depths = []

        for rep in reps:
            bottom_frame = rep["bottom_frame"]
            candidate_poses = self._get_candidate_poses(
                pose_results,
                rep,
                preferred_side=preferred_side
            )

            best_pose = None
            best_frame = None
            best_depth_delta = None
            best_score = None

            for pose in candidate_poses:
                score, hip_y, knee_y, depth_delta = self._score_depth_candidate(
                    pose,
                    bottom_frame,
                    preferred_side=preferred_side
                )

                if best_score is None or score > best_score:
                    best_score = score
                    best_depth_delta = depth_delta
                    best_pose = pose
                    best_frame = pose["frame_index"]

            if best_pose is None:
                rep_depths.append({
                    "rep_number": rep["rep_number"],
                    "bottom_frame": bottom_frame,
                    "evaluated_frame": None,
                    "depth_status": "unknown",
                    "message": "No usable pose data found near bottom position."
                })
                continue

            hip_y = get_primary_value(best_pose, "hip", "y", preferred_side=preferred_side)
            knee_y = get_primary_value(best_pose, "knee", "y", preferred_side=preferred_side)
            depth_delta = hip_y - knee_y

            # bigger y = lower on screen
            # positive delta means hips are lower than knees
            if depth_delta >= 0.02:
                depth_status = "below_parallel"
                message = "Hips are clearly below knee level at the bottom position."
            elif depth_delta >= -0.015:
                depth_status = "at_parallel"
                message = "Hips are approximately at knee level at the bottom position."
            else:
                depth_status = "above_parallel"
                message = "Hips are above knee level at the bottom position."

            rep_depths.append({
                "rep_number": rep["rep_number"],
                "bottom_frame": bottom_frame,
                "evaluated_frame": best_frame,
                "avg_hip_y": float(hip_y),
                "avg_knee_y": float(knee_y),
                "depth_delta": float(depth_delta),
                "depth_status": depth_status,
                "message": message
            })

        return {
            "rep_depths": rep_depths
        }

import os

import cv2
import numpy as np

from shared.frame_annotator import FrameAnnotator
from shared.frame_extractor import save_annotated_frame
from shared.view_classifier import ViewClassifier
from shared.pose_utils import (
    get_dominant_side,
    get_joint_angle,
    get_primary_value,
    get_side_quality,
)
from rules.squat.rep_detection_rule import RepDetectionRule
from rules.squat.depth_rule import DepthRule
from rules.squat.knee_tracking_rule import KneeTrackingRule
from rules.squat.torso_lean_rule import TorsoLeanRule
from rules.squat.feedback_engine import FeedbackEngine
from rules.squat.recommendation_engine import RecommendationEngine


class SquatAnalyzer:
    def __init__(self):
        self.view_classifier = ViewClassifier()
        self.rep_detection_rule = RepDetectionRule()
        self.depth_rule = DepthRule()
        self.knee_tracking_rule = KneeTrackingRule()
        self.torso_lean_rule = TorsoLeanRule()
        self.feedback_engine = FeedbackEngine()
        self.recommendation_engine = RecommendationEngine()
        self.frame_annotator = FrameAnnotator()

    def _safe_video_name(self, video_path: str) -> str:
        base_name = os.path.basename(video_path)
        name_without_ext = os.path.splitext(base_name)[0]
        return "".join(c if c.isalnum() or c in ("_", "-") else "_" for c in name_without_ext)

    def _read_frame(self, frames_folder: str, frame_index: int):
        frame_path = os.path.join(frames_folder, f"frame_{frame_index}.jpg")
        if not os.path.exists(frame_path):
            return None
        return cv2.imread(frame_path, cv2.IMREAD_GRAYSCALE)

    def _estimate_background(self, frames_folder: str, frame_indices):
        sample_indices = sorted(set(frame_indices[:: max(len(frame_indices) // 12, 1)]))
        sample_frames = []

        for frame_index in sample_indices:
            frame = self._read_frame(frames_folder, frame_index)
            if frame is not None:
                sample_frames.append(frame.astype(np.float32))

        if not sample_frames:
            return None

        return np.median(np.stack(sample_frames, axis=0), axis=0).astype(np.uint8)

    def _get_body_box(self, frame_gray, background_gray):
        diff = cv2.absdiff(frame_gray, background_gray)
        _, mask = cv2.threshold(diff, 28, 255, cv2.THRESH_BINARY)
        kernel = np.ones((5, 5), np.uint8)
        mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel)
        mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)

        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        contours = [contour for contour in contours if cv2.contourArea(contour) >= 2500]

        if not contours:
            return None

        largest = max(contours, key=cv2.contourArea)
        x, y, w, h = cv2.boundingRect(largest)
        return {
            "x": x,
            "y": y,
            "w": w,
            "h": h,
        }

    def _refine_bottom_frames_for_side_view(self, pose_results, reps, preferred_side=None):
        refined_reps = []

        for rep in reps:
            start_frame = rep["start_frame"]
            end_frame = rep["end_frame"]
            full_candidate_poses = [
                pose for pose in pose_results
                if start_frame <= pose["frame_index"] <= end_frame
            ]

            if not full_candidate_poses:
                refined_reps.append(rep)
                continue

            quality_filtered_poses = full_candidate_poses
            if preferred_side is not None:
                high_quality = [
                    pose for pose in full_candidate_poses
                    if get_side_quality(pose, preferred_side) >= 0.45
                ]

                if len(high_quality) >= 3:
                    quality_filtered_poses = high_quality
                else:
                    medium_quality = [
                        pose for pose in full_candidate_poses
                        if get_side_quality(pose, preferred_side) >= 0.30
                    ]
                    if medium_quality:
                        quality_filtered_poses = medium_quality

            if len(quality_filtered_poses) >= 5:
                candidate_poses = quality_filtered_poses[1:-1]
            else:
                candidate_poses = quality_filtered_poses

            hip_y_values = [
                get_primary_value(p, "hip", "y", preferred_side=preferred_side)
                for p in candidate_poses
            ]

            hip_knee_gap_values = [
                abs(
                    get_primary_value(p, "hip", "y", preferred_side=preferred_side) -
                    get_primary_value(p, "knee", "y", preferred_side=preferred_side)
                )
                for p in candidate_poses
            ]
            knee_angles = [
                get_joint_angle(
                    p,
                    "hip",
                    "knee",
                    "ankle",
                    preferred_side=preferred_side
                )
                for p in candidate_poses
            ]

            min_hip_y = min(hip_y_values)
            max_hip_y = max(hip_y_values)
            min_gap = min(hip_knee_gap_values)
            max_gap = max(hip_knee_gap_values)
            min_knee_angle = min(knee_angles)
            max_knee_angle = max(knee_angles)
            movement_span = max(max_hip_y - min_hip_y, 0.0001)

            best_pose = None
            best_score = None

            for pose_index, pose in enumerate(candidate_poses):
                hip_y = get_primary_value(pose, "hip", "y", preferred_side=preferred_side)
                knee_y = get_primary_value(pose, "knee", "y", preferred_side=preferred_side)
                hip_knee_gap = abs(hip_y - knee_y)
                knee_angle = get_joint_angle(
                    pose,
                    "hip",
                    "knee",
                    "ankle",
                    preferred_side=preferred_side
                )

                hip_depth_score = (hip_y - min_hip_y) / movement_span

                if max_gap - min_gap > 0.0001:
                    knee_bend_score = 1.0 - ((hip_knee_gap - min_gap) / (max_gap - min_gap))
                else:
                    knee_bend_score = 0.0

                if max_knee_angle - min_knee_angle > 0.0001:
                    knee_flexion_score = 1.0 - (
                        (knee_angle - min_knee_angle) / (max_knee_angle - min_knee_angle)
                    )
                else:
                    knee_flexion_score = 0.0

                if 0 < pose_index < len(candidate_poses) - 1:
                    prev_pose = candidate_poses[pose_index - 1]
                    next_pose = candidate_poses[pose_index + 1]
                    prev_hip_y = get_primary_value(
                        prev_pose,
                        "hip",
                        "y",
                        preferred_side=preferred_side
                    )
                    next_hip_y = get_primary_value(
                        next_pose,
                        "hip",
                        "y",
                        preferred_side=preferred_side
                    )
                    turnaround_delta = abs(next_hip_y - prev_hip_y)
                    turnaround_score = 1.0 - min(turnaround_delta / movement_span, 1.0)
                else:
                    turnaround_score = 0.0

                rep_midpoint = (start_frame + end_frame) / 2
                distance_from_mid = abs(pose["frame_index"] - rep_midpoint)
                rep_half_length = max((end_frame - start_frame) / 2, 1)
                center_preference_score = 1.0 - min(distance_from_mid / rep_half_length, 1.0)

                side_quality_score = (
                    get_side_quality(pose, preferred_side)
                    if preferred_side is not None
                    else 1.0
                )

                bottom_score = (
                    (knee_flexion_score * 0.45) +
                    (hip_depth_score * 0.30) +
                    (knee_bend_score * 0.10) +
                    (turnaround_score * 0.15) +
                    (center_preference_score * 0.05) +
                    (side_quality_score * 0.05)
                )

                if best_score is None or bottom_score > best_score:
                    best_score = bottom_score
                    best_pose = pose

            updated_rep = dict(rep)
            chosen_frame = best_pose["frame_index"]

            updated_rep["bottom_frame"] = chosen_frame
            refined_reps.append(updated_rep)

        return refined_reps

    def _build_side_view_frames(
        self,
        video_path: str,
        reps,
        pose_results,
        preferred_side=None,
        rep_depths=None,
        rep_torso_lean=None
    ):
        video_name = self._safe_video_name(video_path)
        output_dir = "outputs/frames"
        os.makedirs(output_dir, exist_ok=True)
        pose_map = {
            pose["frame_index"]: pose
            for pose in pose_results
        }
        depth_map = {
            item["rep_number"]: item
            for item in (rep_depths or [])
        }
        torso_map = {
            item["rep_number"]: item
            for item in (rep_torso_lean or [])
        }

        rep_frames = []

        for rep in reps:
            rep_number = rep["rep_number"]
            frame_number = rep["bottom_frame"]
            filename = f"{video_name}_rep_{rep_number}_frame_{frame_number}.jpg"
            output_path = os.path.join(output_dir, filename)
            pose = pose_map.get(frame_number)
            depth_item = depth_map.get(rep_number, {})
            torso_item = torso_map.get(rep_number, {})

            saved = save_annotated_frame(
                video_path,
                frame_number,
                output_path,
                lambda frame: self.frame_annotator.annotate_side_view_frame(
                    frame=frame,
                    pose=pose,
                    preferred_side=preferred_side,
                    depth_status=depth_item.get("depth_status", "unknown"),
                    torso_lean_status=torso_item.get("torso_lean_status", "unknown"),
                )
            )

            if saved:
                rep_frames.append({
                    "rep_number": rep_number,
                    "frame": frame_number,
                    "image_path": f"/frames/{filename}?v={frame_number}"
                })

        return {
            "rep_frames": rep_frames
        }

    def _build_front_view_frame(self, video_path: str, pose_results, knee_tracking):
        evaluated_frame = knee_tracking.get("evaluated_frame")
        if evaluated_frame is None:
            return {
                "knee_frame": None
            }

        video_name = self._safe_video_name(video_path)
        output_dir = "outputs/frames"
        os.makedirs(output_dir, exist_ok=True)
        pose_map = {
            pose["frame_index"]: pose
            for pose in pose_results
        }

        filename = f"{video_name}_knee_frame_{evaluated_frame}.jpg"
        output_path = os.path.join(output_dir, filename)
        pose = pose_map.get(evaluated_frame)

        saved = save_annotated_frame(
            video_path,
            evaluated_frame,
            output_path,
            lambda frame: self.frame_annotator.annotate_front_view_frame(
                frame=frame,
                pose=pose,
                knee_tracking_status=knee_tracking.get("status", "unknown"),
            )
        )

        if not saved:
            return {
                "knee_frame": None
            }

        return {
            "knee_frame": {
                "frame": evaluated_frame,
                "image_path": f"/frames/{filename}?v={evaluated_frame}"
            }
        }

    def _refine_bottom_frames_from_images(self, frames_folder: str, reps):
        if not frames_folder or not os.path.isdir(frames_folder):
            return reps

        all_indices = []
        for rep in reps:
            all_indices.extend(range(rep["start_frame"], rep["end_frame"] + 1))

        if not all_indices:
            return reps

        background = self._estimate_background(frames_folder, all_indices)
        if background is None:
            return reps

        refined_reps = []

        for rep in reps:
            best_frame = rep["bottom_frame"]
            best_score = None
            search_start = max(rep["start_frame"], rep["bottom_frame"] - 8)
            search_end = min(rep["end_frame"], rep["bottom_frame"] + 8)

            for frame_index in range(search_start, search_end + 1):
                frame_gray = self._read_frame(frames_folder, frame_index)
                if frame_gray is None:
                    continue

                body_box = self._get_body_box(frame_gray, background)
                if body_box is None:
                    continue

                top_y = body_box["y"]
                height = body_box["h"]
                width = body_box["w"]
                squat_compactness = width / max(height, 1)
                frame_distance = abs(frame_index - rep["bottom_frame"])

                score = (
                    (top_y * 0.50) +
                    (squat_compactness * 140.0) +
                    ((1.0 / max(height, 1)) * 7000.0) -
                    (frame_distance * 2.5)
                )

                if best_score is None or score > best_score:
                    best_score = score
                    best_frame = frame_index

            updated_rep = dict(rep)
            updated_rep["bottom_frame"] = best_frame
            refined_reps.append(updated_rep)

        return refined_reps

    def _build_capture_quality_response(self, response, video_view, view_suitability):
        if view_suitability == "moderate" and video_view == "side_view":
            response["supported_analysis"] = [
                "rep_detection"
            ]
            response["unsupported_analysis"] = [
                "depth",
                "torso_lean",
                "knee_tracking"
            ]
            response["frames"] = {
                "rep_frames": []
            }
            response["recommendation"] = (
                "Vectra detected a mostly side-view video, but the angle is not clean enough for reliable depth or torso-lean analysis. "
                "Rep detection is still available. Re-record from a truer side view if you want depth and torso-lean feedback."
            )
            return response

        if view_suitability == "moderate" and video_view == "front_view":
            response["supported_analysis"] = [
                "knee_tracking"
            ]
            response["unsupported_analysis"] = [
                "rep_detection",
                "depth",
                "torso_lean"
            ]
            response["recommendation"] = (
                "Vectra detected a mostly front-view video. Knee tracking is available, but the camera is slightly rotated, "
                "so treat the result as usable with some caution. Re-record from a straighter front view if you want the cleanest knee-tracking assessment."
            )
            return response

        response["supported_analysis"] = []
        response["unsupported_analysis"] = [
            "rep_detection",
            "depth",
            "torso_lean",
            "knee_tracking"
        ]
        response["frames"] = {}
        response["recommendation"] = (
            "Vectra could not confidently classify this recording as a usable side or front view. "
            "Please upload a clearer side-view video for rep count, depth, and torso lean, or a clearer front-view video for knee tracking."
        )
        return response

    def analyze(self, pose_results, video_path: str, frames_folder: str | None = None):
        view_result = self.view_classifier.classify(pose_results)
        video_view = view_result["video_view"]
        view_suitability = view_result.get("view_suitability", "not_sufficient")

        response = {
            **view_result,
            "supported_analysis": [],
            "unsupported_analysis": [],
            "recommendation": ""
        }

        if video_view == "side_view" and view_suitability in {"good", "moderate"}:
            preferred_side = get_dominant_side(pose_results)
            rep_result = self.rep_detection_rule.evaluate(
                pose_results,
                preferred_side=preferred_side
            )

            if not rep_result["squat_detected"]:
                result = {
                    **response,
                    **rep_result,
                    "frames": {
                        "rep_frames": []
                    },
                    "recommendation": (
                        "This is a side-view squat video, but no clear squat movement was detected."
                    )
                }

                corrective = self.recommendation_engine.build(video_view, result)
                result.update(corrective)
                result["feedback"] = self.feedback_engine.build(
                    video_view,
                    result,
                    corrective.get("corrective_recommendations", [])
                )
                return result

            if view_suitability == "moderate":
                response.update(rep_result)
                response = self._build_capture_quality_response(
                    response=response,
                    video_view=video_view,
                    view_suitability=view_suitability
                )
                corrective = self.recommendation_engine.build(video_view, response)
                response.update(corrective)
                response["feedback"] = self.feedback_engine.build(
                    video_view,
                    response,
                    corrective.get("corrective_recommendations", [])
                )
                return response

            refined_reps = self._refine_bottom_frames_for_side_view(
                pose_results=pose_results,
                reps=rep_result["reps"],
                preferred_side=preferred_side
            )

            rep_result["reps"] = refined_reps

            depth_result = self.depth_rule.evaluate(
                pose_results=pose_results,
                reps=refined_reps,
                preferred_side=preferred_side
            )

            torso_lean_result = self.torso_lean_rule.evaluate(
                pose_results=pose_results,
                reps=refined_reps,
                preferred_side=preferred_side
            )

            response.update(rep_result)
            response.update(depth_result)
            response.update(torso_lean_result)

            frames = self._build_side_view_frames(
                video_path=video_path,
                reps=refined_reps,
                pose_results=pose_results,
                preferred_side=preferred_side,
                rep_depths=depth_result.get("rep_depths", []),
                rep_torso_lean=torso_lean_result.get("rep_torso_lean", []),
            )

            response["frames"] = frames

            response["supported_analysis"] = [
                "rep_detection",
                "depth",
                "torso_lean"
            ]

            response["unsupported_analysis"] = [
                "knee_tracking"
            ]

            response["recommendation"] = (
                "This video is detected as side view. Rep count, depth, and torso lean are available. "
                "Upload a front-view squat video to analyze knee tracking."
            )

            corrective = self.recommendation_engine.build(video_view, response)
            response.update(corrective)
            response["feedback"] = self.feedback_engine.build(
                video_view,
                response,
                corrective.get("corrective_recommendations", [])
            )
            return response

        if video_view == "front_view" and view_suitability in {"good", "moderate"}:
            knee_tracking_result = self.knee_tracking_rule.evaluate(pose_results)
            frames = self._build_front_view_frame(
                video_path=video_path,
                pose_results=pose_results,
                knee_tracking=knee_tracking_result.get("knee_tracking", {})
            )

            response.update(knee_tracking_result)
            response["frames"] = frames

            response["supported_analysis"] = [
                "knee_tracking"
            ]

            response["unsupported_analysis"] = [
                "rep_detection",
                "depth",
                "torso_lean"
            ]

            if view_suitability == "moderate":
                response["recommendation"] = (
                    "This video is detected as mostly front view. Knee tracking is available, but the angle is slightly rotated. "
                    "Upload a straighter front-view squat video for the most reliable knee-tracking read, or a side-view squat video for rep count, depth, and torso lean."
                )
            else:
                response["recommendation"] = (
                    "This video is detected as front view. Knee tracking is available. "
                    "Upload a side-view squat video to analyze rep count, depth, and torso lean."
                )

            corrective = self.recommendation_engine.build(video_view, response)
            response.update(corrective)
            response["feedback"] = self.feedback_engine.build(
                video_view,
                response,
                corrective.get("corrective_recommendations", [])
            )
            return response

        response = self._build_capture_quality_response(
            response=response,
            video_view=video_view,
            view_suitability=view_suitability
        )

        corrective = self.recommendation_engine.build(video_view, response)
        response.update(corrective)
        response["feedback"] = self.feedback_engine.build(
            video_view,
            response,
            corrective.get("corrective_recommendations", [])
        )
        return response

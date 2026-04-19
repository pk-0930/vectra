import unittest
from unittest.mock import patch
import numpy as np

from analyzers.squat_analyzer import SquatAnalyzer
from rules.squat.depth_rule import DepthRule
from rules.squat.rep_detection_rule import RepDetectionRule
from rules.squat.torso_lean_rule import TorsoLeanRule
from shared.frame_annotator import FrameAnnotator
from shared.view_classifier import ViewClassifier


def build_pose(frame_index: int, hip_y: float, knee_y: float, shoulder_x: float = 0.50, hip_x: float = 0.52):
    return {
        "frame_index": frame_index,
        "left_shoulder_x": shoulder_x,
        "right_shoulder_x": shoulder_x,
        "left_shoulder_y": hip_y - 0.28,
        "right_shoulder_y": hip_y - 0.28,
        "left_hip_x": hip_x,
        "right_hip_x": hip_x,
        "left_hip_y": hip_y,
        "right_hip_y": hip_y,
        "left_knee_x": 0.50,
        "right_knee_x": 0.50,
        "left_knee_y": knee_y,
        "right_knee_y": knee_y,
        "left_ankle_x": 0.50,
        "right_ankle_x": 0.50,
        "left_ankle_y": knee_y + 0.20,
        "right_ankle_y": knee_y + 0.20,
    }


class SideViewSquatLogicTests(unittest.TestCase):
    def test_side_view_frame_annotation_draws_on_frame(self):
        annotator = FrameAnnotator()
        frame = np.zeros((200, 200, 3), dtype=np.uint8)
        pose = build_pose(frame_index=10, hip_y=0.60, knee_y=0.68)
        pose["left_shoulder_x"] = 0.50
        pose["left_hip_x"] = 0.52
        pose["left_knee_x"] = 0.54

        annotated = annotator.annotate_side_view_frame(
            frame=frame.copy(),
            pose=pose,
            preferred_side="left",
            depth_status="below_parallel",
            torso_lean_status="moderate_lean",
        )

        self.assertGreater(int(annotated.sum()), 0)

    def test_front_view_frame_annotation_draws_on_frame(self):
        annotator = FrameAnnotator()
        frame = np.zeros((200, 200, 3), dtype=np.uint8)
        pose = build_pose(frame_index=10, hip_y=0.60, knee_y=0.68)
        pose["left_knee_x"] = 0.40
        pose["right_knee_x"] = 0.60
        pose["left_ankle_x"] = 0.38
        pose["right_ankle_x"] = 0.62

        annotated = annotator.annotate_front_view_frame(
            frame=frame.copy(),
            pose=pose,
            knee_tracking_status="moderate_knee_cave",
        )

        self.assertGreater(int(annotated.sum()), 0)

    def test_frame_annotation_scales_line_thickness_for_large_frames(self):
        annotator = FrameAnnotator()
        small_frame = np.zeros((200, 200, 3), dtype=np.uint8)
        large_frame = np.zeros((1920, 1080, 3), dtype=np.uint8)

        self.assertGreaterEqual(annotator._line_thickness(small_frame), 6)
        self.assertGreater(annotator._line_thickness(large_frame), annotator._line_thickness(small_frame))

    def test_side_view_frame_uses_actual_bottom_frame(self):
        analyzer = SquatAnalyzer()

        reps = [{
            "rep_number": 2,
            "start_frame": 60,
            "bottom_frame": 72,
            "end_frame": 80,
        }]
        depth_result = {
            "rep_depths": [{
                "rep_number": 2,
                "evaluated_frame": 70,
            }]
        }
        torso_result = {
            "rep_torso_lean": [{
                "rep_number": 2,
                "evaluated_frame": 71,
            }]
        }

        with patch("analyzers.squat_analyzer.save_annotated_frame", return_value=True) as mocked_save:
            frames = analyzer._build_side_view_frames(
                video_path="demo.mp4",
                reps=reps,
                pose_results=[build_pose(frame_index=72, hip_y=0.60, knee_y=0.68)],
                preferred_side="left",
                rep_depths=depth_result["rep_depths"],
                rep_torso_lean=torso_result["rep_torso_lean"],
            )

        mocked_save.assert_called_once()
        self.assertEqual(mocked_save.call_args[0][1], 72)
        self.assertEqual(frames["rep_frames"][0]["frame"], 72)

    def test_view_classifier_marks_clean_side_view_as_good(self):
        classifier = ViewClassifier()
        pose_results = [
            build_pose(frame_index=i, hip_y=0.50, knee_y=0.66, shoulder_x=0.50, hip_x=0.52)
            for i in range(24)
        ]

        result = classifier.classify(pose_results)

        self.assertEqual(result["video_view"], "side_view")
        self.assertEqual(result["view_suitability"], "good")

    def test_image_refinement_is_not_applied_to_side_view_bottom_frames(self):
        analyzer = SquatAnalyzer()
        pose_results = [
            build_pose(frame_index=100, hip_y=0.42, knee_y=0.64),
            build_pose(frame_index=101, hip_y=0.52, knee_y=0.64),
            build_pose(frame_index=102, hip_y=0.68, knee_y=0.64),
            build_pose(frame_index=103, hip_y=0.56, knee_y=0.64),
            build_pose(frame_index=104, hip_y=0.43, knee_y=0.64),
            build_pose(frame_index=105, hip_y=0.41, knee_y=0.64),
        ]
        reps = [{
            "rep_number": 1,
            "start_frame": 100,
            "bottom_frame": 104,
            "end_frame": 105,
        }]

        pose_refined = analyzer._refine_bottom_frames_for_side_view(pose_results, reps)

        with patch.object(
            analyzer,
            "_refine_bottom_frames_from_images",
            return_value=[{**reps[0], "bottom_frame": 100}]
        ) as mocked_image_refine:
            final_reps = pose_refined

        mocked_image_refine.assert_not_called()
        self.assertEqual(pose_refined[0]["bottom_frame"], 102)
        self.assertEqual(final_reps[0]["bottom_frame"], 102)

    def test_view_classifier_marks_slightly_angled_side_view_as_moderate(self):
        classifier = ViewClassifier()
        pose_results = []
        for i in range(24):
            pose = build_pose(frame_index=i, hip_y=0.50, knee_y=0.66)
            pose["left_shoulder_x"] = 0.465
            pose["right_shoulder_x"] = 0.535
            pose["left_hip_x"] = 0.47
            pose["right_hip_x"] = 0.54
            pose["left_ankle_x"] = 0.475
            pose["right_ankle_x"] = 0.545
            pose_results.append(pose)

        result = classifier.classify(pose_results)

        self.assertEqual(result["video_view"], "side_view")
        self.assertEqual(result["view_suitability"], "moderate")

    def test_analyzer_skips_angle_sensitive_side_rules_for_moderate_side_view(self):
        analyzer = SquatAnalyzer()
        hip_y_values = [
            0.40, 0.40, 0.41, 0.43, 0.48, 0.54, 0.60, 0.65, 0.69, 0.67, 0.61, 0.53, 0.46, 0.42,
            0.40, 0.40, 0.41, 0.44, 0.49, 0.55, 0.61, 0.66, 0.70, 0.68, 0.62, 0.54, 0.47, 0.42,
            0.40, 0.40,
        ]
        pose_results = []
        for i, hip_y in enumerate(hip_y_values):
            pose = build_pose(frame_index=i, hip_y=hip_y, knee_y=0.66)
            pose["left_shoulder_x"] = 0.465
            pose["right_shoulder_x"] = 0.535
            pose["left_hip_x"] = 0.47
            pose["right_hip_x"] = 0.54
            pose["left_ankle_x"] = 0.475
            pose["right_ankle_x"] = 0.545
            pose_results.append(pose)

        result = analyzer.analyze(pose_results, video_path="demo.mp4", frames_folder=None)

        self.assertEqual(result["video_view"], "side_view")
        self.assertEqual(result["view_suitability"], "moderate")
        self.assertEqual(result["supported_analysis"], ["rep_detection"])
        self.assertEqual(result["unsupported_analysis"], ["depth", "torso_lean", "knee_tracking"])
        self.assertNotIn("rep_depths", result)
        self.assertNotIn("rep_torso_lean", result)

    def test_view_classifier_marks_slightly_rotated_front_view_as_moderate(self):
        classifier = ViewClassifier()
        pose_results = []
        for i in range(24):
            pose = build_pose(frame_index=i, hip_y=0.50, knee_y=0.66)
            pose["left_shoulder_x"] = 0.43
            pose["right_shoulder_x"] = 0.57
            pose["left_hip_x"] = 0.435
            pose["right_hip_x"] = 0.575
            pose["left_ankle_x"] = 0.44
            pose["right_ankle_x"] = 0.58
            pose_results.append(pose)

        result = classifier.classify(pose_results)

        self.assertEqual(result["video_view"], "front_view")
        self.assertEqual(result["view_suitability"], "moderate")

    def test_rep_detection_counts_three_reps(self):
        rule = RepDetectionRule()
        hip_y_values = [
            0.40, 0.40, 0.41, 0.43, 0.48, 0.54, 0.60, 0.65, 0.69, 0.67, 0.61, 0.53, 0.46, 0.42,
            0.40, 0.40, 0.41, 0.44, 0.49, 0.55, 0.61, 0.66, 0.70, 0.68, 0.62, 0.54, 0.47, 0.42,
            0.40, 0.40, 0.41, 0.45, 0.50, 0.57, 0.63, 0.68, 0.72, 0.69, 0.63, 0.56, 0.48, 0.43,
            0.40, 0.40,
        ]

        pose_results = [
            build_pose(frame_index=i, hip_y=hip_y, knee_y=0.66)
            for i, hip_y in enumerate(hip_y_values)
        ]

        result = rule.evaluate(pose_results)

        self.assertTrue(result["squat_detected"])
        self.assertEqual(result["rep_count"], 3)
        self.assertEqual(len(result["reps"]), 3)

        bottoms = [rep["bottom_frame"] for rep in result["reps"]]
        self.assertEqual(bottoms, sorted(bottoms))
        self.assertTrue(6 <= bottoms[0] <= 10)
        self.assertTrue(20 <= bottoms[1] <= 24)
        self.assertTrue(34 <= bottoms[2] <= 38)

    def test_bottom_frame_refinement_prefers_deepest_pose_in_rep(self):
        analyzer = SquatAnalyzer()
        pose_results = [
            build_pose(frame_index=100, hip_y=0.42, knee_y=0.64),
            build_pose(frame_index=101, hip_y=0.52, knee_y=0.64),
            build_pose(frame_index=102, hip_y=0.68, knee_y=0.64),
            build_pose(frame_index=103, hip_y=0.56, knee_y=0.64),
            build_pose(frame_index=104, hip_y=0.43, knee_y=0.64),
            build_pose(frame_index=105, hip_y=0.41, knee_y=0.64),
        ]

        reps = [{
            "rep_number": 1,
            "start_frame": 100,
            "bottom_frame": 104,
            "end_frame": 105,
        }]

        refined = analyzer._refine_bottom_frames_for_side_view(pose_results, reps)

        self.assertEqual(refined[0]["bottom_frame"], 102)

    def test_depth_rule_uses_best_depth_within_rep_window(self):
        depth_rule = DepthRule()
        pose_results = [
            build_pose(frame_index=200, hip_y=0.44, knee_y=0.64),
            build_pose(frame_index=201, hip_y=0.50, knee_y=0.64),
            build_pose(frame_index=202, hip_y=0.67, knee_y=0.64),
            build_pose(frame_index=203, hip_y=0.47, knee_y=0.64),
            build_pose(frame_index=204, hip_y=0.43, knee_y=0.64),
        ]

        reps = [{
            "rep_number": 1,
            "start_frame": 200,
            "bottom_frame": 204,
            "end_frame": 204,
        }]

        result = depth_rule.evaluate(pose_results, reps)
        rep_depth = result["rep_depths"][0]

        self.assertEqual(rep_depth["evaluated_frame"], 202)
        self.assertEqual(rep_depth["depth_status"], "below_parallel")

    def test_depth_rule_prefers_pose_closer_to_bottom_when_depth_is_similar(self):
        depth_rule = DepthRule()
        pose_results = [
            build_pose(frame_index=300, hip_y=0.63, knee_y=0.64),
            build_pose(frame_index=301, hip_y=0.64, knee_y=0.64),
            build_pose(frame_index=302, hip_y=0.645, knee_y=0.64),
        ]

        reps = [{
            "rep_number": 1,
            "start_frame": 296,
            "bottom_frame": 300,
            "end_frame": 304,
        }]

        result = depth_rule.evaluate(pose_results, reps)
        rep_depth = result["rep_depths"][0]

        self.assertEqual(rep_depth["evaluated_frame"], 300)

    def test_torso_rule_prefers_pose_closer_to_bottom_when_angle_is_similar(self):
        torso_rule = TorsoLeanRule()
        pose_results = [
            build_pose(frame_index=400, hip_y=0.64, knee_y=0.64, shoulder_x=0.56, hip_x=0.52),
            build_pose(frame_index=401, hip_y=0.64, knee_y=0.64, shoulder_x=0.57, hip_x=0.52),
            build_pose(frame_index=402, hip_y=0.64, knee_y=0.64, shoulder_x=0.575, hip_x=0.52),
        ]

        reps = [{
            "rep_number": 1,
            "start_frame": 396,
            "bottom_frame": 400,
            "end_frame": 404,
        }]

        result = torso_rule.evaluate(pose_results, reps)
        rep_torso = result["rep_torso_lean"][0]

        self.assertEqual(rep_torso["evaluated_frame"], 400)


if __name__ == "__main__":
    unittest.main()

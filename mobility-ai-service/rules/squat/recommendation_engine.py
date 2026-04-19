class RecommendationEngine:
    def build(self, video_view, squat_analysis):
        if video_view == "side_view":
            return self._build_side_view_recommendations(squat_analysis)

        if video_view == "front_view":
            return self._build_front_view_recommendations(squat_analysis)

        return {
            "corrective_recommendations": []
        }

    def _build_side_view_recommendations(self, squat_analysis):
        rep_depths = squat_analysis.get("rep_depths", [])
        rep_torso_lean = squat_analysis.get("rep_torso_lean", [])

        recommendations = []

        above_parallel_count = sum(
            1 for item in rep_depths
            if item.get("depth_status") == "above_parallel"
        )

        at_parallel_count = sum(
            1 for item in rep_depths
            if item.get("depth_status") == "at_parallel"
        )

        moderate_lean_count = sum(
            1 for item in rep_torso_lean
            if item.get("torso_lean_status") == "moderate_lean"
        )

        excessive_lean_count = sum(
            1 for item in rep_torso_lean
            if item.get("torso_lean_status") == "excessive_lean"
        )

        if above_parallel_count > 0:
            recommendations.append({
                "issue": "Squat depth above parallel",
                "likely_cause": "Limited depth control or restricted squat pattern.",
                "coaching_cue": "Sit deeper while staying balanced through the whole foot.",
                "corrective_exercise": "Goblet squat hold"
            })

        if at_parallel_count > 0 and above_parallel_count == 0:
            recommendations.append({
                "issue": "Squat depth around parallel",
                "likely_cause": "Depth is close, but may still be inconsistent across reps.",
                "coaching_cue": "Maintain control and aim for consistent depth on every rep.",
                "corrective_exercise": "Paused bodyweight squat"
            })

        if excessive_lean_count > 0:
            recommendations.append({
                "issue": "Excessive forward torso lean",
                "likely_cause": "Poor bottom-position control or difficulty keeping the chest upright.",
                "coaching_cue": "Keep the chest up and stay more upright during descent.",
                "corrective_exercise": "Heel-elevated goblet squat"
            })
        elif moderate_lean_count > 0:
            recommendations.append({
                "issue": "Moderate forward torso lean",
                "likely_cause": "Mild forward collapse during the squat.",
                "coaching_cue": "Brace well and keep the chest more upright as you descend.",
                "corrective_exercise": "Goblet squat tempo reps"
            })

        return {
            "corrective_recommendations": recommendations
        }

    def _build_front_view_recommendations(self, squat_analysis):
        knee_tracking = squat_analysis.get("knee_tracking", {})
        status = knee_tracking.get("status")

        recommendations = []

        if status == "severe_knee_cave":
            recommendations.append({
                "issue": "Significant inward knee tracking",
                "likely_cause": "Reduced knee control under load or unstable squat mechanics.",
                "coaching_cue": "Drive the knees outward and keep them tracking over the feet.",
                "corrective_exercise": "Banded squat"
            })
            recommendations.append({
                "issue": "Stability under squat load",
                "likely_cause": "Difficulty controlling position through the full squat.",
                "coaching_cue": "Slow the movement down and keep even pressure through both feet.",
                "corrective_exercise": "Banded lateral walk"
            })

        elif status == "moderate_knee_cave":
            recommendations.append({
                "issue": "Moderate inward knee tracking",
                "likely_cause": "Inconsistent knee control during the squat.",
                "coaching_cue": "Keep the knees tracking over the feet throughout the rep.",
                "corrective_exercise": "Banded lateral walk"
            })

        elif status == "mild_knee_cave":
            recommendations.append({
                "issue": "Slight inward knee tracking",
                "likely_cause": "Mild loss of alignment near the most difficult part of the squat.",
                "coaching_cue": "Maintain outward knee pressure as you descend and stand up.",
                "corrective_exercise": "Bodyweight squat with band"
            })

        elif status == "tracking_well":
            recommendations.append({
                "issue": "Knee tracking looks stable",
                "likely_cause": "No major inward knee collapse detected.",
                "coaching_cue": "Maintain the same knee path across all reps.",
                "corrective_exercise": "Continue with current squat pattern"
            })

        return {
            "corrective_recommendations": recommendations
        }
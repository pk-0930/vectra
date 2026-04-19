class FeedbackEngine:
    def build(self, video_view, squat_analysis, corrective_recommendations=None):
        if corrective_recommendations is None:
            corrective_recommendations = []

        view_suitability = squat_analysis.get("view_suitability", "not_sufficient")

        if view_suitability == "moderate":
            return self._build_moderate_view_feedback(
                video_view,
                squat_analysis,
                corrective_recommendations
            )

        if video_view == "side_view":
            return self._build_side_view_feedback(
                squat_analysis,
                corrective_recommendations
            )

        if video_view == "front_view":
            return self._build_front_view_feedback(
                squat_analysis,
                corrective_recommendations
            )

        return {
            "summary": {
                "title": "Could not analyze squat reliably",
                "message": (
                    "Vectra could not confidently determine the video view. "
                    "Please upload a clearer side-view squat video for rep count, depth, and torso lean, "
                    "or a front-view squat video for knee tracking."
                )
            },
            "rep_feedback": [],
            "recommendations": [
                "Record a clearer side-view or front-view squat video.",
                "Keep the full body visible in the frame.",
                "Use a stable camera position."
            ],
            "corrective_recommendations": corrective_recommendations
        }

    def _build_moderate_view_feedback(
        self,
        video_view,
        squat_analysis,
        corrective_recommendations
    ):
        supported_analysis = squat_analysis.get("supported_analysis", [])
        guidance = squat_analysis.get("capture_guidance", [])

        if video_view == "side_view":
            rep_count = squat_analysis.get("rep_count", 0)
            message = (
                f"Vectra detected a mostly side-view recording and counted {rep_count} rep(s), "
                "but the camera angle is slightly rotated, so depth and torso-lean analysis were intentionally skipped to avoid unreliable feedback."
            )
        else:
            knee_tracking = squat_analysis.get("knee_tracking", {})
            knee_message = knee_tracking.get(
                "message",
                "Knee tracking was evaluated from a slightly rotated front-view recording."
            )
            message = (
                f"{knee_message} The camera is slightly rotated, so treat this front-view result with a little caution."
            )

        recommendations = []
        recommendations.extend(guidance)

        if not recommendations:
            recommendations.append("Re-record from a cleaner side or front view for full analysis.")

        if not supported_analysis:
            recommendations.append("This upload is usable as a preview of the exercise, but not for rule-based squat assessment.")

        return {
            "summary": {
                "title": "Capture quality limits full analysis",
                "message": message
            },
            "rep_feedback": [],
            "recommendations": recommendations,
            "corrective_recommendations": corrective_recommendations
        }

    def _build_side_view_feedback(self, squat_analysis, corrective_recommendations):
        rep_count = squat_analysis.get("rep_count", 0)
        rep_depths = squat_analysis.get("rep_depths", [])
        rep_torso_lean = squat_analysis.get("rep_torso_lean", [])

        depth_counts = {
            "below_parallel": 0,
            "at_parallel": 0,
            "above_parallel": 0
        }

        for item in rep_depths:
            status = item.get("depth_status")
            if status in depth_counts:
                depth_counts[status] += 1

        torso_counts = {
            "upright": 0,
            "moderate_lean": 0,
            "excessive_lean": 0
        }

        for item in rep_torso_lean:
            status = item.get("torso_lean_status")
            if status in torso_counts:
                torso_counts[status] += 1

        depth_summary_parts = []
        if depth_counts["below_parallel"] > 0:
            depth_summary_parts.append(f"{depth_counts['below_parallel']} rep(s) below parallel")
        if depth_counts["at_parallel"] > 0:
            depth_summary_parts.append(f"{depth_counts['at_parallel']} rep(s) at parallel")
        if depth_counts["above_parallel"] > 0:
            depth_summary_parts.append(f"{depth_counts['above_parallel']} rep(s) above parallel")

        torso_summary = ""
        if torso_counts["excessive_lean"] > 0:
            torso_summary = "Excessive forward torso lean was detected in some reps."
        elif torso_counts["moderate_lean"] > 0:
            torso_summary = "Moderate forward torso lean was observed across the set."
        else:
            torso_summary = "Torso posture remained relatively upright."

        summary_message = (
            f"You completed {rep_count} squat rep(s). "
            + ("Depth results: " + ", ".join(depth_summary_parts) + ". " if depth_summary_parts else "")
            + torso_summary
        )

        rep_feedback = []
        lean_map = {
            item["rep_number"]: item
            for item in rep_torso_lean
        }

        for depth_item in rep_depths:
            rep_number = depth_item["rep_number"]
            issues = []
            suggestions = []

            depth_status = depth_item["depth_status"]
            if depth_status == "above_parallel":
                issues.append("Depth is above parallel.")
                suggestions.append("Try sitting deeper while keeping control at the bottom.")
            elif depth_status == "at_parallel":
                issues.append("Depth is around parallel.")
                suggestions.append("Try reaching slightly more depth if your mobility allows.")
            elif depth_status == "below_parallel":
                issues.append("Depth is below parallel.")
                suggestions.append("Depth looks good. Maintain consistency across reps.")

            lean_item = lean_map.get(rep_number)
            if lean_item:
                torso_status = lean_item["torso_lean_status"]

                if torso_status == "moderate_lean":
                    issues.append("Moderate forward torso lean detected.")
                    suggestions.append("Keep your chest more upright during the descent.")
                elif torso_status == "excessive_lean":
                    issues.append("Excessive forward torso lean detected.")
                    suggestions.append("Focus on keeping the chest up and reducing forward collapse.")
                elif torso_status == "upright":
                    issues.append("Torso position looks upright.")
                    suggestions.append("Maintain this torso position across all reps.")

            rep_feedback.append({
                "rep_number": rep_number,
                "issues": issues,
                "suggestions": suggestions
            })

        recommendations = []

        if depth_counts["above_parallel"] > 0:
            recommendations.append("Work on squat depth consistency across reps.")
        if torso_counts["moderate_lean"] > 0 or torso_counts["excessive_lean"] > 0:
            recommendations.append("Focus on keeping your chest more upright during the squat.")
        recommendations.append("Upload a front-view squat video if you want knee tracking analysis.")

        return {
            "summary": {
                "title": "Side-view squat analysis",
                "message": summary_message
            },
            "rep_feedback": rep_feedback,
            "recommendations": recommendations,
            "corrective_recommendations": corrective_recommendations
        }

    def _build_front_view_feedback(self, squat_analysis, corrective_recommendations):
        knee_tracking = squat_analysis.get("knee_tracking", {})

        status = knee_tracking.get("status", "unknown")
        message = knee_tracking.get("message", "Knee tracking could not be evaluated.")
        evaluated_frame = knee_tracking.get("evaluated_frame")

        recommendations = []

        if status == "severe_knee_cave":
            recommendations.append("Drive the knees outward more during the descent and ascent.")
            recommendations.append("Reduce load and focus on stable knee tracking.")
        elif status == "moderate_knee_cave":
            recommendations.append("Focus on keeping the knees tracking over the feet.")
            recommendations.append("Use slower reps to improve control.")
        elif status == "mild_knee_cave":
            recommendations.append("Knee tracking is slightly inward. Focus on maintaining outward knee pressure.")
        elif status == "tracking_well":
            recommendations.append("Knee tracking looks good. Maintain this pattern across your sets.")

        recommendations.append("Upload a side-view squat video if you want rep count, depth, and torso lean analysis.")

        rep_feedback = []
        if evaluated_frame is not None:
            rep_feedback.append({
                "frame": evaluated_frame,
                "issues": [message],
                "suggestions": recommendations[:-1] if len(recommendations) > 1 else recommendations
            })

        return {
            "summary": {
                "title": "Front-view squat analysis",
                "message": message
            },
            "rep_feedback": rep_feedback,
            "recommendations": recommendations,
            "corrective_recommendations": corrective_recommendations
        }

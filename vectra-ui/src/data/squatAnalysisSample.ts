export const squatAnalysisSample = {
  status: "Video processed",
  analysis_type: "squat",
  filename: "squats_side_view.mp4",
  frames_extracted: 395,
  pose_frames_detected: 250,
  squat_analysis: {
    video_view: "side_view",
    confidence: "medium",
    message: "This video appears to be a side-view squat recording.",
    supported_analysis: ["rep_detection", "depth", "torso_lean"],
    unsupported_analysis: ["knee_tracking"],
    recommendation:
      "This video is detected as side view. Rep count, depth, and torso lean are available. Upload a front-view squat video to analyze knee tracking.",
    squat_detected: true,
    rep_count: 7,
    movement_range: 0.1432066421617162,
    reps: [
      { rep_number: 1, start_frame: 14, bottom_frame: 26, end_frame: 35 },
      { rep_number: 2, start_frame: 67, bottom_frame: 77, end_frame: 95 },
      { rep_number: 3, start_frame: 124, bottom_frame: 137, end_frame: 158 },
      { rep_number: 4, start_frame: 179, bottom_frame: 192, end_frame: 205 },
      { rep_number: 5, start_frame: 236, bottom_frame: 247, end_frame: 258 },
      { rep_number: 6, start_frame: 291, bottom_frame: 303, end_frame: 312 },
      { rep_number: 7, start_frame: 349, bottom_frame: 357, end_frame: 392 },
    ],
    rep_depths: [
      {
        rep_number: 1,
        depth_status: "at_parallel",
      },
      {
        rep_number: 2,
        depth_status: "at_parallel",
      },
      {
        rep_number: 3,
        depth_status: "at_parallel",
      },
      {
        rep_number: 4,
        depth_status: "at_parallel",
      },
      {
        rep_number: 5,
        depth_status: "below_parallel",
      },
      {
        rep_number: 6,
        depth_status: "at_parallel",
      },
      {
        rep_number: 7,
        depth_status: "above_parallel",
      },
    ],
    rep_torso_lean: [
      {
        rep_number: 1,
        torso_lean_status: "moderate_lean",
        torso_angle_degrees: 55.88,
      },
      {
        rep_number: 2,
        torso_lean_status: "moderate_lean",
        torso_angle_degrees: 52.79,
      },
      {
        rep_number: 3,
        torso_lean_status: "moderate_lean",
        torso_angle_degrees: 56.97,
      },
      {
        rep_number: 4,
        torso_lean_status: "moderate_lean",
        torso_angle_degrees: 59.46,
      },
      {
        rep_number: 5,
        torso_lean_status: "moderate_lean",
        torso_angle_degrees: 57.65,
      },
      {
        rep_number: 6,
        torso_lean_status: "moderate_lean",
        torso_angle_degrees: 57.43,
      },
      {
        rep_number: 7,
        torso_lean_status: "moderate_lean",
        torso_angle_degrees: 45.89,
      },
    ],
    corrective_recommendations: [
      {
        issue: "Squat depth above parallel",
        likely_cause: "Limited depth control or restricted squat pattern.",
        coaching_cue:
          "Sit deeper while staying balanced through the whole foot.",
        corrective_exercise: "Goblet squat hold",
      },
      {
        issue: "Moderate forward torso lean",
        likely_cause: "Mild forward collapse during the squat.",
        coaching_cue:
          "Brace well and keep the chest more upright as you descend.",
        corrective_exercise: "Goblet squat tempo reps",
      },
    ],
    feedback: {
      summary: {
        title: "Side-view squat analysis",
        message:
          "You completed 7 squat rep(s). Depth results: 1 rep(s) below parallel, 5 rep(s) at parallel, 1 rep(s) above parallel. Moderate forward torso lean was observed across the set.",
      },
      recommendations: [
        "Work on squat depth consistency across reps.",
        "Focus on keeping your chest more upright during the squat.",
        "Upload a front-view squat video if you want knee tracking analysis.",
      ],
    },
  },
};
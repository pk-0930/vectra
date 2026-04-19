export type DepthStatus = "below_parallel" | "at_parallel" | "above_parallel";
export type TorsoLeanStatus = "upright" | "moderate_lean" | "excessive_lean";
export type KneeTrackingStatus =
  | "tracking_well"
  | "mild_knee_cave"
  | "moderate_knee_cave"
  | "severe_knee_cave"
  | "unknown";

export type Rep = {
  rep_number: number;
  start_frame: number;
  bottom_frame: number;
  end_frame: number;
};

export type RepDepth = {
  rep_number: number;
  bottom_frame: number;
  evaluated_frame: number | null;
  avg_hip_y?: number;
  avg_knee_y?: number;
  depth_delta?: number;
  depth_status: DepthStatus;
  message: string;
};

export type RepTorsoLean = {
  rep_number: number;
  bottom_frame: number;
  evaluated_frame: number | null;
  torso_angle_degrees?: number;
  torso_lean_status: TorsoLeanStatus | "unknown";
  message: string;
};

export type KneeTracking = {
  status: KneeTrackingStatus;
  message: string;
  evaluated_frame?: number;
  knee_width?: number;
  ankle_width?: number;
  width_ratio?: number;
  frames_considered?: number;
};

export type CorrectiveRecommendation = {
  issue: string;
  likely_cause: string;
  coaching_cue: string;
  corrective_exercise: string;
};

export type FeedbackSummary = {
  title: string;
  message: string;
};

export type FeedbackRep = {
  rep_number?: number;
  frame?: number;
  issues: string[];
  suggestions: string[];
};

export type Feedback = {
  summary: FeedbackSummary;
  rep_feedback: FeedbackRep[];
  recommendations: string[];
  corrective_recommendations: CorrectiveRecommendation[];
};

export type SquatAnalysis = {
  video_view: "side_view" | "front_view" | "unknown";
  confidence: string;
  view_suitability?: "good" | "moderate" | "not_sufficient";
  message: string;
  supported_analysis: string[];
  unsupported_analysis: string[];
  recommendation: string;
  capture_guidance?: string[];

  squat_detected?: boolean;
  rep_count?: number;
  movement_range?: number;
  reps?: Rep[];
  rep_depths?: RepDepth[];
  rep_torso_lean?: RepTorsoLean[];

  knee_tracking?: KneeTracking;

  frames?: Frames;

  corrective_recommendations?: CorrectiveRecommendation[];
  feedback?: Feedback;
};

export type SquatApiResponse = {
  status: string;
  analysis_type: string;
  filename: string;
  frames_extracted: number;
  pose_frames_detected: number;
  squat_analysis: SquatAnalysis;
};

export type RepFrame = {
  rep_number: number;
  frame: number;
  image_path: string;
};

export type KneeFrame = {
  frame: number;
  image_path: string;
};

export type Frames = {
  rep_frames?: RepFrame[];
  knee_frame?: KneeFrame | null;
};

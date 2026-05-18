export type Client = {
  id: number;
  coach_id: number;
  first_name: string;
  last_name: string;
  dob: string | null;
  gender: string | null;
  height_cm: number | null;
  weight_kg: number | null;
  is_active: boolean;
  current_goal_type: string | null;
  current_goal_notes: string | null;
  created_at: string;
  updated_at: string;
};

export type ClientPayload = {
  first_name: string;
  last_name: string;
  dob?: string;
  gender?: string;
  height_cm?: number;
  weight_kg?: number;
  is_active?: boolean;
};

export type GoalPayload = {
  goal_type: string;
  notes?: string;
  start_date?: string;
  end_date?: string;
};

export type Goal = {
  id: number;
  client_id: number;
  goal_type: string;
  notes: string | null;
  start_date: string | null;
  end_date: string | null;
  is_current: boolean;
};

export type ProgressPhoto = {
  id: number;
  client_id: number;
  blob_name: string;
  caption: string | null;
  timeline_type: string;
  captured_on: string;
  created_at: string;
};

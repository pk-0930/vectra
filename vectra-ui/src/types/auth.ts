export type LoginRequest = {
  email: string;
  password: string;
};

export type CoachProfile = {
  id: number;
  user_id: number;
  first_name: string;
  last_name: string;
  dob: string | null;
  gender: string | null;
  mobile: string | null;
  years_of_experience: number;
  associated_gym: string | null;
  clients_trained: number;
};

export type AuthUser = {
  id: number;
  email: string;
};

export type LoginResponse = {
  access_token: string;
  token_type: string;
  user: AuthUser;
  coach: CoachProfile | null;
};

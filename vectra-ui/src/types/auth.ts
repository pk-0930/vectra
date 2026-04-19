export type LoginRequest = {
  username: string;
  password: string;
};

export type LoginResponse = {
  authenticated: boolean;
  message: string;
  username: string;
};

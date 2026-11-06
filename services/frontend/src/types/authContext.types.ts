import type { User } from "./user.types";

export interface AuthContextType {
  user: User | null;
  login: (accessToken: string, refreshToken: string, userData: User) => void;
  updateUser: (userData: User) => void;
  logout: (revokeSession?: boolean) => Promise<void>;
  isLoading: boolean;
  authError: string | null;
  checkAuthStatus: () => Promise<void>;
}
import type { User } from "./user.types";

export interface AuthContextType {
  user: User | null;
  login: (token: string, userData: User) => void;
  logout: () => void;
  isLoading: boolean;
  checkAuthStatus: () => Promise<void>;
}
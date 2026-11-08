import { useCallback, useEffect, useState, type ReactNode } from 'react';
import axios from 'axios';
import { apiClient, getApiErrorMessage } from '../services/apiClient';
import { mapApiUser } from '../services/api';
import type { ApiUser } from '../types/api.types';
import type { User } from '../types/user.types';
import { AuthContext } from './contextValue';

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [isLoading, setIsLoading] = useState(() =>
    typeof window !== "undefined" && Boolean(localStorage.getItem("access_token")),
  );
  const [authError, setAuthError] = useState<string | null>(null);

  const clearSession = useCallback(() => {
    localStorage.removeItem('access_token');
    localStorage.removeItem('refresh_token');
    localStorage.removeItem('token');
    localStorage.removeItem('user');
    setUser(null);
  }, []);

  const checkAuthStatus = useCallback(async () => {
    const token = localStorage.getItem('access_token');
    
    if (!token) {
      return;
    }

    try {
      const { data } = await apiClient.get<ApiUser>('/auth/me');
      setUser(mapApiUser(data));
      setAuthError(null);
    } catch (error) {
      if (axios.isAxiosError(error) && error.response?.status === 401) {
        clearSession();
      }
      setUser(null);
      setAuthError(getApiErrorMessage(error, 'Could not verify the current session.'));
    } finally {
      setIsLoading(false);
    }
  }, [clearSession]);

  useEffect(() => {
    void Promise.resolve().then(checkAuthStatus);
  }, [checkAuthStatus]);

  useEffect(() => {
    const handleExpiredSession = () => {
      clearSession();
      setIsLoading(false);
      setAuthError("Your session has expired. Please sign in again.");
    };
    window.addEventListener("auth:expired", handleExpiredSession);
    return () => window.removeEventListener("auth:expired", handleExpiredSession);
  }, [clearSession]);

  const login = useCallback((accessToken: string, refreshToken: string, userData: User) => {
    localStorage.setItem('access_token', accessToken);
    localStorage.setItem('refresh_token', refreshToken);
    localStorage.removeItem('token');
    localStorage.removeItem('user');
    setUser(userData);
    setAuthError(null);
  }, []);

  const updateUser = useCallback((userData: User) => {
    setUser(userData);
  }, []);

  const logout = useCallback(async (revokeSession = true) => {
    const refreshToken = localStorage.getItem('refresh_token');
    try {
      if (revokeSession && refreshToken) {
        const { data: tokens } = await apiClient.post<{
          access_token: string;
          refresh_token: string;
        }>('/auth/refresh', { refresh_token: refreshToken });
        localStorage.setItem('access_token', tokens.access_token);
        localStorage.setItem('refresh_token', tokens.refresh_token);
        await apiClient.post('/auth/logout', { refresh_token: tokens.refresh_token });
      }
    } finally {
      clearSession();
      setAuthError(null);
    }
  }, [clearSession]);

  return (
    <AuthContext.Provider value={{ user, login, updateUser, logout, isLoading, authError, checkAuthStatus }}>
      {children}
    </AuthContext.Provider>
  );
}
import React, { createContext, useContext, useState, useEffect } from 'react';
import { apiClient } from '../services/apiClient';
import type { User } from '../types/user.types';
import type { AuthContextType } from '../types/authContext.types';

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  const checkAuthStatus = async () => {
    const token = localStorage.getItem('token');
    
    if (!token) {
      setUser(null);
      setIsLoading(false);
      return;
    }

    try {
      const response = await apiClient.get('/users/profile');
      if (response.data.success) {
        setUser(response.data.data); 
        // console.log(response.data.data);
      } else {
        logout();
      }
    } catch (error) {
      console.warn("Sesja wygasła lub błąd połączenia z backendem");
      logout();
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    const savedUser = localStorage.getItem('user');
    const token = localStorage.getItem('token');
    
    if (savedUser && token) {
      setUser(JSON.parse(savedUser));
    }
    
    checkAuthStatus();
  }, []);

  const login = (token: string, userData: User) => {
    localStorage.setItem('token', token);
    localStorage.setItem('user', JSON.stringify(userData));
    setUser(userData);
  };

  const logout = () => {
    localStorage.removeItem('token');
    localStorage.removeItem('user');
    setUser(null);
  };

  return (
    <AuthContext.Provider value={{ user, login, logout, isLoading, checkAuthStatus }}>
      {children}
    </AuthContext.Provider>
  );
}

export const useAuth = () => {
  const context = useContext(AuthContext);
  if (!context) throw new Error('useAuth must be used within an AuthProvider');
  return context;
};
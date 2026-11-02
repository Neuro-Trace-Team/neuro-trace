export type UserRole = 'admin' | 'doctor';

export interface User {
  id: string;
  email: string;
  role: UserRole;
  firstName: string;
  lastName: string;
  createdAt?: string;
}
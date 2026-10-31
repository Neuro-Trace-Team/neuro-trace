import { Navigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import type { UserRole } from '../types/user.types';

interface Props {
  children: React.ReactNode;
  allowedRoles: UserRole[];
}

function ProtectedRoute({ children, allowedRoles }: Props) {
  const { user, isLoading } = useAuth();

  if (isLoading) return <div>Loading...</div>;
  
  if (!user || !allowedRoles.includes(user.role)) {
    return <Navigate to="/" replace />;
  }

  return <>{children}</>;
}

export default ProtectedRoute;
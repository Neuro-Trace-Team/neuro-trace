import { createBrowserRouter, Navigate, RouterProvider } from "react-router-dom"
import RootLayout from "./layouts/RootLayout"
import AuthLayout from "./layouts/AuthLayout"
import ProtectedRoute from './components/ProtectedRoute';
import RootRedirect from './components/RootRedirect';

import Login from './pages/auth/LoginPage';
import Settings from './pages/SettingsPage';

import DoctorDashboard from './pages/doctor/DoctorDashboardPage';
import DoctorExaminations from './pages/doctor/DoctorExaminationsPage';
import DoctorNewExamination from './pages/doctor/DoctorNewExaminationPage';
import DoctorExaminationDetails from './pages/doctor/DoctorExaminationDetailsPage';

import AdminDashboard from './pages/admin/AdminDashboardPage';
import AdminSystemStatus from './pages/admin/AdminSystemStatusPage';
import AdminUsers from './pages/admin/AdminUsersPage';
import AdminAuditLog from './pages/admin/AdminAuditLogPage';
import { AuthProvider } from "./context/AuthContext";
import { ToastProvider } from "./context/ToastContext";

const router = createBrowserRouter([
  {
    path: '/',
    element: <RootRedirect />
  },
  {
    element: <AuthLayout />,
    children: [
      {
        path: '/auth/login',
        element: <Login />
      }
    ]
  },
  {
    element: <RootLayout />,
    children: [
      {
        path: '/settings',
        element: <ProtectedRoute allowedRoles={['doctor', 'admin']}><Settings /></ProtectedRoute>
      },

      {
        path: '/doctor',
        element: <ProtectedRoute allowedRoles={['doctor']}><DoctorDashboard /></ProtectedRoute>
      },
      {
        path: '/doctor/examinations',
        element: <ProtectedRoute allowedRoles={['doctor']}><DoctorExaminations /></ProtectedRoute>
      },
      {
        path: '/doctor/examinations/new',
        element: <ProtectedRoute allowedRoles={['doctor']}><DoctorNewExamination /></ProtectedRoute>
      },
      {
        path: '/doctor/examinations/:id',
        element: <ProtectedRoute allowedRoles={['doctor']}><DoctorExaminationDetails /></ProtectedRoute>
      },

      {
        path: '/admin',
        element: <ProtectedRoute allowedRoles={['admin']}><AdminDashboard /></ProtectedRoute>
      },
      {
        path: '/admin/users',
        element: <ProtectedRoute allowedRoles={['admin']}><AdminUsers /></ProtectedRoute>
      },
      {
        path: '/admin/system',
        element: <ProtectedRoute allowedRoles={['admin']}><AdminSystemStatus /></ProtectedRoute>
      },
      { path: '/admin/database', element: <Navigate to="/admin/system" replace /> },
      { path: '/admin/activity-log', element: <Navigate to="/admin/audit-log" replace /> },
      {
        path: '/admin/audit-log',
        element: <ProtectedRoute allowedRoles={['admin']}><AdminAuditLog /></ProtectedRoute>
      }
    ]
  }
])

function App() {
  return (
    <ToastProvider>
      <AuthProvider>
        <RouterProvider router={router} />
      </AuthProvider>
    </ToastProvider>
  )
}

export default App
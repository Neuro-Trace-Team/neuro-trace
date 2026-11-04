import { Navigate } from "react-router-dom";
import { useAuth } from "../context/AuthContext";

function RootRedirect() {
    const { user, isLoading } = useAuth();

    if (isLoading) return <div>Loading...</div>;

    if (!user) {
        return <Navigate to="/auth/login" replace />;
    }
    if (user.role === 'doctor') {
        return <Navigate to="/doctor" replace />;
    }
    if (user.role === 'admin') {
        return <Navigate to="/admin" replace />;
    }
    return <>ERROR</>;
}
export default RootRedirect;
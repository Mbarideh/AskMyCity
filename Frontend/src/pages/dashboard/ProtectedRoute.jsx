import { Navigate, useLocation } from "react-router-dom";
import { useAuth } from "../../context/AuthContext";
export default function ProtectedRoute({ children }) {
  const { user, authLoading } = useAuth();
  const location = useLocation();
  if (authLoading) return <div className="dashboard-loading">Loading your account...</div>;
  if (!user) return <Navigate to="/login" replace state={{ from: location.pathname }} />;
  return children;
}

import { Navigate } from "react-router-dom";
import { getToken } from "../api/client";

export function ProtectedRoute({ children }: { children: JSX.Element }): JSX.Element {
  if (!getToken()) {
    return <Navigate to="/login" replace />;
  }
  return children;
}

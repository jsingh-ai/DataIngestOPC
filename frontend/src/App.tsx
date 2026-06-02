import { Navigate, Route, Routes } from "react-router-dom";
import { Layout } from "./components/Layout";
import { ProtectedRoute } from "./components/ProtectedRoute";
import { BrowsePage } from "./pages/BrowsePage";
import { CollectorPage } from "./pages/CollectorPage";
import { HealthPage } from "./pages/HealthPage";
import { LoginPage } from "./pages/LoginPage";
import { MachineFormPage } from "./pages/MachineFormPage";
import { MachinesPage } from "./pages/MachinesPage";
import { TagsPage } from "./pages/TagsPage";

export default function App(): JSX.Element {
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route
        element={
          <ProtectedRoute>
            <Layout />
          </ProtectedRoute>
        }
      >
        <Route path="/" element={<Navigate to="/machines" replace />} />
        <Route path="/machines" element={<MachinesPage />} />
        <Route path="/machines/new" element={<MachineFormPage />} />
        <Route path="/machines/:machineId" element={<MachineFormPage />} />
        <Route path="/machines/:machineId/tags" element={<TagsPage />} />
        <Route path="/machines/:machineId/browse" element={<BrowsePage />} />
        <Route path="/health" element={<HealthPage />} />
        <Route path="/collector" element={<CollectorPage />} />
      </Route>
    </Routes>
  );
}

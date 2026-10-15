import { Navigate, Route, Routes } from "react-router-dom";
import Layout from "./components/Layout";
import { useAuth } from "./context/auth";
import { isPlatformAdmin } from "./lib/format";
import Admin from "./pages/Admin";
import Assistant from "./pages/Assistant";
import Audit from "./pages/Audit";
import Automations from "./pages/Automations";
import CannedResponses from "./pages/CannedResponses";
import HelpCentre from "./pages/HelpCentre";
import Inbox from "./pages/Inbox";
import Integrations from "./pages/Integrations";
import Knowledge from "./pages/Knowledge";
import Login from "./pages/Login";
import Reports from "./pages/Reports";
import Requesters from "./pages/Requesters";
import Signup from "./pages/Signup";
import TicketView from "./pages/TicketView";
import Triggers from "./pages/Triggers";
import Settings from "./pages/Settings";
import Webhooks from "./pages/Webhooks";

function RequireAuth({ children }) {
  const { token } = useAuth();
  if (!token) return <Navigate to="/login" replace />;
  return children;
}

function RequireAdmin({ children }) {
  const { user } = useAuth();
  if (!isPlatformAdmin(user)) return <Navigate to="/inbox" replace />;
  return children;
}

export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<Login />} />
      <Route path="/signup" element={<Signup />} />
      <Route path="/help/:slug" element={<HelpCentre />} />
      <Route path="/help/:slug/:articleSlug" element={<HelpCentre />} />
      <Route
        element={
          <RequireAuth>
            <Layout />
          </RequireAuth>
        }
      >
        <Route path="/" element={<Navigate to="/inbox" replace />} />
        <Route path="/inbox" element={<Inbox />} />
        <Route path="/tickets/:id" element={<TicketView />} />
        <Route path="/integrations" element={<Integrations />} />
        <Route path="/knowledge" element={<Knowledge />} />
        <Route path="/assistant" element={<Assistant />} />
        <Route path="/requesters" element={<Requesters />} />
        <Route path="/webhooks" element={<Webhooks />} />
        <Route path="/reports" element={<Reports />} />
        <Route path="/audit" element={<Audit />} />
        <Route path="/triggers" element={<Triggers />} />
        <Route path="/automations" element={<Automations />} />
        <Route path="/canned-responses" element={<CannedResponses />} />
        <Route path="/settings" element={<Settings />} />
        <Route
          path="/admin"
          element={
            <RequireAdmin>
              <Admin />
            </RequireAdmin>
          }
        />
      </Route>
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}

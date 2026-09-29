import { Navigate, Route, Routes } from "react-router";

import { PlaceholderPage } from "../components/shell/PlaceholderPage";
import { AppShell } from "../components/shell/AppShell";
import { AdminPage } from "../features/admin/AdminPage";
import {
  ForgotPage,
  LoginPage,
  RegisterPage,
  ResetPage,
  UnlockPage,
  VerifyPage,
} from "../features/auth/pages";
import { SettingsPage } from "../features/settings/SettingsPage";
import { useSession } from "./session";

const later =
  "This section is not built in the foundation phase. There is no statement data here, and nothing on this page is a balance.";

export function AppRoutes() {
  const { user, locked, loading } = useSession();
  if (loading) {
    return (
      <main className="grid min-h-screen place-items-center bg-canvas text-ink">
        <p>Loading SpendPilot…</p>
      </main>
    );
  }
  if (locked) return <UnlockPage />;
  if (!user) {
    return (
      <Routes>
        <Route path="/login" element={<LoginPage />} />
        <Route path="/register" element={<RegisterPage />} />
        <Route path="/verify" element={<VerifyPage />} />
        <Route path="/forgot" element={<ForgotPage />} />
        <Route path="/reset" element={<ResetPage />} />
        <Route path="*" element={<Navigate to="/login" replace />} />
      </Routes>
    );
  }
  return (
    <Routes>
      <Route element={<AppShell />}>
        <Route path="/overview" element={<PlaceholderPage title="Overview" detail={later} />} />
        <Route path="/money/cards" element={<PlaceholderPage title="Cards & accounts" detail={later} />} />
        <Route path="/money/transactions" element={<PlaceholderPage title="Transactions" detail={later} />} />
        <Route path="/money/statements" element={<PlaceholderPage title="Statements" detail={later} />} />
        <Route path="/money/obligations" element={<PlaceholderPage title="Obligations" detail={later} />} />
        <Route path="/intelligence/advisor" element={<PlaceholderPage title="Advisor" detail={later} />} />
        <Route path="/intelligence/scenarios" element={<PlaceholderPage title="Scenarios" detail={later} />} />
        <Route path="/settings" element={<SettingsPage />} />
        <Route path="/admin" element={<AdminPage />} />
        <Route path="*" element={<Navigate to="/overview" replace />} />
      </Route>
    </Routes>
  );
}

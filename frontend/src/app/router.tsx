import { Navigate, Route, Routes } from "react-router";

import { AppShell } from "../components/shell/AppShell";
import { AdminPage } from "../features/admin/AdminPage";
import { AdvisorPage } from "../features/advisor/AdvisorPage";
import { AnalyticsPage } from "../features/analytics/AnalyticsPage";
import { CardsPage } from "../features/cards/CardsPage";
import { ObligationsPage } from "../features/obligations/ObligationsPage";
import { OverviewPage } from "../features/overview/OverviewPage";
import { StatementsPage } from "../features/statements/StatementsPage";
import { PreviewPage } from "../features/preview/PreviewPage";
import { TransactionsPage } from "../features/transactions/TransactionsPage";
import {
  ForgotPage,
  LoginPage,
  RegisterPage,
  ResetPage,
  UnlockPage,
  VerifyPage,
} from "../features/auth/pages";
import { ScenariosPage } from "../features/scenarios/ScenariosPage";
import { SettingsPage } from "../features/settings/SettingsPage";
import { useSession } from "./session";

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
        <Route path="/overview" element={<OverviewPage />} />
        <Route path="/money/cards" element={<CardsPage />} />
        <Route path="/money/transactions" element={<TransactionsPage />} />
        <Route path="/money/statements" element={<StatementsPage />} />
        <Route path="/money/analytics" element={<AnalyticsPage />} />
        <Route path="/money/obligations" element={<ObligationsPage />} />
        <Route path="/intelligence/advisor" element={<AdvisorPage />} />
        {import.meta.env.DEV ? <Route path="/dev/components" element={<PreviewPage />} /> : null}
        <Route path="/intelligence/scenarios" element={<ScenariosPage />} />
        <Route path="/settings" element={<SettingsPage />} />
        <Route path="/admin" element={<AdminPage />} />
        <Route path="*" element={<Navigate to="/overview" replace />} />
      </Route>
    </Routes>
  );
}

import { useEffect, useState } from "react";

import {
  clearAccessToken,
  getAccessToken,
  getAlerts,
  getCurrentUser,
  getDashboardSummary,
} from "./api/client";

import Login from "./pages/Login";
import AlertCard from "./components/alerts/AlertCard";
import Sidebar from "./components/layout/Sidebar";
import Header from "./components/layout/Header";
import StatCard from "./components/dashboard/StatCard";

import Alerts from "./pages/Alerts";
import AlertInvestigation from "./pages/AlertInvestigation";
import ActivityExplorer from "./pages/ActivityExplorer";
import UserInvestigation, {
  sampleUsers,
} from "./pages/UserInvestigation";

function normalizeAlert(alert) {
  return {
    ...alert,
    risk_level: String(alert.severity || "LOW").toUpperCase(),
    evidence: Array.isArray(alert.evidence)
      ? alert.evidence.join("; ")
      : String(alert.evidence || ""),
  };
}

function App() {
  const [activePage, setActivePage] = useState("Overview");
  const [selectedUserId, setSelectedUserId] = useState("EMP014");
  const [selectedAlertId, setSelectedAlertId] = useState(null);

  const [authenticated, setAuthenticated] = useState(
    Boolean(getAccessToken())
  );
  const [currentUser, setCurrentUser] = useState(null);
  const [dashboardSummary, setDashboardSummary] = useState(null);
  const [liveAlerts, setLiveAlerts] = useState([]);
  const [loadingData, setLoadingData] = useState(false);
  const [apiError, setApiError] = useState("");

  const riskCounts = {
    LOW: sampleUsers.filter((user) => user.risk_level === "LOW").length,
    MEDIUM: sampleUsers.filter((user) => user.risk_level === "MEDIUM").length,
    HIGH: sampleUsers.filter((user) => user.risk_level === "HIGH").length,
    CRITICAL: sampleUsers.filter(
      (user) => user.risk_level === "CRITICAL"
    ).length,
  };

  useEffect(() => {
    if (!authenticated) return undefined;

    let cancelled = false;

    async function loadDashboard() {
      setLoadingData(true);
      setApiError("");

      try {
        const user = await getCurrentUser();

        if (cancelled) return;
        setCurrentUser(user);

        const [summary, alerts] = await Promise.all([
          getDashboardSummary(),
          getAlerts(),
        ]);

        if (cancelled) return;

        setDashboardSummary(summary);
        setLiveAlerts(
          Array.isArray(alerts) ? alerts.map(normalizeAlert) : []
        );
      } catch (error) {
        if (cancelled) return;

        if (!getAccessToken()) {
          setAuthenticated(false);
          setCurrentUser(null);
        }

        setApiError(
          error.message || "Unable to load data from the ARGUS API."
        );
      } finally {
        if (!cancelled) setLoadingData(false);
      }
    }

    loadDashboard();

    return () => {
      cancelled = true;
    };
  }, [authenticated]);

  function handleLogin() {
    setApiError("");
    setAuthenticated(true);
  }

  function handleLogout() {
    clearAccessToken();
    setAuthenticated(false);
    setCurrentUser(null);
    setDashboardSummary(null);
    setLiveAlerts([]);
    setActivePage("Overview");
    setSelectedAlertId(null);
    setApiError("");
  }

  function investigateUser(userId) {
    setSelectedUserId(userId);
    setActivePage("User Investigation");
  }

  function investigateAlert(alertId) {
    setSelectedAlertId(alertId);
    setActivePage("Alert Investigation");
  }

  function investigateAlertUser(userId) {
    setSelectedUserId(userId);
    setActivePage("User Investigation");
  }

  if (!authenticated) {
    return <Login onLogin={handleLogin} />;
  }

  return (
    <div className="flex min-h-screen bg-slate-100">
      <Sidebar
        activePage={activePage}
        onNavigate={setActivePage}
      />

      <div className="flex min-w-0 flex-1 flex-col">
        <Header user={currentUser} onLogout={handleLogout} />

        <main className="min-w-0 flex-1 p-4 md:p-8">
          {apiError && (
            <div
              role="alert"
              className="mb-6 rounded-lg border border-red-200 bg-red-50 p-4 text-sm text-red-700"
            >
              <p className="font-semibold">ARGUS API error</p>
              <p className="mt-1">{apiError}</p>
              <p className="mt-2">
                Check that FastAPI and MongoDB are running and that your
                account has permission to access this endpoint.
              </p>
            </div>
          )}

          {loadingData && (
            <p className="mb-6 text-sm text-slate-500">
              Loading data from the ARGUS backend...
            </p>
          )}

          {/* SECURITY OVERVIEW */}
          {activePage === "Overview" && (
            <>
              <div className="mb-8">
                <h2 className="text-2xl font-semibold text-slate-900">
                  Security Overview
                </h2>
                <p className="mt-2 text-slate-600">
                  Monitor users, events, alerts, and recorded risk across
                  the organization.
                </p>
              </div>

              <div className="grid grid-cols-1 gap-6 md:grid-cols-2 xl:grid-cols-4">
                <StatCard
                  title="Total Users"
                  value={dashboardSummary?.total_users ?? "—"}
                  description="Users recorded by the backend"
                />

                <StatCard
                  title="Total Events"
                  value={dashboardSummary?.total_events ?? "—"}
                  description="Events recorded by the backend"
                />

                <StatCard
                  title="Total Alerts"
                  value={dashboardSummary?.total_alerts ?? "—"}
                  description="Alerts recorded by the backend"
                />

                <StatCard
                  title="Critical Alerts"
                  value={
                    dashboardSummary?.alerts_by_severity?.critical ?? "—"
                  }
                  description="Critical alerts recorded by the backend"
                />
              </div>

              <section className="mt-8">
                <div className="mb-4">
                  <h3 className="text-xl font-semibold text-slate-900">
                    Recent Alerts
                  </h3>
                  <p className="mt-1 text-sm text-slate-500">
                    Backend alerts with their recorded reasons and evidence.
                  </p>
                </div>

                {liveAlerts.length > 0 ? (
                  <div className="grid grid-cols-1 gap-6 md:grid-cols-2 xl:grid-cols-3">
                    {liveAlerts.slice(0, 6).map((alert) => (
                      <div
                        key={alert.alert_id}
                        className="flex flex-col"
                      >
                        <AlertCard alert={alert} />

                        <button
                          type="button"
                          onClick={() =>
                            investigateAlert(alert.alert_id)
                          }
                          className="mt-3 self-start rounded-lg bg-blue-600 px-4 py-2 text-sm font-medium text-white transition hover:bg-blue-700"
                        >
                          Investigate alert →
                        </button>
                      </div>
                    ))}
                  </div>
                ) : (
                  !loadingData &&
                  !apiError && (
                    <div className="rounded-xl border border-slate-200 bg-white p-6 text-sm text-slate-600">
                      No alerts are currently stored in the backend.
                    </div>
                  )
                )}
              </section>
            </>
          )}

          {/* ALERT CENTER */}
          {activePage === "Alerts" && (
            <Alerts
              alerts={liveAlerts}
              onInvestigateAlert={investigateAlert}
            />
          )}

          {/* ALERT INVESTIGATION */}
          {activePage === "Alert Investigation" && (
            <AlertInvestigation
              alertId={selectedAlertId}
              alerts={liveAlerts}
              onBack={() => setActivePage("Alerts")}
              onInvestigateUser={investigateAlertUser}
            />
          )}

          {/* USER INVESTIGATION - CURRENTLY SAMPLE-BASED */}
          {activePage === "User Investigation" && (
            <UserInvestigation initialUserId={selectedUserId} />
          )}

          {/* RISK OVERVIEW - CURRENTLY SAMPLE-BASED */}
          {activePage === "Risks" && (
            <section className="space-y-6">
              <div>
                <h2 className="text-2xl font-semibold text-slate-900">
                  Risk Overview
                </h2>
                <p className="mt-2 text-slate-600">
                  Illustrative employee risk profiles for the frontend demo.
                </p>
              </div>

              <div className="grid grid-cols-1 gap-6 sm:grid-cols-2 xl:grid-cols-4">
                <StatCard
                  title="Low Risk"
                  value={riskCounts.LOW}
                  description="Illustrative risk score 0–30"
                />
                <StatCard
                  title="Medium Risk"
                  value={riskCounts.MEDIUM}
                  description="Illustrative risk score 31–60"
                />
                <StatCard
                  title="High Risk"
                  value={riskCounts.HIGH}
                  description="Illustrative risk score 61–80"
                />
                <StatCard
                  title="Critical Risk"
                  value={riskCounts.CRITICAL}
                  description="Illustrative risk score 81–100"
                />
              </div>

              <div className="overflow-hidden rounded-xl border border-slate-200 bg-white shadow-sm">
                <div className="border-b border-slate-200 p-5">
                  <h3 className="text-lg font-semibold text-slate-900">
                    Employee Risk Register
                  </h3>
                  <p className="mt-1 text-sm text-slate-500">
                    Select an illustrative employee profile to inspect.
                  </p>
                </div>

                <div className="overflow-x-auto">
                  <table className="w-full min-w-[650px] text-left text-sm">
                    <thead className="bg-slate-50 text-slate-600">
                      <tr>
                        <th className="px-5 py-4 font-semibold">Employee ID</th>
                        <th className="px-5 py-4 font-semibold">Role</th>
                        <th className="px-5 py-4 font-semibold">Department</th>
                        <th className="px-5 py-4 font-semibold">Risk Score</th>
                        <th className="px-5 py-4 font-semibold">Risk Level</th>
                        <th className="px-5 py-4 font-semibold">Action</th>
                      </tr>
                    </thead>

                    <tbody className="divide-y divide-slate-100">
                      {sampleUsers
                        .slice()
                        .sort((a, b) => b.risk_score - a.risk_score)
                        .map((user) => {
                          const badgeStyles = {
                            LOW: "bg-emerald-100 text-emerald-700",
                            MEDIUM: "bg-amber-100 text-amber-700",
                            HIGH: "bg-orange-100 text-orange-700",
                            CRITICAL: "bg-red-100 text-red-700",
                          };

                          return (
                            <tr
                              key={user.user_id}
                              className="hover:bg-slate-50"
                            >
                              <td className="px-5 py-4 font-semibold text-slate-900">
                                {user.user_id}
                              </td>
                              <td className="px-5 py-4 text-slate-600">
                                {user.role}
                              </td>
                              <td className="px-5 py-4 text-slate-600">
                                {user.department}
                              </td>
                              <td className="px-5 py-4 font-semibold text-slate-900">
                                {user.risk_score}/100
                              </td>
                              <td className="px-5 py-4">
                                <span
                                  className={`inline-flex rounded-full px-3 py-1 text-xs font-semibold ${
                                    badgeStyles[user.risk_level] ||
                                    "bg-slate-100 text-slate-700"
                                  }`}
                                >
                                  {user.risk_level}
                                </span>
                              </td>
                              <td className="px-5 py-4">
                                <button
                                  type="button"
                                  onClick={() =>
                                    investigateUser(user.user_id)
                                  }
                                  className="rounded-lg bg-blue-600 px-4 py-2 font-medium text-white transition hover:bg-blue-700"
                                >
                                  Investigate
                                </button>
                              </td>
                            </tr>
                          );
                        })}
                    </tbody>
                  </table>
                </div>

                <div className="border-t border-slate-200 px-5 py-3 text-xs leading-5 text-slate-500">
                  These profiles and scores are sample data. They are not
                  live assessments from the ARGUS risk engine.
                </div>
              </div>
            </section>
          )}

          {/* BEHAVIOR CLUSTERS */}
          {activePage === "Clusters" && (
            <section>
              <h2 className="text-2xl font-semibold text-slate-900">
                Behavior Clusters
              </h2>
              <p className="mt-2 text-slate-600">
                Explore behavioral and peer groups identified by ARGUS.
              </p>
              <div className="mt-6 rounded-xl border border-slate-200 bg-white p-6 shadow-sm">
                <h3 className="text-lg font-semibold text-slate-900">
                  Behavioral Groups
                </h3>
                <p className="mt-2 text-sm text-slate-500">
                  Cluster information will appear here when the ML pipeline
                  is connected.
                </p>
              </div>
            </section>
          )}

          {/* ACTIVITY EXPLORER */}
          {activePage === "Activity" && <ActivityExplorer />}
        </main>
      </div>
    </div>
  );
}

export default App;
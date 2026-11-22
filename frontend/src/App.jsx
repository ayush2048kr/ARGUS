
import { useEffect, useState } from "react";

import {
  clearAccessToken,
  getAccessToken,
  getAlerts,
  getCurrentUser,
  getDashboardSummary,
} from "./api/client";

import AlertCard from "./components/alerts/AlertCard";
import StatCard from "./components/dashboard/StatCard";
import Header from "./components/layout/Header";
import Sidebar from "./components/layout/Sidebar";
import Login from "./pages/Login";

import ActivityExplorer from "./pages/ActivityExplorer";
import AlertInvestigation from "./pages/AlertInvestigation";
import Alerts from "./pages/Alerts";
import RiskOverview from "./pages/RiskOverview";
import UserInvestigation from "./pages/UserInvestigation";
import BehaviorClusters from "./pages/BehaviorClusters";

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
  const [selectedUserId, setSelectedUserId] = useState("");
  const [selectedAlertId, setSelectedAlertId] = useState(null);

  const [authenticated, setAuthenticated] = useState(
    Boolean(getAccessToken())
  );

  const [currentUser, setCurrentUser] = useState(null);
  const [dashboardSummary, setDashboardSummary] = useState(null);
  const [liveAlerts, setLiveAlerts] = useState([]);
  const [loadingData, setLoadingData] = useState(false);
  const [apiError, setApiError] = useState("");

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
    setSelectedUserId("");
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
    investigateUser(userId);
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

          {/* USER INVESTIGATION */}
          {activePage === "User Investigation" && (
            <UserInvestigation
              initialUserId={selectedUserId}
            />
          )}

          {/* LIVE RISK OVERVIEW */}
          {activePage === "Risks" && (
            <RiskOverview
              onInvestigateUser={investigateUser}
            />
          )}

          {/* BEHAVIOR CLUSTERS */}
          {activePage === "Clusters" && <BehaviorClusters />}

          {/* ACTIVITY EXPLORER */}
          {activePage === "Activity" && <ActivityExplorer />}
        </main>
      </div>
    </div>
  );
}

export default App;

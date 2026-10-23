
import { useEffect, useMemo, useState } from "react";

export const sampleUsers = [
  {
    user_id: "EMP014",
    role: "Data Analyst",
    department: "Analytics",
    work_schedule: "Standard business hours",
    access_level: "Standard",
    location: "Office",
    risk_score: 72,
    risk_level: "HIGH",
    behavior_deviation_score: 68,
    peer_deviation_score: 54,
    context_risk_score: 61,
  },
  {
    user_id: "EMP027",
    role: "Finance Associate",
    department: "Finance",
    work_schedule: "Standard business hours",
    access_level: "Standard",
    location: "Office",
    risk_score: 48,
    risk_level: "MEDIUM",
    behavior_deviation_score: 35,
    peer_deviation_score: 58,
    context_risk_score: 30,
  },
  {
    user_id: "EMP031",
    role: "Systems Administrator",
    department: "IT",
    work_schedule: "Rotational",
    access_level: "Privileged",
    location: "Office",
    risk_score: 86,
    risk_level: "CRITICAL",
    behavior_deviation_score: 71,
    peer_deviation_score: 66,
    context_risk_score: 89,
  },
];

const sampleAlerts = [
  {
    alert_id: "ALT001",
    user_id: "EMP014",
    risk_level: "HIGH",
    risk_score: 72,
    reason: "Behavior deviates from the user's normal baseline.",
    evidence: "Unusual access to a sensitive resource.",
  },
  {
    alert_id: "ALT002",
    user_id: "EMP027",
    risk_level: "MEDIUM",
    risk_score: 48,
    reason: "Activity differs from the user's peer group.",
    evidence: "Higher-than-usual download volume.",
  },
  {
    alert_id: "ALT003",
    user_id: "EMP031",
    risk_level: "CRITICAL",
    risk_score: 86,
    reason: "Multiple contextual risk indicators detected.",
    evidence:
      "Sensitive resource access combined with an external destination.",
  },
];

const severityStyles = {
  LOW: "bg-emerald-100 text-emerald-700",
  MEDIUM: "bg-amber-100 text-amber-700",
  HIGH: "bg-orange-100 text-orange-700",
  CRITICAL: "bg-red-100 text-red-700",
};

function RiskBadge({ level }) {
  return (
    <span
      className={`inline-flex rounded-full px-3 py-1 text-xs font-semibold ${
        severityStyles[level] || "bg-slate-100 text-slate-700"
      }`}
    >
      {level}
    </span>
  );
}

function ContextItem({ label, value }) {
  return (
    <div className="rounded-lg bg-slate-50 p-4">
      <p className="text-sm text-slate-500">{label}</p>
      <p className="mt-1 font-semibold text-slate-900">{value}</p>
    </div>
  );
}

function DeviationBar({ label, value }) {
  return (
    <div>
      <div className="mb-2 flex items-center justify-between gap-4">
        <span className="text-sm font-medium text-slate-700">{label}</span>
        <span className="text-sm font-semibold text-slate-900">
          {value}/100
        </span>
      </div>

      <div
        className="h-2.5 overflow-hidden rounded-full bg-slate-200"
        role="progressbar"
        aria-label={label}
        aria-valuenow={value}
        aria-valuemin={0}
        aria-valuemax={100}
      >
        <div
          className="h-full rounded-full bg-blue-600 transition-all"
          style={{ width: `${value}%` }}
        />
      </div>
    </div>
  );
}

function UserInvestigation({ initialUserId = "EMP014" }) {
  const [search, setSearch] = useState(initialUserId);
  const [selectedUserId, setSelectedUserId] = useState(initialUserId);

  useEffect(() => {
    setSearch(initialUserId);
    setSelectedUserId(initialUserId);
  }, [initialUserId]);

  const user = useMemo(() => {
    return sampleUsers.find(
      (item) => item.user_id === selectedUserId
    );
  }, [selectedUserId]);

  const userAlerts = useMemo(() => {
    if (!user) return [];

    return sampleAlerts.filter(
      (alert) => alert.user_id === user.user_id
    );
  }, [user]);

  function handleSearch(event) {
    event.preventDefault();

    const query = search.trim().toUpperCase();

    const match = sampleUsers.find(
      (item) => item.user_id === query
    );

    if (match) {
      setSelectedUserId(match.user_id);
      setSearch(match.user_id);
    }
  }

  function selectUser(userId) {
    setSearch(userId);
    setSelectedUserId(userId);
  }

  return (
    <div className="mx-auto w-full max-w-7xl space-y-6">
      <header>
        <h2 className="text-2xl font-semibold text-slate-900">
          User Investigation
        </h2>
        <p className="mt-2 text-slate-600">
          Investigate employee behavior, organizational context, and
          related risk alerts.
        </p>
      </header>

      <section className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
        <form
          onSubmit={handleSearch}
          className="flex flex-col gap-3 sm:flex-row"
        >
          <div className="flex-1">
            <label
              htmlFor="employee-search"
              className="mb-2 block text-sm font-medium text-slate-700"
            >
              Search employee by ID
            </label>

            <input
              id="employee-search"
              type="search"
              value={search}
              onChange={(event) => setSearch(event.target.value)}
              placeholder="For example, EMP031"
              className="w-full rounded-lg border border-slate-300 px-4 py-3 outline-none focus:border-blue-500 focus:ring-2 focus:ring-blue-100"
            />
          </div>

          <button
            type="submit"
            className="self-end rounded-lg bg-blue-600 px-5 py-3 font-medium text-white hover:bg-blue-700"
          >
            Find employee
          </button>
        </form>

        <div className="mt-4 flex flex-wrap items-center gap-2">
          <span className="mr-1 text-sm text-slate-500">
            Sample profiles:
          </span>

          {sampleUsers.map((item) => (
            <button
              key={item.user_id}
              type="button"
              onClick={() => selectUser(item.user_id)}
              className={`rounded-lg border px-3 py-1.5 text-sm font-medium ${
                selectedUserId === item.user_id
                  ? "border-blue-600 bg-blue-50 text-blue-700"
                  : "border-slate-200 text-slate-600 hover:bg-slate-50"
              }`}
            >
              {item.user_id}
            </button>
          ))}
        </div>
      </section>

      {!user ? (
        <section className="rounded-xl border border-amber-200 bg-amber-50 p-6">
          <h3 className="font-semibold text-amber-900">
            No matching sample employee
          </h3>
          <p className="mt-2 text-sm text-amber-800">
            Try EMP014, EMP027, or EMP031.
          </p>
        </section>
      ) : (
        <>
          <section className="rounded-xl border border-slate-200 bg-white p-6 shadow-sm">
            <div className="flex flex-col justify-between gap-4 sm:flex-row sm:items-start">
              <div>
                <p className="text-sm font-medium text-blue-600">
                  Employee profile
                </p>
                <h3 className="mt-1 text-xl font-semibold text-slate-900">
                  {user.user_id}
                </h3>
                <p className="mt-1 text-slate-600">
                  {user.role} · {user.department}
                </p>
              </div>

              <RiskBadge level={user.risk_level} />
            </div>

            <div className="mt-6 grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4">
              <ContextItem
                label="Department"
                value={user.department}
              />
              <ContextItem
                label="Work schedule"
                value={user.work_schedule}
              />
              <ContextItem
                label="Access level"
                value={user.access_level}
              />
              <ContextItem
                label="Recorded location"
                value={user.location}
              />
            </div>
          </section>

          <section className="grid grid-cols-1 gap-6 lg:grid-cols-3">
            <div className="rounded-xl border border-slate-200 bg-white p-6 shadow-sm">
              <p className="text-sm font-medium text-slate-500">
                Current sample risk score
              </p>

              <div className="mt-2 flex items-baseline gap-2">
                <span className="text-4xl font-bold text-slate-900">
                  {user.risk_score}
                </span>
                <span className="text-slate-400">/100</span>
              </div>

              <div className="mt-3">
                <RiskBadge level={user.risk_level} />
              </div>

              <p className="mt-4 text-sm leading-6 text-slate-600">
                This is illustrative sample data for frontend development,
                not a live assessment from the ARGUS risk engine.
              </p>
            </div>

            <div className="rounded-xl border border-slate-200 bg-white p-6 shadow-sm lg:col-span-2">
              <h3 className="text-lg font-semibold text-slate-900">
                Behavior and context indicators
              </h3>

              <p className="mt-1 text-sm text-slate-500">
                Illustrative indicator values, pending ML integration.
              </p>

              <div className="mt-6 space-y-5">
                <DeviationBar
                  label="Behavior deviation"
                  value={user.behavior_deviation_score}
                />
                <DeviationBar
                  label="Peer-group deviation"
                  value={user.peer_deviation_score}
                />
                <DeviationBar
                  label="Context risk indicator"
                  value={user.context_risk_score}
                />
              </div>
            </div>
          </section>

          <section className="rounded-xl border border-slate-200 bg-white p-6 shadow-sm">
            <div className="mb-5">
              <h3 className="text-lg font-semibold text-slate-900">
                Related alerts
              </h3>
              <p className="mt-1 text-sm text-slate-500">
                Sample alerts associated with {user.user_id}.
              </p>
            </div>

            {userAlerts.length === 0 ? (
              <p className="rounded-lg bg-slate-50 p-4 text-sm text-slate-600">
                No sample alerts are associated with this employee.
              </p>
            ) : (
              <div className="space-y-4">
                {userAlerts.map((alert) => (
                  <article
                    key={alert.alert_id}
                    className="rounded-lg border border-slate-200 p-4"
                  >
                    <div className="flex flex-wrap items-center justify-between gap-3">
                      <h4 className="font-semibold text-slate-900">
                        {alert.alert_id}
                      </h4>
                      <RiskBadge level={alert.risk_level} />
                    </div>

                    <p className="mt-3 text-sm text-slate-700">
                      <span className="font-medium">Risk score:</span>{" "}
                      {alert.risk_score}/100
                    </p>

                    <p className="mt-2 text-sm leading-6 text-slate-600">
                      <span className="font-medium text-slate-800">
                        Reason:
                      </span>{" "}
                      {alert.reason}
                    </p>

                    <p className="mt-2 text-sm leading-6 text-slate-600">
                      <span className="font-medium text-slate-800">
                        Evidence:
                      </span>{" "}
                      {alert.evidence}
                    </p>
                  </article>
                ))}
              </div>
            )}
          </section>
        </>
      )}

      <p className="text-xs leading-5 text-slate-500">
        Prototype note: employee profiles, indicator values, and alerts
        are illustrative sample data. Connect the backend and ML outputs
        before using this page for real investigations.
      </p>
    </div>
  );
}

export default UserInvestigation;

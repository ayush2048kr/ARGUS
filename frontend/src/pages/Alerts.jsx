
import { useMemo, useState } from "react";
import sampleAlerts from "../data/sampleAlerts";

const severityStyles = {
  LOW: "bg-emerald-100 text-emerald-700",
  MEDIUM: "bg-amber-100 text-amber-700",
  HIGH: "bg-orange-100 text-orange-700",
  CRITICAL: "bg-red-100 text-red-700",
};

const severityOptions = ["ALL", "LOW", "MEDIUM", "HIGH", "CRITICAL"];

function Alerts({ onInvestigateAlert }) {
  const [search, setSearch] = useState("");
  const [severity, setSeverity] = useState("ALL");
  const [selectedAlert, setSelectedAlert] = useState(null);

  const filteredAlerts = useMemo(() => {
    const query = search.trim().toLowerCase();

    return sampleAlerts.filter((alert) => {
      const matchesSeverity =
        severity === "ALL" || alert.risk_level === severity;

      const matchesSearch =
        !query ||
        alert.alert_id.toLowerCase().includes(query) ||
        alert.user_id.toLowerCase().includes(query) ||
        alert.reason.toLowerCase().includes(query) ||
        alert.evidence.toLowerCase().includes(query);

      return matchesSeverity && matchesSearch;
    });
  }, [search, severity]);

  return (
    <div className="mx-auto w-full max-w-7xl">
      <div className="mb-8">
        <h2 className="text-2xl font-semibold text-slate-900">
          Alert Center
        </h2>
        <p className="mt-2 text-slate-600">
          Search alerts, filter by severity, and investigate the evidence
          behind each risk assessment.
        </p>
      </div>

      {/* SEARCH AND FILTERS */}
      <section className="mb-6 rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
        <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
          <div>
            <label
              htmlFor="alert-search"
              className="mb-2 block text-sm font-medium text-slate-700"
            >
              Search alerts
            </label>

            <input
              id="alert-search"
              type="search"
              value={search}
              onChange={(event) => setSearch(event.target.value)}
              placeholder="Search alert ID, employee, reason, or evidence..."
              className="w-full rounded-lg border border-slate-300 px-4 py-3 text-sm outline-none transition focus:border-blue-500 focus:ring-2 focus:ring-blue-100"
            />
          </div>

          <div>
            <label
              htmlFor="severity-filter"
              className="mb-2 block text-sm font-medium text-slate-700"
            >
              Filter by severity
            </label>

            <select
              id="severity-filter"
              value={severity}
              onChange={(event) => setSeverity(event.target.value)}
              className="w-full rounded-lg border border-slate-300 bg-white px-4 py-3 text-sm outline-none focus:border-blue-500 focus:ring-2 focus:ring-blue-100"
            >
              {severityOptions.map((option) => (
                <option key={option} value={option}>
                  {option === "ALL" ? "All severities" : option}
                </option>
              ))}
            </select>
          </div>
        </div>

        <div className="mt-4 flex flex-wrap items-center justify-between gap-3">
          <p className="text-sm text-slate-500">
            Showing{" "}
            <span className="font-semibold text-slate-800">
              {filteredAlerts.length}
            </span>{" "}
            of {sampleAlerts.length} sample alerts
          </p>

          <button
            type="button"
            onClick={() => {
              setSearch("");
              setSeverity("ALL");
              setSelectedAlert(null);
            }}
            className="rounded-lg border border-slate-300 px-3 py-2 text-sm font-medium text-slate-700 transition hover:bg-slate-50"
          >
            Clear filters
          </button>
        </div>
      </section>

      {/* ALERT LIST */}
      <section>
        <h3 className="mb-4 text-lg font-semibold text-slate-900">
          Alerts
        </h3>

        {filteredAlerts.length === 0 ? (
          <div className="rounded-xl border border-dashed border-slate-300 bg-white p-8 text-center">
            <p className="font-medium text-slate-800">No matching alerts</p>
            <p className="mt-2 text-sm text-slate-500">
              Try another search term or severity filter.
            </p>
          </div>
        ) : (
          <div className="grid grid-cols-1 items-start gap-4 md:grid-cols-2 xl:grid-cols-3">
            {filteredAlerts.map((alert) => (
              <button
                key={alert.alert_id}
                type="button"
                onClick={() => setSelectedAlert(alert)}
                className={`w-full rounded-xl border bg-white p-5 text-left shadow-sm transition hover:-translate-y-0.5 hover:shadow-md ${
                  selectedAlert?.alert_id === alert.alert_id
                    ? "border-blue-500 ring-2 ring-blue-100"
                    : "border-slate-200"
                }`}
              >
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <span className="font-semibold text-slate-900">
                    {alert.alert_id}
                  </span>

                  <span
                    className={`rounded-full px-3 py-1 text-xs font-semibold ${
                      severityStyles[alert.risk_level] ||
                      "bg-slate-100 text-slate-700"
                    }`}
                  >
                    {alert.risk_level}
                  </span>
                </div>

                <p className="mt-3 text-sm text-slate-500">
                  Employee:{" "}
                  <span className="font-medium text-slate-700">
                    {alert.user_id}
                  </span>
                </p>

                <p className="mt-5 text-sm text-slate-600">Risk score</p>
                <p className="mt-1 text-3xl font-bold text-slate-900">
                  {alert.risk_score}
                  <span className="ml-1 text-sm font-normal text-slate-400">
                    /100
                  </span>
                </p>

                <p className="mt-4 text-sm leading-6 text-slate-600">
                  {alert.reason}
                </p>

                <p className="mt-4 text-sm font-semibold text-blue-700">
                  View evidence →
                </p>
              </button>
            ))}
          </div>
        )}
      </section>

      {/* EVIDENCE PANEL */}
      {selectedAlert && (
        <section
          className="mt-8 rounded-xl border border-slate-200 bg-white p-6 shadow-sm"
          aria-labelledby="evidence-heading"
        >
          <div className="flex flex-wrap items-start justify-between gap-4">
            <div>
              <p className="text-sm font-medium text-blue-700">
                Alert evidence
              </p>
              <h3
                id="evidence-heading"
                className="mt-1 text-xl font-semibold text-slate-900"
              >
                {selectedAlert.alert_id}
              </h3>
              <p className="mt-1 text-sm text-slate-500">
                Employee: {selectedAlert.user_id}
              </p>
            </div>

            <button
              type="button"
              onClick={() => setSelectedAlert(null)}
              className="rounded-lg border border-slate-300 px-3 py-2 text-sm text-slate-700 hover:bg-slate-50"
            >
              Close evidence
            </button>
          </div>

          <div className="mt-6 grid grid-cols-1 gap-4 md:grid-cols-3">
            <div className="rounded-lg bg-slate-50 p-4">
              <p className="text-sm text-slate-500">Risk score</p>
              <p className="mt-2 text-2xl font-bold text-slate-900">
                {selectedAlert.risk_score}/100
              </p>
            </div>

            <div className="rounded-lg bg-slate-50 p-4">
              <p className="text-sm text-slate-500">Severity</p>
              <span
                className={`mt-2 inline-block rounded-full px-3 py-1 text-sm font-semibold ${
                  severityStyles[selectedAlert.risk_level] ||
                  "bg-slate-100 text-slate-700"
                }`}
              >
                {selectedAlert.risk_level}
              </span>
            </div>

            <div className="rounded-lg bg-slate-50 p-4">
              <p className="text-sm text-slate-500">Employee ID</p>
              <p className="mt-2 text-lg font-semibold text-slate-900">
                {selectedAlert.user_id}
              </p>
            </div>
          </div>

          <div className="mt-6 grid grid-cols-1 gap-6 md:grid-cols-2">
            <div>
              <h4 className="font-semibold text-slate-900">
                Why was this alert raised?
              </h4>
              <p className="mt-2 text-sm leading-6 text-slate-600">
                {selectedAlert.reason}
              </p>
            </div>

            <div>
              <h4 className="font-semibold text-slate-900">
                Supporting evidence
              </h4>
              <p className="mt-2 text-sm leading-6 text-slate-600">
                {selectedAlert.evidence}
              </p>
            </div>
          </div>

          <div className="mt-6 flex flex-wrap gap-3">
            <button
              type="button"
              onClick={() =>
                onInvestigateAlert?.(selectedAlert.alert_id)
              }
              className="rounded-lg bg-blue-600 px-4 py-2 text-sm font-medium text-white transition hover:bg-blue-700"
            >
              Open full investigation →
            </button>
          </div>

          <p className="mt-6 rounded-lg border border-amber-200 bg-amber-50 p-4 text-sm leading-6 text-amber-900">
            An unusual activity pattern is not, by itself, proof of
            malicious intent. Review the employee's normal behavior, peer
            group, role, and operational context before drawing a conclusion.
          </p>
        </section>
      )}
    </div>
  );
}

export default Alerts;

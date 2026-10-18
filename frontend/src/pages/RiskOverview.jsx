import { useMemo, useState } from "react";
import sampleAlerts from "../data/sampleAlerts";

const riskStyles = {
  LOW: "bg-emerald-100 text-emerald-700",
  MEDIUM: "bg-amber-100 text-amber-700",
  HIGH: "bg-orange-100 text-orange-700",
  CRITICAL: "bg-red-100 text-red-700",
};

const riskOrder = ["LOW", "MEDIUM", "HIGH", "CRITICAL"];

function RiskOverview({ onInvestigateUser }) {
  const [selectedRisk, setSelectedRisk] = useState("ALL");

  const alerts = Array.isArray(sampleAlerts) ? sampleAlerts : [];

  const riskCounts = useMemo(
    () =>
      riskOrder.reduce((counts, level) => {
        counts[level] = alerts.filter(
          (alert) => alert.risk_level === level
        ).length;
        return counts;
      }, {}),
    [alerts]
  );

  const filteredAlerts = alerts
    .filter(
      (alert) =>
        selectedRisk === "ALL" || alert.risk_level === selectedRisk
    )
    .sort((a, b) => b.risk_score - a.risk_score);

  const highestScore =
    alerts.length > 0
      ? Math.max(...alerts.map((alert) => Number(alert.risk_score) || 0))
      : 0;

  return (
    <div className="space-y-8">
      <section>
        <h2 className="text-2xl font-semibold text-slate-900">
          Risk Overview
        </h2>
        <p className="mt-2 text-slate-600">
          Review sample risk levels and identify employees requiring further
          investigation.
        </p>
        <p className="mt-2 text-sm text-slate-500">
          Prototype data only — these are not live ARGUS risk assessments.
        </p>
      </section>

      {/* Risk summary cards */}
      <section className="grid grid-cols-1 gap-5 sm:grid-cols-2 xl:grid-cols-4">
        {riskOrder.map((level) => (
          <button
            key={level}
            type="button"
            onClick={() =>
              setSelectedRisk(selectedRisk === level ? "ALL" : level)
            }
            aria-pressed={selectedRisk === level}
            className={`rounded-xl border bg-white p-5 text-left shadow-sm transition hover:-translate-y-0.5 hover:shadow-md ${
              selectedRisk === level
                ? "border-blue-500 ring-2 ring-blue-100"
                : "border-slate-200"
            }`}
          >
            <div className="flex items-center justify-between gap-3">
              <span className="text-sm font-medium text-slate-500">
                {level} Risk
              </span>
              <span
                className={`rounded-full px-3 py-1 text-xs font-semibold ${riskStyles[level]}`}
              >
                {level}
              </span>
            </div>

            <p className="mt-4 text-3xl font-bold text-slate-900">
              {riskCounts[level] ?? 0}
            </p>
            <p className="mt-1 text-sm text-slate-500">
              Sample alerts
            </p>
          </button>
        ))}
      </section>

      {/* Severity distribution */}
      <section className="rounded-xl border border-slate-200 bg-white p-6 shadow-sm">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <h3 className="text-lg font-semibold text-slate-900">
              Risk Distribution
            </h3>
            <p className="mt-1 text-sm text-slate-500">
              Sample alert counts by severity.
            </p>
          </div>
          <span className="text-sm text-slate-500">
            {alerts.length} total sample alerts
          </span>
        </div>

        <div className="mt-6 space-y-5">
          {riskOrder.map((level) => {
            const count = riskCounts[level] ?? 0;
            const percentage =
              alerts.length > 0 ? (count / alerts.length) * 100 : 0;

            const barStyles = {
              LOW: "bg-emerald-500",
              MEDIUM: "bg-amber-400",
              HIGH: "bg-orange-500",
              CRITICAL: "bg-red-500",
            };

            return (
              <div key={level}>
                <div className="mb-2 flex items-center justify-between gap-3">
                  <span className="text-sm font-medium text-slate-700">
                    {level}
                  </span>
                  <span className="text-sm text-slate-500">
                    {count} alerts · {Math.round(percentage)}%
                  </span>
                </div>

                <div
                  className="h-3 overflow-hidden rounded-full bg-slate-100"
                  role="progressbar"
                  aria-label={`${level} risk alert distribution`}
                  aria-valuenow={Math.round(percentage)}
                  aria-valuemin={0}
                  aria-valuemax={100}
                >
                  <div
                    className={`h-full rounded-full transition-all ${barStyles[level]}`}
                    style={{ width: `${percentage}%` }}
                  />
                </div>
              </div>
            );
          })}
        </div>
      </section>

      {/* Highest-risk sample alerts */}
      <section className="overflow-hidden rounded-xl border border-slate-200 bg-white shadow-sm">
        <div className="flex flex-wrap items-center justify-between gap-4 border-b border-slate-200 p-6">
          <div>
            <h3 className="text-lg font-semibold text-slate-900">
              Highest-Risk Employees
            </h3>
            <p className="mt-1 text-sm text-slate-500">
              Employees associated with the highest-scoring sample alerts.
            </p>
          </div>

          <label className="flex items-center gap-2 text-sm text-slate-600">
            Severity
            <select
              value={selectedRisk}
              onChange={(event) => setSelectedRisk(event.target.value)}
              className="rounded-lg border border-slate-300 bg-white px-3 py-2 text-slate-800 outline-none focus:border-blue-500 focus:ring-2 focus:ring-blue-100"
            >
              <option value="ALL">All levels</option>
              {riskOrder.map((level) => (
                <option key={level} value={level}>
                  {level}
                </option>
              ))}
            </select>
          </label>
        </div>

        {filteredAlerts.length > 0 ? (
          <div className="overflow-x-auto">
            <table className="w-full min-w-[650px] text-left text-sm">
              <thead className="bg-slate-50 text-slate-500">
                <tr>
                  <th className="px-6 py-4 font-medium">Alert ID</th>
                  <th className="px-6 py-4 font-medium">Employee</th>
                  <th className="px-6 py-4 font-medium">Risk Score</th>
                  <th className="px-6 py-4 font-medium">Severity</th>
                  <th className="px-6 py-4 font-medium">Reason</th>
                  <th className="px-6 py-4 font-medium">Action</th>
                </tr>
              </thead>

              <tbody className="divide-y divide-slate-100">
                {filteredAlerts.map((alert) => (
                  <tr
                    key={alert.alert_id}
                    className="transition hover:bg-slate-50"
                  >
                    <td className="px-6 py-4 font-semibold text-slate-900">
                      {alert.alert_id}
                    </td>
                    <td className="px-6 py-4 text-slate-700">
                      {alert.user_id}
                    </td>
                    <td className="px-6 py-4 font-bold text-slate-900">
                      {alert.risk_score}
                      <span className="font-normal text-slate-400">
                        /100
                      </span>
                    </td>
                    <td className="px-6 py-4">
                      <span
                        className={`rounded-full px-3 py-1 text-xs font-semibold ${
                          riskStyles[alert.risk_level] ??
                          "bg-slate-100 text-slate-700"
                        }`}
                      >
                        {alert.risk_level}
                      </span>
                    </td>
                    <td className="max-w-xs px-6 py-4 text-slate-600">
                      {alert.reason}
                    </td>
                    <td className="px-6 py-4">
                      <button
                        type="button"
                        onClick={() =>
                          onInvestigateUser?.(alert.user_id)
                        }
                        className="whitespace-nowrap font-semibold text-blue-600 hover:text-blue-800"
                      >
                        Investigate →
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <div className="p-10 text-center">
            <p className="font-medium text-slate-700">
              No alerts match this severity.
            </p>
            <button
              type="button"
              onClick={() => setSelectedRisk("ALL")}
              className="mt-3 font-semibold text-blue-600 hover:text-blue-800"
            >
              Clear filter
            </button>
          </div>
        )}
      </section>

      <p className="text-xs leading-5 text-slate-500">
        Risk categories follow the ARGUS prototype thresholds: LOW 0–30,
        MEDIUM 31–60, HIGH 61–80, and CRITICAL 81–100. This page displays the
        severity supplied by the sample alert data; it does not calculate
        official risk scores.
      </p>
    </div>
  );
}

export default RiskOverview;
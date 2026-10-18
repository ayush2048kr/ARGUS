
import { useMemo } from "react";
import sampleAlerts from "../data/sampleAlerts";

const severityStyles = {
  LOW: "bg-emerald-100 text-emerald-700",
  MEDIUM: "bg-amber-100 text-amber-700",
  HIGH: "bg-orange-100 text-orange-700",
  CRITICAL: "bg-red-100 text-red-700",
};

function EvidenceItem({ label, value }) {
  return (
    <div className="rounded-xl border border-slate-200 bg-white p-5">
      <p className="text-sm font-medium text-slate-500">{label}</p>
      <p className="mt-2 text-sm leading-6 text-slate-800">
        {value || "Not available in the current sample data."}
      </p>
    </div>
  );
}

function AlertInvestigation({
  alertId,
  onBack,
  onInvestigateUser,
}) {
  const alert = useMemo(
    () => sampleAlerts.find((item) => item.alert_id === alertId),
    [alertId]
  );

  if (!alert) {
    return (
      <section className="mx-auto max-w-4xl rounded-xl border border-slate-200 bg-white p-8">
        <h2 className="text-xl font-semibold text-slate-900">
          Alert not found
        </h2>
        <p className="mt-2 text-sm text-slate-600">
          This alert ID is not present in the current sample data.
        </p>
        <button
          type="button"
          onClick={onBack}
          className="mt-5 rounded-lg bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700"
        >
          Back to Alerts
        </button>
      </section>
    );
  }

  const score = Number(alert.risk_score);
  const scoreWidth = Math.max(0, Math.min(100, score));

  return (
    <div className="mx-auto w-full max-w-7xl space-y-6">
      <div>
        <button
          type="button"
          onClick={onBack}
          className="mb-4 text-sm font-medium text-blue-700 hover:text-blue-900"
        >
          ← Back to Alerts
        </button>

        <p className="text-sm font-semibold uppercase tracking-wide text-blue-700">
          Alert Investigation
        </p>
        <div className="mt-2 flex flex-wrap items-center justify-between gap-3">
          <div>
            <h2 className="text-2xl font-semibold text-slate-900">
              {alert.alert_id}
            </h2>
            <p className="mt-1 text-sm text-slate-500">
              Investigating activity associated with {alert.user_id}
            </p>
          </div>

          <span
            className={`rounded-full px-3 py-1.5 text-sm font-semibold ${
              severityStyles[alert.risk_level] ||
              "bg-slate-100 text-slate-700"
            }`}
          >
            {alert.risk_level}
          </span>
        </div>
      </div>

      <section className="grid grid-cols-1 gap-4 sm:grid-cols-3">
        <div className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
          <p className="text-sm text-slate-500">Risk score</p>
          <p className="mt-2 text-3xl font-bold text-slate-900">
            {alert.risk_score}
            <span className="ml-1 text-sm font-normal text-slate-400">
              /100
            </span>
          </p>
          <div
            className="mt-4 h-2 overflow-hidden rounded-full bg-slate-100"
            aria-label={`Illustrative risk score ${score} out of 100`}
          >
            <div
              className="h-full rounded-full bg-blue-600"
              style={{ width: `${scoreWidth}%` }}
            />
          </div>
        </div>

        <div className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
          <p className="text-sm text-slate-500">Alert ID</p>
          <p className="mt-2 text-xl font-semibold text-slate-900">
            {alert.alert_id}
          </p>
        </div>

        <div className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
          <p className="text-sm text-slate-500">Associated employee</p>
          <p className="mt-2 text-xl font-semibold text-slate-900">
            {alert.user_id}
          </p>
          <button
            type="button"
            onClick={() => onInvestigateUser(alert.user_id)}
            className="mt-3 text-sm font-semibold text-blue-700 hover:text-blue-900"
          >
            Investigate employee →
          </button>
        </div>
      </section>

      <section className="rounded-xl border border-slate-200 bg-white p-6 shadow-sm">
        <h3 className="text-lg font-semibold text-slate-900">
          Why was this alert raised?
        </h3>
        <p className="mt-2 leading-7 text-slate-600">{alert.reason}</p>
      </section>

      <section>
        <div className="mb-4">
          <h3 className="text-lg font-semibold text-slate-900">
            Supporting evidence
          </h3>
          <p className="mt-1 text-sm text-slate-500">
            Evidence currently available in the sample alert record.
          </p>
        </div>

        <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
          <EvidenceItem
            label="Observed evidence"
            value={alert.evidence}
          />
          <EvidenceItem
            label="Behavioral explanation"
            value={alert.reason}
          />
        </div>
      </section>

      <section className="rounded-xl border border-amber-200 bg-amber-50 p-5">
        <h3 className="font-semibold text-amber-950">
          Analyst guidance
        </h3>
        <p className="mt-2 text-sm leading-6 text-amber-900">
          An anomaly is not proof of malicious intent. Review the
          employee's normal behavior, peer group, role, work schedule,
          access level, resource sensitivity, and available device or
          network context before drawing a conclusion.
        </p>
      </section>

      <p className="text-xs leading-5 text-slate-500">
        Demo mode: this page uses illustrative sample data. No timestamp,
        baseline measurements, peer-deviation values, or additional evidence
        are available in the current alert records. The displayed risk score
        is not calculated by the frontend; it is read from the sample record.
      </p>
    </div>
  );
}

export default AlertInvestigation;

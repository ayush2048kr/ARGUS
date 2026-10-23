function AlertCard({ alert }) {
  const severityStyles = {
    LOW: "bg-emerald-100 text-emerald-700",
    MEDIUM: "bg-amber-100 text-amber-700",
    HIGH: "bg-orange-100 text-orange-700",
    CRITICAL: "bg-red-100 text-red-700",
  };

  const level = String(
    alert.risk_level || alert.severity || "LOW"
  ).toUpperCase();

  const evidence = Array.isArray(alert.evidence)
    ? alert.evidence.join("; ")
    : String(alert.evidence || "");

  return (
    <div className="w-full min-w-0 rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
      <div className="flex items-start justify-between gap-4">
        <div className="min-w-0">
          <p className="break-words text-sm font-semibold text-slate-900">
            {alert.alert_id}
          </p>
          <p className="mt-1 text-sm text-slate-500">
            User: {alert.user_id}
          </p>
        </div>

        <span
          className={`shrink-0 rounded-full px-3 py-1 text-xs font-semibold ${
            severityStyles[level] || "bg-slate-100 text-slate-700"
          }`}
        >
          {level}
        </span>
      </div>

      <div className="mt-5">
        <p className="text-sm font-medium text-slate-600">
          Recorded Risk Score
        </p>
        <p className="mt-1 text-3xl font-bold text-slate-900">
          {alert.risk_score ?? "—"}
          <span className="ml-1 text-sm font-normal text-slate-400">
            /100
          </span>
        </p>
      </div>

      <div className="mt-5">
        <p className="text-sm font-semibold text-slate-700">Reason</p>
        <p className="mt-1 break-words text-sm leading-6 text-slate-500">
          {alert.reason || "No reason recorded."}
        </p>
      </div>

      <div className="mt-5">
        <p className="text-sm font-semibold text-slate-700">Evidence</p>
        <p className="mt-1 break-words text-sm leading-6 text-slate-500">
          {evidence || "No evidence recorded."}
        </p>
      </div>
    </div>
  );
}

export default AlertCard;
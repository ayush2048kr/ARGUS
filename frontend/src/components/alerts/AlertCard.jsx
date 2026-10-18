function AlertCard({ alert }) {
  const severityStyles = {
    LOW: "bg-green-100 text-green-700",
    MEDIUM: "bg-yellow-100 text-yellow-700",
    HIGH: "bg-orange-100 text-orange-700",
    CRITICAL: "bg-red-100 text-red-700",
  };

  return (
    <div className="w-full min-w-0 rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
      {/* Header */}
      <div className="flex items-start justify-between gap-4">
        <div className="min-w-0">
          <p className="text-sm font-semibold text-slate-900">
            {alert.alert_id}
          </p>

          <p className="mt-1 text-sm text-slate-500">
            User: {alert.user_id}
          </p>
        </div>

        <span
          className={`shrink-0 rounded-full px-3 py-1 text-xs font-semibold ${
            severityStyles[alert.risk_level] ||
            "bg-slate-100 text-slate-700"
          }`}
        >
          {alert.risk_level}
        </span>
      </div>

      {/* Risk Score */}
      <div className="mt-5">
        <p className="text-sm font-medium text-slate-600">
          Risk Score
        </p>

        <p className="mt-1 text-3xl font-bold text-slate-900">
          {alert.risk_score}
        </p>
      </div>

      {/* Reason */}
      <div className="mt-5">
        <p className="text-sm font-semibold text-slate-700">
          Reason
        </p>

        <p className="mt-1 text-sm leading-6 text-slate-500">
          {alert.reason}
        </p>
      </div>

      {/* Evidence */}
      <div className="mt-5">
        <p className="text-sm font-semibold text-slate-700">
          Evidence
        </p>

        <p className="mt-1 text-sm leading-6 text-slate-500">
          {alert.evidence}
        </p>
      </div>
    </div>
  );
}

export default AlertCard;
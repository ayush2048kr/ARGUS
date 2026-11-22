
import { useEffect, useMemo, useState } from "react";
import { getLatestDailyRisks } from "../api/client";

const levels = ["LOW", "MEDIUM", "HIGH", "CRITICAL", "UNAVAILABLE"];

const styles = {
  LOW: "bg-emerald-100 text-emerald-700",
  MEDIUM: "bg-amber-100 text-amber-700",
  HIGH: "bg-orange-100 text-orange-700",
  CRITICAL: "bg-red-100 text-red-700",
  UNAVAILABLE: "bg-slate-100 text-slate-600",
};

const bars = {
  LOW: "bg-emerald-500",
  MEDIUM: "bg-amber-400",
  HIGH: "bg-orange-500",
  CRITICAL: "bg-red-500",
  UNAVAILABLE: "bg-slate-400",
};

export default function RiskOverview({ onInvestigateUser }) {
  const [records, setRecords] = useState([]);
  const [filter, setFilter] = useState("ALL");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    let cancelled = false;

    async function load() {
      setLoading(true);
      setError("");

      try {
        const result = await getLatestDailyRisks(5000);

        if (!cancelled) {
          setRecords(Array.isArray(result) ? result : []);
        }
      } catch (err) {
        if (!cancelled) {
          setError(err.message || "Could not load risk assessments.");
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    }

    load();

    return () => {
      cancelled = true;
    };
  }, []);

  const counts = useMemo(() => {
    const result = Object.fromEntries(levels.map((level) => [level, 0]));

    records.forEach((record) => {
      const level = String(record.risk_level || "UNAVAILABLE").toUpperCase();
      if (level in result) result[level] += 1;
    });

    return result;
  }, [records]);

  const filtered = useMemo(() => {
    return records
      .filter((record) =>
        filter === "ALL" ? true : record.risk_level === filter
      )
      .sort((a, b) => (b.risk_score ?? -1) - (a.risk_score ?? -1));
  }, [records, filter]);

  const scored = records.filter(
    (record) => record.risk_status === "scored"
  ).length;

  return (
    <div className="space-y-7">
      <header>
        <h2 className="text-2xl font-semibold text-slate-900">
          Risk Overview
        </h2>
        <p className="mt-2 text-slate-600">
          Latest daily context-aware risk assessments from the ARGUS backend.
        </p>
      </header>

      {error && (
        <div role="alert" className="rounded-lg border border-red-200 bg-red-50 p-4 text-sm text-red-700">
          {error}
        </div>
      )}

      {loading ? (
        <div className="rounded-xl border bg-white p-8 text-center text-slate-500">
          Loading daily risk assessments...
        </div>
      ) : (
        <>
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-5">
            {levels.map((level) => (
              <button
                key={level}
                type="button"
                onClick={() => setFilter(filter === level ? "ALL" : level)}
                aria-pressed={filter === level}
                className={`rounded-xl border bg-white p-5 text-left shadow-sm ${
                  filter === level
                    ? "border-blue-500 ring-2 ring-blue-100"
                    : "border-slate-200"
                }`}
              >
                <span className={`rounded-full px-2 py-1 text-xs font-semibold ${styles[level]}`}>
                  {level}
                </span>
                <p className="mt-4 text-3xl font-bold text-slate-900">
                  {counts[level]}
                </p>
                <p className="mt-1 text-sm text-slate-500">
                  Latest employee assessments
                </p>
              </button>
            ))}
          </div>

          <section className="rounded-xl border border-slate-200 bg-white p-6 shadow-sm">
            <div className="flex flex-wrap justify-between gap-3">
              <div>
                <h3 className="text-lg font-semibold text-slate-900">
                  Risk Distribution
                </h3>
                <p className="mt-1 text-sm text-slate-500">
                  Distribution of latest employee assessments.
                </p>
              </div>
              <p className="text-sm text-slate-500">
                {records.length} employees · {scored} scored
              </p>
            </div>

            <div className="mt-6 space-y-5">
              {levels.map((level) => {
                const percentage = records.length
                  ? (counts[level] / records.length) * 100
                  : 0;

                return (
                  <div key={level}>
                    <div className="mb-2 flex justify-between text-sm">
                      <span className="font-medium text-slate-700">
                        {level}
                      </span>
                      <span className="text-slate-500">
                        {counts[level]} · {percentage.toFixed(1)}%
                      </span>
                    </div>
                    <div className="h-3 overflow-hidden rounded-full bg-slate-100">
                      <div
                        className={`h-full rounded-full ${bars[level]}`}
                        style={{ width: `${percentage}%` }}
                      />
                    </div>
                  </div>
                );
              })}
            </div>
          </section>

          <section className="overflow-hidden rounded-xl border border-slate-200 bg-white shadow-sm">
            <div className="flex flex-wrap items-center justify-between gap-4 border-b border-slate-200 p-6">
              <div>
                <h3 className="text-lg font-semibold text-slate-900">
                  Employee Risk Register
                </h3>
                <p className="mt-1 text-sm text-slate-500">
                  One latest daily assessment per employee.
                </p>
              </div>

              <select
                value={filter}
                onChange={(event) => setFilter(event.target.value)}
                aria-label="Filter by risk level"
                className="rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm"
              >
                <option value="ALL">All risk levels</option>
                {levels.map((level) => (
                  <option key={level} value={level}>{level}</option>
                ))}
              </select>
            </div>

            {filtered.length ? (
              <div className="overflow-x-auto">
                <table className="w-full min-w-[750px] text-left text-sm">
                  <thead className="bg-slate-50 text-slate-500">
                    <tr>
                      <th className="px-5 py-4">Employee ID</th>
                      <th className="px-5 py-4">Role</th>
                      <th className="px-5 py-4">LDAP Domain</th>
                      <th className="px-5 py-4">Date</th>
                      <th className="px-5 py-4">Risk Score</th>
                      <th className="px-5 py-4">Risk Level</th>
                      <th className="px-5 py-4">Action</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-100">
                    {filtered.map((record) => (
                      <tr
                        key={`${record.user_id}-${record.date}`}
                        className="hover:bg-slate-50"
                      >
                        <td className="px-5 py-4 font-semibold text-slate-900">
                          {record.user_id}
                        </td>
                        <td className="px-5 py-4 text-slate-600">
                          {record.role || "Not available"}
                        </td>
                        <td className="px-5 py-4 text-slate-600">
                          {record.ldap_domain || "Not available"}
                        </td>
                        <td className="px-5 py-4 text-slate-600">
                          {record.date}
                        </td>
                        <td className="px-5 py-4 font-semibold text-slate-900">
                          {record.risk_score == null
                            ? "Unavailable"
                            : `${Number(record.risk_score).toFixed(2)}/100`}
                        </td>
                        <td className="px-5 py-4">
                          <span className={`rounded-full px-3 py-1 text-xs font-semibold ${styles[record.risk_level] || styles.UNAVAILABLE}`}>
                            {record.risk_level || "UNAVAILABLE"}
                          </span>
                        </td>
                        <td className="px-5 py-4">
                          <button
                            type="button"
                            onClick={() => onInvestigateUser?.(record.user_id)}
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
              <p className="p-8 text-center text-sm text-slate-500">
                No assessments found for this filter.
              </p>
            )}
          </section>

          <p className="text-xs leading-5 text-slate-500">
            Risk thresholds: LOW 0–30, MEDIUM 31–60, HIGH 61–80, CRITICAL
            81–100. UNAVAILABLE means insufficient evidence. An anomaly does
            not establish malicious intent.
          </p>
        </>
      )}
    </div>
  );
}

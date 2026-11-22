
import { useEffect, useState } from "react";
import { getDailyRisksForUser } from "../api/client";

const badgeStyles = {
  LOW: "bg-emerald-100 text-emerald-700",
  MEDIUM: "bg-amber-100 text-amber-700",
  HIGH: "bg-orange-100 text-orange-700",
  CRITICAL: "bg-red-100 text-red-700",
  UNAVAILABLE: "bg-slate-100 text-slate-600",
};

function Badge({ level }) {
  return (
    <span className={`inline-flex rounded-full px-3 py-1 text-xs font-semibold ${badgeStyles[level] || badgeStyles.UNAVAILABLE}`}>
      {level || "UNAVAILABLE"}
    </span>
  );
}

function ScoreCard({ title, value, status }) {
  return (
    <div className="rounded-lg border border-slate-200 p-4">
      <p className="text-sm text-slate-500">{title}</p>
      <p className="mt-2 text-2xl font-bold text-slate-900">
        {value == null ? "Unavailable" : Number(value).toFixed(2)}
        {value != null && (
          <span className="text-sm font-normal text-slate-400"> /100</span>
        )}
      </p>
      {status && (
        <p className="mt-1 text-xs text-slate-500">{status}</p>
      )}
    </div>
  );
}

export default function UserInvestigation({ initialUserId = "" }) {
  const [search, setSearch] = useState(initialUserId);
  const [userId, setUserId] = useState(initialUserId);
  const [records, setRecords] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    setSearch(initialUserId);
    setUserId(initialUserId);
  }, [initialUserId]);

  useEffect(() => {
    if (!userId) {
      setRecords([]);
      return undefined;
    }

    let cancelled = false;

    async function loadHistory() {
      setLoading(true);
      setError("");
      setRecords([]);

      try {
        const result = await getDailyRisksForUser(userId);

        if (!cancelled) {
          const history = Array.isArray(result) ? result : [];
          history.sort((a, b) =>
            String(b.date).localeCompare(String(a.date))
          );
          setRecords(history);
        }
      } catch (err) {
        if (!cancelled) {
          setError(err.message || "Unable to load employee history.");
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    }

    loadHistory();

    return () => {
      cancelled = true;
    };
  }, [userId]);

  function handleSearch(event) {
    event.preventDefault();
    const value = search.trim().toUpperCase();
    if (value) setUserId(value);
  }

  const latest = records[0];

  return (
    <div className="mx-auto w-full max-w-7xl space-y-6">
      <header>
        <h2 className="text-2xl font-semibold text-slate-900">
          User Investigation
        </h2>
        <p className="mt-2 text-slate-600">
          Review employee daily risk assessments and the evidence behind them.
        </p>
      </header>

      <section className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
        <form onSubmit={handleSearch} className="flex flex-col gap-3 sm:flex-row">
          <div className="flex-1">
            <label htmlFor="employee-id" className="mb-2 block text-sm font-medium text-slate-700">
              Employee ID
            </label>
            <input
              id="employee-id"
              value={search}
              onChange={(event) => setSearch(event.target.value)}
              placeholder="For example, EMP142"
              className="w-full rounded-lg border border-slate-300 px-4 py-3 outline-none focus:border-blue-500"
            />
          </div>
          <button
            type="submit"
            className="self-end rounded-lg bg-blue-600 px-5 py-3 font-medium text-white hover:bg-blue-700"
          >
            Find employee
          </button>
        </form>
      </section>

      {error && (
        <div role="alert" className="rounded-lg border border-red-200 bg-red-50 p-4 text-sm text-red-700">
          {error}
        </div>
      )}

      {loading && (
        <div className="rounded-xl border border-slate-200 bg-white p-8 text-center text-slate-500">
          Loading employee history...
        </div>
      )}

      {!loading && !error && userId && records.length === 0 && (
        <div className="rounded-xl border border-amber-200 bg-amber-50 p-6 text-amber-900">
          No daily risk assessments found for {userId}.
        </div>
      )}

      {!loading && latest && (
        <>
          <section className="rounded-xl border border-slate-200 bg-white p-6 shadow-sm">
            <div className="flex flex-wrap items-start justify-between gap-4">
              <div>
                <p className="text-sm font-medium text-blue-600">
                  Employee assessment
                </p>
                <h3 className="mt-1 text-xl font-semibold text-slate-900">
                  {latest.user_id}
                </h3>
                <p className="mt-1 text-slate-600">
                  {latest.role || "Role not available"} ·{" "}
                  {latest.ldap_domain || "LDAP domain not available"}
                </p>
                <p className="mt-1 text-sm text-slate-500">
                  Latest assessment: {latest.date}
                </p>
              </div>
              <Badge level={latest.risk_level} />
            </div>
          </section>

          <section className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4">
            <ScoreCard
              title="Overall Risk Score"
              value={latest.risk_score}
              status={latest.risk_status}
            />
            <ScoreCard
              title="Behavioral Deviation"
              value={latest.behavioral_deviation_score}
              status={latest.baseline_status}
            />
            <ScoreCard
              title="Peer Deviation"
              value={latest.peer_deviation_score}
              status={latest.peer_deviation_status}
            />
            <ScoreCard
              title="Context Risk"
              value={latest.context_risk_score}
              status={latest.context_status}
            />
          </section>

          <section className="rounded-xl border border-slate-200 bg-white p-6 shadow-sm">
            <h3 className="text-lg font-semibold text-slate-900">
              Assessment context
            </h3>
            <div className="mt-5 grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4">
              <div>
                <p className="text-sm text-slate-500">Role</p>
                <p className="mt-1 font-semibold text-slate-900">
                  {latest.role || "Not available"}
                </p>
              </div>
              <div>
                <p className="text-sm text-slate-500">LDAP Domain</p>
                <p className="mt-1 font-semibold text-slate-900">
                  {latest.ldap_domain || "Not available"}
                </p>
              </div>
              <div>
                <p className="text-sm text-slate-500">Context Match</p>
                <p className="mt-1 font-semibold text-slate-900">
                  {latest.context_match_status || "Not available"}
                </p>
              </div>
              <div>
                <p className="text-sm text-slate-500">Peer Score Scope</p>
                <p className="mt-1 font-semibold text-slate-900">
                  {latest.peer_score_scope || "Not available"}
                </p>
              </div>
              <div>
                <p className="text-sm text-slate-500">Context Event Count</p>
                <p className="mt-1 font-semibold text-slate-900">
                  {latest.context_event_count ?? "Not available"}
                </p>
              </div>
              <div>
                <p className="text-sm text-slate-500">Context Peer Count</p>
                <p className="mt-1 font-semibold text-slate-900">
                  {latest.context_peer_count ?? "Not available"}
                </p>
              </div>
            </div>
          </section>

          <section className="rounded-xl border border-slate-200 bg-white p-6 shadow-sm">
            <h3 className="text-lg font-semibold text-slate-900">
              Why was this risk score assigned?
            </h3>
            <p className="mt-3 whitespace-pre-wrap text-sm leading-7 text-slate-700">
              {latest.risk_explanation || "No risk explanation available."}
            </p>

            <div className="mt-5 border-t border-slate-100 pt-5">
              <h4 className="font-semibold text-slate-900">
                Context explanation
              </h4>
              <p className="mt-2 whitespace-pre-wrap text-sm leading-7 text-slate-600">
                {latest.context_explanation || "No context explanation available."}
              </p>
            </div>
          </section>

          <section className="overflow-hidden rounded-xl border border-slate-200 bg-white shadow-sm">
            <div className="border-b border-slate-200 p-6">
              <h3 className="text-lg font-semibold text-slate-900">
                Daily Assessment History
              </h3>
              <p className="mt-1 text-sm text-slate-500">
                {records.length} daily assessments for {latest.user_id}.
              </p>
            </div>

            <div className="overflow-x-auto">
              <table className="w-full min-w-[650px] text-left text-sm">
                <thead className="bg-slate-50 text-slate-500">
                  <tr>
                    <th className="px-5 py-4">Date</th>
                    <th className="px-5 py-4">Risk Score</th>
                    <th className="px-5 py-4">Risk Level</th>
                    <th className="px-5 py-4">Risk Status</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100">
                  {records.map((record) => (
                    <tr
                      key={`${record.user_id}-${record.date}`}
                      className="hover:bg-slate-50"
                    >
                      <td className="px-5 py-4 text-slate-700">
                        {record.date}
                      </td>
                      <td className="px-5 py-4 font-semibold text-slate-900">
                        {record.risk_score == null
                          ? "Unavailable"
                          : Number(record.risk_score).toFixed(2)}
                      </td>
                      <td className="px-5 py-4">
                        <Badge level={record.risk_level} />
                      </td>
                      <td className="px-5 py-4 text-slate-600">
                        {record.risk_status || "Not available"}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </section>

          <p className="text-xs leading-5 text-slate-500">
            These records represent daily risk assessments, not individual
            security alerts. An anomaly does not prove malicious intent.
            Peer deviation uses the recorded peer-score scope shown above.
          </p>
        </>
      )}
    </div>
  );
}

import { useEffect, useState } from "react";
import {
    getClusterSummary,
    getClusterUsers,
} from "../api/client";

function MetricCard({ title, value, description }) {
  return (
    <div className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
      <p className="text-sm text-slate-500">{title}</p>
      <p className="mt-2 text-2xl font-semibold text-slate-900">{value}</p>
      {description && (
        <p className="mt-1 text-xs text-slate-500">{description}</p>
      )}
    </div>
  );
}

function formatFeatureName(name) {
  return name.replace(/_1d$/, "").replaceAll("_", " ");
}

export default function BehaviorClusters() {
  const [summary, setSummary] = useState(null);
  const [selectedCluster, setSelectedCluster] = useState(null);
  const [users, setUsers] = useState([]);
  const [loading, setLoading] = useState(true);
  const [usersLoading, setUsersLoading] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    let cancelled = false;

    async function loadClusters() {
      try {
        setLoading(true);
        setError("");

        const result = await getClusterSummary();

        if (cancelled) return;

        setSummary(result);

        if (result.clusters?.length) {
          setSelectedCluster(result.clusters[0].cluster_id);
        }
      } catch (err) {
        if (!cancelled) {
          setError(err.message || "Unable to load cluster data.");
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    }

    loadClusters();

    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    if (selectedCluster === null) return undefined;

    let cancelled = false;

    async function loadUsers() {
      try {
        setUsersLoading(true);
        const result = await getClusterUsers(selectedCluster, 100);

        if (!cancelled) {
          setUsers(result.users || []);
        }
      } catch (err) {
        if (!cancelled) {
          setError(err.message || "Unable to load cluster employees.");
        }
      } finally {
        if (!cancelled) setUsersLoading(false);
      }
    }

    loadUsers();

    return () => {
      cancelled = true;
    };
  }, [selectedCluster]);

  if (loading) {
    return (
      <div className="rounded-xl border border-slate-200 bg-white p-8 text-slate-600">
        Loading behavioral clusters...
      </div>
    );
  }

  if (error && !summary) {
    return (
      <div className="rounded-xl border border-red-200 bg-red-50 p-6 text-sm text-red-700">
        <p className="font-semibold">Unable to load Behavior Clusters</p>
        <p className="mt-1">{error}</p>
      </div>
    );
  }

  if (!summary) return null;

  const clusters = summary.clusters || [];
  const selected = clusters.find(
    (cluster) => cluster.cluster_id === selectedCluster
  );

  return (
    <section className="space-y-8">
      <div>
        <h2 className="text-2xl font-semibold text-slate-900">
          Behavior Clusters
        </h2>
        <p className="mt-2 text-slate-600">
          Explore employee behavioral groups identified by the existing
          K-Means model.
        </p>
        <p className="mt-1 text-xs text-slate-500">
          Model: {summary.model_key} · Algorithm: {summary.algorithm}
        </p>
      </div>

      {error && (
        <div className="rounded-lg border border-red-200 bg-red-50 p-3 text-sm text-red-700">
          {error}
        </div>
      )}

      <div className="grid grid-cols-1 gap-5 md:grid-cols-3">
        <MetricCard
          title="Total Employees"
          value={summary.user_count}
          description="Employees assigned to a cluster"
        />
        <MetricCard
          title="Behavioral Groups"
          value={summary.cluster_count}
          description="Groups identified by K-Means"
        />
        <MetricCard
          title="Evaluation Configurations"
          value={summary.evaluation_metrics?.length || 0}
          description="K values evaluated"
        />
      </div>

      <div>
        <h3 className="mb-4 text-lg font-semibold text-slate-900">
          Cluster Distribution
        </h3>

        <div className="grid grid-cols-1 gap-5 lg:grid-cols-3">
          {clusters.map((cluster) => (
            <button
              type="button"
              key={cluster.cluster_id}
              onClick={() => setSelectedCluster(cluster.cluster_id)}
              className={`rounded-xl border bg-white p-5 text-left shadow-sm transition ${
                selectedCluster === cluster.cluster_id
                  ? "border-blue-500 ring-2 ring-blue-100"
                  : "border-slate-200 hover:border-slate-400"
              }`}
            >
              <div className="flex items-center justify-between">
                <h4 className="font-semibold text-slate-900">
                  Cluster {cluster.cluster_id}
                </h4>
                <span className="text-sm font-medium text-blue-700">
                  {Number(cluster.percentage).toFixed(1)}%
                </span>
              </div>

              <p className="mt-3 text-3xl font-semibold text-slate-900">
                {cluster.user_count.toLocaleString()}
              </p>
              <p className="mt-1 text-sm text-slate-500">Employees</p>

              <div className="mt-4 h-2 overflow-hidden rounded-full bg-slate-100">
                <div
                  className="h-full rounded-full bg-blue-600"
                  style={{
                    width: `${Math.min(100, Math.max(0, cluster.percentage))}%`,
                  }}
                />
              </div>
            </button>
          ))}
        </div>
      </div>

      {selected && (
        <div className="grid grid-cols-1 gap-6 xl:grid-cols-2">
          <div className="rounded-xl border border-slate-200 bg-white p-6 shadow-sm">
            <h3 className="text-lg font-semibold text-slate-900">
              Cluster {selected.cluster_id} — Behavioral Profile
            </h3>
            <p className="mt-1 text-sm text-slate-500">
              Mean feature values for employees in this cluster.
            </p>

            <div className="mt-5 overflow-x-auto">
              <table className="w-full text-left text-sm">
                <thead>
                  <tr className="border-b border-slate-200 text-slate-500">
                    <th className="py-3 pr-3 font-medium">Feature</th>
                    <th className="py-3 text-right font-medium">Mean value</th>
                  </tr>
                </thead>
                <tbody>
                  {Object.entries(selected.profile || {}).map(
                    ([feature, value]) => (
                      <tr key={feature} className="border-b border-slate-100">
                        <td className="py-3 pr-3 capitalize text-slate-700">
                          {formatFeatureName(feature)}
                        </td>
                        <td className="py-3 text-right tabular-nums text-slate-900">
                          {Number(value).toFixed(3)}
                        </td>
                      </tr>
                    )
                  )}
                </tbody>
              </table>
            </div>
          </div>

          <div className="space-y-6">
            <div className="rounded-xl border border-slate-200 bg-white p-6 shadow-sm">
              <h3 className="text-lg font-semibold text-slate-900">
                Distinguishing Features
              </h3>
              <p className="mt-1 text-sm text-slate-500">
                Standardized centroid differences from the population average.
              </p>

              <div className="mt-4 space-y-4">
                {(selected.top_features || []).map((feature) => (
                  <div key={feature.feature}>
                    <div className="flex justify-between gap-3 text-sm">
                      <span className="capitalize text-slate-700">
                        {formatFeatureName(feature.feature)}
                      </span>
                      <span className="font-medium tabular-nums text-slate-900">
                        {feature.standardized_centroid > 0 ? "+" : ""}
                        {feature.standardized_centroid.toFixed(3)}
                      </span>
                    </div>
                    <p className="mt-1 text-xs text-slate-500">
                      {feature.direction}
                    </p>
                  </div>
                ))}
              </div>
            </div>

            <div className="rounded-xl border border-slate-200 bg-white p-6 shadow-sm">
              <h3 className="text-lg font-semibold text-slate-900">
                Employees in Cluster {selected.cluster_id}
              </h3>
              <p className="mt-1 text-sm text-slate-500">
                Showing up to 100 employee assignments.
              </p>

              {usersLoading ? (
                <p className="mt-4 text-sm text-slate-500">
                  Loading employees...
                </p>
              ) : (
                <div className="mt-4 max-h-64 overflow-y-auto">
                  {users.length ? (
                    <div className="grid grid-cols-2 gap-2 sm:grid-cols-3">
                      {users.map((user) => (
                        <div
                          key={user.user_id}
                          className="rounded-lg bg-slate-50 px-3 py-2 text-sm text-slate-700"
                        >
                          {user.user_id}
                        </div>
                      ))}
                    </div>
                  ) : (
                    <p className="text-sm text-slate-500">
                      No employee assignments found.
                    </p>
                  )}
                </div>
              )}
            </div>
          </div>
        </div>
      )}

      <div className="rounded-xl border border-slate-200 bg-white p-6 shadow-sm">
        <h3 className="text-lg font-semibold text-slate-900">
          K-Means Evaluation
        </h3>
        <p className="mt-1 text-sm text-slate-500">
          Comparison of the tested cluster counts. These metrics describe
          the evaluated configurations, not a guarantee of optimality.
        </p>

        <div className="mt-4 overflow-x-auto">
          <table className="w-full text-left text-sm">
            <thead>
              <tr className="border-b border-slate-200 text-slate-500">
                <th className="py-3 pr-4">K</th>
                <th className="py-3 pr-4">Silhouette Score</th>
                <th className="py-3 pr-4">Davies-Bouldin Index</th>
                <th className="py-3">Inertia</th>
              </tr>
            </thead>
            <tbody>
              {(summary.evaluation_metrics || []).map((metric) => (
                <tr
                  key={metric.k}
                  className="border-b border-slate-100"
                >
                  <td className="py-3 pr-4 font-medium">{metric.k}</td>
                  <td className="py-3 pr-4 tabular-nums">
                    {metric.silhouette_score.toFixed(4)}
                  </td>
                  <td className="py-3 pr-4 tabular-nums">
                    {metric.davies_bouldin_index.toFixed(4)}
                  </td>
                  <td className="py-3 tabular-nums">
                    {metric.inertia.toFixed(2)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </section>
  );
}

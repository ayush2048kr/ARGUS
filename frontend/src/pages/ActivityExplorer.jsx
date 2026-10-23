
import { useMemo, useState } from "react";

const sampleEvents = [
  {
    event_id: "EVT001",
    user_id: "EMP014",
    timestamp: "2026-10-16T09:12:00",
    source: "Identity Provider",
    event_type: "Authentication",
    action: "Login successful",
    resource: "Corporate account",
    resource_sensitivity: "Internal",
    source_ip: "10.0.4.21",
    destination: "Internal network",
    device_id: "DEV014",
    device_type: "Managed laptop",
    location: "Office",
    role: "Data Analyst",
    department: "Analytics",
    work_schedule: "Standard business hours",
    access_level: "Standard",
    is_external: false,
    description:
      "A successful sign-in from a managed device. Review against the employee's normal login pattern if needed.",
  },
  {
    event_id: "EVT002",
    user_id: "EMP014",
    timestamp: "2026-10-16T10:35:00",
    source: "File Activity",
    event_type: "File Access",
    action: "Sensitive resource accessed",
    resource: "Analytics reporting dataset",
    resource_sensitivity: "Sensitive",
    source_ip: "10.0.4.21",
    destination: "Internal file service",
    device_id: "DEV014",
    device_type: "Managed laptop",
    location: "Office",
    role: "Data Analyst",
    department: "Analytics",
    work_schedule: "Standard business hours",
    access_level: "Standard",
    is_external: false,
    description:
      "Access to a sensitive resource. Whether this is unusual depends on job responsibilities, authorization, and historical usage.",
  },
  {
    event_id: "EVT003",
    user_id: "EMP027",
    timestamp: "2026-10-16T14:20:00",
    source: "File Activity",
    event_type: "Download",
    action: "File download",
    resource: "Finance reports",
    resource_sensitivity: "Internal",
    source_ip: "10.0.7.18",
    destination: "Internal workstation",
    device_id: "DEV027",
    device_type: "Managed laptop",
    location: "Office",
    role: "Finance Associate",
    department: "Finance",
    work_schedule: "Standard business hours",
    access_level: "Standard",
    is_external: false,
    description:
      "A file download. The current demo data does not contain a historical baseline or download volume measurement.",
  },
  {
    event_id: "EVT004",
    user_id: "EMP031",
    timestamp: "2026-10-16T19:45:00",
    source: "Network Activity",
    event_type: "Network Connection",
    action: "Connection to external destination",
    resource: "External endpoint",
    resource_sensitivity: "Sensitive",
    source_ip: "10.0.2.11",
    destination: "External destination (example)",
    device_id: "DEV031",
    device_type: "Managed workstation",
    location: "Office",
    role: "Systems Administrator",
    department: "IT",
    work_schedule: "Rotational",
    access_level: "Privileged",
    is_external: true,
    description:
      "An external connection by a privileged account. Verify the destination, authorization, maintenance schedule, and expected administrative activity before drawing conclusions.",
  },
  {
    event_id: "EVT005",
    user_id: "EMP031",
    timestamp: "2026-10-17T08:05:00",
    source: "Identity Provider",
    event_type: "Authentication",
    action: "Login successful",
    resource: "Administrative account",
    resource_sensitivity: "Sensitive",
    source_ip: "10.0.2.11",
    destination: "Internal network",
    device_id: "DEV031",
    device_type: "Managed workstation",
    location: "Office",
    role: "Systems Administrator",
    department: "IT",
    work_schedule: "Rotational",
    access_level: "Privileged",
    is_external: false,
    description:
      "A successful sign-in for a privileged account. Assess it against the user's approved access and normal working pattern.",
  },
];

const eventTypes = [
  "ALL",
  ...new Set(sampleEvents.map((event) => event.event_type)),
];

function formatTimestamp(timestamp) {
  return `${timestamp.replace("T", " ")} (demo timestamp)`;
}

function ActivityExplorer() {
  const [search, setSearch] = useState("");
  const [eventType, setEventType] = useState("ALL");
  const [externalFilter, setExternalFilter] = useState("ALL");
  const [selectedEventId, setSelectedEventId] = useState(null);

  const filteredEvents = useMemo(() => {
    const query = search.trim().toLowerCase();

    return sampleEvents.filter((event) => {
      const matchesSearch =
        !query ||
        event.event_id.toLowerCase().includes(query) ||
        event.user_id.toLowerCase().includes(query) ||
        event.action.toLowerCase().includes(query) ||
        event.resource.toLowerCase().includes(query) ||
        event.source.toLowerCase().includes(query) ||
        event.destination.toLowerCase().includes(query);

      const matchesType =
        eventType === "ALL" || event.event_type === eventType;

      const matchesExternal =
        externalFilter === "ALL" ||
        (externalFilter === "EXTERNAL" && event.is_external) ||
        (externalFilter === "INTERNAL" && !event.is_external);

      return matchesSearch && matchesType && matchesExternal;
    });
  }, [search, eventType, externalFilter]);

  const selectedEvent = sampleEvents.find(
    (event) => event.event_id === selectedEventId
  );

  function clearFilters() {
    setSearch("");
    setEventType("ALL");
    setExternalFilter("ALL");
    setSelectedEventId(null);
  }

  return (
    <div className="mx-auto w-full max-w-7xl space-y-6">
      <header>
        <h2 className="text-2xl font-semibold text-slate-900">
          Activity Explorer
        </h2>
        <p className="mt-2 text-slate-600">
          Search activity events and inspect the surrounding user,
          resource, device, and network context.
        </p>
      </header>

      <section className="rounded-xl border border-blue-200 bg-blue-50 p-4">
        <p className="text-sm leading-6 text-blue-900">
          <strong>Demo mode:</strong> These events are illustrative sample
          records, not live telemetry. An unusual event alone does not
          establish malicious intent. Review authorization, history, peer
          behavior, and operational context.
        </p>
      </section>

      <section className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
        <div className="grid grid-cols-1 gap-4 md:grid-cols-3">
          <div>
            <label
              htmlFor="activity-search"
              className="mb-2 block text-sm font-medium text-slate-700"
            >
              Search events
            </label>
            <input
              id="activity-search"
              type="search"
              value={search}
              onChange={(event) => setSearch(event.target.value)}
              placeholder="Event ID, employee, action, resource..."
              className="w-full rounded-lg border border-slate-300 px-4 py-3 text-sm outline-none focus:border-blue-500 focus:ring-2 focus:ring-blue-100"
            />
          </div>

          <div>
            <label
              htmlFor="event-type-filter"
              className="mb-2 block text-sm font-medium text-slate-700"
            >
              Event type
            </label>
            <select
              id="event-type-filter"
              value={eventType}
              onChange={(event) => setEventType(event.target.value)}
              className="w-full rounded-lg border border-slate-300 bg-white px-4 py-3 text-sm outline-none focus:border-blue-500 focus:ring-2 focus:ring-blue-100"
            >
              {eventTypes.map((type) => (
                <option key={type} value={type}>
                  {type === "ALL" ? "All event types" : type}
                </option>
              ))}
            </select>
          </div>

          <div>
            <label
              htmlFor="external-filter"
              className="mb-2 block text-sm font-medium text-slate-700"
            >
              Network context
            </label>
            <select
              id="external-filter"
              value={externalFilter}
              onChange={(event) => setExternalFilter(event.target.value)}
              className="w-full rounded-lg border border-slate-300 bg-white px-4 py-3 text-sm outline-none focus:border-blue-500 focus:ring-2 focus:ring-blue-100"
            >
              <option value="ALL">Internal and external</option>
              <option value="INTERNAL">Internal only</option>
              <option value="EXTERNAL">External only</option>
            </select>
          </div>
        </div>

        <div className="mt-4 flex flex-wrap items-center justify-between gap-3">
          <p className="text-sm text-slate-500">
            Showing{" "}
            <strong className="text-slate-800">
              {filteredEvents.length}
            </strong>{" "}
            of {sampleEvents.length} sample events
          </p>
          <button
            type="button"
            onClick={clearFilters}
            className="rounded-lg border border-slate-300 px-3 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50"
          >
            Clear filters
          </button>
        </div>
      </section>

      <section className="overflow-hidden rounded-xl border border-slate-200 bg-white shadow-sm">
        <div className="border-b border-slate-200 p-5">
          <h3 className="text-lg font-semibold text-slate-900">
            Activity events
          </h3>
          <p className="mt-1 text-sm text-slate-500">
            Select an event to view its full sample record.
          </p>
        </div>

        {filteredEvents.length === 0 ? (
          <div className="p-8 text-center">
            <p className="font-medium text-slate-800">
              No matching events
            </p>
            <p className="mt-2 text-sm text-slate-500">
              Change your search or filters and try again.
            </p>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full min-w-[850px] text-left text-sm">
              <thead className="bg-slate-50 text-slate-600">
                <tr>
                  <th className="px-5 py-4 font-semibold">Event ID</th>
                  <th className="px-5 py-4 font-semibold">Timestamp</th>
                  <th className="px-5 py-4 font-semibold">Employee</th>
                  <th className="px-5 py-4 font-semibold">Event</th>
                  <th className="px-5 py-4 font-semibold">Resource</th>
                  <th className="px-5 py-4 font-semibold">Network</th>
                  <th className="px-5 py-4 font-semibold">Details</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {filteredEvents.map((event) => (
                  <tr
                    key={event.event_id}
                    className={
                      selectedEventId === event.event_id
                        ? "bg-blue-50"
                        : "hover:bg-slate-50"
                    }
                  >
                    <td className="whitespace-nowrap px-5 py-4 font-semibold text-slate-900">
                      {event.event_id}
                    </td>
                    <td className="whitespace-nowrap px-5 py-4 text-slate-600">
                      {event.timestamp.replace("T", " ")}
                    </td>
                    <td className="px-5 py-4 font-medium text-slate-700">
                      {event.user_id}
                    </td>
                    <td className="px-5 py-4 text-slate-600">
                      {event.event_type}
                      <p className="mt-1 text-xs text-slate-500">
                        {event.action}
                      </p>
                    </td>
                    <td className="px-5 py-4 text-slate-600">
                      {event.resource}
                      <p className="mt-1 text-xs text-slate-500">
                        {event.resource_sensitivity}
                      </p>
                    </td>
                    <td className="px-5 py-4">
                      <span
                        className={`rounded-full px-2.5 py-1 text-xs font-semibold ${
                          event.is_external
                            ? "bg-amber-100 text-amber-800"
                            : "bg-slate-100 text-slate-700"
                        }`}
                      >
                        {event.is_external ? "External" : "Internal"}
                      </span>
                    </td>
                    <td className="px-5 py-4">
                      <button
                        type="button"
                        onClick={() => setSelectedEventId(event.event_id)}
                        className="whitespace-nowrap font-semibold text-blue-700 hover:text-blue-900"
                      >
                        View details →
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>

      {selectedEvent && (
        <section
          className="rounded-xl border border-slate-200 bg-white p-6 shadow-sm"
          aria-labelledby="event-detail-heading"
        >
          <div className="flex flex-wrap items-start justify-between gap-4">
            <div>
              <p className="text-sm font-medium text-blue-700">
                Event investigation
              </p>
              <h3
                id="event-detail-heading"
                className="mt-1 text-xl font-semibold text-slate-900"
              >
                {selectedEvent.event_id} — {selectedEvent.action}
              </h3>
              <p className="mt-2 text-sm text-slate-500">
                {selectedEvent.user_id} · {selectedEvent.event_type}
              </p>
            </div>
            <button
              type="button"
              onClick={() => setSelectedEventId(null)}
              className="rounded-lg border border-slate-300 px-3 py-2 text-sm text-slate-700 hover:bg-slate-50"
            >
              Close details
            </button>
          </div>

          <div className="mt-6 grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-3">
            <div className="rounded-lg bg-slate-50 p-4">
              <p className="text-sm text-slate-500">Timestamp</p>
              <p className="mt-2 break-words font-medium text-slate-900">
                {formatTimestamp(selectedEvent.timestamp)}
              </p>
            </div>
            <div className="rounded-lg bg-slate-50 p-4">
              <p className="text-sm text-slate-500">Source</p>
              <p className="mt-2 font-medium text-slate-900">
                {selectedEvent.source}
              </p>
            </div>
            <div className="rounded-lg bg-slate-50 p-4">
              <p className="text-sm text-slate-500">Resource sensitivity</p>
              <p className="mt-2 font-medium text-slate-900">
                {selectedEvent.resource_sensitivity}
              </p>
            </div>
            <div className="rounded-lg bg-slate-50 p-4">
              <p className="text-sm text-slate-500">Source IP</p>
              <p className="mt-2 font-medium text-slate-900">
                {selectedEvent.source_ip}
              </p>
            </div>
            <div className="rounded-lg bg-slate-50 p-4">
              <p className="text-sm text-slate-500">Destination</p>
              <p className="mt-2 break-words font-medium text-slate-900">
                {selectedEvent.destination}
              </p>
            </div>
            <div className="rounded-lg bg-slate-50 p-4">
              <p className="text-sm text-slate-500">Device</p>
              <p className="mt-2 font-medium text-slate-900">
                {selectedEvent.device_type} ({selectedEvent.device_id})
              </p>
            </div>
            <div className="rounded-lg bg-slate-50 p-4">
              <p className="text-sm text-slate-500">Role and department</p>
              <p className="mt-2 font-medium text-slate-900">
                {selectedEvent.role}
              </p>
              <p className="mt-1 text-sm text-slate-600">
                {selectedEvent.department}
              </p>
            </div>
            <div className="rounded-lg bg-slate-50 p-4">
              <p className="text-sm text-slate-500">Work schedule</p>
              <p className="mt-2 font-medium text-slate-900">
                {selectedEvent.work_schedule}
              </p>
            </div>
            <div className="rounded-lg bg-slate-50 p-4">
              <p className="text-sm text-slate-500">Access level and location</p>
              <p className="mt-2 font-medium text-slate-900">
                {selectedEvent.access_level}
              </p>
              <p className="mt-1 text-sm text-slate-600">
                {selectedEvent.location}
              </p>
            </div>
          </div>

          <div className="mt-6 rounded-xl border border-slate-200 p-5">
            <h4 className="font-semibold text-slate-900">
              Event context
            </h4>
            <p className="mt-2 text-sm leading-6 text-slate-600">
              {selectedEvent.description}
            </p>
          </div>

          <div className="mt-4 rounded-lg border border-amber-200 bg-amber-50 p-4">
            <p className="text-sm leading-6 text-amber-900">
              No official risk score is calculated on this page. Risk
              assessment belongs to the ARGUS backend risk engine and should
              combine behavior, peer deviation, context, and activity
              severity when integrated.
            </p>
          </div>
        </section>
      )}
    </div>
  );
}

export default ActivityExplorer;

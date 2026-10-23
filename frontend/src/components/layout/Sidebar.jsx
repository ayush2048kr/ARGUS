function Sidebar({ activePage, onNavigate }) {
  const menuItems = [
    "Overview",
    "Alerts",
    "User Investigation",
    "Risks",
    "Clusters",
    "Activity",
  ];

  return (
    <aside className="w-64 min-h-screen shrink-0 bg-slate-950 p-6 text-white">
      <div className="mb-10">
        <h1 className="text-2xl font-bold">ARGUS</h1>
        <p className="mt-1 text-sm text-slate-400">
          Insider Threat Detection
        </p>
      </div>

      <nav className="space-y-2">
        {menuItems.map((item) => (
          <button
            key={item}
            type="button"
            onClick={() => onNavigate(item)}
            className={`w-full rounded-lg px-4 py-3 text-left transition ${
              activePage === item
                ? "bg-slate-800 text-white"
                : "text-slate-300 hover:bg-slate-900 hover:text-white"
            }`}
          >
            {item}
          </button>
        ))}
      </nav>
    </aside>
  );
}

export default Sidebar;
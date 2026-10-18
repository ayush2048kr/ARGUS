function Header() {
  return (
    <header className="flex items-center justify-between border-b border-slate-200 bg-white px-8 py-4">
      <div>
        <h1 className="text-xl font-semibold text-slate-900">
          Security Overview
        </h1>
        <p className="text-sm text-slate-500">
          Context-aware security monitoring
        </p>
      </div>

      <div className="flex items-center gap-4">
        <button
          className="rounded-lg p-2 text-slate-600 hover:bg-slate-100"
          aria-label="Notifications"
        >
          🔔
        </button>

        <div className="flex items-center gap-3">
          <div className="flex h-9 w-9 items-center justify-center rounded-full bg-slate-800 text-sm font-semibold text-white">
            A
          </div>

          <div>
            <p className="text-sm font-medium text-slate-900">
              Analyst
            </p>
            <p className="text-xs text-slate-500">
              Security Team
            </p>
          </div>
        </div>
      </div>
    </header>
  )
}

export default Header
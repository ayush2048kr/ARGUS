function Header({ user, onLogout }) {
  const userId = user?.user_id || "Analyst";
  const role = user?.role || "Security Team";
  const initial = userId.charAt(0).toUpperCase();

  return (
    <header className="flex flex-wrap items-center justify-between gap-4 border-b border-slate-200 bg-white px-4 py-4 md:px-8">
      <div>
        <h1 className="text-xl font-semibold text-slate-900">
          Security Overview
        </h1>
        <p className="text-sm text-slate-500">
          Context-aware security monitoring
        </p>
      </div>

      <div className="flex items-center gap-4">
        <div className="flex items-center gap-3">
          <div className="flex h-9 w-9 items-center justify-center rounded-full bg-slate-800 text-sm font-semibold text-white">
            {initial}
          </div>

          <div>
            <p className="text-sm font-medium text-slate-900">
              {userId}
            </p>
            <p className="text-xs capitalize text-slate-500">
              {role}
            </p>
          </div>
        </div>

        <button
          type="button"
          onClick={onLogout}
          className="rounded-lg border border-slate-300 px-3 py-2 text-sm font-medium text-slate-700 transition hover:bg-slate-50"
        >
          Log out
        </button>
      </div>
    </header>
  );
}

export default Header;
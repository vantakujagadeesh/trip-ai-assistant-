(() => {
  const apiBase = ["localhost", "127.0.0.1"].includes(window.location.hostname)
    ? "http://localhost:8000"
    : "";
  let initialization;

  async function initialize() {
    if (!initialization) {
      initialization = (async () => {
        const response = await fetch(`${apiBase}/config`);
        const config = await response.json();
        if (!response.ok) {
          throw new Error(config.detail || "Could not load account configuration.");
        }
        if (!config.supabase_configured) {
          throw new Error("Accounts are not configured yet. Add the Supabase environment variables.");
        }
        if (!window.supabase?.createClient) {
          throw new Error("The account service did not load. Refresh the page and try again.");
        }

        const supabase = window.supabase.createClient(
          config.supabase_url,
          config.supabase_anon_key,
          {
            auth: {
              storage: window.sessionStorage,
              persistSession: true,
              autoRefreshToken: true,
              detectSessionInUrl: true,
            },
          },
        );

        async function apiFetch(path, options = {}) {
          const { data, error } = await supabase.auth.getSession();
          if (error) throw new Error("Could not read the sign-in session.");
          if (!data.session) throw new Error("Sign in to continue.");

          const headers = new Headers(options.headers || {});
          headers.set("Authorization", `Bearer ${data.session.access_token}`);
          if (options.body && !headers.has("Content-Type")) {
            headers.set("Content-Type", "application/json");
          }
          return fetch(`${apiBase}${path}`, { ...options, headers });
        }

        return { apiBase, supabase, apiFetch };
      })();
    }
    return initialization;
  }

  window.RoamAuth = { initialize };
})();

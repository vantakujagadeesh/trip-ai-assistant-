(() => {
  const allowedDestinations = new Set(["my-trips.html", "plan.html", "admin.html"]);
  const requestedDestination = new URLSearchParams(window.location.search).get("next");
  const destination = allowedDestinations.has(requestedDestination)
    ? requestedDestination
    : "my-trips.html";
  const form = document.getElementById("account-form");
  const title = document.getElementById("form-title");
  const submitButton = document.getElementById("submit-button");
  const toggleButton = document.getElementById("mode-toggle");
  const status = document.getElementById("account-status");
  const password = document.getElementById("password");
  let mode = "signin";

  function showStatus(message, isError = false) {
    status.textContent = message;
    status.className = `mt-4 min-h-5 text-sm ${isError ? "text-red-600" : "text-on-surface-variant"}`;
  }

  function setMode(nextMode) {
    mode = nextMode;
    const signingUp = mode === "signup";
    title.textContent = signingUp ? "Create your account" : "Sign in";
    submitButton.textContent = signingUp ? "Create account" : "Sign in";
    toggleButton.textContent = signingUp ? "I already have an account" : "Create an account";
    password.autocomplete = signingUp ? "new-password" : "current-password";
    password.minLength = signingUp ? 12 : 1;
    showStatus("");
  }

  toggleButton.addEventListener("click", () => {
    setMode(mode === "signin" ? "signup" : "signin");
  });
  setMode("signin");

  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    submitButton.disabled = true;
    showStatus(mode === "signup" ? "Creating your account..." : "Signing in...");

    try {
      const { supabase } = await window.RoamAuth.initialize();
      const email = document.getElementById("email").value.trim();
      const passwordValue = password.value;

      if (mode === "signup") {
        const { data, error } = await supabase.auth.signUp({
          email,
          password: passwordValue,
          options: {
            emailRedirectTo: `${window.location.origin}/account.html?next=${encodeURIComponent(destination)}`,
          },
        });
        if (error) throw error;
        if (!data.session) {
          showStatus("Check your email for a confirmation link, then return here to sign in.");
          return;
        }
      } else {
        const { error } = await supabase.auth.signInWithPassword({ email, password: passwordValue });
        if (error) throw error;
      }

      window.location.replace(destination);
    } catch (error) {
      showStatus(error.message || "Account action failed. Please try again.", true);
    } finally {
      submitButton.disabled = false;
    }
  });

  window.RoamAuth.initialize()
    .then(async ({ supabase }) => {
      const { data } = await supabase.auth.getSession();
      if (data.session) window.location.replace(destination);
    })
    .catch((error) => showStatus(error.message || "Account service is unavailable.", true));
})();

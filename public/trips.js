(() => {
  const grid = document.getElementById("trips-grid");
  const requestsContainer = document.getElementById("booking-requests");
  const statusElement = document.getElementById("page-status");
  const signInPrompt = document.getElementById("sign-in-prompt");
  const modal = document.getElementById("booking-modal");
  const form = document.getElementById("booking-form");
  const submitButton = document.getElementById("booking-submit");
  let selectedTrip = null;
  let apiFetch;

  grid.replaceChildren();
  grid.classList.remove("hidden");
  requestsContainer.replaceChildren();
  statusElement.classList.add("hidden");

  function setPageStatus(message, isError = false) {
    statusElement.textContent = message;
    statusElement.className = `fixed bottom-4 left-4 z-40 max-w-md rounded-xl px-4 py-3 text-sm text-white shadow-xl ${isError ? "bg-red-700" : "bg-gray-900"}`;
    window.setTimeout(() => statusElement.classList.add("hidden"), 5000);
  }

  async function readResponse(response) {
    const body = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(body.detail || "The request could not be completed.");
    return body;
  }

  function makeEmptyState(message) {
    const empty = document.createElement("p");
    empty.className = "rounded-2xl border border-dashed border-outline-variant p-8 text-sm text-on-surface-variant";
    empty.textContent = message;
    return empty;
  }

  function renderTrips(trips) {
    grid.replaceChildren();
    if (!trips.length) {
      grid.append(makeEmptyState("No saved trips yet. Plan a trip and use Save trip to keep it here."));
      return;
    }

    for (const trip of trips) {
      const card = document.createElement("article");
      card.className = "trip-card overflow-hidden rounded-2xl border border-outline-variant bg-white shadow-sm";

      const banner = document.createElement("div");
      banner.className = "flex h-36 items-center justify-center bg-gradient-to-r from-orange-500 to-amber-600 text-white";
      const icon = document.createElement("span");
      icon.className = "material-symbols-outlined text-5xl";
      icon.textContent = "flight_takeoff";
      banner.append(icon);

      const content = document.createElement("div");
      content.className = "flex flex-col gap-3 p-5";
      const title = document.createElement("h3");
      title.className = "text-lg font-bold text-on-surface";
      title.textContent = trip.title;

      const details = document.createElement("p");
      details.className = "text-sm text-on-surface-variant";
      const startDate = typeof trip.dates?.start === "string" ? ` · ${trip.dates.start}` : "";
      details.textContent = `${trip.days} days · ${trip.destination}${startDate}`;

      const cost = document.createElement("p");
      cost.className = "text-sm font-bold text-primary";
      cost.textContent = trip.estimated_cost_inr !== null
        && trip.estimated_cost_inr !== undefined
        && Number.isFinite(Number(trip.estimated_cost_inr))
        ? `Estimated ₹${Number(trip.estimated_cost_inr).toLocaleString("en-IN")}`
        : "Estimated cost unavailable";

      const actions = document.createElement("div");
      actions.className = "mt-2 flex flex-wrap gap-2";
      const openButton = document.createElement("button");
      openButton.type = "button";
      openButton.className = "rounded-xl border border-outline px-4 py-2 text-sm font-semibold text-primary hover:bg-primary-fixed";
      openButton.textContent = "Open itinerary";
      openButton.addEventListener("click", () => {
        sessionStorage.setItem("roam_open_trip", JSON.stringify({
          id: trip.id,
          itinerary: trip.itinerary,
        }));
        window.location.href = "plan.html";
      });

      const requestButton = document.createElement("button");
      requestButton.type = "button";
      requestButton.className = "rounded-xl bg-primary px-4 py-2 text-sm font-semibold text-white hover:opacity-90";
      requestButton.textContent = "Request booking";
      requestButton.addEventListener("click", () => openBookingForm(trip));

      actions.append(openButton, requestButton);
      content.append(title, details, cost, actions);
      card.append(banner, content);
      grid.append(card);
    }
  }

  function renderBookingRequests(requests) {
    requestsContainer.replaceChildren();
    if (!requests.length) {
      requestsContainer.append(makeEmptyState("No booking requests yet."));
      return;
    }

    const statusClasses = {
      requested: "bg-amber-100 text-amber-800",
      contacted: "bg-blue-100 text-blue-800",
      confirmed: "bg-green-100 text-green-800",
      cancelled: "bg-gray-200 text-gray-700",
    };

    for (const request of requests) {
      const card = document.createElement("article");
      card.className = "rounded-2xl border border-outline-variant bg-white p-5";
      const heading = document.createElement("h3");
      heading.className = "font-bold text-on-surface";
      heading.textContent = `${request.service_type} · ${request.destination}`;
      const trip = document.createElement("p");
      trip.className = "mt-1 text-sm text-on-surface-variant";
      trip.textContent = request.trip_title;
      const details = document.createElement("p");
      details.className = "mt-2 text-sm text-on-surface-variant";
      details.textContent = `Provider: ${request.provider || "Not specified"} · Travel date: ${request.travel_date || "Not specified"}`;
      const status = document.createElement("span");
      status.className = `mt-3 inline-block rounded-full px-3 py-1 text-xs font-semibold ${statusClasses[request.status] || "bg-gray-100 text-gray-700"}`;
      status.textContent = request.status;
      card.append(heading, trip, details, status);
      requestsContainer.append(card);
    }
  }

  function openBookingForm(trip) {
    selectedTrip = trip;
    form.reset();
    document.getElementById("booking-trip-title").textContent = trip.title;
    document.getElementById("booking-form-status").textContent = "";
    if (/^\d{4}-\d{2}-\d{2}$/.test(trip.dates?.start || "")) {
      document.getElementById("booking-date").value = trip.dates.start;
    }
    modal.classList.remove("hidden");
  }

  function closeBookingForm() {
    modal.classList.add("hidden");
    selectedTrip = null;
  }

  async function refreshData() {
    const [tripsResponse, requestsResponse] = await Promise.all([
      apiFetch("/trips"),
      apiFetch("/booking-requests"),
    ]);
    const [trips, requests] = await Promise.all([
      readResponse(tripsResponse),
      readResponse(requestsResponse),
    ]);
    renderTrips(trips);
    renderBookingRequests(requests);
  }

  document.getElementById("close-booking-modal").addEventListener("click", closeBookingForm);
  modal.addEventListener("click", (event) => {
    if (event.target === modal) closeBookingForm();
  });

  document.getElementById("signout-button").addEventListener("click", async () => {
    try {
      const { supabase } = await window.RoamAuth.initialize();
      const { error } = await supabase.auth.signOut();
      if (error) throw error;
      window.location.replace("account.html?next=my-trips.html");
    } catch (error) {
      setPageStatus(error.message || "Could not sign out.", true);
    }
  });

  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    if (!selectedTrip) return;
    submitButton.disabled = true;
    document.getElementById("booking-form-status").textContent = "Sending request...";

    try {
      const response = await apiFetch("/booking-requests", {
        method: "POST",
        body: JSON.stringify({
          trip_id: selectedTrip.id,
          service_type: document.getElementById("booking-service").value,
          provider: document.getElementById("booking-provider").value.trim() || null,
          travel_date: document.getElementById("booking-date").value || null,
          contact_name: document.getElementById("contact-name").value.trim(),
          contact_phone: document.getElementById("contact-phone").value.trim() || null,
          notes: document.getElementById("booking-notes").value.trim() || null,
        }),
      });
      await readResponse(response);
      closeBookingForm();
      await refreshData();
      setPageStatus("Request received. This is not a confirmed reservation; a provider or our team must confirm it.");
    } catch (error) {
      document.getElementById("booking-form-status").textContent = error.message || "Could not send booking request.";
    } finally {
      submitButton.disabled = false;
    }
  });

  (async () => {
    try {
      const { supabase, apiFetch: authenticatedFetch } = await window.RoamAuth.initialize();
      apiFetch = authenticatedFetch;
      const { data, error } = await supabase.auth.getSession();
      if (error) throw error;
      if (!data.session) {
        signInPrompt.classList.remove("hidden");
        return;
      }

      document.getElementById("account-link").classList.add("hidden");
      document.getElementById("signout-button").classList.remove("hidden");
      if (data.session.user.app_metadata?.role === "admin") {
        document.getElementById("admin-link").classList.remove("hidden");
      }
      await refreshData();
    } catch (error) {
      setPageStatus(error.message || "Could not load your trips.", true);
    }
  })();
})();

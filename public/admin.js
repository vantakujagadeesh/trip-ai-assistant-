(() => {
  const list = document.getElementById("request-list");
  const statusElement = document.getElementById("admin-status");

  function setStatus(message, isError = false) {
    statusElement.textContent = message;
    statusElement.className = `mt-4 text-sm ${isError ? "text-red-600" : "text-on-surface-variant"}`;
  }

  async function readResponse(response) {
    const body = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(body.detail || "The request could not be completed.");
    return body;
  }

  function renderRequests(requests, apiFetch) {
    list.replaceChildren();
    if (!requests.length) {
      const empty = document.createElement("p");
      empty.className = "rounded-2xl border border-dashed border-outline-variant p-8 text-sm text-on-surface-variant";
      empty.textContent = "There are no booking requests yet.";
      list.append(empty);
      return;
    }

    for (const request of requests) {
      const card = document.createElement("article");
      card.className = "grid gap-4 rounded-2xl border border-outline-variant bg-white p-5 md:grid-cols-[1fr_auto] md:items-center";
      const details = document.createElement("div");
      const title = document.createElement("h2");
      title.className = "font-bold";
      title.textContent = `${request.service_type} · ${request.destination} · ${request.trip_title}`;
      const customer = document.createElement("p");
      customer.className = "mt-1 text-sm text-on-surface-variant";
      customer.textContent = `${request.contact_name} · ${request.requester_email}${request.contact_phone ? ` · ${request.contact_phone}` : ""}`;
      const schedule = document.createElement("p");
      schedule.className = "mt-1 text-sm text-on-surface-variant";
      schedule.textContent = `Provider: ${request.provider || "Not specified"} · Travel date: ${request.travel_date || "Not specified"}`;
      const notes = document.createElement("p");
      notes.className = "mt-2 whitespace-pre-wrap text-sm";
      notes.textContent = request.notes || "";
      details.append(title, customer, schedule, notes);

      const controls = document.createElement("div");
      controls.className = "flex flex-col gap-2 sm:flex-row";
      const select = document.createElement("select");
      select.className = "rounded-xl border border-outline-variant px-3 py-2 text-sm";
      for (const value of ["requested", "contacted", "confirmed", "cancelled"]) {
        const option = document.createElement("option");
        option.value = value;
        option.textContent = value;
        option.selected = value === request.status;
        select.append(option);
      }
      const update = document.createElement("button");
      update.type = "button";
      update.className = "rounded-xl bg-primary px-4 py-2 text-sm font-semibold text-white disabled:opacity-60";
      update.textContent = "Update status";
      update.addEventListener("click", async () => {
        update.disabled = true;
        try {
          await readResponse(await apiFetch(`/admin/booking-requests/${encodeURIComponent(request.id)}`, {
            method: "PATCH",
            body: JSON.stringify({ status: select.value }),
          }));
          request.status = select.value;
          setStatus(`Updated request for ${request.destination}.`);
        } catch (error) {
          setStatus(error.message || "Could not update booking request.", true);
        } finally {
          update.disabled = false;
        }
      });
      controls.append(select, update);
      card.append(details, controls);
      list.append(card);
    }
  }

  document.getElementById("signout-button").addEventListener("click", async () => {
    try {
      const { supabase } = await window.RoamAuth.initialize();
      const { error } = await supabase.auth.signOut();
      if (error) throw error;
      window.location.replace("account.html?next=admin.html");
    } catch (error) {
      setStatus(error.message || "Could not sign out.", true);
    }
  });

  (async () => {
    try {
      const { supabase, apiFetch } = await window.RoamAuth.initialize();
      const { data, error } = await supabase.auth.getSession();
      if (error) throw error;
      if (!data.session) {
        window.location.replace("account.html?next=admin.html");
        return;
      }
      if (data.session.user.app_metadata?.role !== "admin") {
        setStatus("Administrator access is required.", true);
        return;
      }
      const requests = await readResponse(await apiFetch("/admin/booking-requests"));
      renderRequests(requests, apiFetch);
      setStatus(`${requests.length} request(s) loaded.`);
    } catch (error) {
      setStatus(error.message || "Could not load booking requests.", true);
    }
  })();
})();

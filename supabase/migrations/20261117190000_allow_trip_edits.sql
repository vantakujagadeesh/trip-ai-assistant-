grant update (days, dates, estimated_cost_inr, itinerary)
    on public.trips to authenticated;

drop policy if exists "Users can update their own trips" on public.trips;
create policy "Users can update their own trips"
    on public.trips for update to authenticated
    using (user_id = (select auth.uid()))
    with check (user_id = (select auth.uid()));

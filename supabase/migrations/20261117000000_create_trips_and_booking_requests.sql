create table if not exists public.trips (
    id uuid primary key default gen_random_uuid(),
    user_id uuid not null references auth.users (id) on delete cascade,
    title text not null check (char_length(btrim(title)) between 1 and 160),
    destination text not null check (char_length(btrim(destination)) between 1 and 120),
    days integer not null check (days between 1 and 90),
    dates jsonb not null default '{}'::jsonb check (pg_column_size(dates) <= 5000),
    estimated_cost_inr numeric(12, 2) check (
        estimated_cost_inr is null or estimated_cost_inr between 0 and 1000000000
    ),
    itinerary jsonb not null check (pg_column_size(itinerary) <= 100000),
    created_at timestamptz not null default now()
);

create index if not exists trips_user_created_idx
    on public.trips (user_id, created_at desc);

alter table public.trips enable row level security;
revoke all on public.trips from anon, authenticated;
grant select, delete on public.trips to authenticated;
grant insert (user_id, title, destination, days, dates, estimated_cost_inr, itinerary)
    on public.trips to authenticated;

create policy "Users can read their own trips"
    on public.trips for select to authenticated
    using (user_id = (select auth.uid()));

create policy "Users can create their own trips"
    on public.trips for insert to authenticated
    with check (user_id = (select auth.uid()));

create policy "Users can delete their own trips"
    on public.trips for delete to authenticated
    using (user_id = (select auth.uid()));

create table if not exists public.booking_requests (
    id uuid primary key default gen_random_uuid(),
    user_id uuid not null references auth.users (id) on delete cascade,
    trip_id uuid not null references public.trips (id) on delete restrict,
    trip_title text not null check (char_length(btrim(trip_title)) between 1 and 160),
    destination text not null check (char_length(btrim(destination)) between 1 and 120),
    service_type text not null check (
        service_type in ('flight', 'hotel', 'train', 'bus', 'cab', 'other')
    ),
    provider text check (provider is null or char_length(btrim(provider)) between 1 and 120),
    travel_date date,
    contact_name text not null check (char_length(btrim(contact_name)) between 1 and 120),
    contact_phone text check (contact_phone is null or char_length(btrim(contact_phone)) <= 30),
    requester_email text not null check (char_length(requester_email) <= 320),
    notes text check (notes is null or char_length(notes) <= 2000),
    status text not null default 'requested' check (
        status in ('requested', 'contacted', 'confirmed', 'cancelled')
    ),
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);

create index if not exists booking_requests_user_created_idx
    on public.booking_requests (user_id, created_at desc);
create index if not exists booking_requests_status_created_idx
    on public.booking_requests (status, created_at desc);

alter table public.booking_requests enable row level security;
revoke all on public.booking_requests from anon, authenticated;
grant select on public.booking_requests to authenticated;
grant insert (
    user_id, trip_id, service_type, provider, travel_date, contact_name, contact_phone, notes
) on public.booking_requests to authenticated;
grant update (status) on public.booking_requests to authenticated;

create policy "Users and administrators can read booking requests"
    on public.booking_requests for select to authenticated
    using (
        user_id = (select auth.uid())
        or (select auth.jwt() -> 'app_metadata' ->> 'role') = 'admin'
    );

create policy "Users can submit booking requests for their own trips"
    on public.booking_requests for insert to authenticated
    with check (
        user_id = (select auth.uid())
        and status = 'requested'
        and exists (
            select 1
            from public.trips
            where trips.id = booking_requests.trip_id
              and trips.user_id = (select auth.uid())
        )
    );

create policy "Administrators can update booking request statuses"
    on public.booking_requests for update to authenticated
    using ((select auth.jwt() -> 'app_metadata' ->> 'role') = 'admin')
    with check ((select auth.jwt() -> 'app_metadata' ->> 'role') = 'admin');

create or replace function public.prepare_booking_request()
returns trigger
language plpgsql
security definer
set search_path = ''
as $$
begin
    if auth.uid() is null or new.user_id <> auth.uid() then
        raise exception 'booking request owner does not match authenticated user'
            using errcode = '42501';
    end if;

    select title, destination
    into new.trip_title, new.destination
    from public.trips
    where id = new.trip_id
      and user_id = auth.uid();

    if not found then
        raise exception 'trip not found for authenticated user'
            using errcode = '23503';
    end if;

    new.requester_email := auth.jwt() ->> 'email';
    if new.requester_email is null then
        raise exception 'an email address is required'
            using errcode = '23514';
    end if;

    new.status := 'requested';
    new.created_at := now();
    new.updated_at := now();
    return new;
end;
$$;

revoke all on function public.prepare_booking_request() from public, anon, authenticated;
drop trigger if exists booking_requests_prepare on public.booking_requests;
create trigger booking_requests_prepare
    before insert on public.booking_requests
    for each row execute function public.prepare_booking_request();

create or replace function public.set_booking_request_updated_at()
returns trigger
language plpgsql
set search_path = ''
as $$
begin
    new.updated_at = now();
    return new;
end;
$$;

revoke all on function public.set_booking_request_updated_at() from public, anon, authenticated;
drop trigger if exists booking_requests_set_updated_at on public.booking_requests;
create trigger booking_requests_set_updated_at
    before update on public.booking_requests
    for each row execute function public.set_booking_request_updated_at();

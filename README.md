# 🌍 Roam AI — Provider-Aware Trip Planner

> **Roam AI** builds trip outlines using **FastAPI**, **LangGraph**, **Google Gemini**, and external travel-data providers. It distinguishes live data from curated suggestions and reports when a provider is unavailable. The app does not train a custom model or book travel.

---

## 🌟 Key Features

### ✈️ 1. Transport and stays
- Amadeus flight and hotel offers are shown only when production credentials return live inventory. Sandbox responses are identified and excluded from recommendations.
- Flight seat counts are shown only when the provider supplies them. Hotel pins and distances to mapped places use provider coordinates; Amadeus does not provide an exact remaining-room count.
- Live train, bus, cab, and rental inventory is not integrated; the app links to external providers instead of fabricating schedules or prices.
- Booking links are external searches. The app does not confirm or charge for bookings.
- **Account-backed Trips:** Sign in to save itineraries across devices and submit booking requests with status tracking. Requests are not reservations or payments.

### 🍽️ 2. Dining
- Some destinations have curated meal suggestions. Restaurant search, opening hours, table availability, and current prices are not connected.
- Unknown destinations receive generic meal breaks, not invented restaurant names.

### 🌤️ 3. Weather
- Current conditions and forecasts come from Open-Meteo when available.
- Trip-date forecasts are limited to the provider's 16-day horizon; dates outside it are marked unavailable rather than extrapolated.

### 🛣️ 4. Travel advisories
- Weather-based destination advisories may be shown when weather data is available.
- Live route traffic, road closures, and local authority alerts are not connected.

### 🎙️ 5. Voice AI Input & Audio Guide Narration
- **Voice Search (Speech-to-Text):** Native browser speech recognition with pulsating microphone indicator.
- **Text-to-Speech Audio Guide:** Single-click audio narration for historical landmarks and attractions.

### 📄 6. PDF Export & Smart Travel Tools
- **Print / PDF Export:** Clean `@media print` layout for printouts and PDF downloads.
- **Packing Checklist:** General suggestions with weather-dependent additions when forecasts are available.
- **Safety Data:** Destination-specific official contacts and local rules are not connected.
- **Interactive Leaflet.js Maps:** Destination map and place markers; current opening hours and entry availability are not verified.

---

## 📐 Architecture Overview

```
                       ┌──────────────────────────────┐
                       │     User Browser Frontend     │
                        │ (HTML5, Tailwind, Leaflet.js)│
                       └──────────────┬───────────────┘
                                      │ SSE Stream
                                      ▼
                       ┌──────────────────────────────┐
                       │      FastAPI Gateway         │
                       │        (main.py)             │
                       └──────────────┬───────────────┘
                                      │
                                      ▼
                       ┌──────────────────────────────┐
                       │       LangGraph Agent        │
                       │      (graph/agent.py)        │
                       └──────┬──────────────┬────────┘
                              │              │
             ┌────────────────┘              └────────────────┐
             ▼                                                ▼
┌──────────────────────────┐                    ┌──────────────────────────┐
│  RAG Knowledge Retriever │                    │   MCP Multi-Tool Suite   │
│   (rag/knowledge_base)   │                    │ (asyncio.gather 10 tools)│
└──────────────────────────┘                    └─────────────┬────────────┘
                                                              │
       ┌──────────────────┬──────────────────┬────────────────┼──────────────────┬──────────────────┐
       ▼                  ▼                  ▼                ▼                  ▼                  ▼
┌──────────────┐   ┌──────────────┐   ┌──────────────┐  ┌──────────────┐   ┌──────────────┐   ┌──────────────┐
│  flights.py  │   │  trains.py   │   │   buses.py   │  │   cabs.py    │   │  hotels.py   │   │  weather.py  │
└──────────────┘   └──────────────┘   └──────────────┘  └──────────────┘   └──────────────┘   └──────────────┘
                                                              │
                                            ┌─────────────────┴─────────────────┐
                                            ▼                                   ▼
                             ┌──────────────────────────────┐    ┌──────────────────────────────┐
                             │     live_conditions.py       │    │          places.py           │
                             └──────────────────────────────┘    └──────────────────────────────┘
```

---

## 🛠️ Tech Stack

- **Frontend:** HTML5, CSS3 (Vanilla CSS + TailwindCSS), JavaScript (ES6+), Leaflet.js Maps, Web Speech API, Web SpeechSynthesis API.
- **Backend:** FastAPI (Python 3.12+), Uvicorn, LangGraph, keyword-based destination knowledge retrieval.
- **AI Models & SDK:** Google Gemini API (`google-genai` SDK — free-tier `gemini-4-hydrogen` with `gemini-3.8-flash` fallback), with a local rule-based fallback. Gemini is optional per request and requires explicit user consent; no model training occurs.
- **APIs & Data:** Open-Meteo weather/geocoding, Amadeus flight/hotel offers, and OpenTripMap place catalogs when configured.

---

## 🚀 Quick Start Guide

### Prerequisites
- Python 3.12
- Git

### 1. Clone the Repository
```bash
git clone https://github.com/vantakujagadeesh/trip-ai-assistant-.git
cd trip-ai-assistant-
```

### 2. Set Up Virtual Environment & Dependencies
```bash
python3.12 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

### 3. Environment Configuration
Copy `.env.example` to `.env` and add the API keys you want to use:
```bash
cp .env.example .env
```

### 4. Launch the Servers

**Terminal 1: Start Backend API (FastAPI)**
```bash
./start.sh
```

**Terminal 2: Start Frontend HTTP Server**
```bash
python3 -m http.server 3000 --directory public
```

### 5. Access the Platform
Open your browser and navigate to:
- **Planner Studio:** `http://localhost:3000/plan.html`
- **Home Landing Page:** `http://localhost:3000/index.html`
- **API Documentation:** `http://localhost:8000/docs`

## Deploy to Vercel

The repository is configured as a FastAPI application with static files served from `public/`. Import the Git repository into Vercel and keep the project root as the Root Directory; Vercel detects the `backend.main:app` entry point from `pyproject.toml`. `backend/requirements.txt` lists the minimal runtime packages for the Vercel function and should stay aligned with the root `pyproject.toml`.

Add the integrations you use under **Project Settings → Environment Variables**:

- `GEMINI_API_KEY` (required for optional Gemini responses; defaults to the free-tier `gemini-4-hydrogen` and `gemini-3.8-flash` models; other model IDs are ignored)
- `AMADEUS_API_KEY` and `AMADEUS_API_SECRET`
- `OPENTRIPMAP_API_KEY`
- `EXCHANGE_RATE_API_KEY`
- `N8N_EMAIL_WEBHOOK_URL` and `N8N_PRICE_ALERT_WEBHOOK_URL`

Redeploy after adding environment variables. No local Chroma database is required; the serverless deployment uses the built-in keyword retrieval fallback.

The planner's Gemini consent checkbox is unchecked by default. When users opt in, Roam sends the request, relevant trip/provider details, and curated context to Google; basic email and phone patterns are redacted first. Google states that free-tier content may be used to improve its products. Without Gemini consent, the local response generator is used; configured travel providers may still receive the search details needed to return results. Do not submit names, account, passport, or payment details. Confirm the Google AI Studio project remains on the Free tier: quotas apply, and paid account settings can enable charges even for these model IDs.

### Accounts, saved trips, and booking requests

The app uses Supabase Auth and Postgres for account-backed trip storage. Booking requests are requests for follow-up, not confirmed travel reservations or payments. Provider responses can change before a user completes an external booking. Amadeus sandbox data is test-only and is not bookable; set `AMADEUS_BASE_URL` to the provider's production endpoint and use production credentials before expecting live offers.

1. Create a Supabase project and run `supabase/migrations/20261117000000_create_trips_and_booking_requests.sql` in its SQL Editor.
2. Enable email/password sign-in and email confirmation in Supabase Auth. Configure the allowed redirect URLs for your local app and deployed `account.html` page.
3. Add `SUPABASE_URL` and `SUPABASE_ANON_KEY` to local `.env` and Vercel Preview/Production environment variables, then redeploy. The anon/publishable key is public; database row-level security protects records. **Do not add a Supabase `service_role` key to the browser or this app.**
4. Configure `ALLOWED_ORIGINS` with the exact frontend origins if the API and frontend use different domains. Same-origin Vercel deployments do not need an additional production origin.
5. To grant an administrator access, run this once in the Supabase SQL Editor as the project owner, replacing the email:

   ```sql
   update auth.users
   set raw_app_meta_data = coalesce(raw_app_meta_data, '{}'::jsonb) || '{"role":"admin"}'::jsonb
   where email = 'admin@example.com';
   ```

   The administrator must sign out and back in; the `admin.html` dashboard then allows booking-request statuses to be changed. Customers can only read their own trips and requests; administrators can read all booking requests.

Existing trips in browser `localStorage` are not moved automatically; they remain on that browser. Before a public launch, add a shared rate limiter or Vercel firewall rules for the public AI endpoint to control abuse and model costs—an in-memory limiter is not reliable on serverless functions. Also publish privacy, terms, support, and data-retention information, and configure real provider credentials. Live India train and bus fares require approved partner APIs; live cab, restaurant, traffic, and road-closure integrations also remain unconnected.

---

## 📂 Project Structure

```
trip-ai-assistant/
├── public/                 # Static frontend served by Vercel's CDN
│   ├── index.html
│   ├── plan.html
│   ├── discover.html
│   ├── my-trips.html
│   ├── account.html        # Supabase sign-in and registration
│   ├── admin.html          # Admin-only booking request dashboard
│   ├── app-auth.js         # Shared Supabase client and authenticated API requests
│   ├── trips.js
│   ├── admin.js
│   ├── trip-details.html
│   └── styles.css
├── supabase/
│   └── migrations/         # Trips, booking requests, constraints, and RLS policies
├── pyproject.toml           # Python version and Vercel ASGI entry point
├── .env.example             # Local environment variable template
├── start.sh                 # Local API launcher
└── backend/
    ├── main.py              # FastAPI server & SSE endpoint
    ├── requirements.txt     # Minimal runtime dependencies for Vercel
    ├── persistence.py       # Supabase Auth verification and RLS-backed API access
    ├── graph/
    │   └── agent.py
    ├── mcp_tools/
    ├── n8n/
    └── rag/
        └── knowledge_base.py
```



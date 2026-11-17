# 🌍 Roam AI — Real-Time Multi-Modal AI Travel Concierge

> **Roam AI** is an advanced, weather-adaptive, multi-modal travel platform powered by **FastAPI**, **LangGraph**, **Google Gemini**, and **Model Context Protocol (MCP)** tools. It generates 100% custom day-by-day travel itineraries with 3 meals a day, live weather forecasts, real-time road condition advisories, multi-transport options, interactive Leaflet.js maps, voice search, and audio guides.

---

## 🌟 Key Features

### ✈️ 1. Multi-Modal Transport Comparison & Best Route Advice
- **Side-by-Side Fare Comparison:** Direct Flights ✈️, Vande Bharat & Rajdhani Trains 🚆, Volvo AC Sleeper Buses 🚌, and Outstation Taxis / Self-Drive Rentals 🚗.
- **Route Recommendation Engine:** Intelligent route synthesis comparing transit speed, comfort, traffic, and cost efficiency.
- **Instant Booking Links:** Direct booking shortcuts to MakeMyTrip, IRCTC, RedBus, Uber, and Booking.com.

### 🍽️ 2. 3-Meal Culinary Dining Engine
- **Breakfast 🍳:** Regional specialties, iconic street food, and heritage café brews (~8:30 AM).
- **Lunch 🥗:** Authentic regional thalis, coastal delicacies, and garden dining (~1:30 PM).
- **Dinner 🍽️:** Clifftop, rooftop, and beach shack fine dining experiences (~8:00 PM).

### 🌤️ 3. Live Weather & Dynamic Weather Adaptation
- **Real-Time Weather Metrics:** Live temperature, feels-like temp, humidity, wind speed, UV index, and Air Quality (US AQI).
- **12-Hour Hourly Forecast:** Visual hourly temperature and rain probability strip.
- **Dynamic Activity Swap:** Automatically swaps outdoor sightseeing with indoor heritage museums and tea houses when rain probability exceeds 45%.

### 🛣️ 4. Real-Time Road Conditions & Hazard Advisories
- **Highway Route Hazards:** Real-time road blockage risk assessment (LOW, MODERATE, HIGH, CRITICAL) for 25+ major highways & mountain ghats.
- **Smart Departure Timing:** Departure recommendations to avoid peak rain, fog, or city traffic.
- **Detour Suggestions:** Alternative bypass route advisories during severe weather.

### 🎙️ 5. Voice AI Input & Audio Guide Narration
- **Voice Search (Speech-to-Text):** Native browser speech recognition with pulsating microphone indicator.
- **Text-to-Speech Audio Guide:** Single-click audio narration for historical landmarks and attractions.

### 📄 6. PDF Export & Smart Travel Tools
- **Print / PDF Export:** Clean `@media print` layout for printouts and PDF downloads.
- **Interactive Packing Checklist:** Weather-adaptive packing list with clickable checkboxes.
- **Culture, Safety & Scam Guide:** Local etiquette rules, tipping standards, emergency helpline numbers, and tourist scam prevention tips.
- **Interactive Leaflet.js Maps:** Day-by-day connected route polylines and live attraction markers.

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
- **AI Models & SDK:** Google Gemini API (`google-genai` SDK — `gemini-1.5-flash`), custom NLP intent parser.
- **APIs & Data:** Open-Meteo Weather API, Open-Meteo Air Quality API, Amadeus Flight API, OpenTripMap API.

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

- `GEMINI_API_KEY`
- `AMADEUS_API_KEY` and `AMADEUS_API_SECRET`
- `OPENTRIPMAP_API_KEY`
- `EXCHANGE_RATE_API_KEY`
- `N8N_EMAIL_WEBHOOK_URL` and `N8N_PRICE_ALERT_WEBHOOK_URL`

Redeploy after adding environment variables. No local Chroma database is required; the serverless deployment uses the built-in keyword retrieval fallback.

---

## 📂 Project Structure

```
trip-ai-assistant/
├── public/                 # Static frontend served by Vercel's CDN
│   ├── index.html
│   ├── plan.html
│   ├── discover.html
│   ├── my-trips.html
│   ├── trip-details.html
│   └── styles.css
├── pyproject.toml           # Python version and Vercel ASGI entry point
├── .env.example             # Local environment variable template
├── start.sh                 # Local API launcher
└── backend/
    ├── main.py              # FastAPI server & SSE endpoint
    ├── requirements.txt     # Minimal runtime dependencies for Vercel
    ├── graph/
    │   └── agent.py
    ├── mcp_tools/
    ├── n8n/
    └── rag/
        └── knowledge_base.py
```



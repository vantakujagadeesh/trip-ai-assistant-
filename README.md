# 🌍 Roam AI — Real-Time Weather-Adaptive Multi-Modal Travel Concierge

[![License: MIT](https://img.shields.io/badge/License-MIT-amber.svg)](LICENSE)
[![Python 3.9+](https://img.shields.io/badge/Python-3.9%2B-blue.svg)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/Backend-FastAPI-009688.svg)](https://fastapi.tiangolo.com/)
[![LangGraph](https://img.shields.io/badge/AI-LangGraph-orange.svg)](https://www.langchain.com/langgraph)
[![Google Gemini](https://img.shields.io/badge/LLM-Google%20Gemini-4285F4.svg)](https://ai.google.dev/)

**Roam AI** is a state-of-the-art, multi-modal travel platform powered by **LangGraph**, **Google Gemini**, and **10+ Model Context Protocol (MCP) tools**. It generates 100% custom, destination-tailored itineraries featuring **3 Meals of the Day (Breakfast 🍳, Lunch 🥗, Dinner 🍽️)**, real-time side-by-side transport options (Flights ✈️, Vande Bharat Trains 🚆, Volvo Buses 🚌, Outstation Cabs 🚗), live weather forecasts with dynamic indoor/outdoor activity swaps, real-time highway hazard alerts, voice AI, audio guides, interactive Leaflet.js maps, and instant PDF exports.

---

## ✨ Key Features

- **🍽️ 3-Meal Culinary Engine:** Recommends authentic, verified local breakfast spots, regional lunch thalis, and rooftop/clifftop dinner venues with dish names and price estimates for every day.
- **🚄 Multi-Modal Transport Comparison:** Compares direct flights, Vande Bharat Express / Shatabdi trains (classes 1A, 2A, 3A, EC, CC), Volvo A/C Multi-Axle sleeper buses, and outstation cabs/self-drive rentals side-by-side with direct booking links.
- **🛣️ Best Route & Highway Advice:** Analyzes distances, travel times, route advice, and highway conditions across 25+ major Indian corridors (e.g. NH-48, Yamuna Expressway, NH-66).
- **🌤️ Live Weather & 🚗 Road Hazards:** Fetches real-time temperatures, hourly 12h forecasts, UV index, air quality (US AQI), fog/rain visibility, and best departure time recommendations via free APIs.
- **🌧️ Dynamic Weather Activity Swap:** Automatically swaps outdoor sightseeing with covered heritage museums and tea houses when rain probability exceeds 45%.
- **🔊 Audio Guide Narration:** Native browser Text-to-Speech audio guide narration for historical landmarks and top attractions.
- **🎙️ Voice AI Input (Speech-to-Text):** Hands-free voice prompt search using Web Speech API with active audio recording indicators.
- **📄 Printable PDF Export:** Dedicated `@media print` engine generating clean, multi-page printouts/PDFs without UI clutter.
- **🗺️ Interactive Route Maps:** Leaflet.js map with custom pin drops and dashed route polylines connecting daily stops sequentially.
- **🚨 Culture, Etiquette & Scam Prevention:** Country/city-specific emergency helplines (Police, Ambulance, Tourist Helpline 1363), tipping guidelines, temple dress codes, and local tourist scams to avoid.
- **🎒 Interactive Packing Checklist:** Destination-tailored, weather-adaptive interactive packing list with checkboxes.
- **📧 Email & Price Alert Webhooks:** Integrated n8n webhooks for sending HTML email itineraries and price-drop notifications.

---

## 📐 Architecture Overview

```
                       ┌──────────────────────────────┐
                       │     User Browser Frontend     │
                       │ (HTML5, Tailwind, Leaflet.js)│
                       └──────────────┬───────────────┘
                                      │ EventSource / SSE Stream
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
│ (Amadeus API)│   │ (IRCTC Mock) │   │ (Volvo A/C)  │  │(Self-Drive)  │   │ (Hotel Search│   │ (Open-Meteo) │
└──────────────┘   └──────────────┘   └──────────────┘  └──────────────┘   └──────────────┘   └──────────────┘
                                                              │
                                            ┌─────────────────┴─────────────────┐
                                            ▼                                   ▼
                             ┌──────────────────────────────┐    ┌──────────────────────────────┐
                             │     live_conditions.py       │    │          places.py           │
                             │ (Weather, UV, Road Hazards)  │    │  (Attractions & 3-Meal Engine)│
                             └──────────────────────────────┘    └──────────────────────────────┘
```

---

## 🛠️ Tech Stack

- **Frontend:** Single-page web app built with HTML5, Vanilla CSS, TailwindCSS, Material Symbols, and Leaflet.js.
- **Backend Framework:** Python 3.9+, FastAPI, Uvicorn, Asyncio.
- **AI Agent Framework:** LangGraph, LangChain, ChromaDB (RAG Vector Store).
- **LLM SDK:** Google GenAI SDK (`google-genai`), Gemini 1.5 Flash / Gemini 2.0 Flash.
- **Live APIs (No-Key / Free Tier):** Open-Meteo Weather & Air Quality API, OpenTripMap API, Amadeus Flight & Hotel Offers API.
- **Automation / Webhooks:** n8n Cloud (Email delivery & fare alerts).

---

## 📁 Repository Structure

```
trip-ai-assistant/
├── backend/
│   ├── graph/
│   │   ├── agent.py               # LangGraph state machine & multi-modal synthesizer
│   ├── mcp_tools/
│   │   ├── itinerary.py           # Master orchestrator & parallel task executor
│   │   ├── live_conditions.py     # Live weather, hourly, UV, AQI & road risk tool
│   │   ├── places.py              # 25+ city attraction & 3-meal culinary database
│   │   ├── flights.py             # Flight search tool (Amadeus integration)
│   │   ├── trains.py              # Indian Railways train search (Vande Bharat / Express)
│   │   ├── buses.py               # Intercity Volvo AC sleeper bus tool
│   │   ├── cabs.py                # Outstation taxi & self-drive rental tool
│   │   ├── hotels.py              # Hotel offers search tool
│   │   ├── weather.py             # Daily weather forecast tool
│   │   └── currency.py            # Budget breakdown calculator
│   ├── rag/
│   │   ├── knowledge_base.py      # ChromaDB retriever & destination guide RAG
│   ├── main.py                    # FastAPI app, SSE streaming endpoints & CORS config
│   ├── requirements.txt           # Python dependencies
│   └── .env.example               # Example environment variable file
├── index.html                     # Landing home page with prompt triggers
├── plan.html                      # Real-time split-screen AI Travel Studio
├── discover.html                  # Destination discovery & prompt hub
├── my-trips.html                  # Saved trips dashboard (LocalStorage sync)
├── styles.css                     # Custom CSS design tokens & animations
└── start.sh                       # One-click startup script
```

---

## 🚀 Quick Start Guide

### Prerequisites
- Python 3.9 or higher
- Google Gemini API Key ([Get a free key at Google AI Studio](https://aistudio.google.com/))

### 1. Clone the Repository
```bash
git clone https://github.com/vantakujagadeesh/trip-ai-assistant-.git
cd trip-ai-assistant-
```

### 2. Set Up Backend & Virtual Environment
```bash
cd backend
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 3. Configure Environment Variables
Copy `.env.example` to `.env` inside the `backend/` directory:
```bash
cp .env.example .env
```
Open `backend/.env` and insert your Gemini API Key:
```env
GEMINI_API_KEY=your_gemini_api_key_here
FASTAPI_PORT=8000
FASTAPI_HOST=0.0.0.0
```

### 4. Run the Servers

#### Option A: One-Click Startup Script (Recommended)
From the project root:
```bash
chmod +x start.sh
./start.sh
```

#### Option B: Manual Startup
1. **Start FastAPI Backend (Port 8000):**
   ```bash
   cd backend
   python3 -m uvicorn main:app --host 0.0.0.0 --port 8000 --reload
   ```
2. **Start Frontend Server (Port 3000):**
   ```bash
   python3 -m http.server 3000
   ```

### 5. Access the Web App
Open your browser and navigate to:
👉 **[http://localhost:3000/plan.html](http://localhost:3000/plan.html)**

---

## 📡 API Endpoints

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/health` | Health check endpoint returning backend status |
| `POST` | `/chat` | Server-Sent Events (SSE) streaming endpoint for AI itinerary planning |
| `POST` | `/itinerary/email` | Triggers n8n webhook to email complete HTML itinerary |
| `POST` | `/alerts/subscribe` | Triggers n8n webhook to set up flight/train fare drop alert |

---

## 📜 License

Distributed under the MIT License. See `LICENSE` for more information.

---

⭐ **If you find this repository helpful, give it a star!**

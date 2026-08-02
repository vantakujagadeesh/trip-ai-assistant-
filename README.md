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
- **Backend:** FastAPI (Python 3.9+), Uvicorn, LangGraph State Machine, ChromaDB (Vector Store), Pydantic.
- **AI Models & SDK:** Google Gemini API (`google-genai` SDK — `gemini-1.5-flash`), Custom NLP Intent Parser.
- **APIs & Data:** Open-Meteo Weather API, Open-Meteo Air Quality API, Amadeus Flight API, OpenTripMap API.

---

## 🚀 Quick Start Guide

### Prerequisites
- Python 3.9 or higher
- Git

### 1. Clone the Repository
```bash
git clone https://github.com/vantakujagadeesh/trip-ai-assistant-.git
cd trip-ai-assistant-
```

### 2. Set Up Virtual Environment & Dependencies
```bash
cd backend
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 3. Environment Configuration
Create a `.env` file inside the `backend/` directory:
```env
GEMINI_API_KEY=your_gemini_api_key_here
```

### 4. Launch the Servers

**Terminal 1: Start Backend API (FastAPI)**
```bash
cd backend
python3 -m uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

**Terminal 2: Start Frontend HTTP Server**
```bash
python3 -m http.server 3000
```

### 5. Access the Platform
Open your browser and navigate to:
- **Planner Studio:** `http://localhost:3000/plan.html`
- **Home Landing Page:** `http://localhost:3000/index.html`
- **API Documentation:** `http://localhost:8000/docs`

---

## 📂 Project Structure

```
trip-ai-assistant/
├── index.html              # Landing page
├── plan.html               # Main AI Travel Studio & Chat interface
├── discover.html           # Destination discovery page
├── my-trips.html           # Saved trips dashboard
├── trip-details.html       # Saved trip details view
├── styles.css              # Custom global styles
├── start.sh                # Server launcher script
├── README.md               # Project documentation
└── backend/
    ├── main.py             # FastAPI server & SSE endpoint
    ├── graph/
    │   └── agent.py        # LangGraph State Machine & Gemini LLM agent
    ├── mcp_tools/          # MCP Tools Suite
    │   ├── flights.py      # Flight search tool
    │   ├── trains.py       # Indian Railways (Vande Bharat/Express) tool
    │   ├── buses.py        # Volvo Intercity bus tool
    │   ├── cabs.py         # Outstation cabs & self-drive rentals tool
    │   ├── hotels.py       # Hotel offers search tool
    │   ├── weather.py      # Open-Meteo weather tool
    │   ├── live_conditions.py # Live weather, UV, AQI & road conditions tool
    │   ├── places.py       # OpenTripMap & 3-Meal Dining Engine
    │   └── itinerary.py    # Master itinerary orchestrator
    └── rag/
        └── knowledge_base.py # ChromaDB vector store retriever
```



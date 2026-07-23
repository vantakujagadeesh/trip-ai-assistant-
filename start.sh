#!/bin/bash
# Roam AI — Quick Start Script
# Run: bash "/Users/vantakujagadeesh/Desktop/trip assitant/start.sh"

cd "$(dirname "$0")/backend"

echo ""
echo "╔══════════════════════════════════════════════════════════╗"
echo "║          🌍 ROAM AI TRAVEL ASSISTANT — SETUP              ║"
echo "╚══════════════════════════════════════════════════════════╝"
echo ""

# Check if GEMINI_API_KEY is set
if grep -q "your_gemini_api_key_here" .env 2>/dev/null; then
  echo "⚠️  GEMINI API KEY NOT SET"
  echo ""
  echo "  Get your FREE key at: https://aistudio.google.com/apikey"
  echo "  Then paste it below (or press Enter to run with demo data):"
  echo ""
  read -r -p "  Paste your Gemini API key: " GKEY
  if [ -n "$GKEY" ]; then
    sed -i '' "s|your_gemini_api_key_here|$GKEY|g" .env
    echo "  ✅ Key saved to .env"
  else
    echo "  ℹ️  Running with demo data (no AI narrative, but itinerary cards will work)"
  fi
fi

echo ""
echo "🚀 Starting Roam AI Backend on http://localhost:8000"
echo "   Frontend running on http://localhost:3000/plan.html"
echo ""
echo "   Stop with Ctrl+C"
echo ""

export PATH="/Users/vantakujagadeesh/fakehome/Library/Python/3.9/bin:$PATH"
python3 -m uvicorn main:app --host 0.0.0.0 --port 8000 --reload

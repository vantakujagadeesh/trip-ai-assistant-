"""
RAG Knowledge Base — ChromaDB setup and document loading
Destination guides embedded with sentence-transformers
"""
import os
import json
from pathlib import Path
from typing import Optional


CHROMA_PERSIST_DIR = os.getenv("CHROMA_PERSIST_DIR", "./rag/chroma_db")

# Destination knowledge documents
KNOWLEDGE_DOCS = [
    {
        "id": "goa_guide",
        "source": "goa",
        "content": """
GOA TRAVEL GUIDE — Complete Insider Knowledge

BEST TIME TO VISIT: November to February (peak season, dry and sunny, 25-30°C). 
Avoid June-September (monsoon, heavy rains). October is shoulder season with great deals.

TOP BEACHES:
- Baga Beach: North Goa, party scene, beach shacks, water sports (jet ski ₹600/ride)
- Palolem Beach: South Goa, quieter, crescent shape, calm for swimming, kayaking ₹300/hr
- Vagator Beach: Dramatic red cliffs, hippie culture, Chapora Fort nearby (free entry)
- Anjuna Beach: Famous Tuesday flea market (clothes, jewelry, spices), best at sunset

MUST-SEE ATTRACTIONS:
- Basilica of Bom Jesus (UNESCO): St. Francis Xavier's remains, Old Goa, free entry, 9am-6:30pm
- Fort Aguada: Portuguese fort 1612, lighthouse, panoramic sea views, ₹100 entry
- Dudhsagar Falls: 4-tiered 600m waterfall, jeep safari ₹2000/jeep, spectacular in Oct-Nov
- Spice Plantation Tour: Savoi or Tropical Spice, ₹500-800 includes lunch

FOOD & RESTAURANTS:
- Fish Curry Rice: Goan staple, ₹150-300, try at Ritz Classic in Panaji
- Vinayak Restaurant: Best pork xacuti and prawn balchao
- Thalassa: Greek-inspired, beach views, upmarket ₹1500-3000/person
- Beach shacks: Johnnys, Britto's, Infantaria — casual, ₹400-800/meal

TRANSPORT:
- Bike rental: ₹250-400/day (most popular way to explore)
- Taxi: South to North Goa approx ₹600-800
- Bus: Kadamba state transport, ₹15-40, slow but cheap

BUDGET BREAKDOWN (per person, 5 days):
- Budget trip: ₹15,000-20,000 (hostel, bike, beach shacks)
- Mid-range: ₹25,000-35,000 (3-star hotel, good restaurants)
- Luxury: ₹50,000+ (5-star resort, private beach clubs)

VISA: Not applicable for Indian nationals. Foreign nationals need Indian e-Visa (online, ~$25).

PACKING LIST: Sunscreen SPF50+, light cotton clothes, flip flops, mosquito repellent, 
beach towel, snorkeling gear (or rent on beach ₹200-400), waterproof bag.

LOCAL TIPS:
- Book water sports directly on beach, avoid hotel middlemen (save 30%)
- Carry ₹500 and ₹200 notes — beach shacks don't accept cards
- Respect local culture in markets/temples — cover shoulders
- North Goa party strip: Baga-Calangute-Candolim. South Goa: peaceful, nature-focused
        """,
    },
    {
        "id": "kerala_guide",
        "source": "kerala",
        "content": """
KERALA TRAVEL GUIDE — God's Own Country

BEST TIME: October to March (cool, 22-33°C, post-monsoon greenery).
Monsoon June-August actually beautiful for Ayurveda retreats and backwater fog.

TOP DESTINATIONS:
- Alleppey (Alappuzha): Houseboat capital, backwater cruises ₹6,000-15,000/night
- Munnar: Tea plantations at 1600m altitude, 22°C even in summer, trekking
- Kovalam Beach: Lighthouse Beach iconic, calmer than Goa, Vizhinjam fishing village nearby
- Wayanad: Wildlife sanctuary, tree houses, tribal culture, Edakkal Caves
- Kumarakom: Bird sanctuary, luxury resorts on Vembanad Lake

UNIQUE EXPERIENCES:
- Houseboat overnight stay: Book through KTDC or direct operators in Alleppey
- Kathakali performance: Daily at cultural centers, ₹200-500
- Ayurveda retreat: 3-day minimum, ₹3,000-8,000/day at certified centers
- Spice garden tour: Kumily (Periyar) area, free with guide
- Snake boat races: Nehru Trophy (August), Champakkulam (June)

FOOD:
- Kerala Sadya: 26-dish banana leaf feast, ₹200-400
- Karimeen Pollichathu: Pearl spot fish in banana leaf, ₹300-500
- Appam and Stew: Breakfast staple, ₹80-150
- Seafood at Fort Kochi: Seagull Restaurant, Oceanos

BUDGET: 5 days Kerala
- Budget: ₹20,000-28,000 (homestays, local food, local buses)
- Mid-range: ₹35,000-50,000 (3-star, houseboat 1 night, A/C transport)
- Luxury: ₹80,000+ (CGH Earth or Taj properties, private houseboat)

TRANSPORT:
- KSRTC buses excellent and cheap (₹15-80 between cities)
- Trains: Konkan railway scenic, book 60 days in advance
- Boat: Regular ferry services on backwaters, very cheap ₹10-25
        """,
    },
    {
        "id": "rajasthan_guide",
        "source": "rajasthan",
        "content": """
RAJASTHAN TRAVEL GUIDE — The Land of Kings

BEST TIME: October to March (cool 15-25°C, perfect weather).
Avoid April-June (extreme heat 40-48°C). Monsoon July-September surprisingly beautiful.

GOLDEN TRIANGLE + RAJASTHAN CIRCUIT:
Delhi → Jaipur (5hr train) → Pushkar (3hr bus) → Jodhpur (5hr) → Jaisalmer (5hr) → Udaipur (7hr)

JAIPUR (Pink City):
- Amber Fort: ₹200 Indian/₹550 foreign, elephant ride ₹900, stunning hilltop fort
- City Palace: ₹200 entry, museum of royal artifacts, still partially inhabited by royals
- Hawa Mahal: ₹50 entry, Instagram-famous "Palace of Winds", 953 small windows
- Jantar Mantar (UNESCO): Ancient astronomical observatory, ₹200

JODHPUR (Blue City):
- Mehrangarh Fort: Best fort in India, ₹100 entry + ₹100 audio guide — worth every rupee
- Blue City rooftop view: Wander Old City lanes, amazing photography
- Chokelao Bagh: Garden restaurant inside fort, ₹1000-2000/meal

JAISALMER (Golden City):
- Jaisalmer Fort: Living fort (people still live inside), ₹200 entry
- Sam Sand Dunes: Camel safari ₹300, overnight desert camp ₹1500-6000
- Patwon Ki Haveli: Stunning carved merchant mansion, ₹200

UDAIPUR (City of Lakes):
- Lake Pichola boat ride: ₹400, sunset views of City Palace from water
- City Palace museum: ₹300, most spectacular palace in India
- Monsoon Palace: ₹100, sunset views, featured in James Bond Octopussy

FOOD:
- Dal Baati Churma: Rajasthani staple, ₹150-300
- Laal Maas: Fiery red mutton curry, ₹300-500
- Ker Sangri: Desert beans and capers, vegetarian specialty

BUDGET (10 days full circuit):
- Budget: ₹25,000-35,000 (dorms, trains, dhabas)
- Mid-range: ₹50,000-70,000 (heritage hotels, A/C travel)
- Luxury: ₹1,50,000+ (Oberoi, Taj heritage properties)
        """,
    },
    {
        "id": "italy_cinque_terre_guide",
        "source": "italy",
        "content": """
ITALY — CINQUE TERRE & ITALIAN RIVIERA TRAVEL GUIDE

BEST TIME: May-June or September-October (fewer crowds, 20-26°C, great for hiking).
July-August: peak crowds and heat (30°C+), book everything 3 months ahead.

CINQUE TERRE (5 Villages):
Monterosso al Mare → Vernazza → Corniglia → Manarola → Riomaggiore
All connected by train (€5 Cinque Terre Card, unlimited rides), trail hiking (moderate-hard), or boat.

WHAT TO DO:
- Sentiero Azzurro (Blue Trail): 12km coastal trail, most scenic sections Vernazza-Monterosso
- Swimming: Monterosso has only real beach (paid €20 sun lounger), other villages rocky
- Vernazza Harbor: Most picturesque village, sunset from Castello Doria (€1.50)
- Manarola vineyards: Sciacchetrà sweet wine, vineyards carved into cliffs
- Via dell'Amore (Lovers' Lane): Romantic cliffside path Riomaggiore-Manarola, €7 entry

PORTOFINO & SANTA MARGHERITA:
- Ferry from Genoa (€8) or drive/bus
- Portofino: Tiny harbor village, expensive restaurants (€30-60/meal), but stunning
- Santa Margherita: More authentic, good base, hotels from €120/night
- San Fruttuoso: Only accessible by boat or 3hr hike, medieval abbey in secluded cove

FOOD:
- Trofie al Pesto: Ligurian pasta with fresh basil pesto, €10-15
- Focaccia Genovese: Best in Italy here, €2-4
- Pansotti in Walnut Sauce: Local pasta, €12-18
- Fried anchovies (Acciughe): €5-8
- Sciacchetrà wine: Local sweet dessert wine, €4-8/glass

TRANSPORT:
- Cinque Terre train: La Spezia ↔ Levanto, €5 day pass
- Genoa airport (GOA) — nearest for Italian Riviera
- Milan Malpensa (MXP) — 2hr train to Genoa
- Ferry: Genova-Portofino (€8), Portofino-Cinque Terre (€25)

ACCOMMODATION:
- Genoa: Budget base ₹3,000-6,000/night (€33-70)
- Santa Margherita: Mid-range ₹8,000-15,000/night (€90-170)
- Portofino hotels: Luxury ₹40,000+/night (€450+)

VISA: Schengen visa required for Indian nationals (€80, apply 3 weeks ahead).
        """,
    },
    {
        "id": "japan_guide",
        "source": "japan",
        "content": """
JAPAN TRAVEL GUIDE — Tokyo, Kyoto & Beyond

BEST TIME:
- Cherry blossoms (Sakura): Late March-early April — magical but crowded
- Autumn foliage: Mid-November — stunning colors, fewer tourists
- Summer: July-August hot+humid (30-35°C), major festivals (Obon)
- Winter: December-February, cold (5°C Tokyo), but quiet and cheap

TOKYO (3-4 days minimum):
- Shibuya Crossing: Free, most impressive at rush hour 5-7pm
- Senso-ji Temple (Asakusa): Free, open 24/7, Nakamise shopping street
- TeamLab digital art museum: ¥3,200 (₹1,700), book 2 weeks ahead
- Akihabara: Electronics and anime district, walk around free
- Harajuku & Meiji Shrine: Free shrine, Takeshita Street quirky fashion
- Tsukiji Outer Market: Fresh sushi breakfast from ¥500 (₹270)
- Tokyo Skytree: ¥2,100 (₹1,120), 634m, observatory views

KYOTO (2-3 days):
- Fushimi Inari Shrine: Free, famous orange torii gates, open 24/7
- Kinkaku-ji (Golden Pavilion): ¥500 (₹270)
- Arashiyama Bamboo Grove: Free, best at 6am before crowds
- Geisha district Gion: Free to walk, geishas appear dusk-10pm
- Philosopher's Path: 2km canal walk, beautiful cherry blossoms

TRANSPORT:
- JR Pass: 7-day ¥50,000 (₹26,500) — includes Shinkansen, worth it for Tokyo-Kyoto-Osaka
- Tokyo Metro: Day pass ¥600, IC card (Suica/Pasmo) easiest
- Shinkansen Tokyo-Kyoto: 2h15m, ¥13,700 one way (covered by JR Pass)

FOOD:
- Ramen: ¥700-1,200 (₹370-640), best at Ichiran or local shops
- Sushi at Tsukiji: Set from ¥1,500 (₹800)
- Takoyaki (octopus balls): ¥500 street food
- Conveyor belt sushi: ¥100-300/plate (₹53-160)
- 7-Eleven/Lawson: Best convenience store food in the world, ¥300-500/meal

BUDGET (7 days Japan):
- Budget: ₹55,000-70,000 (hostels, JR Pass, convenience store meals)
- Mid-range: ₹1,00,000-1,40,000 (3-star hotels, restaurants, JR Pass)
- Luxury: ₹2,00,000+ (Ryokan traditional inn, fine dining)

VISA: Japan tourist visa free for Indian nationals for 90 days (as of 2024).
Apply online through VFS Global, processing 3-5 business days, ₹1,500 fee.

ETIQUETTE:
- Remove shoes when entering homes, some restaurants
- Carry cash — many places don't accept cards
- Be quiet on trains — no phone calls
- Bow slightly when greeting
        """,
    },
    {
        "id": "packing_tips",
        "source": "general",
        "content": """
UNIVERSAL TRAVEL PACKING GUIDE

ALWAYS PACK (regardless of destination):
- Power adapter (universal Type A, B, C, D coverage)
- Portable charger/power bank (10,000mAh minimum)
- Photocopies + digital copies of passport, visa, tickets
- Travel insurance (cover medical + trip cancellation)
- Small first aid kit (pain killers, ORS sachets, bandages, antiseptic)
- Microfiber quick-dry towel (saves space, essential for beaches/hostels)
- Ziplock bags (liquid toiletries, wet items, document protection)

BEACH DESTINATIONS (Goa, Bali, Kerala, Thailand):
- Sunscreen SPF50+ (reef-safe)
- After-sun lotion/aloe vera
- Rash guard for snorkeling
- Waterproof phone pouch
- Light linen/cotton clothes
- Flip flops + walking sandals
- Mosquito repellent (DEET 20%+)

COLD/MOUNTAIN DESTINATIONS (Rajasthan winter, Japan, Europe):
- Thermal base layer
- Down jacket (packable)
- Waterproof outer shell
- Warm hat and gloves
- Merino wool socks

CITY/CULTURAL TRIPS (Europe, Japan, Delhi):
- Comfortable walking shoes (10,000+ steps/day)
- Scarf (for mosque/temple entry)
- Modest clothing (cover knees/shoulders for religious sites)
- Small day-backpack
- Reusable water bottle (many European cities have free fountains)

DOCUMENTS CHECKLIST:
☐ Passport (6 months validity minimum)
☐ Visa (print + digital)
☐ Flight tickets (print + screenshot offline)
☐ Hotel bookings (print + screenshot)
☐ Travel insurance policy
☐ Emergency contacts list
☐ Vaccination certificates (if required)
☐ International driving license (if renting vehicles)
        """,
    },
    {
        "id": "visa_guide",
        "source": "general",
        "content": """
VISA GUIDE FOR INDIAN PASSPORT HOLDERS (2024-2025)

VISA-FREE / VISA ON ARRIVAL DESTINATIONS:
- Thailand: Visa-free 30 days (new 2024 policy)
- Indonesia/Bali: Visa on arrival, $35 USD
- Maldives: Free on arrival, 30 days
- Nepal: Free on arrival (Indian passports free forever)
- Bhutan: SDF fee $100/day + ₹1,200 Indian national fee
- Singapore: 30 days visa-free
- Malaysia: eNTRI online, free, 15 days
- Sri Lanka: eTA online $35, 30 days
- Mauritius: Free, 60 days
- Japan: Visa-free 90 days (from 2024)
- Kenya: eVisa $50

E-VISA / EASY PROCESS (apply online, 3-7 days):
- UK: Standard visa £115, apply 6 weeks ahead
- USA: B1/B2 visa, $185 interview required, apply 3 months ahead
- Europe (Schengen): €80, apply through VFS 3 weeks ahead, covers 26 countries
- Canada: eTA $7 for transit, visitor visa $185 with biometrics
- Australia: eVisitor/ETA for some, Visitor visa $145

FASTEST E-VISAS (24-48 hours):
- Turkey: e-Visa $35, 90 days
- Egypt: e-Visa $25, 30 days
- Vietnam: e-Visa $25, 90 days
- Cambodia: e-Visa $36, 30 days

VISA TIPS:
- Apply minimum 4-6 weeks before departure for Schengen/UK/USA
- Rejection risk factors: no return ticket, insufficient funds shown, previous rejections
- Show 3-6 months bank statements with good average balance
- Have hotel + tour bookings ready before applying
- Travel insurance is mandatory for Schengen visa
        """,
    },
]


def get_knowledge_retriever():
    """
    Initialize ChromaDB collection and return a retriever.
    This runs on backend startup and persists to disk.
    """
    try:
        import chromadb
        from chromadb.utils import embedding_functions

        client = chromadb.PersistentClient(path=CHROMA_PERSIST_DIR)

        # Use sentence-transformers for embedding (free, local)
        ef = embedding_functions.SentenceTransformerEmbeddingFunction(
            model_name="all-MiniLM-L6-v2"
        )

        collection = client.get_or_create_collection(
            name="travel_knowledge",
            embedding_function=ef,
            metadata={"hnsw:space": "cosine"},
        )

        # Seed documents if collection is empty
        if collection.count() == 0:
            print("📚 Seeding RAG knowledge base with destination guides...")
            for doc in KNOWLEDGE_DOCS:
                collection.upsert(
                    ids=[doc["id"]],
                    documents=[doc["content"]],
                    metadatas=[{"source": doc["source"]}],
                )
            print(f"✅ Seeded {len(KNOWLEDGE_DOCS)} knowledge documents")

        def retrieve(query: str, n_results: int = 3) -> str:
            """Retrieve relevant context for a query."""
            results = collection.query(
                query_texts=[query],
                n_results=min(n_results, collection.count()),
            )
            docs = results.get("documents", [[]])[0]
            return "\n\n---\n\n".join(docs) if docs else ""

        return retrieve

    except Exception as e:
        print(f"⚠️  ChromaDB unavailable ({e}), using keyword fallback")
        return _keyword_retriever


def _keyword_retriever(query: str, n_results: int = 3) -> str:
    """Simple keyword-based fallback when ChromaDB is unavailable."""
    query_lower = query.lower()
    relevant = []

    keyword_map = {
        ("goa", "beach", "goan"): "goa_guide",
        ("kerala", "backwater", "ayurveda", "houseboat"): "kerala_guide",
        ("rajasthan", "jaipur", "jodhpur", "jaisalmer", "udaipur", "desert"): "rajasthan_guide",
        ("italy", "cinque terre", "portofino", "riviera", "florence", "rome"): "italy_cinque_terre_guide",
        ("japan", "tokyo", "kyoto", "osaka", "fuji"): "japan_guide",
        ("packing", "luggage", "what to bring", "clothes", "pack"): "packing_tips",
        ("visa", "passport", "entry", "permit"): "visa_guide",
    }

    doc_map = {doc["id"]: doc["content"] for doc in KNOWLEDGE_DOCS}

    for keywords, doc_id in keyword_map.items():
        if any(kw in query_lower for kw in keywords):
            if doc_id in doc_map:
                relevant.append(doc_map[doc_id][:2000])
            if len(relevant) >= n_results:
                break

    if not relevant:
        relevant = [KNOWLEDGE_DOCS[0]["content"][:2000]]

    return "\n\n---\n\n".join(relevant)

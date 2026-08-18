# ============================================================
# BALANCEDBORA GRUWE-KUKU — PIG & POULTRY BOT v2.2
# Fixes: Model 404 (gemini-2.5-flash deprecated), session memory,
#        recommendation engine, no looping, local text parsing,
#        smart natural language flow, accurate least-cost LP
# ============================================================

import os
import requests
import base64
import time
import json
from functools import lru_cache
from fastapi import FastAPI, Form, Request, BackgroundTasks
from fastapi.responses import Response
from fastapi.staticfiles import StaticFiles
from twilio.rest import Client
from twilio.twiml.messaging_response import MessagingResponse
import pulp

from dotenv import load_dotenv
load_dotenv()

from google import genai

app = FastAPI(title="BalancedBora Gruwe-Kuku Bot")
os.makedirs("static", exist_ok=True)
app.mount("/static", StaticFiles(directory="static"), name="static")

# ============================================================
# CREDENTIALS
# ============================================================
TWILIO_SID = os.getenv("TWILIO_ACCOUNT_SID", "")
TWILIO_TOKEN = os.getenv("TWILIO_AUTH_TOKEN", "")
TWILIO_NUMBER = os.getenv("TWILIO_PHONE_NUMBER", "whatsapp:+254703709346")
GOOGLE_API_KEY = os.getenv("GOOGLE_VISION_API_KEY", "")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
# FIXED: gemini-2.5-flash is no longer available to new users (shut down Feb 2026).
# Use gemini-3.5-flash (GA, May 2026) or configure via env var.
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-3.5-flash")

client = Client(TWILIO_SID, TWILIO_TOKEN) if TWILIO_SID else None

# ============================================================
# GEMINI CLIENT
# ============================================================
gemini_client = None
if GEMINI_API_KEY:
    try:
        gemini_client = genai.Client(api_key=GEMINI_API_KEY)
        print(f"[GEMINI] Client initialized. Using model: {GEMINI_MODEL}")
    except Exception as e:
        print(f"[GEMINI] Init failed: {e}")

# ============================================================
# SESSIONS — now with memory
# ============================================================
user_sessions = {}

# ============================================================
# NATIVE TRANSLATION SYSTEM
# ============================================================
LANG_MAP = {'1': 'en', '2': 'sw', '3': 'ki', '4': 'mer'}

MESSAGES = {
    'en': {
        'welcome': "🐷🐔 Welcome to BalancedBora Gruwe-Kuku!\n\nI calculate the cheapest balanced ration for your pigs or chickens using NRC science.",
        'choose_language': "🌍 Choose your language:\n\n1️⃣ English\n2️⃣ Kiswahili\n3️⃣ Kikuyu\n4️⃣ Kimeru\n\nReply with 1, 2, 3, or 4.",
        'choose_species': "Step 1: Choose your animal:\n\n1️⃣ Pigs (Gruwe)\n2️⃣ Chickens (Kuku)\n\nReply with 1 or 2.",
        'choose_pig': "Step 2: Choose pig type:\n\n1️⃣ Weaner (10-20kg)\n2️⃣ Grower (20-50kg)\n3️⃣ Finisher (50-100kg)\n4️⃣ Gestating Sow\n5️⃣ Lactating Sow\n\nReply with 1-5.",
        'choose_chicken': "Step 2: Choose chicken type:\n\n1️⃣ Broiler Starter (0-3 wks)\n2️⃣ Broiler Grower (3-6 wks)\n3️⃣ Broiler Finisher (6-8 wks)\n4️⃣ Layer Starter (0-6 wks)\n5️⃣ Layer Grower (6-18 wks)\n6️⃣ Laying Hen (18+ wks)\n\nReply with 1-6.",
        'feed_selection_pig': "Step 3: Which feeds do you have?\nSend numbers separated by commas (e.g., 1,3,5,7,9):\n\nENERGY:\n1️⃣ Maize Grain (KES 30/kg)\n2️⃣ Wheat Bran (KES 20/kg)\n3️⃣ Rice Bran (KES 22/kg)\n4️⃣ Cassava Chips (KES 18/kg)\n5️⃣ Sweet Potato Vines (KES 5/kg)\n\nPROTEIN:\n6️⃣ Soybean Meal (KES 75/kg)\n7️⃣ Sunflower Cake (KES 55/kg)\n8️⃣ Cottonseed Cake (KES 60/kg)\n9️⃣ Fish Meal (KES 120/kg)\n🔟 Brewers Grains (KES 15/kg)\n\nFORAGE/ROUGHAGE:\n11️⃣ Lucerne Hay (KES 35/kg)\n12️⃣ Grass Hay (KES 10/kg)\n\nADDITIVES:\n13️⃣ Limestone (KES 15/kg)\n14️⃣ Dicalcium Phosphate (KES 80/kg)\n15️⃣ Vitamin-Mineral Premix (KES 150/kg)\n16️⃣ Salt (KES 20/kg)\n17️⃣ Lysine Supplement (KES 200/kg)\n\nTip: Include at least 1 energy + 1 protein source.",
        'feed_selection_chicken': "Step 3: Which feeds do you have?\nSend numbers separated by commas (e.g., 1,3,6,13,15):\n\nENERGY:\n1️⃣ Maize Grain (KES 30/kg)\n2️⃣ Wheat Bran (KES 20/kg)\n3️⃣ Rice Bran (KES 22/kg)\n4️⃣ Sorghum (KES 28/kg)\n5️⃣ Cassava Chips (KES 18/kg)\n\nPROTEIN:\n6️⃣ Soybean Meal (KES 75/kg)\n7️⃣ Sunflower Cake (KES 55/kg)\n8️⃣ Cottonseed Cake (KES 60/kg)\n9️⃣ Fish Meal (KES 120/kg)\n🔟 Blood Meal (KES 100/kg)\n\nMINERALS/ADDITIVES:\n11️⃣ Limestone (KES 15/kg)\n12️⃣ Dicalcium Phosphate (KES 80/kg)\n13️⃣ Oyster Shell — Layers (KES 25/kg)\n14️⃣ Vitamin-Mineral Premix (KES 150/kg)\n15️⃣ Salt (KES 20/kg)\n16️⃣ Methionine Supplement (KES 250/kg)\n17️⃣ Lysine Supplement (KES 200/kg)\n\nTip: Layers need high calcium. Broilers need high protein early.",
        'ration_optimal': "✅ Your Balanced Ration (NRC)",
        'ration_besteffort': "✅ Your Best Ration (Closest Possible)",
        'profile_label': "🐷🐔",
        'dmi_label': "📊 Daily Feed Intake",
        'total_cost_label': "💰 Total Daily Cost",
        'cost_per_kg_label': "💰 Cost per kg Feed",
        'mix_header': "MIX THESE INGREDIENTS:",
        'how_to_feed_pig': "How to feed pigs:\n1. Weigh each ingredient accurately\n2. Mix thoroughly\n3. Feed 2-3 times daily\n4. Provide fresh, clean water always\n5. For sows: adjust based on body condition",
        'how_to_feed_chicken': "How to feed chickens:\n1. Weigh and mix thoroughly\n2. Broilers: feed ad libitum (always available)\n3. Layers: 120g per hen per day\n4. Provide clean water always\n5. Keep feed dry to prevent mold",
        'start_again': "🔄 Send START for another ration.",
        'best_effort_notice': "ℹ️ Best-Effort Mode: Your feeds couldn't hit every target perfectly, so I found the closest possible mix.",
        'nutrient_low': "⚠️ {nutrient}: {actual} (target {min}-{max}) — slightly LOW",
        'nutrient_high': "⚠️ {nutrient}: {actual} (target {min}-{max}) — slightly HIGH",
        'ai_suggestions': "🤖 To improve next time, try adding:",
        'no_energy_error': "❌ Please add at least one energy source (#1-5) for growth.",
        'impossible_mins': "❌ IMPOSSIBLE: Your selected feeds must take up {total_min}%, but a ration is only 100%.\nOffenders: {offenders}\n→ Remove one or more feeds with high minimum requirements.",
        'unknown_feeds': "❌ Unknown feeds: {feeds}",
        'select_at_least_2': "Please select at least 2 feeds.\nSend numbers like 1,3,6,13,15",
        'invalid_choice': "Please send a valid number.",
        'photo_detected': "📸 I can see: {feeds}\n\nReply YES to use these, or send your own numbers.",
        'photo_not_found': "📸 I could not identify feeds in the photo.",
        'voice_soon': "🎙️ Voice notes coming soon!\n\nPlease type or send a photo.",
        'generic_help': "🐷🐔 Send START to calculate a balanced ration.",
        'yes_confirm': "Reply YES to use these, or send your own numbers.",
        'kg_day': "kg/day",
        'g_day': "g/day",
        'kes_day': "KES",
        'notes_header': "NOTES:",
        'calculating': "⏳ Calculating your cheapest balanced ration…\nPlease wait 5 seconds.",
        'supplier_header': "📦 WHERE TO BUY:",
        'supplier_item': "• {name} — {phone} ({location}) — stocks: {stock}",
        'supplier_na': "📦 Supplier info not yet loaded. Add your local agrovet contacts.",
        'recommendations_header': "📋 RECOMMENDATIONS FOR YOUR RATION:",
        'rec_energy': "⚡ You need an ENERGY source (e.g., Maize #1, Wheat Bran #2) for growth and body maintenance.",
        'rec_protein': "🥜 You need a PROTEIN source (e.g., Soybean Meal #6, Fish Meal #9) for muscle development.",
        'rec_mineral': "🦴 You need MINERALS (e.g., Limestone #11, DCP #12, Premix #14, Salt #15) for bone health and metabolism.",
        'rec_calcium_layer': "🥚 LAYERS need extra CALCIUM (Oyster Shell #13 or Limestone #11) for strong eggshells.",
        'rec_lysine_pig': "🧬 Pig weaners/growers need LYSINE (#17) for fast growth.",
        'rec_methionine_broiler': "🧬 Broilers need METHIONINE (#16) for feather and muscle growth.",
        'rec_salt': "🧂 Add SALT (#15) — essential for all animals.",
        'rec_premix': "💊 Add VITAMIN-MINERAL PREMIX (#14) — provides trace minerals and vitamins.",
        'current_selection': "You currently have: {feeds}",
        'ask_confirm_recs': "Reply YES to calculate with these feeds + my recommendations, or send MORE feed numbers to add.",
        'ask_more_feeds': "You need at least 2 feeds (1 energy + 1 protein). Please send more feed numbers.",
        'memory_greeting': "👋 Welcome back! Last time you calculated a ration for {profile} using {feeds}.\n\nSend START for a new ration, or tell me what's changed.",
        'gemini_error': "⚠️ AI helper is temporarily unavailable. Please use the menu numbers (e.g., 1,3,6) to select your feeds.",
    },
    'sw': {
        'welcome': "🐷🐔 Karibu BalancedBora Gruwe-Kuku!\n\nNakuhesabu chakula bora kwa gharama nafuu kwa nguruwe au kuku wako.",
        'choose_language': "🌍 Chagua lugha yako:\n\n1️⃣ English\n2️⃣ Kiswahili\n3️⃣ Kikuyu\n4️⃣ Kimeru\n\nJibu kwa 1, 2, 3, au 4.",
        'choose_species': "Hatua 1: Chagua mnyama wako:\n\n1️⃣ Nguruwe (Gruwe)\n2️⃣ Kuku\n\nJibu kwa 1 au 2.",
        'choose_pig': "Hatua 2: Chagua aina ya nguruwe:\n\n1️⃣ Mtoto (10-20kg)\n2️⃣ Mkubwa (20-50kg)\n3️⃣ Mwisho (50-100kg)\n4️⃣ Tumbili Mjamzito\n5️⃣ Tumbili Ananyonyesha\n\nJibu kwa 1-5.",
        'choose_chicken': "Hatua 2: Chagua aina ya kuku:\n\n1️⃣ Broiler Mwanzo (0-3 wiki)\n2️⃣ Broiler Mkubwa (3-6 wiki)\n3️⃣ Broiler Mwisho (6-8 wiki)\n4️⃣ Layer Mwanzo (0-6 wiki)\n5️⃣ Layer Mkubwa (6-18 wiki)\n6️⃣ Layer Mzima (18+ wiki)\n\nJibu kwa 1-6.",
        'feed_selection_pig': "Hatua 3: Chagua chakula ulicho nacho.\nTuma namba zikitenganishwa na koma (mfano, 1,3,5,7,9):\n\nNISHATI:\n1️⃣ Mahindi (KES 30/kg)\n2️⃣ Makapi ya Ngano (KES 20/kg)\n3️⃣ Makapi ya Mchele (KES 22/kg)\n4️⃣ Vipande vya Muhogo (KES 18/kg)\n5️⃣ Majani ya Viazi (KES 5/kg)\n\nPROTEINI:\n6️⃣ Mlo wa Soya (KES 75/kg)\n7️⃣ Keki ya Alizeti (KES 55/kg)\n8️⃣ Keki ya Pamba (KES 60/kg)\n9️⃣ Mlo wa Samaki (KES 120/kg)\n🔟 Makapi ya Bia (KES 15/kg)\n\nMAJANI:\n11️⃣ Majani ya Lucerne (KES 35/kg)\n12️⃣ Majani ya Nyasi (KES 10/kg)\n\nVITAMINI/MADINI:\n13️⃣ Mawe ya Chokaa (KES 15/kg)\n14️⃣ Dicalcium Phosphate (KES 80/kg)\n15️⃣ Premix ya Vitamin (KES 150/kg)\n16️⃣ Chumvi (KES 20/kg)\n17️⃣ Lysine (KES 200/kg)",
        'feed_selection_chicken': "Hatua 3: Chagua chakula ulicho nacho.\nTuma namba zikitenganishwa na koma (mfano, 1,3,6,13,15):\n\nNISHATI:\n1️⃣ Mahindi (KES 30/kg)\n2️⃣ Makapi ya Ngano (KES 20/kg)\n3️⃣ Makapi ya Mchele (KES 22/kg)\n4️⃣ Sorghum (KES 28/kg)\n5️⃣ Vipande vya Muhogo (KES 18/kg)\n\nPROTEINI:\n6️⃣ Mlo wa Soya (KES 75/kg)\n7️⃣ Keki ya Alizeti (KES 55/kg)\n8️⃣ Keki ya Pamba (KES 60/kg)\n9️⃣ Mlo wa Samaki (KES 120/kg)\n🔟 Mlo wa Damu (KES 100/kg)\n\nMADINI/VITAMINI:\n11️⃣ Mawe ya Chokaa (KES 15/kg)\n12️⃣ Dicalcium Phosphate (KES 80/kg)\n13️⃣ Oyster Shell — Layers (KES 25/kg)\n14️⃣ Premix ya Vitamin (KES 150/kg)\n15️⃣ Chumvi (KES 20/kg)\n16️⃣ Methionine (KES 250/kg)\n17️⃣ Lysine (KES 200/kg)",
        'ration_optimal': "✅ Chakula Chako Bora (NRC)",
        'ration_besteffort': "✅ Chakula Chako Bora Zaidi (Uwezekano wa Karibu)",
        'profile_label': "🐷🐔",
        'dmi_label': "📊 Kula Kwa Siku",
        'total_cost_label': "💰 Gharama Kuu Kwa Siku",
        'cost_per_kg_label': "💰 Gharama kwa kg",
        'mix_header': "CHANGANYA VIUNGO HIVI:",
        'how_to_feed_pig': "Jinsi ya Kulisha Nguruwe:\n1. Pima kila kiungo kwa usahihi\n2. Changanya vizuri\n3. Lisha mara 2-3 kwa siku\n4. Toa maji safi kila wakati\n5. Tumbili: rekebisha kulingana na hali ya mwili",
        'how_to_feed_chicken': "Jinsi ya Kulisha Kuku:\n1. Pima na changanya vizuri\n2. Broilers: weka chakula kila wakati\n3. Layers: gram 120 kwa kuku kwa siku\n4. Toa maji safi kila wakati\n5. Weka chakula kavu kuepuka ukojo",
        'start_again': "🔄 Tuma START kwa chakula kingine.",
        'best_effort_notice': "ℹ️ Hali Bora Zaidi: Chakula chako hakingeweza kufikia kila lengo.",
        'nutrient_low': "⚠️ {nutrient}: {actual} (lengo {min}-{max}) — CHINI kidogo",
        'nutrient_high': "⚠️ {nutrient}: {actual} (lengo {min}-{max}) — JUU kidogo",
        'ai_suggestions': "🤖 Kuboresha wakati ujao, jaribu kuongeza:",
        'no_energy_error': "❌ Tafadhali ongeza chanzo cha nishati angalau kimoja (#1-5).",
        'impossible_mins': "❌ HAIWEZEKANI: Chakula ulichochagua lazima chukue {total_min}%.\nWaliokosea: {offenders}",
        'unknown_feeds': "❌ Chakula isiyojulikana: {feeds}",
        'select_at_least_2': "Tafadhali chagua angalau chakula 2.\nTuma namba kama 1,3,6,13,15",
        'invalid_choice': "Tafadhali tuma namba sahihi.",
        'photo_detected': "📸 Naona: {feeds}\n\nJibu NDIYO kutumia hivi.",
        'photo_not_found': "📸 Sikuweza kutambua chakula katika picha.",
        'voice_soon': "🎙️ Ujumbe wa sauti utakuja hivi karibu!",
        'generic_help': "🐷🐔 Tuma START kuhesabu chakula bora.",
        'yes_confirm': "Jibu NDIYO kutumia hivi, au tuma namba zako.",
        'kg_day': "kg/siku",
        'g_day': "g/siku",
        'kes_day': "KES",
        'notes_header': "MAELEZO:",
        'calculating': "⏳ Nakuhesabu chakula bora kwa bei nafuu…\nTafadhali subiri sekunde 5.",
        'supplier_header': "📦 MAHALI PA KUNUNUA:",
        'supplier_item': "• {name} — {phone} ({location}) — {stock}",
        'supplier_na': "📦 Taarifa ya muuzaji bado haijawekwa. Ongeza mawasiliano ya agrovet yako.",
        'recommendations_header': "📋 MAPENDEKEZO KWA CHAKULA CHAKO:",
        'rec_energy': "⚡ Unahitaji chanzo cha NISHATI (k.m. Mahindi #1, Makapi ya Ngano #2) kwa ukuaji na afya ya mwili.",
        'rec_protein': "🥜 Unahitaji chanzo cha PROTEINI (k.m. Mlo wa Soya #6, Mlo wa Samaki #9) kwa misuli.",
        'rec_mineral': "🦴 Unahitaji MADINI (k.m. Mawe ya Chokaa #11, DCP #12, Premix #14, Chumvi #15) kwa mifupa na metabolism.",
        'rec_calcium_layer': "🥚 LAYERS wanahitaji CALCIUM zaidi (Oyster Shell #13 au Mawe ya Chokaa #11) kwa mayai mazuri.",
        'rec_lysine_pig': "🧬 Nguruwe wadogo/makubwa wanahitaji LYSINE (#17) kwa ukuaji wa haraka.",
        'rec_methionine_broiler': "🧬 Broilers wanahitaji METHIONINE (#16) kwa manyoya na misuli.",
        'rec_salt': "🧂 Ongeza CHUMVI (#15) — muhimu kwa wanyama wote.",
        'rec_premix': "💊 Ongeza PREMIX ya VITAMIN-MADINI (#14) — inatoa madini na vitamini vya kutosha.",
        'current_selection': "Ulichonacho sasa: {feeds}",
        'ask_confirm_recs': "Jibu NDIYO kuhesabu na chakula hiki + mapendekezo yangu, au tuma namba ZAIDI za chakula cha kuongeza.",
        'ask_more_feeds': "Unahitaji chakula angalau 2 (1 nishati + 1 proteini). Tafadhali tuma namba zaidi za chakula.",
        'memory_greeting': "👋 Karibu tena! Mara ya mwisho ulihesabu chakula kwa {profile} ukitumia {feeds}.\n\nTuma START kwa chakula kipya, au niambie kilichobadilika.",
        'gemini_error': "⚠️ Msaidizi wa AI haupo kwa sasa. Tafadhali tumia namba za menyu (k.m. 1,3,6) kuchagua chakula.",
    },
    'ki': {
        'welcome': "🐷🐔 Wî mwega BalancedBora Gruwe-Kuku!\n\nNîndîrathîrîria irio rîtheru ya nguruwe kana ngûkû.",
        'choose_language': "🌍 Thagua rurimi rwaku:\n\n1️⃣ English\n2️⃣ Kiswahili\n3️⃣ Kikuyu\n4️⃣ Kimeru\n\nCokeria na 1, 2, 3, kana 4.",
        'choose_species': "Hatua 1: Thagua nyamû:\n\n1️⃣ Nguruwe (Gruwe)\n2️⃣ Ngûkû\n\nCokeria na 1 kana 2.",
        'choose_pig': "Hatua 2: Thagua nguruwe:\n\n1️⃣ Kîhîî (10-20kg)\n2️⃣ Mûnene (20-50kg)\n3️⃣ Mûthî (50-100kg)\n4️⃣ Tumbili Mûkûrû\n5️⃣ Tumbili Kûnyonithia\n\nCokeria na 1-5.",
        'choose_chicken': "Hatua 2: Thagua ngûkû:\n\n1️⃣ Broiler Kîhîî (0-3 wiki)\n2️⃣ Broiler Mûnene (3-6 wiki)\n3️⃣ Broiler Mûthî (6-8 wiki)\n4️⃣ Layer Kîhîî (0-6 wiki)\n5️⃣ Layer Mûnene (6-18 wiki)\n6️⃣ Layer Mûkûrû (18+ wiki)\n\nCokeria na 1-6.",
        'feed_selection_pig': "Hatua 3: Thagua irio ûrî na rîo.\nTûma namba ikîmenyekanithio na koma (kûranî, 1,3,5,7,9):\n\nHOTI:\n1️⃣ Mûbî (KES 30/kg)\n2️⃣ Makapi ma Ngano (KES 20/kg)\n3️⃣ Makapi ma Mûchele (KES 22/kg)\n4️⃣ Muhogo (KES 18/kg)\n5️⃣ Majani ma Viazi (KES 5/kg)\n\nPROTEINI:\n6️⃣ Mlo wa Soya (KES 75/kg)\n7️⃣ Keki ya Alizeti (KES 55/kg)\n8️⃣ Keki ya Pamba (KES 60/kg)\n9️⃣ Mlo wa Thamaki (KES 120/kg)\n🔟 Makapi ma Bia (KES 15/kg)\n\nMAJANI:\n11️⃣ Majani ma Lucerne (KES 35/kg)\n12️⃣ Majani ma Nyasi (KES 10/kg)\n\nVITAMINI/MADINI:\n13️⃣ Mawe ma Chokaa (KES 15/kg)\n14️⃣ Dicalcium Phosphate (KES 80/kg)\n15️⃣ Premix (KES 150/kg)\n16️⃣ Chumvi (KES 20/kg)\n17️⃣ Lysine (KES 200/kg)",
        'feed_selection_chicken': "Hatua 3: Thagua irio ûrî na rîo.\nTûma namba ikîmenyekanithio na koma (kûranî, 1,3,6,13,15):\n\nHOTI:\n1️⃣ Mûbî (KES 30/kg)\n2️⃣ Makapi ma Ngano (KES 20/kg)\n3️⃣ Makapi ma Mûchele (KES 22/kg)\n4️⃣ Sorghum (KES 28/kg)\n5️⃣ Muhogo (KES 18/kg)\n\nPROTEINI:\n6️⃣ Mlo wa Soya (KES 75/kg)\n7️⃣ Keki ya Alizeti (KES 55/kg)\n8️⃣ Keki ya Pamba (KES 60/kg)\n9️⃣ Mlo wa Thamaki (KES 120/kg)\n🔟 Mlo wa Rûtî (KES 100/kg)\n\nMADINI/VITAMINI:\n11️⃣ Mawe ma Chokaa (KES 15/kg)\n12️⃣ Dicalcium Phosphate (KES 80/kg)\n13️⃣ Oyster Shell — Layers (KES 25/kg)\n14️⃣ Premix (KES 150/kg)\n15️⃣ Chumvi (KES 20/kg)\n16️⃣ Methionine (KES 250/kg)\n17️⃣ Lysine (KES 200/kg)",
        'ration_optimal': "✅ Irio Rîaku Rîtheru (NRC)",
        'ration_besteffort': "✅ Irio Rîaku Rîtheru Zaidi (Kûgîa Gûtîrî)",
        'profile_label': "🐷🐔",
        'dmi_label': "📊 Kûrîa Kwa Mûthenya",
        'total_cost_label': "💰 Bei Kuu Kwa Mûthenya",
        'cost_per_kg_label': "💰 Bei kwa kg",
        'mix_header': "CAMBANIA IRIO ICIO:",
        'how_to_feed_pig': "Uria wa Gûcambania Nguruwe:\n1. Pima kîndu o gîothe gîa kûhûthia\n2. Cambania wega\n3. He irio mara 2-3 mûthenya\n4. He maa matheru ihindî o rîa\n5. Tumbili: rîgîra kûringana na ûhooro wa mwîrî",
        'how_to_feed_chicken': "Uria wa Gûcambania Ngûkû:\n1. Pima na cambania wega\n2. Broilers: he irio ihindî o rîa\n3. Layers: gram 120 kwa ngûkû mûthenya\n4. He maa matheru ihindî o rîa\n5. Ikara irio kûkû kûhûthia ukojo",
        'start_again': "🔄 Tuma START kûgîa irio rîngî.",
        'best_effort_notice': "ℹ️ Hali Bora Zaidi: Irio rîaku rîtingîhîtie kûgîa kîndu o gîothe.",
        'nutrient_low': "⚠️ {nutrient}: {actual} (gûtîrî {min}-{max}) — CHINI hûgûrû",
        'nutrient_high': "⚠️ {nutrient}: {actual} (gûtîrî {min}-{max}) — JUU hûgûrû",
        'ai_suggestions': "🤖 Kûboresha thutha wa gûku, geria kuongeza:",
        'no_energy_error': "❌ Tafadhali ongera chanzo cha hoti (#1-5).",
        'impossible_mins': "❌ HAIWEZEKANI: Irio lazima cûkue {total_min}%.\nArîa mekosea: {offenders}",
        'unknown_feeds': "❌ Irio itarîmenyekana: {feeds}",
        'select_at_least_2': "Tafadhali thagua angalau irio 2.\nTuma namba ta 1,3,6,13,15",
        'invalid_choice': "Tafadhali tuma namba sahihi.",
        'photo_detected': "📸 Nîmona: {feeds}\n\nCokeria II.",
        'photo_not_found': "📸 Nîndîratambua irio kûranî rûtûni.",
        'voice_soon': "🎙️ Ujumbe wa mûgambo ûgûka hûgûrû!",
        'generic_help': "🐷🐔 Tuma START kûhûthia irio rîtheru.",
        'yes_confirm': "Cokeria II kûhûthia icio, kana tuma namba ciaku.",
        'kg_day': "kg/mûthenya",
        'g_day': "g/mûthenya",
        'kes_day': "KES",
        'notes_header': "MAELEZO:",
        'calculating': "⏳ Nîndîrathîrîria irio rîtheru na bei ncheene…\nTafadhali rîgîra thiguku 5.",
        'supplier_header': "📦 MAHALI PA KûGûRA:",
        'supplier_item': "• {name} — {phone} ({location}) — {stock}",
        'supplier_na': "📦 Taarifa ya mûgûrî bado ti îkî. Ongeza mawasiliano ya agrovet yaku.",
        'recommendations_header': "📋 MAENDELEZO KWA IRIO RÎAKU:",
        'rec_energy': "⚡ Wîna bata ciana cia HOTI (k.m. Mûbî #1, Makapi ma Ngano #2) kwa ukuaji na ûhooro wa mwîrî.",
        'rec_protein': "🥜 Wîna bata ciana cia PROTEINI (k.m. Mlo wa Soya #6, Mlo wa Thamaki #9) kwa misuli.",
        'rec_mineral': "🦴 Wîna bata MADINI (k.m. Mawe ma Chokaa #11, DCP #12, Premix #14, Chumvi #15) kwa mifupa.",
        'rec_calcium_layer': "🥚 LAYERS nî bata CALCIUM ingî (Oyster Shell #13 kana Mawe ma Chokaa #11) kwa mayai matheru.",
        'rec_lysine_pig': "🧬 Nguruwe nî bata LYSINE (#17) kwa ukuaji wa haraka.",
        'rec_methionine_broiler': "🧬 Broilers nî bata METHIONINE (#16) kwa manyoya na misuli.",
        'rec_salt': "🧂 Ongera CHUMVI (#15) — muhimu kwa nyamû o yothe.",
        'rec_premix': "💊 Ongera PREMIX (#14) — ina vitamini na madini.",
        'current_selection': "Wîrî na rîo: {feeds}",
        'ask_confirm_recs': "Cokeria II kûhûthia na irio icio + maendekezo makwa, kana tûma namba ingî cia irio.",
        'ask_more_feeds': "Wîna bata irio 2 (1 hoti + 1 proteini). Tafadhali tûma namba ingî cia irio.",
        'memory_greeting': "👋 Wî mwega! Mûthenya wa gûkû ûrathîrîririe irio rîtheru kwa {profile} ukitumia {feeds}.\n\nTuma START kûgîa rîngî, kana ûgîe ûrî na gûtûmîra.",
        'gemini_error': "⚠️ Mûtûngîri wa AI ndarî hûgûrû. Tafadhali tumia namba cia menyu (k.m. 1,3,6) kûthagua irio.",
    },
    'mer': {
        'welcome': "🐷🐔 Urova BalancedBora Gruwe-Kuku!\n\nNtathimana irio theru ya nguruwe kana ngûkû.",
        'choose_language': "🌍 Thagua rurimi rwaku:\n\n1️⃣ English\n2️⃣ Kiswahili\n3️⃣ Kikuyu\n4️⃣ Kimeru\n\nCokeria na 1, 2, 3, kana 4.",
        'choose_species': "Hatua 1: Thagua kiama:\n\n1️⃣ Nguruwe (Gruwe)\n2️⃣ Ngûkû\n\nCokeria na 1 kana 2.",
        'choose_pig': "Hatua 2: Thagua nguruwe:\n\n1️⃣ Kîhîî (10-20kg)\n2️⃣ Mûnene (20-50kg)\n3️⃣ Mûthî (50-100kg)\n4️⃣ Tumbili Mûkûrû\n5️⃣ Tumbili Kûnyonithia\n\nCokeria na 1-5.",
        'choose_chicken': "Hatua 2: Thagua ngûkû:\n\n1️⃣ Broiler Kîhîî (0-3 wiki)\n2️⃣ Broiler Mûnene (3-6 wiki)\n3️⃣ Broiler Mûthî (6-8 wiki)\n4️⃣ Layer Kîhîî (0-6 wiki)\n5️⃣ Layer Mûnene (6-18 wiki)\n6️⃣ Layer Mûkûrû (18+ wiki)\n\nCokeria na 1-6.",
        'feed_selection_pig': "Hatua 3: Thagua irio ûrî na rîo.\nTûma namba ikîmenyekanithio na koma (kûranî, 1,3,5,7,9):\n\nHOTI:\n1️⃣ Mûbî (KES 30/kg)\n2️⃣ Makapi ma Ngano (KES 20/kg)\n3️⃣ Makapi ma Mûchele (KES 22/kg)\n4️⃣ Muhogo (KES 18/kg)\n5️⃣ Majani ma Viazi (KES 5/kg)\n\nPROTEINI:\n6️⃣ Mlo wa Soya (KES 75/kg)\n7️⃣ Keki ya Alizeti (KES 55/kg)\n8️⃣ Keki ya Pamba (KES 60/kg)\n9️⃣ Mlo wa Thamaki (KES 120/kg)\n🔟 Makapi ma Bia (KES 15/kg)\n\nMAJANI:\n11️⃣ Majani ma Lucerne (KES 35/kg)\n12️⃣ Majani ma Nyasi (KES 10/kg)\n\nVITAMINI/MADINI:\n13️⃣ Mawe ma Chokaa (KES 15/kg)\n14️⃣ Dicalcium Phosphate (KES 80/kg)\n15️⃣ Premix (KES 150/kg)\n16️⃣ Chumvi (KES 20/kg)\n17️⃣ Lysine (KES 200/kg)",
        'feed_selection_chicken': "Hatua 3: Thagua irio ûrî na rîo.\nTûma namba ikîmenyekanithio na koma (kûranî, 1,3,6,13,15):\n\nHOTI:\n1️⃣ Mûbî (KES 30/kg)\n2️⃣ Makapi ma Ngano (KES 20/kg)\n3️⃣ Makapi ma Mûchele (KES 22/kg)\n4️⃣ Sorghum (KES 28/kg)\n5️⃣ Muhogo (KES 18/kg)\n\nPROTEINI:\n6️⃣ Mlo wa Soya (KES 75/kg)\n7️⃣ Keki ya Alizeti (KES 55/kg)\n8️⃣ Keki ya Pamba (KES 60/kg)\n9️⃣ Mlo wa Thamaki (KES 120/kg)\n🔟 Mlo wa Rûtî (KES 100/kg)\n\nMADINI/VITAMINI:\n11️⃣ Mawe ma Chokaa (KES 15/kg)\n12️⃣ Dicalcium Phosphate (KES 80/kg)\n13️⃣ Oyster Shell — Layers (KES 25/kg)\n14️⃣ Premix (KES 150/kg)\n15️⃣ Chumvi (KES 20/kg)\n16️⃣ Methionine (KES 250/kg)\n17️⃣ Lysine (KES 200/kg)",
        'ration_optimal': "✅ Irio Rîaku Rîtheru (NRC)",
        'ration_besteffort': "✅ Irio Rîaku Rîtheru Zaidi (Kûgîa Gûtîrî)",
        'profile_label': "🐷🐔",
        'dmi_label': "📊 Kûrîa Kwa Mûthenya",
        'total_cost_label': "💰 Bei Kuu Kwa Mûthenya",
        'cost_per_kg_label': "💰 Bei kwa kg",
        'mix_header': "CAMBANIA IRIO ICIO:",
        'how_to_feed_pig': "Uria wa Gûcambania Nguruwe:\n1. Pima kîndu o gîothe gîa kûhûthia\n2. Cambania wega\n3. He irio mara 2-3 mûthenya\n4. He maa matheru ihindî o rîa\n5. Tumbili: rîgîra kûringana na ûhooro wa mwîrî",
        'how_to_feed_chicken': "Uria wa Gûcambania Ngûkû:\n1. Pima na cambania wega\n2. Broilers: he irio ihindî o rîa\n3. Layers: gram 120 kwa ngûkû mûthenya\n4. He maa matheru ihindî o rîa\n5. Ikara irio kûkû kûhûthia ukojo",
        'start_again': "🔄 Tuma START kûgîa irio rîngî.",
        'best_effort_notice': "ℹ️ Hali Bora Zaidi: Irio rîaku rîtingîhîtie kûgîa kîndu o gîothe.",
        'nutrient_low': "⚠️ {nutrient}: {actual} (gûtîrî {min}-{max}) — CHINI hûgûrû",
        'nutrient_high': "⚠️ {nutrient}: {actual} (gûtîrî {min}-{max}) — JUU hûgûrû",
        'ai_suggestions': "🤖 Kûboresha thutha wa gûku, geria kuongeza:",
        'no_energy_error': "❌ Tafadhali ongera chanzo cha hoti (#1-5).",
        'impossible_mins': "❌ HAIWEZEKANI: Irio lazima cûkue {total_min}%.\nArîa mekosea: {offenders}",
        'unknown_feeds': "❌ Irio itarîmenyekana: {feeds}",
        'select_at_least_2': "Tafadhali thagua angalau irio 2.\nTuma namba ta 1,3,6,13,15",
        'invalid_choice': "Tafadhali tuma namba sahihi.",
        'photo_detected': "📸 Nîmona: {feeds}\n\nCokeria II.",
        'photo_not_found': "📸 Nîndîratambua irio kûranî rûtûni.",
        'voice_soon': "🎙️ Ujumbe wa mûgambo ûgûka hûgûrû!",
        'generic_help': "🐷🐔 Tuma START kûhûthia irio rîtheru.",
        'yes_confirm': "Cokeria II kûhûthia icio, kana tuma namba ciaku.",
        'kg_day': "kg/mûthenya",
        'g_day': "g/mûthenya",
        'kes_day': "KES",
        'notes_header': "MAELEZO:",
        'calculating': "⏳ Ntathimana irio theru na bei ncheene…\nTafadhali rîgîra thiguku 5.",
        'supplier_header': "📦 MAHALI PA KûGûRA:",
        'supplier_item': "• {name} — {phone} ({location}) — {stock}",
        'supplier_na': "📦 Taarifa ya mûgûrî bado ti îkî. Ongeza mawasiliano ya agrovet yaku.",
        'recommendations_header': "📋 MAENDELEZO KWA IRIO RÎAKU:",
        'rec_energy': "⚡ Wîna bata ciana cia HOTI (k.m. Mûbî #1, Makapi ma Ngano #2) kwa ukuaji na ûhooro wa mwîrî.",
        'rec_protein': "🥜 Wîna bata ciana cia PROTEINI (k.m. Mlo wa Soya #6, Mlo wa Thamaki #9) kwa misuli.",
        'rec_mineral': "🦴 Wîna bata MADINI (k.m. Mawe ma Chokaa #11, DCP #12, Premix #14, Chumvi #15) kwa mifupa.",
        'rec_calcium_layer': "🥚 LAYERS nî bata CALCIUM ingî (Oyster Shell #13 kana Mawe ma Chokaa #11) kwa mayai matheru.",
        'rec_lysine_pig': "🧬 Nguruwe nî bata LYSINE (#17) kwa ukuaji wa haraka.",
        'rec_methionine_broiler': "🧬 Broilers nî bata METHIONINE (#16) kwa manyoya na misuli.",
        'rec_salt': "🧂 Ongera CHUMVI (#15) — muhimu kwa nyamû o yothe.",
        'rec_premix': "💊 Ongera PREMIX (#14) — ina vitamini na madini.",
        'current_selection': "Wîrî na rîo: {feeds}",
        'ask_confirm_recs': "Cokeria II kûhûthia na irio icio + maendekezo makwa, kana tûma namba ingî cia irio.",
        'ask_more_feeds': "Wîna bata irio 2 (1 hoti + 1 proteini). Tafadhali tûma namba ingî cia irio.",
        'memory_greeting': "👋 Wî mwega! Mûthenya wa gûkû ûrathîrîririe irio rîtheru kwa {profile} ukitumia {feeds}.\n\nTuma START kûgîa rîngî, kana ûgîe ûrî na gûtûmîra.",
        'gemini_error': "⚠️ Mûtûngîri wa AI ndarî hûgûrû. Tafadhali tumia namba cia menyu (k.m. 1,3,6) kûthagua irio.",
    }
}

def get_msg(phone, key, **kwargs):
    lang = user_sessions.get(phone, {}).get('lang', 'en')
    text = MESSAGES.get(lang, MESSAGES['en']).get(key, MESSAGES['en'][key])
    if kwargs:
        try:
            text = text.format(**kwargs)
        except:
            pass
    return text


# ============================================================
# NUMBER -> FEED ID MAPPING (21 feeds)
# ============================================================
FEED_NUMBER_MAP = {
    '1': 'maize_grain', '2': 'wheat_bran', '3': 'rice_bran',
    '4': 'sorghum', '5': 'cassava_chips',
    '6': 'soybean_meal', '7': 'sunflower_cake', '8': 'cottonseed_cake',
    '9': 'fish_meal', '10': 'blood_meal',
    '11': 'limestone', '12': 'dicalcium_phosphate',
    '13': 'oyster_shell', '14': 'vitamin_mineral_premix',
    '15': 'salt', '16': 'methionine', '17': 'lysine',
    '18': 'sweet_potato_vines', '19': 'lucerne_hay', '20': 'grass_hay',
    '21': 'brewers_grains',
}

ID_TO_NUMBER = {v: k for k, v in FEED_NUMBER_MAP.items()}

# ============================================================
# COMPLETE FEED DATABASE
# ============================================================
FEEDS_DB = {
    'maize_grain': {
        'name': 'Maize Grain', 'cp': 8.5, 'me': 3.35, 'lysine': 0.25, 'ca': 0.03, 'p': 0.27,
        'cf': 2.7, 'fat': 4.0, 'ash': 1.3, 'cost_kg': 30, 'min_incl': 10, 'max_incl': 60,
        'category': 'energy', 'notes': 'Primary energy source for all species'
    },
    'wheat_bran': {
        'name': 'Wheat Bran', 'cp': 15.0, 'me': 2.60, 'lysine': 0.55, 'ca': 0.10, 'p': 0.90,
        'cf': 10.5, 'fat': 3.0, 'ash': 5.5, 'cost_kg': 20, 'min_incl': 0, 'max_incl': 25,
        'category': 'energy', 'notes': 'High fiber, good for pigs'
    },
    'rice_bran': {
        'name': 'Rice Bran', 'cp': 13.0, 'me': 2.50, 'lysine': 0.50, 'ca': 0.08, 'p': 1.40,
        'cf': 12.0, 'fat': 12.0, 'ash': 10.0, 'cost_kg': 22, 'min_incl': 0, 'max_incl': 15,
        'category': 'energy', 'notes': 'High fat, rancidity risk if old'
    },
    'sorghum': {
        'name': 'Sorghum', 'cp': 9.0, 'me': 3.20, 'lysine': 0.20, 'ca': 0.04, 'p': 0.30,
        'cf': 2.5, 'fat': 3.0, 'ash': 1.5, 'cost_kg': 28, 'min_incl': 0, 'max_incl': 40,
        'category': 'energy', 'notes': 'Good maize substitute for poultry'
    },
    'cassava_chips': {
        'name': 'Cassava Chips', 'cp': 3.0, 'me': 3.20, 'lysine': 0.10, 'ca': 0.25, 'p': 0.10,
        'cf': 4.0, 'fat': 0.5, 'ash': 2.5, 'cost_kg': 18, 'min_incl': 0, 'max_incl': 20,
        'category': 'energy', 'notes': 'High starch, must be dried (HCN risk)'
    },
    'soybean_meal': {
        'name': 'Soybean Meal', 'cp': 48.0, 'me': 3.20, 'lysine': 2.90, 'ca': 0.35, 'p': 0.70,
        'cf': 6.0, 'fat': 2.0, 'ash': 6.5, 'cost_kg': 75, 'min_incl': 5, 'max_incl': 35,
        'category': 'protein', 'notes': 'Premium protein, high lysine'
    },
    'sunflower_cake': {
        'name': 'Sunflower Cake', 'cp': 35.0, 'me': 2.20, 'lysine': 1.20, 'ca': 0.40, 'p': 1.00,
        'cf': 22.0, 'fat': 10.0, 'ash': 6.0, 'cost_kg': 55, 'min_incl': 0, 'max_incl': 20,
        'category': 'protein', 'notes': 'High fiber, moderate lysine'
    },
    'cottonseed_cake': {
        'name': 'Cottonseed Cake', 'cp': 40.0, 'me': 2.40, 'lysine': 1.50, 'ca': 0.20, 'p': 1.10,
        'cf': 18.0, 'fat': 5.0, 'ash': 6.0, 'cost_kg': 60, 'min_incl': 0, 'max_incl': 15,
        'category': 'protein', 'notes': 'GOSSYPOL: Max 15% for monogastrics'
    },
    'fish_meal': {
        'name': 'Fish Meal', 'cp': 65.0, 'me': 2.80, 'lysine': 4.50, 'ca': 5.50, 'p': 3.00,
        'cf': 1.0, 'fat': 8.0, 'ash': 18.0, 'cost_kg': 120, 'min_incl': 0, 'max_incl': 8,
        'category': 'protein', 'notes': 'Very high protein, excellent amino acid profile'
    },
    'blood_meal': {
        'name': 'Blood Meal', 'cp': 85.0, 'me': 2.50, 'lysine': 7.50, 'ca': 0.30, 'p': 0.25,
        'cf': 1.0, 'fat': 1.0, 'ash': 5.0, 'cost_kg': 100, 'min_incl': 0, 'max_incl': 4,
        'category': 'protein', 'notes': 'Very high lysine, low calcium'
    },
    'limestone': {
        'name': 'Limestone', 'cp': 0.0, 'me': 0.0, 'lysine': 0.0, 'ca': 38.0, 'p': 0.0,
        'cf': 0.0, 'fat': 0.0, 'ash': 98.0, 'cost_kg': 15, 'min_incl': 0, 'max_incl': 2,
        'category': 'mineral', 'notes': 'Calcium source for all species'
    },
    'dicalcium_phosphate': {
        'name': 'Dicalcium Phosphate', 'cp': 0.0, 'me': 0.0, 'lysine': 0.0, 'ca': 24.0, 'p': 18.5,
        'cf': 0.0, 'fat': 0.0, 'ash': 95.0, 'cost_kg': 80, 'min_incl': 0, 'max_incl': 2,
        'category': 'mineral', 'notes': 'Ca + P balanced mineral'
    },
    'oyster_shell': {
        'name': 'Oyster Shell', 'cp': 0.0, 'me': 0.0, 'lysine': 0.0, 'ca': 36.0, 'p': 0.10,
        'cf': 0.0, 'fat': 0.0, 'ash': 97.0, 'cost_kg': 25, 'min_incl': 0, 'max_incl': 8,
        'category': 'mineral', 'notes': 'Extra calcium for laying hens'
    },
    'vitamin_mineral_premix': {
        'name': 'Vitamin-Mineral Premix', 'cp': 0.0, 'me': 0.0, 'lysine': 0.0, 'ca': 8.0, 'p': 4.0,
        'cf': 0.0, 'fat': 0.0, 'ash': 90.0, 'cost_kg': 150, 'min_incl': 0.2, 'max_incl': 1.5,
        'category': 'mineral', 'notes': 'Essential vitamins and trace minerals'
    },
    'salt': {
        'name': 'Common Salt', 'cp': 0.0, 'me': 0.0, 'lysine': 0.0, 'ca': 0.0, 'p': 0.0,
        'cf': 0.0, 'fat': 0.0, 'ash': 100.0, 'cost_kg': 20, 'min_incl': 0.2, 'max_incl': 0.6,
        'category': 'mineral', 'notes': 'Sodium source, essential'
    },
    'methionine': {
        'name': 'Methionine Supplement', 'cp': 58.0, 'me': 2.00, 'lysine': 0.0, 'ca': 0.0, 'p': 0.0,
        'cf': 0.0, 'fat': 0.0, 'ash': 0.0, 'cost_kg': 250, 'min_incl': 0, 'max_incl': 0.5,
        'category': 'additive', 'notes': 'Essential amino acid for poultry'
    },
    'lysine': {
        'name': 'Lysine Supplement', 'cp': 95.0, 'me': 2.00, 'lysine': 78.0, 'ca': 0.0, 'p': 0.0,
        'cf': 0.0, 'fat': 0.0, 'ash': 0.0, 'cost_kg': 200, 'min_incl': 0, 'max_incl': 0.5,
        'category': 'additive', 'notes': 'Essential amino acid for pigs and poultry'
    },
    'sweet_potato_vines': {
        'name': 'Sweet Potato Vines', 'cp': 12.0, 'me': 1.80, 'lysine': 0.40, 'ca': 0.80, 'p': 0.25,
        'cf': 18.0, 'fat': 2.0, 'ash': 10.0, 'cost_kg': 5, 'min_incl': 0, 'max_incl': 20,
        'category': 'forage', 'notes': 'Green forage for pigs, moderate protein'
    },
    'lucerne_hay': {
        'name': 'Lucerne Hay', 'cp': 18.0, 'me': 1.80, 'lysine': 0.70, 'ca': 1.40, 'p': 0.25,
        'cf': 28.0, 'fat': 2.5, 'ash': 10.0, 'cost_kg': 35, 'min_incl': 0, 'max_incl': 15,
        'category': 'forage', 'notes': 'High protein forage'
    },
    'grass_hay': {
        'name': 'Grass Hay', 'cp': 7.0, 'me': 1.50, 'lysine': 0.20, 'ca': 0.35, 'p': 0.25,
        'cf': 32.0, 'fat': 2.0, 'ash': 8.0, 'cost_kg': 10, 'min_incl': 0, 'max_incl': 20,
        'category': 'forage', 'notes': 'Standard roughage'
    },
    'brewers_grains': {
        'name': 'Brewers Grains', 'cp': 25.0, 'me': 2.10, 'lysine': 0.80, 'ca': 0.35, 'p': 0.55,
        'cf': 18.0, 'fat': 6.0, 'ash': 4.0, 'cost_kg': 15, 'min_incl': 0, 'max_incl': 15,
        'category': 'protein', 'notes': 'Moderate protein, high fiber'
    },
}

# ============================================================
# ANIMAL PROFILES — PIGS (NRC 2012)
# ============================================================
PIG_PROFILES = {
    'p1': {
        'name': 'Pig Weaner (10-20kg)', 'dmi': 0.8,
        'cp': {'min': 18.0, 'max': 22.0}, 'me': {'min': 3.20, 'max': 3.50},
        'lysine': {'min': 1.10, 'max': 1.40}, 'ca': {'min': 0.70, 'max': 1.00},
        'p': {'min': 0.55, 'max': 0.80}, 'cf': {'min': 3.0, 'max': 6.0},
        'fat': {'min': 3.0, 'max': 8.0}, 'ash': {'min': 4.0, 'max': 8.0},
    },
    'p2': {
        'name': 'Pig Grower (20-50kg)', 'dmi': 1.8,
        'cp': {'min': 16.0, 'max': 19.0}, 'me': {'min': 3.10, 'max': 3.40},
        'lysine': {'min': 0.85, 'max': 1.10}, 'ca': {'min': 0.55, 'max': 0.80},
        'p': {'min': 0.45, 'max': 0.65}, 'cf': {'min': 4.0, 'max': 8.0},
        'fat': {'min': 3.0, 'max': 8.0}, 'ash': {'min': 4.0, 'max': 8.0},
    },
    'p3': {
        'name': 'Pig Finisher (50-100kg)', 'dmi': 2.8,
        'cp': {'min': 14.0, 'max': 16.0}, 'me': {'min': 3.00, 'max': 3.30},
        'lysine': {'min': 0.60, 'max': 0.85}, 'ca': {'min': 0.45, 'max': 0.65},
        'p': {'min': 0.35, 'max': 0.50}, 'cf': {'min': 5.0, 'max': 10.0},
        'fat': {'min': 3.0, 'max': 8.0}, 'ash': {'min': 4.0, 'max': 8.0},
    },
    'p4': {
        'name': 'Gestating Sow (150-200kg)', 'dmi': 2.2,
        'cp': {'min': 12.0, 'max': 14.0}, 'me': {'min': 2.80, 'max': 3.10},
        'lysine': {'min': 0.50, 'max': 0.70}, 'ca': {'min': 0.70, 'max': 0.90},
        'p': {'min': 0.55, 'max': 0.70}, 'cf': {'min': 6.0, 'max': 12.0},
        'fat': {'min': 3.0, 'max': 8.0}, 'ash': {'min': 4.0, 'max': 8.0},
    },
    'p5': {
        'name': 'Lactating Sow (150-200kg)', 'dmi': 5.5,
        'cp': {'min': 16.0, 'max': 18.0}, 'me': {'min': 3.10, 'max': 3.40},
        'lysine': {'min': 0.85, 'max': 1.10}, 'ca': {'min': 0.75, 'max': 1.00},
        'p': {'min': 0.60, 'max': 0.80}, 'cf': {'min': 4.0, 'max': 8.0},
        'fat': {'min': 3.0, 'max': 8.0}, 'ash': {'min': 4.0, 'max': 8.0},
    },
}

# ============================================================
# ANIMAL PROFILES — CHICKENS (NRC 1994)
# ============================================================
CHICKEN_PROFILES = {
    'c1': {
        'name': 'Broiler Starter (0-3 weeks)', 'dmi': 0.040,
        'cp': {'min': 22.0, 'max': 24.0}, 'me': {'min': 3.20, 'max': 3.40},
        'lysine': {'min': 1.10, 'max': 1.30}, 'ca': {'min': 1.00, 'max': 1.20},
        'p': {'min': 0.45, 'max': 0.55}, 'cf': {'min': 2.0, 'max': 5.0},
        'fat': {'min': 4.0, 'max': 8.0}, 'ash': {'min': 5.0, 'max': 8.0},
    },
    'c2': {
        'name': 'Broiler Grower (3-6 weeks)', 'dmi': 0.100,
        'cp': {'min': 20.0, 'max': 22.0}, 'me': {'min': 3.20, 'max': 3.40},
        'lysine': {'min': 1.00, 'max': 1.15}, 'ca': {'min': 0.90, 'max': 1.10},
        'p': {'min': 0.40, 'max': 0.50}, 'cf': {'min': 2.5, 'max': 5.5},
        'fat': {'min': 4.0, 'max': 8.0}, 'ash': {'min': 5.0, 'max': 8.0},
    },
    'c3': {
        'name': 'Broiler Finisher (6-8 weeks)', 'dmi': 0.140,
        'cp': {'min': 18.0, 'max': 20.0}, 'me': {'min': 3.20, 'max': 3.40},
        'lysine': {'min': 0.85, 'max': 1.00}, 'ca': {'min': 0.80, 'max': 1.00},
        'p': {'min': 0.35, 'max': 0.45}, 'cf': {'min': 3.0, 'max': 6.0},
        'fat': {'min': 4.0, 'max': 8.0}, 'ash': {'min': 5.0, 'max': 8.0},
    },
    'c4': {
        'name': 'Layer Starter (0-6 weeks)', 'dmi': 0.030,
        'cp': {'min': 18.0, 'max': 20.0}, 'me': {'min': 2.80, 'max': 3.00},
        'lysine': {'min': 0.85, 'max': 1.00}, 'ca': {'min': 0.90, 'max': 1.10},
        'p': {'min': 0.40, 'max': 0.50}, 'cf': {'min': 3.0, 'max': 6.0},
        'fat': {'min': 3.0, 'max': 6.0}, 'ash': {'min': 5.0, 'max': 8.0},
    },
    'c5': {
        'name': 'Layer Grower (6-18 weeks)', 'dmi': 0.070,
        'cp': {'min': 15.0, 'max': 17.0}, 'me': {'min': 2.70, 'max': 2.90},
        'lysine': {'min': 0.60, 'max': 0.75}, 'ca': {'min': 0.80, 'max': 1.00},
        'p': {'min': 0.35, 'max': 0.45}, 'cf': {'min': 4.0, 'max': 7.0},
        'fat': {'min': 3.0, 'max': 6.0}, 'ash': {'min': 5.0, 'max': 8.0},
    },
    'c6': {
        'name': 'Laying Hen (18+ weeks)', 'dmi': 0.120,
        'cp': {'min': 16.0, 'max': 18.0}, 'me': {'min': 2.70, 'max': 2.90},
        'lysine': {'min': 0.70, 'max': 0.85}, 'ca': {'min': 3.50, 'max': 4.50},
        'p': {'min': 0.30, 'max': 0.40}, 'cf': {'min': 4.0, 'max': 7.0},
        'fat': {'min': 3.0, 'max': 6.0}, 'ash': {'min': 12.0, 'max': 16.0},
    },
}

ALL_PROFILES = {**PIG_PROFILES, **CHICKEN_PROFILES}


# ============================================================
# SUPPLIER DATABASE
# ============================================================
SUPPLIERS_DB = [
    {'name': 'KALRO Naivasha', 'phone': '0722-XXX-XXX', 'location': 'Naivasha', 
     'stock': 'Maize, Soybean, Premix', 'feeds': ['maize_grain', 'soybean_meal', 'vitamin_mineral_premix']},
    {'name': 'Unga Feeds — Thika', 'phone': '0709-XXX-XXX', 'location': 'Thika',
     'stock': 'Soybean, Fish Meal, Premix', 'feeds': ['soybean_meal', 'fish_meal', 'vitamin_mineral_premix']},
    {'name': 'Agrovet Mwaura', 'phone': '0712-XXX-XXX', 'location': 'Ngong / Kiserian',
     'stock': 'Maize, Wheat Bran, Lime, DCP', 'feeds': ['maize_grain', 'wheat_bran', 'limestone', 'dicalcium_phosphate']},
    {'name': 'Bungoma Farmers Co-op', 'phone': '0733-XXX-XXX', 'location': 'Bungoma',
     'stock': 'Maize, Sunflower Cake, Cottonseed', 'feeds': ['maize_grain', 'sunflower_cake', 'cottonseed_cake']},
    {'name': 'Eldoret Grain Millers', 'phone': '0720-XXX-XXX', 'location': 'Eldoret',
     'stock': 'Maize, Wheat Bran, Rice Bran', 'feeds': ['maize_grain', 'wheat_bran', 'rice_bran']},
]

def find_suppliers_for_feeds(feed_ids):
    matched = []
    for sup in SUPPLIERS_DB:
        has_any = any(f in sup['feeds'] for f in feed_ids)
        if has_any:
            matched.append(sup)
    return matched

# ============================================================
# RECOMMENDATION ENGINE — tells farmer what's missing
# ============================================================
def analyze_feed_gaps(profile_key, selected_feed_ids):
    """Analyze selected feeds and return recommendation keys for what's missing."""
    if profile_key not in ALL_PROFILES:
        return []
    profile = ALL_PROFILES[profile_key]
    available = {fid: FEEDS_DB[fid] for fid in selected_feed_ids if fid in FEEDS_DB}
    if len(available) < 1:
        return ['rec_energy', 'rec_protein', 'rec_mineral', 'rec_salt', 'rec_premix']
    recs = []
    categories = {f['category'] for f in available.values()}
    # Check energy
    if 'energy' not in categories and 'forage' not in categories:
        recs.append('rec_energy')
    # Check protein
    if 'protein' not in categories:
        recs.append('rec_protein')
    # Check minerals
    has_ca = any(f['ca'] > 1.0 for f in available.values())
    has_p = any(f['p'] > 0.5 for f in available.values())
    has_mineral = 'mineral' in categories
    if not has_ca and not has_mineral:
        recs.append('rec_mineral')
    # Check salt
    has_salt = 'salt' in available
    if not has_salt and not has_mineral:
        recs.append('rec_salt')
    # Check premix
    has_premix = 'vitamin_mineral_premix' in available
    if not has_premix:
        recs.append('rec_premix')
    # Species-specific
    species = 'pig' if profile_key.startswith('p') else 'chicken'
    if species == 'pig' and profile_key in ['p1', 'p2']:
        has_lysine = 'lysine' in available
        if not has_lysine:
            recs.append('rec_lysine_pig')
    if species == 'chicken' and profile_key in ['c1', 'c2']:
        has_methionine = 'methionine' in available
        if not has_methionine:
            recs.append('rec_methionine_broiler')
    if profile_key == 'c6':  # Laying hen
        has_shell = 'oyster_shell' in available
        has_lime = 'limestone' in available
        if not has_shell and not has_lime:
            recs.append('rec_calcium_layer')
    return recs


def format_recommendations(phone, profile_key, selected_feed_ids):
    """Format recommendations message for the farmer."""
    m = lambda k, **kw: get_msg(phone, k, **kw)
    rec_keys = analyze_feed_gaps(profile_key, selected_feed_ids)
    if not rec_keys:
        return ""
    feed_names = [FEEDS_DB[fid]['name'] for fid in selected_feed_ids if fid in FEEDS_DB]
    msg = f"*{m('recommendations_header')}*\n"
    msg += m('current_selection', feeds=', '.join(feed_names)) + "\n\n"
    for key in rec_keys:
        msg += m(key) + "\n"
    msg += f"\n{m('ask_confirm_recs')}"
    return msg


# ============================================================
# AI SUGGESTION ENGINE
# ============================================================
class FeedSuggestionEngine:
    def __init__(self, feeds_db, profiles_db):
        self.feeds = feeds_db
        self.profiles = profiles_db
        self._compute_efficiency_scores()

    def _compute_efficiency_scores(self):
        for fid, data in self.feeds.items():
            data['efficiency'] = {}
            if data['cost_kg'] > 0:
                data['efficiency']['cp'] = data['cp'] / data['cost_kg']
                data['efficiency']['me'] = data['me'] / data['cost_kg']
                data['efficiency']['lysine'] = data['lysine'] / data['cost_kg']
                data['efficiency']['ca'] = data['ca'] / data['cost_kg']
                data['efficiency']['p'] = data['p'] / data['cost_kg']

    def suggest_for_fix(self, profile_key, current_feeds, low_nutrients, high_nutrients):
        current_ids = set(current_feeds)
        candidates = []
        for fid, data in self.feeds.items():
            if fid in current_ids:
                continue
            score = 0.0
            reasons = []
            for nutrient in low_nutrients:
                if nutrient in data and data[nutrient] > 0:
                    efficiency = data.get('efficiency', {}).get(nutrient, 0)
                    score += efficiency * 100
                    if efficiency > 0.3:
                        reasons.append(f"adds {nutrient.upper()}")
            for nutrient in high_nutrients:
                if nutrient in data and data[nutrient] < 5:
                    score += 50
                    reasons.append(f"low {nutrient.upper()}")
            current_cats = {self.feeds[f]['category'] for f in current_ids if f in self.feeds}
            if data['category'] not in current_cats:
                if data['category'] == 'protein':
                    score += 100; reasons.append("adds PROTEIN")
                elif data['category'] == 'energy':
                    score += 80; reasons.append("adds ENERGY")
                elif data['category'] == 'mineral':
                    score += 60; reasons.append("adds MINERALS")
                elif data['category'] == 'additive':
                    score += 50; reasons.append("adds AMINO ACIDS")
            if score > 0:
                candidates.append({
                    'id': fid, 'name': data['name'], 'score': score,
                    'cost': data['cost_kg'], 'category': data['category'],
                    'reasons': reasons[:2], 'notes': data['notes']
                })
        candidates.sort(key=lambda x: x['score'], reverse=True)
        return candidates[:3]

suggestion_engine = FeedSuggestionEngine(FEEDS_DB, ALL_PROFILES)


# ============================================================
# MAIN SOLVER — STRICT + BEST-EFFORT
# ============================================================
def solve_ration(profile_key, selected_feeds):
    if profile_key not in ALL_PROFILES:
        return None, f"Invalid profile: {profile_key}"
    profile = ALL_PROFILES[profile_key]
    available = {fid: FEEDS_DB[fid] for fid in selected_feeds if fid in FEEDS_DB}
    invalid = [fid for fid in selected_feeds if fid not in FEEDS_DB]
    if invalid:
        return None, f"Unknown feeds: {', '.join(invalid)}"
    if len(available) < 2:
        return None, "Please select at least 2 feeds."
    energy_count = sum(1 for f in available.values() if f['category'] == 'energy')
    if energy_count == 0:
        return None, "NO_ENERGY"
    total_min = sum(FEEDS_DB[fid]['min_incl'] for fid in selected_feeds if fid in FEEDS_DB)
    if total_min > 100:
        offenders = [FEEDS_DB[fid]['name'] + f" (min {FEEDS_DB[fid]['min_incl']}%)"
                     for fid in selected_feeds if fid in FEEDS_DB and FEEDS_DB[fid]['min_incl'] > 0]
        return None, ("IMPOSSIBLE_MINS", total_min, offenders)

    nutrients = ['cp', 'me', 'lysine', 'ca', 'p', 'cf', 'fat', 'ash']
    prob = pulp.LpProblem(f"Ration_{profile_key}", pulp.LpMinimize)
    feed_vars = pulp.LpVariable.dicts("Feed", available.keys(), lowBound=0, upBound=100)
    prob += pulp.lpSum([feed_vars[fid] * available[fid]['cost_kg'] for fid in available])
    prob += pulp.lpSum([feed_vars[fid] for fid in available]) == 100
    for nutrient in nutrients:
        if nutrient in profile:
            req = profile[nutrient]
            prob += pulp.lpSum([feed_vars[fid] * available[fid][nutrient] for fid in available]) >= req['min'] * 100
            prob += pulp.lpSum([feed_vars[fid] * available[fid][nutrient] for fid in available]) <= req['max'] * 100
    for fid, data in available.items():
        prob += feed_vars[fid] >= data['min_incl']
        prob += feed_vars[fid] <= data['max_incl']
    prob.solve(pulp.PULP_CBC_CMD(msg=0))
    strict_optimal = (pulp.LpStatus[prob.status] == 'Optimal')

    if not strict_optimal:
        prob2 = pulp.LpProblem(f"Ration_{profile_key}_besteffort", pulp.LpMinimize)
        feed_vars2 = pulp.LpVariable.dicts("FeedBE", available.keys(), lowBound=0, upBound=100)
        slack_under = {}; slack_over = {}
        for nutrient in nutrients:
            if nutrient in profile:
                slack_under[nutrient] = pulp.LpVariable(f"under_{nutrient}", lowBound=0)
                slack_over[nutrient] = pulp.LpVariable(f"over_{nutrient}", lowBound=0)
        objective = pulp.lpSum([100000 * slack_under[n] + 100000 * slack_over[n] for n in slack_under])
        objective += pulp.lpSum([feed_vars2[fid] * available[fid]['cost_kg'] for fid in available])
        prob2 += objective
        prob2 += pulp.lpSum([feed_vars2[fid] for fid in available]) == 100
        for fid, data in available.items():
            prob2 += feed_vars2[fid] >= data['min_incl']
            prob2 += feed_vars2[fid] <= data['max_incl']
        for nutrient in nutrients:
            if nutrient in profile:
                req = profile[nutrient]
                prob2 += pulp.lpSum([feed_vars2[fid] * available[fid][nutrient] for fid in available]) + slack_under[nutrient] * 100 >= req['min'] * 100
                prob2 += pulp.lpSum([feed_vars2[fid] * available[fid][nutrient] for fid in available]) - slack_over[nutrient] * 100 <= req['max'] * 100
        prob2.solve(pulp.PULP_CBC_CMD(msg=0))
        feed_vars = feed_vars2
        best_effort = True
    else:
        best_effort = False

    ration = []
    total_cost = 0
    total_nutrients = {n: 0 for n in nutrients}
    for fid in available:
        qty = feed_vars[fid].varValue
        if qty and qty > 0.05:
            cost = qty * available[fid]['cost_kg']
            total_cost += cost
            ration.append({
                'id': fid, 'name': available[fid]['name'],
                'percentage': qty,
                'kg_per_day': qty / 100 * profile['dmi'],
                'cost_per_day': cost / 100 * profile['dmi'],
                'category': available[fid]['category'],
            })
            for n in nutrients:
                total_nutrients[n] += qty * available[fid][n]
    for n in total_nutrients:
        total_nutrients[n] /= 100

    verification = {}
    low_nutrients = []; high_nutrients = []; all_ok = True
    for n in nutrients:
        if n in profile:
            actual = total_nutrients[n]
            req = profile[n]
            in_range = req['min'] <= actual <= req['max']
            if not in_range:
                all_ok = False
                if actual < req['min']: low_nutrients.append(n)
                else: high_nutrients.append(n)
            verification[n] = {
                'actual': actual, 'min': req['min'], 'max': req['max'],
                'status': '✅' if in_range else '⚠️',
                'unit': '%' if n != 'me' else 'Mcal/kg'
            }

    warnings = []
    if best_effort:
        warnings.append(('best_effort_notice', {}))
        for n in low_nutrients:
            v = verification[n]
            warnings.append(('nutrient_low', {'nutrient': n.upper(), 'actual': f"{v['actual']:.1f}{v['unit']}", 'min': f"{v['min']:.1f}", 'max': f"{v['max']:.1f}"}))
        for n in high_nutrients:
            v = verification[n]
            warnings.append(('nutrient_high', {'nutrient': n.upper(), 'actual': f"{v['actual']:.1f}{v['unit']}", 'min': f"{v['min']:.1f}", 'max': f"{v['max']:.1f}"}))
        ai_sugs = suggestion_engine.suggest_for_fix(profile_key, selected_feeds, low_nutrients, high_nutrients)
        if ai_sugs:
            warnings.append(('ai_suggestions', {}))
            for i, sug in enumerate(ai_sugs, 1):
                num = ID_TO_NUMBER.get(sug['id'], '?')
                reasons = ", ".join(sug['reasons']) if sug['reasons'] else "balanced"
                warnings.append(('ai_item', {'i': i, 'num': num, 'name': sug['name'], 'cost': sug['cost'], 'reasons': reasons}))

    result = {
        'profile': profile['name'], 'dmi': profile['dmi'],
        'total_cost_per_day': total_cost / 100 * profile['dmi'],
        'cost_per_kg_dm': total_cost / 100,
        'ration': ration, 'verification': verification,
        'best_effort': best_effort, 'warnings': warnings
    }
    return result, None


@lru_cache(maxsize=256)
def cached_solve_ration(profile_key: str, selected_feeds_tuple: tuple):
    return solve_ration(profile_key, list(selected_feeds_tuple))


# ============================================================
# IMAGE RECOGNITION (Google Vision)
# ============================================================
FEED_LABELS = {
    'maize': '1', 'corn': '1', 'grain': '1', 'cereal': '1', 'yellow': '1',
    'wheat': '2', 'bran': '2', 'rice': '3', 'sorghum': '4', 'milo': '4',
    'cassava': '5', 'manioc': '5', 'yam': '5',
    'soybean': '6', 'soya': '6', 'sunflower': '7', 'cotton': '8', 'seed': '8',
    'fish': '9', 'meal': '9', 'blood': '10', 'bone': '10',
    'limestone': '11', 'chalk': '11', 'white': '11', 'powder': '11',
    'phosphate': '12', 'dcp': '12', 'oyster': '13', 'shell': '13',
    'premix': '14', 'vitamin': '14', 'mineral': '14', 'salt': '15',
    'methionine': '16', 'lysine': '17', 'amino': '17',
    'potato': '18', 'vine': '18', 'green': '18', 'leaf': '18',
    'lucerne': '19', 'alfalfa': '19', 'grass': '20', 'hay': '20', 'fodder': '20',
    'brewer': '21', 'beer': '21', 'malt': '21',
}

def detect_feeds_from_image(image_url):
    if not GOOGLE_API_KEY:
        return None, "⚠️ Image recognition not configured."
    try:
        img_data = requests.get(image_url, timeout=10).content
        encoded = base64.b64encode(img_data).decode('utf-8')
        vision_url = f"https://vision.googleapis.com/v1/images:annotate?key={GOOGLE_API_KEY}"
        payload = {"requests": [{"image": {"content": encoded}, "features": [{"type": "LABEL_DETECTION", "maxResults": 15}]}]}
        resp = requests.post(vision_url, json=payload, timeout=15)
        result = resp.json()
        if 'error' in result:
            return None, f"Vision API error: {result['error']['message']}"
        labels = [a['description'].lower() for a in result['responses'][0].get('labelAnnotations', [])]
        detected = set()
        for label in labels:
            for keyword, feed_num in FEED_LABELS.items():
                if keyword in label:
                    detected.add(feed_num)
        return list(detected), None
    except Exception as e:
        return None, f"Image analysis failed: {str(e)}"


# ============================================================
# MESSAGE BUILDERS
# ============================================================
def format_ration(phone, result, species):
    m = lambda k, **kw: get_msg(phone, k, **kw)
    header = m('ration_besteffort') if result.get('best_effort') else m('ration_optimal')
    unit = m('g_day') if result['dmi'] < 0.5 else m('kg_day')
    dmi_display = result['dmi'] * 1000 if result['dmi'] < 0.5 else result['dmi']

    msg = (
        f"{header}\n"
        f"{m('profile_label')} {result['profile']}\n"
        f"{m('dmi_label')}: {dmi_display:.0f} {unit}\n"
        f"{m('total_cost_label')}: *{m('kes_day')} {result['total_cost_per_day']:.0f}*\n"
        f"{m('cost_per_kg_label')}: {m('kes_day')} {result['cost_per_kg_dm']:.2f}\n\n"
        f"*{m('mix_header')}*\n"
    )
    for item in result['ration']:
        qty_display = item['kg_per_day'] * 1000 if item['kg_per_day'] < 0.5 else item['kg_per_day']
        unit_item = m('g_day') if item['kg_per_day'] < 0.5 else m('kg_day')
        msg += f"• {item['name']}: {item['percentage']:.1f}% ({qty_display:.0f} {unit_item}) — {m('kes_day')} {item['cost_per_day']:.0f}\n"

    feed_key = 'how_to_feed_pig' if species == 'pig' else 'how_to_feed_chicken'
    msg += f"\n{m(feed_key)}\n"

    if result.get('warnings'):
        msg += f"\n*{m('notes_header')}*\n"
        for warn_key, warn_kwargs in result['warnings']:
            if warn_key == 'ai_item':
                msg += f"{warn_kwargs['i']}. #{warn_kwargs['num']} {warn_kwargs['name']} ({m('kes_day')} {warn_kwargs['cost']}/kg) — {warn_kwargs['reasons']}\n"
            else:
                msg += m(warn_key, **warn_kwargs) + "\n"

    msg += f"\n{m('start_again')}"
    return msg


def format_suppliers(phone, feed_ids):
    m = lambda k, **kw: get_msg(phone, k, **kw)
    suppliers = find_suppliers_for_feeds(feed_ids)
    if not suppliers:
        return f"\n\n{m('supplier_na')}"
    msg = f"\n\n*{m('supplier_header')}*\n"
    for sup in suppliers:
        msg += m('supplier_item', name=sup['name'], phone=sup['phone'], location=sup['location'], stock=sup['stock']) + "\n"
    return msg


# ============================================================
# BACKGROUND TASK
# ============================================================
def process_ration_and_reply(phone: str, profile_key: str, feed_ids: list, lang: str, species: str):
    start = time.time()
    if phone not in user_sessions:
        user_sessions[phone] = {}
    user_sessions[phone]['lang'] = lang
    result, error = cached_solve_ration(profile_key, tuple(sorted(feed_ids)))
    solve_time = (time.time() - start) * 1000
    print(f"[BG TASK] Solved ration for {phone} in {solve_time:.0f}ms")

    if error and isinstance(error, str) and error.startswith("❌"):
        reply_text = error
    elif error == "NO_ENERGY":
        reply_text = get_msg(phone, 'no_energy_error')
    elif error and isinstance(error, tuple) and error[0] == "IMPOSSIBLE_MINS":
        reply_text = get_msg(phone, 'impossible_mins', total_min=error[1], offenders=', '.join(error[2]))
    else:
        reply_text = format_ration(phone, result, species)
        reply_text += format_suppliers(phone, feed_ids)

    if client:
        try:
            client.messages.create(from_=TWILIO_NUMBER, body=reply_text, to=f"whatsapp:{phone}")
            print(f"[BG TASK] Result sent to {phone}")
        except Exception as e:
            print(f"[BG TASK] FAILED to send to {phone}: {e}")
    else:
        print(f"[BG TASK] No Twilio client, cannot send to {phone}")


# ============================================================
# GEMINI NATURAL LANGUAGE UNDERSTANDING
# ============================================================
FEED_NAME_TO_NUMBER = {
    'maize': '1', 'mahindi': '1', 'corn': '1', 'mubî': '1',
    'wheat_bran': '2', 'makapi_ya_ngano': '2', 'ngano': '2', 'bran': '2', 'wheat': '2',
    'rice_bran': '3', 'makapi_ya_mchele': '3', 'mchel': '3', 'mchele': '3', 'rice': '3',
    'sorghum': '4', 'mtama': '4',
    'cassava_chips': '5', 'muhogo': '5', 'cassava': '5', 'manioc': '5',
    'soybean_meal': '6', 'soya': '6', 'soybean': '6', 'mlo_wa_soya': '6',
    'sunflower_cake': '7', 'keki_ya_alizeti': '7', 'alizeti': '7', 'sunflower': '7',
    'cottonseed_cake': '8', 'keki_ya_pamba': '8', 'pamba': '8', 'cotton': '8',
    'fish_meal': '9', 'mlo_wa_samaki': '9', 'samaki': '9', 'mlo_wa_thamaki': '9', 'fish': '9',
    'blood_meal': '10', 'mlo_wa_damu': '10', 'damu': '10', 'mlo_wa_rutî': '10', 'blood': '10',
    'limestone': '11', 'mawe_ya_chokaa': '11', 'chokaa': '11', 'lime': '11',
    'dicalcium_phosphate': '12', 'dcp': '12', 'phosphate': '12',
    'oyster_shell': '13', 'oyster': '13', 'shell': '13',
    'vitamin_mineral_premix': '14', 'premix': '14', 'vitamin': '14', 'mineral': '14',
    'salt': '15', 'chumvi': '15',
    'methionine': '16',
    'lysine': '17',
    'sweet_potato_vines': '18', 'majani_ya_viazi': '18', 'viazi': '18', 'vines': '18',
    'lucerne_hay': '19', 'majani_ya_lucerne': '19', 'lucerne': '19', 'alfalfa': '19',
    'grass_hay': '20', 'majani_ya_nyasi': '20', 'nyasi': '20', 'grass': '20', 'hay': '20',
    'brewers_grains': '21', 'makapi_ya_bia': '21', 'bia': '21', 'brewer': '21', 'beer': '21',
}

STAGE_MAP = {
    'weaner': 'p1', 'grower': 'p2', 'finisher': 'p3',
    'gestating_sow': 'p4', 'gestating': 'p4', 'sow': 'p4', 'pregnant': 'p4',
    'lactating_sow': 'p5', 'lactating': 'p5', 'nursing': 'p5',
    'broiler_starter': 'c1', 'broiler_start': 'c1',
    'broiler_grower': 'c2',
    'broiler_finisher': 'c3', 'broiler_finish': 'c3',
    'layer_starter': 'c4', 'layer_start': 'c4',
    'layer_grower': 'c5',
    'laying_hen': 'c6', 'laying': 'c6', 'layer': 'c6', 'egg': 'c6',
}

SPECIES_MAP = {
    'pig': 'pig', 'nguruwe': 'pig', 'gruwe': 'pig', 'hog': 'pig', 'swine': 'pig',
    'chicken': 'chicken', 'kuku': 'chicken', 'nguku': 'chicken', 'hen': 'chicken', 'broiler': 'chicken', 'layer': 'chicken',
}

LANG_DETECT_MAP = {
    'sw': ['nina', 'na', 'tafadhali', 'nguruwe', 'kuku', 'mahindi', 'samaki', 'chakula', 'hatua', 'mkubwa', 'mwisho', 'mjamzito', 'ananyonyesha', 'mwanzo', 'mzima', 'kula', 'gharama', 'bei', 'siku', 'hivi', 'ndiyo', 'sawa', 'karibu', 'asante', 'hakuna', 'nipe', 'tuma', 'jibu', 'nimepata', 'vyakula', 'vyako', 'tueleze', 'tukupigie', 'hesabu'],
    'ki': ['wî', 'mwega', 'nîndî', 'rîtheru', 'nguruwe', 'ngûkû', 'mûbî', 'mûchele', 'mûthenya', 'cokeria', 'kîhîî', 'mûnene', 'mûthî', 'mûkûrû', 'kûnyonithia', 'tûma', 'thagua', 'ûrî', 'na', 'rîo', 'kûranî', 'hûgûrû', 'gûtîrî'],
    'mer': ['urova', 'ntathimana', 'theru', 'nguruwe', 'ngûkû', 'mûbî', 'mûchele', 'mûthenya', 'cokeria', 'kîhîî', 'mûnene', 'mûthî', 'mûkûrû', 'kûnyonithia', 'tûma', 'thagua', 'ûrî', 'na', 'rîo', 'kûranî', 'hûgûrû', 'gûtîrî'],
}

def detect_language(text: str) -> str:
    text_lower = text.lower()
    scores = {'en': 0, 'sw': 0, 'ki': 0, 'mer': 0}
    for lang, keywords in LANG_DETECT_MAP.items():
        for kw in keywords:
            if kw in text_lower:
                scores[lang] += 1
    best = max(scores, key=scores.get)
    return best if scores[best] > 0 else 'en'


def gemini_parse_natural_language(text: str, current_lang: str = 'en'):
    """Use Gemini to parse natural language. Returns dict or None."""
    if not gemini_client:
        return None

    prompt = f"""You are a Kenyan farming assistant parser. Extract structured data from the farmer's message.

Message: "{text}"
Current language hint: {current_lang}

Available animals: pig (nguruwe, gruwe), chicken (kuku, nguku)
Available pig stages: weaner, grower, finisher, gestating_sow, lactating_sow
Available chicken stages: broiler_starter, broiler_grower, broiler_finisher, layer_starter, layer_grower, laying_hen
Available feeds: maize, wheat_bran, rice_bran, sorghum, cassava_chips, sweet_potato_vines, soybean_meal, sunflower_cake, cottonseed_cake, fish_meal, blood_meal, brewers_grains, lucerne_hay, grass_hay, limestone, dicalcium_phosphate, oyster_shell, vitamin_mineral_premix, salt, methionine, lysine

CRITICAL RULES:
- If the message ONLY contains feed names (no animal or stage), return species=null and stage=null. Do NOT guess the animal.
- If the message contains an animal name, return the species.
- If the message contains a stage name, return the stage.
- Map common names: "mahindi"=maize, "nguruwe"=pig, "kuku"=chicken, "soya"=soybean_meal, "samaki"=fish_meal, "damu"=blood_meal, "chokaa"=limestone, "chumvi"=salt, "viazi"=sweet_potato_vines, "nyasi"=grass_hay, "bia"=brewers_grains
- If message is a greeting like "hi", "hello", "habari", intent=greeting
- If message is clearly a menu number (1, 2, 3, etc.), confidence should be LOW (<0.5)
- "ready" should be TRUE only if species, stage, AND at least 2 feeds are all provided

Respond ONLY with valid JSON:
{{
  "confidence": 0.0-1.0,
  "lang": "en|sw|ki|mer|null",
  "species": "pig|chicken|null",
  "stage": "weaner|grower|finisher|gestating_sow|lactating_sow|broiler_starter|broiler_grower|broiler_finisher|layer_starter|layer_grower|laying_hen|null",
  "feeds": ["feed_name_1", "feed_name_2"],
  "intent": "calculate_ration|greeting|help|unknown",
  "ready": false,
  "response": "A short friendly reply in the detected language. Max 400 chars."
}}"""

    try:
        response = gemini_client.models.generate_content(
            model=GEMINI_MODEL,  # FIXED: was hardcoded "gemini-2.5-flash" (deprecated)
            contents=prompt
        )
        raw = response.text.strip()
        if raw.startswith("```json"): raw = raw[7:]
        if raw.startswith("```"): raw = raw[3:]
        if raw.endswith("```"): raw = raw[:-3]
        raw = raw.strip()
        data = json.loads(raw)
        return data
    except Exception as e:
        print(f"[GEMINI] Parse error: {e}")
        return None


# ============================================================
# WEBHOOK — FIXED: No looping, smart recommendations, memory
# ============================================================
@app.post("/whatsapp")
async def whatsapp_webhook(
    request: Request,
    background_tasks: BackgroundTasks,
    Body: str = Form(default=""),
    From: str = Form(default=""),
    NumMedia: str = Form(default="0"),
    MediaUrl0: str = Form(default=""),
    MediaContentType0: str = Form(default="")
):
    """WhatsApp webhook with flexible natural-language formulation flow.

    A user can now provide animal, stage and ingredients in one message.
    The bot calculates immediately once it has a profile and >=2 feeds.
    The old recommendation -> YES -> calculate loop has been removed.
    """
    phone = From.replace("whatsapp:", "")
    text = Body.strip()
    text_lower = text.lower()
    try:
        num_media = int(NumMedia or 0)
    except (TypeError, ValueError):
        num_media = 0

    if phone not in user_sessions:
        user_sessions[phone] = {'step': -1, 'lang': 'en', 'history': []}
    session = user_sessions[phone]

    session.setdefault('step', -1)
    session.setdefault('lang', 'en')
    session.setdefault('species', None)
    session.setdefault('profile', None)
    session.setdefault('feeds', [])
    session.setdefault('recommended_feeds', [])
    session.setdefault('history', [])
    session.setdefault('ai_detected_feeds', None)

    resp = MessagingResponse()
    msg = resp.message()

    def xml_response():
        return Response(content=str(resp), media_type="application/xml")

    def parse_feed_numbers_local(raw_text: str):
        """Extract feed menu numbers and natural-language feed names locally."""
        numbers = []
        # Accept: 1,3,6 | 1 3 6 | feeds 1, 3, 6
        for token in raw_text.replace(';', ',').split(','):
            token = token.strip()
            if token in FEED_NUMBER_MAP:
                numbers.append(token)
        if not numbers:
            tokens = raw_text.lower().replace(',', ' ').replace(';', ' ').split()
            for token in tokens:
                cleaned = token.strip(".()[]{}:;!?\"")
                if cleaned in FEED_NUMBER_MAP:
                    numbers.append(cleaned)
                    continue
                if cleaned in FEED_NAME_TO_NUMBER:
                    numbers.append(FEED_NAME_TO_NUMBER[cleaned])
                    continue
                for key, num in FEED_NAME_TO_NUMBER.items():
                    if key in cleaned or cleaned in key:
                        numbers.append(num)
                        break
        return list(dict.fromkeys(numbers))

    def parse_feed_ids(raw_text: str):
        nums = parse_feed_numbers_local(raw_text)

        # Gemini only supplements local parsing when necessary.
        if not nums and gemini_client and len(raw_text) > 2:
            data = gemini_parse_natural_language(raw_text, session.get('lang', 'en'))
            if data and data.get('confidence', 0) >= 0.5:
                for feed in data.get('feeds', []) or []:
                    f = str(feed).lower().strip().replace(' ', '_')
                    if f in FEED_NAME_TO_NUMBER:
                        nums.append(FEED_NAME_TO_NUMBER[f])
                    else:
                        for key, num in FEED_NAME_TO_NUMBER.items():
                            if key in f or f in key:
                                nums.append(num)
                                break
        return list(dict.fromkeys(FEED_NUMBER_MAP[n] for n in nums if n in FEED_NUMBER_MAP))

    def detect_stage_local(raw_text: str):
        """Detect common animal-stage phrases without requiring Gemini."""
        normalized = raw_text.lower().strip().replace('-', '_')
        normalized = normalized.replace('  ', ' ')
        stage_aliases = {
            'weaner': 'p1', 'pig weaner': 'p1', 'weaner pig': 'p1',
            'grower pig': 'p2', 'pig grower': 'p2', 'finisher pig': 'p3', 'pig finisher': 'p3',
            'gestating sow': 'p4', 'pregnant sow': 'p4', 'gestating': 'p4',
            'lactating sow': 'p5', 'nursing sow': 'p5', 'lactating': 'p5',
            'broiler starter': 'c1', 'broiler start': 'c1',
            'broiler grower': 'c2', 'broiler finisher': 'c3', 'broiler finish': 'c3',
            'layer starter': 'c4', 'layer start': 'c4',
            'layer grower': 'c5', 'laying hen': 'c6', 'laying': 'c6'
        }
        # Longest phrases first so "broiler starter" wins over "starter"-like fragments.
        for phrase, profile in sorted(stage_aliases.items(), key=lambda x: len(x[0]), reverse=True):
            if phrase in normalized:
                return profile
        return None

    def apply_parsed_data(data):
        """Merge Gemini output into session without wiping existing information."""
        if not data:
            return

        detected_lang = data.get('lang')
        if detected_lang in ['en', 'sw', 'ki', 'mer']:
            session['lang'] = detected_lang

        species = data.get('species')
        stage = data.get('stage')

        if species in ['pig', 'chicken']:
            session['species'] = species

        if stage in STAGE_MAP:
            session['profile'] = STAGE_MAP[stage]
            # Keep species and profile consistent with the decoded profile.
            session['species'] = 'pig' if session['profile'].startswith('p') else 'chicken'

        parsed_feeds = []
        for feed in data.get('feeds', []) or []:
            f = str(feed).lower().strip().replace(' ', '_')
            if f in FEED_NAME_TO_NUMBER:
                parsed_feeds.append(FEED_NUMBER_MAP[FEED_NAME_TO_NUMBER[f]])
            else:
                for key, num in FEED_NAME_TO_NUMBER.items():
                    if key in f or f in key:
                        parsed_feeds.append(FEED_NUMBER_MAP[num])
                        break
        if parsed_feeds:
            session['feeds'] = list(dict.fromkeys(session.get('feeds', []) + parsed_feeds))

    def validate_and_start_calculation():
        """Start LP calculation only when the session is actually ready."""
        profile = session.get('profile')
        species = session.get('species')
        feed_ids = list(dict.fromkeys(session.get('feeds', [])))

        if not species:
            session['step'] = 1
            msg.body(get_msg(phone, 'choose_species'))
            return False

        if not profile:
            session['step'] = 2
            msg.body(get_msg(phone, 'choose_pig' if species == 'pig' else 'choose_chicken'))
            return False

        if len(feed_ids) < 2:
            session['step'] = 3
            feed_key = 'feed_selection_pig' if species == 'pig' else 'feed_selection_chicken'
            msg.body(get_msg(phone, 'ask_more_feeds') + "\n\n" + get_msg(phone, feed_key))
            return False

        available = {fid: FEEDS_DB[fid] for fid in feed_ids if fid in FEEDS_DB}
        if not available:
            session['step'] = 3
            msg.body(get_msg(phone, 'select_at_least_2'))
            return False

        if not any(f['category'] == 'energy' for f in available.values()):
            msg.body(get_msg(phone, 'no_energy_error'))
            session['step'] = 3
            return False

        total_min = sum(FEEDS_DB[fid]['min_incl'] for fid in feed_ids if fid in FEEDS_DB)
        if total_min > 100:
            offenders = [
                FEEDS_DB[fid]['name'] + f" (min {FEEDS_DB[fid]['min_incl']}%)"
                for fid in feed_ids
                if fid in FEEDS_DB and FEEDS_DB[fid]['min_incl'] > 0
            ]
            msg.body(get_msg(phone, 'impossible_mins', total_min=total_min, offenders=', '.join(offenders)))
            session['step'] = 3
            return False

        # Immediate formulation: no recommendation confirmation gate.
        session['feeds'] = feed_ids
        session['step'] = 0
        msg.body(get_msg(phone, 'calculating'))
        background_tasks.add_task(
            process_ration_and_reply,
            phone,
            profile,
            feed_ids,
            session.get('lang', 'en'),
            species
        )
        return True

    # ============================================================
    # IMAGE
    # ============================================================
    if num_media > 0 and 'image' in MediaContentType0:
        detected, error = detect_feeds_from_image(MediaUrl0)
        if error:
            msg.body(error + "\n\n" + get_msg(phone, 'generic_help'))
            return xml_response()
        if not detected:
            msg.body(get_msg(phone, 'photo_not_found') + "\n\n" + get_msg(phone, 'generic_help'))
            return xml_response()
        session['ai_detected_feeds'] = detected
        feed_names = [
            FEEDS_DB[FEED_NUMBER_MAP[n]]['name']
            for n in detected if n in FEED_NUMBER_MAP
        ]
        msg.body(get_msg(phone, 'photo_detected', feeds=', '.join(feed_names)))
        return xml_response()

    # ============================================================
    # VOICE
    # ============================================================
    if num_media > 0 and 'audio' in MediaContentType0:
        msg.body(get_msg(phone, 'voice_soon') + "\n\n" + get_msg(phone, 'generic_help'))
        return xml_response()

    # ============================================================
    # START / RESET
    # ============================================================
    if text_lower in ['start', 'mwanzo', 'anza', 'anza upya']:
        if session.get('profile') and session.get('feeds'):
            session['history'].append({
                'profile': session['profile'],
                'feeds': session['feeds'].copy(),
                'lang': session.get('lang', 'en')
            })
            session['history'] = session['history'][-3:]

        session['step'] = 1
        session['species'] = None
        session['profile'] = None
        session['feeds'] = []
        session['recommended_feeds'] = []
        session['ai_detected_feeds'] = None

        # Do not force language selection on every START. Preserve selected language.
        msg.body(get_msg(phone, 'welcome') + "\n\n" + get_msg(phone, 'choose_species'))
        return xml_response()

    # ============================================================
    # PHOTO CONFIRMATION
    # ============================================================
    if session.get('ai_detected_feeds') and text_lower in ['yes', 'yep', 'sawa', 'correct', 'ndio', 'ii', 'ndiyo']:
        detected_numbers = session.get('ai_detected_feeds') or []
        detected_ids = [FEED_NUMBER_MAP[n] for n in detected_numbers if n in FEED_NUMBER_MAP]
        session['ai_detected_feeds'] = None
        session['feeds'] = list(dict.fromkeys(session.get('feeds', []) + detected_ids))
        # Calculate immediately when animal/stage are already known; otherwise ask only for what's missing.
        if validate_and_start_calculation():
            return xml_response()
        return xml_response()

    # ============================================================
    # FIRST: UNDERSTAND COMPLETE NATURAL-LANGUAGE MESSAGES
    # This runs before the menu state, so users can skip the rigid flow.
    # ============================================================
    if len(text) > 1 and text_lower not in ['hi', 'hello', 'help', 'habari']:
        # Local feed parsing works without AI.
        local_feed_ids = parse_feed_ids(text)
        if local_feed_ids:
            session['feeds'] = list(dict.fromkeys(session.get('feeds', []) + local_feed_ids))

        # Gemini can extract animal + stage + feeds from a single sentence.
        if gemini_client and len(text) > 2:
            gemini_data = gemini_parse_natural_language(text, session.get('lang', 'en'))
            if gemini_data and gemini_data.get('confidence', 0) >= 0.5:
                apply_parsed_data(gemini_data)

        # Local stage detection makes the bot usable even when Gemini is unavailable.
        if not session.get('profile'):
            local_profile = detect_stage_local(text)
            if local_profile:
                session['profile'] = local_profile
                session['species'] = 'pig' if local_profile.startswith('p') else 'chicken'

        # Direct species keywords without Gemini.
        if not session.get('species'):
            if text_lower in ['pig', 'nguruwe', 'gruwe', 'hog', 'swine']:
                session['species'] = 'pig'
            elif text_lower in ['chicken', 'kuku', 'nguku', 'hen', 'broiler', 'layer']:
                session['species'] = 'chicken'

        # If all required inputs are now present, formulate immediately.
        if session.get('species') and session.get('profile') and len(session.get('feeds', [])) >= 2:
            validate_and_start_calculation()
            return xml_response()

    # ============================================================
    # SIMPLE MENU FLOW (kept as an easy fallback)
    # ============================================================
    if text_lower in ['hi', 'hello', 'help', '0', 'habari']:
        if not session.get('species'):
            msg.body(get_msg(phone, 'welcome') + "\n\n" + get_msg(phone, 'choose_species'))
        else:
            msg.body(get_msg(phone, 'generic_help'))
        return xml_response()

    # Language selection is retained for users who prefer the menu.
    if session['step'] == -1:
        if text_lower in LANG_MAP:
            session['lang'] = LANG_MAP[text_lower]
            session['step'] = 1
            msg.body(get_msg(phone, 'welcome') + "\n\n" + get_msg(phone, 'choose_species'))
        else:
            session['step'] = 1
            msg.body(get_msg(phone, 'welcome') + "\n\n" + get_msg(phone, 'choose_species'))
        return xml_response()

    # Step 1: species
    if session['step'] == 1:
        if text_lower == '1' or text_lower in ['pig', 'nguruwe', 'gruwe']:
            session['species'] = 'pig'
            session['step'] = 2
            msg.body(get_msg(phone, 'choose_pig'))
        elif text_lower == '2' or text_lower in ['chicken', 'kuku', 'nguku']:
            session['species'] = 'chicken'
            session['step'] = 2
            msg.body(get_msg(phone, 'choose_chicken'))
        else:
            msg.body(get_msg(phone, 'invalid_choice') + "\n\n" + get_msg(phone, 'choose_species'))
        return xml_response()

    # Step 2: animal stage/profile
    if session['step'] == 2:
        species = session.get('species', 'pig')
        valid = ['1','2','3','4','5'] if species == 'pig' else ['1','2','3','4','5','6']
        if text_lower in valid:
            prefix = 'p' if species == 'pig' else 'c'
            session['profile'] = prefix + text_lower
            session['step'] = 3
            feed_key = 'feed_selection_pig' if species == 'pig' else 'feed_selection_chicken'
            msg.body(get_msg(phone, feed_key))
            return xml_response()

        if gemini_client and len(text) > 2:
            data = gemini_parse_natural_language(text, session.get('lang', 'en'))
            if data and data.get('confidence', 0) >= 0.5:
                apply_parsed_data(data)
                if session.get('profile') and len(session.get('feeds', [])) >= 2:
                    validate_and_start_calculation()
                    return xml_response()
                if session.get('profile'):
                    session['step'] = 3
                    feed_key = 'feed_selection_pig' if species == 'pig' else 'feed_selection_chicken'
                    msg.body(get_msg(phone, feed_key))
                    return xml_response()

        msg.body(get_msg(phone, 'invalid_choice') + "\n\n" + get_msg(phone, 'choose_pig' if species == 'pig' else 'choose_chicken'))
        return xml_response()

    # Step 3: feed entry. Any valid feed list is now calculated immediately.
    if session['step'] in [3, 4, 0]:
        feed_ids = parse_feed_ids(text)
        if feed_ids:
            session['feeds'] = list(dict.fromkeys(session.get('feeds', []) + feed_ids))
            if validate_and_start_calculation():
                return xml_response()
            return xml_response()

        # Special case: if the user sends YES after a previous recommendation message,
        # retain compatibility but calculate using currently selected feeds only.
        if text_lower in ['yes', 'yep', 'sawa', 'correct', 'ndio', 'ii', 'ndiyo', 'sawa sawa']:
            if validate_and_start_calculation():
                return xml_response()

        feed_key = 'feed_selection_pig' if session.get('species') == 'pig' else 'feed_selection_chicken'
        msg.body(get_msg(phone, 'select_at_least_2') + "\n\n" + get_msg(phone, feed_key))
        return xml_response()

    # ============================================================
    # LAST-CHANCE GEMINI PARSER
    # ============================================================
    if gemini_client and len(text) > 2:
        data = gemini_parse_natural_language(text, session.get('lang', 'en'))
        if data and data.get('confidence', 0) >= 0.5:
            apply_parsed_data(data)
            if session.get('species') and session.get('profile') and len(session.get('feeds', [])) >= 2:
                validate_and_start_calculation()
                return xml_response()

    msg.body(get_msg(phone, 'generic_help'))
    return xml_response()


# ============================================================
# HEALTH CHECK
# ============================================================
@app.get("/")
def health_check():
    return {
        "status": "BalancedBora Gruwe-Kuku v2.2 is running 🐷🐔",
        "features": ["pig_profiles", "chicken_profiles", "nrc_lp", "best_effort_mode", "ai_suggestions", 
                     "image_recognition", "21_feeds", "native_translations", "background_tasks", "lru_cache", 
                     "supplier_matching", "gemini_nlp", "recommendation_engine", "session_memory",
                     "local_text_parsing", "no_looping"],
        "vision_configured": bool(GOOGLE_API_KEY),
        "gemini_configured": bool(GEMINI_API_KEY),
        "gemini_model": GEMINI_MODEL,
        "sessions": len(user_sessions),
        "cache_info": str(cached_solve_ration.cache_info())
    }


# ============================================================
# RUN
# ============================================================
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)

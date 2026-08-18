# ============================================================
# BALANCEDBORA GRUWE-KUKU — PIG & POULTRY BOT v2.2
# ============================================================

import os
import requests
import base64
import time
import json
import threading
import traceback
from functools import lru_cache
from fastapi import FastAPI, Form, Request, BackgroundTasks
from fastapi.responses import Response, PlainTextResponse
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
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.0-flash")

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
# SESSIONS
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
        'calculating': "⏳ Calculating your cheapest balanced ration…\nPlease wait ~10 seconds.",
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
        'solver_error': "❌ Something went wrong during calculation. Please try again with START.",
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
        'calculating': "⏳ Nakuhesabu chakula bora kwa bei nafuu…\nTafadhali subiri sekunde 10.",
        'supplier_header': "📦 MAHALI PA KUNUNUA:",
        'supplier_item': "• {name} — {phone} ({location}) — {stock}",
        'supplier_na': "📦 Taarifa ya muuzaji bado haijawekwa.",
        'recommendations_header': "📋 MAPENDEKEZO KWA CHAKULA CHAKO:",
        'rec_energy': "⚡ Unahitaji chanzo cha NISHATI (k.m. Mahindi #1).",
        'rec_protein': "🥜 Unahitaji chanzo cha PROTEINI (k.m. Mlo wa Soya #6).",
        'rec_mineral': "🦴 Unahitaji MADINI (k.m. Mawe ya Chokaa #11, DCP #12).",
        'rec_calcium_layer': "🥚 LAYERS wanahitaji CALCIUM zaidi (Oyster Shell #13).",
        'rec_lysine_pig': "🧬 Nguruwe wanahitaji LYSINE (#17).",
        'rec_methionine_broiler': "🧬 Broilers wanahitaji METHIONINE (#16).",
        'rec_salt': "🧂 Ongeza CHUMVI (#15).",
        'rec_premix': "💊 Ongeza PREMIX ya VITAMIN-MADINI (#14).",
        'current_selection': "Ulichonacho sasa: {feeds}",
        'ask_confirm_recs': "Jibu NDIYO kuhesabu na chakula hiki + mapendekezo, au tuma namba ZAIDI.",
        'ask_more_feeds': "Unahitaji chakula angalau 2. Tafadhali tuma namba zaidi.",
        'memory_greeting': "👋 Karibu tena! Tuma START kwa chakula kipya.",
        'gemini_error': "⚠️ Msaidizi wa AI haupo kwa sasa. Tumia namba za menyu.",
        'solver_error': "❌ Hitilafu ilitokea. Tajaribu tena na START.",
    },
    'ki': {
        'welcome': "🐷🐔 Wî mwega BalancedBora Gruwe-Kuku!\n\nNîndîrathîrîria irio rîtheru.",
        'choose_language': "🌍 Thagua rurimi rwaku:\n\n1️⃣ English\n2️⃣ Kiswahili\n3️⃣ Kikuyu\n4️⃣ Kimeru\n\nCokeria na 1, 2, 3, kana 4.",
        'choose_species': "Hatua 1: Thagua nyamû:\n\n1️⃣ Nguruwe\n2️⃣ Ngûkû\n\nCokeria na 1 kana 2.",
        'choose_pig': "Hatua 2: Thagua nguruwe:\n\n1️⃣ Kîhîî (10-20kg)\n2️⃣ Mûnene (20-50kg)\n3️⃣ Mûthî (50-100kg)\n4️⃣ Tumbili Mûkûrû\n5️⃣ Tumbili Kûnyonithia\n\nCokeria na 1-5.",
        'choose_chicken': "Hatua 2: Thagua ngûkû:\n\n1️⃣ Broiler Kîhîî\n2️⃣ Broiler Mûnene\n3️⃣ Broiler Mûthî\n4️⃣ Layer Kîhîî\n5️⃣ Layer Mûnene\n6️⃣ Layer Mûkûrû\n\nCokeria na 1-6.",
        'feed_selection_pig': "Hatua 3: Thagua irio ûrî na rîo.\nTûma namba (kûranî, 1,3,5,7,9):\n\nHOTI: 1️⃣Mûbî 2️⃣MakapiNgano 3️⃣MakapiMûchele 4️⃣Muhogo 5️⃣MajaniViazi\nPROTEINI: 6️⃣Soya 7️⃣Alizeti 8️⃣Pamba 9️⃣Thamaki 🔟Bia\nMAJANI: 11️⃣Lucerne 12️⃣Nyasi\nMADINI: 13️⃣Chokaa 14️⃣DCP 15️⃣Premix 16️⃣Chumvi 17️⃣Lysine",
        'feed_selection_chicken': "Hatua 3: Thagua irio ûrî na rîo.\nTûma namba (kûranî, 1,3,6,13,15):\n\nHOTI: 1️⃣Mûbî 2️⃣MakapiNgano 3️⃣MakapiMûchele 4️⃣Sorghum 5️⃣Muhogo\nPROTEINI: 6️⃣Soya 7️⃣Alizeti 8️⃣Pamba 9️⃣Thamaki 🔰Damu\nMADINI: 11️⃣Chokaa 12️⃣DCP 13️⃣OysterShell 14️⃣Premix 15️⃣Chumvi 16️⃣Methionine 17️⃣Lysine",
        'ration_optimal': "✅ Irio Rîtheru (NRC)",
        'ration_besteffort': "✅ Irio Rîtheru Zaidi",
        'profile_label': "🐷🐔",
        'dmi_label': "📊 Kûrîa Kwa Mûthenya",
        'total_cost_label': "💰 Bei Kuu Kwa Mûthenya",
        'cost_per_kg_label': "💰 Bei kwa kg",
        'mix_header': "CAMBANIA IRIO ICIO:",
        'how_to_feed_pig': "1. Pima kîndu o gîothe\n2. Cambania wega\n3. He irio mara 2-3 mûthenya\n4. He maa matheru",
        'how_to_feed_chicken': "1. Pima na cambania wega\n2. He irio ihindî o rîa\n3. He maa matheru",
        'start_again': "🔄 Tuma START kûgîa irio rîngî.",
        'best_effort_notice': "ℹ️ Irio rîakû rîtheru zaidi rîtingîhîtie kûgîa kîndu o gîothe.",
        'nutrient_low': "⚠️ {nutrient}: {actual} (lengo {min}-{max}) — CHINI",
        'nutrient_high': "⚠️ {nutrient}: {actual} (lengo {min}-{max}) — JUU",
        'ai_suggestions': "🤖 Kûboresha, geria kuongeza:",
        'no_energy_error': "❌ Ongea chanzo cha hoti (#1-5).",
        'impossible_mins': "❌ HAIWEZEKANI: Irio lazima cûkue {total_min}%.\n{offenders}",
        'unknown_feeds': "❌ Irio itarîmenyekana: {feeds}",
        'select_at_least_2': "Thagua angalau irio 2.\nTuma namba ta 1,3,6",
        'invalid_choice': "Tuma namba sahihi.",
        'photo_detected': "📸 Nîmona: {feeds}\n\nCokeria II.",
        'photo_not_found': "📸 Nîndîratambua irio kûranî rûtûni.",
        'voice_soon': "🎙️ Ujumbe wa mûgambo ûgûka hûgûrû!",
        'generic_help': "🐷🐔 Tuma START kûhûthia irio rîtheru.",
        'yes_confirm': "Cokeria II.",
        'kg_day': "kg/mûthenya",
        'g_day': "g/mûthenya",
        'kes_day': "KES",
        'notes_header': "MAELEZO:",
        'calculating': "⏳ Nîndîrathîrîria irio rîtheru…\nRîgîra thiguku 10.",
        'supplier_header': "📦 MAHALI PA KûGûRA:",
        'supplier_item': "• {name} — {phone} ({location}) — {stock}",
        'supplier_na': "📦 Taarifa ya mûgûrî bado ti îkî.",
        'recommendations_header': "📋 MAENDELEZO:",
        'rec_energy': "⚡ Bata HOTI (k.m. Mûbî #1).",
        'rec_protein': "🥜 Bata PROTEINI (k.m. Soya #6).",
        'rec_mineral': "🦴 Bata MADINI (k.m. Chokaa #11).",
        'rec_calcium_layer': "🥚 LAYERS bata CALCIUM (Oyster Shell #13).",
        'rec_lysine_pig': "🧬 Nguruwe bata LYSINE (#17).",
        'rec_methionine_broiler': "🧬 Broilers bata METHIONINE (#16).",
        'rec_salt': "🧂 Ongera CHUMVI (#15).",
        'rec_premix': "💊 Ongera PREMIX (#14).",
        'current_selection': "Wîrî na rîo: {feeds}",
        'ask_confirm_recs': "Cokeria II kûhûthia, kana tûma namba ingî.",
        'ask_more_feeds': "Bata irio 2. Tûma namba ingî.",
        'memory_greeting': "👋 Wî mwega! Tuma START kûgîa rîngî.",
        'gemini_error': "⚠️ AI ndarî hûgûrû. Tumia namba cia menyu.",
        'solver_error': "❌ Hitilafu. Tuma START tena.",
    },
    'mer': {
        'welcome': "🐷🐔 Urova BalancedBora Gruwe-Kuku!\n\nNtathimana irio theru.",
        'choose_language': "🌍 Thagua rurimi rwaku:\n\n1️⃣ English\n2️⃣ Kiswahili\n3️⃣ Kikuyu\n4️⃣ Kimeru\n\nCokeria na 1, 2, 3, kana 4.",
        'choose_species': "Hatua 1: Thagua kiama:\n\n1️⃣ Nguruwe\n2️⃣ Ngûkû\n\nCokeria na 1 kana 2.",
        'choose_pig': "Hatua 2: Thagua nguruwe:\n\n1️⃣ Kîhîî (10-20kg)\n2️⃣ Mûnene (20-50kg)\n3️⃣ Mûthî (50-100kg)\n4️⃣ Tumbili Mûkûrû\n5️⃣ Tumbili Kûnyonithia\n\nCokeria na 1-5.",
        'choose_chicken': "Hatua 2: Thagua ngûkû:\n\n1️⃣ Broiler Kîhîî\n2️⃣ Broiler Mûnene\n3️⃣ Broiler Mûthî\n4️⃣ Layer Kîhîî\n5️⃣ Layer Mûnene\n6️⃣ Layer Mûkûrû\n\nCokeria na 1-6.",
        'feed_selection_pig': "Hatua 3: Thagua irio ûrî na rîo.\nTûma namba (kûranî, 1,3,5,7,9):\n\nHOTI: 1️⃣Mûbî 2️⃣MakapiNgano 3️⃣MakapiMûchele 4️⃣Muhogo 5️⃣MajaniViazi\nPROTEINI: 6️⃣Soya 7️⃣Alizeti 8️⃣Pamba 9️⃣Thamaki 🔟Bia\nMAJANI: 11️⃣Lucerne 12️⃣Nyasi\nMADINI: 13️⃣Chokaa 14️⃣DCP 15️⃣Premix 16️⃣Chumvi 17️⃣Lysine",
        'feed_selection_chicken': "Hatua 3: Thagua irio ûrî na rîo.\nTûma namba (kûranî, 1,3,6,13,15):\n\nHOTI: 1️⃣Mûbî 2️⃣MakapiNgano 3️⃣MakapiMûchele 4️⃣Sorghum 5️⃣Muhogo\nPROTEINI: 6️⃣Soya 7️⃣Alizeti 8️⃣Pamba 9️⃣Thamaki 🔰Damu\nMADINI: 11️⃣Chokaa 12️⃣DCP 13️⃣OysterShell 14️⃣Premix 15️⃣Chumvi 16️⃣Methionine 17️⃣Lysine",
        'ration_optimal': "✅ Irio Rîtheru (NRC)",
        'ration_besteffort': "✅ Irio Rîtheru Zaidi",
        'profile_label': "🐷🐔",
        'dmi_label': "📊 Kûrîa Kwa Mûthenya",
        'total_cost_label': "💰 Bei Kuu Kwa Mûthenya",
        'cost_per_kg_label': "💰 Bei kwa kg",
        'mix_header': "CAMBANIA IRIO ICIO:",
        'how_to_feed_pig': "1. Pima kîndu o gîothe\n2. Cambania wega\n3. He irio mara 2-3 mûthenya\n4. He maa matheru",
        'how_to_feed_chicken': "1. Pima na cambania wega\n2. He irio ihindî o rîa\n3. He maa matheru",
        'start_again': "🔄 Tuma START kûgîa irio rîngî.",
        'best_effort_notice': "ℹ️ Irio rîakû rîtheru zaidi.",
        'nutrient_low': "⚠️ {nutrient}: {actual} (lengo {min}-{max}) — CHINI",
        'nutrient_high': "⚠️ {nutrient}: {actual} (lengo {min}-{max}) — JUU",
        'ai_suggestions': "🤖 Kûboresha, geria kuongeza:",
        'no_energy_error': "❌ Ongea chanzo cha hoti (#1-5).",
        'impossible_mins': "❌ HAIWEZEKANI: Irio lazima cûkue {total_min}%.\n{offenders}",
        'unknown_feeds': "❌ Irio itarîmenyekana: {feeds}",
        'select_at_least_2': "Thagua angalau irio 2.",
        'invalid_choice': "Tuma namba sahihi.",
        'photo_detected': "📸 Nîmona: {feeds}",
        'photo_not_found': "📸 Nîndîratambua irio.",
        'voice_soon': "🎙️ Mûgambo ûgûka hûgûrû!",
        'generic_help': "🐷🐔 Tuma START.",
        'yes_confirm': "Cokeria II.",
        'kg_day': "kg/mûthenya",
        'g_day': "g/mûthenya",
        'kes_day': "KES",
        'notes_header': "MAELEZO:",
        'calculating': "⏳ Ntathimana irio theru…\nRîgîra thiguku 10.",
        'supplier_header': "📦 MAHALI PA KûGûRA:",
        'supplier_item': "• {name} — {phone} ({location}) — {stock}",
        'supplier_na': "📦 Taarifa ya mûgûrî bado ti îkî.",
        'recommendations_header': "📋 MAENDELEZO:",
        'rec_energy': "⚡ Bata HOTI (#1).",
        'rec_protein': "🥜 Bata PROTEINI (#6).",
        'rec_mineral': "🦴 Bata MADINI (#11).",
        'rec_calcium_layer': "🥚 LAYERS bata CALCIUM (#13).",
        'rec_lysine_pig': "🧬 Nguruwe bata LYSINE (#17).",
        'rec_methionine_broiler': "🧬 Broilers bata METHIONINE (#16).",
        'rec_salt': "🧂 Ongera CHUMVI (#15).",
        'rec_premix': "💊 Ongera PREMIX (#14).",
        'current_selection': "Wîrî na rîo: {feeds}",
        'ask_confirm_recs': "Cokeria II kûhûthia.",
        'ask_more_feeds': "Bata irio 2. Tûma namba ingî.",
        'memory_greeting': "👋 Wî mwega! Tuma START.",
        'gemini_error': "⚠️ AI ndarî hûgûrû.",
        'solver_error': "❌ Hitilafu. Tuma START tena.",
    }
}

def get_msg(phone, key, /, **kwargs):
    lang = user_sessions.get(phone, {}).get('lang', 'en')
    text = MESSAGES.get(lang, MESSAGES['en']).get(key, MESSAGES['en'].get(key, f"[{key}]"))
    if kwargs:
        try:
            text = text.format(**kwargs)
        except:
            pass
    return text


# ============================================================
# NUMBER -> FEED ID MAPPING
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
        'category': 'energy', 'notes': 'Primary energy source'
    },
    'wheat_bran': {
        'name': 'Wheat Bran', 'cp': 15.0, 'me': 2.60, 'lysine': 0.55, 'ca': 0.10, 'p': 0.90,
        'cf': 10.5, 'fat': 3.0, 'ash': 5.5, 'cost_kg': 20, 'min_incl': 0, 'max_incl': 25,
        'category': 'energy', 'notes': 'High fiber'
    },
    'rice_bran': {
        'name': 'Rice Bran', 'cp': 13.0, 'me': 2.50, 'lysine': 0.50, 'ca': 0.08, 'p': 1.40,
        'cf': 12.0, 'fat': 12.0, 'ash': 10.0, 'cost_kg': 22, 'min_incl': 0, 'max_incl': 15,
        'category': 'energy', 'notes': 'High fat'
    },
    'sorghum': {
        'name': 'Sorghum', 'cp': 9.0, 'me': 3.20, 'lysine': 0.20, 'ca': 0.04, 'p': 0.30,
        'cf': 2.5, 'fat': 3.0, 'ash': 1.5, 'cost_kg': 28, 'min_incl': 0, 'max_incl': 40,
        'category': 'energy', 'notes': 'Maize substitute'
    },
    'cassava_chips': {
        'name': 'Cassava Chips', 'cp': 3.0, 'me': 3.20, 'lysine': 0.10, 'ca': 0.25, 'p': 0.10,
        'cf': 4.0, 'fat': 0.5, 'ash': 2.5, 'cost_kg': 18, 'min_incl': 0, 'max_incl': 20,
        'category': 'energy', 'notes': 'High starch'
    },
    'soybean_meal': {
        'name': 'Soybean Meal', 'cp': 48.0, 'me': 3.20, 'lysine': 2.90, 'ca': 0.35, 'p': 0.70,
        'cf': 6.0, 'fat': 2.0, 'ash': 6.5, 'cost_kg': 75, 'min_incl': 5, 'max_incl': 35,
        'category': 'protein', 'notes': 'Premium protein'
    },
    'sunflower_cake': {
        'name': 'Sunflower Cake', 'cp': 35.0, 'me': 2.20, 'lysine': 1.20, 'ca': 0.40, 'p': 1.00,
        'cf': 22.0, 'fat': 10.0, 'ash': 6.0, 'cost_kg': 55, 'min_incl': 0, 'max_incl': 20,
        'category': 'protein', 'notes': 'High fiber'
    },
    'cottonseed_cake': {
        'name': 'Cottonseed Cake', 'cp': 40.0, 'me': 2.40, 'lysine': 1.50, 'ca': 0.20, 'p': 1.10,
        'cf': 18.0, 'fat': 5.0, 'ash': 6.0, 'cost_kg': 60, 'min_incl': 0, 'max_incl': 15,
        'category': 'protein', 'notes': 'Max 15% gossypol'
    },
    'fish_meal': {
        'name': 'Fish Meal', 'cp': 65.0, 'me': 2.80, 'lysine': 4.50, 'ca': 5.50, 'p': 3.00,
        'cf': 1.0, 'fat': 8.0, 'ash': 18.0, 'cost_kg': 120, 'min_incl': 0, 'max_incl': 8,
        'category': 'protein', 'notes': 'Very high protein'
    },
    'blood_meal': {
        'name': 'Blood Meal', 'cp': 85.0, 'me': 2.50, 'lysine': 7.50, 'ca': 0.30, 'p': 0.25,
        'cf': 1.0, 'fat': 1.0, 'ash': 5.0, 'cost_kg': 100, 'min_incl': 0, 'max_incl': 4,
        'category': 'protein', 'notes': 'Very high lysine'
    },
    'limestone': {
        'name': 'Limestone', 'cp': 0.0, 'me': 0.0, 'lysine': 0.0, 'ca': 38.0, 'p': 0.0,
        'cf': 0.0, 'fat': 0.0, 'ash': 98.0, 'cost_kg': 15, 'min_incl': 0, 'max_incl': 2,
        'category': 'mineral', 'notes': 'Calcium source'
    },
    'dicalcium_phosphate': {
        'name': 'Dicalcium Phosphate', 'cp': 0.0, 'me': 0.0, 'lysine': 0.0, 'ca': 24.0, 'p': 18.5,
        'cf': 0.0, 'fat': 0.0, 'ash': 95.0, 'cost_kg': 80, 'min_incl': 0, 'max_incl': 2,
        'category': 'mineral', 'notes': 'Ca + P balanced'
    },
    'oyster_shell': {
        'name': 'Oyster Shell', 'cp': 0.0, 'me': 0.0, 'lysine': 0.0, 'ca': 36.0, 'p': 0.10,
        'cf': 0.0, 'fat': 0.0, 'ash': 97.0, 'cost_kg': 25, 'min_incl': 0, 'max_incl': 8,
        'category': 'mineral', 'notes': 'Extra calcium for layers'
    },
    'vitamin_mineral_premix': {
        'name': 'Vitamin-Mineral Premix', 'cp': 0.0, 'me': 0.0, 'lysine': 0.0, 'ca': 8.0, 'p': 4.0,
        'cf': 0.0, 'fat': 0.0, 'ash': 90.0, 'cost_kg': 150, 'min_incl': 0.2, 'max_incl': 1.5,
        'category': 'mineral', 'notes': 'Vitamins and trace minerals'
    },
    'salt': {
        'name': 'Common Salt', 'cp': 0.0, 'me': 0.0, 'lysine': 0.0, 'ca': 0.0, 'p': 0.0,
        'cf': 0.0, 'fat': 0.0, 'ash': 100.0, 'cost_kg': 20, 'min_incl': 0.2, 'max_incl': 0.6,
        'category': 'mineral', 'notes': 'Sodium source'
    },
    'methionine': {
        'name': 'Methionine Supplement', 'cp': 58.0, 'me': 2.00, 'lysine': 0.0, 'ca': 0.0, 'p': 0.0,
        'cf': 0.0, 'fat': 0.0, 'ash': 0.0, 'cost_kg': 250, 'min_incl': 0, 'max_incl': 0.5,
        'category': 'additive', 'notes': 'Essential AA for poultry'
    },
    'lysine': {
        'name': 'Lysine Supplement', 'cp': 95.0, 'me': 2.00, 'lysine': 78.0, 'ca': 0.0, 'p': 0.0,
        'cf': 0.0, 'fat': 0.0, 'ash': 0.0, 'cost_kg': 200, 'min_incl': 0, 'max_incl': 0.5,
        'category': 'additive', 'notes': 'Essential AA for pigs'
    },
    'sweet_potato_vines': {
        'name': 'Sweet Potato Vines', 'cp': 12.0, 'me': 1.80, 'lysine': 0.40, 'ca': 0.80, 'p': 0.25,
        'cf': 18.0, 'fat': 2.0, 'ash': 10.0, 'cost_kg': 5, 'min_incl': 0, 'max_incl': 20,
        'category': 'forage', 'notes': 'Green forage for pigs'
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
# ANIMAL PROFILES — PIGS
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
# ANIMAL PROFILES — CHICKENS
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
        if any(f in sup['feeds'] for f in feed_ids):
            matched.append(sup)
    return matched


# ============================================================
# RECOMMENDATION ENGINE
# ============================================================
def analyze_feed_gaps(profile_key, selected_feed_ids):
    if profile_key not in ALL_PROFILES:
        return []
    profile = ALL_PROFILES[profile_key]
    available = {fid: FEEDS_DB[fid] for fid in selected_feed_ids if fid in FEEDS_DB}
    if len(available) < 1:
        return ['rec_energy', 'rec_protein', 'rec_mineral', 'rec_salt', 'rec_premix']
    recs = []
    categories = {f['category'] for f in available.values()}
    if 'energy' not in categories and 'forage' not in categories:
        recs.append('rec_energy')
    if 'protein' not in categories:
        recs.append('rec_protein')
    has_ca = any(f['ca'] > 1.0 for f in available.values())
    has_mineral = 'mineral' in categories
    if not has_ca and not has_mineral:
        recs.append('rec_mineral')
    if 'salt' not in available and not has_mineral:
        recs.append('rec_salt')
    if 'vitamin_mineral_premix' not in available:
        recs.append('rec_premix')
    species = 'pig' if profile_key.startswith('p') else 'chicken'
    if species == 'pig' and profile_key in ['p1', 'p2']:
        if 'lysine' not in available:
            recs.append('rec_lysine_pig')
    if species == 'chicken' and profile_key in ['c1', 'c2']:
        if 'methionine' not in available:
            recs.append('rec_methionine_broiler')
    if profile_key == 'c6':
        if 'oyster_shell' not in available and 'limestone' not in available:
            recs.append('rec_calcium_layer')
    return recs


def format_recommendations(phone, profile_key, selected_feed_ids):
    rec_keys = analyze_feed_gaps(profile_key, selected_feed_ids)
    if not rec_keys:
        return ""
    feed_names = [FEEDS_DB[fid]['name'] for fid in selected_feed_ids if fid in FEEDS_DB]
    msg = f"*{get_msg(phone, 'recommendations_header')}*\n"
    msg += get_msg(phone, 'current_selection', feeds=', '.join(feed_names)) + "\n\n"
    for key in rec_keys:
        msg += get_msg(phone, key) + "\n"
    msg += f"\n{get_msg(phone, 'ask_confirm_recs')}"
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
                for n in ['cp', 'me', 'lysine', 'ca', 'p']:
                    data['efficiency'][n] = data[n] / data['cost_kg']

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
                cat_scores = {'protein': 100, 'energy': 80, 'mineral': 60, 'additive': 50, 'forage': 30}
                score += cat_scores.get(data['category'], 20)
                reasons.append(f"adds {data['category'].upper()}")
            if score > 0:
                candidates.append({
                    'id': fid, 'name': data['name'], 'score': score,
                    'cost': data['cost_kg'], 'category': data['category'],
                    'reasons': reasons[:2]
                })
        candidates.sort(key=lambda x: x['score'], reverse=True)
        return candidates[:3]

suggestion_engine = FeedSuggestionEngine(FEEDS_DB, ALL_PROFILES)


# ============================================================
# MAIN SOLVER — STRICT + BEST-EFFORT  (THIS WAS TRUNCATED BEFORE)
# ============================================================
NUTRIENT_LABELS = {
    'cp': 'Crude Protein %', 'me': 'ME (Mcal/kg)', 'lysine': 'Lysine %',
    'ca': 'Calcium %', 'p': 'Phosphorus %', 'cf': 'Crude Fiber %',
    'fat': 'Fat %', 'ash': 'Ash %'
}

def solve_ration(profile_key, selected_feeds):
    """Returns (result_dict, error_string_or_None)"""
    if profile_key not in ALL_PROFILES:
        return None, f"Invalid profile: {profile_key}"

    profile = ALL_PROFILES[profile_key]
    available = {fid: FEEDS_DB[fid] for fid in selected_feeds if fid in FEEDS_DB}
    invalid = [fid for fid in selected_feeds if fid not in FEEDS_DB]
    if invalid:
        return None, f"Unknown feeds: {', '.join(invalid)}"
    if len(available) < 2:
        return None, "LESS_THAN_2"

    energy_count = sum(1 for f in available.values() if f['category'] == 'energy')
    if energy_count == 0:
        return None, "NO_ENERGY"

    total_min = sum(FEEDS_DB[fid]['min_incl'] for fid in selected_feeds if fid in FEEDS_DB)
    if total_min > 100:
        offenders = [FEEDS_DB[fid]['name'] + f" (min {FEEDS_DB[fid]['min_incl']}%)"
                     for fid in selected_feeds if fid in FEEDS_DB and FEEDS_DB[fid]['min_incl'] > 0]
        return None, ("IMPOSSIBLE_MINS", total_min, offenders)

    nutrients = ['cp', 'me', 'lysine', 'ca', 'p', 'cf', 'fat', 'ash']

    # --- TRY STRICT SOLVE FIRST ---
    prob = pulp.LpProblem(f"Ration_{profile_key}", pulp.LpMinimize)
    feed_vars = pulp.LpVariable.dicts("F", available.keys(), lowBound=0, upBound=100)
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

    prob.solve(pulp.PULP_CBC_CMD(msg=0, timeLimit=30))
    strict_optimal = (pulp.LpStatus[prob.status] == 'Optimal')

    # --- BEST-EFFORT FALLBACK ---
    if not strict_optimal:
        prob2 = pulp.LpProblem(f"Ration_{profile_key}_be", pulp.LpMinimize)
        fv2 = pulp.LpVariable.dicts("FBE", available.keys(), lowBound=0, upBound=100)
        slack_under = {}
        slack_over = {}
        for nutrient in nutrients:
            if nutrient in profile:
                slack_under[nutrient] = pulp.LpVariable(f"su_{nutrient}", lowBound=0)
                slack_over[nutrient] = pulp.LpVariable(f"so_{nutrient}", lowBound=0)
        objective = pulp.lpSum([100000 * slack_under[n] + 100000 * slack_over[n] for n in slack_under])
        objective += pulp.lpSum([fv2[fid] * available[fid]['cost_kg'] for fid in available])
        prob2 += objective
        prob2 += pulp.lpSum([fv2[fid] for fid in available]) == 100
        for fid, data in available.items():
            prob2 += fv2[fid] >= data['min_incl']
            prob2 += fv2[fid] <= data['max_incl']
        for nutrient in nutrients:
            if nutrient in profile:
                req = profile[nutrient]
                prob2 += (pulp.lpSum([fv2[fid] * available[fid][nutrient] for fid in available])
                          + slack_under[nutrient] * 100 >= req['min'] * 100)
                prob2 += (pulp.lpSum([fv2[fid] * available[fid][nutrient] for fid in available])
                          - slack_over[nutrient] * 100 <= req['max'] * 100)
        prob2.solve(pulp.PULP_CBC_CMD(msg=0, timeLimit=30))
        feed_vars = fv2
        best_effort = True
    else:
        best_effort = False

    # --- BUILD RESULT ---
    ration = []
    total_cost = 0
    total_nutrients = {n: 0.0 for n in nutrients}

    for fid in available:
        qty = feed_vars[fid].varValue
        if qty is None:
            qty = 0.0
        if qty > 0.01:
            cost = qty * available[fid]['cost_kg']
            total_cost += cost
            ration.append({
                'id': fid,
                'name': available[fid]['name'],
                'percentage': round(qty, 2),
                'kg_per_day': round(qty / 100 * profile['dmi'], 4),
                'cost_per_day': round(cost / 100 * profile['dmi'], 2),
                'category': available[fid]['category'],
            })
            for n in nutrients:
                total_nutrients[n] += qty * available[fid][n]

    # Normalize to 100%
    total_pct = sum(r['percentage'] for r in ration)
    if total_pct > 0 and abs(total_pct - 100) > 0.1:
        for r in ration:
            r['percentage'] = round(r['percentage'] / total_pct * 100, 2)
            r['kg_per_day'] = round(r['percentage'] / 100 * profile['dmi'], 4)
            r['cost_per_day'] = round(r['percentage'] / 100 * profile['dmi'] * available[r['id']]['cost_kg'], 2)
        # Recalculate total cost
        total_cost = sum(r['cost_per_day'] for r in ration)
        # Recalculate nutrients
        total_nutrients = {n: 0.0 for n in nutrients}
        for r in ration:
            fid = r['id']
            pct = r['percentage']
            for n in nutrients:
                total_nutrients[n] += pct * available[fid][n]

    # Analyze deviations for best-effort
    deviations = []
    low_nutrients = []
    high_nutrients = []
    if best_effort:
        for n in nutrients:
            if n in profile:
                actual = total_nutrients[n] / 100 if total_pct > 0 else 0
                req = profile[n]
                if actual < req['min']:
                    deviations.append(('low', n, actual, req['min'], req['max']))
                    low_nutrients.append(n)
                elif actual > req['max']:
                    deviations.append(('high', n, actual, req['min'], req['max']))
                    high_nutrients.append(n)

    # Get AI suggestions for best-effort
    ai_suggestions = []
    if best_effort and (low_nutrients or high_nutrients):
        ai_suggestions = suggestion_engine.suggest_for_fix(
            profile_key, list(available.keys()), low_nutrients, high_nutrients
        )

    # Suppliers
    feed_ids_in_ration = [r['id'] for r in ration]
    suppliers = find_suppliers_for_feeds(feed_ids_in_ration)

    return {
        'profile_name': profile['name'],
        'profile_key': profile_key,
        'dmi': profile['dmi'],
        'ration': ration,
        'total_cost_per_day': round(total_cost / 100 * profile['dmi'], 2) if not best_effort else round(sum(r['cost_per_day'] for r in ration), 2),
        'cost_per_kg': round(total_cost, 2) if not best_effort else round(sum(r['percentage'] * FEEDS_DB[r['id']]['cost_kg'] for r in ration) / 100, 2),
        'total_nutrients': {n: round(v / 100, 2) for n, v in total_nutrients.items()} if not best_effort else {n: round(v / 100, 2) for n, v in total_nutrients.items()},
        'best_effort': best_effort,
        'deviations': deviations,
        'ai_suggestions': ai_suggestions,
        'suppliers': suppliers,
        'species': 'pig' if profile_key.startswith('p') else 'chicken',
    }, None


# ============================================================
# FORMAT RATION FOR WHATSAPP
# ============================================================
def format_ration_message(phone, result):
    """Format the solved ration into a WhatsApp-friendly message."""
    m = lambda k, **kw: get_msg(phone, k, **kw)
    species = result['species']

    # Header
    header_key = 'ration_besteffort' if result['best_effort'] else 'ration_optimal'
    msg = f"*{m(header_key)}*\n"
    msg += f"{m('profile_label')} {result['profile_name']}\n\n"

    # Mix
    msg += f"*{m('mix_header')}*\n"
    for r in result['ration']:
        num = ID_TO_NUMBER.get(r['id'], '?')
        if result['dmi'] >= 1:
            msg += f"  {num}️⃣ {r['name']}: *{r['percentage']}%* → {r['kg_per_day']}kg/{m('kg_day').replace('kg/','').replace('day','')}\n"
        else:
            g = round(r['kg_per_day'] * 1000, 1)
            msg += f"  {num}️⃣ {r['name']}: *{r['percentage']}%* → {g}g/{m('g_day').replace('g/','').replace('day','')}\n"
    msg += "\n"

    # Costs
    msg += f"{m('dmi_label')}: {result['dmi']}kg\n" if result['dmi'] >= 0.1 else f"{m('dmi_label')}: {round(result['dmi']*1000)}g\n"
    msg += f"{m('cost_per_kg_label')}: KES {result['cost_per_kg']}\n"
    msg += f"{m('total_cost_label')}: KES {result['total_cost_per_day']}\n\n"

    # Nutrient table
    msg += f"*{m('notes_header')}*\n"
    for n, label in NUTRIENT_LABELS.items():
        actual = result['total_nutrients'].get(n, 0)
        if n in ALL_PROFILES[result['profile_key']]:
            req = ALL_PROFILES[result['profile_key']][n]
            marker = "✅" if req['min'] <= actual <= req['max'] else "⚠️"
            msg += f"  {marker} {label}: {actual}% (target {req['min']}-{req['max']}%)\n"
    msg += "\n"

    # Best-effort warnings
    if result['best_effort']:
        msg += f"{m('best_effort_notice')}\n\n"
        for dev_type, n, actual, nmin, nmax in result['deviations']:
            label = NUTRIENT_LABELS.get(n, n)
            if dev_type == 'low':
                msg += m('nutrient_low', nutrient=label, actual=f"{actual:.2f}%", min=nmin, max=nmax) + "\n"
            else:
                msg += m('nutrient_high', nutrient=label, actual=f"{actual:.2f}%", min=nmin, max=nmax) + "\n"
        msg += "\n"

    # AI suggestions
    if result.get('ai_suggestions'):
        msg += f"*{m('ai_suggestions')}*\n"
        for s in result['ai_suggestions']:
            num = ID_TO_NUMBER.get(s['id'], '?')
            msg += f"  • #{num} {s['name']} (KES {s['cost']}/kg) — {', '.join(s['reasons'])}\n"
        msg += "\n"

    # Suppliers
    if result.get('suppliers'):
        msg += f"*{m('supplier_header')}*\n"
        for sup in result['suppliers']:
            msg += m('supplier_item', name=sup['name'], phone=sup['phone'],
                     location=sup['location'], stock=sup['stock']) + "\n"
    else:
        msg += m('supplier_na') + "\n"

    msg += "\n"

    # Feeding instructions
    if species == 'pig':
        msg += m('how_to_feed_pig')
    else:
        msg += m('how_to_feed_chicken')

    msg += f"\n\n{m('start_again')}"

    return msg


# ============================================================
# SEND WHATSAPP MESSAGE (for background results)
# ============================================================
def send_whatsapp_message(to_number, body):
    """Send a message via Twilio REST API (not TwiML)."""
    if not client:
        print(f"[TWILIO] No client configured, would send to {to_number}: {body[:100]}...")
        return
    try:
        message = client.messages.create(
            from_=TWILIO_NUMBER,
            body=body,
            to=to_number
        )
        print(f"[TWILIO] Sent message SID: {message.sid}")
    except Exception as e:
        print(f"[TWILIO] Send error: {e}")


# ============================================================
# BACKGROUND CALCULATION TASK
# ============================================================
def run_calculation_and_send(phone, profile_key, feed_ids, recommended_ids=None):
    """Run LP solver in background, then send result via Twilio REST API."""
    all_feeds = list(feed_ids)
    if recommended_ids:
        for fid in recommended_ids:
            if fid not in all_feeds:
                all_feeds.append(fid)

    try:
        print(f"[SOLVER] Starting for {phone}: profile={profile_key}, feeds={all_feeds}")
        result, error = solve_ration(profile_key, all_feeds)

        if error:
            print(f"[SOLVER] Error: {error}")
            if error == "NO_ENERGY":
                send_whatsapp_message(phone, get_msg(phone, 'no_energy_error'))
            elif error == "LESS_THAN_2":
                send_whatsapp_message(phone, get_msg(phone, 'select_at_least_2'))
            elif isinstance(error, tuple) and error[0] == "IMPOSSIBLE_MINS":
                send_whatsapp_message(phone, get_msg(phone, 'impossible_mins',
                    total_min=error[1], offenders=', '.join(error[2])))
            else:
                send_whatsapp_message(phone, get_msg(phone, 'solver_error') + f"\n\nDebug: {error}")
            return

        if result is None:
            send_whatsapp_message(phone, get_msg(phone, 'solver_error'))
            return

        msg = format_ration_message(phone, result)
        # WhatsApp has a 1600 char limit per segment, but Twilio splits automatically
        send_whatsapp_message(phone, msg)
        print(f"[SOLVER] Result sent to {phone}")

        # Save to session memory
        if phone in user_sessions:
            user_sessions[phone]['last_profile'] = result['profile_name']
            user_sessions[phone]['last_feeds'] = [r['name'] for r in result['ration']]
            user_sessions[phone]['state'] = 'done'

    except Exception as e:
        print(f"[SOLVER] EXCEPTION: {traceback.format_exc()}")
        send_whatsapp_message(phone, get_msg(phone, 'solver_error') + f"\n\nError: {str(e)[:200]}")


# ============================================================
# PARSE FEED NUMBERS FROM USER INPUT
# ============================================================
def parse_feed_numbers(text):
    """Parse comma/space separated numbers from user text."""
    import re
    # Remove spaces, split by commas
    cleaned = text.strip().replace(' ', ',')
    parts = cleaned.split(',')
    valid_ids = []
    invalid_nums = []
    for part in parts:
        part = part.strip()
        if not part:
            continue
        if part in FEED_NUMBER_MAP:
            valid_ids.append(FEED_NUMBER_MAP[part])
        else:
            invalid_nums.append(part)
    return valid_ids, invalid_nums


# ============================================================
# GEMINI IMAGE PROCESSING
# ============================================================
def gemini_detect_feeds(image_b64):
    """Use Gemini to detect feed ingredients in a photo."""
    if not gemini_client:
        return None
    try:
        response = gemini_client.models.generate_content(
            model=GEMINI_MODEL,
            contents=[
                {"role": "user", "parts": [
                    {"inline_data": {"mime_type": "image/jpeg", "data": image_b64}},
                    {"text": """You are a feed ingredient identifier for Kenyan livestock farming.
Look at this image and identify any animal feed ingredients visible.
Return ONLY a JSON array of feed IDs from this list:
1=Maize Grain, 2=Wheat Bran, 3=Rice Bran, 4=Sorghum, 5=Cassava Chips,
6=Soybean Meal, 7=Sunflower Cake, 8=Cottonseed Cake, 9=Fish Meal, 10=Blood Meal,
11=Limestone, 12=Dicalcium Phosphate, 13=Oyster Shell, 14=Vitamin-Mineral Premix,
15=Salt, 16=Methionine, 17=Lysine, 18=Sweet Potato Vines, 19=Lucerne Hay, 20=Grass Hay, 21=Brewers Grains.
If you can't identify any feeds, return: []
Example: [1, 6, 14]"""}
                ]}
            ]
        )
        text = response.text.strip()
        # Parse JSON
        if '[' in text:
            start = text.index('[')
            end = text.rindex(']') + 1
            numbers = json.loads(text[start:end])
            feed_ids = []
            for n in numbers:
                ns = str(n)
                if ns in FEED_NUMBER_MAP:
                    feed_ids.append(FEED_NUMBER_MAP[ns])
            return feed_ids if feed_ids else None
        return None
    except Exception as e:
        print(f"[GEMINI] Image error: {e}")
        return None


# ============================================================
# GEMINI TEXT PROCESSING (fallback NLU)
# ============================================================
def gemini_understand_intent(text, profile_key=None, species=None):
    """Use Gemini to understand free-text input about feeds."""
    if not gemini_client:
        return None
    try:
        context = ""
        if species:
            context = f"The user is formulating feed for {species}."
        if profile_key and profile_key in ALL_PROFILES:
            context += f" Profile: {ALL_PROFILES[profile_key]['name']}."

        response = gemini_client.models.generate_content(
            model=GEMINI_MODEL,
            contents=[{"role": "user", "parts": [{"text": f"""{context}
The user said: "{text}"

Available feeds with their IDs:
1=Maize Grain, 2=Wheat Bran, 3=Rice Bran, 4=Sorghum, 5=Cassava Chips,
6=Soybean Meal, 7=Sunflower Cake, 8=Cottonseed Cake, 9=Fish Meal, 10=Blood Meal,
11=Limestone, 12=Dicalcium Phosphate, 13=Oyster Shell, 14=Vitamin-Mineral Premix,
15=Salt, 16=Methionine, 17=Lysine, 18=Sweet Potato Vines, 19=Lucerne Hay, 20=Grass Hay, 21=Brewers Grains.

Return ONLY a JSON object: {{"feeds": [list of feed IDs], "intent": "select_feeds|question|other", "reply": "brief reply"}}
If the user is asking a question (not selecting feeds), set feeds to [] and reply with a helpful answer.
Example: {{"feeds": [1, 6, 14, 15], "intent": "select_feeds", "reply": ""}}
"""}]}]
        )
        result = json.loads(response.text.strip())
        return result
    except Exception as e:
        print(f"[GEMINI] Text error: {e}")
        return None


# ============================================================
# MAIN WEBHOOK — THIS WAS COMPLETELY MISSING BEFORE
# ============================================================
@app.post("/whatsapp")
async def whatsapp_webhook(
    request: Request,
    Body: str = Form(...),
    From: str = Form(...),
    NumMedia: str = Form("0"),
    MediaUrl0: str = Form(""),
    MediaContentType0: str = Form(""),
):
    """Main Twilio WhatsApp webhook — handles the entire conversation."""
    phone = From.replace("whatsapp:", "")
    text = Body.strip().upper()
    num_media = int(NumMedia)

    resp = MessagingResponse()

    # --- Init session ---
    if phone not in user_sessions:
        user_sessions[phone] = {'state': 'new', 'lang': 'en'}

    session = user_sessions[phone]
    state = session.get('state', 'new')

    # --- Handle IMAGE ---
    if num_media > 0 and MediaUrl0:
        if TWILIO_SID and TWILIO_TOKEN:
            try:
                img_resp = requests.get(MediaUrl0, auth=(TWILIO_SID, TWILIO_TOKEN), timeout=10)
                img_b64 = base64.b64encode(img_resp.content).decode()
                detected = gemini_detect_feeds(img_b64)
                if detected:
                    session['photo_feeds'] = detected
                    names = [FEEDS_DB[f]['name'] for f in detected if f in FEEDS_DB]
                    resp.message(get_msg(phone, 'photo_detected', feeds=', '.join(names)))
                else:
                    resp.message(get_msg(phone, 'photo_not_found'))
            except Exception as e:
                print(f"[IMAGE] Error: {e}")
                resp.message(get_msg(phone, 'photo_not_found'))
        else:
            resp.message(get_msg(phone, 'photo_not_found'))
        return Response(content=str(resp), media_type="application/xml")

    # --- Handle AUDIO ---
    if MediaContentType0 and 'audio' in MediaContentType0:
        resp.message(get_msg(phone, 'voice_soon'))
        return Response(content=str(resp), media_type="application/xml")

    # ============================================================
    # STATE MACHINE
    # ============================================================

    # --- NEW / START ---
    if state == 'new' or text in ['START', 'HI', 'HELLO', 'HOLA', 'SAWA', 'MAMBO']:
        session['state'] = 'lang'
        resp.message(get_msg(phone, 'welcome') + "\n\n" + get_msg(phone, 'choose_language'))
        return Response(content=str(resp), media_type="application/xml")

    # --- LANGUAGE SELECTION ---
    if state == 'lang':
        if text in LANG_MAP:
            session['lang'] = LANG_MAP[text]
            session['state'] = 'species'
            resp.message(get_msg(phone, 'choose_species'))
        else:
            resp.message(get_msg(phone, 'invalid_choice') + "\n\n" + get_msg(phone, 'choose_language'))
        return Response(content=str(resp), media_type="application/xml")

    # --- SPECIES SELECTION ---
    if state == 'species':
        if text == '1':
            session['species'] = 'pig'
            session['state'] = 'profile'
            resp.message(get_msg(phone, 'choose_pig'))
        elif text == '2':
            session['species'] = 'chicken'
            session['state'] = 'profile'
            resp.message(get_msg(phone, 'choose_chicken'))
        else:
            resp.message(get_msg(phone, 'invalid_choice') + "\n\n" + get_msg(phone, 'choose_species'))
        return Response(content=str(resp), media_type="application/xml")

    # --- PROFILE SELECTION ---
    if state == 'profile':
        species = session.get('species', 'pig')
        if species == 'pig':
            profile_map = {'1': 'p1', '2': 'p2', '3': 'p3', '4': 'p4', '5': 'p5'}
            if text in profile_map:
                session['profile_key'] = profile_map[text]
                session['state'] = 'feeds'
                resp.message(get_msg(phone, 'feed_selection_pig'))
            else:
                resp.message(get_msg(phone, 'invalid_choice') + "\n\n" + get_msg(phone, 'choose_pig'))
        else:
            profile_map = {'1': 'c1', '2': 'c2', '3': 'c3', '4': 'c4', '5': 'c5', '6': 'c6'}
            if text in profile_map:
                session['profile_key'] = profile_map[text]
                session['state'] = 'feeds'
                resp.message(get_msg(phone, 'feed_selection_chicken'))
            else:
                resp.message(get_msg(phone, 'invalid_choice') + "\n\n" + get_msg(phone, 'choose_chicken'))
        return Response(content=str(resp), media_type="application/xml")

    # --- FEED SELECTION ---
    if state == 'feeds':
        # Handle YES to photo detection
        if text in ['YES', 'NDIYO', 'II', 'NDIO']:
            if session.get('photo_feeds'):
                feed_ids = session['photo_feeds']
                session['selected_feeds'] = feed_ids
                # Go to recommendations check
                _handle_feed_confirmation(phone, session, feed_ids, resp)
                return Response(content=str(resp), media_type="application/xml")
            else:
                resp.message(get_msg(phone, 'invalid_choice'))
                species = session.get('species', 'pig')
                key = 'feed_selection_pig' if species == 'pig' else 'feed_selection_chicken'
                resp.message(get_msg(phone, key))
                return Response(content=str(resp), media_type="application/xml")

        # Parse feed numbers
        feed_ids, invalid = parse_feed_numbers(text)

        if invalid:
            # Try Gemini NLU
            gemini_result = gemini_understand_intent(text, session.get('profile_key'), session.get('species'))
            if gemini_result and gemini_result.get('feeds'):
                feed_ids = gemini_result['feeds']
                if gemini_result.get('reply'):
                    resp.message(gemini_result['reply'] + "\n")
                invalid = []

        if not feed_ids and invalid:
            resp.message(get_msg(phone, 'unknown_feeds', feeds=', '.join(invalid)))
            return Response(content=str(resp), media_type="application/xml")

        if len(feed_ids) < 2:
            resp.message(get_msg(phone, 'select_at_least_2'))
            return Response(content=str(resp), media_type="application/xml")

        session['selected_feeds'] = feed_ids
        _handle_feed_confirmation(phone, session, feed_ids, resp)
        return Response(content=str(resp), media_type="application/xml")

    # --- RECOMMENDATIONS STATE: user can say YES or add more feeds ---
    if state == 'recommendations':
        if text in ['YES', 'NDIYO', 'II', 'NDIO']:
            # Calculate with recommended feeds added
            feed_ids = session.get('selected_feeds', [])
            rec_ids = session.get('recommended_feeds', [])
            session['state'] = 'calculating'
            resp.message(get_msg(phone, 'calculating'))
            # Fire background task
            threading.Thread(
                target=run_calculation_and_send,
                args=(f"whatsapp:{phone}", session['profile_key'], feed_ids, rec_ids),
                daemon=True
            ).start()
            return Response(content=str(resp), media_type="application/xml")
        else:
            # Try parsing more feed numbers
            feed_ids = list(session.get('selected_feeds', []))
            new_ids, invalid = parse_feed_numbers(text)
            if new_ids:
                feed_ids.extend(new_ids)
                session['selected_feeds'] = feed_ids
                _handle_feed_confirmation(phone, session, feed_ids, resp)
            else:
                resp.message(get_msg(phone, 'invalid_choice'))
                resp.message(get_msg(phone, 'ask_confirm_recs'))
            return Response(content=str(resp), media_type="application/xml")

    # --- DONE state ---
    if state == 'done':
        resp.message(get_msg(phone, 'start_again'))
        return Response(content=str(resp), media_type="application/xml")

    # --- CALCULATING state (ignore until result arrives) ---
    if state == 'calculating':
        resp.message("⏳ Still calculating… please wait.")
        return Response(content=str(resp), media_type="application/xml")

    # --- Fallback ---
    resp.message(get_msg(phone, 'generic_help'))
    return Response(content=str(resp), media_type="application/xml")


def _handle_feed_confirmation(phone, session, feed_ids, resp):
    """Check feed gaps and either show recommendations or go straight to calculation."""
    profile_key = session.get('profile_key', 'p1')
    rec_keys = analyze_feed_gaps(profile_key, feed_ids)

    if rec_keys:
        # Show recommendations, ask user to confirm
        # Map rec_keys to actual feed IDs to add
        rec_feed_ids = _recommendation_keys_to_feed_ids(profile_key, feed_ids, rec_keys)
        session['recommended_feeds'] = rec_feed_ids
        session['state'] = 'recommendations'

        # Build message
        feed_names = [FEEDS_DB[f]['name'] for f in feed_ids if f in FEEDS_DB]
        msg = f"*{get_msg(phone, 'recommendations_header')}*\n"
        msg += get_msg(phone, 'current_selection', feeds=', '.join(feed_names)) + "\n\n"
        for key in rec_keys:
            msg += get_msg(phone, key) + "\n"

        if rec_feed_ids:
            rec_names = [f"#{ID_TO_NUMBER[f]} {FEEDS_DB[f]['name']}" for f in rec_feed_ids if f in FEEDS_DB]
            msg += f"\n🤖 I recommend adding: {', '.join(rec_names)}\n"

        msg += f"\n{get_msg(phone, 'ask_confirm_recs')}"
        resp.message(msg)
    else:
        # No gaps — go straight to calculation
        session['state'] = 'calculating'
        resp.message(get_msg(phone, 'calculating'))
        threading.Thread(
            target=run_calculation_and_send,
            args=(f"whatsapp:{phone}", profile_key, feed_ids, None),
            daemon=True
        ).start()


def _recommendation_keys_to_feed_ids(profile_key, current_feeds, rec_keys):
    """Map recommendation keys to specific feed IDs to suggest."""
    current_set = set(current_feeds)
    suggested = []

    # For each gap, pick the best available feed
    if 'rec_energy' in rec_keys:
        # Prefer maize, then wheat bran
        for fid in ['maize_grain', 'wheat_bran', 'sorghum', 'cassava_chips', 'rice_bran']:
            if fid not in current_set and fid not in suggested:
                suggested.append(fid)
                break

    if 'rec_protein' in rec_keys:
        for fid in ['soybean_meal', 'sunflower_cake', 'cottonseed_cake', 'fish_meal', 'brewers_grains']:
            if fid not in current_set and fid not in suggested:
                suggested.append(fid)
                break

    if 'rec_mineral' in rec_keys:
        for fid in ['limestone', 'dicalcium_phosphate']:
            if fid not in current_set and fid not in suggested:
                suggested.append(fid)

    if 'rec_salt' in rec_keys and 'salt' not in current_set and 'salt' not in suggested:
        suggested.append('salt')

    if 'rec_premix' in rec_keys and 'vitamin_mineral_premix' not in current_set and 'vitamin_mineral_premix' not in suggested:
        suggested.append('vitamin_mineral_premix')

    if 'rec_calcium_layer' in rec_keys:
        for fid in ['oyster_shell', 'limestone']:
            if fid not in current_set and fid not in suggested:
                suggested.append(fid)
                break

    if 'rec_lysine_pig' in rec_keys and 'lysine' not in current_set and 'lysine' not in suggested:
        suggested.append('lysine')

    if 'rec_methionine_broiler' in rec_keys and 'methionine' not in current_set and 'methionine' not in suggested:
        suggested.append('methionine')

    return suggested


# ============================================================
# HEALTH / ROOT ENDPOINTS
# ============================================================
@app.get("/")
async def root():
    return {"bot": "BalancedBora Gruwe-Kuku v2.2", "status": "running",
            "sessions": len(user_sessions), "model": GEMINI_MODEL}

@app.get("/health")
async def health():
    return {"status": "ok"}

# ============================================================
# STARTUP
# ============================================================
@app.on_event("startup")
async def startup():
    print("=" * 60)
    print("  BALANCEDBORA GRUWE-KUKU BOT v2.2")
    print(f"  Model: {GEMINI_MODEL}")
    print(f"  Twilio: {'configured' if client else 'NOT CONFIGURED'}")
    print(f"  Gemini: {'configured' if gemini_client else 'NOT CONFIGURED'}")
    print(f"  Feeds: {len(FEEDS_DB)}")
    print(f"  Profiles: {len(ALL_PROFILES)}")
    print("=" * 60)


# ============================================================
# RUN WITH: uvicorn main:app --host 0.0.0.0 --port 8000
# ============================================================
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
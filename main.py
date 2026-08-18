# BALANCEDBORA GRUWE-KUKU v2.2
import os,requests,base64,time,json,threading,traceback
from fastapi import FastAPI,Form,Request
from fastapi.responses import Response
from fastapi.staticfiles import StaticFiles
from twilio.rest import Client
from twilio.twiml.messaging_response import MessagingResponse
import pulp
from dotenv import load_dotenv
load_dotenv()
from google import genai
app = FastAPI(title="BalancedBora Bot")
os.makedirs("static",exist_ok=True)
app.mount("/static",StaticFiles(directory="static"),name="static")
TWILIO_SID=os.getenv("TWILIO_ACCOUNT_SID","")
TWILIO_TOKEN=os.getenv("TWILIO_AUTH_TOKEN","")
TWILIO_NUMBER=os.getenv("TWILIO_PHONE_NUMBER","whatsapp:+254703709346")
GEMINI_API_KEY=os.getenv("GEMINI_API_KEY","")
GEMINI_MODEL=os.getenv("GEMINI_MODEL","gemini-2.0-flash")
client=Client(TWILIO_SID,TWILIO_TOKEN) if TWILIO_SID else None
gemini_client=None
if GEMINI_API_KEY:
    try:
        gemini_client=genai.Client(api_key=GEMINI_API_KEY)
        print(f"[GEMINI] OK model={GEMINI_MODEL}")
    except Exception as e: print(f"[GEMINI] Fail: {e}")
user_sessions={}
MESSAGES={
'en':{'welcome':"Welcome to BalancedBora!\nI calculate cheapest balanced rations using NRC science.",'choose_language':"Choose language:\n1 English\n2 Kiswahili\n3 Kikuyu\n4 Kimeru",'choose_species':"Step 1: Animal:\n1 Pigs\n2 Chickens",'choose_pig':"Step 2: Pig type:\n1 Weaner 10-20kg\n2 Grower 20-50kg\n3 Finisher 50-100kg\n4 Gestating Sow\n5 Lactating Sow",'choose_chicken':"Step 2: Chicken type:\n1 Broiler Starter 0-3wks\n2 Broiler Grower 3-6wks\n3 Broiler Finisher 6-8wks\n4 Layer Starter 0-6wks\n5 Layer Grower 6-18wks\n6 Laying Hen 18+wks",'feed_selection_pig':"Step 3: Which feeds? Send comma-separated numbers:\nENERGY:\n1 Maize 30kg\n2 Wheat Bran 20kg\n3 Rice Bran 22kg\n4 Cassava 18kg\n5 Sweet Potato Vines 5kg\nPROTEIN:\n6 Soybean 75kg\n7 Sunflower 55kg\n8 Cottonseed 60kg\n9 Fish Meal 120kg\n10 Brewers 15kg\nFORAGE:\n11 Lucerne 35kg\n12 Grass Hay 10kg\nADDITIVES:\n13 Limestone 15kg\n14 DCP 80kg\n15 Premix 150kg\n16 Salt 20kg\n17 Lysine 200kg",'feed_selection_chicken':"Step 3: Which feeds? Send comma-separated numbers:\nENERGY:\n1 Maize 30kg\n2 Wheat Bran 20kg\n3 Rice Bran 22kg\n4 Sorghum 28kg\n5 Cassava 18kg\nPROTEIN:\n6 Soybean 75kg\n7 Sunflower 55kg\n8 Cottonseed 60kg\n9 Fish Meal 120kg\n10 Blood Meal 100kg\nMINERALS:\n11 Limestone 15kg\n12 DCP 80kg\n13 Oyster Shell 25kg\n14 Premix 150kg\n15 Salt 20kg\n16 Methionine 250kg\n17 Lysine 200kg",'calculating':"Calculating... wait ~10 seconds.",'no_energy':"ERROR: Add at least 1 energy source (#1-5).",'impossible_mins':"ERROR: Feeds minimums exceed 100%. Remove some.",'unknown_feeds':"Unknown feeds: {feeds}",'select_at_least_2':"Select at least 2 feeds (e.g. 1,3,6,15)",'invalid_choice':"Send a valid number.",'start_again':"Send START for another ration.",'solver_error':"Calculation error. Try START again.",'photo_not_found':"Could not identify feeds in photo.",'voice_soon':"Voice notes coming soon!",'generic_help':"Send START to calculate a ration.",'yes_confirm':"Reply YES to use these.",'ask_more_feeds':"Need 2+ feeds. Send more numbers.",'recommendations_header':"RECOMMENDATIONS:",'rec_energy':"Add ENERGY (Maize #1, Wheat Bran #2)",'rec_protein':"Add PROTEIN (Soybean #6, Fish Meal #9)",'rec_mineral':"Add MINERALS (Limestone #11, DCP #12)",'rec_salt':"Add SALT (#15)",'rec_premix':"Add PREMIX (#14)",'rec_calcium_layer':"LAYERS: Add CALCIUM (Oyster Shell #13)",'rec_lysine_pig':"Pig weaners: Add LYSINE (#17)",'rec_methionine_broiler':"Broilers: Add METHIONINE (#16)",'current_selection':"You have: {feeds}",'ask_confirm_recs':"Reply YES to calculate with these + my recommendations, or send more numbers.",'ration_optimal':"*Your Balanced Ration (NRC)*",'ration_besteffort':"*Your Best Ration (Closest Possible)*",'mix_header':"MIX THESE:",'dmi_label':"Daily Intake",'cost_kg_label':"Cost/kg",'total_cost_label':"Cost/day",'notes_header':"NUTRIENTS:",'best_effort_notice':"Best-Effort: could not hit all targets perfectly.",'nutrient_low':"{n}: {a}% (need {mi}-{ma}) LOW",'nutrient_high':"{n}: {a}% (need {mi}-{ma}) HIGH",'ai_suggestions':"To improve, try adding:",'how_to_feed_pig':"FEEDING: Weigh accurately, mix well, feed 2-3x daily, provide clean water always.",'how_to_feed_chicken':"FEEDING: Weigh and mix well. Broilers: always available. Layers: 120g/hen/day. Clean water always.",'supplier_header':"SUPPLIERS:",'supplier_na':"No supplier data loaded yet.",'gemini_error':"AI unavailable. Use menu numbers.",'memory_greeting':"Welcome back! Send START for a new ration."},
'sw':{'welcome':"Karibu BalancedBora!\nNakuhesabu chakula bora kwa gharama nafuu.",'choose_language':"Chagua lugha:\n1 English\n2 Kiswahili\n3 Kikuyu\n4 Kimeru",'choose_species':"Hatua 1:\n1 Nguruwe\n2 Kuku",'choose_pig':"Hatua 2: Aina ya nguruwe:\n1 Mtoto 10-20kg\n2 Mkubwa 20-50kg\n3 Mwisho 50-100kg\n4 Tumbili Mjamzito\n5 Tumbili Ananyonyesha",'choose_chicken':"Hatua 2: Aina ya kuku:\n1 Broiler Mwanzo\n2 Broiler Mkubwa\n3 Broiler Mwisho\n4 Layer Mwanzo\n5 Layer Mkubwa\n6 Layer Mzima",'feed_selection_pig':"Hatua 3: Chagua chakula (namba):\nNISHATI: 1 Mahindi 2 MakapiNgano 3 MakapiMchele 4 Muhogo 5 MajaniViazi\nPROTEINI: 6 Soya 7 Alizeti 8 Pamba 9 Samaki 10 Bia\nMAJANI: 11 Lucerne 12 Nyasi\nMADINI: 13 Chokaa 14 DCP 15 Premix 16 Chumvi 17 Lysine",'feed_selection_chicken':"Hatua 3: Chagua chakula (namba):\nNISHATI: 1 Mahindi 2 MakapiNgano 3 MakapiMchele 4 Sorghum 5 Muhogo\nPROTEINI: 6 Soya 7 Alizeti 8 Pamba 9 Samaki 10 Damu\nMADINI: 11 Chokaa 12 DCP 13 OysterShell 14 Premix 15 Chumvi 16 Methionine 17 Lysine",'calculating':"Nakuhesabu... subiri sekunde 10.",'no_energy':"Ongeza chanzo cha nishati (#1-5).",'impossible_mins':"Haiwezekani. Ondoa baadhi ya chakula.",'unknown_feeds':"Haijulikani: {feeds}",'select_at_least_2':"Chagua angalau chakula 2 (mfano 1,6,15)",'invalid_choice':"Tuma namba sahihi.",'start_again':"Tuma START kwa chakula kingine.",'solver_error':"Hitilafu. Tuma START tena.",'photo_not_found':"Sikuweza kutambua chakula.",'voice_soon':"Sauti utakuja hivi karibu!",'generic_help':"Tuma START.",'yes_confirm':"Jibu NDIYO.",'ask_more_feeds':"Unahitaji chakula 2+. Tuma namba zaidi.",'recommendations_header':"MAPENDEKEZO:",'rec_energy':"Ongeza NISHATI (Mahindi #1)",'rec_protein':"Ongeza PROTEINI (Soya #6)",'rec_mineral':"Ongeza MADINI (Chokaa #11)",'rec_salt':"Ongeza CHUMVI (#15)",'rec_premix':"Ongeza PREMIX (#14)",'rec_calcium_layer':"LAYERS: Ongeza CALCIUM (#13)",'rec_lysine_pig':"Nguruwe: Ongeza LYSINE (#17)",'rec_methionine_broiler':"Broilers: Ongeza METHIONINE (#16)",'current_selection':"Unacho: {feeds}",'ask_confirm_recs':"Jibu NDIYO kuhesabu, au tuma namba zaidi.",'ration_optimal':"*Chakula Bora (NRC)*",'ration_besteffort':"*Chakula Bora Zaidi*",'mix_header':"CHANGANYA:",'dmi_label':"Kula/Siku",'cost_kg_label':"Bei/kg",'total_cost_label':"Bei/Siku",'notes_header':"MATUNZI:",'best_effort_notice':"Hali bora zaidi: halingewezi kufikia kila lengo.",'nutrient_low':"{n}: {a}% (lengo {mi}-{ma}) CHINI",'nutrient_high':"{n}: {a}% (lengo {mi}-{ma}) JUU",'ai_suggestions':"Kuboresha, ongeza:",'how_to_feed_pig':"Pima vizuri, changanya, lisha 2-3x/siku, maji safi.",'how_to_feed_chicken':"Pima vizuri, changanya. Broilers: kila wakati. Layers: 120g/siku. Maji safi.",'supplier_header':"WAUZAJI:",'supplier_na':"Hakuna data ya wauzaji.",'gemini_error':"AI haipo. Tumia namba.",'memory_greeting':"Karibu tena! Tuma START."},
'ki':{'welcome':"Mwega BalancedBora!",'choose_language':"1 English\n2 Kiswahili\n3 Kikuyu\n4 Kimeru",'choose_species':"1 Nguruwe\n2 Ngukuu",'choose_pig':"1 Kihii 2 Munene 3 Muthi 4 Tumbili Mukuru 5 Tumbili Kunyithia",'choose_chicken':"1 Broiler Kihii 2 Broiler Munene 3 Broiler Muthi 4 Layer Kihii 5 Layer Munene 6 Layer Mukuru",'feed_selection_pig':"Tuma namba:\nHOTI: 1 Mubii 2 MakapiNgano 3 MakapiMuchelee 4 Muhogo 5 MajaniViazi\nPROTEINI: 6 Soya 7 Alizeti 8 Pamba 9 Thamaki 10 Bia\nMAJANI: 11 Lucerne 12 Nyasi\nMADINI: 13 Chokaa 14 DCP 15 Premix 16 Chumvi 17 Lysine",'feed_selection_chicken':"Tuma namba:\nHOTI: 1 Mubii 2 MakapiNgano 3 MakapiMuchelee 4 Sorghum 5 Muhogo\nPROTEINI: 6 Soya 7 Alizeti 8 Pamba 9 Thamaki 10 Riutii\nMADINI: 11 Chokaa 12 DCP 13 OysterShell 14 Premix 15 Chumvi 16 Methionine 17 Lysine",'calculating':"Ndirathiriria... rigira thiguku 10.",'no_energy':"Ongea hoti (#1-5).",'impossible_mins':"Haiwezekani.",'unknown_feeds':"Itarimenyekana: {feeds}",'select_at_least_2':"Thagua irio 2+.",'invalid_choice':"Tuma namba sahihi.",'start_again':"Tuma START.",'solver_error':"Hitilafu. Tuma START.",'photo_not_found':"Ndiratambua.",'voice_soon':"Mugamo uguka!",'generic_help':"Tuma START.",'yes_confirm':"Cokeria II.",'ask_more_feeds':"Bata irio 2+.",'recommendations_header':"MAENDELEZO:",'rec_energy':"Bata HOTI (#1)",'rec_protein':"Bata PROTEINI (#6)",'rec_mineral':"Bata MADINI (#11)",'rec_salt':"Bata CHUMVI (#15)",'rec_premix':"Bata PREMIX (#14)",'rec_calcium_layer':"LAYERS: CALCIUM (#13)",'rec_lysine_pig':"LYSINE (#17)",'rec_methionine_broiler':"METHIONINE (#16)",'current_selection':"Wira na: {feeds}",'ask_confirm_recs':"Cokeria II kuhuthia.",'ration_optimal':"*Irio Ritheru*",'ration_besteffort':"*Irio Ritheru Zaidi*",'mix_header':"CAMBANIA:",'dmi_label':"Kuria/Mthenya",'cost_kg_label':"Bei/kg",'total_cost_label':"Bei/Mthenya",'notes_header':"MAELEZO:",'best_effort_notice':"Ritheru zaidi.",'nutrient_low':"{n}: {a}% ({mi}-{ma}) CHINI",'nutrient_high':"{n}: {a}% ({mi}-{ma}) JUU",'ai_suggestions':"Kuboresha:",'how_to_feed_pig':"Pima, cambania, he irio 2-3x.",'how_to_feed_chicken':"Pima, cambania, he irio.",'supplier_header':"MAGURA:",'supplier_na':"Ti ikii.",'gemini_error':"AI ndari. Tumia namba.",'memory_greeting':"Mwega! Tuma START."},
'mer':{'welcome':"Urova BalancedBora!",'choose_language':"1 English\n2 Kiswahili\n3 Kikuyu\n4 Kimeru",'choose_species':"1 Nguruwe\n2 Ngukuu",'choose_pig':"1 Kihii 2 Munene 3 Muthi 4 Tumbili Mukuru 5 Tumbili Kunyithia",'choose_chicken':"1 Broiler Kihii 2 Broiler Munene 3 Broiler Muthi 4 Layer Kihii 5 Layer Munene 6 Layer Mukuru",'feed_selection_pig':"Tuma namba:\nHOTI: 1 Mubii 2 MakapiNgano 3 MakapiMuchelee 4 Muhogo 5 MajaniViazi\nPROTEINI: 6 Soya 7 Alizeti 8 Pamba 9 Thamaki 10 Bia\nMAJANI: 11 Lucerne 12 Nyasi\nMADINI: 13 Chokaa 14 DCP 15 Premix 16 Chumvi 17 Lysine",'feed_selection_chicken':"Tuma namba:\nHOTI: 1 Mubii 2 MakapiNgano 3 MakapiMuchelee 4 Sorghum 5 Muhogo\nPROTEINI: 6 Soya 7 Alizeti 8 Pamba 9 Thamaki 10 Riutii\nMADINI: 11 Chokaa 12 DCP 13 OysterShell 14 Premix 15 Chumvi 16 Methionine 17 Lysine",'calculating':"Ntathimana... rigira thiguku 10.",'no_energy':"Ongea hoti (#1-5).",'impossible_mins':"Haiwezekani.",'unknown_feeds':"Itarimenyekana: {feeds}",'select_at_least_2':"Thagua irio 2+.",'invalid_choice':"Tuma namba sahihi.",'start_again':"Tuma START.",'solver_error':"Hitilafu. Tuma START.",'photo_not_found':"Ndiratambua.",'voice_soon':"Mugamo uguka!",'generic_help':"Tuma START.",'yes_confirm':"Cokeria II.",'ask_more_feeds':"Bata irio 2+.",'recommendations_header':"MAENDELEZO:",'rec_energy':"Bata HOTI (#1)",'rec_protein':"Bata PROTEINI (#6)",'rec_mineral':"Bata MADINI (#11)",'rec_salt':"Bata CHUMVI (#15)",'rec_premix':"Bata PREMIX (#14)",'rec_calcium_layer':"LAYERS: CALCIUM (#13)",'rec_lysine_pig':"LYSINE (#17)",'rec_methionine_broiler':"METHIONINE (#16)",'current_selection':"Wira na: {feeds}",'ask_confirm_recs':"Cokeria II kuhuthia.",'ration_optimal':"*Irio Ritheru*",'ration_besteffort':"*Irio Ritheru Zaidi*",'mix_header':"CAMBANIA:",'dmi_label':"Kuria/Mthenya",'cost_kg_label':"Bei/kg",'total_cost_label':"Bei/Mthenya",'notes_header':"MAELEZO:",'best_effort_notice':"Ritheru zaidi.",'nutrient_low':"{n}: {a}% ({mi}-{ma}) CHINI",'nutrient_high':"{n}: {a}% ({mi}-{ma}) JUU",'ai_suggestions':"Kuboresha:",'how_to_feed_pig':"Pima, cambania, he irio 2-3x.",'how_to_feed_chicken':"Pima, cambania, he irio.",'supplier_header':"MAGURA:",'supplier_na':"Ti ikii.",'gemini_error':"AI ndari. Tumia namba.",'memory_greeting':"Mwega! Tuma START."}
}
def gm(p,k,**kw):
    l=user_sessions.get(p,{}).get('lang','en')
    t=MESSAGES.get(l,MESSAGES['en']).get(k,MESSAGES['en'].get(k,f'[{k}]'))
    try: t=t.format(**kw)
    except: pass
    return t
FEED_NUMBER_MAP={'1':'maize_grain','2':'wheat_bran','3':'rice_bran','4':'sorghum','5':'cassava_chips','6':'soybean_meal','7':'sunflower_cake','8':'cottonseed_cake','9':'fish_meal','10':'blood_meal','11':'limestone','12':'dicalcium_phosphate','13':'oyster_shell','14':'vitamin_mineral_premix','15':'salt','16':'methionine','17':'lysine','18':'sweet_potato_vines','19':'lucerne_hay','20':'grass_hay','21':'brewers_grains'}
ID_TO_NUMBER={v:k for k,v in FEED_NUMBER_MAP.items()}
FEEDS_DB={'maize_grain':{'name':'Maize Grain','cp':8.5,'me':3.35,'lysine':0.25,'ca':0.03,'p':0.27,'cf':2.7,'fat':4.0,'ash':1.3,'cost_kg':30,'min_incl':10,'max_incl':60,'category':'energy'},'wheat_bran':{'name':'Wheat Bran','cp':15.0,'me':2.60,'lysine':0.55,'ca':0.10,'p':0.90,'cf':10.5,'fat':3.0,'ash':5.5,'cost_kg':20,'min_incl':0,'max_incl':25,'category':'energy'},'rice_bran':{'name':'Rice Bran','cp':13.0,'me':2.50,'lysine':0.50,'ca':0.08,'p':1.40,'cf':12.0,'fat':12.0,'ash':10.0,'cost_kg':22,'min_incl':0,'max_incl':15,'category':'energy'},'sorghum':{'name':'Sorghum','cp':9.0,'me':3.20,'lysine':0.20,'ca':0.04,'p':0.30,'cf':2.5,'fat':3.0,'ash':1.5,'cost_kg':28,'min_incl':0,'max_incl':40,'category':'energy'},'cassava_chips':{'name':'Cassava Chips','cp':3.0,'me':3.20,'lysine':0.10,'ca':0.25,'p':0.10,'cf':4.0,'fat':0.5,'ash':2.5,'cost_kg':18,'min_incl':0,'max_incl':20,'category':'energy'},'soybean_meal':{'name':'Soybean Meal','cp':48.0,'me':3.20,'lysine':2.90,'ca':0.35,'p':0.70,'cf':6.0,'fat':2.0,'ash':6.5,'cost_kg':75,'min_incl':5,'max_incl':35,'category':'protein'},'sunflower_cake':{'name':'Sunflower Cake','cp':35.0,'me':2.20,'lysine':1.20,'ca':0.40,'p':1.00,'cf':22.0,'fat':10.0,'ash':6.0,'cost_kg':55,'min_incl':0,'max_incl':20,'category':'protein'},'cottonseed_cake':{'name':'Cottonseed Cake','cp':40.0,'me':2.40,'lysine':1.50,'ca':0.20,'p':1.10,'cf':18.0,'fat':5.0,'ash':6.0,'cost_kg':60,'min_incl':0,'max_incl':15,'category':'protein'},'fish_meal':{'name':'Fish Meal','cp':65.0,'me':2.80,'lysine':4.50,'ca':5.50,'p':3.00,'cf':1.0,'fat':8.0,'ash':18.0,'cost_kg':120,'min_incl':0,'max_incl':8,'category':'protein'},'blood_meal':{'name':'Blood Meal','cp':85.0,'me':2.50,'lysine':7.50,'ca':0.30,'p':0.25,'cf':1.0,'fat':1.0,'ash':5.0,'cost_kg':100,'min_incl':0,'max_incl':4,'category':'protein'},'limestone':{'name':'Limestone','cp':0.0,'me':0.0,'lysine':0.0,'ca':38.0,'p':0.0,'cf':0.0,'fat':0.0,'ash':98.0,'cost_kg':15,'min_incl':0,'max_incl':2,'category':'mineral'},'dicalcium_phosphate':{'name':'DCP','cp':0.0,'me':0.0,'lysine':0.0,'ca':24.0,'p':18.5,'cf':0.0,'fat':0.0,'ash':95.0,'cost_kg':80,'min_incl':0,'max_incl':2,'category':'mineral'},'oyster_shell':{'name':'Oyster Shell','cp':0.0,'me':0.0,'lysine':0.0,'ca':36.0,'p':0.10,'cf':0.0,'fat':0.0,'ash':97.0,'cost_kg':25,'min_incl':0,'max_incl':8,'category':'mineral'},'vitamin_mineral_premix':{'name':'Premix','cp':0.0,'me':0.0,'lysine':0.0,'ca':8.0,'p':4.0,'cf':0.0,'fat':0.0,'ash':90.0,'cost_kg':150,'min_incl':0.2,'max_incl':1.5,'category':'mineral'},'salt':{'name':'Salt','cp':0.0,'me':0.0,'lysine':0.0,'ca':0.0,'p':0.0,'cf':0.0,'fat':0.0,'ash':100.0,'cost_kg':20,'min_incl':0.2,'max_incl':0.6,'category':'mineral'},'methionine':{'name':'Methionine','cp':58.0,'me':2.0,'lysine':0.0,'ca':0.0,'p':0.0,'cf':0.0,'fat':0.0,'ash':0.0,'cost_kg':250,'min_incl':0,'max_incl':0.5,'category':'additive'},'lysine':{'name':'Lysine','cp':95.0,'me':2.0,'lysine':78.0,'ca':0.0,'p':0.0,'cf':0.0,'fat':0.0,'ash':0.0,'cost_kg':200,'min_incl':0,'max_incl':0.5,'category':'additive'},'sweet_potato_vines':{'name':'Sweet Potato Vines','cp':12.0,'me':1.80,'lysine':0.40,'ca':0.80,'p':0.25,'cf':18.0,'fat':2.0,'ash':10.0,'cost_kg':5,'min_incl':0,'max_incl':20,'category':'forage'},'lucerne_hay':{'name':'Lucerne Hay','cp':18.0,'me':1.80,'lysine':0.70,'ca':1.40,'p':0.25,'cf':28.0,'fat':2.5,'ash':10.0,'cost_kg':35,'min_incl':0,'max_incl':15,'category':'forage'},'grass_hay':{'name':'Grass Hay','cp':7.0,'me':1.50,'lysine':0.20,'ca':0.35,'p':0.25,'cf':32.0,'fat':2.0,'ash':8.0,'cost_kg':10,'min_incl':0,'max_incl':20,'category':'forage'},'brewers_grains':{'name':'Brewers Grains','cp':25.0,'me':2.10,'lysine':0.80,'ca':0.35,'p':0.55,'cf':18.0,'fat':6.0,'ash':4.0,'cost_kg':15,'min_incl':0,'max_incl':15,'category':'protein'}}
PIG_PROFILES={'p1':{'name':'Pig Weaner 10-20kg','dmi':0.8,'cp':{'min':18,'max':22},'me':{'min':3.2,'max':3.5},'lysine':{'min':1.1,'max':1.4},'ca':{'min':0.7,'max':1.0},'p':{'min':0.55,'max':0.8},'cf':{'min':3,'max':6},'fat':{'min':3,'max':8},'ash':{'min':4,'max':8}},'p2':{'name':'Pig Grower 20-50kg','dmi':1.8,'cp':{'min':16,'max':19},'me':{'min':3.1,'max':3.4},'lysine':{'min':0.85,'max':1.1},'ca':{'min':0.55,'max':0.8},'p':{'min':0.45,'max':0.65},'cf':{'min':4,'max':8},'fat':{'min':3,'max':8},'ash':{'min':4,'max':8}},'p3':{'name':'Pig Finisher 50-100kg','dmi':2.8,'cp':{'min':14,'max':16},'me':{'min':3.0,'max':3.3},'lysine':{'min':0.6,'max':0.85},'ca':{'min':0.45,'max':0.65},'p':{'min':0.35,'max':0.5},'cf':{'min':5,'max':10},'fat':{'min':3,'max':8},'ash':{'min':4,'max':8}},'p4':{'name':'Gestating Sow','dmi':2.2,'cp':{'min':12,'max':14},'me':{'min':2.8,'max':3.1},'lysine':{'min':0.5,'max':0.7},'ca':{'min':0.7,'max':0.9},'p':{'min':0.55,'max':0.7},'cf':{'min':6,'max':12},'fat':{'min':3,'max':8},'ash':{'min':4,'max':8}},'p5':{'name':'Lactating Sow','dmi':5.5,'cp':{'min':16,'max':18},'me':{'min':3.1,'max':3.4},'lysine':{'min':0.85,'max':1.1},'ca':{'min':0.75,'max':1.0},'p':{'min':0.6,'max':0.8},'cf':{'min':4,'max':8},'fat':{'min':3,'max':8},'ash':{'min':4,'max':8}}}
CHICKEN_PROFILES={'c1':{'name':'Broiler Starter 0-3wks','dmi':0.04,'cp':{'min':22,'max':24},'me':{'min':3.2,'max':3.4},'lysine':{'min':1.1,'max':1.3},'ca':{'min':1.0,'max':1.2},'p':{'min':0.45,'max':0.55},'cf':{'min':2,'max':5},'fat':{'min':4,'max':8},'ash':{'min':5,'max':8}},'c2':{'name':'Broiler Grower 3-6wks','dmi':0.1,'cp':{'min':20,'max':22},'me':{'min':3.2,'max':3.4},'lysine':{'min':1.0,'max':1.15},'ca':{'min':0.9,'max':1.1},'p':{'min':0.4,'max':0.5},'cf':{'min':2.5,'max':5.5},'fat':{'min':4,'max':8},'ash':{'min':5,'max':8}},'c3':{'name':'Broiler Finisher 6-8wks','dmi':0.14,'cp':{'min':18,'max':20},'me':{'min':3.2,'max':3.4},'lysine':{'min':0.85,'max':1.0},'ca':{'min':0.8,'max':1.0},'p':{'min':0.35,'max':0.45},'cf':{'min':3,'max':6},'fat':{'min':4,'max':8},'ash':{'min':5,'max':8}},'c4':{'name':'Layer Starter 0-6wks','dmi':0.03,'cp':{'min':18,'max':20},'me':{'min':2.8,'max':3.0},'lysine':{'min':0.85,'max':1.0},'ca':{'min':0.9,'max':1.1},'p':{'min':0.4,'max':0.5},'cf':{'min':3,'max':6},'fat':{'min':3,'max':6},'ash':{'min':5,'max':8}},'c5':{'name':'Layer Grower 6-18wks','dmi':0.07,'cp':{'min':15,'max':17},'me':{'min':2.7,'max':2.9},'lysine':{'min':0.6,'max':0.75},'ca':{'min':0.8,'max':1.0},'p':{'min':0.35,'max':0.45},'cf':{'min':4,'max':7},'fat':{'min':3,'max':6},'ash':{'min':5,'max':8}},'c6':{'name':'Laying Hen 18+wks','dmi':0.12,'cp':{'min':16,'max':18},'me':{'min':2.7,'max':2.9},'lysine':{'min':0.7,'max':0.85},'ca':{'min':3.5,'max':4.5},'p':{'min':0.3,'max':0.4},'cf':{'min':4,'max':7},'fat':{'min':3,'max':6},'ash':{'min':12,'max':16}}}
ALL_PROFILES={**PIG_PROFILES,**CHICKEN_PROFILES}
NL={'cp':'CP%','me':'ME','lysine':'Lys%','ca':'Ca%','p':'P%','cf':'CF%','fat':'Fat%','ash':'Ash%'}
def solve_ration(pk,sf):
    if pk not in ALL_PROFILES: return None,"Invalid profile"
    pr=ALL_PROFILES[pk]; av={f:FEEDS_DB[f] for f in sf if f in FEEDS_DB}
    if len(av)<2: return None,"LESS_THAN_2"
    if not any(v['category']=='energy' for v in av.values()): return None,"NO_ENERGY"
    tm=sum(FEEDS_DB[f]['min_incl'] for f in sf if f in FEEDS_DB)
    if tm>100: return None,"IMPOSSIBLE_MINS"
    ns=['cp','me','lysine','ca','p','cf','fat','ash']
    prob=pulp.LpProblem(f"R_{pk}",pulp.LpMinimize)
    fv=pulp.LpVariable.dicts("F",av.keys(),lowBound=0,upBound=100)
    prob+=pulp.lpSum([fv[f]*av[f]['cost_kg'] for f in av])
    prob+=pulp.lpSum([fv[f] for f in av])==100
    for n in ns:
        if n in pr:
            prob+=pulp.lpSum([fv[f]*av[f][n] for f in av])>=pr[n]['min']*100
            prob+=pulp.lpSum([fv[f]*av[f][n] for f in av])<=pr[n]['max']*100
    for f,d in av.items():
        prob+=fv[f]>=d['min_incl']; prob+=fv[f]<=d['max_incl']
    prob.solve(pulp.PULP_CBC_CMD(msg=0,timeLimit=30))
    be=False
    if pulp.LpStatus[prob.status]!='Optimal':
        prob2=pulp.LpProblem(f"R_{pk}_be",pulp.LpMinimize)
        fv2=pulp.LpVariable.dicts("FB",av.keys(),lowBound=0,upBound=100)
        su={}; so={}
        for n in ns:
            if n in pr: su[n]=pulp.LpVariable(f"u_{n}",lowBound=0); so[n]=pulp.LpVariable(f"o_{n}",lowBound=0)
        obj=pulp.lpSum([100000*su[n]+100000*so[n] for n in su])+pulp.lpSum([fv2[f]*av[f]['cost_kg'] for f in av])
        prob2+=obj; prob2+=pulp.lpSum([fv2[f] for f in av])==100
        for f,d in av.items(): prob2+=fv2[f]>=d['min_incl']; prob2+=fv2[f]<=d['max_incl']
        for n in ns:
            if n in pr:
                prob2+=pulp.lpSum([fv2[f]*av[f][n] for f in av])+su[n]*100>=pr[n]['min']*100
                prob2+=pulp.lpSum([fv2[f]*av[f][n] for f in av])-so[n]*100<=pr[n]['max']*100
        prob2.solve(pulp.PULP_CBC_CMD(msg=0,timeLimit=30))
        fv=fv2; be=True
    ra=[]; tc=0; tn={n:0.0 for n in ns}
    for f in av:
        q=fv[f].varValue
        if q is None: q=0
        if q>0.01:
            c=q*av[f]['cost_kg']; tc+=c
            ra.append({'id':f,'name':av[f]['name'],'pct':round(q,2),'kgd':round(q/100*pr['dmi'],4),'cpd':round(c/100*pr['dmi'],2)})
            for n in ns: tn[n]+=q*av[f][n]
    tp=sum(r['pct'] for r in ra)
    if tp>0 and abs(tp-100)>0.1:
        for r in ra:
            r['pct']=round(r['pct']/tp*100,2); r['kgd']=round(r['pct']/100*pr['dmi'],4); r['cpd']=round(r['pct']/100*pr['dmi']*av[r['id']]['cost_kg'],2)
        tn={n:0.0 for n in ns}
        for r in ra:
            for n in ns: tn[n]+=r['pct']*av[r['id']][n]
    dev=[]; lo=[]; hi=[]
    if be:
        for n in ns:
            if n in pr:
                a=tn[n]/100; rq=pr[n]
                if a<rq['min']: dev.append(('low',n,a,rq['min'],rq['max'])); lo.append(n)
                elif a>rq['max']: dev.append(('high',n,a,rq['min'],rq['max'])); hi.append(n)
    return {'pn':pr['name'],'pk':pk,'dmi':pr['dmi'],'ra':ra,'tcpd':round(sum(r['cpd'] for r in ra),2),'cpkg':round(sum(r['pct']*av[r['id']]['cost_kg'] for r in ra)/100,2),'tn':{n:round(v/100,2) for n,v in tn.items()},'be':be,'dev':dev,'sp':'pig' if pk[0]=='p' else 'chicken'},None

def send_wa(to,body):
    if not client: print(f"[TWILIO] No client"); return
    try:
        M=1500
        if len(body)<=M:
            client.messages.create(from_=TWILIO_NUMBER,body=body,to=to)
            print(f"[TWILIO] Sent {len(body)}c")
        else:
            parts=[]; rem=body
            while len(rem)>M:
                c=rem.rfind('\n',0,M)
                if c<=0: c=M
                parts.append(rem[:c].strip()); rem=rem[c:].strip()
            if rem: parts.append(rem)
            for i,p in enumerate(parts):
                client.messages.create(from_=TWILIO_NUMBER,body=p,to=to)
                print(f"[TWILIO] Part {i+1}/{len(parts)}")
                if i<len(parts)-1: time.sleep(0.5)
    except Exception as e: print(f"[TWILIO] Err: {e}")

def bg_calc(phone,pk,fids,recs=None):
    af=list(fids)
    if recs:
        for f in recs:
            if f not in af: af.append(f)
    try:
        print(f"[SOLVE] {phone} pk={pk} feeds={af}")
        r,err=solve_ration(pk,af)
        if err:
            if err=="NO_ENERGY": send_wa(phone,gm(phone,'no_energy'))
            elif err=="LESS_THAN_2": send_wa(phone,gm(phone,'select_at_least_2'))
            elif err=="IMPOSSIBLE_MINS": send_wa(phone,gm(phone,'impossible_mins'))
            else: send_wa(phone,gm(phone,'solver_error'))
            return
        if not r: send_wa(phone,gm(phone,'solver_error')); return
        sp=r['sp']; dmi=r['dmi']
        hk='ration_besteffort' if r['be'] else 'ration_optimal'
        msg=f"{gm(phone,hk)}\n{r['pn']}\n\n*{gm(phone,'mix_header')}*\n"
        for it in r['ra']:
            num=ID_TO_NUMBER.get(it['id'],'?')
            if dmi>=1: msg+=f" {num} {it['name']}: *{it['pct']}%* = {it['kgd']}kg/day\n"
            else: msg+=f" {num} {it['name']}: *{it['pct']}%* = {round(it['kgd']*1000,1)}g/day\n"
        msg+=f"\n{gm(phone,'dmi_label')}: {dmi}kg\n{gm(phone,'cost_kg_label')}: KES {r['cpkg']}\n{gm(phone,'total_cost_label')}: KES {r['tcpd']}\n\n*{gm(phone,'notes_header')}*\n"
        for n in ['cp','me','lysine','ca','p','cf','fat','ash']:
            if n in ALL_PROFILES[r['pk']]:
                a=r['tn'].get(n,0); rq=ALL_PROFILES[r['pk']][n]
                ok="OK" if rq['min']<=a<=rq['max'] else "!!"
                msg+=f" {ok} {NL[n]}: {a}% ({rq['min']}-{rq['max']}%)\n"
        if r['be']:
            msg+=f"\n{gm(phone,'best_effort_notice')}\n"
            for dt,n,a,mi,ma in r['dev']:
                lb=NL.get(n,n)
                if dt=='low': msg+=f" LOW {lb}: {a:.1f}% (need {mi}-{ma})\n"
                else: msg+=f" HIGH {lb}: {a:.1f}% (need {mi}-{ma})\n"
        how='how_to_feed_pig' if sp=='pig' else 'how_to_feed_chicken'
        msg+=f"\n{gm(phone,how)}\n\n{gm(phone,'start_again')}"
        send_wa(phone,msg)
        if phone in user_sessions: user_sessions[phone]['state']='done'
    except Exception as e:
        print(f"[SOLVE] ERR: {traceback.format_exc()}")
        send_wa(phone,gm(phone,'solver_error'))

def parse_nums(txt):
    import re
    cl=txt.strip().replace(' ',',').replace('，',',')
    ps=cl.split(',')
    ok=[]; bad=[]
    for p in ps:
        p=p.strip()
        if not p: continue
        if p in FEED_NUMBER_MAP: ok.append(FEED_NUMBER_MAP[p])
        else: bad.append(p)
    return ok,bad

def analyze_gaps(pk,fids):
    if pk not in ALL_PROFILES: return []
    av={f:FEEDS_DB[f] for f in fids if f in FEEDS_DB}
    if not av: return ['rec_energy','rec_protein','rec_mineral','rec_salt','rec_premix']
    rc=[]; cats={f['category'] for f in av.values()}
    if 'energy' not in cats and 'forage' not in cats: rc.append('rec_energy')
    if 'protein' not in cats: rc.append('rec_protein')
    hm='mineral' in cats
    if not any(f['ca']>1 for f in av.values()) and not hm: rc.append('rec_mineral')
    if 'salt' not in av and not hm: rc.append('rec_salt')
    if 'vitamin_mineral_premix' not in av: rc.append('rec_premix')
    sp='pig' if pk[0]=='p' else 'chicken'
    if sp=='pig' and pk in ['p1','p2'] and 'lysine' not in av: rc.append('rec_lysine_pig')
    if sp=='chicken' and pk in ['c1','c2'] and 'methionine' not in av: rc.append('rec_methionine_broiler')
    if pk=='c6' and 'oyster_shell' not in av and 'limestone' not in av: rc.append('rec_calcium_layer')
    return rc

def map_recs(pk,fids,rcs):
    cs=set(fids); sg=[]
    if 'rec_energy' in rcs:
        for f in ['maize_grain','wheat_bran','sorghum','cassava_chips']:
            if f not in cs and f not in sg: sg.append(f); break
    if 'rec_protein' in rcs:
        for f in ['soybean_meal','sunflower_cake','cottonseed_cake','fish_meal','brewers_grains']:
            if f not in cs and f not in sg: sg.append(f); break
    if 'rec_mineral' in rcs:
        for f in ['limestone','dicalcium_phosphate']:
            if f not in cs and f not in sg: sg.append(f)
    if 'rec_salt' in rcs and 'salt' not in cs and 'salt' not in sg: sg.append('salt')
    if 'rec_premix' in rcs and 'vitamin_mineral_premix' not in cs and 'vitamin_mineral_premix' not in sg: sg.append('vitamin_mineral_premix')
    if 'rec_calcium_layer' in rcs:
        for f in ['oyster_shell','limestone']:
            if f not in cs and f not in sg: sg.append(f); break
    if 'rec_lysine_pig' in rcs and 'lysine' not in cs and 'lysine' not in sg: sg.append('lysine')
    if 'rec_methionine_broiler' in rcs and 'methionine' not in cs and 'methionine' not in sg: sg.append('methionine')
    return sg

def handle_confirm(phone,session,fids,resp):
    pk=session.get('profile_key','p1')
    rcs=analyze_gaps(pk,fids)
    if rcs:
        sg=map_recs(pk,fids,rcs)
        session['recommended_feeds']=sg; session['state']='recommendations'
        fn=[FEEDS_DB[f]['name'] for f in fids if f in FEEDS_DB]
        msg=f"*{gm(phone,'recommendations_header')}*\n{gm(phone,'current_selection',feeds=', '.join(fn))}\n\n"
        for k in rcs: msg+=gm(phone,k)+"\n"
        if sg:
            sn=[f"#{ID_TO_NUMBER[f]} {FEEDS_DB[f]['name']}" for f in sg if f in FEEDS_DB]
            msg+=f"\nAdd: {', '.join(sn)}\n"
        msg+=f"\n{gm(phone,'ask_confirm_recs')}"
        resp.message(msg)
    else:
        session['state']='calculating'
        resp.message(gm(phone,'calculating'))
        threading.Thread(target=bg_calc,args=(f"whatsapp:{phone}",pk,fids,None),daemon=True).start()

@app.post("/whatsapp")
async def whatsapp_webhook(Body:str=Form(...),From:str=Form(...),NumMedia:str=Form("0"),MediaUrl0:str=Form(""),MediaContentType0:str=Form("")):
    phone=From.replace("whatsapp:",""); txt=Body.strip().upper(); nm=int(NumMedia)
    resp=MessagingResponse()
    if phone not in user_sessions: user_sessions[phone]={'state':'new','lang':'en'}
    s=user_sessions[phone]; st=s.get('state','new')
    if nm>0 and MediaUrl0:
        resp.message(gm(phone,'photo_not_found')); return Response(content=str(resp),media_type="application/xml")
    if MediaContentType0 and 'audio' in MediaContentType0:
        resp.message(gm(phone,'voice_soon')); return Response(content=str(resp),media_type="application/xml")
    if st=='new' or txt in ['START','HI','HELLO','SAWA']:
        s['state']='lang'; resp.message(gm(phone,'welcome')+"\n\n"+gm(phone,'choose_language'))
    elif st=='lang':
        lm={'1':'en','2':'sw','3':'ki','4':'mer'}
        if txt in lm: s['lang']=lm[txt]; s['state']='species'; resp.message(gm(phone,'choose_species'))
        else: resp.message(gm(phone,'invalid_choice')+"\n\n"+gm(phone,'choose_language'))
    elif st=='species':
        if txt=='1': s['species']='pig'; s['state']='profile'; resp.message(gm(phone,'choose_pig'))
        elif txt=='2': s['species']='chicken'; s['state']='profile'; resp.message(gm(phone,'choose_chicken'))
        else: resp.message(gm(phone,'invalid_choice')+"\n\n"+gm(phone,'choose_species'))
    elif st=='profile':
        sp=s.get('species','pig')
        if sp=='pig':
            pm={'1':'p1','2':'p2','3':'p3','4':'p4','5':'p5'}
            if txt in pm: s['profile_key']=pm[txt]; s['state']='feeds'; resp.message(gm(phone,'feed_selection_pig'))
            else: resp.message(gm(phone,'invalid_choice')+"\n\n"+gm(phone,'choose_pig'))
        else:
            pm={'1':'c1','2':'c2','3':'c3','4':'c4','5':'c5','6':'c6'}
            if txt in pm: s['profile_key']=pm[txt]; s['state']='feeds'; resp.message(gm(phone,'feed_selection_chicken'))
            else: resp.message(gm(phone,'invalid_choice')+"\n\n"+gm(phone,'choose_chicken'))
    elif st=='feeds':
        if txt in ['YES','NDIYO','II','NDIO']:
            if s.get('photo_feeds'):
                fids=s['photo_feeds']; s['selected_feeds']=fids; handle_confirm(phone,s,fids,resp)
            else:
                resp.message(gm(phone,'invalid_choice'))
                k='feed_selection_pig' if s.get('species')=='pig' else 'feed_selection_chicken'
                resp.message(gm(phone,k))
        else:
            fids,bad=parse_nums(txt)
            if not fids and bad: resp.message(gm(phone,'unknown_feeds',feeds=', '.join(bad)))
            elif len(fids)<2: resp.message(gm(phone,'select_at_least_2'))
            else:
                s['selected_feeds']=fids; handle_confirm(phone,s,fids,resp)
    elif st=='recommendations':
        if txt in ['YES','NDIYO','II','NDIO']:
            fids=s.get('selected_feeds',[]); rids=s.get('recommended_feeds',[])
            s['state']='calculating'; resp.message(gm(phone,'calculating'))
            threading.Thread(target=bg_calc,args=(f"whatsapp:{phone}",s['profile_key'],fids,rids),daemon=True).start()
        else:
            fids=list(s.get('selected_feeds',[])); nids,bad=parse_nums(txt)
            if nids: fids.extend(nids); s['selected_feeds']=fids; handle_confirm(phone,s,fids,resp)
            else: resp.message(gm(phone,'ask_confirm_recs'))
    elif st=='done': resp.message(gm(phone,'start_again'))
    elif st=='calculating': resp.message("Still calculating...")
    else: resp.message(gm(phone,'generic_help'))
    return Response(content=str(resp),media_type="application/xml")

@app.get("/")
async def root(): return {"bot":"BalancedBora v2.2","status":"running","model":GEMINI_MODEL}
@app.get("/health")
async def health(): return {"status":"ok"}
@app.on_event("startup")
async def startup():
    print("="*50)
    print(f"  BALANCEDBORA v2.2 | Model: {GEMINI_MODEL}")
    print(f"  Twilio: {'OK' if client else 'MISSING'}")
    print(f"  Gemini: {'OK' if gemini_client else 'MISSING'}")
    print("="*50)
if __name__=="__main__":
    import uvicorn
    uvicorn.run(app,host="0.0.0.0",port=8000)

import os
import json
import urllib.parse
import urllib.request
from functools import lru_cache
from concurrent.futures import ThreadPoolExecutor
from flask import Flask, jsonify, request
from flask_cors import CORS
from openai import OpenAI

app = Flask(__name__)
CORS(app)

RECORDS = [
 {"id":"castes-india","title":"Castes in India: Their Mechanism, Genesis and Development","type":"Essay","year":1916,"language":"English","collection":"Writings & Speeches","summary":"Ambedkar’s early scholarly analysis of caste, first presented as an anthropology seminar paper at Columbia University.","excerpt":"The superposition of endogamy on exogamy means the creation of caste.","themes":["Caste","Social reform","Anthropology"],"source":"Dr. Babasaheb Ambedkar: Writings and Speeches, Vol. 1","pages":32,"color":"amber"},
 {"id":"waiting-visa","title":"Waiting for a Visa","type":"Autobiographical notes","year":1935,"language":"English","collection":"Manuscripts","summary":"A set of autobiographical episodes recording Ambedkar’s lived experience of untouchability and exclusion.","excerpt":"The incidents which I am recording in this story are in my experience and are, therefore, true.","themes":["Untouchability","Memory","Human rights"],"source":"Dr. Babasaheb Ambedkar: Writings and Speeches, Vol. 12","pages":20,"color":"blue"},
 {"id":"annihilation-caste","title":"Annihilation of Caste","type":"Book","year":1936,"language":"English","collection":"Rare books","summary":"The undelivered address prepared for the Jat-Pat Todak Mandal, presenting a sustained critique of caste and the conditions required for social democracy.","excerpt":"You cannot build anything on the foundations of caste. You cannot build up a nation, you cannot build up a morality.","themes":["Caste","Liberty","Social democracy"],"source":"Dr. Babasaheb Ambedkar: Writings and Speeches, Vol. 1","pages":96,"color":"red"},
 {"id":"states-minorities","title":"States and Minorities","type":"Memorandum","year":1947,"language":"English","collection":"Constitutional papers","summary":"A memorandum submitted to the Constituent Assembly outlining constitutional safeguards and proposals for the protection of minorities.","excerpt":"The main purpose behind the clause is to put an obligation on the State to plan the economic life of the people.","themes":["Constitution","Minority rights","Economy"],"source":"Dr. Babasaheb Ambedkar: Writings and Speeches, Vol. 1","pages":64,"color":"green"},
 {"id":"constitution-speech","title":"Constituent Assembly Speech, 25 November 1949","type":"Speech","year":1949,"language":"English","collection":"Constituent Assembly Debates","summary":"Ambedkar’s final address before adoption of the Constitution, reflecting on constitutional methods, equality and the future of Indian democracy.","excerpt":"Political democracy cannot last unless there lies at the base of it social democracy.","themes":["Constitution","Democracy","Fraternity"],"source":"Constituent Assembly Debates, Vol. XI","duration":"42 min","color":"violet"},
 {"id":"buddha-dhamma","title":"The Buddha and His Dhamma","type":"Book","year":1957,"language":"English","collection":"Published works","summary":"Published posthumously, this work presents Ambedkar’s interpretation of the Buddha’s life, teaching and social philosophy.","excerpt":"What is necessary is to draw out the implications of his statements and make them explicit.","themes":["Buddhism","Ethics","Equality"],"source":"Dr. Babasaheb Ambedkar: Writings and Speeches, Vol. 11","pages":599,"color":"indigo"}
]

LANGUAGES = {"as":"Assamese","bn":"Bengali","brx":"Bodo","doi":"Dogri","gu":"Gujarati","hi":"Hindi","kn":"Kannada","ks":"Kashmiri","kok":"Konkani","mai":"Maithili","ml":"Malayalam","mni":"Manipuri","mr":"Marathi","ne":"Nepali","or":"Odia","pa":"Punjabi","sa":"Sanskrit","sat":"Santali","sd":"Sindhi","ta":"Tamil","te":"Telugu","ur":"Urdu","en":"English"}
TRANSLATE_CODES = {"kok":"gom","mni":"mni-Mtei","brx":"brx","sat":"sat","or":"or"}

@lru_cache(maxsize=4096)
def translate_text(text, language_code):
    if language_code == "en" or not text.strip():
        return text
    target = TRANSLATE_CODES.get(language_code, language_code)
    params = urllib.parse.urlencode({"client":"gtx","sl":"en","tl":target,"dt":"t","q":text})
    try:
        req = urllib.request.Request("https://translate.googleapis.com/translate_a/single?" + params, headers={"User-Agent":"SMRITI-AI/1.0"})
        with urllib.request.urlopen(req, timeout=8) as response:
            data = json.loads(response.read().decode("utf-8"))
        translated = "".join(part[0] for part in data[0] if part and part[0])
        return translated or text
    except Exception:
        return text
FALLBACK = {
 "as":"আম্বেদকাৰৰ মতে গণতন্ত্ৰ কেৱল চৰকাৰৰ পদ্ধতি নাছিল; ই স্বাধীনতা, সমতা আৰু ভ্ৰাতৃত্বৰ ওপৰত প্ৰতিষ্ঠিত সামাজিক জীৱন-পদ্ধতি আছিল। ২৫ নৱেম্বৰ ১৯৪৯ৰ ভাষণে সামাজিক আৰু অৰ্থনৈতিক অসমতাৰ মাজত ৰাজনৈতিক সমতাৰ বিপদৰ বিষয়ে সতৰ্ক কৰিছিল।",
 "bn":"আম্বেদকরের কাছে গণতন্ত্র কেবল শাসনপদ্ধতি ছিল না; এটি ছিল স্বাধীনতা, সাম্য ও ভ্রাতৃত্বের ভিত্তিতে গড়া সামাজিক জীবনপদ্ধতি। ২৫ নভেম্বর ১৯৪৯-এর ভাষণে তিনি সামাজিক ও অর্থনৈতিক বৈষম্যের মধ্যে রাজনৈতিক সাম্যের বিপদ সম্পর্কে সতর্ক করেন।",
 "brx":"आम्बेदकरनि बाथ्रायाव गनतन्त्रआ खालि खुंथाइनि राहा नङामोन; बेयो उदांथि, समानथि आरो लोगोसे थानायाव सोनारनाय समाजारि जिउनि राहामोन।",
 "doi":"अंबेडकर आस्तै लोकतंत्र सिर्फ सरकार दी प्रणाली नेईं हा; एह् आजादी, बराबरी ते भाईचारे उप्पर टिकी दी सामाजिक जीवन-पद्धति ही। 25 नवंबर 1949 दे भाशण च उने राजनीतिक बराबरी ते सामाजिक-आर्थिक गैरबराबरी दे टकराव बारे चेताया।",
 "gu":"આંબેડકર માટે લોકશાહી માત્ર સરકારની પદ્ધતિ નહોતી; તે સ્વતંત્રતા, સમાનતા અને બંધુત્વ પર આધારિત સામાજિક જીવનપદ્ધતિ હતી. 25 નવેમ્બર 1949ના ભાષણમાં તેમણે રાજકીય સમાનતા અને સામાજિક-આર્થિક અસમાનતા વચ્ચેના વિરોધાભાસ વિશે ચેતવણી આપી હતી.",
 "hi":"आंबेडकर के लिए लोकतंत्र केवल शासन की पद्धति नहीं था; वह स्वतंत्रता, समानता और बंधुत्व पर आधारित सामाजिक जीवन-पद्धति था। 25 नवंबर 1949 के भाषण में उन्होंने राजनीतिक समानता और सामाजिक-आर्थिक असमानता के बीच विरोधाभास के प्रति चेताया।",
 "kn":"ಅಂಬೇಡ್ಕರ್ ಅವರಿಗೆ ಪ್ರಜಾಪ್ರಭುತ್ವವು ಕೇವಲ ಆಡಳಿತ ಪದ್ಧತಿಯಲ್ಲ; ಅದು ಸ್ವಾತಂತ್ರ್ಯ, ಸಮಾನತೆ ಮತ್ತು ಭ್ರಾತೃತ್ವದ ಮೇಲೆ ನಿಂತ ಸಾಮಾಜಿಕ ಜೀವನ ವಿಧಾನವಾಗಿತ್ತು. 25 ನವೆಂಬರ್ 1949ರ ಭಾಷಣದಲ್ಲಿ ರಾಜಕೀಯ ಸಮಾನತೆ ಮತ್ತು ಸಾಮಾಜಿಕ-ಆರ್ಥಿಕ ಅಸಮಾನತೆಯ ವಿರೋಧಾಭಾಸದ ಬಗ್ಗೆ ಅವರು ಎಚ್ಚರಿಸಿದರು.",
 "ks":"امبیڈکرن ہٕندِ نزدیک جمہوریت صرف حکومت ہُنٛد طریقہٕ نہٕ اوس؛ یہِ ٲزادی، برابری تہٕ برادری پؠٹھ قٲیم سماجی زندگی ہُند طریقہٕ اوس۔",
 "kok":"आंबेडकरां खातीर लोकशाय ही फकत राज्यकारभाराची पद्दत नासली; ती स्वातंत्र्य, समता आनी बंधुभावाचेर उबी आशिल्ली समाजीक जिणेची पद्दत आशिल्ली.",
 "mai":"आंबेडकरक लेल लोकतंत्र केवल शासन-पद्धति नहि छल; ई स्वतंत्रता, समानता आ बंधुत्व पर आधारित सामाजिक जीवन-पद्धति छल।",
 "ml":"അംബേദ്കറെ സംബന്ധിച്ചിടത്തോളം ജനാധിപത്യം ഒരു ഭരണരീതി മാത്രമായിരുന്നില്ല; സ്വാതന്ത്ര്യം, സമത്വം, സാഹോദര്യം എന്നിവയിൽ അധിഷ്ഠിതമായ സാമൂഹിക ജീവിതരീതിയായിരുന്നു.",
 "mni":"ꯑꯝꯕꯦꯗꯀꯔꯒꯤꯗꯃꯛ ꯂꯩꯉꯥꯛ ꯆꯠꯅꯕꯤ ꯈꯛꯇ ꯅꯠꯇꯦ; ꯃꯁꯤ ꯅꯤꯡꯇꯝꯕ, ꯃꯥꯟꯅꯕ ꯑꯃꯁꯨꯡ ꯃꯌꯥꯏ ꯀꯥꯡꯂꯨꯞꯇ ꯌꯨꯝꯐꯝ ꯑꯣꯏꯕ ꯈꯨꯟꯅꯥꯏ ꯄꯨꯟꯁꯤꯒꯤ ꯃꯑꯣꯡ ꯑꯃꯅꯤ।",
 "mr":"आंबेडकरांसाठी लोकशाही ही केवळ शासनपद्धती नव्हती; ती स्वातंत्र्य, समता आणि बंधुतेवर आधारलेली सामाजिक जीवनपद्धती होती. 25 नोव्हेंबर 1949 च्या भाषणात त्यांनी राजकीय समता आणि सामाजिक-आर्थिक विषमता यांतील विरोधाभासाबद्दल इशारा दिला.",
 "ne":"अम्बेडकरका लागि लोकतन्त्र केवल शासन प्रणाली थिएन; यो स्वतन्त्रता, समानता र भ्रातृत्वमा आधारित सामाजिक जीवनपद्धति थियो।",
 "or":"ଆମ୍ବେଦକରଙ୍କ ପାଇଁ ଗଣତନ୍ତ୍ର କେବଳ ଶାସନ ପଦ୍ଧତି ନଥିଲା; ଏହା ସ୍ୱାଧୀନତା, ସମାନତା ଓ ଭ୍ରାତୃତ୍ୱ ଉପରେ ଆଧାରିତ ସାମାଜିକ ଜୀବନ ପଦ୍ଧତି ଥିଲା।",
 "pa":"ਅੰਬੇਡਕਰ ਲਈ ਲੋਕਤੰਤਰ ਸਿਰਫ਼ ਸਰਕਾਰ ਦੀ ਪ੍ਰਣਾਲੀ ਨਹੀਂ ਸੀ; ਇਹ ਆਜ਼ਾਦੀ, ਸਮਾਨਤਾ ਅਤੇ ਭਾਈਚਾਰੇ ਉੱਤੇ ਆਧਾਰਿਤ ਸਮਾਜਿਕ ਜੀਵਨ-ਪੱਧਤੀ ਸੀ।",
 "sa":"अम्बेडकरस्य मते लोकतन्त्रं केवलं शासनपद्धतिः नासीत्; तत् स्वतन्त्रता-समानता-बन्धुत्वेषु प्रतिष्ठिता सामाजिकजीवनपद्धतिः आसीत्।",
 "sat":"ᱟᱢᱵᱮᱰᱠᱟᱨ ᱞᱟᱹᱜᱤᱫ ᱜᱚᱱᱚᱛᱚᱱᱛᱨᱚ ᱫᱚ ᱥᱟᱥᱚᱱ ᱨᱮᱭᱟᱜ ᱦᱚᱨ ᱮᱥᱠᱟᱨ ᱵᱟᱝ ᱛᱟᱦᱮᱸᱫ; ᱱᱚᱶᱟ ᱫᱚ ᱥᱟᱫᱷᱤᱱᱛᱟ, ᱥᱚᱢᱟᱱᱛᱟ ᱟᱨ ᱵᱷᱟᱭᱟᱨᱤ ᱨᱮ ᱵᱮᱱᱟᱣ ᱥᱟᱢᱟᱡᱤᱠ ᱡᱤᱭᱚᱱ ᱨᱮᱭᱟᱜ ᱦᱚᱨ ᱠᱟᱱᱟ।",
 "sd":"امبيڊڪر لاءِ جمهوريت رڳو حڪومت جو طريقو نه هئي؛ اها آزادي، برابري ۽ ڀائيچاري تي ٻڌل سماجي زندگيءَ جو طريقو هئي۔",
 "ta":"அம்பேத்கருக்கு ஜனநாயகம் என்பது வெறும் ஆட்சி முறை அல்ல; அது சுதந்திரம், சமத்துவம், சகோதரத்துவம் ஆகியவற்றின் அடிப்படையிலான சமூக வாழ்க்கை முறை.",
 "te":"అంబేడ్కర్‌కు ప్రజాస్వామ్యం కేవలం పాలనా విధానం కాదు; అది స్వేచ్ఛ, సమానత్వం, సౌభ్రాతృత్వంపై ఆధారపడిన సామాజిక జీవన విధానం.",
 "ur":"امبیڈکر کے نزدیک جمہوریت محض طرزِ حکومت نہیں تھی؛ یہ آزادی، مساوات اور اخوت پر قائم سماجی طرزِ زندگی تھی۔",
 "en":"For Ambedkar, democracy was more than a form of government. It was a way of social life grounded in liberty, equality and fraternity. In his 25 November 1949 address, he warned about the contradiction between political equality and social and economic inequality."
}

@app.get("/api/health")
def health(): return jsonify({"status":"ok","service":"SMRITI AI archive"})

@app.get("/api/records")
def records():
    query = request.args.get("q", "").lower().strip()
    found = RECORDS if not query else [r for r in RECORDS if query in (r["title"]+r["summary"]+" ".join(r["themes"])).lower()]
    return jsonify({"records": found, "total": len(found)})

@app.get("/api/records/<record_id>")
def record(record_id):
    item = next((r for r in RECORDS if r["id"] == record_id), None)
    return (jsonify(item), 200) if item else (jsonify({"error":"Record not found"}), 404)

@app.post("/api/translate")
def translate():
    payload = request.get_json(silent=True) or {}
    language_code = str(payload.get("language", "en"))
    texts = payload.get("texts", [])
    if language_code not in LANGUAGES or not isinstance(texts, list):
        return jsonify({"error":"Invalid translation request"}), 400
    clean = [str(text)[:1800] for text in texts[:50]]
    with ThreadPoolExecutor(max_workers=8) as pool:
        translations = list(pool.map(lambda text: translate_text(text, language_code), clean))
    return jsonify({"language":language_code,"translations":translations})

@app.post("/api/ask")
def ask():
    payload = request.get_json(silent=True) or {}
    raw_question = str(payload.get("question", "")).strip()
    question = raw_question.lower()
    language_code = str(payload.get("language", "en"))
    language_name = LANGUAGES.get(language_code, "English")
    topic = "general"
    if any(w in question for w in ["social democracy", "democracy", "equality", "fraternity"]):
        topic = "democracy"
        answer = "For Ambedkar, democracy was more than a form of government. In his 25 November 1949 address, he described social democracy as a way of life grounded in liberty, equality and fraternity. His warning was practical: political equality could remain fragile while social and economic life continued to be marked by deep inequality. Read together with Annihilation of Caste, the archive shows that democratic institutions required a transformed social order, not only constitutional rules."
        ids=["constitution-speech","annihilation-caste"]
    elif any(w in question for w in ["caste", "annihilation", "untouchability"]):
        topic = "caste"
        answer = "Across Castes in India, Waiting for a Visa and Annihilation of Caste, Ambedkar treated caste as a system reproduced through social rules and enforced through everyday exclusion. His argument moved from analysis to remedy: reform required dismantling the authority and practices that sustained graded inequality."
        ids=["castes-india","waiting-visa","annihilation-caste"]
    elif any(w in question for w in ["constitution", "constitutional", "minority", "rights"]):
        topic = "constitution"
        answer = "The selected constitutional records show Ambedkar linking legal safeguards to social conditions. States and Minorities proposed enforceable protections and economic obligations, while his final Constituent Assembly address stressed constitutional methods and warned that institutions could not remain secure without social democracy."
        ids=["states-minorities","constitution-speech"]
    elif any(w in question for w in ["buddha", "buddhism", "dhamma"]):
        topic = "buddhism"
        answer = "In The Buddha and His Dhamma, Ambedkar presented Dhamma as an ethical and social practice concerned with right relations among people. Within this archive, it connects to his longer search for a moral order based on reason, dignity and equality."
        ids=["buddha-dhamma"]
    else:
        answer = "The current demonstration archive contains records on caste, democracy, constitutional safeguards, minority rights and Buddhism. Try asking how Ambedkar understood social democracy, why he criticised caste, or what concerns he raised before the Constitution was adopted."
        ids=["constitution-speech","annihilation-caste"]
    citations=[]
    for n, rid in enumerate(ids, 1):
        r=next(x for x in RECORDS if x["id"]==rid)
        citations.append({"number":n,"id":rid,"title":r["title"],"source":r["source"]})
    api_key = os.getenv("OPENAI_API_KEY")
    mode = "curated-multilingual-fallback"
    if api_key and raw_question:
        try:
            passages = []
            for number, record_id in enumerate(ids, 1):
                archive_record = next(item for item in RECORDS if item["id"] == record_id)
                passages.append(f"[{number}] {archive_record['title']}: {archive_record['summary']} Source: {archive_record['source']}")
            client = OpenAI(api_key=api_key)
            response = client.responses.create(
                model=os.getenv("OPENAI_MODEL", "gpt-4.1-mini"),
                store=False,
                instructions=f"You are SMRITI, an evidence-grounded research assistant about Dr. B. R. Ambedkar. Answer entirely in {language_name}, using its native script. Use only the supplied archive evidence. Do not invent quotations, dates, page numbers, or facts. Cite supporting evidence inline as [1], [2]. If evidence is insufficient, say so clearly in {language_name}.",
                input=f"Visitor question: {raw_question}\n\nArchive evidence:\n" + "\n\n".join(passages),
            )
            answer = response.output_text
            mode = "openai-grounded-multilingual"
        except Exception:
            answer = FALLBACK.get(language_code, answer)
    elif language_code != "en":
        answer = FALLBACK.get(language_code, answer) if topic == "democracy" else translate_text(answer, language_code)
    return jsonify({"answer":answer,"citations":citations,"mode":mode,"language":language_code,"language_name":language_name})

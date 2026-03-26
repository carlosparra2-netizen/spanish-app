import streamlit as st
import json
import time
import random
from datetime import datetime

# ── Google Drive & Docs ───────────────────────────────────
PROJECT_ID   = "spanish-app-490602"
CLIENT_EMAIL = "spanish-app-service@spanish-app-490602.iam.gserviceaccount.com"
FOLDER_NAME  = "Español App"

def get_drive_service():
    try:
        from google.oauth2.service_account import Credentials
        from googleapiclient.discovery import build
        creds_dict = dict(st.secrets["gcp_service_account"])
        creds = Credentials.from_service_account_info(
            creds_dict,
            scopes=[
                "https://www.googleapis.com/auth/drive",
                "https://www.googleapis.com/auth/documents",
            ]
        )
        drive = build("drive", "v3", credentials=creds)
        docs  = build("docs",  "v1", credentials=creds)
        return drive, docs
    except Exception:
        return None, None

def get_or_create_folder(drive, name):
    try:
        q = f"name='{name}' and mimeType='application/vnd.google-apps.folder' and trashed=false"
        res = drive.files().list(q=q, fields="files(id,name)").execute()
        files = res.get("files", [])
        if files:
            return files[0]["id"]
        meta = {"name": name, "mimeType": "application/vnd.google-apps.folder"}
        folder = drive.files().create(body=meta, fields="id").execute()
        return folder["id"]
    except Exception:
        return None

def create_student_doc(drive, docs, folder_id, student_name, task_id, level, title, prompt_text, rubric, target, response_text, ai_feedback):
    try:
        doc_title = f"{student_name} — {task_id} {title}"
        doc = docs.documents().create(body={"title": doc_title}).execute()
        doc_id  = doc["documentId"]
        doc_url = f"https://docs.google.com/document/d/{doc_id}/edit"

        drive.files().update(
            fileId=doc_id,
            addParents=folder_id,
            fields="id, parents"
        ).execute()

        now_str = datetime.now().strftime("%B %d, %Y — %I:%M %p")

        feedback_section = ai_feedback if ai_feedback else "⚠️ AI feedback not available (API key not configured)."

        full_text = (
            f"Student: {student_name}\n"
            f"Task: {task_id} · {level} · {title}\n"
            f"Date: {now_str}\n"
            f"Target: {target}\n"
            f"{'─'*60}\n\n"
            f"PROMPT:\n{prompt_text}\n\n"
            f"{'─'*60}\n\n"
            f"AAPPL CHECKLIST:\n{rubric}\n\n"
            f"{'─'*60}\n\n"
            f"STUDENT RESPONSE:\n\n{response_text}\n\n"
            f"{'─'*60}\n\n"
            f"AI FEEDBACK (Claude):\n\n{feedback_section}\n"
        )

        docs.documents().batchUpdate(
            documentId=doc_id,
            body={"requests": [{"insertText": {"location": {"index": 1}, "text": full_text}}]}
        ).execute()

        return doc_url, doc_id
    except Exception as e:
        return None, None

def list_student_docs(drive, folder_id):
    try:
        q = f"'{folder_id}' in parents and trashed=false"
        res = drive.files().list(
            q=q,
            fields="files(id,name,createdTime,webViewLink)",
            orderBy="createdTime desc"
        ).execute()
        return res.get("files", [])
    except Exception:
        return []

# ── AI Feedback ───────────────────────────────────────────
def get_ai_feedback(student_name, task_id, level, title, prompt_text, rubric, target, response_text):
    """Call Claude API to get writing feedback. Returns (feedback_text, error_msg)."""
    import anthropic

    # Robust key reading — try all methods
    api_key = None
    try:
        api_key = str(st.secrets["anthropic_api_key"]).strip()
    except Exception:
        pass
    if not api_key:
        try:
            api_key = str(st.secrets.get("anthropic_api_key", "")).strip()
        except Exception:
            pass
    if not api_key:
        try:
            # Sometimes Streamlit wraps secrets in a dict-like object
            for k, v in st.secrets.items():
                if k == "anthropic_api_key":
                    api_key = str(v).strip()
                    break
        except Exception:
            pass
    if not api_key or api_key == "None":
        return None, "NO_KEY"

    try:
        client = anthropic.Anthropic(api_key=api_key)

        system_prompt = """You are an expert Spanish teacher evaluating writing from 7th grade students who are native English speakers learning Spanish as a foreign language.

CRITICAL RULES:
- Always respond ENTIRELY in English — never in Spanish
- NEVER rewrite or correct the student's Spanish text
- NEVER show corrected versions of their sentences
- Instead, describe what they should improve WITHOUT rewriting it for them
- Be encouraging, specific, and constructive
- Keep your response between 120 and 180 words"""

        user_prompt = f"""Evaluate this Spanish writing from a 7th grade English-speaking student learning Spanish.

TASK: {task_id} — {title} ({level})
PROMPT GIVEN TO STUDENT: {prompt_text}
AAPPL CRITERIA: {rubric}
WORD COUNT TARGET: {target}

STUDENT'S RESPONSE:
{response_text}

Give feedback in these three sections:
1. ✅ What you did well (2-3 specific strengths from their writing)
2. 📝 What to improve (2-3 suggestions — describe the issue but do NOT rewrite their sentences)
3. 🎯 Approximate AAPPL level for this response

Remember: respond in English only. Do not correct or rewrite any Spanish."""

        message = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=600,
            messages=[{"role": "user", "content": user_prompt}],
            system=system_prompt
        )
        return message.content[0].text, None
    except Exception as e:
        return None, str(e)

# ── Page config ───────────────────────────────────────────
st.set_page_config(
    page_title="¡Español! Spanish Practice",
    page_icon="🇪🇸",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ── Custom CSS ────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Fraunces:wght@700;900&family=DM+Sans:wght@400;500;600&display=swap');

html, body, [class*="css"] { font-family: 'DM Sans', sans-serif; }

p, li, span, div, label, h1, h2, h3, h4, h5 { color: #1a1a2e !important; }
.stMarkdown p, .stMarkdown li { color: #1a1a2e !important; }
.stTextArea label { color: #1a1a2e !important; }
.stSelectbox label { color: #1a1a2e !important; }

.main-title { color: #1b3a6b !important; }
.main-sub   { color: #4a5568 !important; }
.prompt-box {
    background: #f8fafc; border: 1px solid #cbd5e0;
    border-radius: 16px; padding: 1.5rem;
    font-size: 1.05rem; line-height: 1.8; color: #1a1a2e !important;
}
.prompt-box p, .prompt-box li, .prompt-box ol, .prompt-box br { color: #1a1a2e !important; }
.badge {
    display: inline-block; padding: 0.2rem 0.8rem;
    border-radius: 100px; font-size: 0.75rem; font-weight: 700;
    margin-bottom: 0.5rem;
}
.badge-green  { background: rgba(16,185,129,0.12); color: #047857 !important; border: 1px solid rgba(16,185,129,0.3); }
.badge-yellow { background: rgba(217,119,6,0.12);  color: #92400e !important; border: 1px solid rgba(217,119,6,0.3); }
.badge-red    { background: rgba(220,38,38,0.1);   color: #991b1b !important; border: 1px solid rgba(220,38,38,0.3); }
.badge-purple { background: rgba(109,40,217,0.1);  color: #5b21b6 !important; border: 1px solid rgba(109,40,217,0.3); }
.badge-teal   { background: rgba(13,148,136,0.1);  color: #0f766e !important; border: 1px solid rgba(13,148,136,0.3); }

.tips-item {
    background: rgba(220,38,38,0.06);
    border: 1px solid rgba(220,38,38,0.2);
    border-radius: 10px; padding: 0.6rem 0.9rem;
    margin-bottom: 0.4rem; font-size: 0.9rem;
    color: #7f1d1d !important;
}
.timer-big {
    font-family: 'Fraunces', serif;
    font-size: 2.8rem; font-weight: 900;
    text-align: center; padding: 0.5rem;
    border-radius: 12px; margin-bottom: 0.5rem;
}
.timer-green  { color: #047857 !important; background: rgba(16,185,129,0.08); border: 1px solid rgba(16,185,129,0.2); }
.timer-yellow { color: #92400e !important; background: rgba(217,119,6,0.08);  border: 1px solid rgba(217,119,6,0.2); }
.timer-red    { color: #991b1b !important; background: rgba(220,38,38,0.08);  border: 1px solid rgba(220,38,38,0.3); }

.word-count { font-size: 0.85rem; color: #4a5568 !important; margin-top: 0.3rem; }
.word-good  { color: #047857 !important; font-weight: 600; }
.word-over  { color: #991b1b !important; font-weight: 600; }

.feedback-box {
    background: #f0fdf4; border: 1px solid #86efac;
    border-radius: 16px; padding: 1.4rem;
    font-size: 0.95rem; line-height: 1.8; color: #1a1a2e !important;
    margin-top: 1rem;
}
.feedback-box p, .feedback-box li { color: #1a1a2e !important; }
.feedback-title {
    font-weight: 700; font-size: 1rem;
    color: #047857 !important; margin-bottom: 0.6rem;
}

.flashcard-front {
    background: #f0f4ff; border: 2px solid #c7d2fe;
    border-radius: 20px; padding: 2.5rem;
    text-align: center; min-height: 160px;
    display: flex; flex-direction: column;
    align-items: center; justify-content: center;
}
.flashcard-word {
    font-family: 'Fraunces', serif;
    font-size: 2.5rem; font-weight: 700; color: #1b3a6b !important;
}
.flashcard-back {
    background: #fefce8; border: 2px solid #fde68a;
    border-radius: 20px; padding: 2.5rem; text-align: center;
}
.flashcard-back * { color: #1a1a2e !important; }

/* ── Textarea — spell-check & autocorrect disabled ── */
.stTextArea textarea {
    background: #ffffff !important;
    border: 2px solid #c7d2fe !important;
    color: #1a1a2e !important;
    border-radius: 12px !important;
    font-family: 'DM Sans', sans-serif !important;
    font-size: 1rem !important;
    line-height: 1.7 !important;
    pointer-events: auto !important;
    cursor: text !important;
    spellcheck: false;
    -webkit-spell-check: false;
}
.stTextArea textarea:focus {
    border-color: #4f46e5 !important;
    box-shadow: 0 0 0 3px rgba(79,70,229,0.15) !important;
}
.stTextArea textarea:disabled {
    background: #f1f5f9 !important;
    color: #94a3b8 !important;
    cursor: not-allowed !important;
}

.stButton > button {
    border-radius: 10px !important;
    font-family: 'DM Sans', sans-serif !important;
    font-weight: 600 !important;
    font-size: 1.1rem !important;
}

/* ── Special char buttons — bigger touch targets ── */
div[data-testid="column"] .stButton > button {
    font-size: 1.3rem !important;
    font-weight: 700 !important;
    padding: 0.4rem 0 !important;
    min-height: 3rem !important;
    background-color: #4f46e5 !important;
    color: white !important;
    border: none !important;
}
div[data-testid="column"] .stButton > button:hover {
    background-color: #3730a3 !important;
}
</style>

<script>
// ── Disable spell-check & autocorrect aggressively ──
function disableSpellCheck() {
    document.querySelectorAll('textarea, input[type="text"], input:not([type])').forEach(function(el) {
        el.setAttribute('spellcheck', 'false');
        el.setAttribute('autocorrect', 'off');
        el.setAttribute('autocomplete', 'off');
        el.setAttribute('autocapitalize', 'off');
        el.setAttribute('data-gramm', 'false');
        el.setAttribute('data-gramm_editor', 'false');
        el.setAttribute('data-enable-grammarly', 'false');
    });
}
// Run immediately, on interval, and on DOM changes
disableSpellCheck();
setInterval(disableSpellCheck, 500);
const _obs = new MutationObserver(disableSpellCheck);
_obs.observe(document.body, { childList: true, subtree: true });
</script>
""", unsafe_allow_html=True)

# ═══════════════════════════════════════════════════════════
# DATA
# ═══════════════════════════════════════════════════════════

VOCAB_SETS = {
    "La Casa": [
        ("la ventana","the window","La ventana está abierta."),
        ("el tejado","the roof","El tejado es de tejas rojas."),
        ("la escalera","the staircase","Subo las escaleras al segundo piso."),
        ("el sótano","the basement","Guardamos las cajas en el sótano."),
        ("el pasillo","the hallway","El pasillo es muy largo."),
        ("la chimenea","the fireplace","Hay fuego en la chimenea."),
        ("la alfombra","the rug/carpet","La alfombra es suave."),
        ("el armario","the closet","Mi ropa está en el armario."),
    ],
    "La Comida": [
        ("las fresas","strawberries","Me encantan las fresas con crema."),
        ("el aguacate","avocado","El guacamole tiene aguacate."),
        ("los mariscos","seafood","Los mariscos son típicos en la costa."),
        ("la masa","dough","La masa para el pan está lista."),
        ("asado/a","roasted/grilled","El pollo asado huele muy bien."),
        ("crudo/a","raw","No me gusta comer el pescado crudo."),
        ("la receta","the recipe","Sigo la receta de mi abuela."),
        ("el sabor","flavor/taste","El sabor de esta sopa es increíble."),
    ],
    "El Tiempo": [
        ("la tormenta","the storm","Hay una tormenta esta noche."),
        ("la niebla","the fog","No veo nada con esta niebla."),
        ("el granizo","hail","El granizo dañó los autos."),
        ("húmedo/a","humid","El verano aquí es muy húmedo."),
        ("despejado/a","clear/sunny","Hoy el cielo está despejado."),
        ("helar","to freeze","Va a helar esta noche."),
        ("el relámpago","lightning","Vi un relámpago en el horizonte."),
        ("la sequía","drought","La sequía afecta a los agricultores."),
    ],
    "Los Viajes": [
        ("el equipaje","luggage","Perdí mi equipaje en el aeropuerto."),
        ("el pasaporte","passport","Necesito renovar mi pasaporte."),
        ("el vuelo","flight","El vuelo dura tres horas."),
        ("el alojamiento","accommodation","Buscamos alojamiento en el centro."),
        ("el itinerario","itinerary","El itinerario incluye cinco ciudades."),
        ("el destino","destination","¿Cuál es tu destino favorito?"),
        ("reservar","to book/reserve","Voy a reservar el hotel ahora."),
        ("el turista","tourist","Hay muchos turistas en verano."),
    ],
    "Las Emociones": [
        ("agotado/a","exhausted","Estoy agotada después de correr."),
        ("orgulloso/a","proud","Estoy orgulloso de mi trabajo."),
        ("celoso/a","jealous","No seas tan celoso."),
        ("asustado/a","scared","Estaba asustada en el laberinto."),
        ("avergonzado/a","embarrassed","Me sentí avergonzado frente a todos."),
        ("esperanzado/a","hopeful","Estoy esperanzada con los resultados."),
        ("decepcionado/a","disappointed","Estoy decepcionado con la película."),
        ("aliviado/a","relieved","Me sentí aliviada al ver las notas."),
    ],
    "La Tecnología": [
        ("la contraseña","password","Olvidé mi contraseña del correo."),
        ("la pantalla","screen","La pantalla de mi teléfono se rompió."),
        ("descargar","to download","Voy a descargar la aplicación ahora."),
        ("la red","network/internet","No hay red en este lugar."),
        ("la aplicación","app","Uso esa aplicación todos los días."),
        ("el teclado","keyboard","El teclado de mi laptop está roto."),
        ("guardar","to save","Guarda el documento antes de cerrar."),
        ("el archivo","file","Envíame el archivo por correo."),
    ],
    "La Naturaleza": [
        ("el bosque","forest/woods","Caminamos por el bosque al amanecer."),
        ("la cascada","waterfall","La cascada es impresionante."),
        ("el río","river","El río está muy crecido hoy."),
        ("la montaña","mountain","Subimos la montaña en dos horas."),
        ("el desierto","desert","El desierto de noche es muy frío."),
        ("la costa","coast","La costa de Maine es rocosa."),
        ("la pradera","meadow/prairie","Las vacas pastan en la pradera."),
        ("el volcán","volcano","El volcán entró en erupción."),
    ],
    "La Escuela": [
        ("el horario","schedule","Mi horario cambia cada semestre."),
        ("el recreo","recess/break","Jugamos fútbol en el recreo."),
        ("la nota","grade/mark","Saqué buena nota en el examen."),
        ("el ensayo","essay","Escribí un ensayo sobre la historia."),
        ("el repaso","review","Hicimos repaso antes del examen."),
        ("la matrícula","enrollment","La matrícula cierra el viernes."),
        ("el compañero","classmate","Mi compañero me ayudó con el proyecto."),
        ("los deberes","homework","Tengo muchos deberes esta semana."),
    ],
}

GRAMMAR_QUESTIONS = [
    ("Ser vs. Estar","Mi hermana ___ muy inteligente.",["es","está","son","estás"],0,"'Es' — permanent traits like personality use 'ser'."),
    ("Ser vs. Estar","El libro ___ encima de la mesa.",["es","somos","está","estoy"],2,"'Está' — location of objects uses 'estar'."),
    ("Preterite","Ayer yo ___ al parque con mi familia.",["voy","fui","iba","iré"],1,"'Fui' — preterite of 'ir', completed past action."),
    ("Preterite","Ella ___ la cena a las ocho.",["come","comió","comía","comerá"],1,"'Comió' — specific completed action in the past."),
    ("Imperfect","Cuando era niño, siempre ___ helado los domingos.",["como","comí","comía","comeré"],2,"'Comía' — imperfect for habitual past actions."),
    ("Reflexive","Todos los días me ___ a las siete.",["levanta","levanto","levantas","levantamos"],1,"'Me levanto' — reflexive verb, yo form."),
    ("Direct Object","___ vi ayer en el mercado.",["Lo","Le","Se","Me"],0,"'Lo' = direct object pronoun, masculine singular."),
    ("Subjunctive","Espero que tú ___ bien mañana.",["estás","estar","estés","estabas"],2,"'Espero que' triggers subjunctive → 'estés'."),
    ("Por vs. Para","Compré flores ___ mi mamá.",["por","para","con","de"],1,"'Para' = intended for a recipient."),
    ("Por vs. Para","Caminé ___ el parque toda la tarde.",["para","de","por","hacia"],2,"'Por' = through/along a place."),
    ("Preterite","Nosotros ___ la película tres veces.",["vemos","vimos","veíamos","veremos"],1,"'Vimos' — preterite of 'ver'."),
    ("Ser vs. Estar","La fiesta ___ en casa de María.",["es","está","ser","estamos"],0,"'Es' — location of events uses 'ser'."),
    ("Imperfect","Antes, mi abuelo ___ en el campo.",["vivió","vivía","vive","vivirá"],1,"'Vivía' — imperfect for past states."),
    ("Subjunctive","Es importante que ustedes ___ los deberes.",["hagan","hacen","hicieron","harán"],0,"'Es importante que' + subjunctive → 'hagan'."),
    ("Por vs. Para","Gracias ___ tu ayuda.",["para","por","con","de"],1,"'Por' = gratitude, reason/cause."),
]

SPEAKING_PROMPTS = [
    ("Personal","Describe tu rutina de un día normal de escuela. ¿Qué es lo primero que haces cuando llegas a casa?","Use present tense verbs: llego, como, hago, veo..."),
    ("Personal","¿Cuál es tu comida favorita y por qué? ¿Quién la prepara en tu familia?","Use ser/estar and adjectives: deliciosa, picante, dulce..."),
    ("Personal","Habla sobre un momento en que te sentiste muy orgulloso/a. ¿Qué pasó?","Use preterite: sentí, logré, gané..."),
    ("Opinion","¿Crees que las escuelas deberían tener uniformes? Da dos razones.","En mi opinión... / Creo que... / Por un lado..."),
    ("Opinion","¿Los estudiantes deberían tener más o menos tarea? Explica.","Use debería / deberían + infinitive."),
    ("Opinion","¿Es mejor vivir en una ciudad grande o en un pueblo pequeño?","Comparatives: más tranquilo que / menos contaminada que..."),
    ("Storytelling","Continúa: 'Cuando abrí la puerta del sótano, vi algo que nunca olvidaré...'","Imperfect for setting + preterite for events."),
    ("Storytelling","Inventa el comienzo de una novela. Preséntanos al personaje principal.","¿Cómo es? ¿Dónde vive? ¿Qué quiere? ¿Qué problema tiene?"),
    ("Debate","Convence a tu clase de que aprender español es más útil que aprender a programar.","Es evidente que / sin duda / no se puede negar que..."),
    ("Debate","Eres el alcalde. Explica por qué construirías un parque nuevo en vez de un estacionamiento.","Use futuro: construiré, habrá, podrán, tendremos..."),
]

WRITING_TASKS = {
    "👤 Personal": [
        ("P-01","Novice High","Introduce yourself to a pen pal",
         "Write an e-mail to a new pen pal in another country. Introduce yourself and write four facts about yourself.\n\n💡 Tip: Include your name, age, where you live, and one hobby or interest.",
         "60–90 words", 60, 90,
         "Include name, age, location • 1 hobby/interest • 4 clear facts • E-mail format"),
        ("P-02","Novice High","E-mail to a new teacher",
         "Write an e-mail to a new teacher. Introduce yourself and share four things that are important for your teacher to know about you.\n\n💡 Tip: Think about learning style, interests, goals, or anything personal.",
         "60–90 words", 60, 90,
         "4 things teacher should know • Personal and specific • Appropriate register"),
        ("P-03","Intermediate Low","Yearbook bio",
         "Write a short bio for a school yearbook. Include four facts that describe who you are as a student and as a person.",
         "70–100 words", 70, 100,
         "4 facts as student & person • Descriptive language • Organized structure"),
        ("P-04","Intermediate Low","E-mail to an exchange student",
         "An exchange student is coming to live with your family for one month. Write an e-mail introducing yourself and explaining four things you enjoy doing at home.",
         "80–110 words", 80, 110,
         "4 home activities with details • Welcoming tone • Connect to your personality"),
        ("P-05","Novice High","Daily routine facts",
         "Write four facts about your daily routine that you would share with someone who does not know you.",
         "60–80 words", 60, 80,
         "4 routine facts • Present tense verbs • Specific times/details"),
        ("P-06","Intermediate Low","Sports app profile",
         "You are creating a profile for a student sports app. Write a short introduction about yourself and describe four activities or sports that are part of your life.",
         "80–110 words", 80, 110,
         "Self-introduction • 4 sports/activities • Explain why each matters to you"),
        ("P-07","Novice High","E-mail about four friends",
         "Write an e-mail in which you name four friends and explain one interesting thing about each of them.",
         "70–100 words", 70, 100,
         "4 friends named • 1 interesting fact each • Variety of descriptions"),
        ("P-08","Intermediate Low","Describe four family members",
         "Describe four members of your family. For each person, explain what they do and why they are important to you.",
         "90–120 words", 90, 120,
         "4 family members • What each does • Why each is important to you"),
        ("P-09","Intermediate Low","E-mail to Maria about your friends",
         "Write an e-mail to Maria describing your four closest friends. Explain what you have in common with each one and why you enjoy spending time with them.",
         "100–130 words", 100, 130,
         "4 friends described • Something in common • Why you enjoy time with them"),
        ("P-10","Novice High","People who have influenced you",
         "Name four people who have influenced your life. Write one sentence about each person explaining why they matter to you.",
         "60–80 words", 60, 80,
         "4 people named • 1 sentence each • Explain why they matter"),
    ],
    "❓ Questions": [
        ("Q-01","Novice High","Questions for a new student",
         "Write four questions you would like to ask a new student who just moved to your school. Try to ask questions that require more than a yes/no answer.\n\n💡 Tip: Use 'why,' 'how,' 'what kind,' and 'tell me about…'",
         "50–80 words", 50, 80,
         "4 open-ended questions • No yes/no questions • Variety of question words"),
        ("Q-02","Novice High","Interview the school principal",
         "You are going to interview your school principal for the school newspaper. Write four questions about life at your school.",
         "50–80 words", 50, 80,
         "4 questions about school life • Formal register • Go beyond basic facts"),
        ("Q-03","Intermediate Low","Questions for Maria about moving",
         "Write four questions for Maria about her experience moving from another country to the United States. Ask for opinions and feelings, not just facts.",
         "60–90 words", 60, 90,
         "4 questions • Ask for opinions and feelings • No simple fact questions"),
        ("Q-04","Intermediate Low","Questions for a family member",
         "Write four questions for a family member about their childhood. Your questions should invite them to share stories and memories, not just dates or places.",
         "60–90 words", 60, 90,
         "4 questions inviting stories • Open-ended and reflective • Invite memories"),
        ("Q-05","Intermediate Low","Questions for a professional athlete",
         "A professional athlete is visiting your school. Write four questions about their career, training, and personal life.\n\n💡 Tip: Ask about challenges, sacrifices, and what success means to them.",
         "60–90 words", 60, 90,
         "4 deep questions • Career, training, personal life • Beyond salary/schedule"),
        ("Q-06","Intermediate Mid","Teen life survey questions",
         "You are writing questions for a survey about teen life in America. Write four questions that help understand how teenagers balance school, social life, and personal goals.",
         "70–100 words", 70, 100,
         "4 survey questions • School, social life, and goals • Invite thoughtful responses"),
        ("Q-07","Novice High","Questions about a career",
         "Write four questions about a job or career that interests you. Go beyond just asking what the job pays or what hours it requires.",
         "50–80 words", 50, 80,
         "4 career questions • Go beyond pay and hours • Ask about challenges and meaning"),
        ("Q-08","Intermediate Low","Questions for Maria about a holiday",
         "Write four questions for Maria about her favorite holiday tradition. Make sure your questions encourage her to describe, compare, and reflect — not just list facts.",
         "60–90 words", 60, 90,
         "4 questions • Description, comparison, and reflection • Not just listing facts"),
    ],
    "📍 Places": [
        ("C-01","Novice High","Things to do in your town",
         "Write an e-mail listing four things to do or places to visit in your town. For each one, say why someone would enjoy it.",
         "70–100 words", 70, 100,
         "4 places/activities • Explain why each is enjoyable • E-mail format"),
        ("C-02","Intermediate Low","Weekend visit plans",
         "A friend from another state is visiting you for the weekend. Write an e-mail describing four places you plan to take them and explaining what makes each place special.",
         "90–120 words", 90, 120,
         "4 places described • What makes each special • Welcoming and personal tone"),
        ("C-03","Intermediate Low","Fitness activities in your community",
         "Write about four fitness activities that people in your community enjoy. Describe each activity and explain where or when people do it.",
         "80–110 words", 80, 110,
         "4 fitness activities • Where/when each happens • Descriptive details"),
        ("C-04","Intermediate Mid","Recommend your town",
         "Write an e-mail recommending your town to a student who is thinking about moving there. Include four specific reasons why your town is a good place to grow up.",
         "100–130 words", 100, 130,
         "4 specific reasons • Persuasive tone • Details and examples for each"),
        ("C-05","Intermediate Low","What your town needs",
         "List four things you wish your town had more of. For each item, explain what it is and why it would improve life for students your age.",
         "80–110 words", 80, 110,
         "4 things your town needs • Explain what each is • Why it would help students"),
        ("C-06","Novice High","Healthy activities at school",
         "Describe four activities available at your school or in your neighborhood that help students stay active and healthy.",
         "60–90 words", 60, 90,
         "4 activities described • Connection to health • Where/when available"),
    ],
    "🇺🇸 Life in America": [
        ("E-01","Intermediate Mid","Shopping",
         "This is a 3-part task. Address ALL three parts:\n\n1. Explain what a shopping mall is to someone who has never been to one.\n2. Describe in detail the layout and overall organization of your favorite mall.\n3. Relate a personal experience you had at that mall. Tell the whole story and explain why it was memorable.",
         "150–200 words", 150, 200,
         "All 3 parts addressed • Explanation + description + narrative • Past tense in part 3"),
        ("E-02","Intermediate Mid","Holidays and celebrations",
         "This is a 3-part task. Address ALL three parts:\n\n1. Explain what a typical American holiday celebration looks like to someone from another culture.\n2. Describe how your family or community celebrates one specific holiday.\n3. Share a personal memory from that celebration. Tell the complete story and explain why it is meaningful.",
         "150–200 words", 150, 200,
         "All 3 parts addressed • Cultural explanation • Detailed description • Personal narrative"),
        ("E-03","Intermediate Mid","School sports",
         "This is a 3-part task. Address ALL three parts:\n\n1. Explain what school sports teams are and their role in American school life.\n2. Describe your favorite school sport or team in detail, including how practices and games are organized.\n3. Describe one specific game, competition, or practice you remember well. Tell the whole story.",
         "150–200 words", 150, 200,
         "All 3 parts addressed • General → specific → personal • Vivid details in part 3"),
        ("E-04","Intermediate Mid","Social media and technology",
         "This is a 3-part task. Address ALL three parts:\n\n1. Explain how social media fits into the daily life of American teenagers.\n2. Describe how you or your peers use one specific platform — how often, for what purpose, and with whom.\n3. Write about one experience connected to social media that taught you something. Tell the full story.",
         "150–200 words", 150, 200,
         "All 3 parts addressed • General → specific use → personal experience"),
        ("E-05","Intermediate Mid","Volunteering and community service",
         "This is a 3-part task. Address ALL three parts:\n\n1. Explain what community service is and why it is encouraged in American schools.\n2. Describe one volunteer activity or project that students at your school participate in.\n3. Write about a personal experience you had while volunteering. Tell the complete story and explain what you learned.",
         "150–200 words", 150, 200,
         "All 3 parts addressed • Definition + example + personal narrative • Lesson learned"),
        ("E-06","Intermediate Mid","Family traditions",
         "This is a 3-part task. Address ALL three parts:\n\n1. Explain what family traditions are and why they are important in American culture.\n2. Describe one specific tradition your family follows — when it happens, who participates, and what activities are involved.\n3. Tell the story of one time that tradition was especially meaningful. Explain what happened and why it affected you.",
         "150–200 words", 150, 200,
         "All 3 parts addressed • Explanation → specific tradition → personal memory"),
        ("E-07","Intermediate Mid","School clubs",
         "This is a 3-part task. Address ALL three parts:\n\n1. Explain what school clubs are to someone from another country.\n2. Describe your favorite school club and explain how its schedule of activities is organized.\n3. Write about one specific experience you had as a member of that club. Tell the whole story and explain why you remember it.",
         "150–200 words", 150, 200,
         "All 3 parts addressed • Explanation + description + full narrative"),
    ],
}

COMMON_MISTAKES = [
    "✗  Starting every sentence with **'I'** — vary your sentence structure.",
    "✗  Repeating the same vocabulary — use **synonyms** when possible.",
    "✗  Forgetting to answer **ALL parts** of the prompt.",
    "✗  Writing **lists** instead of sentences.",
]

# ═══════════════════════════════════════════════════════════
# SESSION STATE
# ═══════════════════════════════════════════════════════════
def init_state():
    defaults = {
        "screen": "home",
        "vocab_set": list(VOCAB_SETS.keys())[0],
        "vocab_idx": 0,
        "vocab_flipped": False,
        "vocab_shuffled": [],
        "grammar_pool": [],
        "grammar_idx": 0,
        "grammar_score": 0,
        "grammar_answered": 0,
        "grammar_selected": None,
        "reading_idx": 0,
        "speaking_filter": "All",
        "speaking_prompt": None,
        "writing_cat": "👤 Personal",
        "writing_idx": 0,
        "writing_started": False,
        "writing_timer_end": None,
        "writing_responses": {},
        "student_name": "",
        "name_entered": False,
        "teacher_mode": False,
        "teacher_pw_attempt": "",
        "sheet_cache": None,
        "sheet_last_load": 0,
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v

init_state()

# ═══════════════════════════════════════════════════════════
# SIDEBAR
# ═══════════════════════════════════════════════════════════
with st.sidebar:
    st.markdown('<div class="main-title" style="font-size:2.2rem">🇪🇸 ¡Español!</div>', unsafe_allow_html=True)
    st.divider()

    if st.session_state.teacher_mode:
        st.markdown("🔐 **Teacher Dashboard**")
        if st.button("🚪 Exit Teacher Mode", use_container_width=True):
            st.session_state.teacher_mode = False
            st.session_state.name_entered = False
            st.session_state.student_name = ""
            st.rerun()
    else:
        if not st.session_state.name_entered:
            st.markdown("**Enter your name to start:**")
            name_input = st.text_input("Your name", placeholder="Type your name here...", label_visibility="collapsed")
            if st.button("¡Entrar!", use_container_width=True, type="primary"):
                if name_input.strip():
                    st.session_state.student_name = name_input.strip()
                    st.session_state.name_entered = True
                    st.rerun()
                else:
                    st.warning("Please enter your name first.")
            st.divider()
            with st.expander("🔐 Teacher login"):
                pw = st.text_input("Password", type="password", label_visibility="collapsed",
                                   placeholder="Teacher password...")
                if st.button("Login", use_container_width=True):
                    teacher_pw = st.secrets.get("teacher_password", "maestro2024")
                    if pw == teacher_pw:
                        st.session_state.teacher_mode = True
                        st.session_state.name_entered = True
                        st.rerun()
                    else:
                        st.error("Incorrect password.")
        else:
            st.markdown(f"👤 **{st.session_state.student_name}**")
            st.divider()
            st.markdown("**Go to:**")
            nav_items = [
                ("🏠", "Home",          "home"),
                ("🃏", "Vocabulario",   "vocab"),
                ("⚡", "Gramática",     "grammar"),
                ("📖", "Lectura",       "reading"),
                ("💬", "Conversación",  "speaking"),
                ("✍️", "Escritura AAPPL","writing"),
            ]
            for icon, label, key in nav_items:
                active = st.session_state.screen == key
                if st.button(f"{icon}  {label}", use_container_width=True,
                             type="primary" if active else "secondary"):
                    st.session_state.screen = key
                    st.rerun()

# ═══════════════════════════════════════════════════════════
# GATE: name required
# ═══════════════════════════════════════════════════════════
if not st.session_state.name_entered and not st.session_state.teacher_mode:
    st.markdown('<div class="main-title">¡Español!</div>', unsafe_allow_html=True)
    st.markdown('<div class="main-sub">Spanish Practice</div>', unsafe_allow_html=True)
    st.info("👈  Enter your name in the sidebar to get started.")
    st.stop()

# ═══════════════════════════════════════════════════════════
# TEACHER DASHBOARD
# ═══════════════════════════════════════════════════════════
if st.session_state.teacher_mode:
    st.markdown("## 🔐 Teacher Dashboard")
    st.markdown("All student writing submissions appear here as Google Docs in your Drive folder.")
    st.divider()

    drive, docs_svc = get_drive_service()

    if not drive:
        st.warning("⚠️ Google Drive not connected yet. Add your credentials in Streamlit Cloud → Settings → Secrets.")
    else:
        folder_id = get_or_create_folder(drive, FOLDER_NAME)

        c1, c2 = st.columns([3,1])
        with c1:
            st.markdown(f"📁 Folder: **{FOLDER_NAME}** in your Google Drive")
        with c2:
            if st.button("🔄 Refresh", type="secondary", use_container_width=True):
                st.session_state.sheet_last_load = 0
                st.rerun()

        now = time.time()
        if folder_id and (now - st.session_state.sheet_last_load > 30):
            st.session_state.sheet_cache = list_student_docs(drive, folder_id)
            st.session_state.sheet_last_load = now

        docs_list = st.session_state.sheet_cache or []

        if not docs_list:
            st.info("No submissions yet. Docs will appear here as students submit their writing.")
        else:
            col1, col2 = st.columns(2)
            col1.metric("Total Submissions", len(docs_list))
            students_set = set(d["name"].split("—")[0].strip() for d in docs_list if "—" in d["name"])
            col2.metric("Students", len(students_set))
            st.divider()

            filter_name = st.text_input("🔍 Search by student name:", placeholder="Type to filter...")
            filtered = [d for d in docs_list if filter_name.lower() in d["name"].lower()] if filter_name else docs_list
            st.markdown(f"**{len(filtered)} document(s)**")
            st.divider()

            GRADE_OPTIONS = ["—", "Exceeds", "Meets", "Approaching", "Beginning"]

            for i, doc in enumerate(filtered):
                name    = doc.get("name","")
                link    = doc.get("webViewLink","")
                created = doc.get("createdTime","")[:10] if doc.get("createdTime") else ""

                c1, c2, c3 = st.columns([4, 2, 2])
                with c1:
                    st.markdown(f"**{name}**")
                with c2:
                    st.markdown(f"📅 {created}")
                with c3:
                    if link:
                        st.markdown(f"[📄 Open Doc]({link})")

                gc1, gc2 = st.columns([2,4])
                with gc1:
                    grade_key = f"grade_{i}"
                    if grade_key not in st.session_state:
                        st.session_state[grade_key] = "—"
                    grade = st.selectbox("Grade:", GRADE_OPTIONS,
                                        index=GRADE_OPTIONS.index(st.session_state[grade_key]),
                                        key=f"grade_sel_{i}", label_visibility="collapsed")
                    st.session_state[grade_key] = grade
                with gc2:
                    st.text_input("Note:", placeholder="Optional feedback...",
                                  key=f"note_{i}", label_visibility="collapsed")
                st.divider()

    st.stop()

# ═══════════════════════════════════════════════════════════
# HOME
# ═══════════════════════════════════════════════════════════
if st.session_state.screen == "home":
    st.markdown('<div class="main-title" style="font-size:3rem">🇪🇸 ¡Español!</div>', unsafe_allow_html=True)
    st.markdown(f'<div class="main-sub">Bienvenido/a, {st.session_state.student_name}! Elige una actividad.</div>', unsafe_allow_html=True)

    col1, col2, col3 = st.columns(3)
    with col1:
        st.markdown('<div class="badge badge-yellow">🃏 Vocab</div>', unsafe_allow_html=True)
        st.markdown("**Vocabulario**\n\nFlashcards · 8 topic sets · flip to reveal")
        if st.button("Open Vocabulario →", key="nav_vocab", use_container_width=True):
            st.session_state.screen = "vocab"; st.rerun()
        st.divider()
        st.markdown('<div class="badge badge-teal">⚡ Grammar</div>', unsafe_allow_html=True)
        st.markdown("**Gramática**\n\nFill-in-the-blank · multiple choice · instant feedback")
        if st.button("Open Gramática →", key="nav_grammar", use_container_width=True):
            st.session_state.screen = "grammar"; st.session_state.grammar_pool = []; st.rerun()

    with col2:
        st.markdown('<div class="badge badge-purple">📖 Reading</div>', unsafe_allow_html=True)
        st.markdown("**Lectura**\n\nShort texts · comprehension questions")
        if st.button("Open Lectura →", key="nav_reading", use_container_width=True):
            st.session_state.screen = "reading"; st.rerun()
        st.divider()
        st.markdown('<div class="badge badge-red">💬 Speaking</div>', unsafe_allow_html=True)
        st.markdown("**Conversación**\n\nSpeaking prompts · timed challenges")
        if st.button("Open Conversación →", key="nav_speaking", use_container_width=True):
            st.session_state.screen = "speaking"; st.rerun()

    with col3:
        st.markdown('<div class="badge badge-green">✍️ Writing</div>', unsafe_allow_html=True)
        st.markdown("**Escritura AAPPL**\n\n31 prompts · P / Q / C / E categories · 10-min timer · AI feedback")
        if st.button("Open Escritura →", key="nav_writing", use_container_width=True):
            st.session_state.screen = "writing"; st.rerun()

# ═══════════════════════════════════════════════════════════
# VOCAB
# ═══════════════════════════════════════════════════════════
elif st.session_state.screen == "vocab":
    st.markdown("### 🃏 Vocabulario")

    selected_set = st.selectbox("Topic set / Tema:", list(VOCAB_SETS.keys()),
                                 index=list(VOCAB_SETS.keys()).index(st.session_state.vocab_set))
    if selected_set != st.session_state.vocab_set:
        st.session_state.vocab_set = selected_set
        st.session_state.vocab_idx = 0
        st.session_state.vocab_flipped = False
        st.session_state.vocab_shuffled = list(VOCAB_SETS[selected_set])
        st.rerun()

    if not st.session_state.vocab_shuffled:
        st.session_state.vocab_shuffled = list(VOCAB_SETS[st.session_state.vocab_set])

    cards = st.session_state.vocab_shuffled
    idx   = st.session_state.vocab_idx % len(cards)
    card  = cards[idx]

    st.markdown(f"**{idx+1} / {len(cards)}** — {st.session_state.vocab_set}")

    if not st.session_state.vocab_flipped:
        st.markdown(f'<div class="flashcard-front"><div style="font-size:0.75rem;color:#7b82a8;letter-spacing:0.1em;text-transform:uppercase;margin-bottom:0.8rem">{st.session_state.vocab_set}</div><div class="flashcard-word">{card[0]}</div><div style="color:#7b82a8;font-size:0.85rem;margin-top:0.8rem">Click Reveal to see translation</div></div>', unsafe_allow_html=True)
    else:
        st.markdown(f'<div class="flashcard-back"><div style="font-size:0.75rem;color:#7b82a8;letter-spacing:0.1em;text-transform:uppercase;margin-bottom:0.8rem">{st.session_state.vocab_set}</div><div style="font-family:Fraunces,serif;font-size:2rem;font-weight:700;color:#e8eaf6;margin-bottom:0.5rem">{card[1]}</div><div style="font-style:italic;color:#7b82a8;font-size:0.9rem">{card[2]}</div></div>', unsafe_allow_html=True)

    c1, c2, c3, c4 = st.columns(4)
    with c1:
        if st.button("← Prev", use_container_width=True):
            st.session_state.vocab_idx = (idx - 1) % len(cards)
            st.session_state.vocab_flipped = False; st.rerun()
    with c2:
        label = "🔙 Hide" if st.session_state.vocab_flipped else "👁 Reveal"
        if st.button(label, use_container_width=True):
            st.session_state.vocab_flipped = not st.session_state.vocab_flipped; st.rerun()
    with c3:
        if st.button("Next →", use_container_width=True):
            st.session_state.vocab_idx = (idx + 1) % len(cards)
            st.session_state.vocab_flipped = False; st.rerun()
    with c4:
        if st.button("🔀 Shuffle", use_container_width=True):
            shuffled = list(VOCAB_SETS[st.session_state.vocab_set])
            random.shuffle(shuffled)
            st.session_state.vocab_shuffled = shuffled
            st.session_state.vocab_idx = 0
            st.session_state.vocab_flipped = False; st.rerun()

# ═══════════════════════════════════════════════════════════
# GRAMMAR
# ═══════════════════════════════════════════════════════════
elif st.session_state.screen == "grammar":
    st.markdown("### ⚡ Gramática")

    if not st.session_state.grammar_pool:
        pool = list(GRAMMAR_QUESTIONS)
        random.shuffle(pool)
        st.session_state.grammar_pool    = pool
        st.session_state.grammar_idx     = 0
        st.session_state.grammar_score   = 0
        st.session_state.grammar_answered = 0
        st.session_state.grammar_selected = None

    pool = st.session_state.grammar_pool
    idx  = st.session_state.grammar_idx

    if idx >= len(pool):
        pct = st.session_state.grammar_score / len(pool)
        emoji = "🏆" if pct >= 0.8 else "🎉" if pct >= 0.6 else "💪"
        st.markdown(f"## {emoji} Quiz Complete!")
        st.markdown(f"### Score: {st.session_state.grammar_score} / {len(pool)}")
        if st.button("🔄 Try Again", type="primary"):
            st.session_state.grammar_pool = []; st.rerun()
        st.stop()

    tag, text, options, answer, explanation = pool[idx]
    progress = idx / len(pool)
    st.progress(progress)
    st.markdown(f'<div class="badge badge-teal">{tag}</div>', unsafe_allow_html=True)
    st.markdown(f"**{text.replace('___', '`___`')}**", unsafe_allow_html=False)
    st.markdown(f"Score: **{st.session_state.grammar_score} / {st.session_state.grammar_answered}**")

    selected = st.session_state.grammar_selected

    if selected is None:
        cols = st.columns(2)
        for i, opt in enumerate(options):
            with cols[i % 2]:
                if st.button(opt, key=f"opt_{idx}_{i}", use_container_width=True):
                    st.session_state.grammar_selected = i
                    st.session_state.grammar_answered += 1
                    if i == answer:
                        st.session_state.grammar_score += 1
                    st.rerun()
    else:
        cols = st.columns(2)
        for i, opt in enumerate(options):
            with cols[i % 2]:
                if i == answer:
                    st.success(f"✓ {opt}")
                elif i == selected:
                    st.error(f"✗ {opt}")
                else:
                    st.button(opt, key=f"opt_d_{idx}_{i}", disabled=True, use_container_width=True)

        if selected == answer:
            st.success(f"✓ Correct! {explanation}")
        else:
            st.error(f"✗ Not quite. Correct: **{options[answer]}**. {explanation}")

        if st.button("Next question →", type="primary"):
            st.session_state.grammar_idx += 1
            st.session_state.grammar_selected = None; st.rerun()

# ═══════════════════════════════════════════════════════════
# READING
# ═══════════════════════════════════════════════════════════
elif st.session_state.screen == "reading":
    st.markdown("### 📖 Lectura")

    READING_TEXTS = [
        ("🌮 La Feria de Comida",
         """El sábado pasado, mi familia y yo fuimos a la feria anual de comida en el centro de la ciudad. Había puestos de comida de todo el mundo: tacos mexicanos, sushi japonés, empanadas argentinas y mucho más.

Mi plato favorito fue un tamal de elote con crema. Era dulce y suave, y lo comí mientras paseábamos entre los puestos. Mi hermano, en cambio, prefirió las empanadas de carne.

Lo mejor de la feria no fue solo la comida, sino la música. Un grupo tocaba salsa en vivo y muchas personas bailaban en la calle. Fue una tarde inolvidable.""",
         [("¿Cuándo fue la feria?",["El viernes","El sábado","El domingo","El lunes"],1),
          ("¿Qué comió el narrador?",["Sushi","Empanadas de carne","Un tamal de elote","Tacos"],2),
          ("¿Qué fue 'lo mejor' según el texto?",["La comida mexicana","Los precios bajos","La música en vivo","El clima"],2)]),
        ("🌱 El Huerto Escolar",
         """Desde el año pasado, nuestra escuela tiene un huerto en el patio trasero. Lo plantamos entre todos los estudiantes de séptimo grado, y ahora es uno de los proyectos más populares del colegio.

En el huerto cultivamos tomates, lechugas, zanahorias y hierbas como el cilantro y la albahaca. Cada clase tiene un día asignado para regar y cuidar las plantas.

El mes pasado, cosechamos suficientes verduras para preparar una ensalada para toda la escuela. Fue un éxito total. El cocinero de la cafetería dijo que le encantaría usar nuestras verduras más seguido.""",
         [("¿Quién plantó el huerto?",["Los profesores","El cocinero","Los estudiantes de séptimo","Los padres"],2),
          ("¿Qué hicieron con las verduras el mes pasado?",["Las vendieron","Prepararon una ensalada","Las regalaron","Hicieron sopa"],1),
          ("¿Qué dijo el cocinero?",["Las verduras no están maduras","Prefiere el mercado","Le gustaría usarlas más seguido","El huerto necesita agua"],2)]),
    ]

    tabs = st.tabs([t[0] for t in READING_TEXTS])
    for i, (tab, (title, text, questions)) in enumerate(zip(tabs, READING_TEXTS)):
        with tab:
            col1, col2 = st.columns([3,2])
            with col1:
                st.markdown(f'<div class="prompt-box">{text.replace(chr(10), "<br>")}</div>', unsafe_allow_html=True)
            with col2:
                st.markdown("**Comprehension Questions:**")
                for qi, (q, opts, ans) in enumerate(questions):
                    key = f"reading_{i}_{qi}"
                    if key not in st.session_state:
                        st.session_state[key] = None
                    st.markdown(f"**{qi+1}. {q}**")
                    if st.session_state[key] is None:
                        for oi, opt in enumerate(opts):
                            if st.button(opt, key=f"{key}_opt_{oi}", use_container_width=True):
                                st.session_state[key] = oi; st.rerun()
                    else:
                        chosen = st.session_state[key]
                        for oi, opt in enumerate(opts):
                            if oi == ans:    st.success(f"✓ {opt}")
                            elif oi == chosen: st.error(f"✗ {opt}")
                    st.markdown("")

# ═══════════════════════════════════════════════════════════
# SPEAKING
# ═══════════════════════════════════════════════════════════
elif st.session_state.screen == "speaking":
    st.markdown("### 💬 Conversación")

    categories = ["All"] + list(set(p[0] for p in SPEAKING_PROMPTS))
    filter_cat = st.selectbox("Category:", categories, label_visibility="collapsed")

    pool = SPEAKING_PROMPTS if filter_cat == "All" else [p for p in SPEAKING_PROMPTS if p[0] == filter_cat]

    if st.session_state.speaking_prompt is None:
        st.session_state.speaking_prompt = random.choice(pool)

    cat, prompt_text, hint = st.session_state.speaking_prompt

    st.markdown(f'<div class="badge badge-red">💬 {cat}</div>', unsafe_allow_html=True)
    st.markdown(f'<div class="prompt-box"><p style="font-size:1.2rem;font-weight:600">{prompt_text}</p></div>', unsafe_allow_html=True)
    st.markdown(f"💡 **Language tip:** {hint}")

    c1, c2 = st.columns(2)
    with c1:
        if st.button("🎲 New Prompt", use_container_width=True, type="primary"):
            st.session_state.speaking_prompt = random.choice(pool); st.rerun()
    with c2:
        if st.button("⏱ Start 60s Timer", use_container_width=True):
            st.session_state["speak_timer_end"] = time.time() + 60; st.rerun()

    if "speak_timer_end" in st.session_state and st.session_state.speak_timer_end:
        remaining = int(st.session_state.speak_timer_end - time.time())
        if remaining > 0:
            cls = "timer-green" if remaining > 30 else "timer-yellow" if remaining > 10 else "timer-red"
            m, s = divmod(remaining, 60)
            st.markdown(f'<div class="timer-big {cls}">{m}:{s:02d}</div>', unsafe_allow_html=True)
            time.sleep(1); st.rerun()
        else:
            st.markdown('<div class="timer-big timer-red">¡Tiempo!</div>', unsafe_allow_html=True)
            st.session_state.speak_timer_end = None

# ═══════════════════════════════════════════════════════════
# WRITING
# ═══════════════════════════════════════════════════════════
elif st.session_state.screen == "writing":
    st.markdown("### ✍️ Escritura AAPPL")

    cat = st.selectbox("Category:", list(WRITING_TASKS.keys()),
                        index=list(WRITING_TASKS.keys()).index(st.session_state.writing_cat),
                        label_visibility="collapsed")
    if cat != st.session_state.writing_cat:
        st.session_state.writing_cat       = cat
        st.session_state.writing_idx       = 0
        st.session_state.writing_started   = False
        st.session_state.writing_timer_end = None
        st.rerun()

    tasks   = WRITING_TASKS[st.session_state.writing_cat]
    idx     = st.session_state.writing_idx
    task    = tasks[idx]
    tid, level, title, prompt_text, target, min_w, max_w, rubric = task
    key_resp = f"{cat}_{idx}"

    # ── Navigation ──
    c1, c2, c3 = st.columns([1,4,1])
    with c1:
        if st.button("← Prev", use_container_width=True):
            st.session_state.writing_idx       = (idx - 1) % len(tasks)
            st.session_state.writing_started   = False
            st.session_state.writing_timer_end = None; st.rerun()
    with c2:
        st.markdown(f"**{idx+1} / {len(tasks)}** — {tid} · {level} · {title}")
    with c3:
        if st.button("Next →", use_container_width=True):
            st.session_state.writing_idx       = (idx + 1) % len(tasks)
            st.session_state.writing_started   = False
            st.session_state.writing_timer_end = None; st.rerun()

    already_done = key_resp in st.session_state.writing_responses

    # ── TIPS overlay (before start) ──────────────────────
    if not st.session_state.writing_started and not already_done:
        st.divider()
        st.markdown("#### 💡 Before you start / Antes de comenzar")
        st.markdown(f"**{tid} · {level} — {title}**")
        st.markdown(f"📏 Target: **{target}**")
        st.markdown("")
        st.markdown("**⚠️ Common mistakes to avoid:**")
        for m in COMMON_MISTAKES:
            st.markdown(f'<div class="tips-item">{m}</div>', unsafe_allow_html=True)
        st.markdown("")
        st.info("⏱ You will have **10 minutes** to complete this task. Once you start, the timer cannot be paused.")
        st.markdown("")
        if st.button("✍️  Start Writing — Begin Timer", type="primary", use_container_width=True):
            st.session_state.writing_started   = True
            st.session_state.writing_timer_end = time.time() + 600
            st.rerun()

    # ── Writing area ─────────────────────────────────────
    else:
        col1, col2 = st.columns([2, 3])

        with col1:
            st.markdown(f'<div class="badge badge-green">{cat} · {level}</div>', unsafe_allow_html=True)
            st.markdown(f"**{title}**")
            st.markdown(f'<div class="prompt-box">{prompt_text.replace(chr(10),"<br>")}</div>', unsafe_allow_html=True)
            st.markdown("")
            st.markdown(f"📊 **AAPPL Checklist:** {rubric}")

        with col2:
            # ── Timer ──
            timer_end = st.session_state.writing_timer_end
            timed_out = False
            if timer_end and not already_done:
                remaining = int(timer_end - time.time())
                if remaining > 0:
                    cls = "timer-green" if remaining > 120 else "timer-yellow" if remaining > 30 else "timer-red"
                    m, s = divmod(remaining, 60)
                    st.markdown(f'<div class="timer-big {cls}">{m}:{s:02d} remaining</div>', unsafe_allow_html=True)
                else:
                    st.markdown('<div class="timer-big timer-red">⏰ Time\'s up!</div>', unsafe_allow_html=True)
                    timed_out = True

            saved     = st.session_state.writing_responses.get(key_resp, {})
            is_locked = already_done or timed_out

            if is_locked and not already_done:
                st.warning("⏰ Time's up! Your response is locked. Click **Submit** to send it to your teacher.")

            # ── Special characters — pure Streamlit buttons ──
            if not is_locked:
                st.markdown("**Toca para insertar · Tap to insert:**")
                all_chars = ["á","é","í","ó","ú","ü","ñ","¿","¡","Á","É","Í","Ó","Ú","Ü","Ñ"]
                char_cols = st.columns(len(all_chars))
                for ci, char in enumerate(all_chars):
                    with char_cols[ci]:
                        if st.button(char, key=f"ch_{key_resp}_{ci}",
                                     use_container_width=True):
                            cur = st.session_state.get(f"textarea_{key_resp}",
                                                       saved.get("text", ""))
                            st.session_state[f"textarea_{key_resp}"] = cur + char
                            st.rerun()

            # ── Text area ──
            init_val = st.session_state.get(f"textarea_{key_resp}", saved.get("text",""))
            # Render textarea — spellcheck disabled via JS above
            response_text = st.text_area(
                f"✍️ Escribe aquí (meta: {target})",
                value=init_val,
                height=320,
                disabled=is_locked,
                key=f"textarea_{key_resp}",
                placeholder="Escribe tu respuesta aquí...",
                help="No hay autocorrección. Usa los botones de arriba para ñ y acentos."
            )
            # Inject spellcheck=false directly onto this specific textarea
            st.markdown("""
<script>
(function() {
    var tas = document.querySelectorAll('textarea');
    tas.forEach(function(ta) {
        ta.spellcheck = false;
        ta.setAttribute('spellcheck','false');
        ta.setAttribute('autocorrect','off');
        ta.setAttribute('autocomplete','off');
        ta.setAttribute('autocapitalize','off');
    });
})();
</script>
""", unsafe_allow_html=True)

            # Word count
            words = len(response_text.split()) if response_text.strip() else 0
            wc_class = "word-good" if min_w <= words <= max_w else "word-over" if words > max_w else "word-count"
            st.markdown(f'<div class="{wc_class}">{words} words (target: {target})</div>', unsafe_allow_html=True)

            # ── Already submitted ──
            if already_done:
                st.success("✅ Submitted! / ¡Enviado!")
                doc_url = saved.get("doc_url")
                if doc_url:
                    st.markdown(f"📄 [Open your Google Doc]({doc_url})")

                # Show AI feedback if it was saved
                ai_fb  = saved.get("ai_feedback")
                ai_err = saved.get("ai_error")
                if ai_fb:
                    st.markdown('<div class="feedback-box"><div class="feedback-title">🤖 Retroalimentación de IA</div>' +
                                ai_fb.replace("\n", "<br>") + '</div>', unsafe_allow_html=True)
                elif ai_err == "NO_KEY":
                    st.warning("⚠️ La API key de Anthropic no está configurada en Streamlit Secrets.")
                elif ai_err:
                    st.warning(f"⚠️ Error al generar retroalimentación: {ai_err}")
                elif saved.get("ai_feedback_attempted"):
                    st.info("ℹ️ No se pudo generar retroalimentación de IA.")

            # ── Submit button ──
            else:
                if st.button("📤 Submit & Get AI Feedback", type="primary", use_container_width=True,
                             disabled=not response_text.strip()):

                    ai_feedback = None
                    ai_attempted = False

                    # Step 1 — Get AI feedback
                    with st.spinner("🤖 Generando retroalimentación de IA..."):
                        ai_feedback, ai_error = get_ai_feedback(
                            st.session_state.student_name,
                            tid, level, title, prompt_text, rubric, target,
                            response_text
                        )
                        ai_attempted = True

                    # Step 2 — Create Google Doc (includes feedback)
                    with st.spinner("📄 Saving to Google Drive..."):
                        drive, docs_svc = get_drive_service()
                        doc_url = None
                        if drive and docs_svc:
                            folder_id = get_or_create_folder(drive, FOLDER_NAME)
                            if folder_id:
                                doc_url, _ = create_student_doc(
                                    drive, docs_svc, folder_id,
                                    st.session_state.student_name,
                                    tid, level, title, task[3], rubric, target,
                                    response_text, ai_feedback
                                )

                    # Step 3 — Save to session
                    st.session_state.writing_responses[key_resp] = {
                        "text":                response_text,
                        "submitted":           True,
                        "words":               words,
                        "task":                f"{tid} — {title}",
                        "level":               level,
                        "doc_url":             doc_url,
                        "ai_feedback":         ai_feedback,
                        "ai_error":            ai_error,
                        "ai_feedback_attempted": ai_attempted,
                    }
                    st.session_state.writing_timer_end = None
                    st.rerun()

            # Auto-refresh timer
            if timer_end and not already_done and not timed_out:
                time.sleep(1)
                st.rerun()

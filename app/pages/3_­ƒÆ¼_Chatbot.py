"""Page Chatbot — assistant virtuel STB Bank.

Fonctionne en mode démo (réponses par règles) par défaut.
Si une clé API Anthropic est fournie dans st.secrets["ANTHROPIC_API_KEY"],
les réponses sont générées par Claude à la place.
"""
import streamlit as st
from utils.auth import require_login
from utils.ui import render_header, render_sidebar_user, inject_css

st.set_page_config(page_title="Chatbot | STB Bank", page_icon="💬", layout="wide")
inject_css()
require_login()
render_sidebar_user()
render_header("Assistant virtuel")

SYSTEM_PROMPT = (
    "Tu es l'assistant virtuel du portail STB Bank. Tu réponds de façon claire, "
    "professionnelle et concise aux questions des collaborateurs sur les services "
    "bancaires, l'utilisation du portail (Power BI, module de prédiction) et les "
    "procédures internes générales. Tu ne donnes jamais de conseils financiers "
    "personnalisés définitifs et tu rappelles de consulter un conseiller pour toute "
    "décision engageante."
)

FAQ_RULES = [
    (("bonjour", "salut", "hello"), "Bonjour 👋 ! Comment puis-je vous aider aujourd'hui ?"),
    (("power bi", "rapport", "dashboard", "tableau de bord"),
     "Le rapport Power BI se trouve dans la page **📊 PowerBI** du menu. "
     "Vous pouvez y coller le lien d'intégration de votre rapport."),
    (("prédiction", "prediction", "credit", "crédit", "score"),
     "Le module **🔮 Prédiction** permet d'estimer la probabilité d'octroi d'un crédit "
     "à partir du revenu, du montant demandé, de la durée, du score et de l'ancienneté."),
    (("mot de passe", "password", "connexion", "login"),
     "Pour la démo, utilisez l'identifiant `admin` et le mot de passe `admin123`, "
     "ou `agent` / `stb2025`."),
    (("merci",), "Avec plaisir 🙂 N'hésitez pas si vous avez d'autres questions."),
]


def rule_based_reply(user_text: str) -> str:
    text = user_text.lower()
    for keywords, reply in FAQ_RULES:
        if any(k in text for k in keywords):
            return reply
    return (
        "Je suis un assistant de démonstration 🤖. Je peux répondre à des questions simples "
        "sur le portail (Power BI, prédiction, connexion). Pour connecter un vrai modèle de "
        "langage, ajoutez une clé API dans `st.secrets` (voir le code de cette page)."
    )


def call_claude(messages: list) -> str:
    """Appelle l'API Anthropic si une clé est configurée dans st.secrets."""
    import anthropic

    client = anthropic.Anthropic(api_key=st.secrets["ANTHROPIC_API_KEY"])
    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=800,
        system=SYSTEM_PROMPT,
        messages=messages,
    )
    return "".join(block.text for block in response.content if block.type == "text")


def has_llm_configured() -> bool:
    try:
        return bool(st.secrets.get("ANTHROPIC_API_KEY"))
    except Exception:
        return False


if "chat_messages" not in st.session_state:
    st.session_state["chat_messages"] = [
        {"role": "assistant", "content": "Bonjour 👋 Je suis l'assistant virtuel STB Bank. Comment puis-je vous aider ?"}
    ]

if has_llm_configured():
    st.caption("🟢 Mode connecté : réponses générées par Claude (Anthropic API).")
else:
    st.caption(
        "🟡 Mode démonstration (réponses par règles). "
        "Ajoutez `ANTHROPIC_API_KEY` dans `.streamlit/secrets.toml` pour activer les réponses IA complètes."
    )

for msg in st.session_state["chat_messages"]:
    with st.chat_message(msg["role"], avatar="🏦" if msg["role"] == "assistant" else "🧑"):
        st.markdown(msg["content"])

prompt = st.chat_input("Écrivez votre message ici...")

if prompt:
    st.session_state["chat_messages"].append({"role": "user", "content": prompt})
    with st.chat_message("user", avatar="🧑"):
        st.markdown(prompt)

    with st.chat_message("assistant", avatar="🏦"):
        with st.spinner("L'assistant rédige une réponse..."):
            if has_llm_configured():
                try:
                    api_messages = [
                        {"role": m["role"], "content": m["content"]}
                        for m in st.session_state["chat_messages"]
                        if m["role"] in ("user", "assistant")
                    ]
                    reply = call_claude(api_messages)
                except Exception as e:
                    reply = f"⚠️ Erreur lors de l'appel à l'API : {e}"
            else:
                reply = rule_based_reply(prompt)
        st.markdown(reply)

    st.session_state["chat_messages"].append({"role": "assistant", "content": reply})

if st.button("🗑️ Effacer la conversation"):
    st.session_state["chat_messages"] = []
    st.rerun()

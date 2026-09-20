"""Vue Accueil — affichée après connexion. Le contenu s'adapte au rôle de l'utilisateur."""
import streamlit as st
from utils.permissions import allowed_pages
from utils.ui import render_header

render_header("Accueil")

role = st.session_state.get("role", "Utilisateur")
allowed = allowed_pages(role)

st.markdown(f"## Bonjour, {st.session_state['display_name']} 👋")
st.caption(f"Rôle : **{role}**")
st.write("Utilisez le menu à gauche pour naviguer entre les différents modules du portail.")

all_kpis = [
    ("powerbi", "📊", "Rapport Power BI", "Vue en direct de vos indicateurs métier"),
    ("prediction", "🔮", "Prédiction", "Estimez le risque / l'approbation d'un dossier"),
    ("chatbot", "💬", "Assistant virtuel", "Posez vos questions à l'assistant STB"),
    ("admin", "🛠️", "Administration", "Gérez les comptes et les rôles des utilisateurs"),
]
visible_kpis = [k for k in all_kpis if k[0] in allowed]

cols = st.columns(len(visible_kpis)) if visible_kpis else []
for col, (key, icon, title, desc) in zip(cols, visible_kpis):
    with col:
        st.markdown(
            f"""
            <div class="stb-card">
                <div style="font-size:32px;">{icon}</div>
                <div class="stb-kpi-value" style="font-size:18px;">{title}</div>
                <div class="stb-kpi-label" style="text-transform:none;">{desc}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

st.divider()

if role == "Utilisateur":
    st.info(
        "🔒 Votre compte a un **accès limité** (Accueil + Chatbot). "
        "Pour accéder à Power BI, au module de Prédiction et à la Détection de fraude, "
        "contactez un administrateur afin qu'il mette à jour votre rôle."
    )
else:
    st.markdown("### 🧭 Navigation")
    st.info("Utilisez le menu à gauche pour accéder aux différentes pages disponibles selon votre rôle.")

st.divider()
st.caption(
    "STB Bank Portal — démonstration Streamlit. "
    "Remplacez `assets/logo.png` par le vrai logo de l'établissement pour le voir apparaître "
    "dans l'en-tête et la barre latérale."
)

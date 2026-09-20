"""
STB Bank Portal — Application Streamlit principale.

Lancer avec :  streamlit run app.py

Utilise st.navigation / st.Page pour afficher des noms d'onglets propres et
fixes dans la barre latérale (indépendants des noms de fichiers), ce qui évite
les problèmes d'affichage ("noms bug") liés aux emojis dans les noms de fichiers
sur certains systèmes.
"""
import os

import streamlit as st

from utils.auth import is_authenticated, render_login_form, render_signup_form
from utils.floating_chat import render_floating_chat
from utils.permissions import allowed_pages
from utils.ui import inject_css, render_header, render_sidebar_user

# Utilise le vrai logo de la banque comme icône d'onglet (favicon) quand il est
# disponible ; repli sur l'emoji si le fichier est absent.
_FAVICON_PATH = os.path.join(os.path.dirname(__file__), "assets", "favicon.png")
_page_icon = _FAVICON_PATH if os.path.exists(_FAVICON_PATH) else "🏦"

st.set_page_config(
    page_title="STB Bank Portal",
    page_icon=_page_icon,
    layout="wide",
    # Pas de menu latéral tant que l'utilisateur n'est pas connecté : il n'y a
    # rien à y afficher avant l'authentification (voir plus bas, st.navigation
    # n'est construit qu'après un login réussi).
    initial_sidebar_state="expanded" if is_authenticated() else "collapsed",
)

inject_css()

# ---------------------------------------------------------------------------
# ÉCRAN DE CONNEXION / INSCRIPTION
# ---------------------------------------------------------------------------
if not is_authenticated():
    # Masque complètement la barre latérale (et son bouton d'ouverture) sur
    # l'écran de connexion : aucun onglet ne doit être visible/accessible
    # avant une authentification réussie.
    st.markdown(
        """
        <style>
            section[data-testid="stSidebar"],
            div[data-testid="stSidebarCollapsedControl"] {
                display: none !important;
            }
        </style>
        """,
        unsafe_allow_html=True,
    )
    render_header("Connexion")

    left, center, right = st.columns([1, 1.3, 1])
    with center:
        st.markdown('<div class="stb-card">', unsafe_allow_html=True)
        tab_login, tab_signup = st.tabs(["🔐 Connexion", "🆕 Créer un compte"])
        with tab_login:
            st.write(
                "Connectez-vous pour accéder au tableau de bord Power BI, au module "
                "de prédiction, à la détection de fraude et à l'assistant données."
            )
            render_login_form()
        with tab_signup:
            render_signup_form()
        st.markdown("</div>", unsafe_allow_html=True)

    st.stop()

# ---------------------------------------------------------------------------
# NAVIGATION (utilisateur connecté) — noms d'onglets définis explicitement ici
# Les pages affichées dépendent du rôle de l'utilisateur (voir utils/permissions.py)
# ---------------------------------------------------------------------------
render_sidebar_user()

role = st.session_state.get("role", "Utilisateur")
allowed = allowed_pages(role)

all_pages = {
    "home": st.Page("views/home.py", title="Accueil", icon=":material/home:", default=True),
    "powerbi": st.Page("views/powerbi.py", title="Power BI", icon=":material/bar_chart:"),
    "prediction": st.Page("views/prediction.py", title="Prédiction", icon=":material/insights:"),
    "realtime": st.Page("views/realtime.py", title="Détection de fraude", icon=":material/warning:"),
    "admin": st.Page("views/admin.py", title="Administration", icon=":material/admin_panel_settings:"),
}

pages = [page for key, page in all_pages.items() if key in allowed]

pg = st.navigation(pages)
pg.run()

# ---------------------------------------------------------------------------
# ASSISTANT DONNÉES — widget de chat flottant (bas droite), affiché sur
# toutes les pages plutôt que comme une page entière dans le menu.
# ---------------------------------------------------------------------------
if "chatbot" in allowed:
    render_floating_chat()

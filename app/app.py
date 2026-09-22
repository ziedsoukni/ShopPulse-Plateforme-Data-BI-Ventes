"""
ShopPulse Portal — Application Streamlit principale.

Lancer avec :  streamlit run app.py

Utilise st.navigation / st.Page pour afficher des noms d'onglets propres et
fixes dans la barre latérale (indépendants des noms de fichiers), ce qui évite
les problèmes d'affichage ("noms bug") liés aux emojis dans les noms de fichiers
sur certains systèmes.
"""
import os

import streamlit as st

from utils import gemini_chat
from utils.auth import is_authenticated, render_login_form, render_signup_form
from utils.floating_chat import render_floating_chat
from utils.permissions import allowed_pages
from utils.ui import inject_css, render_header, render_sidebar_user

# Utilise le logo ShopPulse comme icône d'onglet (favicon) quand il est
# disponible ; repli sur l'emoji si le fichier est absent.
_FAVICON_PATH = os.path.join(os.path.dirname(__file__), "assets", "favicon.png")
_page_icon = _FAVICON_PATH if os.path.exists(_FAVICON_PATH) else "🛒"

st.set_page_config(
    page_title="ShopPulse Portal",
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
        st.markdown('<div class="sp-card">', unsafe_allow_html=True)
        tab_login, tab_signup = st.tabs(["🔐 Connexion", "🆕 Créer un compte"])
        with tab_login:
            st.write(
                "Connectez-vous pour accéder au tableau de bord Power BI, au module "
                "de prévision, au scoring du risque de retour et à l'assistant données."
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

# ---------------------------------------------------------------------------
# CONNEXION AUTOMATIQUE DES DONNÉES — chargée une fois au démarrage (mise en
# cache par Streamlit), pour que le chatbot et les pages de données n'aient
# jamais besoin d'un téléversement manuel. Le résultat (y compris une
# éventuelle erreur claire) est mémorisé pour être réutilisé partout.
# ---------------------------------------------------------------------------
if "chatbot" in allowed and "sp_data_status" not in st.session_state:
    _result = gemini_chat.load_data_safe(gemini_chat.EXCEL_PATH_DEFAUT)
    st.session_state["sp_data_status"] = {
        "ok": _result.ok,
        "error": _result.error,
        "missing_sheets": _result.missing_sheets,
    }

all_pages = {
    "home": st.Page("views/home.py", title="Accueil", icon=":material/home:", default=True),
    "powerbi": st.Page("views/powerbi.py", title="Power BI", icon=":material/bar_chart:"),
    "prediction": st.Page("views/prediction.py", title="Prédiction", icon=":material/insights:"),
    "realtime": st.Page("views/realtime.py", title="Risque de retour", icon=":material/warning:"),
    "chatbot": st.Page("views/chatbot.py", title="Assistant données", icon=":material/smart_toy:"),
    "admin": st.Page("views/admin.py", title="Administration", icon=":material/admin_panel_settings:"),
}

pages = [page for key, page in all_pages.items() if key in allowed]

pg = st.navigation(pages)
pg.run()

# ---------------------------------------------------------------------------
# ASSISTANT DONNÉES — widget de chat flottant (bas droite), affiché sur
# toutes les pages (en plus de la page dédiée "Assistant données" ci-dessus,
# pour un accès rapide depuis n'importe quel écran du portail).
# ---------------------------------------------------------------------------
if "chatbot" in allowed:
    render_floating_chat()

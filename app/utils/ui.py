"""
Composants d'interface partagés : thème CSS, en-tête avec logo + horloge en direct.

Identité visuelle "ShopPulse Analytics" — thème sombre moderne orienté
Data/Analytics (fond profond, accents indigo -> violet -> cyan en dégradé,
cartes et composants "glassmorphism" légers). Volontairement très différente
de l'identité du dashboard Power BI (claire, navy/or) : les deux interfaces
ont chacune leur propre identité, comme demandé.

Toute la palette est centralisée dans les constantes ci-dessous : il suffit
de les modifier pour ajuster le thème sur l'ensemble de l'application (une
seule fonction `inject_css()` est utilisée par toutes les pages via
`render_header`).
"""
import base64
import os
import streamlit as st
import streamlit.components.v1 as components

ASSETS_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "assets")
LOGO_PATH = os.path.join(ASSETS_DIR, "logo.png")

# ---------------------------------------------------------------------------
# Palette — "ShopPulse Analytics" (sombre, Data/Analytics)
# ---------------------------------------------------------------------------
BG = "#0B0E14"                 # fond principal (presque noir, nuance navy)
BG_ELEVATED = "#10141F"        # fond légèrement plus clair (zones secondaires)
SURFACE = "#151A24"            # cartes / conteneurs
SURFACE_ALT = "#1B2131"        # cartes en survol / lignes alternées
BORDER = "#252C3D"             # bordures discrètes
BORDER_STRONG = "#323B52"

PRIMARY = "#6C5CE7"            # violet-indigo — couleur de marque principale
PRIMARY_2 = "#4F7CFF"          # bleu électrique — second point du dégradé
ACCENT = "#22D3EE"             # cyan — accent vif (troisième point du dégradé)
ACCENT_WARM = "#F59E0B"        # ambre — alertes / mise en avant secondaire

SUCCESS = "#10B981"
WARNING = "#F59E0B"
DANGER = "#F43F5E"

TEXT = "#E6E9F2"               # texte principal (presque blanc)
TEXT_SECONDARY = "#9AA5B8"     # texte secondaire / légendes
TEXT_MUTED = "#6B7690"

GRADIENT = f"linear-gradient(135deg, {PRIMARY_2} 0%, {PRIMARY} 55%, {ACCENT} 100%)"

# Conservé pour compatibilité avec d'éventuel code externe qui importerait
# encore ces anciens noms de variables.
ACCENT_2 = ACCENT
ACCENT_LIGHT = BORDER_STRONG


def inject_css():
    st.markdown(
        f"""
        <style>
            :root {{
                --sp-bg: {BG};
                --sp-bg-elevated: {BG_ELEVATED};
                --sp-surface: {SURFACE};
                --sp-surface-alt: {SURFACE_ALT};
                --sp-border: {BORDER};
                --sp-border-strong: {BORDER_STRONG};
                --sp-primary: {PRIMARY};
                --sp-primary-2: {PRIMARY_2};
                --sp-accent: {ACCENT};
                --sp-success: {SUCCESS};
                --sp-warning: {WARNING};
                --sp-danger: {DANGER};
                --sp-text: {TEXT};
                --sp-text-secondary: {TEXT_SECONDARY};
                --sp-text-muted: {TEXT_MUTED};
                --sp-gradient: {GRADIENT};
            }}

            /* ---------------------------------------------------------- */
            /* Fond général                                                */
            /* ---------------------------------------------------------- */
            .stApp {{
                background:
                    radial-gradient(1200px 600px at 15% -10%, rgba(108,92,231,0.12) 0%, rgba(108,92,231,0) 60%),
                    radial-gradient(1000px 500px at 100% 0%, rgba(34,211,238,0.10) 0%, rgba(34,211,238,0) 55%),
                    {BG};
            }}
            html, body, [class*="css"] {{
                color: {TEXT};
            }}
            * {{
                scrollbar-width: thin;
                scrollbar-color: {BORDER_STRONG} transparent;
            }}
            ::-webkit-scrollbar {{ width: 8px; height: 8px; }}
            ::-webkit-scrollbar-thumb {{ background: {BORDER_STRONG}; border-radius: 8px; }}
            ::-webkit-scrollbar-track {{ background: transparent; }}

            /* ---------------------------------------------------------- */
            /* Sidebar                                                     */
            /* ---------------------------------------------------------- */
            section[data-testid="stSidebar"] {{
                background: linear-gradient(180deg, {BG_ELEVATED} 0%, #080A10 100%);
                border-right: 1px solid {BORDER};
            }}
            section[data-testid="stSidebar"] * {{
                color: {TEXT} !important;
            }}
            section[data-testid="stSidebar"] .stButton>button {{
                background: {GRADIENT};
                color: #0B0E14 !important;
                font-weight: 700;
                border: none;
                border-radius: 10px;
                transition: filter 0.15s ease, transform 0.15s ease;
            }}
            section[data-testid="stSidebar"] .stButton>button:hover {{
                filter: brightness(1.1);
                transform: translateY(-1px);
            }}
            div[data-testid="stSidebarNav"] a,
            section[data-testid="stSidebar"] div[data-testid="stPageLink-NavLink"] {{
                border-radius: 10px !important;
                margin: 2px 6px;
            }}
            div[data-testid="stSidebarNav"] a[aria-current="page"],
            section[data-testid="stSidebar"] div[data-testid="stPageLink-NavLink"][aria-current="page"] {{
                background: linear-gradient(90deg, rgba(108,92,231,0.28) 0%, rgba(34,211,238,0.14) 100%) !important;
                box-shadow: inset 3px 0 0 {ACCENT};
            }}
            section[data-testid="stSidebar"] hr {{
                border-color: {BORDER};
            }}

            /* ---------------------------------------------------------- */
            /* En-tête de page                                             */
            /* ---------------------------------------------------------- */
            .sp-header {{
                display: flex;
                align-items: center;
                justify-content: space-between;
                background: {GRADIENT};
                padding: 20px 30px;
                border-radius: 18px;
                margin-bottom: 26px;
                box-shadow: 0 12px 34px rgba(76, 60, 190, 0.35);
                position: relative;
                overflow: hidden;
            }}
            .sp-header::after {{
                content: "";
                position: absolute;
                inset: 0;
                background: linear-gradient(120deg, rgba(255,255,255,0.14) 0%, rgba(255,255,255,0) 40%);
                pointer-events: none;
            }}
            .sp-header-left {{
                display: flex;
                align-items: center;
                gap: 16px;
                z-index: 1;
            }}
            .sp-title {{
                color: #FFFFFF;
                font-size: 26px;
                font-weight: 800;
                letter-spacing: 0.3px;
                margin: 0;
            }}
            .sp-subtitle {{
                color: rgba(255,255,255,0.85);
                font-size: 12px;
                font-weight: 700;
                margin: 2px 0 0 0;
                letter-spacing: 1.6px;
                text-transform: uppercase;
            }}
            .sp-clock {{
                color: white;
                text-align: right;
                font-family: 'Courier New', monospace;
                z-index: 1;
            }}
            .sp-clock .time {{
                font-size: 22px;
                font-weight: 700;
                color: #FFFFFF;
            }}
            .sp-clock .date {{
                font-size: 13px;
                color: rgba(255,255,255,0.85);
                text-transform: capitalize;
            }}
            .sp-logo-fallback {{
                width: 54px;
                height: 54px;
                border-radius: 14px;
                background: rgba(255,255,255,0.18);
                border: 1px solid rgba(255,255,255,0.35);
                color: #FFFFFF;
                display: flex;
                align-items: center;
                justify-content: center;
                font-weight: 900;
                font-size: 19px;
                font-family: Arial, sans-serif;
                flex-shrink: 0;
                backdrop-filter: blur(6px);
            }}
            .sp-logo-img {{
                width: 54px;
                height: 54px;
                object-fit: contain;
                border-radius: 14px;
                background: rgba(255,255,255,0.92);
                padding: 5px;
                flex-shrink: 0;
                box-shadow: 0 2px 10px rgba(0,0,0,0.25);
            }}

            /* ---------------------------------------------------------- */
            /* Cartes                                                      */
            /* ---------------------------------------------------------- */
            .sp-card {{
                background: {SURFACE};
                border-radius: 16px;
                padding: 22px;
                box-shadow: 0 4px 18px rgba(0,0,0,0.28);
                border: 1px solid {BORDER};
                border-left: 3px solid {PRIMARY};
                transition: transform 0.15s ease, border-color 0.15s ease;
            }}
            .sp-card:hover {{
                transform: translateY(-2px);
                border-left-color: {ACCENT};
            }}
            .sp-kpi-value {{
                font-size: 30px;
                font-weight: 800;
                background: {GRADIENT};
                -webkit-background-clip: text;
                background-clip: text;
                -webkit-text-fill-color: transparent;
            }}
            .sp-kpi-label {{
                font-size: 12px;
                color: {TEXT_SECONDARY};
                text-transform: uppercase;
                letter-spacing: 0.6px;
            }}

            /* Cartes KPI natives Streamlit (st.metric) */
            div[data-testid="stMetric"] {{
                background: {SURFACE};
                border: 1px solid {BORDER};
                border-radius: 14px;
                padding: 16px 18px;
                box-shadow: 0 4px 16px rgba(0,0,0,0.22);
            }}
            div[data-testid="stMetric"] label {{
                color: {TEXT_SECONDARY} !important;
                font-weight: 600;
                text-transform: uppercase;
                font-size: 11px;
                letter-spacing: 0.6px;
            }}
            div[data-testid="stMetricValue"] {{
                color: {TEXT} !important;
                font-weight: 800;
            }}

            /* ---------------------------------------------------------- */
            /* Boutons                                                     */
            /* ---------------------------------------------------------- */
            .stButton>button, .stDownloadButton>button, .stFormSubmitButton>button {{
                border-radius: 10px;
                font-weight: 700;
                border: 1px solid {BORDER_STRONG};
                background: {SURFACE_ALT};
                color: {TEXT};
                transition: all 0.15s ease;
            }}
            .stButton>button:hover, .stDownloadButton>button:hover, .stFormSubmitButton>button:hover {{
                border-color: {ACCENT};
                color: {ACCENT};
            }}
            button[kind="primary"], .stButton>button[kind="primary"], .stFormSubmitButton>button[kind="primary"] {{
                background: {GRADIENT} !important;
                color: #0B0E14 !important;
                border: none !important;
                box-shadow: 0 8px 22px rgba(108,92,231,0.35);
            }}
            button[kind="primary"]:hover {{
                filter: brightness(1.08);
                box-shadow: 0 10px 28px rgba(108,92,231,0.5);
            }}

            /* ---------------------------------------------------------- */
            /* Champs de saisie / sélecteurs                               */
            /* ---------------------------------------------------------- */
            .stTextInput input, .stNumberInput input, .stTextArea textarea,
            div[data-baseweb="select"] > div, div[data-baseweb="base-input"] {{
                background-color: {SURFACE} !important;
                border-color: {BORDER_STRONG} !important;
                color: {TEXT} !important;
                border-radius: 10px !important;
            }}
            .stTextInput input:focus, .stNumberInput input:focus, .stTextArea textarea:focus {{
                border-color: {ACCENT} !important;
                box-shadow: 0 0 0 1px {ACCENT} !important;
            }}

            /* Tabs */
            div[data-baseweb="tab-list"] {{
                gap: 6px;
                border-bottom: 1px solid {BORDER};
            }}
            button[data-baseweb="tab"] {{
                color: {TEXT_SECONDARY};
                border-radius: 10px 10px 0 0 !important;
            }}
            button[data-baseweb="tab"][aria-selected="true"] {{
                color: {TEXT} !important;
                background: {SURFACE};
                border-bottom: 2px solid {ACCENT} !important;
            }}

            /* Segmented control / pills */
            div[data-testid="stSegmentedControl"] label {{
                border-radius: 999px !important;
                border-color: {BORDER_STRONG} !important;
            }}

            /* ---------------------------------------------------------- */
            /* Tableaux / dataframes                                       */
            /* ---------------------------------------------------------- */
            div[data-testid="stDataFrame"], div[data-testid="stTable"] {{
                border: 1px solid {BORDER};
                border-radius: 12px;
                overflow: hidden;
            }}

            /* ---------------------------------------------------------- */
            /* Bannières d'information (info / warning / error / success)  */
            /* ---------------------------------------------------------- */
            div[data-testid="stAlertContainer"] {{
                border-radius: 12px;
                border: 1px solid {BORDER};
            }}

            /* ---------------------------------------------------------- */
            /* Assistant IA — bulles de discussion modernes                */
            /* ---------------------------------------------------------- */
            div[data-testid="stChatMessage"] {{
                background: {SURFACE};
                border: 1px solid {BORDER};
                border-radius: 16px;
                padding: 4px 6px;
                margin-bottom: 6px;
            }}
            div[data-testid="stChatInput"] {{
                border-radius: 14px;
                border: 1px solid {BORDER_STRONG} !important;
                background: {SURFACE} !important;
            }}
            div[data-testid="stChatInput"] textarea {{
                color: {TEXT} !important;
            }}

            /* Panneau du chat flottant (voir utils/floating_chat.py) */
            .st-key-chat_panel {{
                color: {TEXT};
            }}

            /* ---------------------------------------------------------- */
            /* Carte de connexion (voir app.py)                            */
            /* ---------------------------------------------------------- */
            .st-key-login_card {{
                background: {SURFACE};
                border-radius: 18px;
                padding: 30px 32px 12px 32px;
                box-shadow: 0 10px 34px rgba(0,0,0,0.35);
                border: 1px solid {BORDER};
                border-top: 3px solid {PRIMARY};
            }}
            .st-key-login_card div[data-baseweb="tab-list"] {{
                justify-content: center;
            }}
            .st-key-login_card .stCaption {{
                text-align: center;
            }}

            /* ---------------------------------------------------------- */
            /* Cadre du rapport Power BI intégré (voir views/powerbi.py)   */
            /* ---------------------------------------------------------- */
            .st-key-powerbi_frame {{
                background: {SURFACE};
                border-radius: 18px;
                padding: 14px;
                border: 1px solid {BORDER};
                box-shadow: 0 10px 30px rgba(0,0,0,0.30);
            }}
            .st-key-powerbi_frame iframe {{
                border-radius: 12px;
                border: 1px solid {BORDER};
            }}

            /* Expander */
            div[data-testid="stExpander"] {{
                background: {SURFACE};
                border: 1px solid {BORDER};
                border-radius: 12px;
            }}

            /* Diviseurs */
            hr {{
                border-color: {BORDER} !important;
            }}

            /* ---------------------------------------------------------- */
            /* Responsive — écrans étroits (mobile / tablette)             */
            /* ---------------------------------------------------------- */
            @media (max-width: 640px) {{
                .sp-header {{
                    padding: 14px 18px;
                    border-radius: 14px;
                    flex-direction: column;
                    align-items: flex-start;
                    gap: 10px;
                }}
                .sp-title {{ font-size: 20px; }}
                .sp-clock {{ text-align: left; }}
                .sp-card {{ padding: 16px; }}
            }}
        </style>
        """,
        unsafe_allow_html=True,
    )


def _logo_html() -> str:
    if os.path.exists(LOGO_PATH):
        with open(LOGO_PATH, "rb") as f:
            encoded = base64.b64encode(f.read()).decode()
        return f'<img class="sp-logo-img" src="data:image/png;base64,{encoded}" />'
    # Repli élégant si aucun logo n'est fourni dans assets/logo.png
    return '<div class="sp-logo-fallback">SP</div>'


def render_header(page_title: str = "Accueil"):
    """Affiche l'en-tête (logo + titre + horloge en direct) en haut de chaque page."""
    inject_css()
    st.markdown(
        f"""
        <div class="sp-header">
            <div class="sp-header-left">
                {_logo_html()}
                <div>
                    <p class="sp-title">ShopPulse Portal</p>
                    <p class="sp-subtitle">{page_title.upper()}</p>
                </div>
            </div>
            <div id="sp-clock-container"></div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    render_live_clock()


def render_live_clock(height: int = 55):
    """Horloge en direct (JS côté client, pas de rerun Streamlit nécessaire)."""
    components.html(
        f"""
        <div style="display:flex; justify-content:flex-end; font-family:'Courier New', monospace;">
            <div style="text-align:right;">
                <div id="sp-time" style="font-size:22px; font-weight:700; color:#FFFFFF;"></div>
                <div id="sp-date" style="font-size:13px; color:rgba(255,255,255,0.85); text-transform:capitalize;"></div>
            </div>
        </div>
        <script>
            function spUpdateClock() {{
                const now = new Date();
                const timeEl = document.getElementById('sp-time');
                const dateEl = document.getElementById('sp-date');
                if (timeEl) {{
                    timeEl.innerHTML = now.toLocaleTimeString('fr-FR');
                }}
                if (dateEl) {{
                    dateEl.innerHTML = now.toLocaleDateString('fr-FR', {{
                        weekday: 'long', year: 'numeric', month: 'long', day: 'numeric'
                    }});
                }}
            }}
            spUpdateClock();
            setInterval(spUpdateClock, 1000);
        </script>
        """,
        height=height,
    )


def render_sidebar_user():
    """Affiche les infos utilisateur + bouton de déconnexion dans la sidebar."""
    from utils.auth import logout

    name = st.session_state.get("display_name")
    role = st.session_state.get("role")
    if name:
        st.sidebar.markdown(f"### 👤 {name}")
        st.sidebar.caption(f"Rôle : {role}")
        if st.sidebar.button("🚪 Se déconnecter", use_container_width=True):
            logout()
            st.rerun()
        st.sidebar.divider()

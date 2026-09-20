"""
Composants d'interface partagés : thème CSS, en-tête avec logo + horloge en direct.
"""
import base64
import os
import streamlit as st
import streamlit.components.v1 as components

ASSETS_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "assets")
LOGO_PATH = os.path.join(ASSETS_DIR, "logo.png")

PRIMARY = "#00517A"     # bleu STB (dérivé du logo officiel)
ACCENT = "#D4AF37"      # or / doré — contraste chaleureux sur le bleu
ACCENT_2 = "#0077B3"    # bleu STB vif (second point du dégradé d'en-tête)
ACCENT_LIGHT = "#BFE2F4"  # bleu clair — bordures / séparateurs discrets
BG = "#EBF6FB"          # fond très légèrement teinté bleu, plus doux que du blanc pur
TEXT = "#1B1B1B"


def inject_css():
    st.markdown(
        f"""
        <style>
            .stApp {{
                background-color: {BG};
            }}
            section[data-testid="stSidebar"] {{
                background: linear-gradient(180deg, {PRIMARY} 0%, #003655 100%);
            }}
            section[data-testid="stSidebar"] * {{
                color: #FFFFFF !important;
            }}
            section[data-testid="stSidebar"] .stButton>button {{
                background-color: {ACCENT};
                color: {PRIMARY} !important;
                font-weight: 700;
                border: none;
                transition: filter 0.15s ease;
            }}
            section[data-testid="stSidebar"] .stButton>button:hover {{
                filter: brightness(1.08);
            }}
            div[data-testid="stSidebarNav"] a[aria-current="page"],
            section[data-testid="stSidebar"] div[data-testid="stPageLink-NavLink"][aria-current="page"] {{
                background-color: rgba(255,255,255,0.14) !important;
                border-radius: 8px;
            }}
            .stb-header {{
                display: flex;
                align-items: center;
                justify-content: space-between;
                background: linear-gradient(90deg, {PRIMARY} 0%, {ACCENT_2} 100%);
                padding: 18px 28px;
                border-radius: 14px;
                margin-bottom: 24px;
                box-shadow: 0 6px 20px rgba(0,81,122,0.22);
                border-bottom: 3px solid {ACCENT};
            }}
            .stb-header-left {{
                display: flex;
                align-items: center;
                gap: 16px;
            }}
            .stb-title {{
                color: white;
                font-size: 26px;
                font-weight: 800;
                letter-spacing: 0.5px;
                margin: 0;
            }}
            .stb-subtitle {{
                color: {ACCENT};
                font-size: 13px;
                font-weight: 600;
                margin: 0;
                letter-spacing: 1px;
            }}
            .stb-clock {{
                color: white;
                text-align: right;
                font-family: 'Courier New', monospace;
            }}
            .stb-clock .time {{
                font-size: 22px;
                font-weight: 700;
                color: {ACCENT};
            }}
            .stb-clock .date {{
                font-size: 13px;
                color: #E6E6E6;
                text-transform: capitalize;
            }}
            .stb-logo-fallback {{
                width: 56px;
                height: 56px;
                border-radius: 12px;
                background: {ACCENT};
                color: {PRIMARY};
                display: flex;
                align-items: center;
                justify-content: center;
                font-weight: 900;
                font-size: 20px;
                font-family: Arial, sans-serif;
                flex-shrink: 0;
            }}
            .stb-logo-img {{
                width: 56px;
                height: 56px;
                object-fit: contain;
                border-radius: 12px;
                background: white;
                padding: 5px;
                flex-shrink: 0;
                box-shadow: 0 2px 8px rgba(0,0,0,0.12);
            }}
            .stb-card {{
                background: white;
                border-radius: 14px;
                padding: 22px;
                box-shadow: 0 2px 12px rgba(0,81,122,0.08);
                border: 1px solid {ACCENT_LIGHT};
                border-left: 5px solid {ACCENT};
            }}
            .stb-kpi-value {{
                font-size: 30px;
                font-weight: 800;
                color: {PRIMARY};
            }}
            .stb-kpi-label {{
                font-size: 13px;
                color: #666;
                text-transform: uppercase;
                letter-spacing: 0.5px;
            }}
            div[data-testid="stMetric"] {{
                background: white;
                border: 1px solid {ACCENT_LIGHT};
                border-radius: 12px;
                padding: 14px 16px;
                box-shadow: 0 2px 10px rgba(0,81,122,0.06);
            }}
            div[data-testid="stMetric"] label {{
                color: {PRIMARY} !important;
            }}
        </style>
        """,
        unsafe_allow_html=True,
    )


def _logo_html() -> str:
    if os.path.exists(LOGO_PATH):
        with open(LOGO_PATH, "rb") as f:
            encoded = base64.b64encode(f.read()).decode()
        return f'<img class="stb-logo-img" src="data:image/png;base64,{encoded}" />'
    # Repli élégant si aucun logo n'est fourni dans assets/logo.png
    return '<div class="stb-logo-fallback">STB</div>'


def render_header(page_title: str = "Accueil"):
    """Affiche l'en-tête (logo + titre + horloge en direct) en haut de chaque page."""
    inject_css()
    st.markdown(
        f"""
        <div class="stb-header">
            <div class="stb-header-left">
                {_logo_html()}
                <div>
                    <p class="stb-title">STB Bank Portal</p>
                    <p class="stb-subtitle">{page_title.upper()}</p>
                </div>
            </div>
            <div id="stb-clock-container"></div>
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
                <div id="stb-time" style="font-size:22px; font-weight:700; color:{ACCENT};"></div>
                <div id="stb-date" style="font-size:13px; color:#444; text-transform:capitalize;"></div>
            </div>
        </div>
        <script>
            function stbUpdateClock() {{
                const now = new Date();
                const timeEl = document.getElementById('stb-time');
                const dateEl = document.getElementById('stb-date');
                if (timeEl) {{
                    timeEl.innerHTML = now.toLocaleTimeString('fr-FR');
                }}
                if (dateEl) {{
                    dateEl.innerHTML = now.toLocaleDateString('fr-FR', {{
                        weekday: 'long', year: 'numeric', month: 'long', day: 'numeric'
                    }});
                }}
            }}
            stbUpdateClock();
            setInterval(stbUpdateClock, 1000);
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

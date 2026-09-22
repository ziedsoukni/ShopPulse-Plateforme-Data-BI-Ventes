"""
Composants d'interface partagés : thème CSS, en-tête avec logo + horloge en direct.
"""
import base64
import os
import streamlit as st
import streamlit.components.v1 as components

ASSETS_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "assets")
LOGO_PATH = os.path.join(ASSETS_DIR, "logo.png")

PRIMARY = "#0B3C49"     # bleu-vert profond ShopPulse
ACCENT = "#F28C28"      # orange — contraste chaleureux
ACCENT_2 = "#0E9F8E"    # turquoise ShopPulse (second point du dégradé d'en-tête)
ACCENT_LIGHT = "#CFE8E4"  # turquoise clair — bordures / séparateurs discrets
BG = "#EAF5F3"          # fond légèrement teinté turquoise, plus doux que du blanc pur
TEXT = "#1B1B1B"


def inject_css():
    st.markdown(
        f"""
        <style>
            .stApp {{
                background-color: {BG};
            }}
            section[data-testid="stSidebar"] {{
                background: linear-gradient(180deg, {PRIMARY} 0%, #072A33 100%);
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
            .sp-header {{
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
            .sp-header-left {{
                display: flex;
                align-items: center;
                gap: 16px;
            }}
            .sp-title {{
                color: white;
                font-size: 26px;
                font-weight: 800;
                letter-spacing: 0.5px;
                margin: 0;
            }}
            .sp-subtitle {{
                color: {ACCENT};
                font-size: 13px;
                font-weight: 600;
                margin: 0;
                letter-spacing: 1px;
            }}
            .sp-clock {{
                color: white;
                text-align: right;
                font-family: 'Courier New', monospace;
            }}
            .sp-clock .time {{
                font-size: 22px;
                font-weight: 700;
                color: {ACCENT};
            }}
            .sp-clock .date {{
                font-size: 13px;
                color: #E6E6E6;
                text-transform: capitalize;
            }}
            .sp-logo-fallback {{
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
            .sp-logo-img {{
                width: 56px;
                height: 56px;
                object-fit: contain;
                border-radius: 12px;
                background: white;
                padding: 5px;
                flex-shrink: 0;
                box-shadow: 0 2px 8px rgba(0,0,0,0.12);
            }}
            .sp-card {{
                background: white;
                border-radius: 14px;
                padding: 22px;
                box-shadow: 0 2px 12px rgba(0,81,122,0.08);
                border: 1px solid {ACCENT_LIGHT};
                border-left: 5px solid {ACCENT};
            }}
            .sp-kpi-value {{
                font-size: 30px;
                font-weight: 800;
                color: {PRIMARY};
            }}
            .sp-kpi-label {{
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
                box-shadow: 0 2px 10px rgba(11,60,73,0.06);
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
                <div id="sp-time" style="font-size:22px; font-weight:700; color:{ACCENT};"></div>
                <div id="sp-date" style="font-size:13px; color:#444; text-transform:capitalize;"></div>
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

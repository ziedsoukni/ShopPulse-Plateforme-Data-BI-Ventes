"""Page Power BI — intègre un rapport Power BI dans l'application."""
import streamlit as st
from utils.auth import require_login
from utils.ui import render_header, render_sidebar_user, inject_css

st.set_page_config(page_title="Power BI | STB Bank", page_icon="📊", layout="wide")
inject_css()
require_login()
render_sidebar_user()
render_header("Tableau de bord Power BI")

st.markdown(
    """
    Intégrez ici votre rapport **Power BI**. Deux méthodes possibles :

    1. **Publier sur le web** (rapports publics) : dans Power BI → *Fichier* → *Intégrer le rapport* →
       *Publier sur le web*, puis collez le lien `https://app.powerbi.com/view?r=...` ci-dessous.
    2. **Intégration organisationnelle** (rapports internes / sécurisés) : nécessite Azure AD
       + Power BI Embedded (un jeton d'accès doit être généré côté serveur). Contactez votre
       administrateur Power BI pour ce type d'intégration.
    """
)

default_url = st.session_state.get("powerbi_url", "")

with st.form("powerbi_form"):
    url = st.text_input(
        "Lien d'intégration du rapport Power BI",
        value=default_url,
        placeholder="https://app.powerbi.com/view?r=xxxxxxxxxxxxxxxxxx",
    )
    height = st.slider("Hauteur d'affichage (px)", 400, 1200, 700, step=50)
    submitted = st.form_submit_button("Afficher le rapport", use_container_width=True)

if submitted and url:
    st.session_state["powerbi_url"] = url

active_url = st.session_state.get("powerbi_url", "")

if active_url:
    st.components.v1.iframe(active_url, height=height if submitted else 700, scrolling=True)
else:
    st.warning(
        "⚠️ Aucun rapport n'est configuré pour le moment. "
        "Collez le lien d'intégration Power BI ci-dessus pour l'afficher ici."
    )
    st.markdown(
        """
        <div class="stb-card">
            <b>Astuce :</b> vous pouvez aussi coder l'URL en dur directement dans ce fichier
            (variable <code>default_url</code>) si le rapport est toujours le même,
            afin que les utilisateurs n'aient rien à saisir.
        </div>
        """,
        unsafe_allow_html=True,
    )

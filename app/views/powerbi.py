import streamlit as st
import streamlit.components.v1 as components

# Note : st.set_page_config() n'est pas rappelé ici — il est déjà appelé une
# seule fois dans app.py (Streamlit exige un unique appel par run, sinon ça
# lève une erreur quand cette page est chargée via st.navigation).

# URL d'intégration du rapport publié dans le service Power BI (Fichier → Intégrer le rapport).
POWERBI_URL = (
    "https://app.powerbi.com/reportEmbed"
    "?reportId=29298b08-be28-4e38-a34c-f9acd6d8e7b0"
    "&autoAuth=true"
    "&ctid=604f1a96-cbe8-43f8-abbf-f8eaf5d85730"
)

st.markdown("### 📊 Tableau de bord Power BI — ShopPulse Ventes e-commerce")

if not POWERBI_URL:
    st.info("Collez l'URL d'intégration du rapport Power BI dans `POWERBI_URL` (`views/powerbi.py`).")
else:
    # Rapport affiché dans un cadre habillé (fond + bordure arrondie) plutôt
    # qu'en iframe brute posée directement sur le fond sombre de l'application :
    # le rapport Power BI (thème clair, voir ThemeVentes.json) s'intègre ainsi
    # proprement dans l'interface sombre du portail.
    with st.container(key="powerbi_frame"):
        components.iframe(POWERBI_URL, height=820, scrolling=True)
    st.caption(
        "Si le rapport n'apparaît pas, connectez-vous à Power BI dans ce navigateur "
        "(compte ayant accès au rapport) puis rechargez la page."
    )

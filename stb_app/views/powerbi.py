import streamlit as st

# Note : st.set_page_config() n'est pas rappelé ici — il est déjà appelé une
# seule fois dans app.py (Streamlit exige un unique appel par run, sinon ça
# lève une erreur quand cette page est chargée via st.navigation).

POWERBI_URL = (
    "https://app.powerbi.com/reportEmbed?reportId=d88200ec-b47c-421c-9366-030d9ee9422d"
    "&autoAuth=true&ctid=604f1a96-cbe8-43f8-abbf-f8eaf5d85730"
)

st.markdown(
    f"""
    <iframe title="powerbi"
        width="100%"
        height="800"
        src="{POWERBI_URL}"
        frameborder="0"
        allowFullScreen="true">
    </iframe>
    """,
    unsafe_allow_html=True,
)

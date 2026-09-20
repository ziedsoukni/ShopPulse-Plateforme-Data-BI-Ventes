"""Vue Chatbot — assistant données (Gemini + pandas) affiché en panneau de discussion.

Gemini transforme la question en requête structurée, pandas calcule le vrai
résultat sur le fichier Excel (jamais inventé par l'IA), puis Gemini reformule
la réponse en français.
"""
import os

import pandas as pd
import streamlit as st
from utils.ui import render_header
from utils import gemini_chat

render_header("Assistant données")

api_key = gemini_chat.get_gemini_api_key()

side, chat_col = st.columns([1, 1.4], gap="large")

with side:
    st.markdown(
        """
        <div class="stb-card">
            <h4 style="margin-top:0;">📊 Assistant données</h4>
            <p style="font-size:14px; color:#555;">
                Posez vos questions sur les clients, agences, produits, comptes
                et transactions du projet.
            </p>
        </div>
        """,
        unsafe_allow_html=True,
    )
    if not api_key:
        st.warning(
            "⚠️ Aucune clé Gemini configurée. Ajoutez `GEMINI_API_KEY` dans "
            "`.streamlit/secrets.toml`."
        )

with chat_col:
    if api_key:
        default_path = gemini_chat.EXCEL_PATH_DEFAUT
        source = None
        if os.path.exists(default_path):
            source = default_path
        else:
            st.warning(f"⚠️ Fichier introuvable : `{default_path}`")
            uploaded = st.file_uploader(
                "Déposez le fichier Excel des données", type=["xlsx"], key="gemini_excel_uploader"
            )
            if uploaded is not None:
                source = uploaded.getvalue()

        if source is not None:
            if "data_chat_history" not in st.session_state:
                st.session_state["data_chat_history"] = []

            chat_box = st.container(height=480, border=True)
            with chat_box:
                if not st.session_state["data_chat_history"]:
                    st.caption("💬 Posez votre première question ci-dessous.")
                for entry in st.session_state["data_chat_history"]:
                    with st.chat_message("user", avatar="🧑"):
                        st.markdown(entry["question"])
                    with st.chat_message("assistant", avatar="📊"):
                        st.markdown(entry["answer"])
                        if entry.get("table") is not None:
                            st.dataframe(entry["table"], use_container_width=True)

            question = st.chat_input("Posez votre question...", key="gemini_chat_input")

            if question:
                with chat_box:
                    with st.chat_message("user", avatar="🧑"):
                        st.markdown(question)
                    with st.chat_message("assistant", avatar="📊"):
                        table = None
                        with st.spinner("Analyse..."):
                            try:
                                data = gemini_chat.load_data(source)
                                answer, result, kind, plan = gemini_chat.ask(question, data, api_key)
                                if isinstance(result, (pd.DataFrame, pd.Series)):
                                    table = result
                            except Exception as e:
                                answer = f"⚠️ Erreur : {e}"
                        st.markdown(answer)
                        if table is not None:
                            st.dataframe(table, use_container_width=True)

                st.session_state["data_chat_history"].append(
                    {"question": question, "answer": answer, "table": table}
                )

            if st.button("🗑️ Effacer la conversation", key="clear_data_chat"):
                st.session_state["data_chat_history"] = []
                st.rerun()

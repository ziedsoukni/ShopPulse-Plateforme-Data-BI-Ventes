"""Vue Chatbot — assistant données (Gemini + pandas) affiché en panneau de discussion.

Le fichier Excel du projet est connecté AUTOMATIQUEMENT au démarrage (chemin
centralisé dans `utils/data_config.py`, aucune sélection manuelle requise).
Gemini transforme la question en requête structurée, pandas calcule le vrai
résultat sur les données (jamais inventé par l'IA) ; si l'information
demandée n'existe pas dans le fichier, l'assistant le dit clairement plutôt
que de deviner.
"""
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
        <div class="sp-card">
            <h4 style="margin-top:0;">🤖 Assistant ShopPulse</h4>
            <p style="font-size:14px; color:var(--sp-text-secondary);">
                Posez vos questions sur les clients, boutiques, produits, canaux
                et ventes du projet. Les réponses s'appuient uniquement sur les
                données réellement présentes dans le fichier connecté.
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
        # Connexion automatique au fichier Excel du projet.
        source = gemini_chat.EXCEL_PATH_DEFAUT
        result = gemini_chat.load_data_safe(source)

        if result.error:
            st.error(f"⚠️ {result.error}")
            uploaded = st.file_uploader(
                "Ou déposez le fichier Excel des données manuellement", type=["xlsx"],
                key="gemini_excel_uploader",
            )
            if uploaded is not None:
                result = gemini_chat.load_data_safe(uploaded.getvalue())
        else:
            n_ventes = len(result.data["vente"]) if "vente" in result.data else None
            detail = f" ({n_ventes:,} ventes)".replace(",", " ") if n_ventes is not None else ""
            st.caption(f"🟢 Fichier `{result.source_label}` connecté automatiquement{detail}.")
            if result.missing_sheets:
                st.caption(f"⚠️ Feuilles absentes du fichier : {', '.join(result.missing_sheets)}")

        if result.ok:
            data = result.data
            if "data_chat_history" not in st.session_state:
                st.session_state["data_chat_history"] = []

            chat_box = st.container(height=480, border=True)
            with chat_box:
                if not st.session_state["data_chat_history"]:
                    st.caption("💬 Posez votre première question ci-dessous.")
                for entry in st.session_state["data_chat_history"]:
                    with st.chat_message("user", avatar="🧑"):
                        st.markdown(entry["question"])
                    with st.chat_message("assistant", avatar="🤖"):
                        st.markdown(entry["answer"])
                        if entry.get("table") is not None:
                            st.dataframe(entry["table"], use_container_width=True)

            question = st.chat_input("Posez votre question...", key="gemini_chat_input")

            if question:
                with chat_box:
                    with st.chat_message("user", avatar="🧑"):
                        st.markdown(question)
                    with st.chat_message("assistant", avatar="🤖"):
                        table = None
                        with st.spinner("Analyse des données..."):
                            try:
                                answer, result_val, kind, plan = gemini_chat.ask(question, data, api_key)
                                if isinstance(result_val, (pd.DataFrame, pd.Series)):
                                    table = result_val
                            except Exception as e:
                                answer = f"⚠️ Erreur inattendue : {e}"
                        st.markdown(answer)
                        if table is not None:
                            st.dataframe(table, use_container_width=True)

                st.session_state["data_chat_history"].append(
                    {"question": question, "answer": answer, "table": table}
                )

            if st.button("🗑️ Effacer la conversation", key="clear_data_chat"):
                st.session_state["data_chat_history"] = []
                st.rerun()

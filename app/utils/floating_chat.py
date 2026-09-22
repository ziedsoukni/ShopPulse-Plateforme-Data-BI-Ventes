"""Widget de chat flottant (façon "chat en direct" d'un site web classique).

Affiché en bas à droite, sur toutes les pages, avec un bouton rond pour
l'ouvrir/le fermer — il ne prend jamais toute une page à lui seul.

Le positionnement fixe utilise le paquet `streamlit-float` (bien plus fiable
qu'une simple classe CSS ici, car Streamlit imbrique les éléments dans des
conteneurs qui peuvent casser un `position: fixed` classique).

Réutilise `utils.gemini_chat` : Gemini transforme la question en requête
structurée, pandas calcule le vrai résultat sur le fichier Excel, Gemini
reformule la réponse.
"""
import os

import pandas as pd
import streamlit as st
from streamlit_float import float_init
from utils import gemini_chat

float_init()


def _inject_button_css():
    st.markdown(
        """
        <style>
            .st-key-chat_toggle_btn button {
                width: 58px;
                height: 58px;
                border-radius: 50% !important;
                font-size: 24px;
                line-height: 1;
                box-shadow: 0 6px 18px rgba(0,0,0,0.28);
            }
        </style>
        """,
        unsafe_allow_html=True,
    )


def render_floating_chat():
    """À appeler une fois par page (depuis app.py) pour afficher le widget."""
    if "chat_widget_open" not in st.session_state:
        st.session_state["chat_widget_open"] = False

    _inject_button_css()

    # --- Bouton rond flottant (ouvrir / fermer) ---
    toggle_box = st.container(key="chat_toggle_btn")
    with toggle_box:
        icon = "✕" if st.session_state["chat_widget_open"] else "💬"
        if st.button(icon, key="chat_toggle_button", help="Assistant données"):
            st.session_state["chat_widget_open"] = not st.session_state["chat_widget_open"]
            st.rerun()
    toggle_box.float(
        "bottom: 24px; right: 24px; width: 58px; z-index: 999999;"
    )

    if not st.session_state["chat_widget_open"]:
        return

    # --- Panneau de discussion flottant ---
    panel_box = st.container(key="chat_panel")
    with panel_box:
        st.markdown("**📊 Assistant données**")

        api_key = gemini_chat.get_gemini_api_key()
        if not api_key:
            st.warning(
                "⚠️ Aucune clé Gemini configurée (`GEMINI_API_KEY` dans `.streamlit/secrets.toml`)."
            )
        else:
            default_path = gemini_chat.EXCEL_PATH_DEFAUT
            source = None
            if os.path.exists(default_path):
                source = default_path
            else:
                st.warning(f"⚠️ Fichier introuvable : `{default_path}`")
                uploaded = st.file_uploader(
                    "Déposez le fichier Excel", type=["xlsx"], key="gemini_excel_uploader_floating"
                )
                if uploaded is not None:
                    source = uploaded.getvalue()

            if source is not None:
                if "data_chat_history" not in st.session_state:
                    st.session_state["data_chat_history"] = []

                # chat_input placé dans ce conteneur de hauteur fixe : il se
                # colle au bas DE CE CONTENEUR (et non du bas de la page).
                chat_area = st.container(height=320)
                with chat_area:
                    if not st.session_state["data_chat_history"]:
                        st.caption("💬 Posez votre première question ci-dessous.")
                    for entry in st.session_state["data_chat_history"]:
                        with st.chat_message("user", avatar="🧑"):
                            st.markdown(entry["question"])
                        with st.chat_message("assistant", avatar="📊"):
                            st.markdown(entry["answer"])
                            if entry.get("table") is not None:
                                st.dataframe(entry["table"], use_container_width=True)

                    question = st.chat_input(
                        "Posez votre question...", key="gemini_chat_input_floating"
                    )

                    if question:
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

                if st.session_state["data_chat_history"]:
                    if st.button("🗑️ Effacer", key="clear_data_chat_floating"):
                        st.session_state["data_chat_history"] = []
                        st.rerun()

    panel_box.float(
        "bottom: 94px; right: 24px; width: 380px; max-width: calc(100vw - 32px); "
        "z-index: 999998; background: #FFFFFF; border-radius: 16px; "
        "box-shadow: 0 10px 34px rgba(0,0,0,0.28); padding: 14px 16px 4px 16px;"
    )

"""Widget de chat flottant — assistant IA façon copilote de données.

Affiché en bas à droite, sur toutes les pages, avec un bouton rond pour
l'ouvrir/le fermer — il ne prend jamais toute une page à lui seul.

Le positionnement fixe utilise le paquet `streamlit-float` (bien plus fiable
qu'une simple classe CSS ici, car Streamlit imbrique les éléments dans des
conteneurs qui peuvent casser un `position: fixed` classique).

Réutilise `utils.gemini_chat` : Gemini transforme la question en requête
structurée, pandas calcule le vrai résultat sur le fichier Excel du projet
(connecté automatiquement, sans sélection manuelle), Gemini reformule la
réponse. Aucune donnée n'est jamais inventée : si l'information demandée
n'existe pas dans le fichier, l'assistant le dit clairement.
"""
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
                width: 60px;
                height: 60px;
                border-radius: 50% !important;
                font-size: 24px;
                line-height: 1;
                background: linear-gradient(135deg, #6C5CE7 0%, #22D3EE 100%) !important;
                color: #FFFFFF !important;
                border: none !important;
                box-shadow: 0 8px 24px rgba(108, 92, 231, 0.45);
                transition: transform 0.15s ease, box-shadow 0.15s ease;
            }
            .st-key-chat_toggle_btn button:hover {
                transform: scale(1.06);
                box-shadow: 0 10px 30px rgba(108, 92, 231, 0.6);
            }
        </style>
        """,
        unsafe_allow_html=True,
    )


def _status_caption(result: "gemini_chat.DataLoadResult"):
    if result.error:
        st.error(f"⚠️ {result.error}")
        return
    n_lignes = result.data.get("vente")
    n_lignes = len(n_lignes) if n_lignes is not None else None
    detail = f" · {n_lignes:,} ventes".replace(",", " ") if n_lignes is not None else ""
    st.caption(f"🟢 Données connectées automatiquement{detail}")
    if result.missing_sheets:
        st.caption(f"⚠️ Feuilles absentes du fichier : {', '.join(result.missing_sheets)}")


def render_floating_chat():
    """À appeler une fois par page (depuis app.py) pour afficher le widget."""
    if "chat_widget_open" not in st.session_state:
        st.session_state["chat_widget_open"] = False

    _inject_button_css()

    # --- Bouton rond flottant (ouvrir / fermer) ---
    toggle_box = st.container(key="chat_toggle_btn")
    with toggle_box:
        icon = "✕" if st.session_state["chat_widget_open"] else "💬"
        if st.button(icon, key="chat_toggle_button", help="Assistant données ShopPulse"):
            st.session_state["chat_widget_open"] = not st.session_state["chat_widget_open"]
            st.rerun()
    toggle_box.float(
        "bottom: 24px; right: 24px; width: 60px; z-index: 999999;"
    )

    if not st.session_state["chat_widget_open"]:
        return

    # --- Panneau de discussion flottant ---
    panel_box = st.container(key="chat_panel")
    with panel_box:
        st.markdown(
            """
            <div style="display:flex; align-items:center; gap:8px; margin-bottom:2px;">
                <span style="font-size:20px;">🤖</span>
                <span style="font-weight:700; color:#E6E9F2; font-size:15px;">
                    Assistant ShopPulse
                </span>
            </div>
            """,
            unsafe_allow_html=True,
        )

        api_key = gemini_chat.get_gemini_api_key()
        if not api_key:
            st.warning(
                "⚠️ Aucune clé Gemini configurée (`GEMINI_API_KEY` dans `.streamlit/secrets.toml`)."
            )
        else:
            # Connexion automatique au fichier Excel du projet (chemin centralisé
            # dans utils/data_config.py) — aucun téléversement manuel requis.
            source = gemini_chat.EXCEL_PATH_DEFAUT
            result = gemini_chat.load_data_safe(source)
            _status_caption(result)

            if result.error:
                uploaded = st.file_uploader(
                    "Ou déposez le fichier Excel manuellement", type=["xlsx"],
                    key="gemini_excel_uploader_floating",
                )
                if uploaded is not None:
                    result = gemini_chat.load_data_safe(uploaded.getvalue())

            if result.ok:
                data = result.data
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
                        with st.chat_message("assistant", avatar="🤖"):
                            st.markdown(entry["answer"])
                            if entry.get("table") is not None:
                                st.dataframe(entry["table"], use_container_width=True)

                    question = st.chat_input(
                        "Posez votre question...", key="gemini_chat_input_floating"
                    )

                    if question:
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

                if st.session_state["data_chat_history"]:
                    if st.button("🗑️ Effacer", key="clear_data_chat_floating"):
                        st.session_state["data_chat_history"] = []
                        st.rerun()

    panel_box.float(
        "bottom: 96px; right: 24px; width: 380px; max-width: calc(100vw - 32px); "
        "z-index: 999998; background: #151A24; border: 1px solid #2A3348; "
        "border-radius: 18px; box-shadow: 0 20px 50px rgba(0,0,0,0.55); "
        "padding: 16px 18px 6px 18px;"
    )

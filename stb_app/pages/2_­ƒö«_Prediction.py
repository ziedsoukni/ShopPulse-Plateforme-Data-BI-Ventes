"""Page Prédiction — démonstrateur d'estimation d'octroi de crédit."""
import numpy as np
import pandas as pd
import streamlit as st
from utils.auth import require_login
from utils.ui import render_header, render_sidebar_user, inject_css

st.set_page_config(page_title="Prédiction | STB Bank", page_icon="🔮", layout="wide")
inject_css()
require_login()
render_sidebar_user()
render_header("Module de prédiction")

st.markdown(
    """
    Ce module illustre comment brancher un **modèle de machine learning** dans le portail
    (ici : estimation de la probabilité d'octroi d'un crédit à partir de quelques variables).
    Remplacez la fonction `train_demo_model()` par le chargement de votre **vrai modèle**
    (`joblib.load("model.pkl")`, endpoint API, etc.).
    """
)


@st.cache_resource(show_spinner="Chargement du modèle de démonstration...")
def train_demo_model():
    """Entraîne un petit modèle logistique sur des données synthétiques.
    À remplacer par le chargement d'un vrai modèle entraîné hors-ligne."""
    from sklearn.linear_model import LogisticRegression

    rng = np.random.default_rng(42)
    n = 2000
    revenu = rng.normal(2200, 900, n).clip(300, 15000)
    montant = rng.normal(15000, 8000, n).clip(500, 100000)
    duree = rng.integers(6, 84, n)
    score_credit = rng.normal(650, 90, n).clip(300, 900)
    anciennete = rng.integers(0, 30, n)

    ratio_endettement = (montant / duree) / (revenu + 1)
    logit = (
        -3.0
        + 0.004 * score_credit
        + 0.15 * anciennete
        - 4.5 * ratio_endettement
        + 0.0003 * revenu
    )
    proba = 1 / (1 + np.exp(-logit))
    y = (rng.random(n) < proba).astype(int)

    X = np.column_stack([revenu, montant, duree, score_credit, anciennete])
    model = LogisticRegression()
    model.fit(X, y)
    return model


model = train_demo_model()

tab1, tab2 = st.tabs(["🧮 Simulation individuelle", "📂 Prédiction par lot (CSV)"])

with tab1:
    st.markdown("#### Renseignez le dossier client")
    c1, c2 = st.columns(2)
    with c1:
        revenu = st.number_input("Revenu mensuel net (TND)", 300, 20000, 2200, step=50)
        montant = st.number_input("Montant du crédit demandé (TND)", 500, 300000, 15000, step=500)
        duree = st.slider("Durée du crédit (mois)", 6, 84, 36)
    with c2:
        score_credit = st.slider("Score de crédit interne (300-900)", 300, 900, 650)
        anciennete = st.slider("Ancienneté du client (années)", 0, 40, 5)

    if st.button("🔍 Estimer la probabilité d'octroi", use_container_width=True, type="primary"):
        X = np.array([[revenu, montant, duree, score_credit, anciennete]])
        proba = model.predict_proba(X)[0][1]
        pct = round(proba * 100, 1)

        st.markdown("---")
        col1, col2 = st.columns([1, 2])
        with col1:
            st.markdown(
                f"""
                <div class="stb-card" style="text-align:center;">
                    <div class="stb-kpi-label">Probabilité d'octroi</div>
                    <div class="stb-kpi-value" style="font-size:42px;">{pct}%</div>
                </div>
                """,
                unsafe_allow_html=True,
            )
        with col2:
            st.progress(min(max(proba, 0.0), 1.0))
            if proba >= 0.7:
                st.success("✅ Dossier favorable — probabilité d'octroi élevée.")
            elif proba >= 0.4:
                st.warning("⚠️ Dossier à étudier — probabilité d'octroi modérée.")
            else:
                st.error("❌ Dossier à risque — probabilité d'octroi faible.")
        st.caption(
            "⚠️ Résultat généré par un modèle de démonstration entraîné sur des données "
            "synthétiques — à ne pas utiliser pour une décision réelle."
        )

with tab2:
    st.markdown("#### Prédiction sur un fichier de plusieurs dossiers")
    st.write(
        "Le fichier CSV doit contenir les colonnes : "
        "`revenu, montant, duree, score_credit, anciennete`"
    )
    uploaded = st.file_uploader("Déposez votre fichier CSV", type=["csv"])

    if uploaded is not None:
        try:
            df = pd.read_csv(uploaded)
            required_cols = {"revenu", "montant", "duree", "score_credit", "anciennete"}
            if not required_cols.issubset(df.columns):
                st.error(f"Colonnes manquantes. Attendu : {sorted(required_cols)}")
            else:
                X = df[["revenu", "montant", "duree", "score_credit", "anciennete"]].values
                df["probabilite_octroi_%"] = (model.predict_proba(X)[:, 1] * 100).round(1)
                df["decision_suggeree"] = np.where(
                    df["probabilite_octroi_%"] >= 70,
                    "Favorable",
                    np.where(df["probabilite_octroi_%"] >= 40, "À étudier", "Risqué"),
                )
                st.dataframe(df, use_container_width=True)
                st.download_button(
                    "⬇️ Télécharger les résultats (CSV)",
                    df.to_csv(index=False).encode("utf-8"),
                    file_name="predictions_stb.csv",
                    mime="text/csv",
                    use_container_width=True,
                )
        except Exception as e:
            st.error(f"Erreur de lecture du fichier : {e}")

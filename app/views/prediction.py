"""Vue Prédiction — prévision du chiffre d'affaires mensuel net des ventes (production).

Holt-Winters (tendance amortie) et SARIMA(1,1,0)(0,1,1)[12], tous deux
appliqués sur le logarithme du CA (croissance multiplicative), avec un
backtesting sur les 12 derniers mois connus pour valider chaque modèle avant
d'afficher les prévisions.
"""
import io
import os

import pandas as pd
import streamlit as st
from utils.ui import render_header
from utils import forecasting

render_header("Prévision du chiffre d'affaires")

default_path = forecasting.FICHIER_EXCEL_DEFAUT
source = None
if os.path.exists(default_path):
    source = default_path
    st.caption(f"📄 Source des données : `{default_path}`")
else:
    st.warning(f"⚠️ Fichier introuvable : `{default_path}`")
    uploaded_xlsx = st.file_uploader(
        "Déposez le fichier Excel des ventes", type=["xlsx"], key="forecast_xlsx_uploader"
    )
    if uploaded_xlsx is not None:
        source = uploaded_xlsx.getvalue()

if source is not None:
    try:
        resultats = forecasting.calculer_previsions(source)
    except Exception as e:
        st.error(f"Erreur lors du calcul des prévisions : {e}")
        resultats = None

    if resultats is not None:
        vue = st.segmented_control(
            "Affichage",
            options=["✅ Validation", "📈 Holt-Winters", "📉 SARIMA", "🔀 Comparaison"],
            default="📈 Holt-Winters",
            key="forecast_view_selector",
        )
        if vue is None:
            vue = "📈 Holt-Winters"

        st.markdown("---")

        # ---------------------------------------------------------------
        # Validation (backtesting sur les 12 derniers mois connus)
        # ---------------------------------------------------------------
        if vue == "✅ Validation":
            st.markdown("#### Validation des modèles (backtesting sur 12 mois)")
            st.dataframe(resultats["metriques"].round(2), use_container_width=True)
            st.pyplot(
                forecasting.figure_backtest(
                    resultats["train"], resultats["test"],
                    resultats["prev_hw_bt"], resultats["prev_sarima_bt"],
                ),
                use_container_width=True,
            )

        # ---------------------------------------------------------------
        # Holt-Winters
        # ---------------------------------------------------------------
        elif vue == "📈 Holt-Winters":
            scores = resultats["metriques"].loc["Holt-Winters"]
            c1, c2, c3 = st.columns(3)
            c1.metric("MAE", f"{scores['MAE']:,.0f}".replace(",", " "))
            c2.metric("RMSE", f"{scores['RMSE']:,.0f}".replace(",", " "))
            c3.metric("MAPE", f"{scores['MAPE (%)']:.1f}%")

            st.pyplot(
                forecasting.figure_prevision(
                    resultats["serie"], resultats["prev_hw"], "Holt-Winters",
                    couleur_prevision=forecasting.GRAPH_HW, scores=scores,
                ),
                use_container_width=True,
            )

            st.markdown("#### Valeurs prévues (Holt-Winters)")
            st.dataframe(resultats["prev_hw"].round(0).rename("ca_prevu"), use_container_width=True)

        # ---------------------------------------------------------------
        # SARIMA
        # ---------------------------------------------------------------
        elif vue == "📉 SARIMA":
            scores = resultats["metriques"].loc["SARIMA (log)"]
            c1, c2, c3 = st.columns(3)
            c1.metric("MAE", f"{scores['MAE']:,.0f}".replace(",", " "))
            c2.metric("RMSE", f"{scores['RMSE']:,.0f}".replace(",", " "))
            c3.metric("MAPE", f"{scores['MAPE (%)']:.1f}%")

            st.pyplot(
                forecasting.figure_prevision(
                    resultats["serie"], resultats["prev_sarima"], "SARIMA",
                    intervalle=resultats["intervalle_sarima"],
                    couleur_prevision=forecasting.GRAPH_SARIMA, scores=scores,
                ),
                use_container_width=True,
            )

            st.markdown("#### Valeurs prévues (SARIMA)")
            st.dataframe(resultats["prev_sarima"].round(0).rename("ca_prevu"), use_container_width=True)

        # ---------------------------------------------------------------
        # Comparaison des 2 modèles
        # ---------------------------------------------------------------
        elif vue == "🔀 Comparaison":
            st.dataframe(resultats["metriques"].round(2), use_container_width=True)

            st.pyplot(
                forecasting.figure_comparaison(
                    resultats["serie"], resultats["prev_hw"], resultats["prev_sarima"],
                    scores=resultats["metriques"],
                ),
                use_container_width=True,
            )

            st.markdown("#### Tableau des prévisions mensuelles (les 2 modèles)")
            st.dataframe(resultats["tableau_previsions"].round(0), use_container_width=True)

        st.markdown("---")
        buffer = io.BytesIO()
        with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
            resultats["tableau_previsions"].to_excel(writer, sheet_name="Previsions")
            resultats["metriques"].to_excel(writer, sheet_name="Validation_backtest")
        st.download_button(
            "⬇️ Télécharger les prévisions (Excel)",
            buffer.getvalue(),
            file_name="previsions_ventes.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True,
        )

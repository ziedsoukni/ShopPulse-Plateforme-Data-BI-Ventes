"""Prévision du chiffre d'affaires mensuel net des ventes e-commerce (Holt-Winters + SARIMA).

Adapté du script `Untitled-1.py` du projet ShopPulse (ventes e-commerce) pour une intégration directe
dans Streamlit : mêmes modèles, mêmes paramètres fixes, mais les fonctions
retournent des DataFrames / figures matplotlib au lieu d'écrire des fichiers
sur disque, et le calcul est mis en cache par Streamlit (st.cache_data).

Choix de modélisation (repris du script d'origine) :
- Les deux modèles sont appliqués sur le LOGARITHME du montant, car la série
  croît de façon multiplicative (pourcentages), pas linéaire.
- Holt-Winters : tendance additive AMORTIE (phi = 0.85, fixé en dur après
  backtesting) + saisonnalité additive (période 12 mois).
- SARIMA(1,1,0)(0,1,1)[12] sur log(montant).
- Un backtesting (entraînement 48 mois / test sur les 12 derniers mois déjà
  connus) valide objectivement chaque modèle (MAE, RMSE, MAPE) avant de
  produire les prévisions finales à 12 mois.
"""
import io

import numpy as np
import pandas as pd
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import streamlit as st

from statsmodels.tsa.holtwinters import ExponentialSmoothing
from statsmodels.tsa.statespace.sarimax import SARIMAX

# ------------------------------------------------------------------------
# Paramètres généraux (identiques au script d'origine)
# ------------------------------------------------------------------------
FICHIER_EXCEL_DEFAUT = r"C:\Users\user\Desktop\github\Plateforme Data & BI -- Detection de Fraude\donnees_ventes_ecommerce.xlsx"
FEUILLE = "fact_vente"
COLONNE_DATE = "date"
COLONNE_MONTANT = "montant"
COLONNE_STATUT = "statut_commande"
STATUTS_EXCLUS = ["Annulée", "Retournée"]

HORIZON_MOIS = 12
SAISONNALITE = 12
MOIS_BACKTEST = 12

HW_TREND = "add"
HW_SEASONAL = "add"
HW_DAMPED = True
HW_DAMPING_FACTOR = 0.85  # phi fixé en dur (voir justification dans le script d'origine)

SARIMA_ORDER = (1, 1, 0)
SARIMA_SEASONAL_ORDER = (0, 1, 1, SAISONNALITE)


# ------------------------------------------------------------------------
# 1. Chargement et préparation des données
# ------------------------------------------------------------------------
def charger_serie_mensuelle(source) -> pd.Series:
    """`source` : chemin de fichier (str) ou contenu bytes (upload Streamlit)."""
    if isinstance(source, (bytes, bytearray)):
        source = io.BytesIO(source)
    df = pd.read_excel(source, sheet_name=FEUILLE)
    df = df[~df[COLONNE_STATUT].isin(STATUTS_EXCLUS)].copy()  # CA net : hors commandes annulées / retournées
    df[COLONNE_DATE] = pd.to_datetime(df[COLONNE_DATE])

    df["mois"] = df[COLONNE_DATE].values.astype("datetime64[M]")
    serie = (
        df.groupby("mois")[COLONNE_MONTANT]
        .sum()
        .asfreq("MS")
        .fillna(0)
        .rename("ca_total")
    )
    return serie


# ------------------------------------------------------------------------
# 2. Modèle 1 : Holt-Winters sur log(montant), tendance amortie (phi fixé)
# ------------------------------------------------------------------------
def _entrainer_holt_winters(serie_train):
    log_train = np.log(serie_train)
    return ExponentialSmoothing(
        log_train,
        trend=HW_TREND,
        seasonal=HW_SEASONAL,
        seasonal_periods=SAISONNALITE,
        damped_trend=HW_DAMPED,
        initialization_method="estimated",
    ).fit(damping_trend=HW_DAMPING_FACTOR, optimized=True)


def previsions_holt_winters(serie, horizon):
    modele = _entrainer_holt_winters(serie)
    previsions_log = modele.forecast(horizon)
    previsions = np.exp(previsions_log)
    previsions.index = pd.date_range(
        start=serie.index[-1] + pd.DateOffset(months=1), periods=horizon, freq="MS"
    )
    return previsions, modele


# ------------------------------------------------------------------------
# 3. Modèle 2 : SARIMA sur log(montant)
# ------------------------------------------------------------------------
def _entrainer_sarima_log(serie_train):
    log_train = np.log(serie_train)
    return SARIMAX(
        log_train,
        order=SARIMA_ORDER,
        seasonal_order=SARIMA_SEASONAL_ORDER,
        enforce_stationarity=True,
        enforce_invertibility=True,
    ).fit(disp=False)


def previsions_sarima(serie, horizon):
    modele = _entrainer_sarima_log(serie)
    resultat = modele.get_forecast(steps=horizon)

    previsions = np.exp(resultat.predicted_mean)
    intervalle = np.exp(resultat.conf_int(alpha=0.20))  # IC à 80%

    index_futur = pd.date_range(
        start=serie.index[-1] + pd.DateOffset(months=1), periods=horizon, freq="MS"
    )
    previsions.index = index_futur
    intervalle.index = index_futur
    return previsions, intervalle, modele


# ------------------------------------------------------------------------
# 4. Backtesting : validation objective sur les 12 derniers mois connus
# ------------------------------------------------------------------------
def _calculer_metriques(y_reel, y_predit):
    erreur = y_reel.values - y_predit.values
    mae = np.mean(np.abs(erreur))
    rmse = np.sqrt(np.mean(erreur ** 2))
    mape = np.mean(np.abs(erreur / y_reel.values)) * 100
    return {"MAE": mae, "RMSE": rmse, "MAPE (%)": mape}


def executer_backtest(serie):
    train = serie.iloc[:-MOIS_BACKTEST]
    test = serie.iloc[-MOIS_BACKTEST:]

    prev_hw_bt, _ = previsions_holt_winters(train, MOIS_BACKTEST)
    prev_hw_bt.index = test.index

    prev_sarima_bt, _, _ = previsions_sarima(train, MOIS_BACKTEST)
    prev_sarima_bt.index = test.index

    metriques = pd.DataFrame(
        {
            "Holt-Winters": _calculer_metriques(test, prev_hw_bt),
            "SARIMA (log)": _calculer_metriques(test, prev_sarima_bt),
        }
    ).T

    return train, test, prev_hw_bt, prev_sarima_bt, metriques


def securiser_previsions(previsions, serie_historique):
    """Une prévision de montant ne peut pas être négative, et on plafonne à un
    multiple raisonnable du plus haut historique (5x) pour éviter toute
    divergence numérique."""
    plafond = serie_historique.max() * 5
    return previsions.clip(lower=0, upper=plafond)


# ------------------------------------------------------------------------
# 5. Graphiques (figures matplotlib, à afficher avec st.pyplot)
# ------------------------------------------------------------------------
def _formatter_axe_montant(ax):
    ax.yaxis.set_major_formatter(
        mticker.FuncFormatter(lambda x, _: f"{x:,.0f}".replace(",", " "))
    )


def figure_backtest(train, test, prev_hw_bt, prev_sarima_bt):
    fig, ax = plt.subplots(figsize=(11, 5.5))
    ax.plot(train.index, train.values, color="tab:blue", linewidth=2, label="Historique (entraînement)")
    ax.plot(test.index, test.values, color="black", linewidth=2.5, marker="o", markersize=4,
            label="Réel (période de test)")
    ax.plot(test.index, prev_hw_bt.values, color="tab:orange", linewidth=2, linestyle="--",
            marker="o", markersize=4, label="Prévu - Holt-Winters")
    ax.plot(test.index, prev_sarima_bt.values, color="tab:green", linewidth=2, linestyle="--",
            marker="s", markersize=4, label="Prévu - SARIMA")
    ax.axvline(train.index[-1], color="gray", linestyle=":", linewidth=1)
    ax.set_title("Validation des modèles (backtesting sur les 12 derniers mois connus)",
                 fontsize=12, fontweight="bold")
    ax.set_xlabel("Mois")
    ax.set_ylabel("Chiffre d'affaires net (TND)")
    _formatter_axe_montant(ax)
    ax.legend()
    ax.grid(alpha=0.3)
    fig.tight_layout()
    return fig


def figure_prevision(serie_historique, previsions, nom_modele, intervalle=None,
                      couleur_prevision="tab:orange", scores=None):
    previsions_reliees = pd.concat([serie_historique.iloc[[-1]], previsions])

    fig, ax = plt.subplots(figsize=(11, 5.5))
    ax.plot(serie_historique.index, serie_historique.values,
            label="Historique réel", color="tab:blue", linewidth=2)
    ax.plot(previsions_reliees.index, previsions_reliees.values,
            label=f"Prévision ({nom_modele})", color=couleur_prevision,
            linewidth=2, linestyle="--", marker="o", markersize=4)

    if intervalle is not None:
        inter = intervalle.copy()
        inter.loc[serie_historique.index[-1]] = [serie_historique.iloc[-1], serie_historique.iloc[-1]]
        inter = inter.sort_index()
        ax.fill_between(inter.index, inter.iloc[:, 0], inter.iloc[:, 1],
                         color=couleur_prevision, alpha=0.15, label="Intervalle de confiance (80%)")

    if scores is not None:
        texte_score = (
            f"Score du modèle (validé sur 12 mois)\n"
            f"MAE  : {scores['MAE']:,.0f}\n"
            f"RMSE : {scores['RMSE']:,.0f}\n"
            f"MAPE : {scores['MAPE (%)']:.1f}%"
        ).replace(",", " ")
        ax.text(0.02, 0.97, texte_score, transform=ax.transAxes, va="top", ha="left", fontsize=9,
                bbox=dict(boxstyle="round", facecolor="white", edgecolor=couleur_prevision, alpha=0.9))

    ax.axvline(serie_historique.index[-1], color="gray", linestyle=":", linewidth=1)
    ax.set_title(f"Chiffre d'affaires mensuel net - {nom_modele}",
                 fontsize=12, fontweight="bold")
    ax.set_xlabel("Mois")
    ax.set_ylabel("Chiffre d'affaires net (TND)")
    _formatter_axe_montant(ax)
    ax.legend()
    ax.grid(alpha=0.3)
    fig.tight_layout()
    return fig


def figure_comparaison(serie_historique, prev_hw, prev_sarima, scores=None):
    prev_hw_reliee = pd.concat([serie_historique.iloc[[-1]], prev_hw])
    prev_sarima_reliee = pd.concat([serie_historique.iloc[[-1]], prev_sarima])

    fig, ax = plt.subplots(figsize=(11, 5.5))
    ax.plot(serie_historique.index, serie_historique.values,
            label="Historique réel", color="tab:blue", linewidth=2)
    ax.plot(prev_hw_reliee.index, prev_hw_reliee.values,
            label="Prévision Holt-Winters", color="tab:orange",
            linewidth=2, linestyle="--", marker="o", markersize=4)
    ax.plot(prev_sarima_reliee.index, prev_sarima_reliee.values,
            label="Prévision SARIMA", color="tab:green",
            linewidth=2, linestyle="--", marker="s", markersize=4)
    ax.axvline(serie_historique.index[-1], color="gray", linestyle=":", linewidth=1)

    if scores is not None:
        texte_score = (
            "Scores des modèles (validés sur 12 mois)\n"
            f"Holt-Winters : MAE {scores.loc['Holt-Winters','MAE']:,.0f} | "
            f"RMSE {scores.loc['Holt-Winters','RMSE']:,.0f} | "
            f"MAPE {scores.loc['Holt-Winters','MAPE (%)']:.1f}%\n"
            f"SARIMA       : MAE {scores.loc['SARIMA (log)','MAE']:,.0f} | "
            f"RMSE {scores.loc['SARIMA (log)','RMSE']:,.0f} | "
            f"MAPE {scores.loc['SARIMA (log)','MAPE (%)']:.1f}%"
        ).replace(",", " ")
        ax.text(0.02, 0.97, texte_score, transform=ax.transAxes, va="top", ha="left", fontsize=8.5,
                bbox=dict(boxstyle="round", facecolor="white", edgecolor="gray", alpha=0.9))

    ax.set_title("Comparaison des 2 modèles de prévision - Chiffre d'affaires mensuel net",
                 fontsize=12, fontweight="bold")
    ax.set_xlabel("Mois")
    ax.set_ylabel("Chiffre d'affaires net (TND)")
    _formatter_axe_montant(ax)
    ax.legend()
    ax.grid(alpha=0.3)
    fig.tight_layout()
    return fig


# ------------------------------------------------------------------------
# 6. Point d'entrée unique (mis en cache par Streamlit)
# ------------------------------------------------------------------------
@st.cache_data(show_spinner="Entraînement des modèles de prévision (Holt-Winters + SARIMA)...")
def calculer_previsions(source, horizon: int = HORIZON_MOIS):
    """Calcule tout : backtest + prévisions finales sécurisées.
    `source` doit être hashable (chemin str, ou bytes pour un fichier uploadé)."""
    serie = charger_serie_mensuelle(source)

    train, test, prev_hw_bt, prev_sarima_bt, metriques = executer_backtest(serie)

    prev_hw, _ = previsions_holt_winters(serie, horizon)
    prev_hw = securiser_previsions(prev_hw, serie)

    prev_sarima, intervalle_sarima, _ = previsions_sarima(serie, horizon)
    prev_sarima = securiser_previsions(prev_sarima, serie)
    intervalle_sarima = intervalle_sarima.clip(lower=0)

    tableau_previsions = pd.DataFrame({"Holt-Winters": prev_hw, "SARIMA (log)": prev_sarima})
    tableau_previsions.index.name = "mois"

    return {
        "serie": serie,
        "train": train,
        "test": test,
        "prev_hw_bt": prev_hw_bt,
        "prev_sarima_bt": prev_sarima_bt,
        "metriques": metriques,
        "prev_hw": prev_hw,
        "prev_sarima": prev_sarima,
        "intervalle_sarima": intervalle_sarima,
        "tableau_previsions": tableau_previsions,
    }

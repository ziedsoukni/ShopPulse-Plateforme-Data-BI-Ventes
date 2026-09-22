# -*- coding: utf-8 -*-
"""
==============================================================================
 PREVISION DU CHIFFRE D'AFFAIRES MENSUEL - ShopPulse (ventes e-commerce)
==============================================================================

Variable à prédire : CHIFFRE D'AFFAIRES NET MENSUEL (somme de `montant` des
commandes qui ne sont ni "Annulée" ni "Retournée"), sur 60 mois
(2021-01 -> 2025-12), à partir de la feuille `fact_vente` du classeur
donnees_ventes_ecommerce.xlsx.

Pourquoi le CA net plutôt que le nombre de commandes ?
  C'est la variable à impact financier direct, la plus suivie dans un tableau
  de bord commercial ; le volume de commandes lui est fortement corrélé.

Pourquoi deux modèles, tous deux sur le LOGARITHME du CA ?
  Le CA d'une plateforme e-commerce en croissance progresse de façon
  MULTIPLICATIVE (en pourcentage) et non linéaire. Travailler sur log(CA)
  transforme cette croissance en tendance linéaire que les deux modèles
  savent prolonger, puis on repasse en TND avec exp().
    1) Holt-Winters : tendance additive AMORTIE (phi = 0,85 fixé en dur) +
       saisonnalité additive de période 12 mois, sur log(CA).
    2) SARIMA(1,1,0)(0,1,1)[12] sur log(CA), avec intervalle de confiance à 80 %.
  Les paramètres sont FIXES (aucune recherche d'hyperparamètres à l'exécution).

Saisonnalité attendue dans ces données : pics du Ramadan / Aïd, des soldes
d'été et d'hiver, de la rentrée (septembre) et du Black Friday (novembre).

Validation :
  Un backtesting (entraînement 48 mois / test sur les 12 derniers mois connus)
  donne MAE, RMSE et MAPE de chaque modèle AVANT de produire la prévision
  finale sur les 12 mois suivants (2026-01 -> 2026-12).

Sorties (dans le dossier courant) :
  - forecast_backtest_validation.png (preuve de fiabilité des modèles)
  - forecast_holtwinters.png
  - forecast_sarima.png
  - forecast_comparaison.png (les 2 modèles sur le même graphe)
  - previsions_ventes.xlsx (prévisions + métriques de validation)
==============================================================================
"""

import warnings
warnings.filterwarnings("ignore")

import pandas as pd
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker

from statsmodels.tsa.holtwinters import ExponentialSmoothing
from statsmodels.tsa.statespace.sarimax import SARIMAX

# ------------------------------------------------------------------------
# 0. PARAMETRES GENERAUX
# ------------------------------------------------------------------------
FICHIER_EXCEL   = "/mnt/user-data/outputs/donnees_ventes_ecommerce.xlsx"
FEUILLE         = "fact_vente"
COLONNE_DATE    = "date"
COLONNE_MONTANT = "montant"
COLONNE_STATUT  = "statut_commande"
STATUTS_EXCLUS  = ["Annulée", "Retournée"]

HORIZON_MOIS    = 12   # nombre de mois à prédire pour le futur
SAISONNALITE    = 12   # période saisonnière (12 = annuelle, données mensuelles)
MOIS_BACKTEST   = 12   # taille de la fenêtre de test pour la validation

# --- Paramètres FIXES du modèle 1 : Holt-Winters sur log(montant) ------
# Appliqué sur le LOGARITHME du montant (comme le modèle 2), donc sur une
# croissance en pourcentage constant : cela évite qu'il diverge du SARIMA.
# Le facteur d'amortissement (phi) est FIXÉ EN DUR à 0.85 : avec estimation
# automatique, phi tend vers 1 et le modèle extrapole une croissance trop
# agressive ; phi=0.85 donne une prévision Holt-Winters plus prudente que le SARIMA.
HW_TREND          = "add"
HW_SEASONAL       = "add"
HW_DAMPED         = True
HW_DAMPING_FACTOR = 0.85   # phi fixé en dur (voir justification ci-dessus)

# --- Paramètres FIXES du modèle 2 : SARIMA sur log(montant) -------------
# Ordre choisi par backtesting parmi plusieurs combinaisons (p,d,q)(P,D,Q,12) ;
# le log-SARIMA prolonge un taux de croissance proche de celui observé.
SARIMA_ORDER          = (1, 1, 0)
SARIMA_SEASONAL_ORDER = (0, 1, 1, SAISONNALITE)


# ------------------------------------------------------------------------
# 1. CHARGEMENT ET PREPARATION DES DONNEES
# ------------------------------------------------------------------------
def charger_serie_mensuelle(path_excel):
    df = pd.read_excel(path_excel, sheet_name=FEUILLE)
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
# 2. MODELE 1 : HOLT-WINTERS SUR LOG(MONTANT), TENDANCE AMORTIE (phi fixé)
# ------------------------------------------------------------------------
def entrainer_holt_winters(serie_train):
    log_train = np.log(serie_train)
    return ExponentialSmoothing(
        log_train,
        trend=HW_TREND,
        seasonal=HW_SEASONAL,
        seasonal_periods=SAISONNALITE,
        damped_trend=HW_DAMPED,
        initialization_method="estimated",
    ).fit(damping_trend=HW_DAMPING_FACTOR, optimized=True)
    # damping_trend est fixé en dur (HW_DAMPING_FACTOR) : seuls les autres
    # coefficients de lissage (alpha, beta, gamma) sont estimés, la
    # STRUCTURE et le facteur d'amortissement restent fixes.


def previsions_holt_winters(serie, horizon):
    modele = entrainer_holt_winters(serie)
    previsions_log = modele.forecast(horizon)
    previsions = np.exp(previsions_log)          # retour à l'échelle réelle
    previsions.index = pd.date_range(
        start=serie.index[-1] + pd.DateOffset(months=1),
        periods=horizon, freq="MS",
    )
    return previsions, modele


# ------------------------------------------------------------------------
# 3. MODELE 2 : SARIMA SUR LOG(MONTANT)
# ------------------------------------------------------------------------
def entrainer_sarima_log(serie_train):
    log_train = np.log(serie_train)
    return SARIMAX(
        log_train,
        order=SARIMA_ORDER,
        seasonal_order=SARIMA_SEASONAL_ORDER,
        enforce_stationarity=True,
        enforce_invertibility=True,
    ).fit(disp=False)


def previsions_sarima(serie, horizon):
    modele = entrainer_sarima_log(serie)
    resultat = modele.get_forecast(steps=horizon)

    previsions = np.exp(resultat.predicted_mean)            # retour à l'échelle réelle
    intervalle = np.exp(resultat.conf_int(alpha=0.20))       # IC à 80%, aussi retransformé

    index_futur = pd.date_range(
        start=serie.index[-1] + pd.DateOffset(months=1),
        periods=horizon, freq="MS",
    )
    previsions.index = index_futur
    intervalle.index = index_futur
    return previsions, intervalle, modele


# ------------------------------------------------------------------------
# 4. BACKTESTING : validation objective sur les 12 derniers mois connus
# ------------------------------------------------------------------------
def calculer_metriques(y_reel, y_predit):
    erreur = y_reel.values - y_predit.values
    mae  = np.mean(np.abs(erreur))
    rmse = np.sqrt(np.mean(erreur ** 2))
    mape = np.mean(np.abs(erreur / y_reel.values)) * 100
    return {"MAE": mae, "RMSE": rmse, "MAPE (%)": mape}


def executer_backtest(serie):
    train = serie.iloc[:-MOIS_BACKTEST]
    test  = serie.iloc[-MOIS_BACKTEST:]

    prev_hw_bt, _ = previsions_holt_winters(train, MOIS_BACKTEST)
    prev_hw_bt.index = test.index

    prev_sarima_bt, _, _ = previsions_sarima(train, MOIS_BACKTEST)
    prev_sarima_bt.index = test.index

    metriques = pd.DataFrame({
        "Holt-Winters": calculer_metriques(test, prev_hw_bt),
        "SARIMA (log)": calculer_metriques(test, prev_sarima_bt),
    }).T

    return train, test, prev_hw_bt, prev_sarima_bt, metriques


def tracer_backtest(train, test, prev_hw_bt, prev_sarima_bt, fichier_sortie):
    fig, ax = plt.subplots(figsize=(12, 6))
    ax.plot(train.index, train.values, color="tab:blue", linewidth=2,
            label="Historique (entraînement)")
    ax.plot(test.index, test.values, color="black", linewidth=2.5,
            marker="o", markersize=4, label="Réel (période de test)")
    ax.plot(test.index, prev_hw_bt.values, color="tab:orange", linewidth=2,
            linestyle="--", marker="o", markersize=4,
            label="Prévu - Holt-Winters")
    ax.plot(test.index, prev_sarima_bt.values, color="tab:green", linewidth=2,
            linestyle="--", marker="s", markersize=4,
            label="Prévu - SARIMA")
    ax.axvline(train.index[-1], color="gray", linestyle=":", linewidth=1)
    ax.set_title("Validation des modèles (backtesting sur les 12 derniers mois connus)",
                 fontsize=13, fontweight="bold")
    ax.set_xlabel("Mois")
    ax.set_ylabel("Chiffre d'affaires net (TND)")
    formatter_axe_montant(ax)
    ax.legend()
    ax.grid(alpha=0.3)
    fig.tight_layout()
    fig.savefig(fichier_sortie, dpi=150)
    plt.close(fig)


# ------------------------------------------------------------------------
# 5. CONTROLE DE COHERENCE DES PREVISIONS FINALES
# ------------------------------------------------------------------------
def securiser_previsions(previsions, serie_historique):
    """
    Une prévision de montant ne peut pas être négative. On plafonne aussi
    à un multiple raisonnable du dernier plus haut historique (5x), pour
    éviter toute divergence numérique, même si les modèles retenus sont
    déjà conçus pour ne pas s'emballer.
    """
    plafond = serie_historique.max() * 5
    return previsions.clip(lower=0, upper=plafond)


# ------------------------------------------------------------------------
# 6. GRAPHIQUES FINAUX (la prévision démarre juste après le dernier point réel)
# ------------------------------------------------------------------------
def formatter_axe_montant(ax):
    ax.yaxis.set_major_formatter(
        mticker.FuncFormatter(lambda x, _: f"{x:,.0f}".replace(",", " "))
    )


def tracer_prevision(serie_historique, previsions, nom_modele, fichier_sortie,
                      intervalle=None, couleur_prevision="tab:orange", scores=None):
    previsions_reliees = pd.concat([serie_historique.iloc[[-1]], previsions])

    fig, ax = plt.subplots(figsize=(12, 6))
    ax.plot(serie_historique.index, serie_historique.values,
            label="Historique réel", color="tab:blue", linewidth=2)
    ax.plot(previsions_reliees.index, previsions_reliees.values,
            label=f"Prévision ({nom_modele})", color=couleur_prevision,
            linewidth=2, linestyle="--", marker="o", markersize=4)

    if intervalle is not None:
        inter = intervalle.copy()
        inter.loc[serie_historique.index[-1]] = [
            serie_historique.iloc[-1], serie_historique.iloc[-1]
        ]
        inter = inter.sort_index()
        ax.fill_between(inter.index, inter.iloc[:, 0], inter.iloc[:, 1],
                         color=couleur_prevision, alpha=0.15,
                         label="Intervalle de confiance (80%)")

    if scores is not None:
        texte_score = (
            f"Score du modèle (validé sur 12 mois)\n"
            f"MAE  : {scores['MAE']:,.0f}\n"
            f"RMSE : {scores['RMSE']:,.0f}\n"
            f"MAPE : {scores['MAPE (%)']:.1f}%"
        ).replace(",", " ")
        ax.text(0.02, 0.97, texte_score, transform=ax.transAxes,
                va="top", ha="left", fontsize=10,
                bbox=dict(boxstyle="round", facecolor="white",
                          edgecolor=couleur_prevision, alpha=0.9))

    ax.axvline(serie_historique.index[-1], color="gray", linestyle=":", linewidth=1)
    ax.set_title(f"Chiffre d'affaires mensuel net - {nom_modele}",
                 fontsize=13, fontweight="bold")
    ax.set_xlabel("Mois")
    ax.set_ylabel("Chiffre d'affaires net (TND)")
    formatter_axe_montant(ax)
    ax.legend()
    ax.grid(alpha=0.3)
    fig.tight_layout()
    fig.savefig(fichier_sortie, dpi=150)
    plt.close(fig)


def tracer_comparaison(serie_historique, prev_hw, prev_sarima, fichier_sortie, scores=None):
    prev_hw_reliee = pd.concat([serie_historique.iloc[[-1]], prev_hw])
    prev_sarima_reliee = pd.concat([serie_historique.iloc[[-1]], prev_sarima])

    fig, ax = plt.subplots(figsize=(12, 6))
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
        ax.text(0.02, 0.97, texte_score, transform=ax.transAxes,
                va="top", ha="left", fontsize=9.5,
                bbox=dict(boxstyle="round", facecolor="white",
                          edgecolor="gray", alpha=0.9))

    ax.set_title("Comparaison des 2 modèles de prévision - Chiffre d'affaires mensuel net",
                 fontsize=13, fontweight="bold")
    ax.set_xlabel("Mois")
    ax.set_ylabel("Chiffre d'affaires net (TND)")
    formatter_axe_montant(ax)
    ax.legend()
    ax.grid(alpha=0.3)
    fig.tight_layout()
    fig.savefig(fichier_sortie, dpi=150)
    plt.close(fig)


# ------------------------------------------------------------------------
# 7. PROGRAMME PRINCIPAL
# ------------------------------------------------------------------------
def main():
    print("Chargement des données...")
    serie = charger_serie_mensuelle(FICHIER_EXCEL)
    print(f"Série mensuelle : {len(serie)} points, de {serie.index.min().date()} "
          f"à {serie.index.max().date()}")

    # --- Etape A : Backtesting (validation objective) --------------------
    print("\n--- Backtesting (entraînement sur 48 mois, test sur les 12 derniers "
          "mois déjà connus) ---")
    train, test, prev_hw_bt, prev_sarima_bt, metriques = executer_backtest(serie)
    print(metriques.round(2))
    tracer_backtest(train, test, prev_hw_bt, prev_sarima_bt,
                     "forecast_backtest_validation.png")

    # --- Etape B : Prévisions finales sur les 12 prochains mois ----------
    print("\nEntraînement final du modèle Holt-Winters (tendance amortie)...")
    prev_hw, modele_hw = previsions_holt_winters(serie, HORIZON_MOIS)
    prev_hw = securiser_previsions(prev_hw, serie)

    print("Entraînement final du modèle SARIMA (log)...")
    prev_sarima, intervalle_sarima, modele_sarima = previsions_sarima(serie, HORIZON_MOIS)
    prev_sarima = securiser_previsions(prev_sarima, serie)
    intervalle_sarima = intervalle_sarima.clip(lower=0)

    croissance_2025 = serie[-12:].sum()
    croissance_hw = prev_hw.sum()
    croissance_sarima = prev_sarima.sum()
    print(f"\nTotal 2025 (réel)                : {croissance_2025:,.0f}")
    print(f"Total 2026 prévu (Holt-Winters)  : {croissance_hw:,.0f}  "
          f"(x{croissance_hw / croissance_2025:.2f})")
    print(f"Total 2026 prévu (SARIMA log)    : {croissance_sarima:,.0f}  "
          f"(x{croissance_sarima / croissance_2025:.2f})")
    print("Pour comparaison, la dernière croissance annuelle réelle observée "
          "(2025 vs 2024) était de x{:.2f}".format(
              serie[-12:].sum() / serie[-24:-12].sum()))

    print("\nGénération des graphiques...")
    tracer_prevision(serie, prev_hw, "Holt-Winters",
                      "forecast_holtwinters.png", couleur_prevision="tab:orange",
                      scores=metriques.loc["Holt-Winters"])
    tracer_prevision(serie, prev_sarima, "SARIMA",
                      "forecast_sarima.png", intervalle=intervalle_sarima,
                      couleur_prevision="tab:green",
                      scores=metriques.loc["SARIMA (log)"])
    tracer_comparaison(serie, prev_hw, prev_sarima, "forecast_comparaison.png",
                        scores=metriques)

    # --- Etape C : Export Excel -------------------------------------------
    tableau_previsions = pd.DataFrame({
        "Holt-Winters": prev_hw,
        "SARIMA (log)": prev_sarima,
    })
    tableau_previsions.index.name = "mois"

    with pd.ExcelWriter("previsions_ventes.xlsx") as writer:
        tableau_previsions.to_excel(writer, sheet_name="Previsions_2026")
        metriques.to_excel(writer, sheet_name="Validation_backtest")

    print("\n=== Résumé des prévisions (montant total mensuel prévu) ===")
    print(tableau_previsions.round(0))
    print("\nFichiers générés :")
    print(" - forecast_backtest_validation.png")
    print(" - forecast_holtwinters.png")
    print(" - forecast_sarima.png")
    print(" - forecast_comparaison.png")
    print(" - previsions_ventes.xlsx")


if __name__ == "__main__":
    main()
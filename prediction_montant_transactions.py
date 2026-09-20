"""
prediction_montant_transactions.py
===================================

Prévision du MONTANT TOTAL MENSUEL des transactions (somme des montants),
avec DEUX modèles de séries temporelles différents :

    1. Holt-Winters (lissage exponentiel triple, tendance amortie + saisonnalité)
    2. SARIMA(1,1,0)(0,1,1)[12]  (modèle statistique ARIMA saisonnier)

Les deux modèles sont d'abord VALIDÉS par backtesting (3 fenêtres glissantes
de 12 mois, sur des données déjà connues) pour donner un score réaliste
(MAE / RMSE / MAPE), puis RÉ-ENTRAÎNÉS sur tout l'historique pour produire
la prévision finale des 12 prochains mois.

Pourquoi deux modèles ?
    - Holt-Winters capture bien la tendance + la saisonnalité de façon simple
      et robuste.
    - SARIMA modélise en plus l'auto-corrélation résiduelle (différenciation
      saisonnière) et fournit un intervalle de confiance à 80 %.
    Sur ce jeu de données, les deux sont proches mais SARIMA est légèrement
    plus précis (RMSE/MAE plus bas) sur la validation glissante -> il est
    retenu comme modèle "recommandé", Holt-Winters restant affiché en
    comparaison / robustesse.

Pourquoi une prévision sur log(montant) ?
    Le montant total mensuel des transactions croît de façon quasi
    exponentielle (digitalisation croissante des paiements). Travailler sur
    log(montant) transforme cette croissance exponentielle en tendance
    linéaire, ce que les deux modèles savent bien extrapoler. On repasse en
    échelle réelle avec exp() à la fin.

Utilisation :
    python prediction_montant_transactions.py
        -> cherche "donnees_PFE_BI_Talend_reduit.xlsx" dans le dossier courant

    python prediction_montant_transactions.py "chemin/vers/mon_fichier.xlsx"
        -> utilise ce fichier à la place

Dépendances (à installer une seule fois) :
    pip install pandas numpy statsmodels matplotlib openpyxl

Sorties générées dans le dossier "previsions_output/" :
    - previsions_12_mois.xlsx   (tableau des prévisions + intervalle de confiance)
    - previsions_graphique.png  (historique + prévisions des deux modèles)
"""

import sys
import warnings
from pathlib import Path

import numpy as np
import pandas as pd

warnings.filterwarnings("ignore")  # les warnings de convergence statsmodels sont sans gravité ici

from statsmodels.tsa.holtwinters import ExponentialSmoothing
from statsmodels.tsa.statespace.sarimax import SARIMAX

import matplotlib
matplotlib.use("Agg")  # génère les images sans avoir besoin d'un affichage graphique
import matplotlib.pyplot as plt


# ----------------------------------------------------------------------
# CONFIGURATION
# ----------------------------------------------------------------------
DEFAULT_DATA_PATH = "donnees_PFE_BI_Talend_reduit.xlsx"
SHEET_NAME = "TRANSACTION"
DATE_COL = "date"
AMOUNT_COL = "montant"

FORECAST_HORIZON = 12          # nombre de mois à prévoir dans le futur
BACKTEST_HORIZON = 12          # taille (en mois) de chaque fenêtre de test
N_BACKTEST_FOLDS = 3           # nombre de fenêtres de validation glissante

OUTPUT_DIR = Path("previsions_output")

# Palette du portail STB (pour un graphique cohérent avec le reste du projet)
COLOR_HIST = "#00517A"
COLOR_HW = "#0077B3"
COLOR_SARIMA = "#D4AF37"


# ----------------------------------------------------------------------
# CHARGEMENT DES DONNÉES
# ----------------------------------------------------------------------
def load_monthly_series(path: Path) -> pd.Series:
    """Charge la feuille TRANSACTION et agrège le montant total par mois."""
    if not path.exists():
        raise FileNotFoundError(
            f"Fichier introuvable : {path}\n"
            "Place ce script dans le même dossier que le fichier Excel, "
            "ou passe le chemin en argument : "
            "python prediction_montant_transactions.py \"chemin\\vers\\fichier.xlsx\""
        )

    df = pd.read_excel(path, sheet_name=SHEET_NAME, usecols=[DATE_COL, AMOUNT_COL])
    df[DATE_COL] = pd.to_datetime(df[DATE_COL])

    monthly = df.set_index(DATE_COL).resample("MS")[AMOUNT_COL].sum()
    monthly.index.freq = "MS"

    if len(monthly) < 24:
        raise ValueError(
            f"Seulement {len(monthly)} mois de données : il en faut au moins 24 "
            "(2 cycles annuels complets) pour une prévision saisonnière fiable."
        )
    return monthly


# ----------------------------------------------------------------------
# MODÈLES
# ----------------------------------------------------------------------
def forecast_holt_winters(train_log: pd.Series, horizon: int) -> np.ndarray:
    model = ExponentialSmoothing(
        train_log,
        trend="add",
        damped_trend=True,
        seasonal="add",
        seasonal_periods=12,
        initialization_method="estimated",
    )
    fit = model.fit(optimized=True)
    return fit.forecast(horizon).values


def forecast_sarima(train_log: pd.Series, horizon: int, conf_level: float = 0.80):
    """Retourne (prévision_moyenne, borne_basse, borne_haute) en log."""
    model = SARIMAX(
        train_log,
        order=(1, 1, 0),
        seasonal_order=(0, 1, 1, 12),
        enforce_stationarity=False,
        enforce_invertibility=False,
    )
    # method="powell" converge nettement mieux que l'optimiseur par défaut
    # (lbfgs) sur cette série courte -> évite des intervalles de confiance
    # aberrants (ex. bornes à 0 / +l'infini) liés à une non-convergence.
    fit = model.fit(disp=False, method="powell", maxiter=500)
    fc = fit.get_forecast(horizon)
    mean = fc.predicted_mean.values
    ci = fc.conf_int(alpha=1 - conf_level)
    return mean, ci.iloc[:, 0].values, ci.iloc[:, 1].values


def safety_cap(values: np.ndarray, historical_max: float) -> np.ndarray:
    """Sécurise les prévisions : jamais négatives, jamais > 5x le maximum historique
    (évite une extrapolation absurde en cas de dérive du modèle)."""
    return np.clip(values, 0, historical_max * 5)


# ----------------------------------------------------------------------
# ÉVALUATION
# ----------------------------------------------------------------------
def compute_metrics(y_true: np.ndarray, y_pred: np.ndarray) -> dict:
    y_true = np.asarray(y_true, dtype=float)
    y_pred = np.asarray(y_pred, dtype=float)
    mae = float(np.mean(np.abs(y_true - y_pred)))
    rmse = float(np.sqrt(np.mean((y_true - y_pred) ** 2)))
    mape = float(np.mean(np.abs((y_true - y_pred) / y_true)) * 100)
    return {"MAE": mae, "RMSE": rmse, "MAPE": mape}


def run_backtest(monthly: pd.Series, monthly_log: pd.Series, horizon: int, n_folds: int) -> dict:
    """Validation glissante : pour chaque fenêtre, on entraîne sur tout ce qui
    précède et on prévoit les `horizon` mois suivants déjà connus, qu'on
    compare aux vraies valeurs."""
    n = len(monthly_log)
    origins = sorted({n - horizon * (k + 1) for k in range(n_folds) if n - horizon * (k + 1) >= 24})

    results = {"Holt-Winters": [], "SARIMA": []}
    print(f"Validation glissante sur {len(origins)} fenêtre(s) de {horizon} mois :\n")

    for origin in origins:
        train_log = monthly_log.iloc[:origin]
        test = monthly.iloc[origin: origin + horizon]
        h = len(test)
        if h == 0:
            continue

        period_label = f"{test.index[0].strftime('%Y-%m')} -> {test.index[-1].strftime('%Y-%m')}"

        hw_pred = np.exp(forecast_holt_winters(train_log, h))
        sar_mean_log, _, _ = forecast_sarima(train_log, h)
        sar_pred = np.exp(sar_mean_log)

        m_hw = compute_metrics(test.values, hw_pred)
        m_sar = compute_metrics(test.values, sar_pred)
        results["Holt-Winters"].append(m_hw)
        results["SARIMA"].append(m_sar)

        print(f"  Fenêtre {period_label} (entraîné sur {origin} mois précédents)")
        print(f"    Holt-Winters : MAE={m_hw['MAE']:>10,.0f}  RMSE={m_hw['RMSE']:>10,.0f}  MAPE={m_hw['MAPE']:>6.2f}%")
        print(f"    SARIMA       : MAE={m_sar['MAE']:>10,.0f}  RMSE={m_sar['RMSE']:>10,.0f}  MAPE={m_sar['MAPE']:>6.2f}%")

    return results


def summarize_backtest(results: dict) -> dict:
    summary = {}
    for name, folds in results.items():
        if not folds:
            continue
        summary[name] = {k: float(np.mean([f[k] for f in folds])) for k in folds[0]}
    return summary


# ----------------------------------------------------------------------
# PROGRAMME PRINCIPAL
# ----------------------------------------------------------------------
def main():
    data_path = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(DEFAULT_DATA_PATH)

    print("=" * 78)
    print("PRÉVISION DU MONTANT TOTAL MENSUEL DES TRANSACTIONS")
    print("=" * 78)

    monthly = load_monthly_series(data_path)
    monthly_log = np.log(monthly)

    print(f"\nFichier source : {data_path}")
    print(f"Historique     : {monthly.index[0].strftime('%Y-%m')} -> {monthly.index[-1].strftime('%Y-%m')} "
          f"({len(monthly)} mois)")
    print(f"Dernier mois connu ({monthly.index[-1].strftime('%Y-%m')}) : {monthly.iloc[-1]:,.0f}")

    # ---- 1. Validation (backtesting) ----
    print("\n" + "-" * 78)
    print("ÉTAPE 1 — VALIDATION DES MODÈLES (backtesting sur données déjà connues)")
    print("-" * 78)
    results = run_backtest(monthly, monthly_log, BACKTEST_HORIZON, N_BACKTEST_FOLDS)
    summary = summarize_backtest(results)

    print("\nScore moyen sur toutes les fenêtres de validation :")
    for name, m in summary.items():
        print(f"  {name:15s} -> MAE={m['MAE']:>10,.0f}  RMSE={m['RMSE']:>10,.0f}  MAPE={m['MAPE']:>6.2f}%")

    best_model = min(summary, key=lambda k: summary[k]["MAPE"])
    print(f"\n>>> Modèle le plus précis sur cette validation : {best_model} "
          f"(MAPE moyen = {summary[best_model]['MAPE']:.2f}%)")

    # ---- 2. Prévision finale (entraînement sur tout l'historique) ----
    print("\n" + "-" * 78)
    print(f"ÉTAPE 2 — PRÉVISION DES {FORECAST_HORIZON} PROCHAINS MOIS "
          "(modèles ré-entraînés sur l'historique complet)")
    print("-" * 78)

    hist_max = float(monthly.max())
    future_index = pd.date_range(
        monthly.index[-1] + pd.offsets.MonthBegin(1), periods=FORECAST_HORIZON, freq="MS"
    )

    hw_fc = safety_cap(np.exp(forecast_holt_winters(monthly_log, FORECAST_HORIZON)), hist_max)

    sar_mean_log, sar_lo_log, sar_hi_log = forecast_sarima(monthly_log, FORECAST_HORIZON)
    sar_fc = safety_cap(np.exp(sar_mean_log), hist_max)
    sar_lo = safety_cap(np.exp(sar_lo_log), hist_max)
    sar_hi = np.exp(sar_hi_log)  # borne haute : pas de plafonnement, c'est une fourchette d'incertitude

    forecast_table = pd.DataFrame({
        "mois": future_index.strftime("%Y-%m"),
        "prevision_holt_winters": np.round(hw_fc, 2),
        "prevision_sarima": np.round(sar_fc, 2),
        "sarima_ic80_bas": np.round(sar_lo, 2),
        "sarima_ic80_haut": np.round(sar_hi, 2),
    })
    print()
    print(forecast_table.to_string(index=False))

    # ---- 3. Export ----
    OUTPUT_DIR.mkdir(exist_ok=True)

    excel_path = OUTPUT_DIR / "previsions_12_mois.xlsx"
    with pd.ExcelWriter(excel_path, engine="openpyxl") as writer:
        forecast_table.to_excel(writer, sheet_name="Prevision_12_mois", index=False)
        monthly.rename("montant_total").reset_index().rename(columns={"index": "mois"}).to_excel(
            writer, sheet_name="Historique_mensuel", index=False
        )
        pd.DataFrame(summary).T.reset_index().rename(columns={"index": "modele"}).to_excel(
            writer, sheet_name="Score_validation", index=False
        )

    fig, ax = plt.subplots(figsize=(12, 6))
    ax.plot(monthly.index, monthly.values, label="Historique", color=COLOR_HIST, linewidth=2)
    ax.plot(future_index, hw_fc, "--", marker="o", label="Prévision Holt-Winters", color=COLOR_HW)
    ax.plot(future_index, sar_fc, "--", marker="o", label="Prévision SARIMA", color=COLOR_SARIMA)
    ax.fill_between(future_index, sar_lo, sar_hi, color=COLOR_SARIMA, alpha=0.15,
                     label="Intervalle de confiance 80% (SARIMA)")
    ax.axvline(monthly.index[-1], color="grey", linestyle=":", linewidth=1)
    ax.set_title("Montant total des transactions — historique et prévision à 12 mois")
    ax.set_ylabel("Montant (TND)")
    ax.legend()
    ax.grid(alpha=0.25)
    fig.tight_layout()
    graph_path = OUTPUT_DIR / "previsions_graphique.png"
    fig.savefig(graph_path, dpi=150)

    print("\n" + "-" * 78)
    print("FICHIERS GÉNÉRÉS")
    print("-" * 78)
    print(f"  {excel_path}")
    print(f"  {graph_path}")
    print("\nTerminé.")


if __name__ == "__main__":
    main()

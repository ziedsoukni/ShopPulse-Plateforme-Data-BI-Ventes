"""Vue Détection de fraude — analyse un fichier de transactions (CSV/Excel) et
explique pourquoi chaque transaction est jugée risquée ou non.

Les seuils (Faible / Moyen / Élevé, alerte à partir de 70) reprennent la même
logique que le tableau de bord Power BI, pour rester cohérent avec le reste
du projet.
"""
import pandas as pd
import streamlit as st
from utils.ui import render_header

render_header("Détection de fraude")

st.caption(
    "Dépose un fichier de transactions (CSV ou Excel) : chaque ligne est analysée "
    "et un score de risque, avec explication, est calculé automatiquement."
)

with st.expander("ℹ️ Comment le score de risque est calculé (barème)"):
    st.markdown(
        """
        Chaque transaction reçoit une note de risque **entre 0 et 100**, construite ainsi :

        **1. Note de départ — liée au montant**
        Plus le montant est élevé, plus la note de départ monte (mais pas de façon
        linéaire : un montant 4 fois plus gros ne multiplie pas la note par 4, seulement
        par 2 environ).

        **2. Points ajoutés selon des facteurs de risque**

        | Facteur détecté | Points ajoutés |
        |---|---|
        | Canal à distance (Mobile ou Web) | + 5 |
        | Horaire nocturne (avant 6h ou après 22h) | + 10 |

        **3. Classification finale**

        | Score | Statut |
        |---|---|
        | 0 – 39 | 🟢 Faible |
        | 40 – 69 | 🟡 Moyen |
        | 70 – 100 | 🔴 Élevé (alerte) |

        *Exemple : un paiement de 500 TND par Mobile à 2h du matin obtient environ
        67 points pour le montant, + 5 (Mobile) + 10 (nocturne) = 82 → classé Élevé.*

        Ces seuils (40 / 70) sont les mêmes que ceux utilisés dans le tableau de bord
        Power BI, pour que les deux parties du projet restent cohérentes. La colonne
        **explication** du tableau ci-dessous détaille, pour chaque transaction,
        lesquels de ces facteurs ont été détectés.
        """
    )

SEUIL_ELEVE = 70
SEUIL_MOYEN = 40

COLONNES_MONTANT = ["montant", "amount", "montant_transaction"]
COLONNES_CANAL = ["canal", "channel", "type_operation"]
COLONNES_DATE = ["date", "date_transaction", "horodatage", "timestamp"]
COLONNES_HEURE = ["heure", "hour"]
COLONNES_CLIENT = ["client", "id_client", "client_id", "identifiant_client"]


def _trouver_colonne(df, candidats):
    cols_lower = {c.lower(): c for c in df.columns}
    for cand in candidats:
        if cand in cols_lower:
            return cols_lower[cand]
    return None


def calculer_score(montant: float, canal: str, heure) -> tuple:
    """Retourne (score 0-100, liste des facteurs de risque détectés)."""
    score = (max(montant, 0) ** 0.5) * 3
    facteurs = []

    if montant > 1000:
        facteurs.append(f"montant élevé ({fmt_montant(montant)} TND)")

    if isinstance(canal, str) and canal.lower() in ("web", "mobile"):
        score += 5
        facteurs.append(f"canal distant ({canal})")

    if heure is not None and (heure < 6 or heure > 22):
        score += 10
        facteurs.append(f"horaire nocturne ({heure}h)")

    return round(min(100, max(0, score)), 1), facteurs


def fmt_montant(x: float) -> str:
    return f"{x:,.0f}".replace(",", " ")


def statut_depuis_score(score: float) -> str:
    if score >= SEUIL_ELEVE:
        return "Élevé"
    if score >= SEUIL_MOYEN:
        return "Moyen"
    return "Faible"


def expliquer(statut: str, facteurs: list) -> str:
    if not facteurs:
        return "Aucun facteur de risque détecté (montant modéré, horaire normal)."
    prefixe = {
        "Élevé": "Risque élevé car : ",
        "Moyen": "Risque modéré car : ",
        "Faible": "Quelques éléments à noter : ",
    }[statut]
    return prefixe + ", ".join(facteurs) + "."


def analyser(df: pd.DataFrame) -> pd.DataFrame:
    col_montant = _trouver_colonne(df, COLONNES_MONTANT)
    col_canal = _trouver_colonne(df, COLONNES_CANAL)
    col_date = _trouver_colonne(df, COLONNES_DATE)
    col_heure = _trouver_colonne(df, COLONNES_HEURE)
    col_client = _trouver_colonne(df, COLONNES_CLIENT)

    if col_montant is None:
        raise ValueError(
            "Impossible de trouver une colonne de montant dans le fichier "
            f"(colonnes disponibles : {', '.join(map(str, df.columns))}). "
            "Renomme la colonne du montant en `montant` par exemple."
        )

    lignes = []
    for _, row in df.iterrows():
        montant = float(row[col_montant]) if pd.notna(row[col_montant]) else 0.0
        canal = str(row[col_canal]) if col_canal and pd.notna(row[col_canal]) else "Inconnu"

        heure = None
        if col_heure and pd.notna(row[col_heure]):
            try:
                heure = int(row[col_heure])
            except (TypeError, ValueError):
                heure = None
        elif col_date and pd.notna(row[col_date]):
            try:
                heure = pd.to_datetime(row[col_date]).hour
            except Exception:
                heure = None

        score, facteurs = calculer_score(montant, canal, heure)
        statut = statut_depuis_score(score)

        lignes.append(
            {
                "client": row[col_client] if col_client and pd.notna(row[col_client]) else "—",
                "montant": montant,
                "canal": canal,
                "heure": heure if heure is not None else "—",
                "score_risque": score,
                "statut_risque": statut,
                "explication": expliquer(statut, facteurs),
            }
        )

    return pd.DataFrame(lignes)


uploaded = st.file_uploader(
    "Fichier de transactions (CSV ou Excel)", type=["csv", "xlsx", "xls"]
)

if uploaded is None:
    st.info("Dépose un fichier CSV ou Excel de transactions pour lancer l'analyse.")
else:
    try:
        if uploaded.name.lower().endswith(".csv"):
            df_brut = pd.read_csv(uploaded)
        else:
            df_brut = pd.read_excel(uploaded)
    except Exception as e:
        st.error(f"Erreur de lecture du fichier : {e}")
        df_brut = None

    if df_brut is not None:
        try:
            resultats_df = analyser(df_brut)
        except ValueError as e:
            st.error(str(e))
            resultats_df = None

        if resultats_df is not None:
            nb_total = len(resultats_df)
            nb_eleve = int((resultats_df["statut_risque"] == "Élevé").sum())
            nb_moyen = int((resultats_df["statut_risque"] == "Moyen").sum())
            montant_risque = resultats_df.loc[
                resultats_df["statut_risque"] == "Élevé", "montant"
            ].sum()

            k1, k2, k3, k4 = st.columns(4)
            k1.metric("Transactions analysées", nb_total)
            k2.metric("Risque élevé", nb_eleve)
            k3.metric("Risque moyen", nb_moyen)
            k4.metric("Montant à risque", f"{fmt_montant(montant_risque)} TND")

            if nb_eleve > 0:
                pire = resultats_df.sort_values("score_risque", ascending=False).iloc[0]
                st.error(
                    f"🚨 Transaction la plus à risque : client **{pire['client']}**, "
                    f"{fmt_montant(pire['montant'])} TND via {pire['canal']} — "
                    f"score {pire['score_risque']}. {pire['explication']}"
                )
            else:
                st.success("✅ Aucune transaction à risque élevé détectée dans ce fichier.")

            st.markdown("#### Détail des transactions analysées")

            def _couleur_statut(val):
                if val == "Élevé":
                    return "background-color: #FBD5D5; color:#7A1F1F; font-weight:700;"
                if val == "Moyen":
                    return "background-color: #FDEFC8; color:#7A5B00;"
                return "background-color: #DFF3E3; color:#1E5C33;"

            styler = resultats_df.style
            if hasattr(styler, "map"):
                styler = styler.map(_couleur_statut, subset=["statut_risque"])
            else:  # pandas plus ancien
                styler = styler.applymap(_couleur_statut, subset=["statut_risque"])

            st.dataframe(styler, use_container_width=True, height=450)

            st.download_button(
                "⬇️ Télécharger l'analyse (CSV)",
                resultats_df.to_csv(index=False).encode("utf-8"),
                file_name="analyse_risque_transactions.csv",
                mime="text/csv",
                use_container_width=True,
            )

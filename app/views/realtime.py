"""Vue Risque de retour — analyse un fichier de commandes (CSV/Excel) et
explique pourquoi chaque commande présente un risque de retour ou non.

Les seuils (Faible / Moyen / Élevé, alerte à partir de 70) reprennent la même
logique que le tableau de bord Power BI (colonne Statut_Risque_Retour), pour
rester cohérent avec le reste du projet ShopPulse.
"""
import pandas as pd
import streamlit as st
from utils.ui import render_header

render_header("Risque de retour")

st.caption(
    "Dépose un fichier de commandes (CSV ou Excel, par ex. la feuille `fact_vente` "
    "ou `exemple_commandes_test.csv`) : chaque ligne est analysée et un score de "
    "risque de retour, avec explication, est calculé automatiquement."
)

with st.expander("ℹ️ Comment le score de risque de retour est calculé (barème)"):
    st.markdown(
        """
        Chaque commande reçoit une note **entre 0 et 100**, construite ainsi :

        **1. Note de départ : 20 points.**

        **2. Points ajoutés selon des facteurs de risque**

        | Facteur détecté | Points ajoutés |
        |---|---|
        | Catégorie Mode (taille / modèle inadapté) | + 22 |
        | Catégorie Électronique | + 10 |
        | Paiement à la livraison | + 14 |
        | Canal Réseaux sociaux | + 10 |
        | Remise ≥ 30 % du prix catalogue | + 8 |
        | Délai de livraison ≥ 5 jours | + 7 |
        | Montant supérieur à 1 500 TND | + 6 |

        **3. Classification finale**

        | Score | Statut |
        |---|---|
        | 0 – 39 | 🟢 Faible |
        | 40 – 69 | 🟡 Moyen |
        | 70 – 100 | 🔴 Élevé (à surveiller) |

        *Exemple : une commande Mode payée à la livraison, avec 30 % de remise,
        obtient 20 + 22 + 14 + 8 = 64 → classée Moyen ; si le délai de livraison
        dépasse 5 jours (+ 7), elle atteint 71 → Élevé.*

        Ces seuils (40 / 70) sont les mêmes que ceux du tableau de bord Power BI.
        La colonne **explication** du tableau détaille les facteurs détectés.
        """
    )

SEUIL_ELEVE = 70
SEUIL_MOYEN = 40

COLONNES_MONTANT = ["montant", "amount", "montant_commande"]
COLONNES_CANAL = ["canal", "channel"]
COLONNES_PAIEMENT = ["moyen_paiement", "paiement", "payment"]
COLONNES_CATEGORIE = ["categorie", "category"]
COLONNES_REMISE = ["remise", "discount"]
COLONNES_DELAI = ["delai_livraison", "delai", "delivery_days"]
COLONNES_CLIENT = ["client", "id_client", "client_id", "identifiant_client"]


def _trouver_colonne(df, candidats):
    cols_lower = {c.lower(): c for c in df.columns}
    for cand in candidats:
        if cand in cols_lower:
            return cols_lower[cand]
    return None


def fmt_montant(x: float) -> str:
    return f"{x:,.0f}".replace(",", " ")


def calculer_score(montant, canal, paiement, categorie, remise, delai) -> tuple:
    """Retourne (score 0-100, liste des facteurs de risque détectés)."""
    score = 20.0
    facteurs = []

    if categorie == "Mode":
        score += 22
        facteurs.append("catégorie Mode (retours fréquents : taille / modèle)")
    elif categorie == "Électronique":
        score += 10
        facteurs.append("catégorie Électronique")

    if isinstance(paiement, str) and paiement.lower().startswith("paiement à la livraison"):
        score += 14
        facteurs.append("paiement à la livraison")

    if isinstance(canal, str) and canal.lower() == "réseaux sociaux":
        score += 10
        facteurs.append("vente via réseaux sociaux")

    if remise is not None and montant + remise > 0 and remise / (montant + remise) >= 0.30:
        score += 8
        facteurs.append("remise ≥ 30 %")

    if delai is not None and delai >= 5:
        score += 7
        facteurs.append(f"délai de livraison long ({int(delai)} j)")

    if montant > 1500:
        score += 6
        facteurs.append(f"montant élevé ({fmt_montant(montant)} TND)")

    return round(min(100, max(0, score)), 1), facteurs


def statut_depuis_score(score: float) -> str:
    if score >= SEUIL_ELEVE:
        return "Élevé"
    if score >= SEUIL_MOYEN:
        return "Moyen"
    return "Faible"


def expliquer(statut: str, facteurs: list) -> str:
    if not facteurs:
        return "Aucun facteur de risque détecté (commande standard)."
    prefixe = {
        "Élevé": "Risque de retour élevé car : ",
        "Moyen": "Risque de retour modéré car : ",
        "Faible": "Quelques éléments à noter : ",
    }[statut]
    return prefixe + ", ".join(facteurs) + "."


def analyser(df: pd.DataFrame) -> pd.DataFrame:
    col_montant = _trouver_colonne(df, COLONNES_MONTANT)
    col_canal = _trouver_colonne(df, COLONNES_CANAL)
    col_paiement = _trouver_colonne(df, COLONNES_PAIEMENT)
    col_categorie = _trouver_colonne(df, COLONNES_CATEGORIE)
    col_remise = _trouver_colonne(df, COLONNES_REMISE)
    col_delai = _trouver_colonne(df, COLONNES_DELAI)
    col_client = _trouver_colonne(df, COLONNES_CLIENT)

    if col_montant is None:
        raise ValueError(
            "Impossible de trouver une colonne de montant dans le fichier "
            f"(colonnes disponibles : {', '.join(map(str, df.columns))}). "
            "Renomme la colonne du montant en `montant` par exemple."
        )

    def _val(row, col):
        return row[col] if col and pd.notna(row[col]) else None

    lignes = []
    for _, row in df.iterrows():
        montant = float(row[col_montant]) if pd.notna(row[col_montant]) else 0.0
        canal = _val(row, col_canal)
        paiement = _val(row, col_paiement)
        categorie = _val(row, col_categorie)
        remise = _val(row, col_remise)
        remise = float(remise) if remise is not None else None
        delai = _val(row, col_delai)
        delai = float(delai) if delai is not None else None

        score, facteurs = calculer_score(montant, canal, paiement, categorie, remise, delai)
        statut = statut_depuis_score(score)

        lignes.append(
            {
                "client": _val(row, col_client) or "—",
                "montant": montant,
                "canal": canal or "Inconnu",
                "categorie": categorie or "—",
                "score_risque": score,
                "statut_risque": statut,
                "explication": expliquer(statut, facteurs),
            }
        )

    return pd.DataFrame(lignes)


uploaded = st.file_uploader(
    "Fichier de commandes (CSV ou Excel)", type=["csv", "xlsx", "xls"]
)

if uploaded is None:
    st.info("Dépose un fichier CSV ou Excel de commandes pour lancer l'analyse.")
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
            k1.metric("Commandes analysées", nb_total)
            k2.metric("Risque élevé", nb_eleve)
            k3.metric("Risque moyen", nb_moyen)
            k4.metric("CA exposé aux retours", f"{fmt_montant(montant_risque)} TND")

            if nb_eleve > 0:
                pire = resultats_df.sort_values("score_risque", ascending=False).iloc[0]
                st.error(
                    f"🚨 Commande la plus à risque : client **{pire['client']}**, "
                    f"{fmt_montant(pire['montant'])} TND via {pire['canal']} — "
                    f"score {pire['score_risque']}. {pire['explication']}"
                )
            else:
                st.success("✅ Aucune commande à risque de retour élevé dans ce fichier.")

            st.markdown("#### Détail des commandes analysées")

            def _couleur_statut(val):
                if val == "Élevé":
                    return "background-color: rgba(244,63,94,0.16); color:#FCA5AF; font-weight:700;"
                if val == "Moyen":
                    return "background-color: rgba(245,158,11,0.16); color:#FBBF24;"
                return "background-color: rgba(16,185,129,0.16); color:#6EE7B7;"

            styler = resultats_df.style
            if hasattr(styler, "map"):
                styler = styler.map(_couleur_statut, subset=["statut_risque"])
            else:  # pandas plus ancien
                styler = styler.applymap(_couleur_statut, subset=["statut_risque"])

            st.dataframe(styler, use_container_width=True, height=450)

            st.download_button(
                "⬇️ Télécharger l'analyse (CSV)",
                resultats_df.to_csv(index=False).encode("utf-8"),
                file_name="analyse_risque_retour.csv",
                mime="text/csv",
                use_container_width=True,
            )

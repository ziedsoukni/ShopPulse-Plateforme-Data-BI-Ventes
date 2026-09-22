"""Assistant données (Gemini + pandas) — répond à des questions libres sur les
données Excel du projet ShopPulse (ventes e-commerce) sans jamais laisser l'IA inventer un résultat.

Adapté du script `chatbot.py` du projet ShopPulse :

    Question libre
        -> Gemini transforme la question en PLAN JSON structuré (table, filtres, opération)
        -> pandas exécute ce plan sur le fichier Excel (calcul réel, déterministe)
        -> Gemini reformule le résultat en réponse naturelle

Gemini ne fait donc jamais le calcul lui-même : il choisit quoi calculer, et
pandas calcule. Aucune bibliothèque supplémentaire (l'appel à Gemini se fait
avec `urllib`, inclus dans Python).

Connexion aux données : le fichier Excel est chargé AUTOMATIQUEMENT depuis le
chemin centralisé dans `utils/data_config.py` (aucune sélection manuelle
requise). Les feuilles, colonnes et types de données réellement présents dans
le fichier sont détectés dynamiquement à chaque chargement : si une feuille
attendue est absente, le module continue avec les autres (au lieu de planter)
et signale ce qui manque ; si des feuilles supplémentaires existent, elles
sont mises à disposition du chatbot elles aussi.
"""
import io
import json
import os
import re
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field

import pandas as pd
import streamlit as st

from utils import data_config

GEMINI_MODEL = "gemini-3.6-flash"
GEMINI_URL = f"https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_MODEL}:generateContent"
# Modèles de secours essayés si le modèle principal est surchargé (erreur 503/429).
GEMINI_FALLBACK_MODELS = ["gemini-2.5-flash", "gemini-2.0-flash"]
GEMINI_RETRY_CODES = {404, 429, 500, 502, 503, 504}  # 404 : modèle indisponible -> modèle suivant

# Chemin du fichier Excel : calculé une fois ici (compatibilité avec le code
# existant qui importe `EXCEL_PATH_DEFAUT`) — voir utils/data_config.py pour
# la configuration centralisée (secret Streamlit > variable d'environnement >
# valeur par défaut dans le dossier du projet).
EXCEL_PATH_DEFAUT = data_config.get_excel_path()

# Feuilles attendues (nom technique dans le classeur Excel) et la clé
# "métier" utilisée dans le reste du code. Le chargement reste tolérant si
# l'une d'elles est absente ou renommée : voir `load_data_safe`.
REQUIRED_SHEETS = {
    "client": "dim_client",
    "boutique": "dim_boutique",
    "produit": "dim_produit",
    "canaux": "dim_canal",
    "calendrier": "dim_temps",
    "vente": "fact_vente",
}


def get_gemini_api_key():
    """Lit la clé Gemini depuis st.secrets, sinon depuis la variable d'environnement.

    La clé n'est jamais codée en dur dans le code : elle vit uniquement dans
    `.streamlit/secrets.toml` (non versionné, voir .gitignore) ou dans
    l'environnement d'exécution.
    """
    try:
        key = st.secrets.get("GEMINI_API_KEY")
        if key:
            return key
    except Exception:
        pass
    return os.getenv("GEMINI_API_KEY")


# =========================================================
# 1) Appel à l'API Gemini (gratuite, via urllib, sans SDK)
# =========================================================
def call_gemini(prompt: str, api_key: str, temperature: float = 0.0) -> str:
    if not api_key:
        raise RuntimeError(
            "GEMINI_API_KEY manquante. Créez une clé gratuite sur "
            "https://aistudio.google.com/apikey et ajoutez-la dans .streamlit/secrets.toml"
        )
    body = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"temperature": temperature},
    }
    payload = json.dumps(body).encode("utf-8")
    last_error = None
    # Pour chaque modèle : 3 essais avec attente croissante (1 s, 2 s) avant de passer au suivant.
    for model in [GEMINI_MODEL] + GEMINI_FALLBACK_MODELS:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
        for attempt in range(3):
            req = urllib.request.Request(
                f"{url}?key={api_key}",
                data=payload,
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            try:
                with urllib.request.urlopen(req, timeout=30) as resp:
                    data = json.loads(resp.read().decode("utf-8"))
                last_error = None
                break
            except urllib.error.HTTPError as e:
                detail = e.read().decode("utf-8")
                last_error = RuntimeError(f"Erreur API Gemini ({e.code}) : {detail}")
                if e.code not in GEMINI_RETRY_CODES:
                    raise last_error  # erreur définitive (clé invalide, requête incorrecte...)
                time.sleep(2 ** attempt)
            except (urllib.error.URLError, TimeoutError) as e:
                last_error = RuntimeError(f"Connexion à Gemini impossible : {e}")
                time.sleep(2 ** attempt)
        if last_error is None:
            break
    if last_error is not None:
        raise RuntimeError(
            "Le service Gemini est momentanément surchargé, réessayez dans quelques instants. "
            f"(détail : {last_error})"
        )
    try:
        return data["candidates"][0]["content"]["parts"][0]["text"]
    except (KeyError, IndexError):
        raise RuntimeError(f"Réponse Gemini inattendue : {data}")


# =========================================================
# 2) Chargement des données Excel — détection automatique des feuilles,
#    colonnes et types, avec gestion d'erreurs explicite.
# =========================================================
@dataclass
class DataLoadResult:
    """Résultat du chargement automatique du fichier de données."""

    data: dict = field(default_factory=dict)          # clé métier -> DataFrame
    missing_sheets: list = field(default_factory=list)  # feuilles attendues absentes
    extra_sheets: dict = field(default_factory=dict)    # feuilles supplémentaires trouvées (nom -> DataFrame)
    source_label: str = ""
    error: str = ""                                     # message clair si échec total

    @property
    def ok(self) -> bool:
        return not self.error and bool(self.data)


def _read_all_sheets(source):
    """Lit toutes les feuilles du classeur. Lève une exception explicite et
    compréhensible en cas de fichier absent, illisible ou corrompu."""
    if isinstance(source, (bytes, bytearray)):
        source = io.BytesIO(source)
    return pd.read_excel(source, sheet_name=None)


@st.cache_data(show_spinner=False)
def load_data_safe(source) -> "DataLoadResult":
    """Charge automatiquement le fichier Excel et détecte les feuilles,
    colonnes et types de données réellement présents.

    `source` : chemin de fichier (str) ou contenu bytes (upload Streamlit).
    Ne lève jamais d'exception : les erreurs (fichier absent, inaccessible,
    corrompu, feuille manquante...) sont retournées dans `DataLoadResult.error`
    / `.missing_sheets` pour un affichage clair côté interface, sans jamais
    laisser le chatbot "inventer" une réponse à partir de données absentes.
    """
    label = source if isinstance(source, str) else "fichier téléversé"

    if isinstance(source, str):
        if not os.path.exists(source):
            return DataLoadResult(
                source_label=label,
                error=(
                    f"Fichier introuvable à l'emplacement configuré : `{source}`. "
                    "Vérifiez que `donnees_ventes_ecommerce.xlsx` existe bien à cet endroit, "
                    "ou ajustez `EXCEL_DATA_PATH` (secret Streamlit ou variable d'environnement)."
                ),
            )
        if not os.access(source, os.R_OK):
            return DataLoadResult(
                source_label=label,
                error=f"Fichier trouvé mais inaccessible en lecture (permissions) : `{source}`.",
            )

    try:
        sheets = _read_all_sheets(source)
    except Exception as e:  # fichier corrompu, mauvais format, feuille protégée, etc.
        return DataLoadResult(
            source_label=label,
            error=f"Impossible de lire le fichier Excel (fichier corrompu ou format invalide ?) : {e}",
        )

    data = {}
    missing_sheets = []
    for key, sheet_name in REQUIRED_SHEETS.items():
        if sheet_name in sheets:
            data[key] = sheets[sheet_name].copy()
        else:
            missing_sheets.append(sheet_name)

    # Feuilles supplémentaires (au-delà de celles attendues) : mises à
    # disposition sous leur propre nom, pour rester utile même si le classeur évolue.
    extra_sheets = {
        name: df for name, df in sheets.items() if name not in REQUIRED_SHEETS.values()
    }

    if not data:
        return DataLoadResult(
            source_label=label,
            missing_sheets=missing_sheets,
            extra_sheets=extra_sheets,
            error=(
                "Aucune des feuilles attendues n'a été trouvée dans le fichier "
                f"(feuilles présentes : {', '.join(sheets.keys()) or 'aucune'})."
            ),
        )

    # Préparations ponctuelles, uniquement si les colonnes nécessaires existent
    # réellement (le chargement ne plante pas si le schéma a légèrement changé).
    if "vente" in data:
        if "date" in data["vente"].columns:
            data["vente"]["date"] = pd.to_datetime(data["vente"]["date"], errors="coerce")
        if {"montant", "cout_total"}.issubset(data["vente"].columns):
            data["vente"]["marge"] = data["vente"]["montant"] - data["vente"]["cout_total"]
    if "calendrier" in data and "date" in data["calendrier"].columns:
        data["calendrier"]["date"] = pd.to_datetime(data["calendrier"]["date"], errors="coerce")

    return DataLoadResult(
        data=data,
        missing_sheets=missing_sheets,
        extra_sheets=extra_sheets,
        source_label=label,
    )


def load_data(source) -> dict:
    """Ancienne API (compatibilité) : retourne uniquement le dict de DataFrames,
    lève une exception si le chargement a échoué. Préférez `load_data_safe`
    dans le nouveau code pour une gestion d'erreurs propre."""
    result = load_data_safe(source)
    if result.error:
        raise RuntimeError(result.error)
    return result.data


def describe_schema(data) -> str:
    """Décrit dynamiquement les tables, colonnes ET types de données
    réellement présents (aucune colonne codée en dur : tout vient du fichier)."""
    lignes = []
    for name, df in data.items():
        colonnes = ", ".join(f"{c} ({df[c].dtype})" for c in df.columns)
        lignes.append(f"- {name} ({len(df)} lignes) : colonnes = {colonnes}")
    return "\n".join(lignes)


def known_categorical_values(data) -> dict:
    valeurs = {}
    mapping = {
        "ville_client": ("client", "ville"),
        "ville_boutique": ("boutique", "ville"),
        "region": ("client", "region"),
        "segment_client": ("client", "segment_client"),
        "canal": ("vente", "canal"),
        "moyen_paiement": ("vente", "moyen_paiement"),
        "statut_commande": ("vente", "statut_commande"),
        "categorie": ("produit", "categorie"),
    }
    for label, (table, colonne) in mapping.items():
        df = data.get(table)
        if df is not None and colonne in df.columns:
            valeurs[label] = sorted(df[colonne].dropna().unique().tolist())
    return valeurs


# =========================================================
# 3) Gemini transforme la question en "plan" JSON structuré
# =========================================================
PLAN_PROMPT_TEMPLATE = """Tu transformes une question en français en un PLAN JSON structuré pour interroger des tables pandas. Réponds UNIQUEMENT avec un objet JSON valide, sans texte autour, sans ```.

Tables et colonnes RÉELLEMENT disponibles dans le fichier (n'utilise jamais une colonne qui n'y figure pas) :
{schema}

Valeurs catégorielles connues (utilise EXACTEMENT ces valeurs si elles apparaissent dans la question) :
{known_values}

Format du JSON à produire (mets null pour tout champ non utilisé) :
{{
  "table": "client | boutique | produit | canaux | vente",
  "ville": null,
  "region": null,
  "segment_client": null,
  "canal": null,
  "moyen_paiement": null,
  "statut_commande": null,
  "categorie": null,
  "year": null,
  "operation": "count | sum | mean | max | min | nunique | top_n | groupby_count | groupby_sum | groupby_mean",
  "value_column": null,
  "sort_desc": true,
  "limit": 5,
  "groupby_column": null,
  "display_columns": null,
  "unavailable": null
}}

Règles :
- "operation" = "count" pour "combien de...".
- "operation" = "sum"/"mean"/"max"/"min"/"nunique" nécessite "value_column" (ex: "montant", "marge", "valeur_client").
- "operation" = "top_n" pour "les N meilleurs/premiers/plus...", avec "value_column" = colonne de tri, "sort_desc"=true pour "les plus élevés", false pour "les plus bas", "limit" = N (5 par défaut), "display_columns" = colonnes utiles à afficher.
- "operation" = "groupby_count" pour "répartition par...", avec "groupby_column" = la colonne de regroupement.
- "operation" = "groupby_sum"/"groupby_mean" pour "le CA / la marge / la quantité PAR région / catégorie / canal...", avec "groupby_column" = colonne de regroupement et "value_column" = colonne à agréger.
- "ville" ne s'applique qu'aux tables ayant une colonne ville, ou à "vente" (dans ce cas on filtre via la boutique).
- Si la question porte sur une information qui n'existe dans AUCUNE des tables/colonnes listées ci-dessus, ne devine rien : mets "operation" à null et renseigne "unavailable" avec une courte explication de ce qui manque.

Question : {question}
"""


def extract_json(text: str) -> dict:
    text = text.strip()
    text = re.sub(r"^```json", "", text, flags=re.IGNORECASE).strip()
    text = re.sub(r"^```", "", text).strip()
    text = re.sub(r"```$", "", text).strip()
    return json.loads(text)


def generate_plan(question: str, schema: str, known_values: dict, api_key: str) -> dict:
    prompt = PLAN_PROMPT_TEMPLATE.format(
        schema=schema, known_values=json.dumps(known_values, ensure_ascii=False), question=question
    )
    raw = call_gemini(prompt, api_key)
    return extract_json(raw)


# =========================================================
# 4) Exécution déterministe du plan avec pandas (aucune IA ici)
# =========================================================
class DonneesIndisponibles(Exception):
    """Levée quand la question porte sur une information absente du fichier
    (jamais inventée) : à afficher telle quelle à l'utilisateur."""


def execute_plan(data, plan: dict):
    if plan.get("unavailable") or not plan.get("operation"):
        raise DonneesIndisponibles(
            plan.get("unavailable")
            or "Cette information n'est pas disponible dans les données du fichier."
        )

    table = plan.get("table")
    if table not in data:
        raise DonneesIndisponibles(
            f"La table « {table} » n'existe pas dans le fichier de données actuellement chargé."
        )
    df = data[table].copy()

    ville = plan.get("ville")
    if ville:
        if "ville" in df.columns:
            df = df[df["ville"] == ville]
        elif "id_boutique" in df.columns and "boutique" in data:
            ids = data["boutique"].loc[data["boutique"]["ville"] == ville, "id_boutique"]
            df = df[df["id_boutique"].isin(ids)]

    for key in ["region", "segment_client", "canal", "moyen_paiement", "statut_commande"]:
        val = plan.get(key)
        if val and key in df.columns:
            df = df[df[key] == val]

    categorie = plan.get("categorie")
    if categorie and "id_produit" in df.columns and "produit" in data:
        ids = data["produit"].loc[data["produit"]["categorie"] == categorie, "id_produit"]
        df = df[df["id_produit"].isin(ids)]

    year = plan.get("year")
    if year and "date" in df.columns:
        df = df[pd.to_datetime(df["date"]).dt.year == int(year)]

    operation = plan.get("operation", "count")

    if operation == "count":
        return len(df), "count"

    if operation in ("sum", "mean", "max", "min", "nunique"):
        col = plan.get("value_column")
        if col not in df.columns:
            raise DonneesIndisponibles(f"La colonne « {col} » n'existe pas dans les données disponibles.")
        value = getattr(df[col], operation)()
        return value, operation

    if operation == "top_n":
        col = plan.get("value_column")
        if col not in df.columns:
            raise DonneesIndisponibles(f"La colonne de tri « {col} » n'existe pas dans les données disponibles.")
        n = int(plan.get("limit") or 5)
        ascending = not plan.get("sort_desc", True)
        sorted_df = df.sort_values(col, ascending=ascending).head(n)
        display_cols = plan.get("display_columns") or list(df.columns)
        display_cols = [c for c in display_cols if c in df.columns]
        return sorted_df[display_cols], "top_n"

    if operation == "groupby_count":
        col = plan.get("groupby_column")
        if col not in df.columns:
            raise DonneesIndisponibles(f"La colonne de regroupement « {col} » n'existe pas dans les données disponibles.")
        result = df.groupby(col).size().sort_values(ascending=False)
        return result, "groupby_count"

    if operation in ("groupby_sum", "groupby_mean"):
        group_col = plan.get("groupby_column")
        value_col = plan.get("value_column")
        if group_col not in df.columns:
            raise DonneesIndisponibles(f"La colonne de regroupement « {group_col} » n'existe pas dans les données disponibles.")
        if value_col not in df.columns:
            raise DonneesIndisponibles(f"La colonne « {value_col} » n'existe pas dans les données disponibles.")
        agg = "sum" if operation == "groupby_sum" else "mean"
        result = df.groupby(group_col)[value_col].agg(agg).sort_values(ascending=False)
        return result, operation

    raise DonneesIndisponibles(f"Opération demandée non reconnue : « {operation} ».")


# =========================================================
# 5) Gemini reformule le résultat en réponse naturelle
# =========================================================
ANSWER_PROMPT_TEMPLATE = """Tu expliques un résultat de données à un utilisateur non technique, en français, en une ou deux phrases claires, avec les chiffres clés bien mis en avant.

Question posée : {question}

Résultat réel calculé (ne l'invente jamais, utilise exactement ces chiffres) :
{result_preview}
"""


def result_to_preview(result, kind) -> str:
    if kind in ("count", "sum", "mean", "max", "min", "nunique"):
        return str(result)
    if isinstance(result, (pd.DataFrame, pd.Series)):
        return result.to_string()
    return str(result)


def generate_answer(question: str, result, kind: str, api_key: str) -> str:
    preview = result_to_preview(result, kind)
    prompt = ANSWER_PROMPT_TEMPLATE.format(question=question, result_preview=preview)
    return call_gemini(prompt, api_key, temperature=0.3)


# =========================================================
# 6) Pipeline complet — ne lève jamais d'exception non gérée : toute erreur
#    (donnée absente, table/colonne inconnue, service IA indisponible) est
#    retournée comme un message clair plutôt que de planter l'interface.
# =========================================================
def ask(question: str, data: dict, api_key: str):
    """question -> plan JSON -> calcul pandas -> réponse naturelle.
    Retourne (reponse_texte, resultat_brut_ou_None, kind, plan_ou_None)."""
    schema = describe_schema(data)
    known_values = known_categorical_values(data)
    try:
        plan = generate_plan(question, schema, known_values, api_key)
    except (json.JSONDecodeError, KeyError, ValueError) as e:
        return (
            "Je n'ai pas réussi à interpréter cette question à partir des données disponibles. "
            "Pouvez-vous la reformuler plus précisément ?",
            None,
            "erreur",
            None,
        )

    try:
        result, kind = execute_plan(data, plan)
    except DonneesIndisponibles as e:
        return (
            f"Je ne trouve pas cette information dans les données disponibles ({e}).",
            None,
            "indisponible",
            plan,
        )

    answer = generate_answer(question, result, kind, api_key)
    return answer, result, kind, plan

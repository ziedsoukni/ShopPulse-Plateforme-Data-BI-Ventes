"""Assistant données (Gemini + pandas) — répond à des questions libres sur les
données Excel du projet PFE sans jamais laisser l'IA inventer un résultat.

Adapté du script `chatbot.py` du projet PFE :

    Question libre
        -> Gemini transforme la question en PLAN JSON structuré (table, filtres, opération)
        -> pandas exécute ce plan sur le fichier Excel (calcul réel, déterministe)
        -> Gemini reformule le résultat en réponse naturelle

Gemini ne fait donc jamais le calcul lui-même : il choisit quoi calculer, et
pandas calcule. Aucune bibliothèque supplémentaire (l'appel à Gemini se fait
avec `urllib`, inclus dans Python).
"""
import io
import json
import os
import re
import urllib.error
import urllib.request

import pandas as pd
import streamlit as st

GEMINI_MODEL = "gemini-3.6-flash"
GEMINI_URL = f"https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_MODEL}:generateContent"

EXCEL_PATH_DEFAUT = r"C:\Users\user\Downloads\donnees_PFE_BI_Talend_reduit.xlsx"

REQUIRED_SHEETS = {
    "client": "CLIENT",
    "agence": "AGENCE",
    "produit": "PRODUIT",
    "compte": "COMPTE",
    "calendrier": "CALENDRIER",
    "transaction": "TRANSACTION",
}


def get_gemini_api_key():
    """Lit la clé Gemini depuis st.secrets, sinon depuis la variable d'environnement."""
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
    req = urllib.request.Request(
        f"{GEMINI_URL}?key={api_key}",
        data=json.dumps(body).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"Erreur API Gemini ({e.code}) : {e.read().decode('utf-8')}")
    try:
        return data["candidates"][0]["content"]["parts"][0]["text"]
    except (KeyError, IndexError):
        raise RuntimeError(f"Réponse Gemini inattendue : {data}")


# =========================================================
# 2) Chargement des données Excel (mis en cache par Streamlit)
# =========================================================
@st.cache_data(show_spinner=False)
def load_data(source):
    """`source` : chemin de fichier (str) ou contenu bytes (upload Streamlit)."""
    if isinstance(source, (bytes, bytearray)):
        source = io.BytesIO(source)
    sheets = pd.read_excel(source, sheet_name=None)
    data = {key: sheets[name] for key, name in REQUIRED_SHEETS.items()}
    data["transaction"]["date"] = pd.to_datetime(data["transaction"]["date"])
    data["calendrier"]["date"] = pd.to_datetime(data["calendrier"]["date"])
    return data


def describe_schema(data) -> str:
    return "\n".join(f"- {name} : colonnes = {', '.join(df.columns)}" for name, df in data.items())


def known_categorical_values(data) -> dict:
    return {
        "ville_client": sorted(data["client"]["ville"].dropna().unique().tolist()),
        "ville_agence": sorted(data["agence"]["ville"].dropna().unique().tolist()),
        "region": sorted(data["client"]["region"].dropna().unique().tolist()),
        "segment_client": sorted(data["client"]["segment_client"].dropna().unique().tolist()),
        "canal": sorted(data["transaction"]["canal"].dropna().unique().tolist()),
        "type_operation": sorted(data["transaction"]["type_operation"].dropna().unique().tolist()),
        "statut_transaction": sorted(data["transaction"]["statut_transaction"].dropna().unique().tolist()),
    }


# =========================================================
# 3) Gemini transforme la question en "plan" JSON structuré
# =========================================================
PLAN_PROMPT_TEMPLATE = """Tu transformes une question en français en un PLAN JSON structuré pour interroger des tables pandas. Réponds UNIQUEMENT avec un objet JSON valide, sans texte autour, sans ```.

Tables et colonnes disponibles :
{schema}

Valeurs catégorielles connues (utilise EXACTEMENT ces valeurs si elles apparaissent dans la question) :
{known_values}

Format du JSON à produire (mets null pour tout champ non utilisé) :
{{
  "table": "client | agence | produit | compte | transaction",
  "ville": null,
  "region": null,
  "segment_client": null,
  "canal": null,
  "type_operation": null,
  "statut_transaction": null,
  "year": null,
  "operation": "count | sum | mean | max | min | top_n | groupby_count",
  "value_column": null,
  "sort_desc": true,
  "limit": 5,
  "groupby_column": null,
  "display_columns": null
}}

Règles :
- "operation" = "count" pour "combien de...".
- "operation" = "sum"/"mean"/"max"/"min" nécessite "value_column" (ex: "montant", "revenu_mensuel").
- "operation" = "top_n" pour "les N meilleurs/premiers/plus...", avec "value_column" = colonne de tri, "sort_desc"=true pour "les plus élevés", false pour "les plus bas", "limit" = N (5 par défaut), "display_columns" = colonnes utiles à afficher.
- "operation" = "groupby_count" pour "répartition par...", avec "groupby_column" = la colonne de regroupement.
- "ville" ne s'applique qu'aux tables ayant une colonne ville, ou à "transaction" (dans ce cas on filtre via l'agence).

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
def execute_plan(data, plan: dict):
    table = plan.get("table")
    if table not in data:
        raise ValueError(f"Table inconnue dans le plan : {table}")
    df = data[table].copy()

    ville = plan.get("ville")
    if ville:
        if "ville" in df.columns:
            df = df[df["ville"] == ville]
        elif "id_agence" in df.columns:
            ids = data["agence"].loc[data["agence"]["ville"] == ville, "id_agence"]
            df = df[df["id_agence"].isin(ids)]

    for key in ["region", "segment_client", "canal", "type_operation", "statut_transaction"]:
        val = plan.get(key)
        if val and key in df.columns:
            df = df[df[key] == val]

    year = plan.get("year")
    if year and "date" in df.columns:
        df = df[pd.to_datetime(df["date"]).dt.year == int(year)]

    operation = plan.get("operation", "count")

    if operation == "count":
        return len(df), "count"

    if operation in ("sum", "mean", "max", "min"):
        col = plan.get("value_column")
        if col not in df.columns:
            raise ValueError(f"Colonne inconnue pour l'agrégation : {col}")
        value = getattr(df[col], operation)()
        return value, operation

    if operation == "top_n":
        col = plan.get("value_column")
        if col not in df.columns:
            raise ValueError(f"Colonne de tri inconnue : {col}")
        n = int(plan.get("limit") or 5)
        ascending = not plan.get("sort_desc", True)
        sorted_df = df.sort_values(col, ascending=ascending).head(n)
        display_cols = plan.get("display_columns") or list(df.columns)
        display_cols = [c for c in display_cols if c in df.columns]
        return sorted_df[display_cols], "top_n"

    if operation == "groupby_count":
        col = plan.get("groupby_column")
        if col not in df.columns:
            raise ValueError(f"Colonne de regroupement inconnue : {col}")
        result = df.groupby(col).size().sort_values(ascending=False)
        return result, "groupby_count"

    raise ValueError(f"Opération inconnue : {operation}")


# =========================================================
# 5) Gemini reformule le résultat en réponse naturelle
# =========================================================
ANSWER_PROMPT_TEMPLATE = """Tu expliques un résultat de données à un utilisateur non technique, en français, en une ou deux phrases claires, avec les chiffres clés bien mis en avant.

Question posée : {question}

Résultat réel calculé (ne l'invente jamais, utilise exactement ces chiffres) :
{result_preview}
"""


def result_to_preview(result, kind) -> str:
    if kind in ("count", "sum", "mean", "max", "min"):
        return str(result)
    if isinstance(result, (pd.DataFrame, pd.Series)):
        return result.to_string()
    return str(result)


def generate_answer(question: str, result, kind: str, api_key: str) -> str:
    preview = result_to_preview(result, kind)
    prompt = ANSWER_PROMPT_TEMPLATE.format(question=question, result_preview=preview)
    return call_gemini(prompt, api_key, temperature=0.3)


# =========================================================
# 6) Pipeline complet
# =========================================================
def ask(question: str, data: dict, api_key: str):
    """question -> plan JSON -> calcul pandas -> réponse naturelle.
    Retourne (reponse_texte, resultat_brut, kind, plan)."""
    schema = describe_schema(data)
    known_values = known_categorical_values(data)
    plan = generate_plan(question, schema, known_values, api_key)
    result, kind = execute_plan(data, plan)
    answer = generate_answer(question, result, kind, api_key)
    return answer, result, kind, plan

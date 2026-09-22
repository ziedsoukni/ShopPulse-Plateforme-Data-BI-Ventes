"""
Chatbot ShopPulse "intelligent" — comprend des questions formulées librement,
grâce à l'API gratuite Google Gemini, mais ne laisse JAMAIS l'IA inventer
un résultat : Gemini transforme la question en un PLAN structuré (JSON),
et c'est Python/pandas qui calcule le vrai résultat sur le fichier Excel.

    Question libre
        -> Gemini transforme la question en plan JSON (table, filtres, opération)
        -> pandas exécute ce plan sur le fichier Excel (calcul réel, déterministe)
        -> Gemini reformule le résultat en réponse naturelle

Aucune bibliothèque à installer en plus de pandas/openpyxl : l'appel à Gemini
se fait avec urllib (inclus dans Python), pas besoin du SDK google-generativeai.

Installation :
    pip install pandas openpyxl

Configuration :
    1. Créez une clé gratuite sur https://aistudio.google.com/apikey (aucune carte bancaire requise)
    2. Définissez-la dans un fichier .env à côté de ce script :
         GEMINI_API_KEY=AIzaxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
       (ou directement dans la variable GEMINI_API_KEY ci-dessous)

Lancer :
    python chatbot.py
"""

import os
import re
import sys
import json
import urllib.request
import urllib.error

import pandas as pd

# --- Charger le .env s'il existe (sans dépendance externe) ---
def load_dotenv_simple(path=".env"):
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, v = line.split("=", 1)
                    os.environ.setdefault(k.strip(), v.strip())


load_dotenv_simple()

# Chemin du fichier de données : par défaut, à côté de ce script (fonctionne
# quel que soit l'endroit où le projet est cloné) ; surchargeable via la
# variable d'environnement EXCEL_PATH (ou EXCEL_DATA_PATH, utilisée par
# l'application Streamlit dans app/utils/data_config.py) sans toucher au code.
_DEFAUT_EXCEL_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "donnees_ventes_ecommerce.xlsx")
EXCEL_PATH = os.getenv("EXCEL_PATH") or os.getenv("EXCEL_DATA_PATH") or _DEFAUT_EXCEL_PATH
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")  # <- lu depuis le fichier .env, ne jamais coller la clé ici
GEMINI_MODEL = "gemini-3.6-flash"  # modèle gratuit rapide
GEMINI_URL = f"https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_MODEL}:generateContent"


# =========================================================
# 1) APPEL À L'API GEMINI (gratuite, via urllib, sans SDK)
# =========================================================
def call_gemini(prompt: str, temperature: float = 0.0) -> str:
    if not GEMINI_API_KEY:
        raise RuntimeError(
            "GEMINI_API_KEY manquante. Créez une clé gratuite sur "
            "https://aistudio.google.com/apikey et mettez-la dans un fichier .env"
        )
    body = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"temperature": temperature},
    }
    req = urllib.request.Request(
        f"{GEMINI_URL}?key={GEMINI_API_KEY}",
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
# 2) CHARGEMENT DES DONNÉES EXCEL
# =========================================================
def load_data(path):
    if not os.path.exists(path):
        raise FileNotFoundError(f"Fichier Excel introuvable : {path}")
    sheets = pd.read_excel(path, sheet_name=None)
    data = {
        "client": sheets["dim_client"],
        "boutique": sheets["dim_boutique"],
        "produit": sheets["dim_produit"],
        "canaux": sheets["dim_canal"],
        "calendrier": sheets["dim_temps"],
        "vente": sheets["fact_vente"],
    }
    data["vente"]["date"] = pd.to_datetime(data["vente"]["date"])
    data["calendrier"]["date"] = pd.to_datetime(data["calendrier"]["date"])
    data["vente"]["marge"] = data["vente"]["montant"] - data["vente"]["cout_total"]
    return data


def describe_schema(data):
    """Décrit les tables et colonnes disponibles, pour que Gemini connaisse le vrai schéma."""
    lines = []
    for name, df in data.items():
        lines.append(f"- {name} : colonnes = {', '.join(df.columns)}")
    return "\n".join(lines)


def known_categorical_values(data):
    return {
        "ville_client": sorted(data["client"]["ville"].dropna().unique().tolist()),
        "ville_boutique": sorted(data["boutique"]["ville"].dropna().unique().tolist()),
        "region": sorted(data["client"]["region"].dropna().unique().tolist()),
        "segment_client": sorted(data["client"]["segment_client"].dropna().unique().tolist()),
        "canal": sorted(data["vente"]["canal"].dropna().unique().tolist()),
        "moyen_paiement": sorted(data["vente"]["moyen_paiement"].dropna().unique().tolist()),
        "statut_commande": sorted(data["vente"]["statut_commande"].dropna().unique().tolist()),
        "categorie": sorted(data["produit"]["categorie"].dropna().unique().tolist()),
    }


# =========================================================
# 3) GEMINI TRANSFORME LA QUESTION EN "PLAN" JSON STRUCTURÉ
# =========================================================
PLAN_PROMPT_TEMPLATE = """Tu transformes une question en français en un PLAN JSON structuré pour interroger des tables pandas. Réponds UNIQUEMENT avec un objet JSON valide, sans texte autour, sans ```.

Tables et colonnes disponibles :
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
  "operation": "count | sum | mean | max | min | top_n | groupby_count",
  "value_column": null,
  "sort_desc": true,
  "limit": 5,
  "groupby_column": null,
  "display_columns": null
}}

Règles :
- "operation" = "count" pour "combien de...".
- "operation" = "sum"/"mean"/"max"/"min" nécessite "value_column" (ex: "montant", "marge", "valeur_client").
- "operation" = "top_n" pour "les N meilleurs/premiers/plus...", avec "value_column" = colonne de tri, "sort_desc"=true pour "les plus élevés", false pour "les plus bas", "limit" = N (5 par défaut), "display_columns" = colonnes utiles à afficher.
- "operation" = "groupby_count" pour "répartition par...", avec "groupby_column" = la colonne de regroupement.
- "ville" ne s'applique qu'aux tables ayant une colonne ville, ou à "vente" (dans ce cas on filtre via la boutique).

Question : {question}
"""


def extract_json(text: str) -> dict:
    text = text.strip()
    text = re.sub(r"^```json", "", text, flags=re.IGNORECASE).strip()
    text = re.sub(r"^```", "", text).strip()
    text = re.sub(r"```$", "", text).strip()
    return json.loads(text)


def generate_plan(question: str, schema: str, known_values: dict) -> dict:
    prompt = PLAN_PROMPT_TEMPLATE.format(
        schema=schema, known_values=json.dumps(known_values, ensure_ascii=False), question=question
    )
    raw = call_gemini(prompt)
    return extract_json(raw)


# =========================================================
# 4) EXÉCUTION DÉTERMINISTE DU PLAN AVEC PANDAS (aucune IA ici)
# =========================================================
def execute_plan(data, plan: dict):
    table = plan.get("table")
    if table not in data:
        raise ValueError(f"Table inconnue dans le plan : {table}")
    df = data[table].copy()

    # --- Filtres ---
    ville = plan.get("ville")
    if ville:
        if "ville" in df.columns:
            df = df[df["ville"] == ville]
        elif "id_boutique" in df.columns:
            ids = data["boutique"].loc[data["boutique"]["ville"] == ville, "id_boutique"]
            df = df[df["id_boutique"].isin(ids)]

    for key in ["region", "segment_client", "canal", "moyen_paiement", "statut_commande"]:
        val = plan.get(key)
        if val and key in df.columns:
            df = df[df[key] == val]

    categorie = plan.get("categorie")
    if categorie and "id_produit" in df.columns:
        ids = data["produit"].loc[data["produit"]["categorie"] == categorie, "id_produit"]
        df = df[df["id_produit"].isin(ids)]

    year = plan.get("year")
    if year and "date" in df.columns:
        df = df[pd.to_datetime(df["date"]).dt.year == int(year)]

    # --- Opération ---
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
# 5) GEMINI REFORMULE LE RÉSULTAT EN RÉPONSE NATURELLE
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


def generate_answer(question: str, result, kind: str) -> str:
    preview = result_to_preview(result, kind)
    prompt = ANSWER_PROMPT_TEMPLATE.format(question=question, result_preview=preview)
    return call_gemini(prompt, temperature=0.3)


# =========================================================
# 6) BOUCLE PRINCIPALE
# =========================================================
def main():
    print("=" * 60)
    print(" Chatbot PFE intelligent (Gemini gratuit + pandas/Excel)")
    print("=" * 60)

    if not GEMINI_API_KEY:
        print("❌ GEMINI_API_KEY manquante. Créez une clé gratuite sur https://aistudio.google.com/apikey")
        print("   puis mettez-la dans un fichier .env à côté de ce script : GEMINI_API_KEY=AIza...")
        sys.exit(1)

    print(f"Chargement du fichier Excel : {EXCEL_PATH} ...")
    try:
        data = load_data(EXCEL_PATH)
    except Exception as e:
        print(f"❌ {e}")
        sys.exit(1)

    schema = describe_schema(data)
    known_values = known_categorical_values(data)
    print("✅ Prêt ! Posez vos questions librement (tapez 'exit' pour quitter, 'plan' pour voir le dernier plan JSON).\n")

    last_plan = None

    while True:
        try:
            question = input("Vous > ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nAu revoir !")
            break

        if not question:
            continue
        if question.lower() in ("exit", "quit", "quitter"):
            print("Au revoir !")
            break
        if question.lower() == "plan":
            print(f"\nDernier plan généré :\n{json.dumps(last_plan, ensure_ascii=False, indent=2)}\n")
            continue

        # 1) Gemini transforme la question en plan JSON
        try:
            plan = generate_plan(question, schema, known_values)
            last_plan = plan
        except Exception as e:
            print(f"❌ Erreur lors de la génération du plan : {e}\n")
            continue

        # 2) pandas exécute le plan (calcul réel, déterministe)
        try:
            result, kind = execute_plan(data, plan)
        except Exception as e:
            print(f"❌ Erreur lors de l'exécution du plan :\n{json.dumps(plan, ensure_ascii=False)}\n\n{e}\n")
            continue

        # 3) Gemini reformule le résultat en réponse naturelle
        try:
            answer = generate_answer(question, result, kind)
        except Exception as e:
            print(f"❌ Erreur lors de la génération de la réponse : {e}\n")
            continue

        print(f"\n🤖 {answer}\n")


if __name__ == "__main__":
    main()
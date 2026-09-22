"""Configuration centralisée de la source de données du portail ShopPulse.

Un seul et unique endroit définit où se trouve le fichier Excel des ventes
(`donnees_ventes_ecommerce.xlsx`) : si son emplacement doit changer un jour,
il suffit de modifier ce fichier (ou de définir une variable d'environnement /
un secret Streamlit), sans toucher au code du chatbot, de la prévision, etc.

Ordre de priorité (du plus prioritaire au moins prioritaire) :
    1. `st.secrets["EXCEL_DATA_PATH"]` (à définir dans `.streamlit/secrets.toml`
       si on veut pointer vers un autre emplacement sans toucher au code).
    2. Variable d'environnement `EXCEL_DATA_PATH`.
    3. Chemin par défaut : `donnees_ventes_ecommerce.xlsx` à la racine du
       projet (dossier parent du dossier `app/`). Ce chemin fonctionne quel
       que soit l'endroit où le dépôt est cloné sur le disque — aucun chemin
       absolu propre à une machine n'est codé en dur.

Aucun secret (clé API, mot de passe...) n'est stocké ici : uniquement
l'emplacement, sur disque, d'un fichier de données.
"""
import os
from pathlib import Path

# .../app/utils/data_config.py -> APP_DIR = .../app -> PROJECT_ROOT = racine du dépôt
APP_DIR = Path(__file__).resolve().parent.parent
PROJECT_ROOT = APP_DIR.parent

DEFAULT_EXCEL_FILENAME = "donnees_ventes_ecommerce.xlsx"
DEFAULT_EXCEL_PATH = PROJECT_ROOT / DEFAULT_EXCEL_FILENAME


def get_excel_path() -> str:
    """Retourne le chemin (str) du fichier Excel des ventes à utiliser.

    Recalculé à chaque appel : si un administrateur modifie le secret ou la
    variable d'environnement puis relance l'application, le nouveau chemin
    est pris en compte sans autre modification de code.
    """
    try:
        import streamlit as st

        secret_path = st.secrets.get("EXCEL_DATA_PATH")
        if secret_path:
            return str(secret_path)
    except Exception:
        # st.secrets peut lever une exception hors contexte Streamlit
        # (exécution en script autonome) ou si aucun secrets.toml n'existe.
        pass

    env_path = os.getenv("EXCEL_DATA_PATH")
    if env_path:
        return env_path

    return str(DEFAULT_EXCEL_PATH)


# Valeur par défaut calculée une fois à l'import, réutilisée par les modules
# qui n'ont pas besoin de la réévaluer à chaque exécution.
EXCEL_PATH = get_excel_path()

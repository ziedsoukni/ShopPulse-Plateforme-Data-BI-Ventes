# ShopPulse Portal — Application Streamlit

Portail interne de la plateforme **ShopPulse (ventes e-commerce)** avec **connexion**,
**création de compte avec vérification par e-mail**, **rapport Power BI**,
**prévision du chiffre d'affaires**, **scoring du risque de retour** et **assistant données**.

## 🚀 Lancer l'application

```bash
pip install -r requirements.txt
streamlit run app.py
```

Puis ouvrez l'URL affichée (en général http://localhost:8501).

## 🔑 Comptes de démonstration

| Identifiant | Mot de passe | Rôle  |
|-------------|--------------|-------|
| `admin`     | `admin123`   | Admin |
| `agent`     | `agent2025`  | Agent |

⚠️ **À faire avant toute mise en production** : remplacez `utils/auth.py` par une vraie
source d'authentification (base de données, LDAP, SSO...) et ne laissez jamais de mots
de passe en clair dans le code.

## 👥 Rôles et pages

| Rôle | Accueil | Power BI | Prévision | Risque de retour | Assistant | Administration |
|---|---|---|---|---|---|---|
| **Admin** | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| **Agent** | ✅ | ✅ | ✅ | ✅ | ✅ | ❌ |
| **Utilisateur** | ✅ | ❌ | ❌ | ❌ | ✅ | ❌ |

Les permissions se modifient dans `ROLE_PERMISSIONS` (`utils/permissions.py`). Les pages non
autorisées n'apparaissent pas dans la navigation.

## 📁 Structure

```
app.py                     # Connexion / inscription + navigation (st.navigation)
views/
  home.py                  # Accueil
  powerbi.py               # Intégration du rapport Power BI (URL à renseigner)
  prediction.py            # Prévision du CA mensuel (Holt-Winters + SARIMA, backtesting)
  realtime.py              # Scoring du risque de retour d'un fichier de commandes
  chatbot.py               # Assistant données (Gemini + pandas)
  admin.py                 # Gestion des utilisateurs et des rôles
utils/
  auth.py, mailer.py, permissions.py, ui.py
  forecasting.py           # Modèles de prévision (statsmodels)
  gemini_chat.py           # Question en langage naturel -> plan JSON -> calcul pandas
  floating_chat.py         # Widget de discussion flottant
data/users.json            # Comptes utilisateurs (créé automatiquement)
assets/                    # Logo et favicon ShopPulse
exemple_commandes_test.csv # Fichier d'exemple pour la page Risque de retour
```

## 📊 Données

Les pages Prévision et Assistant lisent `donnees_ventes_ecommerce.xlsx` (dossier parent du
projet, chemin par défaut dans `utils/forecasting.py` et `utils/gemini_chat.py`). Si le fichier
est introuvable, la page propose de le téléverser. Les données sont **synthétiques**.

## 📊 Page Power BI

Ouvrez `powerbiecom.pbip` dans Power BI Desktop, publiez-le dans le service Power BI, copiez l'URL d'intégration et collez-la dans
`POWERBI_URL` (`views/powerbi.py`).

## 🔮 Page Prévision

Deux modèles sur le logarithme du CA net mensuel : Holt-Winters (tendance amortie) et
SARIMA(1,1,0)(0,1,1)[12], validés par backtesting sur les 12 derniers mois avant de prévoir 12 mois.

## 🛒 Page Risque de retour

Déposez un fichier de commandes (CSV/Excel, voir `exemple_commandes_test.csv`) : chaque ligne
reçoit un score de 0 à 100 et une explication ; les seuils (40 / 70) sont ceux du tableau de bord.

## 💬 Assistant données

Nécessite une clé API Gemini : ajoutez `GEMINI_API_KEY` dans `.streamlit/secrets.toml`
(modèle : `.streamlit/secrets.toml.example`).

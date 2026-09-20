# STB Bank Portal — Application Streamlit

Portail interne avec **connexion**, **création de compte avec vérification par e-mail**,
**rapport Power BI**, **module de prédiction** et **chatbot**.

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
| `agent`     | `stb2025`    | Agent |

⚠️ **À faire avant toute mise en production** : remplacez `utils/auth.py` par une vraie
source d'authentification (base de données, LDAP, SSO...) et ne laissez jamais de mots
de passe en clair dans le code.

## 🆕 Création de compte (avec vérification e-mail)

Depuis l'écran de connexion, onglet **Créer un compte** :
1. L'utilisateur saisit nom, identifiant, e-mail, mot de passe.
2. Un code à 6 chiffres est envoyé par e-mail (valable 10 minutes).
3. L'utilisateur saisit le code → le compte est créé dans `data/users.json` et un
   e-mail de bienvenue est envoyé.

**Configurer l'envoi d'e-mails réel :**
1. Copiez `.streamlit/secrets.toml.example` vers `.streamlit/secrets.toml`.
2. Renseignez les identifiants SMTP (`host`, `port`, `user`, `password`).
   - Avec Gmail : activez la validation en 2 étapes puis créez un
     [mot de passe d'application](https://myaccount.google.com/apppasswords).
3. Relancez l'application.

**Sans configuration SMTP** : l'application fonctionne quand même en "mode démo" —
le code de vérification s'affiche directement à l'écran au lieu d'être envoyé par e-mail.

Les comptes créés sont stockés dans `data/users.json` (créé automatiquement au premier
lancement, avec les comptes démo `admin` et `agent` par défaut). Les comptes créés via
l'inscription publique reçoivent automatiquement le rôle **Utilisateur** (accès limité).

## 🛡️ Gestion des rôles (espace Admin)

Les comptes ayant le rôle **Admin** voient apparaître une page **🛠️ Administration**
dans le menu, qui permet de :
- Consulter la liste de tous les comptes (identifiant, nom, e-mail, rôle).
- **Modifier le rôle** de n'importe quel utilisateur (`Admin`, `Agent`, `Utilisateur`).
- Supprimer un compte.

**Permissions par rôle** (définies dans `utils/permissions.py`) :

| Rôle           | Accueil | Power BI | Prédiction | Chatbot | Administration |
|----------------|:-------:|:--------:|:----------:|:-------:|:---------------:|
| **Admin**      | ✅ | ✅ | ✅ | ✅ | ✅ |
| **Agent**      | ✅ | ✅ | ✅ | ✅ | ❌ |
| **Utilisateur**| ✅ | ❌ | ❌ | ✅ | ❌ |

Les pages non autorisées pour le rôle courant n'apparaissent tout simplement pas dans
la barre latérale (elles ne sont même pas enregistrées dans la navigation Streamlit),
ce qui empêche tout accès direct.

Pour changer les permissions (ex : donner Power BI aux `Utilisateur`), modifiez
simplement le dictionnaire `ROLE_PERMISSIONS` dans `utils/permissions.py`.

## 🖼️ Logo

Un logo de remplacement (générique, style "banque") a été généré dans
`assets/logo.png`. **Remplacez ce fichier par le vrai logo STB Bank** (format PNG,
fond transparent de préférence) — il apparaîtra automatiquement dans l'en-tête et
la barre latérale. Si le fichier est absent, un badge "STB" stylisé s'affiche à la place.

## 📁 Structure du projet

```
stb_app/
├── app.py                     # Connexion / inscription + navigation (st.navigation)
├── views/
│   ├── home.py                # Accueil
│   ├── powerbi.py             # Intégration d'un rapport Power BI (iframe)
│   ├── prediction.py          # Démonstrateur de prédiction (scikit-learn)
│   ├── chatbot.py             # Assistant virtuel (règles ou API Claude)
│   └── admin.py               # Gestion des utilisateurs et des rôles (Admin uniquement)
├── utils/
│   ├── auth.py                # Authentification, comptes, inscription, rôles
│   ├── mailer.py               # Envoi d'e-mails (SMTP)
│   ├── permissions.py         # Permissions par rôle (pages accessibles)
│   └── ui.py                  # Thème, en-tête, logo, horloge en direct
├── data/
│   └── users.json             # Comptes utilisateurs (créé automatiquement)
├── assets/
│   └── logo.png               # Logo (à remplacer par le vrai logo)
├── .streamlit/
│   ├── config.toml            # Thème Streamlit
│   └── secrets.toml.example   # Modèle pour la config SMTP / API
└── requirements.txt
```

> ℹ️ Les noms d'onglets de la barre latérale sont désormais définis explicitement
> dans `app.py` via `st.Page(..., title="...")`, ce qui règle les soucis d'affichage
> liés aux noms de fichiers (emojis mal interprétés selon l'OS).

## 📊 Page Power BI

Collez le lien d'intégration ("Publier sur le web" ou lien d'intégration
organisationnel Power BI) dans le champ prévu. Pour l'intégration sécurisée
(Power BI Embedded avec Azure AD), un développement backend supplémentaire est
nécessaire (génération de jeton côté serveur) — voir la documentation Microsoft.

## 🔮 Page Prédiction

Un modèle de démonstration (régression logistique scikit-learn, entraîné sur des
données synthétiques) estime une probabilité d'octroi de crédit. Remplacez la
fonction `train_demo_model()` dans `pages/2_🔮_Prediction.py` par le chargement de
votre propre modèle entraîné (`joblib.load(...)`) pour un usage réel.

## 💬 Page Chatbot

Fonctionne en mode "règles" par défaut (aucune clé requise). Pour activer des
réponses générées par Claude, créez un fichier `.streamlit/secrets.toml` :

```toml
ANTHROPIC_API_KEY = "sk-ant-..."
```

## 🎨 Personnalisation

Les couleurs du thème (bleu marine + or) se modifient dans `utils/ui.py`
(variables `PRIMARY`, `ACCENT`, `ACCENT_2`) et dans `.streamlit/config.toml`.

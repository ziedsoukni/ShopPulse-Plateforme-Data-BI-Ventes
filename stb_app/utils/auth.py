"""
Authentification + gestion des comptes du portail STB Bank.

- Les comptes sont stockés dans data/users.json (persistant entre les sessions).
- L'inscription se fait en 2 étapes : saisie des infos -> code de vérification
  envoyé par e-mail -> saisie du code -> compte créé.

⚠️ DÉMO : le stockage JSON + hachage SHA-256 conviennent pour une démonstration.
En production, utilisez une vraie base de données et un hachage dédié aux mots
de passe (bcrypt / argon2), ainsi qu'un vrai fournisseur d'envoi d'e-mails.
"""
import hashlib
import json
import os
import re
import secrets as pysecrets
import time

import streamlit as st

from utils.mailer import send_verification_code, send_welcome_email

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data")
USERS_FILE = os.path.join(DATA_DIR, "users.json")

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[a-zA-Z]{2,}$")
MAX_ATTEMPTS = 5
LOCK_SECONDS = 60
CODE_TTL_SECONDS = 600  # 10 minutes
PENDING_KEY = "pending_signup"

# Rôles disponibles dans l'application.
# - Admin       : accès complet + gestion des utilisateurs
# - Agent       : accès complet (Power BI, Prédiction, Détection de fraude, Chatbot) mais pas la gestion des comptes
# - Utilisateur : accès limité (rôle par défaut pour les inscriptions publiques)
ROLES = ["Admin", "Agent", "Utilisateur"]
DEFAULT_SIGNUP_ROLE = "Utilisateur"


# ---------------------------------------------------------------------------
# Stockage des utilisateurs (JSON)
# ---------------------------------------------------------------------------
def _hash(password: str) -> str:
    return hashlib.sha256(password.encode("utf-8")).hexdigest()


def _default_users() -> dict:
    return {
        "admin": {
            "password": _hash("admin123"),
            "name": "Administrateur",
            "role": "Admin",
            "email": "admin@stb.com.tn",
        },
        "agent": {
            "password": _hash("stb2025"),
            "name": "Agent STB",
            "role": "Agent",
            "email": "agent@stb.com.tn",
        },
    }


def load_users() -> dict:
    os.makedirs(DATA_DIR, exist_ok=True)
    if not os.path.exists(USERS_FILE):
        users = _default_users()
        save_users(users)
        return users
    try:
        with open(USERS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return _default_users()


def save_users(users: dict):
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(USERS_FILE, "w", encoding="utf-8") as f:
        json.dump(users, f, ensure_ascii=False, indent=2)


def username_exists(username: str) -> bool:
    return username.strip().lower() in load_users()


def email_exists(email: str) -> bool:
    email = email.strip().lower()
    return any(u.get("email", "").lower() == email for u in load_users().values())


def valid_email(email: str) -> bool:
    return bool(EMAIL_RE.match(email.strip()))


def valid_username(username: str) -> bool:
    return bool(re.match(r"^[a-zA-Z0-9_.]{3,20}$", username.strip()))


# ---------------------------------------------------------------------------
# Gestion des utilisateurs (réservé à l'espace Admin)
# ---------------------------------------------------------------------------
def list_users() -> dict:
    """Retourne tous les comptes (sans les mots de passe), pour l'affichage admin."""
    users = load_users()
    return {
        u: {k: v for k, v in info.items() if k != "password"}
        for u, info in users.items()
    }


def update_user_role(username: str, new_role: str) -> bool:
    if new_role not in ROLES:
        return False
    users = load_users()
    if username not in users:
        return False
    users[username]["role"] = new_role
    save_users(users)
    if st.session_state.get("username") == username:
        st.session_state["role"] = new_role
    return True


def delete_user(username: str) -> bool:
    users = load_users()
    if username not in users:
        return False
    del users[username]
    save_users(users)
    return True


# ---------------------------------------------------------------------------
# Session / connexion
# ---------------------------------------------------------------------------
def _init_state():
    defaults = {
        "authenticated": False,
        "username": None,
        "display_name": None,
        "role": None,
        "login_attempts": 0,
        "lock_until": 0.0,
        "signup_step": "form",
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


def is_authenticated() -> bool:
    _init_state()
    return st.session_state["authenticated"]


def login(username: str, password: str) -> bool:
    _init_state()
    users = load_users()
    user = users.get(username.strip().lower())
    if user and user["password"] == _hash(password):
        st.session_state["authenticated"] = True
        st.session_state["username"] = username.strip().lower()
        st.session_state["display_name"] = user["name"]
        st.session_state["role"] = user["role"]
        st.session_state["login_attempts"] = 0
        return True
    st.session_state["login_attempts"] += 1
    if st.session_state["login_attempts"] >= MAX_ATTEMPTS:
        st.session_state["lock_until"] = time.time() + LOCK_SECONDS
        st.session_state["login_attempts"] = 0
    return False


def logout():
    for key in ("authenticated", "username", "display_name", "role"):
        st.session_state[key] = None
    st.session_state["authenticated"] = False


def require_login():
    """À appeler en haut d'une page protégée (sécurité supplémentaire)."""
    _init_state()
    if not st.session_state["authenticated"]:
        st.warning("⚠️ Vous devez vous connecter pour accéder à cette page.")
        st.stop()


def require_role(*allowed_roles: str):
    """À appeler en haut d'une page réservée à certains rôles (ex : Admin)."""
    require_login()
    if st.session_state.get("role") not in allowed_roles:
        st.error("⛔ Accès refusé : cette page est réservée aux rôles " + ", ".join(allowed_roles) + ".")
        st.stop()


# ---------------------------------------------------------------------------
# UI — Connexion
# ---------------------------------------------------------------------------
def render_login_form():
    _init_state()

    remaining_lock = st.session_state["lock_until"] - time.time()
    if remaining_lock > 0:
        st.error(f"🔒 Trop de tentatives échouées. Réessayez dans {int(remaining_lock)} secondes.")
        return

    with st.form("login_form", clear_on_submit=False):
        username = st.text_input("Identifiant ou e-mail", placeholder="ex : admin")
        password = st.text_input("Mot de passe", type="password", placeholder="••••••••")
        submit = st.form_submit_button("Se connecter", use_container_width=True, type="primary")
        st.caption("Compte démo : `admin` / `admin123`  —  ou créez votre propre compte ➡️")

    if submit:
        if not username or not password:
            st.warning("Merci de renseigner l'identifiant et le mot de passe.")
        elif login(username, password):
            st.success(f"Bienvenue {st.session_state['display_name']} 👋")
            st.rerun()
        else:
            left = MAX_ATTEMPTS - st.session_state["login_attempts"]
            st.error(f"Identifiant ou mot de passe incorrect. Tentatives restantes : {left}")


# ---------------------------------------------------------------------------
# UI — Inscription (2 étapes : formulaire -> code de vérification)
# ---------------------------------------------------------------------------
def _start_signup(username: str, email: str, password: str, name: str):
    code = f"{pysecrets.randbelow(900_000) + 100_000}"
    st.session_state[PENDING_KEY] = {
        "username": username.strip().lower(),
        "email": email.strip().lower(),
        "password": _hash(password),
        "name": name.strip() or username.strip(),
        "code": code,
        "expires": time.time() + CODE_TTL_SECONDS,
        "attempts": 0,
    }
    return code


def _finalize_signup() -> tuple[bool, str]:
    pending = st.session_state.get(PENDING_KEY)
    users = load_users()
    users[pending["username"]] = {
        "password": pending["password"],
        "name": pending["name"],
        "role": DEFAULT_SIGNUP_ROLE,
        "email": pending["email"],
    }
    save_users(users)
    send_welcome_email(pending["email"], pending["name"])
    name = pending["name"]
    del st.session_state[PENDING_KEY]
    return True, name


def render_signup_form():
    """Formulaire d'inscription en 2 étapes avec vérification par e-mail."""
    _init_state()

    # -------------------- Étape 2 : saisie du code --------------------
    if st.session_state.get(PENDING_KEY):
        pending = st.session_state[PENDING_KEY]
        remaining = int(pending["expires"] - time.time())

        st.markdown("#### 📩 Vérifiez votre e-mail")
        st.write(
            f"Un code à 6 chiffres a été envoyé à **{pending['email']}**. "
            f"Il expire dans **{max(remaining, 0) // 60} min {max(remaining, 0) % 60}s**."
        )

        with st.form("verify_code_form"):
            code_input = st.text_input("Code de vérification", max_chars=6, placeholder="123456")
            col1, col2 = st.columns(2)
            with col1:
                confirm = st.form_submit_button("✅ Valider", use_container_width=True, type="primary")
            with col2:
                cancel = st.form_submit_button("↩️ Annuler", use_container_width=True)

        if cancel:
            del st.session_state[PENDING_KEY]
            st.rerun()

        if confirm:
            if remaining <= 0:
                st.error("Le code a expiré. Merci de relancer l'inscription.")
                del st.session_state[PENDING_KEY]
            elif code_input.strip() == pending["code"]:
                ok, name = _finalize_signup()
                st.success(
                    f"🎉 Compte créé avec succès pour {name} ! Vous pouvez maintenant vous connecter. "
                    f"Votre rôle par défaut est **{DEFAULT_SIGNUP_ROLE}** (accès limité) — "
                    "un administrateur pourra l'étendre si besoin."
                )
                st.balloons()
            else:
                pending["attempts"] += 1
                if pending["attempts"] >= 5:
                    st.error("Trop de tentatives incorrectes. Merci de relancer l'inscription.")
                    del st.session_state[PENDING_KEY]
                else:
                    st.error(f"Code incorrect. Tentatives restantes : {5 - pending['attempts']}")

        if st.button("📤 Renvoyer le code", use_container_width=True):
            ok, msg = send_verification_code(pending["email"], pending["code"], pending["name"])
            pending["expires"] = time.time() + CODE_TTL_SECONDS
            if ok:
                st.success("Un nouveau code a été envoyé.")
            else:
                st.info(f"Mode démo — SMTP non configuré. Votre code est : **{pending['code']}**")
        return

    # -------------------- Étape 1 : formulaire d'inscription --------------------
    st.markdown("#### 🆕 Créer un compte")
    with st.form("signup_form"):
        name = st.text_input("Nom complet", placeholder="ex : Ahmed Ben Salah")
        username = st.text_input("Identifiant souhaité", placeholder="ex : ahmed.bensalah")
        email = st.text_input("Adresse e-mail", placeholder="ex : ahmed@exemple.com")
        col1, col2 = st.columns(2)
        with col1:
            password = st.text_input("Mot de passe", type="password", placeholder="Min. 8 caractères")
        with col2:
            password2 = st.text_input("Confirmer le mot de passe", type="password")
        submit = st.form_submit_button("Créer mon compte", use_container_width=True, type="primary")

    if submit:
        errors = []
        if not name or not username or not email or not password:
            errors.append("Merci de remplir tous les champs.")
        if username and not valid_username(username):
            errors.append("L'identifiant doit contenir 3 à 20 caractères (lettres, chiffres, `.` ou `_`).")
        if username and username_exists(username):
            errors.append("Cet identifiant est déjà utilisé.")
        if email and not valid_email(email):
            errors.append("Adresse e-mail invalide.")
        if email and email_exists(email):
            errors.append("Un compte existe déjà avec cette adresse e-mail.")
        if password and len(password) < 8:
            errors.append("Le mot de passe doit contenir au moins 8 caractères.")
        if password != password2:
            errors.append("Les mots de passe ne correspondent pas.")

        if errors:
            for e in errors:
                st.error(e)
        else:
            code = _start_signup(username, email, password, name)
            ok, msg = send_verification_code(email, code, name)
            st.session_state["signup_step"] = "code"
            if not ok:
                st.info(
                    f"📭 Mode démo — SMTP non configuré, l'e-mail n'a pas été envoyé. "
                    f"Votre code de vérification est : **{code}**"
                )
            st.rerun()

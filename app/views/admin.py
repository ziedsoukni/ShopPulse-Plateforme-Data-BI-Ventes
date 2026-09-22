"""Vue Administration — réservée au rôle Admin.

Permet de consulter la liste des comptes et de modifier le rôle de chaque
utilisateur (Admin / Agent / Utilisateur), ainsi que de supprimer un compte.
"""
import pandas as pd
import streamlit as st

from utils.auth import ROLES, delete_user, list_users, require_role, update_user_role
from utils.ui import render_header

require_role("Admin")
render_header("Administration — Gestion des utilisateurs")

st.markdown(
    """
    Cette page est réservée aux administrateurs. Vous pouvez ici consulter tous les
    comptes du portail et modifier leur rôle :

    - **Admin** : accès complet + gestion des utilisateurs.
    - **Agent** : accès complet aux modules métier (Power BI, Prévision, Risque de retour, Chatbot).
    - **Utilisateur** : accès limité (Accueil + Chatbot uniquement) — rôle par défaut
      des comptes créés via l'inscription publique.
    """
)

current_username = st.session_state.get("username")
users = list_users()

# --- Indicateurs rapides -----------------------------------------------------
c1, c2, c3 = st.columns(3)
role_counts = {r: sum(1 for u in users.values() if u.get("role") == r) for r in ROLES}
for col, role in zip((c1, c2, c3), ROLES):
    with col:
        st.markdown(
            f"""
            <div class="sp-card" style="text-align:center;">
                <div class="sp-kpi-label">{role}</div>
                <div class="sp-kpi-value">{role_counts.get(role, 0)}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

st.divider()

# --- Tableau des utilisateurs -------------------------------------------------
st.markdown("### 👥 Liste des comptes")
df = pd.DataFrame(
    [
        {
            "Identifiant": u,
            "Nom": info.get("name", ""),
            "E-mail": info.get("email", ""),
            "Rôle": info.get("role", "Utilisateur"),
        }
        for u, info in sorted(users.items())
    ]
)
st.dataframe(df, use_container_width=True, hide_index=True)

st.divider()

# --- Modifier le rôle ---------------------------------------------------------
st.markdown("### ✏️ Modifier le rôle d'un utilisateur")

if not users:
    st.info("Aucun utilisateur enregistré.")
else:
    col1, col2, col3 = st.columns([2, 2, 1])
    with col1:
        target = st.selectbox(
            "Utilisateur",
            options=sorted(users.keys()),
            format_func=lambda u: f"{u} — {users[u].get('name', '')} ({users[u].get('role', '')})",
            key="admin_role_target",
        )
    with col2:
        current_role = users.get(target, {}).get("role", "Utilisateur")
        new_role = st.selectbox(
            "Nouveau rôle",
            options=ROLES,
            index=ROLES.index(current_role) if current_role in ROLES else ROLES.index("Utilisateur"),
            key="admin_role_new",
        )
    with col3:
        st.write("")
        st.write("")
        apply_clicked = st.button("💾 Appliquer", use_container_width=True, type="primary")

    self_demotion = target == current_username and new_role != "Admin"
    if self_demotion:
        st.warning(
            "⚠️ Vous êtes sur le point de modifier votre propre rôle "
            f"vers **{new_role}**, ce qui vous fera perdre l'accès Admin."
        )
        confirm_self = st.checkbox("Je confirme vouloir modifier mon propre rôle")
    else:
        confirm_self = True

    if apply_clicked:
        if current_role == new_role:
            st.info("Ce compte a déjà ce rôle.")
        elif self_demotion and not confirm_self:
            st.error("Merci de cocher la case de confirmation avant de continuer.")
        else:
            update_user_role(target, new_role)
            st.success(f"✅ Le rôle de **{target}** est maintenant **{new_role}**.")
            st.rerun()

st.divider()

# --- Supprimer un utilisateur --------------------------------------------------
with st.expander("🗑️ Supprimer un compte"):
    deletable = [u for u in users if u != current_username]
    if not deletable:
        st.caption("Aucun autre compte à supprimer.")
    else:
        col1, col2 = st.columns([3, 1])
        with col1:
            to_delete = st.selectbox(
                "Compte à supprimer",
                options=sorted(deletable),
                format_func=lambda u: f"{u} — {users[u].get('name', '')}",
                key="admin_delete_target",
            )
        with col2:
            st.write("")
            confirm_delete = st.checkbox("Confirmer", key="confirm_delete")
        if st.button("Supprimer définitivement", type="secondary", disabled=not confirm_delete):
            delete_user(to_delete)
            st.success(f"Le compte **{to_delete}** a été supprimé.")
            st.rerun()

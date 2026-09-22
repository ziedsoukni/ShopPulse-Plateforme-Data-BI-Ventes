"""
Permissions par rôle — détermine quelles pages sont visibles pour chaque rôle.

- Admin       : accès complet, y compris la gestion des utilisateurs.
- Agent       : accès complet aux modules métier (Power BI, Prévision, Risque de retour, Chatbot).
- Utilisateur : accès limité (rôle par défaut des comptes créés via inscription publique).
"""

ROLE_PERMISSIONS = {
    "Admin": {"home", "powerbi", "prediction", "realtime", "chatbot", "admin"},
    "Agent": {"home", "powerbi", "prediction", "realtime", "chatbot"},
    "Utilisateur": {"home", "chatbot"},
}


def allowed_pages(role: str) -> set:
    return ROLE_PERMISSIONS.get(role, ROLE_PERMISSIONS["Utilisateur"])


def can_access(role: str, page_key: str) -> bool:
    return page_key in allowed_pages(role)

"""
Envoi d'e-mails via SMTP pour la vérification de compte.

Configuration attendue dans .streamlit/secrets.toml :

    [smtp]
    host = "smtp.gmail.com"
    port = 587
    user = "votre.compte@gmail.com"
    password = "mot-de-passe-application"
    sender_name = "ShopPulse Portal"

Si aucune configuration n'est présente, l'application bascule automatiquement
en "mode démo" : le code de vérification est affiché à l'écran au lieu d'être
envoyé par e-mail (pratique pour tester sans configurer de serveur SMTP).
"""
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

import streamlit as st


def smtp_configured() -> bool:
    try:
        cfg = st.secrets["smtp"]
        return all(k in cfg for k in ("host", "port", "user", "password"))
    except Exception:
        return False


def send_email(to_email: str, subject: str, html_body: str) -> tuple[bool, str]:
    """Envoie un e-mail HTML. Retourne (succès, message)."""
    if not smtp_configured():
        return False, "SMTP non configuré (mode démo)."

    cfg = st.secrets["smtp"]
    sender_name = cfg.get("sender_name", "ShopPulse Portal")

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = f"{sender_name} <{cfg['user']}>"
    msg["To"] = to_email
    msg.attach(MIMEText(html_body, "html", "utf-8"))

    try:
        port = int(cfg["port"])
        if port == 465:
            with smtplib.SMTP_SSL(cfg["host"], port, timeout=15) as server:
                server.login(cfg["user"], cfg["password"])
                server.sendmail(cfg["user"], [to_email], msg.as_string())
        else:
            with smtplib.SMTP(cfg["host"], port, timeout=15) as server:
                server.ehlo()
                server.starttls()
                server.ehlo()
                server.login(cfg["user"], cfg["password"])
                server.sendmail(cfg["user"], [to_email], msg.as_string())
        return True, "E-mail envoyé avec succès."
    except Exception as e:
        return False, f"Échec de l'envoi : {e}"


def send_verification_code(to_email: str, code: str, name: str = "") -> tuple[bool, str]:
    subject = "ShopPulse Portal — Votre code de vérification"
    html = f"""
    <div style="font-family:Arial,Helvetica,sans-serif; max-width:480px; margin:auto;">
        <div style="background:#0A2647; padding:20px; border-radius:10px 10px 0 0;">
            <h2 style="color:#F28C28; margin:0;">🛒 ShopPulse Portal</h2>
        </div>
        <div style="border:1px solid #eee; border-top:none; padding:24px; border-radius:0 0 10px 10px;">
            <p>Bonjour {name or ''},</p>
            <p>Merci de votre inscription. Voici votre code de vérification :</p>
            <p style="font-size:32px; font-weight:bold; letter-spacing:6px; color:#0A2647; text-align:center; background:#F4F6F8; padding:14px; border-radius:8px;">
                {code}
            </p>
            <p>Ce code est valable <b>10 minutes</b>. Si vous n'êtes pas à l'origine de cette
            demande, vous pouvez ignorer cet e-mail en toute sécurité.</p>
            <p style="color:#888; font-size:12px; margin-top:24px;">
                ShopPulse Portal — E-mail automatique, merci de ne pas répondre.
            </p>
        </div>
    </div>
    """
    return send_email(to_email, subject, html)


def send_welcome_email(to_email: str, name: str = "") -> tuple[bool, str]:
    subject = "Bienvenue sur ShopPulse Portal 🎉"
    html = f"""
    <div style="font-family:Arial,Helvetica,sans-serif; max-width:480px; margin:auto;">
        <div style="background:#0A2647; padding:20px; border-radius:10px 10px 0 0;">
            <h2 style="color:#F28C28; margin:0;">🛒 ShopPulse Portal</h2>
        </div>
        <div style="border:1px solid #eee; border-top:none; padding:24px; border-radius:0 0 10px 10px;">
            <p>Bonjour {name or ''},</p>
            <p>Votre compte a été créé et vérifié avec succès. Vous pouvez dès à présent
            vous connecter au portail.</p>
            <p style="color:#888; font-size:12px; margin-top:24px;">
                ShopPulse Portal — E-mail automatique, merci de ne pas répondre.
            </p>
        </div>
    </div>
    """
    return send_email(to_email, subject, html)

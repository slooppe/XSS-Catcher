import smtplib
import ssl
from email.mime.text import MIMEText
from functools import wraps
from typing import Any

import requests
from app.models import XSS, Client, Settings
from flask import jsonify
from flask_jwt_extended import get_current_user


def send_mail(recipient: str, xss: XSS = None) -> None:

    settings = Settings.query.first()

    if xss:
        msg = MIMEText(f"XSS Catcher just caught a new {xss.xss_type} XSS for client {xss.client_name}! Go check it out!")
        msg["Subject"] = f"Captured XSS for client {xss.client_name}"
    else:
        msg = MIMEText("This is a test email from XSS catcher. If you are getting this, it's because your SMTP configuration works. ")
        msg["Subject"] = "XSS Catcher mail test"

    msg["To"] = recipient
    msg["From"] = f"XSS Catcher <{settings.smtp_mail_from}>"

    if settings.smtp_ssl_tls:

        context = ssl.create_default_context()

        with smtplib.SMTP_SSL(settings.smtp_host, settings.smtp_port, context=context) as server:

            smtp_server_login(settings, server)

            server.sendmail(settings.smtp_mail_from, recipient, msg.as_string())

    else:
        with smtplib.SMTP(settings.smtp_host, settings.smtp_port) as server:

            smtp_server_login(settings, server)

            if settings.starttls:
                server.starttls()

            server.sendmail(settings.smtp_mail_from, recipient, msg.as_string())


def send_webhook(recipient: str, xss: XSS = None) -> None:

    if xss:
        requests.post(url=recipient, json={"text": f"XSS Catcher just caught a new {xss.xss_type} XSS for client {xss.client.name}! Go check it out!"})

    else:
        requests.post(
            url=recipient, json={"text": "This is a test webhook from XSS catcher. If you are getting this, it's because your webhook configuration works."}
        )


def smtp_server_login(settings: Settings, server: smtplib.SMTP) -> None:
    if settings.smtp_user is not None and settings.smtp_password is not None:
        server.login(settings.smtp_user, settings.smtp_pass)


def generate_data_response(message: Any, status_code: int = 200) -> tuple:
    return jsonify(message), status_code


def generate_message_response(message: str, status_code: int = 200) -> tuple:
    return jsonify({"message": message}), status_code


def permissions(all_of=[], one_of=[]):
    """Manages permissions"""

    def deco(orig_func):
        @wraps(orig_func)
        def new_func(*args, **kwargs):
            current_user = get_current_user()
            if len(all_of) != 0:
                if "admin" in all_of:
                    if not current_user.is_admin:
                        return jsonify({"status": "error", "detail": "Only an administrator can do that"}), 403

                if "owner" in all_of:
                    if "client_id" in kwargs:
                        client = Client.query.filter_by(id=kwargs["client_id"]).first_or_404()
                        if current_user.id != client.owner_id:
                            return jsonify({"status": "error", "detail": "You are not the client's owner"}), 403

                    if "xss_id" in kwargs:
                        xss = XSS.query.filter_by(id=kwargs["xss_id"]).first_or_404()
                        if current_user.id != xss.client.owner_id:
                            return jsonify({"status": "error", "detail": "You are not the client's owner"}), 403

                return orig_func(*args, **kwargs)

            elif len(one_of) != 0:
                if "admin" in one_of:
                    if current_user.is_admin:
                        return orig_func(*args, **kwargs)

                if "owner" in one_of:
                    if "client_id" in kwargs:
                        client = Client.query.filter_by(id=kwargs["client_id"]).first_or_404()
                        if current_user.id == client.owner_id:
                            return orig_func(*args, **kwargs)
                    if "xss_id" in kwargs:
                        xss = XSS.query.filter_by(id=kwargs["xss_id"]).first_or_404()
                        if current_user.id == xss.client.owner_id:
                            return orig_func(*args, **kwargs)

                return jsonify({"status": "error", "detail": "Insufficient permissions"}), 403

            else:
                return orig_func(*args, **kwargs)

        return new_func

    return deco
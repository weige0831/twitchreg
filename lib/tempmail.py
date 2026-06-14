import re
import time

import requests

from .utils import extract_code


class TempMail:
    def __init__(self, base_url="https://mail.minecraft-cn.net", domain="olsbvgq.shop", timeout=30):
        self.base_url = base_url.rstrip("/")
        self.domain = domain
        self.timeout = timeout
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})

    def create_address(self, username):
        url = f"{self.base_url}/api/v1/addresses"
        payload = {"username": username, "domain": self.domain}
        resp = self.session.post(url, json=payload, timeout=self.timeout)
        resp.raise_for_status()
        data = resp.json()
        return data["email"], data["token"]

    def list_emails(self, token):
        url = f"{self.base_url}/api/v1/{token}/emails"
        resp = self.session.get(url, timeout=self.timeout)
        resp.raise_for_status()
        data = resp.json()
        return data.get("emails", [])

    def get_email(self, token, email_id):
        url = f"{self.base_url}/api/v1/{token}/emails/{email_id}"
        resp = self.session.get(url, timeout=self.timeout)
        resp.raise_for_status()
        return resp.json()

    def wait_for_code(self, token, timeout=180, interval=3):
        deadline = time.time() + timeout
        seen = set()
        while time.time() < deadline:
            try:
                emails = self.list_emails(token)
            except Exception:
                emails = []
            for mail in emails:
                mid = mail.get("id")
                if mid in seen:
                    continue
                seen.add(mid)
                subject = mail.get("subject", "") or ""
                sender = (mail.get("from") or "").lower()
                if "twitch" not in sender and "verify" not in subject.lower() and "code" not in subject.lower():
                    code = extract_code(subject)
                    if code:
                        return code
                code = extract_code(subject)
                if code and ("twitch" in sender or "verify" in subject.lower() or "code" in subject.lower()):
                    return code
                try:
                    detail = self.get_email(token, mid)
                except Exception:
                    detail = {}
                body = (detail.get("text") or "") + " " + (detail.get("html") or "")
                code = extract_code(subject + " " + body)
                if code:
                    return code
            time.sleep(interval)
        return None

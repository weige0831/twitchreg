import requests

TWITCH_CLIENT_ID = "kimne78kx3ncx6brgo4mv6wki5h1ko"


class TwitchError(Exception):
    def __init__(self, message, error_code=None):
        super().__init__(message)
        self.error_code = error_code


def username_taken(username, proxy=None, timeout=15):
    try:
        r = requests.head(
            f"https://passport.twitch.tv/usernames/{username}",
            headers={"Connection": "close"},
            timeout=timeout,
            proxies={"http": proxy, "https": proxy} if proxy else None,
            allow_redirects=False,
        )
        return r.status_code == 200
    except Exception:
        return False


class TwitchRegistrator:
    """Drives registration through the browser session so Kasada's proof
    headers cover every call. The payload now matches the live SPA exactly
    (isOver18 camelCase, email_verification_enabled, no integrity_token — the
    auth_passport_skip_integrity_on_signup flag is on)."""

    def __init__(self, browser, client_id=TWITCH_CLIENT_ID):
        self.browser = browser
        self.client_id = client_id

    def register(self, username, password, email, birthday,
                 email_verification_code=None):
        payload = {
            "username": username,
            "password": password,
            "email": email,
            "birthday": {
                "day": birthday["day"],
                "month": birthday["month"],
                "year": birthday["year"],
                "isOver18": True,
            },
            "email_verification_enabled": False,
            "client_id": self.client_id,
            "is_password_guide": "nist",
        }
        if email_verification_code is not None:
            payload["email_verification_code"] = email_verification_code

        result = self.browser.protected_register(payload)
        status = result["status"]
        data = result["data"]

        if status == 200 and "access_token" in data:
            return {
                "success": True,
                "access_token": data.get("access_token"),
                "user_id": str(data.get("userID") or data.get("user_id") or ""),
            }

        error_code = data.get("error_code")
        error_msg = data.get("error") or data.get("Error") or "unknown"
        if error_code == 2026:
            return {"success": False, "need_verification": True}
        if error_code == 2013:
            raise TwitchError(f"Email used too many times: {error_msg}", error_code=2013)
        raise TwitchError(
            f"Register failed [{error_code}]: {error_msg} | {str(data)[:300]}",
            error_code=error_code,
        )

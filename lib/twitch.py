import requests

TWITCH_CLIENT_ID = "kimne78kx3ncx6brgo4mv6wki5h1ko"
PROTECTED_REGISTER_URL = "https://passport.twitch.tv/protected_register"
USERNAME_CHECK_URL = "https://passport.twitch.tv/usernames/"


class TwitchError(Exception):
    def __init__(self, message, error_code=None, status_code=None):
        super().__init__(message)
        self.error_code = error_code
        self.status_code = status_code


class TwitchProtocol:
    def __init__(self, user_agent, cookies, proxy=None, timeout=40):
        self.session = requests.Session()
        self.user_agent = user_agent
        self.cookies = cookies or {}
        self.timeout = timeout
        if proxy:
            self.session.proxies = {"http": proxy, "https": proxy}
        self.session.headers.update({
            "User-Agent": user_agent,
            "Accept": "*/*",
            "Accept-Language": "en-US,en;q=0.5",
            "Referer": "https://www.twitch.tv/",
            "Origin": "https://www.twitch.tv",
            "Sec-Fetch-Dest": "empty",
            "Sec-Fetch-Mode": "cors",
            "Sec-Fetch-Site": "same-site",
        })

    def _cookie_header(self, extra=None):
        merged = dict(self.cookies)
        if extra:
            merged.update(extra)
        return "; ".join(f"{k}={v}" for k, v in merged.items())

    def username_taken(self, username):
        try:
            resp = self.session.head(
                USERNAME_CHECK_URL + username,
                headers={"Connection": "close"},
                timeout=self.timeout,
                allow_redirects=False,
            )
            return resp.status_code == 200
        except Exception:
            return False

    def register(self, username, password, email, birthday, integrity_token, email_verification_code=None):
        payload = {
            "username": username,
            "password": password,
            "client_id": TWITCH_CLIENT_ID,
            "birthday": {
                "day": birthday["day"],
                "month": birthday["month"],
                "year": birthday["year"],
            },
            "email": email,
            "integrity_token": integrity_token,
            "is_password_guide": "nist",
        }
        if email_verification_code is not None:
            payload["email_verification_code"] = email_verification_code

        headers = {
            "Content-Type": "text/plain;charset=UTF-8",
            "Cookie": self._cookie_header(),
        }
        import json as _json
        resp = self.session.post(
            PROTECTED_REGISTER_URL,
            data=_json.dumps(payload),
            headers=headers,
            timeout=self.timeout,
        )
        try:
            data = resp.json()
        except Exception:
            raise TwitchError(
                f"Non-JSON register response (HTTP {resp.status_code}): {resp.text[:300]}",
                status_code=resp.status_code,
            )

        if resp.status_code == 200 and "access_token" in data:
            return {
                "success": True,
                "access_token": data.get("access_token"),
                "user_id": str(data.get("userID") or data.get("user_id") or ""),
            }

        error_code = data.get("error_code") or data.get("ErrorCode")
        error_msg = data.get("error") or data.get("Error") or "unknown"
        if error_code == 2026:
            return {"success": False, "need_verification": True}
        if error_code == 2013:
            raise TwitchError(f"Email used too many times: {error_msg}", error_code=2013, status_code=resp.status_code)
        raise TwitchError(
            f"Register failed [{error_code}]: {error_msg} | full: {str(data)[:300]}",
            error_code=error_code,
            status_code=resp.status_code,
        )

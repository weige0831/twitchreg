import json
import time

from playwright.sync_api import sync_playwright


SIGNUP_URL = "https://www.twitch.tv/signup"
TWITCH_URL = "https://www.twitch.tv"
INTEGRITY_URL = "https://passport.twitch.tv/integrity"
REGISTER_URL = "https://passport.twitch.tv/protected_register"

UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
)

INTEGRITY_JS = """
async () => {
    try {
        const resp = await fetch("%s", {
            method: "POST",
            credentials: "include",
            headers: { "Content-Type": "text/plain;charset=UTF-8" },
            body: "",
        });
        const text = await resp.text();
        let data = {};
        try { data = JSON.parse(text); } catch (e) {}
        return { status: resp.status, token: data.token || null, raw: text.slice(0, 400) };
    } catch (e) {
        return { status: 0, token: null, raw: String(e) };
    }
}
""" % INTEGRITY_URL

REGISTER_JS = """
async (body) => {
    try {
        const resp = await fetch("%s", {
            method: "POST",
            credentials: "include",
            headers: { "Content-Type": "text/plain;charset=UTF-8" },
            body: body,
        });
        const text = await resp.text();
        return { status: resp.status, body: text.slice(0, 1200) };
    } catch (e) {
        return { status: 0, body: String(e) };
    }
}
""" % REGISTER_URL


def _log(msg):
    print(f"[net] {msg}", flush=True)


class BrowserSession:
    def __init__(self, headless=True, proxy=None, page_timeout=60000, debug=True):
        self.headless = headless
        self.proxy = proxy
        self.page_timeout = page_timeout
        self.debug = debug
        self._pw = None
        self._browser = None
        self._context = None
        self._page = None

    def start(self):
        self._pw = sync_playwright().start()
        launch_args = [
            "--no-sandbox",
            "--disable-blink-features=AutomationControlled",
            "--disable-dev-shm-usage",
        ]
        launch_kwargs = {"headless": self.headless, "args": launch_args}
        if self.proxy:
            launch_kwargs["proxy"] = {"server": self.proxy}
        self._browser = self._pw.chromium.launch(**launch_kwargs)
        self._context = self._browser.new_context(
            viewport={"width": 1366, "height": 850},
            locale="en-US",
            user_agent=UA,
        )
        self._context.add_init_script(
            "Object.defineProperty(navigator,'webdriver',{get:()=>undefined});"
        )
        self._page = self._context.new_page()
        self._page.set_default_timeout(self.page_timeout)

        if self.debug:
            def on_request(req):
                if "passport.twitch.tv" in req.url or "kpsdk" in str(req.headers).lower():
                    ksdk = {k: v[:40] for k, v in req.headers.items() if "kpsdk" in k.lower()}
                    _log(f"REQ {req.method} {req.url} kpsdk={ksdk}")

            def on_response(resp):
                if "passport.twitch.tv" in resp.url:
                    _log(f"RESP {resp.status} {resp.url}")

            self._page.on("request", on_request)
            self._page.on("response", on_response)

        try:
            self._page.goto(SIGNUP_URL, wait_until="domcontentloaded")
        except Exception:
            self._page.goto(TWITCH_URL, wait_until="domcontentloaded")
        self._stabilize()
        return self

    def _stabilize(self):
        for _ in range(30):
            try:
                if self._page.evaluate("() => typeof window.fetch === 'function'"):
                    break
            except Exception:
                pass
            time.sleep(0.5)
        time.sleep(3)

    def get_integrity(self, retries=3, delay=2):
        last = None
        for _ in range(retries):
            try:
                result = self._page.evaluate(INTEGRITY_JS)
            except Exception as e:
                result = {"status": 0, "token": None, "raw": str(e)}
            last = result
            if self.debug:
                _log(f"integrity result: {json.dumps(result)[:300]}")
            if result.get("token"):
                return result["token"]
            time.sleep(delay)
        raise RuntimeError("Integrity token harvest failed: %s" % json.dumps(last)[:500])

    def user_agent(self):
        return UA

    def protected_register(self, payload, retries=2, delay=2):
        import json as _json
        body = _json.dumps(payload)
        last = None
        for _ in range(retries):
            try:
                result = self._page.evaluate(REGISTER_JS, body)
            except Exception as e:
                result = {"status": 0, "body": str(e)}
            last = result
            if self.debug:
                _log(f"register HTTP {result.get('status')}: {str(result.get('body'))[:300]}")
            if result.get("status") and result["status"] > 0:
                try:
                    data = _json.loads(result["body"])
                except Exception:
                    data = {"_raw": result["body"]}
                return {"status": result["status"], "data": data}
            time.sleep(delay)
        raise RuntimeError("protected_register failed: %s" % json.dumps(last)[:500])

    def close(self):
        for attr in ("_context", "_browser"):
            obj = getattr(self, attr, None)
            if obj:
                try:
                    obj.close()
                except Exception:
                    pass
        if self._pw:
            try:
                self._pw.stop()
            except Exception:
                pass
        self._pw = self._browser = self._context = self._page = None

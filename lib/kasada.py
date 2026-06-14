import json
import time

from playwright.sync_api import sync_playwright


SIGNUP_URL = "https://www.twitch.tv/signup"
TWITCH_URL = "https://www.twitch.tv"
INTEGRITY_URL = "https://passport.twitch.tv/integrity"

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
        try { data = JSON.parse(text); } catch (e) { data = { _raw: text }; }
        return { ok: resp.ok, status: resp.status, token: data.token || null, raw: text.slice(0, 500) };
    } catch (e) {
        return { ok: false, status: 0, token: null, raw: String(e) };
    }
}
""" % INTEGRITY_URL


class KasadaHarvester:
    """Harvest Twitch integrity tokens using a headless browser so the Kasada
    anti-bot script runs naturally. The registration itself stays pure-protocol."""

    def __init__(self, headless=True, proxy=None, page_timeout=60000):
        self.headless = headless
        self.proxy = proxy
        self.page_timeout = page_timeout
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
            "--disable-features=IsolateOrigins,site-per-process",
        ]
        launch_kwargs = {"headless": self.headless, "args": launch_args}
        if self.proxy:
            launch_kwargs["proxy"] = {"server": self.proxy}
        self._browser = self._pw.chromium.launch(**launch_kwargs)
        self._context = self._browser.new_context(
            viewport={"width": 1280, "height": 800},
            locale="en-US",
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
            ),
        )
        self._context.add_init_script(
            "Object.defineProperty(navigator,'webdriver',{get:()=>undefined});"
        )
        self._page = self._context.new_page()
        self._page.set_default_timeout(self.page_timeout)
        url = SIGNUP_URL
        try:
            self._page.goto(url, wait_until="domcontentloaded")
        except Exception:
            self._page.goto(TWITCH_URL, wait_until="domcontentloaded")
        self._stabilize()
        return self

    def _stabilize(self):
        for _ in range(40):
            try:
                ready = self._page.evaluate(
                    "() => typeof window.fetch === 'function' && document.readyState"
                )
                if ready:
                    break
            except Exception:
                pass
            time.sleep(0.5)
        time.sleep(2)

    def harvest(self, retries=3, delay=2):
        last = None
        for _ in range(retries):
            try:
                result = self._page.evaluate(INTEGRITY_JS)
            except Exception as e:
                result = {"ok": False, "status": 0, "token": None, "raw": str(e)}
            last = result
            if result.get("token"):
                cookies = {
                    c["name"]: c["value"]
                    for c in self._context.cookies("https://www.twitch.tv")
                }
                passport_cookies = {
                    c["name"]: c["value"]
                    for c in self._context.cookies("https://passport.twitch.tv")
                }
                cookies.update(passport_cookies)
                ua = self._page.evaluate("() => navigator.userAgent")
                return {
                    "token": result["token"],
                    "cookies": cookies,
                    "user_agent": ua,
                }
            time.sleep(delay)
        raise RuntimeError(
            "Failed to harvest integrity token. Last response: %s"
            % json.dumps(last)[:800]
        )

    def user_agent(self):
        try:
            return self._page.evaluate("() => navigator.userAgent")
        except Exception:
            return (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
            )

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

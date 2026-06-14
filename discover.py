"""Discover the protected_register payload format by scanning the Twitch SPA
JavaScript bundles for the relevant field names and request construction."""
import re
import sys

from playwright.sync_api import sync_playwright

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36")

KEYWORDS = [
    "protected_register", "integrity_token", "is_password_guide",
    "birthday", "is_over_18", "client_id", "email_verification_code",
    "username", "password", "Signup_Register", "registerUser",
]

INTEREST = re.compile(
    r'.{0,80}(protected_register|integrity_token|is_password_guide|'
    r'email_verification_code|is_over_18).{0,120}',
    re.IGNORECASE,
)


def log(m):
    print(f"[scan] {m}", flush=True)


def main():
    scripts = {}
    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            args=["--no-sandbox", "--disable-blink-features=AutomationControlled"],
        )
        ctx = browser.new_context(viewport={"width": 1366, "height": 900}, locale="en-US", user_agent=UA)
        ctx.add_init_script("Object.defineProperty(navigator,'webdriver',{get:()=>undefined});")
        page = ctx.new_page()
        page.set_default_timeout(30000)

        def on_response(resp):
            url = resp.url
            if url.endswith(".js") or "script" in resp.headers.get("content-type", ""):
                try:
                    body = resp.text()
                    scripts[url] = body
                except Exception:
                    pass

        page.on("response", on_response)
        try:
            page.goto("https://www.twitch.tv/signup", wait_until="networkidle")
        except Exception:
            page.goto("https://www.twitch.tv/signup", wait_until="domcontentloaded")
        page.wait_for_timeout(6000)
        browser.close()

    log(f"captured {len(scripts)} scripts")
    hits = {}
    for url, body in scripts.items():
        for m in INTEREST.finditer(body):
            snippet = m.group(0).replace("\n", " ")
            hits.setdefault(url, []).append(snippet)
    for url, snippets in hits.items():
        short = url.split("/")[-1][:60]
        log(f"=== {short} ({len(snippets)} hits) ===")
        seen = set()
        for s in snippets:
            key = s[:60]
            if key in seen:
                continue
            seen.add(key)
            log(f"  ...{s}...")
    if not hits:
        log("NO HITS. Dumping field-name search across all scripts:")
        for url, body in scripts.items():
            for kw in KEYWORDS:
                if kw in body:
                    idx = body.index(kw)
                    short = url.split("/")[-1][:50]
                    log(f"  [{short}] '{kw}': ...{body[max(0,idx-40):idx+80]}...")

    log("done")


if __name__ == "__main__":
    main()

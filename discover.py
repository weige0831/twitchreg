"""Scan Twitch JS bundles for error code 5025 and related registration
error mappings to understand what triggers it."""
import re

from playwright.sync_api import sync_playwright

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36")


def log(m):
    print(f"[scan] {m}", flush=True)


def main():
    scripts = {}
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, args=["--no-sandbox", "--disable-blink-features=AutomationControlled"])
        ctx = browser.new_context(viewport={"width": 1366, "height": 900}, locale="en-US", user_agent=UA)
        page = ctx.new_page()
        page.on("response", lambda r: scripts.__setitem__(r.url, r.text()) if (r.url.endswith(".js") or "javascript" in r.headers.get("content-type", "")) else None)
        try:
            page.goto("https://www.twitch.tv/signup", wait_until="networkidle")
        except Exception:
            page.goto("https://www.twitch.tv/signup", wait_until="domcontentloaded")
        page.wait_for_timeout(5000)
        browser.close()

    log(f"{len(scripts)} scripts")
    pat = re.compile(r'.{0,60}5025.{0,100}')
    pat2 = re.compile(r'(?:error_?code|errorCode|REGISTER|registration)[^a-z0-9]{1,4}50\d{2}', re.IGNORECASE)
    for url, body in scripts.items():
        short = url.split("/")[-1][:55]
        for m in pat.finditer(body):
            log(f"[{short}] 5025: ...{m.group(0).replace(chr(10),' ')}...")
        for m in pat2.finditer(body):
            log(f"[{short}] code: ...{body[max(0,m.start()-30):m.end()+60].replace(chr(10),' ')}...")
    # also search for nearby error codes 50xx to see the pattern
    allcodes = set()
    for body in scripts.values():
        for m in re.finditer(r'50\d{2}', body):
            allcodes.add(m.group(0))
    log(f"all 50xx codes found: {sorted(allcodes)}")
    log("done")


if __name__ == "__main__":
    main()

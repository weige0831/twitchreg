"""Discovery script: fills the real Twitch signup form with Playwright and
captures the exact protected_register request body + headers so the
pure-protocol flow can replicate it precisely."""
import json
import sys
import time

from playwright.sync_api import sync_playwright

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36")

HOOK_JS = """
window.__caps = [];
(function(){
  const origFetch = window.fetch;
  window.fetch = async function(...args){
    try {
      const url = (typeof args[0]==='string') ? args[0] : (args[0]&&args[0].url)||'';
      if (url.indexOf('passport.twitch.tv') !== -1 || url.indexOf('protected_register') !== -1 || url.indexOf('integrity') !== -1) {
        const init = args[1]||{};
        let body = init.body;
        if (body && typeof body !== 'string') { try { body = String(body); } catch(e){} }
        window.__caps.push({url:url, method:init.method||'GET', body: body||null});
      }
    } catch(e){}
    return origFetch.apply(this, args);
  };
  const origOpen = XMLHttpRequest.prototype.open;
  const origSend = XMLHttpRequest.prototype.send;
  XMLHttpRequest.prototype.open = function(m,u){ this.__u=u; this.__m=m; return origOpen.apply(this, arguments); };
  XMLHttpRequest.prototype.send = function(b){
    try {
      if (this.__u && (this.__u.indexOf('passport.twitch.tv')!==-1 || this.__u.indexOf('protected_register')!==-1)) {
        window.__caps.push({url:this.__u, method:this.__m, body: b?String(b):null});
      }
    } catch(e){}
    return origSend.apply(this, arguments);
  };
})();
"""


def log(m):
    print(f"[discover] {m}", flush=True)


def try_fill(page, selector, value, label):
    try:
        el = page.locator(selector).first
        el.wait_for(state="visible", timeout=8000)
        el.fill(value)
        log(f"filled {label} ({selector})")
        return True
    except Exception as e:
        log(f"could not fill {label} ({selector}): {e}")
        return False


def try_click(page, texts):
    for t in texts:
        try:
            loc = page.get_by_role("button", name=t).first
            loc.wait_for(state="visible", timeout=4000)
            loc.click()
            log(f"clicked '{t}'")
            return True
        except Exception:
            pass
        try:
            loc = page.locator(f"button:has-text('{t}')").first
            loc.wait_for(state="visible", timeout=4000)
            loc.click()
            log(f"clicked '{t}'")
            return True
        except Exception:
            pass
    return False


def main():
    username = "test" + str(int(time.time()))[-8:]
    password = "Aa1!dddddddd"
    email = username + "@olsbvgq.shop"
    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            args=["--no-sandbox", "--disable-blink-features=AutomationControlled", "--disable-dev-shm-usage"],
        )
        ctx = browser.new_context(viewport={"width": 1366, "height": 900}, locale="en-US", user_agent=UA)
        ctx.add_init_script("Object.defineProperty(navigator,'webdriver',{get:()=>undefined});")
        ctx.add_init_script(HOOK_JS)
        page = ctx.new_page()
        page.set_default_timeout(20000)

        responses = []
        page.on("response", lambda r: responses.append(r) if "passport.twitch.tv" in r.url else None)

        log("loading signup page ...")
        try:
            page.goto("https://www.twitch.tv/signup", wait_until="domcontentloaded")
        except Exception as e:
            log(f"goto error: {e}")
        page.wait_for_timeout(4000)
        log(f"page url: {page.url}")
        log(f"page title: {page.title()}")

        # Step 1: username
        for sel in ["#signup-username", "input[name='username']", "input[autocomplete='username']"]:
            if try_fill(page, sel, username, "username"):
                break
        page.wait_for_timeout(800)
        try_click(page, ["Next Step", "Next", "Continue"])

        # Step 2: password
        page.wait_for_timeout(2000)
        for sel in ["#password-input", "input[name='password']", "input[type='password']"]:
            if try_fill(page, sel, password, "password"):
                break
        page.wait_for_timeout(800)
        try_click(page, ["Next Step", "Next", "Continue"])
        page.wait_for_timeout(2000)

        # maybe need "use email instead"
        try_click(page, ["Use email instead", "Sign up with email"])
        page.wait_for_timeout(1000)

        # email
        for sel in ["#email-input", "input[name='email']", "input[type='email']", "input[autocomplete='email']"]:
            if try_fill(page, sel, email, "email"):
                break
        page.wait_for_timeout(800)
        try_click(page, ["Next Step", "Next", "Continue"])
        page.wait_for_timeout(2000)

        # birthday - try selects
        try:
            page.locator("select").first.wait_for(state="visible", timeout=5000)
            selects = page.locator("select").all()
            log(f"found {len(selects)} select elements")
            for s in selects:
                opts = s.locator("option").all_inner_texts()
                if len(opts) > 10:
                    s.select_option(index=3)
                else:
                    s.select_option(index=1)
        except Exception as e:
            log(f"birthday selects: {e}")

        page.wait_for_timeout(1000)
        try_click(page, ["Sign Up", "Sign up", "Submit", "Next Step", "Continue"])
        page.wait_for_timeout(6000)

        caps = page.evaluate("() => window.__caps || []")
        log(f"=== CAPTURED {len(caps)} passport requests ===")
        for c in caps:
            log(json.dumps(c)[:1200])

        log("=== passport responses ===")
        for r in responses:
            try:
                body = r.text()[:500]
            except Exception:
                body = "<n/a>"
            log(f"{r.status} {r.url} :: {body}")

        browser.close()


if __name__ == "__main__":
    main()

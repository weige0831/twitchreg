"""Capture the full modern signup flow: email -> username/password -> birthday,
logging every passport.twitch.tv request body and the protected_register payload."""
import json
import time

import requests
from playwright.sync_api import sync_playwright

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36")

HOOK_JS = """
window.__caps = [];
(function(){
  const of = window.fetch;
  window.fetch = async function(...a){
    try {
      const u = (typeof a[0]==='string')?a[0]:(a[0]&&a[0].url)||'';
      const init = a[1]||{};
      if (u.indexOf('passport.twitch.tv')!==-1 || u.indexOf('protected_register')!==-1 || u.indexOf('/integrity')!==-1) {
        let b = init.body;
        if (b && typeof b!=='string'){ try{b=String(b)}catch(e){} }
        window.__caps.push({url:u, method:init.method||'GET', body: b?b.slice(0,2000):null});
      }
    } catch(e){}
    return of.apply(this,a);
  };
})();
"""


def log(m):
    print(f"[d] {m}", flush=True)


def make_email():
    r = requests.post("https://mail.minecraft-cn.net/api/v1/addresses",
                      json={"username": "tw" + str(int(time.time())), "domain": "olsbvgq.shop"}, timeout=20)
    d = r.json()
    return d["email"]


def dump_inputs(page):
    return page.evaluate("""() => {
        const out = [];
        document.querySelectorAll('input,select,button').forEach(el => {
            out.push({tag:el.tagName, type:el.type||'', id:el.id||'', name:el.name||'',
                      ph:el.placeholder||'', text:(el.innerText||'').slice(0,25),
                      aria:el.getAttribute('aria-label')||'', auto:el.getAttribute('autocomplete')||''});
        });
        return out;
    }""")


def main():
    email = make_email()
    username = "tw" + str(int(time.time()))[-8:]
    password = "Tw1!secure99aa"
    log(f"email={email} user={username}")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, args=["--no-sandbox", "--disable-blink-features=AutomationControlled"])
        ctx = browser.new_context(viewport={"width": 1366, "height": 900}, locale="en-US", user_agent=UA)
        ctx.add_init_script("Object.defineProperty(navigator,'webdriver',{get:()=>undefined});")
        ctx.add_init_script(HOOK_JS)
        page = ctx.new_page()
        page.set_default_timeout(12000)

        responses = []
        page.on("response", lambda r: responses.append((r.status, r.url)) if "passport.twitch.tv" in r.url else None)

        log("goto signup")
        try:
            page.goto("https://www.twitch.tv/signup", wait_until="networkidle")
        except Exception:
            page.goto("https://www.twitch.tv/signup", wait_until="domcontentloaded")
        page.wait_for_timeout(4000)

        # Step 1: email
        log("step1: email")
        try:
            page.locator("#email-input").first.wait_for(state="visible", timeout=10000)
            page.locator("#email-input").first.fill(email)
            page.wait_for_timeout(500)
            page.locator("button:has-text('Continue')").first.click()
            log("  clicked Continue")
        except Exception as e:
            log(f"  step1 error: {e}")
        page.wait_for_timeout(4000)

        log("  inputs after email step:")
        for el in dump_inputs(page):
            log(f"    {el}")

        # Step 2: username + password
        log("step2: username/password")
        for sel, val, label in [
            ("#signup-username", username, "username"),
            ("input[autocomplete='username']", username, "username2"),
            ("input[name='username']", username, "username3"),
        ]:
            try:
                page.locator(sel).first.wait_for(state="visible", timeout=4000)
                page.locator(sel).first.fill(val)
                log(f"  filled {label}")
                break
            except Exception:
                pass
        for sel, val, label in [
            ("#password-input", password, "password"),
            ("input[type='password']", password, "password2"),
            ("input[autocomplete='new-password']", password, "password3"),
        ]:
            try:
                page.locator(sel).first.wait_for(state="visible", timeout=4000)
                page.locator(sel).first.fill(val)
                log(f"  filled {label}")
                break
            except Exception:
                pass
        page.wait_for_timeout(500)
        try:
            page.locator("button:has-text('Continue')").first.click(timeout=5000)
            log("  clicked Continue")
        except Exception as e:
            log(f"  step2 continue error: {e}")
        page.wait_for_timeout(4000)

        log("  inputs after user/pass step:")
        for el in dump_inputs(page):
            log(f"    {el}")

        # Step 3: birthday
        log("step3: birthday")
        try:
            selects = page.locator("select").all()
            log(f"  found {len(selects)} selects")
            for i, s in enumerate(selects):
                try:
                    opts = s.locator("option").count()
                    if opts > 12:
                        s.select_option(index=5)  # month-ish/day
                    else:
                        s.select_option(index=2)
                    log(f"  select {i}: chose idx")
                except Exception:
                    pass
        except Exception as e:
            log(f"  birthday error: {e}")
        page.wait_for_timeout(800)
        try:
            page.locator("button:has-text('Sign Up')").first.click(timeout=5000)
            log("  clicked Sign Up")
        except Exception as e:
            log(f"  signup click error: {e}")
        page.wait_for_timeout(6000)

        log("=== ALL passport responses ===")
        for st, u in responses:
            log(f"  {st} {u}")

        caps = page.evaluate("() => window.__caps || []")
        log(f"=== {len(caps)} captured passport/integrity requests ===")
        for c in caps:
            log(json.dumps(c)[:1600])
        browser.close()


if __name__ == "__main__":
    main()

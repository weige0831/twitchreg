"""Definitive test: fill the real signup form with a VALID adult birthday and
capture the protected_register request + response to determine if the GitHub
Actions IP is blocked or if the earlier failure was just the bad birthday."""
import json
import time

import requests as req
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
      if (u.indexOf('protected_register')!==-1) {
        let b = init.body;
        if (b && typeof b!=='string'){ try{b=String(b)}catch(e){} }
        window.__caps.push({url:u, body: b?b.slice(0,2000):null});
      }
    } catch(e){}
    return of.apply(this,a);
  };
})();
"""


def log(m):
    print(f"[d] {m}", flush=True)


def main():
    email = "tw" + str(int(time.time())) + "@olsbvgq.shop"
    username = "tw" + str(int(time.time()))[-7:]
    password = "Tw1!secure99aa"
    log(f"email={email} user={username}")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, args=["--no-sandbox", "--disable-blink-features=AutomationControlled"])
        ctx = browser.new_context(viewport={"width": 1366, "height": 900}, locale="en-US", user_agent=UA)
        ctx.add_init_script("Object.defineProperty(navigator,'webdriver',{get:()=>undefined});")
        ctx.add_init_script(HOOK_JS)
        page = ctx.new_page()
        page.set_default_timeout(12000)

        resp_log = []
        def on_response(r):
            if "protected_register" in r.url or "/integrity" in r.url:
                try:
                    body = r.text()[:600]
                except Exception:
                    body = "<n/a>"
                resp_log.append((r.status, r.url, body))
        page.on("response", on_response)

        log("goto signup")
        try:
            page.goto("https://www.twitch.tv/signup", wait_until="networkidle")
        except Exception:
            page.goto("https://www.twitch.tv/signup", wait_until="domcontentloaded")
        page.wait_for_timeout(4000)

        # email
        log("fill email + continue")
        page.locator("#email-input").first.fill(email)
        page.wait_for_timeout(400)
        page.locator("button:has-text('Continue')").first.click()
        page.wait_for_timeout(3500)

        # username + password
        log("fill username/password")
        page.locator("#signup-username").first.fill(username)
        page.locator("#password-input").first.fill(password)
        page.wait_for_timeout(400)
        # the Sign Up button is on the same page now; no Continue needed
        page.wait_for_timeout(1000)

        # birthday - valid adult, via JS for robustness
        log("select birthday via JS")
        bd_result = page.evaluate("""() => {
            const out = [];
            document.querySelectorAll('select').forEach(s => {
                const aria = s.getAttribute('aria-label') || '';
                const opts = [...s.options].map(o => ({text:o.text, value:o.value}));
                let target = null;
                if (aria.toLowerCase().includes('month')) {
                    target = opts.find(o => o.text === 'June') || opts[1];
                } else if (aria.toLowerCase().includes('day')) {
                    target = opts.find(o => o.text === '15') || opts[15];
                } else if (aria.toLowerCase().includes('year')) {
                    target = opts.find(o => o.text === '1995')
                        || opts.find(o => parseInt(o.text) <= 2000 && parseInt(o.text) > 1950)
                        || opts[Math.min(40, opts.length-1)];
                }
                if (target) {
                    s.value = target.value;
                    s.dispatchEvent(new Event('input', {bubbles:true}));
                    s.dispatchEvent(new Event('change', {bubbles:true}));
                    out.push({aria, picked: target.text});
                }
            });
            return out;
        }""")
        log(f"  birthday: {bd_result}")
        page.wait_for_timeout(800)

        # Sign Up
        log("click Sign Up")
        try:
            page.locator("button:has-text('Sign Up')").first.click(timeout=8000)
        except Exception as e:
            log(f"signup click error: {e}")
        page.wait_for_timeout(8000)

        # report
        caps = page.evaluate("() => window.__caps || []")
        log(f"=== {len(caps)} protected_register BODIES ===")
        for c in caps:
            log(f"BODY: {c.get('body')}")
        log(f"=== {len(resp_log)} responses ===")
        for st, u, body in resp_log:
            log(f"RESP {st} {u} :: {body}")

        # check page state for errors / verification prompts
        log(f"page url after submit: {page.url}")
        body_text = page.evaluate("() => document.body ? document.body.innerText.slice(0,800) : ''")
        log(f"page text: {body_text[:500]}")
        browser.close()


if __name__ == "__main__":
    main()

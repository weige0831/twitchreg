"""Definitive test: proxy IP check + real SPA form submission with valid data."""
import json
import os
import time

import requests as req
from playwright.sync_api import sync_playwright

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36")
STEALTH = ("Object.defineProperty(navigator,'webdriver',{get:()=>undefined});"
           "window.chrome=window.chrome||{runtime:{}};")


def log(m):
    print(f"[d] {m}", flush=True)


def main():
    proxy = os.environ.get("PROXY")
    log(f"proxy set: {bool(proxy)}")
    email = "tw" + str(int(time.time())) + "@olsbvgq.shop"
    username = "tw" + str(int(time.time()))[-7:]
    password = "Tw1!secure99aa"

    with sync_playwright() as p:
        launch_kw = {"headless": False, "args": ["--no-sandbox", "--disable-blink-features=AutomationControlled"]}
        if proxy:
            from urllib.parse import urlparse
            pu = urlparse(proxy)
            pc = {"server": f"{pu.scheme}://{pu.hostname}:{pu.port}"}
            if pu.username:
                pc["username"] = pu.username
            if pu.password:
                pc["password"] = pu.password
            launch_kw["proxy"] = pc
        browser = p.chromium.launch(**launch_kw)
        ctx = browser.new_context(viewport={"width": 1366, "height": 900}, locale="en-US", user_agent=UA)
        ctx.add_init_script(STEALTH)
        page = ctx.new_page()
        page.set_default_timeout(15000)

        resp_log = []
        page.on("response", lambda r: resp_log.append((r.status, r.url, r.text()[:400])) if "protected_register" in r.url else None)

        # Check IP through proxy
        try:
            page.goto("https://api.ipify.org", wait_until="domcontentloaded", timeout=15000)
            ip = page.evaluate("() => document.body.innerText.trim()")
            log(f"BROWSER IP (via proxy): {ip}")
        except Exception as e:
            log(f"IP check error: {e}")

        # Go to signup
        log("goto signup")
        try:
            page.goto("https://www.twitch.tv/signup", wait_until="networkidle")
        except Exception:
            page.goto("https://www.twitch.tv/signup", wait_until="domcontentloaded")
        page.wait_for_timeout(4000)

        # Fill form
        log("fill email")
        page.locator("#email-input").first.fill(email)
        page.wait_for_timeout(400)
        page.locator("button:has-text('Continue')").first.click()
        page.wait_for_timeout(3500)

        log("fill username/password")
        page.locator("#signup-username").first.fill(username)
        page.locator("#password-input").first.fill(password)
        page.wait_for_timeout(800)

        log("select birthday")
        bd = page.evaluate("""() => {
            const out=[];
            document.querySelectorAll('select').forEach(s=>{
                const a=(s.getAttribute('aria-label')||'').toLowerCase();
                const opts=[...s.options].map(o=>({t:o.text,v:o.value}));
                let target=null;
                if(a.includes('month')) target=opts.find(o=>o.t==='June')||opts[1];
                else if(a.includes('day')) target=opts.find(o=>o.t==='15')||opts[15];
                else if(a.includes('year')){
                    target=opts.find(o=>o.t==='1995')||opts.find(o=>parseInt(o.t)<=2000&&parseInt(o.t)>1950)||opts[Math.min(30,opts.length-1)];
                }
                if(target){s.value=target.value;s.dispatchEvent(new Event('change',{bubbles:true}));out.push({a,a:a,picked:target.t});}
            });
            return out;
        }""")
        log(f"birthday: {json.dumps(bd)}")
        page.wait_for_timeout(800)

        log("click Sign Up")
        try:
            page.locator("button:has-text('Sign Up')").first.click(timeout=8000)
        except Exception as e:
            log(f"click error: {e}")
        page.wait_for_timeout(8000)

        log(f"=== {len(resp_log)} protected_register responses ===")
        for st, u, body in resp_log:
            log(f"  {st} {u} :: {body}")

        log(f"page url: {page.url}")
        txt = page.evaluate("() => document.body ? document.body.innerText.slice(0,400) : ''")
        log(f"page text (first 400): {txt[:400]}")
        browser.close()


if __name__ == "__main__":
    main()

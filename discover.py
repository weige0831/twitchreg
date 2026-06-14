"""Discover modern signup form structure, client_id, and capture the real
protected_register request body."""
import json

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
      if (u.indexOf('protected_register')!==-1 || u.indexOf('passport.twitch.tv')!==-1) {
        const init=a[1]||{}; let b=init.body;
        if (b && typeof b!=='string'){ try{b=String(b)}catch(e){} }
        window.__caps.push({url:u, method:init.method||'GET', body:b?b.slice(0,2000):null});
      }
    } catch(e){}
    return of.apply(this,a);
  };
})();
"""


def log(m):
    print(f"[d] {m}", flush=True)


def main():
    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            args=["--no-sandbox", "--disable-blink-features=AutomationControlled"],
        )
        ctx = browser.new_context(viewport={"width": 1366, "height": 900}, locale="en-US", user_agent=UA)
        ctx.add_init_script("Object.defineProperty(navigator,'webdriver',{get:()=>undefined});")
        ctx.add_init_script(HOOK_JS)
        page = ctx.new_page()
        page.set_default_timeout(15000)

        captured = []
        page.on("request", lambda r: captured.append(r) if "protected_register" in r.url else None)

        log("loading signup ...")
        try:
            page.goto("https://www.twitch.tv/signup", wait_until="networkidle")
        except Exception:
            page.goto("https://www.twitch.tv/signup", wait_until="domcontentloaded")
        page.wait_for_timeout(5000)

        # Extract client_id from page config
        cid = page.evaluate("""() => {
            try {
                const s = document.documentElement.outerHTML;
                const m = s.match(/client[_-]?id['":\\s]+([a-z0-9]{20,})/i);
                if (m) return m[1];
                if (window.__twitchIntegrations) return JSON.stringify(window.__twitchIntegrations);
                const gs = window.__TWITCH_SHARED__ || window.__twilight;
                if (gs) return JSON.stringify(gs).slice(0,500);
            } catch(e){ return 'err:'+e; }
            return null;
        }""")
        log(f"client_id probe: {cid}")

        # Dump all inputs / buttons on page
        inputs = page.evaluate("""() => {
            const out = [];
            document.querySelectorAll('input,select,button,[role=button]').forEach(el => {
                out.push({tag:el.tagName, type:el.type||'', id:el.id||'', name:el.name||'',
                          placeholder:el.placeholder||'', text:(el.innerText||'').slice(0,30),
                          aria:el.getAttribute('aria-label')||'', auto:el.getAttribute('autocomplete')||''});
            });
            return out;
        }""")
        log(f"=== {len(inputs)} form elements on main page ===")
        for el in inputs[:40]:
            log(f"  {el}")

        # Iframes
        frames = page.frames
        log(f"=== {len(frames)} frames ===")
        for f in frames:
            log(f"  frame: {f.url} (name={f.name})")
            try:
                finputs = f.evaluate("""() => {
                    const out = [];
                    document.querySelectorAll('input,select,button').forEach(el => {
                        out.push({tag:el.tagName, type:el.type||'', id:el.id||'', name:el.name||'', auto:el.getAttribute('autocomplete')||''});
                    });
                    return out;
                }""")
                for el in finputs[:20]:
                    log(f"    {el}")
            except Exception:
                pass

        # Try to fill whatever inputs exist and submit, to capture a real request
        log("attempting auto-fill ...")
        try:
            page.evaluate("""() => {
                document.querySelectorAll('input').forEach(el => {
                    const t = el.type || '';
                    const ac = el.getAttribute('autocomplete') || el.id || el.name || '';
                    let v = '';
                    if (t==='email'||ac.includes('email')) v='probe' + Date.now() + '@olsbvgq.shop';
                    else if (t==='password'||ac.includes('password')) v='Aa1!testpw99';
                    else if (ac.includes('username')||ac.includes('user')) v='probe' + (Date.now()%100000);
                    else if (t==='text'||t==='' ) v='probe' + (Date.now()%100000);
                    if (v) { try { el.value=v; el.dispatchEvent(new Event('input',{bubbles:true})); el.dispatchEvent(new Event('change',{bubbles:true})); } catch(e){} }
                });
            }""")
        except Exception as e:
            log(f"autofill error: {e}")
        page.wait_for_timeout(1000)

        # click any submit/signup button
        for sel in ["button:has-text('Sign Up')", "button:has-text('Sign up')", "button:has-text('Continue')", "button:has-text('Next')", "[type=submit]"]:
            try:
                page.locator(sel).first.click(timeout=3000)
                log(f"clicked {sel}")
                page.wait_for_timeout(2000)
            except Exception:
                pass

        page.wait_for_timeout(3000)
        caps = page.evaluate("() => window.__caps || []")
        log(f"=== {len(caps)} passport requests captured ===")
        for c in caps:
            log(json.dumps(c)[:1500])
        log(f"=== {len(captured)} protected_register requests via listener ===")
        for r in captured:
            try:
                log(f"BODY: {r.post_data}")
            except Exception:
                log("BODY: <n/a>")
        browser.close()


if __name__ == "__main__":
    main()

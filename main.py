import os
import sys
import time
import traceback
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from lib.kasada import BrowserSession
from lib.tempmail import TempMail
from lib.twitch import TwitchRegistrator, TwitchError, username_taken
from lib.utils import (
    random_birthday,
    random_password,
    random_username,
)

RESULTS_DIR = Path(__file__).resolve().parent / "results"
ACCOUNTS_FILE = RESULTS_DIR / "accounts.txt"


def env(name, default=None):
    val = os.environ.get(name)
    return val if val not in (None, "") else default


def log(msg):
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)


def ensure_results():
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    ACCOUNTS_FILE.touch(exist_ok=True)


def save_account(line):
    with open(ACCOUNTS_FILE, "a", encoding="utf-8") as f:
        f.write(line + "\n")


def diagnostics(mail):
    log("== Diagnostics ==")
    try:
        import requests
        r = requests.get("https://passport.twitch.tv/", timeout=15)
        log(f"Twitch passport reachable: HTTP {r.status_code}")
    except Exception as e:
        log(f"WARN: cannot reach Twitch passport: {e}")
    email, _ = mail.create_address("diag" + str(int(time.time())))
    log(f"Tempmail OK: {email}")
    log("=================")


def pick_username():
    for _ in range(8):
        candidate = random_username()
        if not username_taken(candidate):
            return candidate
    return random_username()


def register_one(browser, mail):
    username = pick_username()
    password = random_password()
    birthday = random_birthday()
    email, mail_token = mail.create_address(username)
    log(f"Target: {username} / {email}")

    reg = TwitchRegistrator(browser)
    log("Step 1: protected_register (integrity + register via browser) ...")
    res1 = reg.register(username, password, email, birthday)
    if res1.get("success"):
        log("Registered without verification step (unexpected but OK).")
        return username, password, email, res1["access_token"], res1["user_id"]
    if not res1.get("need_verification"):
        raise RuntimeError(f"Unexpected register response: {res1}")
    log("Verification email triggered. Waiting for code ...")

    code = mail.wait_for_code(mail_token, timeout=220, interval=4)
    if not code:
        raise RuntimeError("No verification code received in time")
    log(f"Verification code received: {code}")

    log("Step 2: protected_register with verification code ...")
    res2 = reg.register(username, password, email, birthday, email_verification_code=code)
    if not res2.get("success"):
        raise RuntimeError(f"Final register did not succeed: {res2}")
    return username, password, email, res2["access_token"], res2["user_id"]


def main():
    count = int(env("COUNT", "1"))
    base_url = env("TEMPMAIL_BASE_URL", "https://mail.minecraft-cn.net")
    domain = env("TEMPMAIL_DOMAIN", "olsbvgq.shop")
    proxy = env("PROXY")
    headless = env("HEADLESS", "1") != "0"

    ensure_results()
    mail = TempMail(base_url=base_url, domain=domain)
    diagnostics(mail)

    log(f"Starting browser session (headless={headless}) ...")
    browser = BrowserSession(headless=headless, proxy=proxy)
    browser.start()
    log("Browser ready. Beginning batch registration.")

    success = 0
    failed = 0
    try:
        for i in range(count):
            log(f"===== Account {i + 1}/{count} =====")
            try:
                u, p, e, tok, uid = register_one(browser, mail)
                line = f"{u}:{p}:{e}:{uid}:{tok}"
                save_account(line)
                log(f"SUCCESS: {u} (uid={uid}) token={tok[:24]}...")
                success += 1
            except Exception as ex:
                failed += 1
                log(f"FAILED: {ex}")
                traceback.print_exc()
            time.sleep(3)
    finally:
        browser.close()

    log(f"Done. success={success} failed={failed}")
    with open(os.environ["GITHUB_OUTPUT"], "a") if "GITHUB_OUTPUT" in os.environ else open(os.devnull, "w") as f:
        f.write(f"success={success}\nfailed={failed}\n")
    if success == 0:
        sys.exit(1)


if __name__ == "__main__":
    main()

import os
import sys
import time
import traceback
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from lib.kasada import KasadaHarvester
from lib.tempmail import TempMail
from lib.twitch import TwitchProtocol, TwitchError
from lib.utils import (
    random_birthday,
    random_password,
    random_username,
)

RESULTS_DIR = Path(__file__).resolve().parent / "results"
ACCOUNTS_FILE = RESULTS_DIR / "accounts.txt"


def env(name, default=None):
    return os.environ.get(name, default)


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
    try:
        email, token = mail.create_address("diagprobe" + str(int(time.time())))
        log(f"Tempmail OK: {email}")
    except Exception as e:
        log(f"ERROR: Tempmail unreachable: {e}")
        raise
    log("=================")


def register_one(harvester, mail, proxy=None):
    username = None
    for _ in range(8):
        candidate = random_username()
        proto = TwitchProtocol(harvester.user_agent(), {}, proxy=proxy)
        if not proto.username_taken(candidate):
            username = candidate
            break
    if not username:
        username = random_username()

    password = random_password()
    birthday = random_birthday()
    email, mail_token = mail.create_address(username)
    log(f"Target: {username} / {email}")

    log("Harvesting integrity token #1 ...")
    h1 = harvester.harvest()
    log(f"Integrity token #1 acquired ({len(h1['token'])} chars)")

    proto = TwitchProtocol(h1["user_agent"], h1["cookies"], proxy=proxy)
    log("Sending protected_register (step 1) ...")
    res1 = proto.register(username, password, email, birthday, h1["token"])
    if not res1.get("need_verification"):
        if res1.get("success"):
            log("Registered without verification step (unexpected).")
            return username, password, email, res1["access_token"], res1["user_id"]
        raise RuntimeError(f"Unexpected register response: {res1}")
    log("Verification email triggered. Waiting for code ...")

    code = mail.wait_for_code(mail_token, timeout=200, interval=4)
    if not code:
        raise RuntimeError("No verification code received in time")
    log(f"Verification code: {code}")

    log("Harvesting integrity token #2 ...")
    h2 = harvester.harvest()
    proto2 = TwitchProtocol(h2["user_agent"], h2["cookies"], proxy=proxy)
    log("Sending protected_register (step 2 with code) ...")
    res2 = proto2.register(username, password, email, birthday, h2["token"], email_verification_code=code)
    if not res2.get("success"):
        raise RuntimeError(f"Final register did not succeed: {res2}")

    return username, password, email, res2["access_token"], res2["user_id"]


def main():
    count = int(env("COUNT", "1"))
    base_url = env("TEMPMAIL_BASE_URL", "https://mail.minecraft-cn.net")
    domain = env("TEMPMAIL_DOMAIN", "olsbvgq.shop")
    proxy = env("PROXY") or None
    headless = env("HEADLESS", "1") != "0"

    ensure_results()
    mail = TempMail(base_url=base_url, domain=domain)
    diagnostics(mail)

    log(f"Starting Kasada harvester (headless={headless}) ...")
    harvester = KasadaHarvester(headless=headless, proxy=proxy)
    harvester.start()
    log("Browser ready. Beginning batch registration.")

    success = 0
    failed = 0
    try:
        for i in range(count):
            log(f"===== Account {i + 1}/{count} =====")
            try:
                u, p, e, tok, uid = register_one(harvester, mail, proxy=proxy)
                line = f"{u}:{p}:{e}:{uid}:{tok}"
                save_account(line)
                log(f"SUCCESS: {u} (uid={uid})")
                log(f"  token={tok[:24]}...")
                success += 1
            except Exception as ex:
                failed += 1
                log(f"FAILED: {ex}")
                traceback.print_exc()
            time.sleep(3)
    finally:
        harvester.close()

    log(f"Done. success={success} failed={failed}")
    print(f"::set-output name=success::{success}", flush=True)
    print(f"::set-output name=failed::{failed}", flush=True)
    if success == 0:
        sys.exit(1)


if __name__ == "__main__":
    main()

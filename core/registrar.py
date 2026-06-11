import asyncio
import random
import sys
import httpx
from camoufox.async_api import AsyncCamoufox
from playwright.async_api import Page, BrowserContext
from loguru import logger

from .email_client import TempMailClient
from .api_client import CDKApiClient
from .generator import random_username, random_password, random_birthday

SIGNUP_URL = "https://www.twitch.tv/signup"


async def human_type(page: Page, locator, text: str):
    await locator.click()
    for ch in text:
        await locator.press(ch)
        await asyncio.sleep(random.uniform(0.03, 0.10))


async def human_delay(lo: float = 0.5, hi: float = 1.5):
    await asyncio.sleep(random.uniform(lo, hi))


async def _upload_github(client: httpx.AsyncClient, path: str) -> str:
    import base64 as b64mod
    import os
    token = os.environ.get("GITHUB_TOKEN", "")
    repo = os.environ.get("GITHUB_REPOSITORY", "")
    run_id = os.environ.get("GITHUB_RUN_ID", "0")
    if not token or not repo:
        raise Exception("GITHUB_TOKEN/GITHUB_REPOSITORY not set")

    filename = os.path.basename(path)
    with open(path, "rb") as f:
        content = b64mod.b64encode(f.read()).decode()

    gh_headers = {"Authorization": f"Bearer {token}", "Accept": "application/vnd.github+json"}

    branch = "debug-screenshots"
    check = await client.get(f"https://api.github.com/repos/{repo}/branches/{branch}", headers=gh_headers)
    if check.status_code == 404:
        ref = await client.get(f"https://api.github.com/repos/{repo}/git/ref/heads/main", headers=gh_headers)
        sha = ref.json()["object"]["sha"]
        await client.post(
            f"https://api.github.com/repos/{repo}/git/refs",
            headers=gh_headers,
            json={"ref": f"refs/heads/{branch}", "sha": sha},
        )

    file_path = f"{run_id}/{filename}"
    resp = await client.put(
        f"https://api.github.com/repos/{repo}/contents/{file_path}",
        headers=gh_headers,
        json={"message": f"debug: {filename}", "content": content, "branch": branch},
    )
    if resp.status_code in (200, 201):
        return f"https://raw.githubusercontent.com/{repo}/{branch}/{file_path}"
    raise Exception(f"GitHub API {resp.status_code}: {resp.text[:200]}")


async def take_screenshot(page: Page, name: str, task_id: int) -> str:
    path = f"debug_{name}_{task_id}.png"
    try:
        await page.screenshot(path=path)
    except Exception as e:
        logger.debug(f"[Task-{task_id}] Screenshot capture failed: {e}")
        return ""

    upload_services = [
        _upload_github,
    ]
    async with httpx.AsyncClient(timeout=10, follow_redirects=True) as client:
        for upload_fn in upload_services:
            try:
                link = await upload_fn(client, path)
                if link:
                    logger.info(f"[Task-{task_id}] Screenshot ({name}): {link}")
                    return link
            except Exception as e:
                logger.warning(f"[Task-{task_id}] {upload_fn.__name__} failed: {e}")

    logger.warning(f"[Task-{task_id}] Screenshot upload failed, saved locally: {path}")
    logger.warning(f"[Task-{task_id}] -> Download from Actions tab -> Artifacts -> debug-screenshots")
    return path


async def find_visible(page: Page, selectors: list[str], timeout: int = 5000):
    for sel in selectors:
        try:
            el = page.locator(sel).first
            await el.wait_for(state="visible", timeout=timeout)
            return el
        except Exception:
            continue
    return None


async def click_button(page: Page, selectors: list[str], timeout: int = 5000) -> bool:
    el = await find_visible(page, selectors, timeout)
    if el:
        await el.click()
        return True
    return False


async def extract_cookies(context: BrowserContext) -> tuple[list[dict], str]:
    cookies = await context.cookies()
    cookie_list = []
    auth_token = ""
    for c in cookies:
        cookie_list.append({
            "name": c["name"],
            "value": c["value"],
            "domain": c["domain"],
            "path": c["path"],
        })
        if c["name"] == "auth-token":
            auth_token = c["value"]
    return cookie_list, auth_token


async def register_one(
    cfg: dict,
    mail_client: TempMailClient,
    api_client: CDKApiClient,
    task_id: int,
) -> dict | None:
    username = random_username()
    password = random_password()
    birthday = random_birthday()

    tag = f"[Task-{task_id}]"
    logger.info(f"{tag} Starting registration for {username}")

    mail_data = await mail_client.create_address()
    email = mail_data["email"]
    mail_token = mail_data["token"]
    logger.info(f"{tag} Email: {email}")

    if sys.platform == "linux" and cfg["browser"]["headless"]:
        headless_mode = "virtual"
    elif cfg["browser"]["headless"]:
        headless_mode = True
    else:
        headless_mode = False

    page = None
    try:
        async with AsyncCamoufox(
            headless=headless_mode,
            humanize=True,
            os="windows",
        ) as context:
            page = await context.new_page()

            logger.info(f"{tag} Navigating to signup page")
            await page.goto(SIGNUP_URL, wait_until="domcontentloaded", timeout=cfg["browser"]["timeout"])
            await human_delay(3.0, 5.0)

            await take_screenshot(page, "step0_loaded", task_id)

            not_supported = await find_visible(page, [
                "text='Your browser is not currently supported'",
                "text='browser is not currently supported'",
            ], timeout=3000)
            if not_supported:
                logger.error(f"{tag} Browser detected as unsupported by Twitch")
                await take_screenshot(page, "browser_not_supported", task_id)
                return None

            email_input = await find_visible(page, [
                "#email-input",
                "input[type='email']",
                "input[name='email']",
                "[data-a-target='signup-email-input'] input",
                "input[aria-label='Email']",
                "form input:first-of-type",
            ], timeout=10000)

            if email_input:
                logger.info(f"{tag} Step 1: Filling email")
                await human_type(page, email_input, email)
                await human_delay(0.5, 1.0)

                await click_button(page, [
                    "button:has-text('Continue')",
                    "button:has-text('Next')",
                    "button:has-text('Next Step')",
                    "form button[type='submit']",
                    "form button",
                ])
                await human_delay(2.0, 3.0)
            else:
                logger.warning(f"{tag} No email-first flow detected, trying classic layout")
                await take_screenshot(page, "step1_no_email", task_id)

            logger.info(f"{tag} Step 2: Filling username")
            username_input = await find_visible(page, [
                "#signup-username",
                "input[name='username']",
                "input[autocomplete='username']",
                "input[aria-label='Username']",
                "[data-a-target='signup-username-input'] input",
            ], timeout=10000)
            if username_input:
                await human_type(page, username_input, username)
                await human_delay()
            else:
                logger.error(f"{tag} Could not find username input")
                await take_screenshot(page, "step2_no_username", task_id)
                return None

            logger.info(f"{tag} Step 3: Filling password")
            password_input = await find_visible(page, [
                "#password-input",
                "#signup-password",
                "input[type='password']",
                "input[name='password']",
                "input[autocomplete='new-password']",
                "input[aria-label='Password']",
            ])
            if password_input:
                await human_type(page, password_input, password)
                await human_delay()
            else:
                logger.error(f"{tag} Could not find password input")
                await take_screenshot(page, "step3_no_password", task_id)
                return None

            logger.info(f"{tag} Step 4: Filling birthday")
            month_names = {
                1: "January", 2: "February", 3: "March", 4: "April",
                5: "May", 6: "June", 7: "July", 8: "August",
                9: "September", 10: "October", 11: "November", 12: "December",
            }
            selects = page.locator("form select")
            select_count = await selects.count()
            if select_count >= 3:
                await selects.nth(0).select_option(label=month_names[birthday["month"]])
                await human_delay(0.3, 0.5)
                await selects.nth(1).select_option(str(birthday["day"]))
                await human_delay(0.3, 0.5)
                await selects.nth(2).select_option(str(birthday["year"]))
                await human_delay(0.5, 1.0)
            else:
                logger.warning(f"{tag} Found {select_count} select elements, trying text-based birthday")
                month_btn = await find_visible(page, [
                    "button:has-text('Month')",
                    "[data-a-target='birthday-month-select']",
                ])
                if month_btn:
                    await month_btn.click()
                    await human_delay(0.3, 0.5)
                    await page.get_by_text(month_names[birthday["month"]], exact=True).first.click()
                    await human_delay(0.3, 0.5)

                day_btn = await find_visible(page, [
                    "button:has-text('Day')",
                    "[data-a-target='birthday-day-select']",
                ])
                if day_btn:
                    await day_btn.click()
                    await human_delay(0.3, 0.5)
                    await page.get_by_text(str(birthday["day"]), exact=True).first.click()
                    await human_delay(0.3, 0.5)

                year_btn = await find_visible(page, [
                    "button:has-text('Year')",
                    "[data-a-target='birthday-year-select']",
                ])
                if year_btn:
                    await year_btn.click()
                    await human_delay(0.3, 0.5)
                    await page.get_by_text(str(birthday["year"]), exact=True).first.click()

            await human_delay(1.0, 2.0)

            logger.info(f"{tag} Step 5: Clicking Sign Up")
            signup_clicked = await click_button(page, [
                "button[data-a-target='passport-signup-button']",
                "button:has-text('Sign Up')",
                "button:has-text('Join Twitch')",
                "form button[type='submit']",
            ])
            if not signup_clicked:
                logger.error(f"{tag} Could not find signup button")
                await take_screenshot(page, "step5_no_signup", task_id)
                return None

            await asyncio.sleep(3)
            logger.info(f"{tag} Page URL after submit: {page.url}")
            page_title = await page.title()
            logger.info(f"{tag} Page title: {page_title}")
            await take_screenshot(page, "step5_submitted", task_id)

            await asyncio.sleep(3)

            error_el = await find_visible(page, [
                "text='Your browser is not currently supported'",
                "[data-a-target='signup-error']",
                ".server-message-alert",
                "[class*='error-message']",
                "[class*='ErrorMessage']",
            ], timeout=3000)
            if error_el:
                err_text = await error_el.text_content()
                logger.error(f"{tag} Registration error: {err_text}")
                await take_screenshot(page, "step5_error", task_id)
                return None

            captcha_el = await find_visible(page, [
                "iframe[src*='captcha']",
                "iframe[src*='arkose']",
                "iframe[src*='funcaptcha']",
                "iframe[title*='arkose']",
                "[id*='captcha']",
                "[class*='captcha']",
            ], timeout=2000)
            if captcha_el:
                logger.warning(f"{tag} Captcha/challenge detected after submit")
                await take_screenshot(page, "step5_captcha", task_id)

            logger.info(f"{tag} Step 6: Waiting for verification code")
            try:
                code = await mail_client.wait_for_verification_code(mail_token)
            except TimeoutError:
                logger.error(f"{tag} Verification email not received within timeout")
                await take_screenshot(page, "step6_email_timeout", task_id)
                return None

            otp_input = await find_visible(page, [
                "input[name='code']",
                "input[aria-label*='erification']",
                "input[aria-label*='code']",
                "input[placeholder*='code']",
                "input[maxlength='6']",
                "[data-a-target='verification-code-input'] input",
            ], timeout=10000)

            if otp_input:
                await human_type(page, otp_input, code)
                await human_delay(1.0, 2.0)

                await click_button(page, [
                    "button[data-a-target='passport-verify-button']",
                    "button:has-text('Submit')",
                    "button:has-text('Verify')",
                    "button[type='submit']",
                ])
                await asyncio.sleep(5)
            else:
                logger.warning(f"{tag} Could not find OTP input, trying digit inputs")
                for i in range(6):
                    digit = page.locator(f"input[data-index='{i}']").first
                    if await digit.count() > 0:
                        await digit.fill(code[i])
                        await asyncio.sleep(0.1)

            logger.info(f"{tag} Step 7: Extracting cookies")
            cookie_list, auth_token = await extract_cookies(context)

            if not auth_token:
                for c in await context.cookies():
                    if "auth" in c["name"].lower() and "token" in c["name"].lower():
                        auth_token = c["value"]
                        break

            if not auth_token:
                try:
                    auth_token = await page.evaluate(
                        "() => { try { return document.cookie.match(/auth-token=([^;]+)/)?.[1] || '' } catch { return '' } }"
                    )
                except Exception:
                    pass

            if not auth_token:
                logger.warning(f"{tag} No auth_token found")
                await take_screenshot(page, "step7_no_token", task_id)

            result = {
                "username": username,
                "password": password,
                "email": email,
                "auth_token": auth_token,
                "cookies": cookie_list,
            }

            if api_client.enabled and auth_token:
                try:
                    await api_client.upload_account(
                        username=username,
                        password=password,
                        email=email,
                        auth_token=auth_token,
                        cookies=cookie_list,
                    )
                except Exception as e:
                    logger.error(f"{tag} Failed to upload to CDK system: {e}")

            if auth_token:
                logger.success(f"{tag} Done: {username} | token={auth_token[:20]}...")
            else:
                logger.warning(f"{tag} Done: {username} | no auth_token")
            return result

    except Exception as e:
        logger.error(f"{tag} Registration failed: {e}")
        try:
            if page:
                await take_screenshot(page, "error", task_id)
        except Exception:
            pass
        return None

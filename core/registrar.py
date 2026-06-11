import asyncio
import random
import re
from playwright.async_api import async_playwright, Page, BrowserContext
_STEALTH_V2 = False
try:
    from playwright_stealth import Stealth
    _stealth_instance = Stealth()
    _STEALTH_V2 = True
except ImportError:
    pass
try:
    from playwright_stealth import stealth_async as _stealth_async_v1
except ImportError:
    _stealth_async_v1 = None
from loguru import logger

from .email_client import TempMailClient
from .api_client import CDKApiClient
from .generator import random_username, random_password, random_birthday

SIGNUP_URL = "https://www.twitch.tv/signup"


async def human_type(page: Page, selector: str, text: str):
    el = page.locator(selector).first
    await el.click()
    for ch in text:
        await el.press(ch if len(ch) == 1 else ch)
        await asyncio.sleep(random.uniform(0.04, 0.12))


async def human_delay(lo: float = 0.5, hi: float = 1.5):
    await asyncio.sleep(random.uniform(lo, hi))


async def select_dropdown(page: Page, trigger_sel: str, value: str):
    trigger = page.locator(trigger_sel).first
    await trigger.scroll_into_view_if_needed()
    await trigger.click()
    await asyncio.sleep(0.3)

    option = page.locator(f"[data-value='{value}']").first
    if await option.count() == 0:
        option = page.get_by_text(value, exact=True).first
    await option.click()
    await human_delay(0.2, 0.5)


async def fill_birthday(page: Page, birthday: dict):
    month_names = [
        "", "January", "February", "March", "April", "May", "June",
        "July", "August", "September", "October", "November", "December",
    ]

    month_sel = (
        "[data-a-target='birthday-month-select'] select,"
        "[data-a-target='birthday-date-select-month'],"
        "select#month,"
        "select[aria-label='Month']"
    )
    day_sel = (
        "[data-a-target='birthday-day-select'] select,"
        "[data-a-target='birthday-date-select-day'],"
        "select#day,"
        "select[aria-label='Day']"
    )
    year_sel = (
        "[data-a-target='birthday-year-select'] select,"
        "[data-a-target='birthday-date-select-year'],"
        "select#year,"
        "select[aria-label='Year']"
    )

    for sel, val in [
        (month_sel, str(birthday["month"])),
        (day_sel, str(birthday["day"])),
        (year_sel, str(birthday["year"])),
    ]:
        el = page.locator(sel).first
        try:
            tag = await el.evaluate("e => e.tagName.toLowerCase()")
        except Exception:
            tag = ""

        if tag == "select":
            await el.select_option(val)
        else:
            await el.click()
            await asyncio.sleep(0.3)
            if sel.startswith("[data-a-target='birthday-month"):
                display = month_names[int(val)]
            else:
                display = val
            opt = page.get_by_text(display, exact=True).first
            await opt.click()

        await human_delay(0.3, 0.6)


async def switch_to_email_tab(page: Page):
    email_tab_selectors = [
        "button[data-a-target='passport-tab-email']",
        "button:has-text('Email')",
        "a:has-text('Use email instead')",
        "[data-a-target='signup-email-tab']",
    ]
    for sel in email_tab_selectors:
        el = page.locator(sel).first
        if await el.count() > 0 and await el.is_visible():
            await el.click()
            await human_delay(0.5, 1.0)
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

    pw = None
    browser = None
    try:
        pw = await async_playwright().start()
        browser = await pw.chromium.launch(
            headless=cfg["browser"]["headless"],
            args=[
                "--disable-blink-features=AutomationControlled",
                "--disable-dev-shm-usage",
                "--no-sandbox",
            ],
        )
        context = await browser.new_context(
            viewport={"width": random.randint(1280, 1920), "height": random.randint(800, 1080)},
            locale="en-US",
            timezone_id="America/New_York",
        )
        if _STEALTH_V2:
            await _stealth_instance.apply_stealth_async(context)
        page = await context.new_page()
        if not _STEALTH_V2 and _stealth_async_v1:
            await _stealth_async_v1(page)

        logger.info(f"{tag} Navigating to signup page")
        await page.goto(SIGNUP_URL, wait_until="networkidle", timeout=cfg["browser"]["timeout"])
        await human_delay(1.0, 2.0)

        await switch_to_email_tab(page)

        username_selectors = [
            "#signup-username",
            "input[name='username']",
            "input[autocomplete='username']",
            "[data-a-target='signup-username-input'] input",
            "input[aria-label='Username']",
        ]
        for sel in username_selectors:
            el = page.locator(sel).first
            if await el.count() > 0 and await el.is_visible():
                await human_type(page, sel, username)
                break
        await human_delay()

        password_selectors = [
            "#signup-password",
            "input[name='password']",
            "input[autocomplete='new-password']",
            "[data-a-target='signup-password-input'] input",
            "input[aria-label='Password']",
        ]
        for sel in password_selectors:
            el = page.locator(sel).first
            if await el.count() > 0 and await el.is_visible():
                await human_type(page, sel, password)
                break
        await human_delay()

        await fill_birthday(page, birthday)
        await human_delay()

        email_selectors = [
            "input[name='email']",
            "input[type='email']",
            "#signup-email",
            "[data-a-target='signup-email-input'] input",
            "input[aria-label='Email']",
        ]
        for sel in email_selectors:
            el = page.locator(sel).first
            if await el.count() > 0 and await el.is_visible():
                await human_type(page, sel, email)
                break
        await human_delay(1.0, 2.0)

        signup_btn_selectors = [
            "button[data-a-target='passport-signup-button']",
            "button[data-a-target='signup-button']",
            "button:has-text('Sign Up')",
            "button:has-text('Join Twitch')",
        ]
        for sel in signup_btn_selectors:
            btn = page.locator(sel).first
            if await btn.count() > 0 and await btn.is_visible():
                await btn.click()
                break
        logger.info(f"{tag} Signup form submitted, waiting for verification")

        await asyncio.sleep(5)

        current_url = page.url
        page_content = await page.content()

        has_error = False
        error_selectors = [
            "[data-a-target='signup-error']",
            ".server-message-alert",
            "[class*='error-message']",
        ]
        for sel in error_selectors:
            el = page.locator(sel).first
            if await el.count() > 0 and await el.is_visible():
                err_text = await el.text_content()
                logger.error(f"{tag} Registration error: {err_text}")
                has_error = True
                break

        if has_error:
            return None

        logger.info(f"{tag} Waiting for verification code email...")
        code = await mail_client.wait_for_verification_code(mail_token)

        code_input_selectors = [
            "input[name='code']",
            "input[aria-label*='erification']",
            "input[aria-label*='code']",
            "[data-a-target='verification-code-input'] input",
            "input[placeholder*='code']",
            "input[maxlength='6']",
        ]
        code_entered = False
        for sel in code_input_selectors:
            el = page.locator(sel).first
            if await el.count() > 0 and await el.is_visible():
                await human_type(page, sel, code)
                code_entered = True
                break

        if not code_entered:
            for digit_idx in range(6):
                digit_input = page.locator(f"input[data-index='{digit_idx}']").first
                if await digit_input.count() > 0:
                    await digit_input.fill(code[digit_idx])
                    await asyncio.sleep(0.1)
                    code_entered = True

        if code_entered:
            submit_selectors = [
                "button[data-a-target='passport-verify-button']",
                "button:has-text('Submit')",
                "button:has-text('Verify')",
                "button[type='submit']",
            ]
            for sel in submit_selectors:
                btn = page.locator(sel).first
                if await btn.count() > 0 and await btn.is_visible():
                    await btn.click()
                    break
            await asyncio.sleep(5)

        logger.info(f"{tag} Extracting cookies...")
        cookie_list, auth_token = await extract_cookies(context)

        if not auth_token:
            all_cookies = await context.cookies()
            for c in all_cookies:
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
            logger.warning(f"{tag} Could not find auth_token in cookies, registration may have failed")

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

        logger.success(f"{tag} Registration complete: {username} | auth_token={auth_token[:20]}..." if auth_token else f"{tag} Registration complete: {username} | no auth_token")
        return result

    except Exception as e:
        logger.error(f"{tag} Registration failed: {e}")
        return None
    finally:
        if browser:
            await browser.close()
        if pw:
            await pw.stop()

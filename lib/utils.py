import random
import re
import string


ADJECTIVES = [
    "swift", "brave", "calm", "eager", "fierce", "gentle", "happy", "jolly",
    "kind", "lively", "merry", "noble", "proud", "quiet", "royal", "sharp",
    "smart", "solid", "stellar", "sunny", "super", "tidy", "trim", "vivid",
    "witty", "zesty", "amber", "azure", "cosmic", "crimson", "frozen", "golden",
    "iron", "jade", "lunar", "misty", "onyx", "solar", "storm", "wild",
]

NOUNS = [
    "wolf", "falcon", "tiger", "bear", "eagle", "hawk", "lion", "shark",
    "raven", "fox", "otter", "lynx", "panther", "viper", "cobra", "drake",
    "phoenix", "griffin", "ranger", "knight", "scout", "pilot", "rider", "hunter",
    "runner", "coder", "gamer", "ninja", "sage", "wizard", "titan", "atom",
]


def random_username():
    base = random.choice(ADJECTIVES) + random.choice(NOUNS)
    suffix = "".join(random.choices(string.digits, k=random.randint(2, 4)))
    username = (base + suffix)[:25]
    return username.lower()


def random_password():
    lower = random.choices(string.ascii_lowercase, k=8)
    upper = random.choices(string.ascii_uppercase, k=4)
    digits = random.choices(string.digits, k=4)
    special = random.choices("@#$%&*", k=2)
    pool = lower + upper + digits + special
    random.shuffle(pool)
    return "".join(pool)


def random_birthday():
    year = random.randint(1985, 2003)
    month = random.randint(1, 12)
    day = random.randint(1, 28)
    return {"year": year, "month": month, "day": day, "is_over_18": True}


def random_device_id():
    return "".join(random.choices("abcdef" + string.digits, k=32))


def random_session_id():
    return "".join(random.choices(string.ascii_lowercase + string.digits, k=16))


def random_client_request_id():
    return "".join(random.choices(string.ascii_lowercase + string.digits, k=32))


def extract_code(text):
    if not text:
        return None
    matches = re.findall(r"\b(\d{6})\b", text)
    if matches:
        return matches[0]
    matches = re.findall(r"(\d{4,8})", text)
    if matches:
        return matches[0]
    return None

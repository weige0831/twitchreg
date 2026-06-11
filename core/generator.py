import random
import string


def random_username(length: int = 10) -> str:
    prefix = random.choice(string.ascii_lowercase)
    body = "".join(random.choices(string.ascii_lowercase + string.digits, k=length - 1))
    return prefix + body


def random_password(length: int = 16) -> str:
    lower = random.choices(string.ascii_lowercase, k=4)
    upper = random.choices(string.ascii_uppercase, k=4)
    digits = random.choices(string.digits, k=4)
    special = random.choices("!@#$%&*", k=2)
    rest = random.choices(string.ascii_letters + string.digits + "!@#$%&*", k=length - 14)
    pool = lower + upper + digits + special + rest
    random.shuffle(pool)
    return "".join(pool)


def random_birthday() -> dict:
    return {
        "day": random.randint(1, 28),
        "month": random.randint(1, 12),
        "year": random.randint(1975, 2000),
    }

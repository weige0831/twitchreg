import os
import yaml

DEFAULT_CONFIG_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.yaml")


def load_config(path: str = None) -> dict:
    path = path or DEFAULT_CONFIG_PATH
    with open(path, "r", encoding="utf-8") as f:
        cfg = yaml.safe_load(f)

    defaults = {
        "twitch": {
            "client_id": "kimne78kx3ncx6brgo4mv6wki5h1ko",
            "signup_url": "https://www.twitch.tv/signup",
        },
        "worker": {
            "concurrency": 3,
            "total_count": 0,
            "worker_name": "reg_worker",
        },
        "tempmail": {
            "base_url": "https://mail.minecraft-cn.net",
            "mail_domain": "olsbvgq.shop",
            "poll_interval": 5,
            "poll_timeout": 120,
        },
        "cdk_api": {
            "base_url": "",
            "api_token": "twitch-cdk-api-token-2024",
        },
        "browser": {
            "headless": True,
            "timeout": 30000,
        },
    }

    for section, values in defaults.items():
        if section not in cfg:
            cfg[section] = {}
        for key, val in values.items():
            cfg[section].setdefault(key, val)

    return cfg

import requests


def fetch_url(url: str) -> str:
    # УЯЗВИМОСТЬ (Bandit B501 HIGH): отключена проверка SSL-сертификата
    # УЯЗВИМОСТЬ (Bandit B113): запрос без timeout
    r = requests.get(url, verify=False)
    return r.text


def save_report(text: str) -> str:
    # УЯЗВИМОСТЬ (Bandit B108): небезопасная временная директория
    path = "/tmp/report.txt"
    with open(path, "w") as f:
        f.write(text)
    return path


def safe_parse(value: str):
    try:
        return int(value)
    except Exception:
        # УЯЗВИМОСТЬ (Bandit B110): try/except/pass
        pass

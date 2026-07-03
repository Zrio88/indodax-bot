import json
import time
import urllib.request


class FearGreedSentiment:
    _cache: dict = {"value": None, "ts": 0}

    @classmethod
    def fetch(cls) -> int | None:
        now = time.time()
        if cls._cache["value"] is not None and now - cls._cache["ts"] < 3600:
            return cls._cache["value"]
        try:
            req = urllib.request.Request(
                "https://api.alternative.me/fng/?limit=1",
                headers={"User-Agent": "Mozilla/5.0"},
            )
            with urllib.request.urlopen(req, timeout=10) as r:
                data = json.loads(r.read())
            val = int(data["data"][0]["value"])
            cls._cache = {"value": val, "ts": now}
            return val
        except Exception:
            return cls._cache["value"]

    @classmethod
    def score(cls) -> float:
        fng = cls.fetch()
        if fng is None:
            return 0.5
        if fng <= 20:
            return 1.00
        if fng <= 40:
            return 0.75
        if fng <= 60:
            return 0.50
        if fng <= 80:
            return 0.25
        return 0.00

    @classmethod
    def label(cls) -> str:
        fng = cls.fetch()
        if fng is None:
            return "unknown"
        if fng <= 20:
            return f"extreme_fear ({fng})"
        if fng <= 40:
            return f"fear ({fng})"
        if fng <= 60:
            return f"neutral ({fng})"
        if fng <= 80:
            return f"greed ({fng})"
        return f"extreme_greed ({fng})"

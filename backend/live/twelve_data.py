from __future__ import annotations

import os
from datetime import datetime, timezone

import requests

from backend.nds_core import Bar


class TwelveDataError(RuntimeError):
    pass


class TwelveDataFeed:
    URL = "https://api.twelvedata.com/time_series"

    def __init__(self, api_key: str | None = None, timeout: float = 15.0):
        self.api_key = api_key or os.getenv("TWELVE_DATA_API_KEY")
        self.timeout = timeout

        if not self.api_key:
            raise TwelveDataError("TWELVE_DATA_API_KEY is not configured")

    def bars(
        self,
        symbol: str = "XAU/USD",
        interval: str = "5min",
        outputsize: int = 300,
    ) -> list[Bar]:
        response = requests.get(
            self.URL,
            params={
                "symbol": symbol,
                "interval": interval,
                "outputsize": outputsize,
                "apikey": self.api_key,
            },
            timeout=self.timeout,
        )
        response.raise_for_status()

        data = response.json()

        if data.get("status") == "error":
            raise TwelveDataError(data.get("message", "Twelve Data API error"))

        values = data.get("values")
        if not values:
            raise TwelveDataError("Twelve Data returned no candle data")

        result: list[Bar] = []

        for row in reversed(values):
            dt = datetime.strptime(
                row["datetime"],
                "%Y-%m-%d %H:%M:%S",
            ).replace(tzinfo=timezone.utc)

            result.append(
                Bar(
                    time=dt,
                    open=float(row["open"]),
                    high=float(row["high"]),
                    low=float(row["low"]),
                    close=float(row["close"]),
                )
            )

        return result

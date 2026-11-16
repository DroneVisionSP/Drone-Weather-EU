import requests
import pandas as pd
import matplotlib.pyplot as plt
from datetime import date, timedelta

from analyse import ForecastAnalyzer
from locations import laad_locaties, kies_locatie
from drone import kies_drone


def haal_werkelijkheid(latitude, longitude, start, eind):
    url = "https://archive-api.open-meteo.com/v1/archive"
    parameters = {
        "latitude": latitude,
        "longitude": longitude,
        "start_date": start,
        "end_date": eind,
        "hourly": "wind_gusts_10m",
        "wind_speed_unit": "ms",
        "timezone": "auto",
    }
    try:
        antwoord = requests.get(url, params=parameters, timeout=15)
        antwoord.raise_for_status()
        data = antwoord.json()
    except requests.exceptions.RequestException as fout:
        print("Kon geen gemeten data ophalen:", fout)
        return None

    tabel = pd.DataFrame(data["hourly"])
    tabel["time"] = pd.to_datetime(tabel["time"])
    tabel = tabel.rename(columns={"wind_gusts_10m": "werkelijk"})
    return tabel.dropna()


class ForecastVerifier:
    def __init__(self, data, werkelijk):
        self.data = data
        self.werkelijk = werkelijk

    def vergelijk(self):
        d = self.data[self.data["is_day"] == 1].copy()
        d = d.merge(self.werkelijk, on="time", how="inner")
        d["uren_vooruit"] = (d["time"] - d["opgehaald_op"]).dt.total_seconds() / 3600
        d = d[d["uren_vooruit"] >= 0]
        d["verschil"] = d["wind_gusts_10m"] - d["werkelijk"]
        d["fout"] = d["verschil"].abs()
        d["dagen_vooruit"] = (d["uren_vooruit"] // 24).astype(int)
        return d

    def samenvatting(self, vergelijking):
        return vergelijking.groupby("dagen_vooruit").agg(
            fout=("fout", "mean"),
            bias=("verschil", "mean"),
            aantal=("fout", "count"),
        )

    def grafiek(self, vergelijking, locatie, drone):
        plt.figure(figsize=(7, 7))
        plt.scatter(vergelijking["werkelijk"], vergelijking["wind_gusts_10m"], alpha=0.3)
        grens = max(vergelijking["werkelijk"].max(), vergelijking["wind_gusts_10m"].max())
        plt.plot([0, grens], [0, grens], color="red", linestyle="--", label="Perfecte voorspelling")
        plt.title(f"Voorspeld tegenover gemeten - {locatie} ({drone})")
        plt.xlabel("Gemeten windstoten (m/s)")
        plt.ylabel("Voorspelde windstoten (m/s)")
        plt.legend()
        plt.tight_layout()
        plt.savefig("verificatie.png")
        plt.show()


def main():
    try:
        analyzer = ForecastAnalyzer("log.csv")
    except FileNotFoundError:
        print("log.csv niet gevonden.")
        return

    namen = analyzer.drones()
    drone = kies_drone(namen, namen[0])

    locaties = laad_locaties("locations.json")
    if locaties is None:
        return
    locatie = kies_locatie(locaties)

    data = analyzer.selecteer(locatie, drone)
    if data.empty:
        print("Geen data voor deze keuze.")
        return

    start = data["time"].min().date()
    eind = min(data["time"].max().date(), date.today() - timedelta(days=1))
    if start > eind:
        print("Er zijn nog geen voorbije uren om mee te vergelijken. Meet nog wat langer.")
        return

    plaats = locaties[locatie]
    werkelijk = haal_werkelijkheid(plaats["latitude"], plaats["longitude"], start, eind)
    if werkelijk is None or werkelijk.empty:
        print("Er is nog geen gemeten data beschikbaar voor deze periode.")
        return

    verifier = ForecastVerifier(data, werkelijk)
    vergelijking = verifier.vergelijk()
    if vergelijking.empty:
        print("Geen overlap tussen voorspellingen en gemeten data.")
        return

    print(f"\nVergeleken metingen: {len(vergelijking)}")
    print("\nAfwijking per aantal dagen vooruit (m/s):")
    print(verifier.samenvatting(vergelijking).round(2))

    verifier.grafiek(vergelijking, locatie, drone)


if __name__ == "__main__":
    main()
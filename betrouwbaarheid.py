import matplotlib.pyplot as plt

from analyse import ForecastAnalyzer
from locations import laad_locaties, kies_locatie
from drone import kies_drone


class AccuracyAnalyzer:
    def __init__(self, data):
        self.data = data[data["is_day"] == 1].copy()

    def bereken_fouten(self):
        d = self.data.sort_values("opgehaald_op")
        d["uren_vooruit"] = (d["time"] - d["opgehaald_op"]).dt.total_seconds() / 3600
        d = d[d["uren_vooruit"] >= 0]

        laatste_run = d.groupby("time")["opgehaald_op"].transform("max")
        referentie = d.groupby("time")["wind_gusts_10m"].last()

        vergelijk = d[d["opgehaald_op"] < laatste_run].copy()
        vergelijk["referentie"] = vergelijk["time"].map(referentie)
        vergelijk["fout"] = (vergelijk["wind_gusts_10m"] - vergelijk["referentie"]).abs()
        vergelijk["dagen_vooruit"] = (vergelijk["uren_vooruit"] // 24).astype(int)
        return vergelijk

    def samenvatting(self, fouten):
        return fouten.groupby("dagen_vooruit")["fout"].agg(["mean", "max", "count"])

    def grafiek(self, samenvatting, locatie, drone):
        plt.figure(figsize=(10, 5))
        plt.bar(samenvatting.index.astype(str), samenvatting["mean"])
        plt.title(f"Gemiddelde afwijking windstoten - {locatie} ({drone})")
        plt.xlabel("Dagen vooruit (0 = minder dan 24 uur)")
        plt.ylabel("Gemiddelde afwijking (m/s)")
        plt.tight_layout()
        plt.savefig("betrouwbaarheid.png")
        plt.show()


def main():
    try:
        analyzer = ForecastAnalyzer("log.csv")
    except FileNotFoundError:
        print("log.csv niet gevonden. Draai eerst main.py of meting.py.")
        return

    namen = analyzer.drones()
    drone = kies_drone(namen, namen[0])

    locaties = laad_locaties("locations.json")
    if locaties is None:
        return
    locatie = kies_locatie(locaties)

    data = analyzer.selecteer(locatie, drone)
    runs = analyzer.aantal_runs(data)
    print(f"\nAantal runs voor {locatie} met {drone}: {runs}")
    if runs < 2:
        print("Je hebt minstens 2 runs nodig. Meet nog wat langer.")
        return

    accuracy = AccuracyAnalyzer(data)
    fouten = accuracy.bereken_fouten()
    if fouten.empty:
        print("Nog niets om te vergelijken.")
        return

    samenvatting = accuracy.samenvatting(fouten)
    print("\nAfwijking per aantal dagen vooruit:")
    print(samenvatting.round(2))

    accuracy.grafiek(samenvatting, locatie, drone)


if __name__ == "__main__":
    main()
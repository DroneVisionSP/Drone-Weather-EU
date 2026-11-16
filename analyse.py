import pandas as pd
import matplotlib.pyplot as plt

from locations import laad_locaties, kies_locatie
from drone import kies_drone


class ForecastAnalyzer:
    def __init__(self, bestand):
        self.log = pd.read_csv(bestand)
        self.log["time"] = pd.to_datetime(self.log["time"])
        self.log["opgehaald_op"] = pd.to_datetime(self.log["opgehaald_op"], format="mixed")

    def drones(self):
        return sorted(self.log["drone"].unique())

    def selecteer(self, locatie, drone):
        return self.log[(self.log["locatie"] == locatie) & (self.log["drone"] == drone)]

    def aantal_runs(self, data):
        return data["opgehaald_op"].nunique()

    def verschillen(self, data):
        overdag = data[data["is_day"] == 1].sort_values("opgehaald_op")
        groepen = overdag.groupby("time")
        eerste = groepen.first()
        laatste = groepen.last()

        resultaat = pd.DataFrame({
            "aantal": groepen.size(),
            "eerste_stoot": eerste["wind_gusts_10m"],
            "laatste_stoot": laatste["wind_gusts_10m"],
            "eerste_score": eerste["score"],
            "laatste_score": laatste["score"],
        })
        resultaat["verschil"] = (resultaat["laatste_stoot"] - resultaat["eerste_stoot"]).abs()
        resultaat["score_veranderd"] = resultaat["eerste_score"] != resultaat["laatste_score"]
        return resultaat[resultaat["aantal"] >= 2]

    def grafiek(self, data, locatie, drone):
        plt.figure(figsize=(12, 5))
        for tijdstip, groep in data.groupby("opgehaald_op"):
            groep = groep.drop_duplicates("time", keep="last").sort_values("time")
            plt.plot(groep["time"], groep["wind_gusts_10m"],
                     label=tijdstip.strftime("%d/%m %H:%M:%S"))
        plt.title(f"Hoe de voorspelde windstoten verschuiven - {locatie} ({drone})")
        plt.xlabel("Tijd")
        plt.ylabel("Windstoten (m/s)")
        plt.legend(title="Opgehaald op")
        plt.tight_layout()
        plt.savefig("analyse.png")
        plt.show()


def main():
    try:
        analyzer = ForecastAnalyzer("log.csv")
    except FileNotFoundError:
        print("log.csv niet gevonden. Draai eerst main.py.")
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
        print("Je hebt minstens 2 runs nodig om te vergelijken. Draai main.py nog eens.")
        return

    verschil = analyzer.verschillen(data)
    print(f"Vergeleken daguren: {len(verschil)}")
    print(f"Gemiddeld verschil windstoot: {verschil['verschil'].mean():.2f} m/s")
    print(f"Grootste verschil windstoot:  {verschil['verschil'].max():.2f} m/s")
    print(f"Uren waarvan de score veranderde: {verschil['score_veranderd'].sum()}")

    veranderd = verschil[verschil["score_veranderd"]]
    if not veranderd.empty:
        print("\nUren met een andere score:")
        print(veranderd[["eerste_stoot", "laatste_stoot", "eerste_score", "laatste_score"]])

    analyzer.grafiek(data, locatie, drone)


if __name__ == "__main__":
    main()
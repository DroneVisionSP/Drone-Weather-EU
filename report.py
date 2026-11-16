import os
from datetime import datetime
import pandas as pd
import matplotlib.pyplot as plt

LOG_KOLOMMEN = ["time", "temperature_2m", "wind_speed_10m", "wind_gusts_10m",
                "precipitation", "visibility", "is_day", "dag", "score"]


class Report:
    def __init__(self, drone, locatie, marge):
        self.drone = drone
        self.locatie = locatie
        self.marge = marge

    def sla_op(self, tabel, bestandsnaam):
        kopie = tabel[LOG_KOLOMMEN].copy()
        kopie["opgehaald_op"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        kopie["locatie"] = self.locatie
        kopie["drone"] = self.drone.naam

        bestaat_al = os.path.exists(bestandsnaam)
        kopie.to_csv(bestandsnaam, mode="a", header=not bestaat_al, index=False)

    def maak_grafiek(self, tabel):
        plt.figure(figsize=(12, 5))
        plt.plot(tabel["time"], tabel["wind_speed_10m"], label="Wind")
        plt.plot(tabel["time"], tabel["wind_gusts_10m"], label="Windstoten")
        plt.axhline(self.drone.max_wind, color="red", linestyle="--", label="Limiet drone")
        plt.axhline(self.drone.max_wind * self.marge, color="orange", linestyle="--", label="Twijfelgrens")
        plt.title(f"Wind komende 7 dagen - {self.locatie} ({self.drone.naam})")
        plt.xlabel("Tijd")
        plt.ylabel("Snelheid (m/s)")
        plt.legend()
        plt.tight_layout()
        plt.savefig("grafiek.png")

    def maak_dagoverzicht(self, tabel):
        overdag = tabel[tabel["score"] != "nacht"]
        telling = pd.crosstab(overdag["dag"], overdag["score"])

        volgorde = ["goed", "twijfelachtig", "niet vliegen"]
        for kolom in volgorde:
            if kolom not in telling.columns:
                telling[kolom] = 0
        telling = telling[volgorde]

        print("\nOverzicht per dag (aantal daguren):")
        print(telling)

        telling.index = [dag.strftime("%a %d/%m") for dag in telling.index]
        ax = telling.plot(kind="bar", stacked=True,
                          color=["green", "orange", "red"], figsize=(12, 5))
        ax.set_title(f"Vliegbare uren per dag - {self.locatie} ({self.drone.naam})")
        ax.set_xlabel("Dag")
        ax.set_ylabel("Aantal uren overdag")
        plt.xticks(rotation=0)
        plt.tight_layout()
        plt.savefig("dagoverzicht.png")

    def toon(self):
        plt.show()
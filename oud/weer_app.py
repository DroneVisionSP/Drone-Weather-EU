import json
import requests
import pandas as pd
import matplotlib.pyplot as plt

START_UUR = 10     # eerste uur waarop je wilt vliegen
EIND_UUR = 16      # laatste uur waarop je wilt vliegen


class Drone:
    def __init__(self, naam, max_wind, min_temp, max_temp):
        self.naam = naam
        self.max_wind = max_wind
        self.min_temp = min_temp
        self.max_temp = max_temp


def laad_drone(bestand, naam):
    try:
        with open(bestand, encoding="utf-8") as f:
            alle_drones = json.load(f)
        gegevens = alle_drones[naam]
    except FileNotFoundError:
        print(f"Bestand {bestand} niet gevonden.")
        return None
    except json.JSONDecodeError:
        print(f"Er zit een fout in {bestand}.")
        return None
    except KeyError:
        print(f"Drone '{naam}' staat niet in {bestand}.")
        return None

    return Drone(
        naam,
        gegevens["max_wind"],
        gegevens["min_temp"],
        gegevens["max_temp"],
    )


def laad_locaties(bestand):
    try:
        with open(bestand, encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        print(f"Bestand {bestand} niet gevonden.")
        return None
    except json.JSONDecodeError:
        print(f"Er zit een fout in {bestand}.")
        return None


def kies_locatie(locaties):
    namen = list(locaties.keys())
    print("Kies een locatie:")
    for nummer, naam in enumerate(namen, start=1):
        print(f"  {nummer}. {naam}")

    while True:
        invoer = input("Nummer: ")
        try:
            keuze = int(invoer)
        except ValueError:
            print("Typ een getal.")
            continue
        if 1 <= keuze <= len(namen):
            return namen[keuze - 1]
        print(f"Kies een getal tussen 1 en {len(namen)}.")


class WeatherClient:
    def __init__(self, latitude, longitude):
        self.latitude = latitude
        self.longitude = longitude

    def haal_weer_op(self):
        url = "https://api.open-meteo.com/v1/forecast"
        parameters = {
            "latitude": self.latitude,
            "longitude": self.longitude,
            "hourly": "temperature_2m,wind_speed_10m,wind_gusts_10m,precipitation,visibility,is_day",
            "wind_speed_unit": "ms",
            "timezone": "auto",
        }
        try:
            antwoord = requests.get(url, params=parameters, timeout=10)
            antwoord.raise_for_status()
            return antwoord.json()
        except requests.exceptions.RequestException as fout:
            print("Kon geen weerdata ophalen:", fout)
            return None

    def haal_tabel(self):
        data = self.haal_weer_op()
        if data is None:
            return None
        tabel = pd.DataFrame(data["hourly"])
        tabel["time"] = pd.to_datetime(tabel["time"])
        tabel["dag"] = tabel["time"].dt.date
        return tabel


class FlightScorer:
    def __init__(self, drone):
        self.drone = drone

    def score_van_rij(self, rij):
        d = self.drone
        if rij["is_day"] == 0:
            return "nacht"
        if rij["precipitation"] > 0.1:
            return "niet vliegen"
        if rij["visibility"] < 1000:
            return "niet vliegen"
        if rij["temperature_2m"] < d.min_temp or rij["temperature_2m"] > d.max_temp:
            return "niet vliegen"
        if rij["wind_gusts_10m"] > d.max_wind:
            return "niet vliegen"
        if rij["wind_gusts_10m"] > d.max_wind * 0.7:
            return "twijfelachtig"
        return "goed"

    def voeg_score_toe(self, tabel):
        tabel["score"] = tabel.apply(self.score_van_rij, axis=1)
        return tabel

    def beste_uren(self, tabel):
        uur = tabel["time"].dt.hour
        goede_uren = tabel[(tabel["score"] == "goed") & (uur >= START_UUR) & (uur <= EIND_UUR)]
        return goede_uren.loc[goede_uren.groupby("dag")["wind_gusts_10m"].idxmin()]


class Report:
    def __init__(self, drone, locatie):
        self.drone = drone
        self.locatie = locatie

    def sla_op(self, tabel, bestandsnaam):
        tabel.to_csv(bestandsnaam, index=False)

    def maak_grafiek(self, tabel):
        plt.figure(figsize=(12, 5))
        plt.plot(tabel["time"], tabel["wind_speed_10m"], label="Wind")
        plt.plot(tabel["time"], tabel["wind_gusts_10m"], label="Windstoten")
        plt.axhline(self.drone.max_wind, color="red", linestyle="--", label="Limiet drone")
        plt.axhline(self.drone.max_wind * 0.7, color="orange", linestyle="--", label="Twijfelgrens")
        plt.title(f"Wind komende 7 dagen - {self.locatie} ({self.drone.naam})")
        plt.xlabel("Tijd")
        plt.ylabel("Snelheid (m/s)")
        plt.legend()
        plt.tight_layout()
        plt.savefig("grafiek.png")
        plt.show()


def main():
    drone = laad_drone("drones.json", "Mini 5 Pro")
    if drone is None:
        return

    locaties = laad_locaties("locations.json")
    if locaties is None:
        return

    locatie_naam = kies_locatie(locaties)
    gegevens = locaties[locatie_naam]

    weer = WeatherClient(gegevens["latitude"], gegevens["longitude"])
    scorer = FlightScorer(drone)
    rapport = Report(drone, locatie_naam)

    tabel = weer.haal_tabel()
    if tabel is None:
        print("Het programma stopt omdat er geen weerdata is.")
        return

    tabel = scorer.voeg_score_toe(tabel)

    print("\nDrone:", drone.naam)
    print("Locatie:", locatie_naam)
    print(tabel["score"].value_counts())
    print("\nBeste uur per dag:")
    print(scorer.beste_uren(tabel)[["time", "wind_gusts_10m", "temperature_2m"]])

    rapport.sla_op(tabel, "log.csv")
    rapport.maak_grafiek(tabel)


if __name__ == "__main__":
    main()
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
    with open(bestand, encoding="utf-8") as f:
        alle_drones = json.load(f)
    gegevens = alle_drones[naam]
    return Drone(
        naam,
        gegevens["max_wind"],
        gegevens["min_temp"],
        gegevens["max_temp"],
    )


def haal_weer_op(latitude, longitude):
    url = "https://api.open-meteo.com/v1/forecast"
    parameters = {
        "latitude": latitude,
        "longitude": longitude,
        "hourly": "temperature_2m,wind_speed_10m,wind_gusts_10m,precipitation,visibility,is_day",
        "wind_speed_unit": "ms",
        "timezone": "auto",
    }
    antwoord = requests.get(url, params=parameters)
    return antwoord.json()


def maak_tabel(data):
    tabel = pd.DataFrame(data["hourly"])
    tabel["time"] = pd.to_datetime(tabel["time"])
    tabel["dag"] = tabel["time"].dt.date
    return tabel


def bepaal_score(rij, drone):
    if rij["is_day"] == 0:
        return "nacht"
    if rij["precipitation"] > 0.1:
        return "niet vliegen"
    if rij["visibility"] < 1000:
        return "niet vliegen"
    if rij["temperature_2m"] < drone.min_temp or rij["temperature_2m"] > drone.max_temp:
        return "niet vliegen"
    if rij["wind_gusts_10m"] > drone.max_wind:
        return "niet vliegen"
    if rij["wind_gusts_10m"] > drone.max_wind * 0.7:
        return "twijfelachtig"
    return "goed"


def voeg_score_toe(tabel, drone):
    tabel["score"] = tabel.apply(bepaal_score, axis=1, drone=drone)
    return tabel


def beste_uren(tabel):
    uur = tabel["time"].dt.hour
    goede_uren = tabel[(tabel["score"] == "goed") & (uur >= START_UUR) & (uur <= EIND_UUR)]
    return goede_uren.loc[goede_uren.groupby("dag")["wind_gusts_10m"].idxmin()]


def sla_op(tabel, bestandsnaam):
    tabel.to_csv(bestandsnaam, index=False)


def maak_grafiek(tabel, drone):
    plt.figure(figsize=(12, 5))
    plt.plot(tabel["time"], tabel["wind_speed_10m"], label="Wind")
    plt.plot(tabel["time"], tabel["wind_gusts_10m"], label="Windstoten")
    plt.axhline(drone.max_wind, color="red", linestyle="--", label="Limiet drone")
    plt.axhline(drone.max_wind * 0.7, color="orange", linestyle="--", label="Twijfelgrens")
    plt.title(f"Wind komende 7 dagen ({drone.naam})")
    plt.xlabel("Tijd")
    plt.ylabel("Snelheid (m/s)")
    plt.legend()
    plt.tight_layout()
    plt.savefig("grafiek.png")
    plt.show()


def main():
    drone = laad_drone("drones.json", "Mini 5 Pro")
    data = haal_weer_op(51.2093, 3.2247)
    tabel = maak_tabel(data)
    tabel = voeg_score_toe(tabel, drone)

    print("Drone:", drone.naam)
    print(tabel["score"].value_counts())
    print("\nBeste uur per dag:")
    print(beste_uren(tabel)[["time", "wind_gusts_10m", "temperature_2m"]])

    sla_op(tabel, "log.csv")
    maak_grafiek(tabel, drone)


if __name__ == "__main__":
    main()
import requests
import pandas as pd
import matplotlib.pyplot as plt

# --- Instellingen van de drone (DJI Mini 5 Pro) ---
MAX_WIND = 12      # m/s, maximale windweerstand
MIN_TEMP = -10     # graden Celsius
MAX_TEMP = 40

# --- Locatie ---
latitude = 51.2093
longitude = 3.2247

# --- Weerdata ophalen ---
url = "https://api.open-meteo.com/v1/forecast"
parameters = {
    "latitude": latitude,
    "longitude": longitude,
    "hourly": "temperature_2m,wind_speed_10m,wind_gusts_10m,precipitation,visibility,is_day",
    "wind_speed_unit": "ms",
    "timezone": "auto",
}

antwoord = requests.get(url, params=parameters)
data = antwoord.json()

# --- Tabel maken ---
tabel = pd.DataFrame(data["hourly"])
tabel["time"] = pd.to_datetime(tabel["time"])
tabel["dag"] = tabel["time"].dt.date


# --- Score per uur ---
def bepaal_score(rij):
    if rij["is_day"] == 0:
        return "nacht"
    if rij["precipitation"] > 0.1:
        return "niet vliegen"
    if rij["visibility"] < 1000:
        return "niet vliegen"
    if rij["temperature_2m"] < MIN_TEMP or rij["temperature_2m"] > MAX_TEMP:
        return "niet vliegen"
    if rij["wind_gusts_10m"] > MAX_WIND:
        return "niet vliegen"
    if rij["wind_gusts_10m"] > MAX_WIND * 0.7:
        return "twijfelachtig"
    return "goed"


tabel["score"] = tabel.apply(bepaal_score, axis=1)

# --- Overzicht ---
print(tabel["score"].value_counts())

goede_uren = tabel[tabel["score"] == "goed"]

print("\nAantal goede uren per dag:")
print(goede_uren.groupby("dag").size())

beste = goede_uren.loc[goede_uren.groupby("dag")["wind_gusts_10m"].idxmin()]
print("\nBeste uur per dag (minste windstoten):")
print(beste[["time", "wind_gusts_10m", "temperature_2m"]])

# --- Opslaan ---
tabel.to_csv("log.csv", index=False)
print("\nOpgeslagen in log.csv")

# --- Grafiek ---
plt.figure(figsize=(12, 5))
plt.plot(tabel["time"], tabel["wind_speed_10m"], label="Wind")
plt.plot(tabel["time"], tabel["wind_gusts_10m"], label="Windstoten")
plt.axhline(MAX_WIND, color="red", linestyle="--", label="Limiet drone")
plt.axhline(MAX_WIND * 0.7, color="orange", linestyle="--", label="Twijfelgrens")

plt.title("Wind komende 7 dagen")
plt.xlabel("Tijd")
plt.ylabel("Snelheid (m/s)")
plt.legend()
plt.tight_layout()
plt.savefig("grafiek.png")
plt.show()
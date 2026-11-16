import requests
import pandas as pd

ZON_MARGE_MINUTEN = 30   # mag vliegen vanaf zo veel minuten voor zonsopgang tot zo veel erna


class WeatherClient:
    def __init__(self, latitude, longitude, marge_minuten=ZON_MARGE_MINUTEN):
        self.latitude = latitude
        self.longitude = longitude
        self.marge = pd.Timedelta(minutes=marge_minuten)

    def haal_weer_op(self):
        url = "https://api.open-meteo.com/v1/forecast"
        parameters = {
            "latitude": self.latitude,
            "longitude": self.longitude,
            "hourly": ("temperature_2m,wind_speed_10m,wind_gusts_10m,precipitation,"
                       "visibility,is_day,weather_code,precipitation_probability"),
            "daily": "sunrise,sunset",
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

    def zon_tijden(self, data):
        daily = data.get("daily")
        if not daily or "sunrise" not in daily or "sunset" not in daily:
            return None

        zon = pd.DataFrame({
            "dag": [d.date() for d in pd.to_datetime(daily["time"])],
            "zonsopgang": pd.to_datetime(daily["sunrise"]),
            "zonsondergang": pd.to_datetime(daily["sunset"]),
        })
        zon["vliegen_van"] = zon["zonsopgang"] - self.marge
        zon["vliegen_tot"] = zon["zonsondergang"] + self.marge
        return zon

    def pas_vliegvenster_toe(self, tabel, zon):
        koppel = zon[["dag", "vliegen_van", "vliegen_tot"]]
        tabel = tabel.merge(koppel, on="dag", how="left")

        einde_uur = tabel["time"] + pd.Timedelta(hours=1)
        mag = (einde_uur > tabel["vliegen_van"]) & (tabel["time"] < tabel["vliegen_tot"])
        tabel["is_day"] = mag.astype(int)
        return tabel.drop(columns=["vliegen_van", "vliegen_tot"])

    def haal_alles(self):
        data = self.haal_weer_op()
        if data is None:
            return None, None

        tabel = pd.DataFrame(data["hourly"])
        tabel["time"] = pd.to_datetime(tabel["time"])
        tabel["dag"] = tabel["time"].dt.date

        zon = self.zon_tijden(data)
        if zon is not None:
            tabel = self.pas_vliegvenster_toe(tabel, zon)
        return tabel, zon

    def haal_tabel(self):
        tabel, _ = self.haal_alles()
        return tabel
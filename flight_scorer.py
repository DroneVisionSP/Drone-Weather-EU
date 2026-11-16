import pandas as pd

NIVEAUS = ["goed", "twijfelachtig", "niet vliegen"]

MIST_CODES = {45, 48}
MOTREGEN_CODES = {51, 53, 55}
ONDERKOELD_CODES = {56, 57, 66, 67}
SNEEUW_CODES = {71, 73, 75, 77, 85, 86}
ONWEER_CODES = {95, 96, 99}


class FlightScorer:
    def __init__(self, drone, instellingen):
        self.drone = drone
        self.instellingen = instellingen

    def wind(self, rij):
        stoot = rij["wind_gusts_10m"]
        if stoot > self.drone.max_wind:
            return 2, f"windstoten van {stoot:.1f} m/s boven de limiet"
        if stoot > self.drone.max_wind * self.instellingen["marge"]:
            return 1, f"veel wind (stoten {stoot:.1f} m/s)"
        return 0, ""

    def temperatuur(self, rij):
        t = rij["temperature_2m"]
        d = self.drone
        speling = self.instellingen["temp_marge"]
        if t < d.min_temp or t > d.max_temp:
            return 2, f"temperatuur van {t:.0f} °C buiten het bereik van de drone"
        if t < d.min_temp + speling:
            return 1, f"koud ({t:.0f} °C), dicht bij de temperatuurgrens"
        if t > d.max_temp - speling:
            return 1, f"warm ({t:.0f} °C), dicht bij de temperatuurgrens"
        return 0, ""

    def zicht(self, rij):
        s = self.instellingen
        zicht = rij["visibility"]
        code = rij.get("weather_code")
        if code in MIST_CODES or zicht < s["min_zicht"]:
            return 2, f"mist (zicht {zicht:.0f} m)"
        if zicht < s["twijfel_zicht"]:
            return 1, f"nevel (zicht {zicht:.0f} m)"
        return 0, ""

    def neerslag(self, rij):
        s = self.instellingen
        regen = rij["precipitation"]
        code = rij.get("weather_code")
        kans = rij.get("precipitation_probability")

        if code in ONWEER_CODES:
            return 2, "onweer"
        if code in SNEEUW_CODES:
            return 2, "sneeuw"
        if code in ONDERKOELD_CODES:
            return 2, "ijzel of onderkoelde regen"
        if regen > s["max_regen"]:
            return 2, f"neerslag ({regen:.1f} mm)"
        if regen > 0 or code in MOTREGEN_CODES:
            return 1, "lichte neerslag"
        if pd.notna(kans) and kans >= s["regenkans"]:
            return 1, f"kans op neerslag ({kans:.0f}%)"
        return 0, ""

    def beoordeel(self, rij):
        if rij["is_day"] == 0:
            return {"score": "nacht", "reden": "buiten het vliegtijdvenster",
                    "niveaus": (-1, -1, -1, -1)}

        resultaten = [self.wind(rij), self.temperatuur(rij),
                      self.zicht(rij), self.neerslag(rij)]
        niveaus = tuple(niveau for niveau, _ in resultaten)
        redenen = [tekst for niveau, tekst in sorted(resultaten, key=lambda r: -r[0])
                   if niveau > 0]
        return {
            "score": NIVEAUS[max(niveaus)],
            "reden": "; ".join(redenen) if redenen else "geen bijzonderheden",
            "niveaus": niveaus,
        }

    def voeg_score_toe(self, tabel):
        beoordelingen = [self.beoordeel(rij) for _, rij in tabel.iterrows()]
        tabel["score"] = [b["score"] for b in beoordelingen]
        tabel["reden"] = [b["reden"] for b in beoordelingen]
        for i, naam in enumerate(["wind_niv", "temp_niv", "zicht_niv", "neerslag_niv"]):
            tabel[naam] = [b["niveaus"][i] for b in beoordelingen]
        return tabel

    def beste_uren(self, tabel):
        uur = tabel["time"].dt.hour
        start = self.instellingen["start_uur"]
        eind = self.instellingen["eind_uur"]
        goede_uren = tabel[(tabel["score"] == "goed") & (uur >= start) & (uur <= eind)]
        return goede_uren.loc[goede_uren.groupby("dag")["wind_gusts_10m"].idxmin()]
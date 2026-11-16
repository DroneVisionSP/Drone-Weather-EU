import pandas as pd

from flight_scorer import ONWEER_CODES, SNEEUW_CODES

KOLOMMEN = ["dag", "goed", "twijfelachtig", "niet vliegen",
            "max_stoot", "oordeel", "opmerking"]

SYMBOLEN = {"goed": "🟢", "twijfelachtig": "🟡", "niet vliegen": "🔴", "nacht": "🌙"}
ICOON = {0: "🟢", 1: "🟡", 2: "🔴"}


class Advisor:
    def __init__(self, drone, instellingen):
        self.drone = drone
        self.instellingen = instellingen

    def week(self, tabel):
        s = self.instellingen
        uur = tabel["time"].dt.hour
        venster = tabel[(uur >= s["start_uur"]) & (uur <= s["eind_uur"])
                        & (tabel["score"] != "nacht")]
        if venster.empty:
            return pd.DataFrame(columns=KOLOMMEN)

        rijen = []
        for dag, groep in venster.groupby("dag"):
            telling = groep["score"].value_counts()
            goed = int(telling.get("goed", 0))
            twijfel = int(telling.get("twijfelachtig", 0))
            niet = int(telling.get("niet vliegen", 0))
            rijen.append({
                "dag": dag,
                "goed": goed,
                "twijfelachtig": twijfel,
                "niet vliegen": niet,
                "max_stoot": groep["wind_gusts_10m"].max(),
                "oordeel": self.oordeel(goed, twijfel, niet),
                "opmerking": self.opmerking(groep),
            })
        return pd.DataFrame(rijen, columns=KOLOMMEN)

    def uurtabel(self, tabel):
        d = tabel.copy()
        d["uur"] = d["time"].dt.hour

        toegestane_uren = sorted(d.loc[d["score"] != "nacht", "uur"].unique())
        if not toegestane_uren:
            return pd.DataFrame()

        d = d[d["uur"].isin(toegestane_uren)]
        raster = d.pivot(index="dag", columns="uur", values="score")
        goede_uren = (raster == "goed").sum(axis=1)

        raster = raster.map(lambda score: SYMBOLEN.get(score, ""))
        raster.columns = [f"{u}u" for u in raster.columns]
        raster.insert(0, "Goede uren totaal", goede_uren)
        return raster

    def weerbericht(self, tabel):
        venster = tabel[tabel["score"] != "nacht"]
        if venster.empty:
            return pd.DataFrame()

        rijen = []
        for dag, g in venster.groupby("dag"):
            rijen.append({
                "dag": dag,
                "Wind": self.wind_tekst(g),
                "Temperatuur": self.temperatuur_tekst(g),
                "Mist en zicht": self.zicht_tekst(g),
                "Neerslag": self.neerslag_tekst(g),
            })
        return pd.DataFrame(rijen)

    def wind_tekst(self, g):
        icoon = ICOON[int(g["wind_niv"].max())]
        return (f"{icoon} {g['wind_speed_10m'].min():.0f} tot {g['wind_speed_10m'].max():.0f} m/s, "
                f"stoten tot {g['wind_gusts_10m'].max():.1f} m/s")

    def temperatuur_tekst(self, g):
        icoon = ICOON[int(g["temp_niv"].max())]
        return f"{icoon} {g['temperature_2m'].min():.0f} tot {g['temperature_2m'].max():.0f} °C"

    def zicht_tekst(self, g):
        niveau = int(g["zicht_niv"].max())
        icoon = ICOON[niveau]
        if niveau == 2:
            uren = g.loc[g["zicht_niv"] == 2, "time"].dt.hour
            return f"{icoon} mist, rond {uren.min()}u tot {uren.max()}u"
        if niveau == 1:
            return f"{icoon} nevel, zicht tot {g['visibility'].min() / 1000:.1f} km"
        return f"{icoon} goed zicht (minstens {g['visibility'].min() / 1000:.0f} km)"

    def neerslag_tekst(self, g):
        niveau = int(g["neerslag_niv"].max())
        icoon = ICOON[niveau]
        codes = set(g["weather_code"].dropna().astype(int)) if "weather_code" in g else set()

        if niveau == 2:
            if codes & ONWEER_CODES:
                soort = "onweer"
            elif codes & SNEEUW_CODES:
                soort = "sneeuw"
            else:
                soort = "neerslag"
            uren = int((g["precipitation"] > 0).sum())
            return f"{icoon} {soort}, {g['precipitation'].sum():.1f} mm ({uren} uur nat)"

        if niveau == 1:
            kans = g["precipitation_probability"].max() if "precipitation_probability" in g else float("nan")
            extra = f", kans tot {kans:.0f}%" if pd.notna(kans) else ""
            return f"{icoon} lichte neerslag mogelijk{extra}"

        return f"{icoon} droog"

    def oordeel(self, goed, twijfel, niet):
        totaal = goed + twijfel + niet
        if goed >= max(1, (totaal + 1) // 2):
            return "goed"
        if goed + twijfel >= 1:
            return "twijfelachtig"
        return "niet vliegen"

    def opmerking(self, groep):
        delen = []

        wind = int(groep["wind_niv"].max())
        stoot = groep["wind_gusts_10m"].max()
        if wind == 2:
            delen.append(f"windstoten tot {stoot:.1f} m/s (limiet {self.drone.max_wind})")
        elif wind == 1:
            delen.append(f"veel wind, stoten tot {stoot:.1f} m/s")

        temp = int(groep["temp_niv"].max())
        if temp == 2:
            delen.append("temperatuur buiten het bereik van de drone")
        elif temp == 1:
            delen.append("dicht bij de temperatuurgrens")

        zicht = int(groep["zicht_niv"].max())
        if zicht == 2:
            delen.append("mist")
        elif zicht == 1:
            delen.append("nevel")

        neerslag = int(groep["neerslag_niv"].max())
        if neerslag == 2:
            delen.append("neerslag of onweer")
        elif neerslag == 1:
            delen.append("lichte neerslag mogelijk")

        return ", ".join(delen) if delen else "geen bijzonderheden"
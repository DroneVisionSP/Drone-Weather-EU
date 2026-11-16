"""Tests voor de Vliegweer-assistent. Starten met: python -m unittest -v"""
import json
import os
import tempfile
import unittest
from unittest import mock

import matplotlib
matplotlib.use("Agg")

import pandas as pd
import requests

import geocoding
from advies import Advisor
from drone import Drone, laad_drone
from flight_scorer import FlightScorer
from geocoding import Geocoder
from report import LOG_KOLOMMEN, Report
from settings import STANDAARD, laad_settings
from weather_client import WeatherClient


# --- Hulpfuncties ---------------------------------------------------------

def rij_dict(**wijzigingen):
    """Een gewoon uur: droog, helder, weinig wind, 12 graden, overdag."""
    rij = {
        "time": "2026-11-10 12:00",
        "temperature_2m": 12.0,
        "wind_speed_10m": 3.0,
        "wind_gusts_10m": 5.0,
        "precipitation": 0.0,
        "visibility": 20000.0,
        "is_day": 1,
        "weather_code": 0,
        "precipitation_probability": 0,
    }
    rij.update(wijzigingen)
    return rij


def maak_tabel(rijen):
    tabel = pd.DataFrame(rijen)
    tabel["time"] = pd.to_datetime(tabel["time"])
    tabel["dag"] = tabel["time"].dt.date
    return tabel


class BasisTest(unittest.TestCase):
    def setUp(self):
        self.drone = Drone("Testdrone", 12, -10, 40)
        self.instellingen = dict(STANDAARD)
        self.scorer = FlightScorer(self.drone, self.instellingen)

    def score(self, **wijzigingen):
        return self.scorer.beoordeel(pd.Series(rij_dict(**wijzigingen)))["score"]


# --- Score per factor -----------------------------------------------------

class TestScoreFactoren(BasisTest):
    def test_gewoon_uur_is_goed(self):
        self.assertEqual(self.score(), "goed")

    def test_nacht(self):
        self.assertEqual(self.score(is_day=0), "nacht")

    def test_wind(self):
        gevallen = [(5, "goed"), (8, "goed"), (9, "twijfelachtig"),
                    (12, "twijfelachtig"), (12.1, "niet vliegen"), (20, "niet vliegen")]
        for stoot, verwacht in gevallen:
            with self.subTest(stoot=stoot):
                self.assertEqual(self.score(wind_gusts_10m=stoot), verwacht)

    def test_temperatuur(self):
        gevallen = [(12, "goed"), (-5, "goed"), (-6, "twijfelachtig"),
                    (-10, "twijfelachtig"), (-10.1, "niet vliegen"),
                    (35, "goed"), (36, "twijfelachtig"), (40, "twijfelachtig"),
                    (40.1, "niet vliegen")]
        for temp, verwacht in gevallen:
            with self.subTest(temperatuur=temp):
                self.assertEqual(self.score(temperature_2m=temp), verwacht)

    def test_zicht(self):
        gevallen = [(20000, "goed"), (5000, "goed"), (4999, "twijfelachtig"),
                    (1000, "twijfelachtig"), (999, "niet vliegen")]
        for zicht, verwacht in gevallen:
            with self.subTest(zicht=zicht):
                self.assertEqual(self.score(visibility=zicht), verwacht)

    def test_mist_volgens_weercode_ook_bij_goed_zicht(self):
        self.assertEqual(self.score(weather_code=45, visibility=20000), "niet vliegen")

    def test_neerslag(self):
        gevallen = [(0.0, "goed"), (0.05, "twijfelachtig"), (0.1, "twijfelachtig"),
                    (0.11, "niet vliegen"), (2.0, "niet vliegen")]
        for regen, verwacht in gevallen:
            with self.subTest(regen=regen):
                self.assertEqual(self.score(precipitation=regen), verwacht)

    def test_weercodes(self):
        gevallen = [(95, "niet vliegen"), (73, "niet vliegen"),
                    (66, "niet vliegen"), (51, "twijfelachtig"), (3, "goed")]
        for code, verwacht in gevallen:
            with self.subTest(code=code):
                self.assertEqual(self.score(weather_code=code), verwacht)

    def test_regenkans(self):
        gevallen = [(60, "twijfelachtig"), (50, "twijfelachtig"),
                    (40, "goed"), (float("nan"), "goed")]
        for kans, verwacht in gevallen:
            with self.subTest(kans=kans):
                self.assertEqual(self.score(precipitation_probability=kans), verwacht)

    def test_ergste_factor_wint(self):
        self.assertEqual(self.score(wind_gusts_10m=9, precipitation=0.5), "niet vliegen")

    def test_reden_noemt_de_oorzaak(self):
        reden = self.scorer.beoordeel(pd.Series(rij_dict(visibility=800)))["reden"]
        self.assertIn("mist", reden)

    def test_andere_drone_andere_limiet(self):
        zwakke_drone = Drone("Zwak", 8, -10, 40)
        scorer = FlightScorer(zwakke_drone, self.instellingen)
        rij = pd.Series(rij_dict(wind_gusts_10m=9))
        self.assertEqual(scorer.beoordeel(rij)["score"], "niet vliegen")


# --- Beste uren, dagoordeel, tabellen ------------------------------------

class TestAdvies(BasisTest):
    def test_beste_uur_ligt_binnen_voorkeursuren(self):
        tabel = maak_tabel([
            rij_dict(time="2026-11-10 09:00", wind_gusts_10m=1.0),
            rij_dict(time="2026-11-10 11:00", wind_gusts_10m=6.0),
            rij_dict(time="2026-11-10 13:00", wind_gusts_10m=4.0),
        ])
        tabel = self.scorer.voeg_score_toe(tabel)
        beste = self.scorer.beste_uren(tabel)
        self.assertEqual(len(beste), 1)
        self.assertEqual(beste.iloc[0]["time"], pd.Timestamp("2026-11-10 13:00"))

    def test_dagoordeel(self):
        advisor = Advisor(self.drone, self.instellingen)
        gevallen = [(5, 0, 0, "goed"), (2, 0, 2, "goed"), (1, 3, 1, "twijfelachtig"),
                    (0, 2, 0, "twijfelachtig"), (0, 0, 4, "niet vliegen")]
        for goed, twijfel, niet, verwacht in gevallen:
            with self.subTest(uren=(goed, twijfel, niet)):
                self.assertEqual(advisor.oordeel(goed, twijfel, niet), verwacht)

    def test_week_telt_alleen_toegestane_voorkeursuren(self):
        tabel = maak_tabel([
            rij_dict(time="2026-11-10 03:00", is_day=0),
            rij_dict(time="2026-11-10 10:00"),
            rij_dict(time="2026-11-10 11:00"),
            rij_dict(time="2026-11-10 12:00", wind_gusts_10m=20.0),
        ])
        tabel = self.scorer.voeg_score_toe(tabel)
        week = Advisor(self.drone, self.instellingen).week(tabel)
        self.assertEqual(len(week), 1)
        rij = week.iloc[0]
        self.assertEqual((rij["goed"], rij["twijfelachtig"], rij["niet vliegen"]), (2, 0, 1))
        self.assertEqual(rij["oordeel"], "goed")

    def test_uurtabel_toont_alleen_toegestane_uren(self):
        tabel = maak_tabel([
            rij_dict(time="2026-11-10 03:00", is_day=0),
            rij_dict(time="2026-11-10 10:00"),
            rij_dict(time="2026-11-10 11:00"),
        ])
        tabel = self.scorer.voeg_score_toe(tabel)
        raster = Advisor(self.drone, self.instellingen).uurtabel(tabel)
        self.assertEqual(list(raster.columns), ["Goede uren totaal", "10u", "11u"])
        self.assertEqual(raster.iloc[0]["Goede uren totaal"], 2)

    def test_weerbericht_noemt_mist_en_droog(self):
        tabel = maak_tabel([
            rij_dict(time="2026-11-10 10:00"),
            rij_dict(time="2026-11-10 11:00", visibility=800.0),
        ])
        tabel = self.scorer.voeg_score_toe(tabel)
        bericht = Advisor(self.drone, self.instellingen).weerbericht(tabel)
        self.assertIn("mist", bericht.iloc[0]["Mist en zicht"])
        self.assertIn("droog", bericht.iloc[0]["Neerslag"])

    def test_week_leeg_als_alles_nacht_is(self):
        tabel = maak_tabel([rij_dict(time="2026-11-10 03:00", is_day=0)])
        tabel = self.scorer.voeg_score_toe(tabel)
        self.assertTrue(Advisor(self.drone, self.instellingen).week(tabel).empty)


# --- Zonnetijden en vliegvenster ------------------------------------------

class TestVliegvenster(unittest.TestCase):
    def test_zon_tijden_met_marge_van_30_minuten(self):
        data = {"daily": {"time": ["2026-11-10"],
                          "sunrise": ["2026-11-10T07:42"],
                          "sunset": ["2026-11-10T17:04"]}}
        zon = WeatherClient(51.0, 3.0).zon_tijden(data)
        self.assertEqual(zon.iloc[0]["vliegen_van"], pd.Timestamp("2026-11-10 07:12"))
        self.assertEqual(zon.iloc[0]["vliegen_tot"], pd.Timestamp("2026-11-10 17:34"))

    def test_zon_tijden_ontbreken(self):
        self.assertIsNone(WeatherClient(51.0, 3.0).zon_tijden({}))

    def test_poolnacht_geeft_geen_daguren_en_geen_crash(self):
        data = {"daily": {"time": ["2026-11-10"], "sunrise": [None], "sunset": [None]}}
        client = WeatherClient(78.2, 15.6)
        zon = client.zon_tijden(data)
        uren = pd.date_range("2026-11-10 00:00", "2026-11-10 23:00", freq="h")
        tabel = pd.DataFrame({"time": uren})
        tabel["dag"] = tabel["time"].dt.date
        tabel["is_day"] = 1
        resultaat = client.pas_vliegvenster_toe(tabel, zon)
        self.assertEqual(resultaat["is_day"].sum(), 0)

    def test_vliegvenster_rondt_uren_correct_af(self):
        uren = pd.date_range("2026-11-10 05:00", "2026-11-10 20:00", freq="h")
        tabel = pd.DataFrame({"time": uren})
        tabel["dag"] = tabel["time"].dt.date
        tabel["is_day"] = 0
        zon = pd.DataFrame({
            "dag": [uren[0].date()],
            "vliegen_van": [pd.Timestamp("2026-11-10 07:12")],
            "vliegen_tot": [pd.Timestamp("2026-11-10 17:34")],
        })
        resultaat = WeatherClient(51.0, 3.0).pas_vliegvenster_toe(tabel, zon)
        mag = dict(zip(resultaat["time"].dt.hour, resultaat["is_day"]))
        self.assertEqual(mag[6], 0)   # eindigt om 07:00, voor 07:12
        self.assertEqual(mag[7], 1)   # 07:00-08:00 raakt het venster
        self.assertEqual(mag[17], 1)  # begint voor 17:34
        self.assertEqual(mag[18], 0)  # begint na 17:34


# --- Bestanden: log, instellingen, drones ---------------------------------

class TestBestanden(BasisTest):
    def test_log_heeft_vaste_kolommen_en_groeit(self):
        tabel = self.scorer.voeg_score_toe(maak_tabel([
            rij_dict(time="2026-11-10 10:00"), rij_dict(time="2026-11-10 11:00")]))
        with tempfile.TemporaryDirectory() as map_:
            pad = os.path.join(map_, "log.csv")
            rapport = Report(self.drone, "Testplaats", 0.7)
            rapport.sla_op(tabel, pad)
            rapport.sla_op(tabel, pad)
            log = pd.read_csv(pad)
        self.assertEqual(list(log.columns),
                         LOG_KOLOMMEN + ["opgehaald_op", "locatie", "drone"])
        self.assertEqual(len(log), 4)

    def test_settings_standaard_als_bestand_ontbreekt(self):
        with tempfile.TemporaryDirectory() as map_:
            s = laad_settings(os.path.join(map_, "bestaat_niet.json"))
        self.assertEqual(s, STANDAARD)

    def test_settings_overschrijft_alleen_opgegeven_velden(self):
        with tempfile.TemporaryDirectory() as map_:
            pad = os.path.join(map_, "s.json")
            with open(pad, "w", encoding="utf-8") as f:
                json.dump({"marge": 0.5}, f)
            s = laad_settings(pad)
        self.assertEqual(s["marge"], 0.5)
        self.assertEqual(s["start_uur"], STANDAARD["start_uur"])

    def test_settings_met_kapot_bestand(self):
        with tempfile.TemporaryDirectory() as map_:
            pad = os.path.join(map_, "kapot.json")
            with open(pad, "w", encoding="utf-8") as f:
                f.write("{ dit is geen json")
            s = laad_settings(pad)
        self.assertEqual(s, STANDAARD)

    def test_laad_drone(self):
        with tempfile.TemporaryDirectory() as map_:
            pad = os.path.join(map_, "drones.json")
            with open(pad, "w", encoding="utf-8") as f:
                json.dump({"Mini": {"max_wind": 12, "min_temp": -10, "max_temp": 40}}, f)
            drone = laad_drone(pad, "Mini")
            onbekend = laad_drone(pad, "Onbekend")
            ontbreekt = laad_drone(os.path.join(map_, "nee.json"), "Mini")
        self.assertEqual((drone.naam, drone.max_wind, drone.min_temp, drone.max_temp),
                         ("Mini", 12, -10, 40))
        self.assertIsNone(onbekend)
        self.assertIsNone(ontbreekt)


# --- Plaatsen zoeken (zonder internet, met nep-antwoorden) ----------------

class NepAntwoord:
    def __init__(self, data):
        self._data = data

    def raise_for_status(self):
        pass

    def json(self):
        return self._data


class TestGeocoder(unittest.TestCase):
    def test_resultaten_worden_omgezet(self):
        data = {"results": [{"name": "Gent", "admin1": "Vlaanderen", "country": "België",
                             "latitude": 51.05, "longitude": 3.72}]}
        with mock.patch.object(geocoding.requests, "get", return_value=NepAntwoord(data)):
            resultaten = Geocoder().zoek("Gent")
        self.assertEqual(resultaten, [{"label": "Gent, Vlaanderen, België",
                                       "latitude": 51.05, "longitude": 3.72}])

    def test_niets_gevonden_geeft_lege_lijst(self):
        with mock.patch.object(geocoding.requests, "get", return_value=NepAntwoord({})):
            self.assertEqual(Geocoder().zoek("xqzv"), [])

    def test_geen_internet_geeft_none(self):
        fout = requests.exceptions.ConnectionError("geen internet")
        with mock.patch.object(geocoding.requests, "get", side_effect=fout):
            self.assertIsNone(Geocoder().zoek("Gent"))

    def test_te_korte_naam_doet_geen_aanvraag(self):
        with mock.patch.object(geocoding.requests, "get",
                               side_effect=AssertionError("mag niet gebeld worden")):
            self.assertEqual(Geocoder().zoek("a"), [])


if __name__ == "__main__":
    unittest.main()
    
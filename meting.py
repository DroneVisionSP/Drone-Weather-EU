from settings import laad_settings
from drone import laad_drone
from locations import laad_locaties
from weather_client import WeatherClient
from flight_scorer import FlightScorer
from report import Report

LOCATIE = "Brugge"


def main():
    instellingen = laad_settings("instellingen.json")

    drone = laad_drone("drones.json", instellingen["drone"])
    if drone is None:
        return

    locaties = laad_locaties("locations.json")
    if locaties is None:
        return

    if LOCATIE not in locaties:
        print(f"Locatie '{LOCATIE}' staat niet in locations.json.")
        return

    gegevens = locaties[LOCATIE]
    weer = WeatherClient(gegevens["latitude"], gegevens["longitude"])
    scorer = FlightScorer(drone, instellingen)
    rapport = Report(drone, LOCATIE, instellingen["marge"])

    tabel = weer.haal_tabel()
    if tabel is None:
        print("Geen weerdata, er is niets opgeslagen.")
        return

    tabel = scorer.voeg_score_toe(tabel)
    rapport.sla_op(tabel, "log.csv")
    print(f"Meting opgeslagen: {LOCATIE}, {drone.naam}, {len(tabel)} uren.")


if __name__ == "__main__":
    main()
    
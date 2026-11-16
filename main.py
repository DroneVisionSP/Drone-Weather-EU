from settings import laad_settings
from drone import laad_drone, laad_drone_namen, kies_drone
from locations import laad_locaties, kies_locatie
from weather_client import WeatherClient
from flight_scorer import FlightScorer
from report import Report


def main():
    instellingen = laad_settings("instellingen.json")

    namen = laad_drone_namen("drones.json")
    if namen is None:
        return

    drone_naam = kies_drone(namen, instellingen["drone"])
    drone = laad_drone("drones.json", drone_naam)
    if drone is None:
        return

    locaties = laad_locaties("locations.json")
    if locaties is None:
        return

    locatie_naam = kies_locatie(locaties)
    gegevens = locaties[locatie_naam]

    weer = WeatherClient(gegevens["latitude"], gegevens["longitude"])
    scorer = FlightScorer(drone, instellingen)
    rapport = Report(drone, locatie_naam, instellingen["marge"])

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
    rapport.maak_dagoverzicht(tabel)
    rapport.toon()


if __name__ == "__main__":
    main()
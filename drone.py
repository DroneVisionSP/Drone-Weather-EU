import json


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


def laad_drone_namen(bestand):
    try:
        with open(bestand, encoding="utf-8") as f:
            return list(json.load(f).keys())
    except FileNotFoundError:
        print(f"Bestand {bestand} niet gevonden.")
        return None
    except json.JSONDecodeError:
        print(f"Er zit een fout in {bestand}.")
        return None


def kies_drone(namen, standaard):
    print("\nKies een drone (Enter = " + standaard + "):")
    for nummer, naam in enumerate(namen, start=1):
        print(f"  {nummer}. {naam}")

    while True:
        invoer = input("Nummer: ").strip()
        if invoer == "":
            return standaard if standaard in namen else namen[0]
        try:
            keuze = int(invoer)
        except ValueError:
            print("Typ een getal.")
            continue
        if 1 <= keuze <= len(namen):
            return namen[keuze - 1]
        print(f"Kies een getal tussen 1 en {len(namen)}.")
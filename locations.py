import json


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
        
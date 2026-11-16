import json

STANDAARD = {
    "drone": "Mini 5 Pro",
    "start_uur": 10,
    "eind_uur": 16,
    "marge": 0.7,
    "max_regen": 0.1,
    "min_zicht": 1000,
    "twijfel_zicht": 5000,
    "temp_marge": 5,
    "regenkans": 50,
}


def laad_settings(bestand):
    instellingen = dict(STANDAARD)
    try:
        with open(bestand, encoding="utf-8") as f:
            instellingen.update(json.load(f))
    except FileNotFoundError:
        print(f"{bestand} niet gevonden, standaardinstellingen worden gebruikt.")
    except json.JSONDecodeError:
        print(f"Er zit een fout in {bestand}, standaardinstellingen worden gebruikt.")
    return instellingen
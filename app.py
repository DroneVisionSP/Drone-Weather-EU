def toon_weer():
    from main import main
    main()


def snelle_meting():
    from meting import main
    main()


def analyse_verschuiving():
    from analyse import main
    main()


def analyse_betrouwbaarheid():
    from betrouwbaarheid import main
    main()


MENU = [
    ("Weer bekijken en opslaan", toon_weer),
    ("Snelle meting (Brugge, zonder grafieken)", snelle_meting),
    ("Analyse: hoe verschuift de voorspelling?", analyse_verschuiving),
    ("Analyse: hoe betrouwbaar is de voorspelling?", analyse_betrouwbaarheid),
]


def toon_menu():
    print("\n=== Vliegweer-assistent ===")
    for nummer, (omschrijving, _) in enumerate(MENU, start=1):
        print(f"  {nummer}. {omschrijving}")
    print("  0. Stoppen")


def main():
    while True:
        toon_menu()
        invoer = input("Keuze: ").strip()

        if invoer == "0":
            print("Tot de volgende vlucht!")
            return

        try:
            keuze = int(invoer)
        except ValueError:
            print("Typ een getal.")
            continue

        if 1 <= keuze <= len(MENU):
            MENU[keuze - 1][1]()
        else:
            print(f"Kies een getal tussen 0 en {len(MENU)}.")


if __name__ == "__main__":
    main()
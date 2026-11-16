import requests


class Geocoder:
    URL = "https://geocoding-api.open-meteo.com/v1/search"

    def zoek(self, naam, aantal=8):
        naam = naam.strip()
        if len(naam) < 2:
            return []

        parameters = {
            "name": naam,
            "count": aantal,
            "language": "nl",
            "format": "json",
        }
        try:
            antwoord = requests.get(self.URL, params=parameters, timeout=10)
            antwoord.raise_for_status()
            data = antwoord.json()
        except requests.exceptions.RequestException as fout:
            print("Kon plaats niet zoeken:", fout)
            return None

        resultaten = []
        for item in data.get("results", []):
            delen = [item.get("name"), item.get("admin1"), item.get("country")]
            label = ", ".join(deel for deel in delen if deel)
            resultaten.append({
                "label": label,
                "latitude": item["latitude"],
                "longitude": item["longitude"],
            })
        return resultaten
    
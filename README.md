# Vliegweer-assistent 🚁

Een hulpmiddel dat toont wanneer het weer geschikt is om met een drone te vliegen.
De app beoordeelt elk uur van de komende 7 dagen op wind, temperatuur, mist en neerslag,
rekening houdend met de limieten van de gekozen drone.

> **Geen officieel vliegadvies.** Controleer altijd de omstandigheden ter plaatse en de
> regels van je land (luchtruim, no-flyzones, natuurgebieden) voor je opstijgt.

## Functies

- Keuze uit 12 DJI-drones of een eigen drone (naam, windlimiet, temperatuurbereik).
- Vier manieren om een plek te kiezen: uit de lijst (23 Belgische steden en 37 Europese
  hoofdsteden, je kunt typen om te zoeken), plaats zoeken (wereldwijd), op de kaart klikken
  of coördinaten invoeren.
- Vliegvenster van 30 minuten voor zonsopgang tot 30 minuten na zonsondergang.
- Beoordeling per uur: 🟢 goed, 🟡 twijfelachtig, 🔴 niet vliegen. De kleur komt nooit alleen,
  er staat altijd ook een icoon en tekst bij.
- Advies bovenaan, kerncijfers, weekoverzicht, weerbericht per dag, grafieken en een tabel met alle uren.
- Instelbare voorkeursuren en twijfelgrens.
- Delen via de URL: de gekozen drone en plaats staan in de link.

### Tabs

| Tab | Inhoud |
|---|---|
| Overzicht | Week in één oogopslag, vliegbare uren per dag, beste uur per dag |
| Europa | Kaart van Europa met het weer nu per hoofdstad, klik voor de uurtabel van die stad of zoek elke plaats ter wereld |
| Weerbericht | Per dag en per factor |
| Per dag | Uurbalk, reden per uur, gouden uur, bewolking, mistrisico, wind op 80 en 120 m, Kp-waarschuwing |
| Grafieken | Vliegbare uren en wind |
| Alle uren | Volledige uurtabel |
| Vergelijken | 2 of 3 plaatsen met dezelfde drone, of 2 of 3 drones op dezelfde plek |
| Logboek | Eigen vluchten bijhouden, downloaden en weer inladen |
| Export en regels | Agenda-bestand (.ics), csv, links naar droneregels |
| Uitleg, Over | Berekening, bronnen, privacy |

Het programma op je pc (geplande metingen, groeiend logboek, analyses van verschuiving en
betrouwbaarheid, vergelijking met gemeten weer) staat los van de webapp.

## Installatie

Vereist Python 3.10 of nieuwer.

```bash
pip install -r requirements.txt
streamlit run web_app.py
```

`requirements.txt` bevat `streamlit` (1.30 of nieuwer, nodig voor het delen via de URL),
`pandas`, `matplotlib`, `folium`, `streamlit-folium` en `requests`.

## Projectstructuur

| Bestand | Doel |
|---|---|
| `web_app.py` | De Streamlit-webapp |
| `extras.py` | Tabs Europa, Per dag, Vergelijken, Logboek en Export |
| `stijl.py` | Kleuren, kopbalk, adviesblok en cijfertegels |
| `achtergrond.py` | Banner en uitleg over weer en drones |
| `advies.py` | Weekadvies, uurtabel en weerbericht |
| `flight_scorer.py` | Score per uur |
| `weather_client.py` | Weerdata en zonnetijden ophalen (Open-Meteo) |
| `geocoding.py` | Plaatsnamen zoeken |
| `drone.py`, `locations.py`, `settings.py` | Drones, locaties en instellingen laden |
| `drones.json` | De dronelijst |
| `locations.json` | De Belgische plaatsenlijst (de Europese hoofdsteden staan in `extras.py`) |
| `instellingen.json` | Standaarddrone, uren en marges |
| `meting.py` | Geplande metingen (via de Taakplanner) |
| `controleer_locaties.py` | Controleert de coördinaten in `locations.json` |
| `.streamlit/config.toml` | Kleurenthema |
| `requirements.txt` | Benodigde pakketten |

## Drones

Waarden komen uit de officiële specificaties van DJI of van winkels en databanken die ze overnemen.
Waar bronnen elkaar tegenspreken, is de voorzichtigste waarde gebruikt.

| Drone | Max. wind (m/s) | Temperatuur (°C) |
|---|---|---|
| Mini 5 Pro | 12 | -10 tot 40 |
| Mini 4 Pro | 10,7 | -10 tot 40 |
| Mini 3 Pro | 10,7 | -10 tot 40 |
| Mini 3 | 10,7 | -10 tot 40 |
| Mini 4K | 10,7 | 0 tot 40 |
| Air 3 | 12 | -10 tot 40 |
| Air 3S | 12 | -10 tot 40 |
| Mavic 3 Pro | 12 | -10 tot 40 |
| Mavic 4 Pro | 12 | -10 tot 40 |
| Neo 2 | 10,7 | -10 tot 40 |
| Inspire 3 | 12 | -20 tot 40 |
| Matrice 4TD | 12 | -20 tot 50 |

Opmerkingen:
- **Mini 4K:** bronnen geven -10 °C of 0 °C. Er is 0 °C gebruikt. -10 °C hoort bij de afstandsbediening.
- **Neo 2:** de originele Neo heeft maar 8 m/s.
- **Inspire 3:** 12 m/s bij opstijgen en landen, 14 m/s tijdens de vlucht. Er is 12 gebruikt.

Een drone toevoegen: voeg een blok toe aan `drones.json` met `max_wind`, `min_temp` en `max_temp`.

## Locaties

`locations.json` bevat 23 Belgische steden: Brugge, Oostende en Antwerpen vooraan, daarna alle
Vlaamse centrumsteden, Brussel en de grootste Waalse steden (alfabetisch). `extras.py` voegt
37 Europese hoofdsteden toe. Elke andere plaats ter wereld vind je via "Plaats zoeken" of in
de tab Europa.

Coördinaten van de Belgische lijst controleren:

```bash
python controleer_locaties.py
```

De coördinaten van de Europese hoofdsteden zijn uit het geheugen overgenomen. Een afwijking van
een paar honderd meter is niet erg, een echte fout wel.

## Metingen

Houd `LOCATIES` in `meting.py` bij 1 tot 3 plaatsen. Elke meting doet per plaats een aanvraag
en schrijft 168 rijen weg. Met veel plaatsen groeit het logboek snel en loop je tegen de limieten
van het gratis gebruik aan. De lijsten in de app zijn alleen voor de keuze.

## Hoe wordt de score berekend?

Elk uur wordt voor vijf factoren beoordeeld. Het ergste oordeel telt.

1. **Nacht:** buiten het vliegvenster wordt niet gevlogen.
2. **Wind:** windstoten boven de limiet van de drone zijn "niet vliegen". Boven de twijfelgrens
   (standaard een deel van de limiet) is het "twijfelachtig".
3. **Temperatuur:** buiten het werkbereik is het "niet vliegen", dicht bij de grenzen "twijfelachtig".
4. **Mist en zicht:** weinig zicht of een mistcode is "niet vliegen", nevel is "twijfelachtig".
5. **Neerslag:** veel regen, onweer, sneeuw of ijzel is "niet vliegen". Lichte neerslag of een hoge
   regenkans is "twijfelachtig".

De drempels voor zicht, neerslag en temperatuurmarge zijn voorzichtige eigen keuzes, geen regels
van de fabrikant. Ze staan in `instellingen.json`.

De kaart in de tab Europa is een momentopname van nu en gebruikt alleen wind, temperatuur en neerslag.
Wind op 80 en 120 m, mistrisico en de Kp-index in de tab Per dag tellen niet mee in de score.

## Beperkingen

- De app kent de luchtvaartregels niet: geen luchtruim, no-flyzones of natuurgebieden.
- Lokale wind (gebouwen, bomen, kust) kan sterk afwijken van het weermodel.
- Mist is plaatselijk en wordt door modellen soms gemist.
- Voor plaatsen met poolnacht of middernachtzon kan geen vliegvenster bepaald worden.
- Het logboek in de app bestaat alleen zolang de pagina openstaat. Download het om het te bewaren.

## Tests

```bash
python -m unittest -v
```

De tests gebruiken je JSON-bestanden niet.

## Online zetten

Zet het project op GitHub (zonder je logbestanden) en kies op share.streamlit.io je repository
en `web_app.py`. Zorg dat `requirements.txt` in de hoofdmap staat.

## Bronnen en privacy

- Weerdata, zonnetijden en plaatsnamen: [Open-Meteo.com](https://open-meteo.com) (CC BY 4.0).
- Geomagnetische activiteit: NOAA Space Weather Prediction Center.
- Kaart: © OpenStreetMap-bijdragers.
- Dronespecificaties: fabrikanten, handmatig overgenomen.

De app slaat zelf geen persoonsgegevens, locaties of zoekopdrachten op. Coördinaten en zoektermen
worden wel naar Open-Meteo gestuurd. Het platform waarop de app draait kan eigen logbestanden bijhouden.

## Versie
1.2

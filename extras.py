"""Extra onderdelen voor de Vliegweer-assistent: uurbalk per dag, gouden uur, wolken,
mistrisico, wind op hoogte, Kp-index, vergelijken, vluchtlogboek en export."""
import hashlib
import html
import json
from datetime import datetime, timedelta, timezone
from urllib.parse import quote

import pandas as pd
import requests
import streamlit as st

from advies import Advisor
from drone import laad_drone
from flight_scorer import FlightScorer
from stijl import FONT, KLEUR

SCORE_KLEUR = {"goed": KLEUR["goed"], "twijfelachtig": KLEUR["twijfel"],
               "niet vliegen": KLEUR["niet"], "nacht": "#9AA5B1"}
TEKST_KLEUR = {"goed": "#FFFFFF", "twijfelachtig": "#3D2A00",
               "niet vliegen": "#FFFFFF", "nacht": "#FFFFFF"}
ICOON = {"goed": "🟢", "twijfelachtig": "🟡", "niet vliegen": "🔴", "nacht": "🌙"}

EXTRA_URL = "https://api.open-meteo.com/v1/forecast"
KP_URL = "https://services.swpc.noaa.gov/products/noaa-planetary-k-index-forecast.json"


# ---------------------------------------------------------------- extra weerdata
def _haal_extra(latitude, longitude):
    r = requests.get(EXTRA_URL, params={
        "latitude": latitude, "longitude": longitude,
        "hourly": ("cloud_cover,temperature_2m,dew_point_2m,relative_humidity_2m,"
                   "wind_speed_80m,wind_speed_120m,wind_direction_10m"),
        "wind_speed_unit": "ms", "timezone": "auto", "forecast_days": 7,
    }, timeout=15)
    r.raise_for_status()
    df = pd.DataFrame(r.json()["hourly"])
    df["time"] = pd.to_datetime(df["time"])
    return df


@st.cache_data(ttl=3600)
def _extra_gecached(latitude, longitude):
    try:
        return _haal_extra(latitude, longitude)
    except (requests.RequestException, KeyError, ValueError):
        raise RuntimeError("Geen extra weerdata")


def extra_weer(latitude, longitude):
    """Bewolking, dauwpunt, vocht en wind op hoogte. None bij een fout."""
    try:
        return _extra_gecached(latitude, longitude)
    except RuntimeError:
        return None


def mistrisico(temp, dauw, vocht):
    if pd.isna(temp) or pd.isna(dauw):
        return "onbekend"
    verschil = temp - dauw
    if verschil <= 1 and (pd.isna(vocht) or vocht >= 95):
        return "🔴 hoog"
    if verschil <= 2.5:
        return "🟡 verhoogd"
    return "🟢 laag"



# ---------------------------------------------------------------- profielen
PROFIELEN = {
    "Standaard": {},
    "Hobby": {"marge": 0.8, "min_zicht": 1000, "twijfel_zicht": 3000, "max_regen": 0.5,
              "regenkans": 50, "temp_marge": 3},
    "Fotograaf": {"marge": 0.75, "min_zicht": 3000, "twijfel_zicht": 8000, "max_regen": 0.1,
                  "regenkans": 30, "temp_marge": 5, "bewolking_max": 80},
    "Inspectie": {"marge": 0.6, "min_zicht": 2000, "twijfel_zicht": 5000, "max_regen": 0.1,
                  "regenkans": 30, "temp_marge": 5},
}
SCORE_SLEUTELS = ("min_zicht", "twijfel_zicht", "max_regen", "regenkans", "temp_marge")


def profiel_drempels(naam):
    """De drempels die in keuzes terechtkomen (de twijfelgrens staat in de schuif)."""
    return {k: v for k, v in PROFIELEN[naam].items() if k in SCORE_SLEUTELS}


def profiel_marge(naam, standaard):
    return PROFIELEN[naam].get("marge", standaard)


def profiel_uitleg(naam):
    p = PROFIELEN[naam]
    if not p:
        return "Gebruikt de waarden uit instellingen.json."
    tekst = (f"Twijfelgrens {int(p['marge'] * 100)}% van de windlimiet. Zicht onder "
             f"{p['min_zicht']} m is niet vliegen. Regen vanaf {p['max_regen']} mm per uur is "
             f"niet vliegen. Regenkans vanaf {p['regenkans']}% is twijfelachtig.")
    if "bewolking_max" in p:
        tekst += (f" Bewolking boven {p['bewolking_max']}% krijgt een opmerking "
                  "(telt niet mee in de score).")
    return tekst


# ---------------------------------------------------------------- windrichting en kou
KOU_GRENS = 10
_KOMPAS = ["N", "NO", "O", "ZO", "Z", "ZW", "W", "NW"]


def kompas(graden):
    if pd.isna(graden):
        return ""
    return _KOMPAS[int((graden + 22.5) // 45) % 8]


def richting_tekst(graden):
    if pd.isna(graden):
        return ""
    return f"{kompas(graden)} ({graden:.0f}°)"


def kou_tekst(tabel, start=0, eind=23, dag=None):
    """Waarschuwing als het tijdens vliegbare uren kouder is dan KOU_GRENS."""
    t = tabel[tabel["score"].isin(["goed", "twijfelachtig"])]
    uur = t["time"].dt.hour
    t = t[(uur >= start) & (uur <= eind)]
    if dag is not None:
        t = t[t["dag"] == dag]
    koud = t[t["temperature_2m"] < KOU_GRENS]
    if koud.empty:
        return None
    laagste = koud["temperature_2m"].min()
    raad = (f"Onder ongeveer {KOU_GRENS} °C verliezen batterijen merkbaar vliegtijd, ook binnen "
            "het werkbereik van de drone. Houd batterijen warm, vlieg korter en land op tijd.")
    if dag is not None:
        return f"🥶 Koud: tot {laagste:.0f} °C tijdens je vliegmomenten. {raad}"
    koude_dagen, alle_dagen = koud["dag"].nunique(), t["dag"].nunique()
    wanneer = (f"op alle {alle_dagen} dagen" if koude_dagen == alle_dagen
               else f"op {koude_dagen} van de {alle_dagen} dagen")
    return (f"🥶 Koud: {wanneer} met vliegmomenten daalt de temperatuur onder {KOU_GRENS} °C "
            f"(laagste {laagste:.0f} °C). {raad}")


def _blokken(tijden):
    """Aaneengesloten uren omzetten naar (begin, einde)-blokken."""
    blokken, begin, vorige = [], None, None
    for t in sorted(tijden):
        if begin is None:
            begin = vorige = t
        elif t - vorige == timedelta(hours=1):
            vorige = t
        else:
            blokken.append((begin, vorige + timedelta(hours=1)))
            begin = vorige = t
    if begin is not None:
        blokken.append((begin, vorige + timedelta(hours=1)))
    return blokken


# ---------------------------------------------------------------- Kp-index
@st.cache_data(ttl=3600)
def _kp_data():
    r = requests.get(KP_URL, timeout=10)
    r.raise_for_status()
    data = r.json()
    if data and isinstance(data[0], list):
        kop = data[0]
        rijen = [dict(zip(kop, x)) for x in data[1:]]
    else:
        rijen = data
    uit = []
    for x in rijen:
        tijd = pd.to_datetime(x["time_tag"], utc=True).tz_convert(None)
        uit.append((tijd, float(x["kp"])))
    return uit


def kp_komende_72u():
    """Hoogste verwachte Kp in de komende 72 uur, of None bij een fout."""
    try:
        reeks = _kp_data()
    except (requests.RequestException, KeyError, ValueError, TypeError):
        return None
    nu = pd.Timestamp(datetime.now(timezone.utc).replace(tzinfo=None))
    komend = [k for t, k in reeks if nu <= t <= nu + pd.Timedelta(hours=72)]
    return max(komend) if komend else None


# ---------------------------------------------------------------- tab "Per dag"
def uurbalk(rijen):
    delen = [f'<div style="display:flex;gap:3px;flex-wrap:wrap;font-family:{FONT};">']
    for _, r in rijen.iterrows():
        score = r["score"]
        kleur = SCORE_KLEUR.get(score, "#9AA5B1")
        tekst = TEKST_KLEUR.get(score, "#FFFFFF")
        icoon = ICOON.get(score, "")
        titel = html.escape(f"{score}: {r['reden']}")
        uur = r["time"].strftime("%H")
        delen.append(
            f'<div title="{titel}" style="flex:1 1 38px;min-width:38px;text-align:center;'
            f'background:{kleur};color:{tekst};border-radius:6px;padding:5px 0;'
            f'font-size:0.8rem;font-weight:600;">{uur}<br>{icoon}</div>')
    delen.append("</div>")
    return "".join(delen)


def zon_tekst(zon, dag):
    if zon is None:
        return None
    rij = zon[zon["dag"] == dag]
    if rij.empty:
        return None
    van, tot = rij.iloc[0]["vliegen_van"], rij.iloc[0]["vliegen_tot"]
    if pd.isna(van) or pd.isna(tot):
        return None
    opkomst = van + timedelta(minutes=30)
    onder = tot - timedelta(minutes=30)
    uur = timedelta(hours=1)
    return (f"🌅 Zonsopgang {opkomst:%H:%M}, gouden uur tot {opkomst + uur:%H:%M} · "
            f"🌇 gouden uur vanaf {onder - uur:%H:%M}, zonsondergang {onder:%H:%M}")


def toon_dag(tabel, zon, dag, drone, extra, profiel=None):
    rijen = tabel[tabel["dag"] == dag]

    kp = kp_komende_72u()
    if kp is not None and kp >= 5:
        st.warning(f"Hoge geomagnetische activiteit verwacht (Kp {kp:g}). "
                   "Dat kan de gps-ontvangst van je drone storen.")
    elif kp is not None and kp >= 4:
        st.warning(f"Verhoogde geomagnetische activiteit verwacht (Kp {kp:g}). "
                   "Let op je gps-signaal.")

    kou = kou_tekst(tabel, dag=dag)
    if kou:
        st.warning(kou)

    with st.container(border=True):
        st.markdown("**Uur per uur**")
        st.markdown(uurbalk(rijen), unsafe_allow_html=True)
        st.caption("🟢 goed · 🟡 twijfelachtig · 🔴 niet vliegen · 🌙 nacht. "
                   "Houd de muis boven een blok voor de reden.")
        tekst = zon_tekst(zon, dag)
        if tekst:
            st.markdown(tekst)
            st.caption("Het gouden uur is hier bij benadering het uur na zonsopgang "
                       "en het uur voor zonsondergang.")

    with st.container(border=True):
        st.markdown("**Waarom niet goed?**")
        slecht = rijen[rijen["score"].isin(["niet vliegen", "twijfelachtig"])]
        if slecht.empty:
            st.success("Geen bezwaren op deze dag.")
        for _, r in slecht.iterrows():
            st.markdown(f"{ICOON[r['score']]} **{r['time']:%H:%M}**: {r['reden']}")

    with st.container(border=True):
        st.markdown("**Wolken, mistrisico en wind op hoogte**")
        if extra is None:
            st.info("Extra weergegevens zijn nu niet beschikbaar.")
            return
        uren = rijen[rijen["score"] != "nacht"][["time", "wind_speed_10m", "score"]]
        d = uren.merge(extra, on="time", how="left")
        if d.empty or d["wind_speed_80m"].isna().all():
            st.info("Geen extra gegevens voor deze dag.")
            return
        tonen = pd.DataFrame({
            "Tijd": d["time"].dt.strftime("%H:%M"),
            "Bewolking (%)": d["cloud_cover"],
            "Wind 10 m (m/s)": d["wind_speed_10m"].round(1),
            "Wind uit": [richting_tekst(g) for g in d["wind_direction_10m"]],
            "Wind 80 m (m/s)": d["wind_speed_80m"].round(1),
            "Wind 120 m (m/s)": d["wind_speed_120m"].round(1),
            "Mistrisico": [mistrisico(t, dp, rh) for t, dp, rh in
                           zip(d["temperature_2m"], d["dew_point_2m"],
                               d["relative_humidity_2m"])],
        })
        st.dataframe(tonen, hide_index=True)
        top = d["wind_speed_120m"].max()
        if top > drone.max_wind:
            st.warning(f"Op 120 m is de gemiddelde wind tot {top:.1f} m/s, boven de limiet "
                       f"van {drone.max_wind:g} m/s. Vlieg je hoog, houd daar rekening mee.")

        bew_max = (profiel or {}).get("bewolking_max")
        goed = d[d["score"] == "goed"]
        if bew_max is not None and not goed.empty:
            te_veel = int((goed["cloud_cover"] > bew_max).sum())
            if te_veel:
                st.info(f"Profiel: {te_veel} van de {len(goed)} goede uren hebben bewolking "
                        f"boven {bew_max}%. Het licht is dan vaak vlak.")
            else:
                st.caption(f"Profiel: alle goede uren hebben bewolking onder {bew_max}%.")

        st.caption("\"Wind uit\" is de richting waaruit de wind komt. Tip: vlieg bij veel wind "
                   "eerst tegen de wind in, dan heb je op de terugweg wind mee als de batterij "
                   "minder vol is. Met wind mee gaat de drone wel sneller. Wind op hoogte is een "
                   "gemiddelde, geen windstoot. Bewolking, wind op hoogte en mistrisico tellen "
                   "niet mee in de score.")


# ---------------------------------------------------------------- tab "Vergelijken"
def _goede_per_dag(tabel, drone, keuzes):
    tabel = FlightScorer(drone, keuzes).voeg_score_toe(tabel)
    week = Advisor(drone, keuzes).week(tabel)
    if week.empty:
        return pd.Series(dtype=int)
    return week.set_index("dag")["goed"]


def _toon_reeksen(reeksen, dag_label):
    if not reeksen:
        st.info("Niets om te tonen.")
        return
    df = pd.DataFrame(reeksen).fillna(0).astype(int)
    if df.empty:
        st.info("Geen toegestane uren gevonden.")
        return
    totaal = df.sum()
    df.index = [dag_label(d) for d in df.index]
    df.loc["Totaal"] = totaal
    st.dataframe(df)
    if totaal.max() == 0:
        st.info("Geen enkele keuze heeft goede uren.")
    elif (totaal == totaal.max()).sum() > 1:
        st.info(f"Gelijkspel: {int(totaal.max())} goede uren.")
    else:
        st.success(f"Meeste goede uren: {totaal.idxmax()} ({int(totaal.max())} uur).")
    st.caption("Aantal goede uren per dag, binnen je voorkeursuren.")


def toon_vergelijking(haal_alles, drone, keuzes, locaties, namen,
                      latitude, longitude, locatie_naam, dag_label):
    with st.container(border=True):
        st.markdown("**Plaatsen vergelijken** (met je gekozen drone)")
        lijst = list(locaties)
        standaard = [locatie_naam] if locatie_naam in lijst else lijst[:1]
        standaard += [p for p in lijst if p not in standaard][:1]
        keuze = st.multiselect("Kies 2 of 3 plaatsen", lijst, default=standaard,
                               max_selections=3, key="vergelijk_plaatsen")
        if len(keuze) < 2:
            st.info("Kies minstens twee plaatsen.")
        else:
            reeksen = {}
            for naam in keuze:
                try:
                    t, _ = haal_alles(locaties[naam]["latitude"], locaties[naam]["longitude"])
                except RuntimeError:
                    st.warning(f"Geen weerdata voor {naam}.")
                    continue
                reeksen[naam] = _goede_per_dag(t, drone, keuzes)
            _toon_reeksen(reeksen, dag_label)

    with st.container(border=True):
        st.markdown("**Drones vergelijken** (op je gekozen plek)")
        andere = [n for n in namen if n != drone.naam][:1]
        standaard = ([drone.naam] if drone.naam in namen else []) + andere
        keuze = st.multiselect("Kies 2 of 3 drones", namen, default=standaard,
                               max_selections=3, key="vergelijk_drones")
        if len(keuze) < 2:
            st.info("Kies minstens twee drones.")
        else:
            try:
                t, _ = haal_alles(latitude, longitude)
            except RuntimeError:
                st.warning("Geen weerdata voor deze plek.")
                return
            reeksen = {}
            for naam in keuze:
                d = laad_drone("drones.json", naam)
                if d is None:
                    continue
                reeksen[f"{naam} ({d.max_wind:g} m/s)"] = _goede_per_dag(t, d, keuzes)
            _toon_reeksen(reeksen, dag_label)


# ---------------------------------------------------------------- tab "Logboek"
LOG_KOLOMMEN = ["Datum", "Drone", "Plek", "Weer was", "Opmerking"]


def toon_logboek(namen):
    if "logboek" not in st.session_state:
        st.session_state["logboek"] = []

    with st.container(border=True):
        st.markdown("**Mijn vluchten**")
        with st.form("logboek_form", clear_on_submit=True):
            k1, k2 = st.columns(2)
            datum = k1.date_input("Datum")
            drone = k2.selectbox("Drone", namen)
            plek = st.text_input("Plek")
            weer = st.selectbox("Hoe was het weer echt?", ["Goed", "Twijfelachtig", "Slecht"])
            opmerking = st.text_input("Opmerking (wind, zicht, ...)")
            if st.form_submit_button("Vlucht toevoegen"):
                st.session_state["logboek"].append({
                    "Datum": datum.isoformat(), "Drone": drone, "Plek": plek,
                    "Weer was": weer, "Opmerking": opmerking})

        df = pd.DataFrame(st.session_state["logboek"], columns=LOG_KOLOMMEN)
        if df.empty:
            st.info("Nog geen vluchten.")
        else:
            st.dataframe(df, hide_index=True)
            st.download_button("Logboek downloaden (CSV)",
                               df.to_csv(index=False).encode("utf-8"),
                               file_name="vluchtlogboek.csv", mime="text/csv")

        bestand = st.file_uploader("Eerder opgeslagen logboek inladen", type="csv")
        if bestand is not None and st.button("Logboek inladen"):
            try:
                ingelezen = pd.read_csv(bestand)
            except (ValueError, pd.errors.ParserError):
                st.error("Dit bestand kon niet worden gelezen.")
            else:
                if list(ingelezen.columns) != LOG_KOLOMMEN:
                    st.error("Dit is geen logboek van deze app (kolommen kloppen niet).")
                else:
                    st.session_state["logboek"] = ingelezen.fillna("").to_dict("records")
                    st.rerun()
        st.caption("Het logboek leeft alleen zolang de pagina openstaat. Download het om het "
                   "te bewaren en laad het de volgende keer weer in.")


# ---------------------------------------------------------------- tab "Export en regels"
def maak_ics(tabel, naam, start, eind):
    uur = tabel["time"].dt.hour
    goede = tabel[(tabel["score"] == "goed") & (uur >= start) & (uur <= eind)]
    blokken = _blokken(goede["time"])

    titel = f"Goed vliegweer: {naam}".replace(",", "\\,").replace(";", "\\;")
    nu = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    regels = ["BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//Vliegweer-assistent//NL"]
    for i, (a, b) in enumerate(blokken):
        regels += ["BEGIN:VEVENT",
                   f"UID:vliegweer-{a:%Y%m%dT%H%M}-{i}@vliegweer",
                   f"DTSTAMP:{nu}",
                   f"DTSTART:{a:%Y%m%dT%H%M%S}",
                   f"DTEND:{b:%Y%m%dT%H%M%S}",
                   f"SUMMARY:{titel}",
                   "END:VEVENT"]
    regels.append("END:VCALENDAR")
    return "\r\n".join(regels) + "\r\n", len(blokken)


def maak_samenvatting(tabel, drone, locatie_naam, start, eind, dag_label, extra=None):
    """Korte tekst met per dag de goede uren, om te delen."""
    richting = None
    if extra is not None and "wind_direction_10m" in extra:
        richting = extra.set_index("time")["wind_direction_10m"]

    regels = [f"Vliegweer {drone.naam} in {locatie_naam}"]
    for dag in tabel["dag"].unique():
        rijen = tabel[tabel["dag"] == dag]
        uur = rijen["time"].dt.hour
        goede = rijen[(rijen["score"] == "goed") & (uur >= start) & (uur <= eind)]
        kop = dag_label(dag).capitalize()
        if goede.empty:
            regels.append(f"{kop}: geen goede uren")
            continue
        langste = max(_blokken(goede["time"]), key=lambda blok: blok[1] - blok[0])
        deel = (f"{kop}: {len(goede)} goede uren, {langste[0]:%H:%M} tot {langste[1]:%H:%M}, "
                f"windstoten max {goede['wind_gusts_10m'].max():.0f} m/s")
        if richting is not None and langste[0] in richting.index:
            graden = richting.loc[langste[0]]
            if not pd.isna(graden):
                deel += f", wind uit {kompas(graden)}"
        laagste = goede["temperature_2m"].min()
        if laagste < KOU_GRENS:
            deel += f", koud ({laagste:.0f} °C)"
        regels.append(deel)
    regels.append("Geen officieel vliegadvies.")
    return "\n".join(regels)


def toon_samenvatting(tabel, drone, locatie_naam, start, eind, dag_label, extra):
    with st.container(border=True):
        st.markdown("**Samenvatting om te delen**")
        tekst = maak_samenvatting(tabel, drone, locatie_naam, start, eind, dag_label, extra)
        st.code(tekst, language=None)
        st.link_button("💬 Deel via WhatsApp", "https://wa.me/?text=" + quote(tekst))
        st.caption("Kopieer de tekst met het icoontje rechtsboven in het blok, of open WhatsApp "
                   "met de knop. De tijden gelden voor de langste goede reeks van elke dag.")


def toon_export(tabel, drone, locatie_naam, start, eind):
    with st.container(border=True):
        st.markdown("**Exporteren**")
        ics, aantal = maak_ics(tabel, f"{drone.naam} in {locatie_naam}", start, eind)
        if aantal:
            st.download_button(f"📅 {aantal} vliegmomenten in je agenda (.ics)",
                               ics.encode("utf-8"), file_name="vliegmomenten.ics",
                               mime="text/calendar")
        else:
            st.info("Geen goede vliegmomenten om te exporteren.")
        kolommen = ["time", "temperature_2m", "wind_speed_10m", "wind_gusts_10m",
                    "precipitation", "visibility", "score", "reden"]
        st.download_button("📄 Alle uren (CSV)",
                           tabel[kolommen].to_csv(index=False).encode("utf-8"),
                           file_name="vliegweer_uren.csv", mime="text/csv")
        st.caption("Een pdf nodig? Kies in je browser Afdrukken en dan Opslaan als pdf.")

    with st.container(border=True):
        st.markdown("**Regels en kaarten**")
        st.link_button("Belgische droneregels en kaart met vliegzones", "https://www.droneguide.be")
        st.link_button("Europese droneregels (EASA)",
                       "https://www.easa.europa.eu/en/domains/drones-air-mobility")
        st.caption("Controleer altijd luchtruim, no-flyzones en lokale regels voor je opstijgt.")


# ---------------------------------------------------------------- tab "Europa"
_STEDEN = [
    ("Amsterdam", "Nederland", 52.3676, 4.9041), ("Athene", "Griekenland", 37.9838, 23.7275),
    ("Belgrado", "Servië", 44.7866, 20.4489), ("Berlijn", "Duitsland", 52.52, 13.405),
    ("Bern", "Zwitserland", 46.948, 7.4474), ("Boedapest", "Hongarije", 47.4979, 19.0402),
    ("Boekarest", "Roemenië", 44.4268, 26.1025), ("Bratislava", "Slowakije", 48.1486, 17.1077),
    ("Chisinau", "Moldavië", 47.0105, 28.8638), ("Dublin", "Ierland", 53.3498, -6.2603),
    ("Helsinki", "Finland", 60.1699, 24.9384), ("Kiev", "Oekraïne", 50.4501, 30.5234),
    ("Kopenhagen", "Denemarken", 55.6761, 12.5683), ("Lissabon", "Portugal", 38.7223, -9.1393),
    ("Ljubljana", "Slovenië", 46.0569, 14.5058), ("Londen", "Verenigd Koninkrijk", 51.5074, -0.1278),
    ("Luxemburg", "Luxemburg", 49.6116, 6.1319), ("Madrid", "Spanje", 40.4168, -3.7038),
    ("Nicosia", "Cyprus", 35.1856, 33.3823), ("Oslo", "Noorwegen", 59.9139, 10.7522),
    ("Parijs", "Frankrijk", 48.8566, 2.3522), ("Podgorica", "Montenegro", 42.4304, 19.2594),
    ("Praag", "Tsjechië", 50.0755, 14.4378), ("Reykjavik", "IJsland", 64.1466, -21.9426),
    ("Riga", "Letland", 56.9496, 24.1052), ("Rome", "Italië", 41.9028, 12.4964),
    ("Sarajevo", "Bosnië", 43.8563, 18.4131), ("Skopje", "Noord-Macedonië", 41.9981, 21.4254),
    ("Sofia", "Bulgarije", 42.6977, 23.3219), ("Stockholm", "Zweden", 59.3293, 18.0686),
    ("Tallinn", "Estland", 59.437, 24.7536), ("Tirana", "Albanië", 41.3275, 19.8187),
    ("Valletta", "Malta", 35.8989, 14.5146), ("Vilnius", "Litouwen", 54.6872, 25.2797),
    ("Warschau", "Polen", 52.2297, 21.0122), ("Wenen", "Oostenrijk", 48.2082, 16.3738),
    ("Zagreb", "Kroatië", 45.815, 15.9819),
]
EUROPA = {f"{s} ({l})": {"latitude": a, "longitude": b} for s, l, a, b in _STEDEN}


@st.cache_data(ttl=1800)
def _europa_gecached():
    try:
        namen = list(EUROPA)
        r = requests.get(EXTRA_URL, params={
            "latitude": ",".join(str(EUROPA[n]["latitude"]) for n in namen),
            "longitude": ",".join(str(EUROPA[n]["longitude"]) for n in namen),
            "current": "temperature_2m,wind_gusts_10m,precipitation,cloud_cover",
            "wind_speed_unit": "ms", "timezone": "auto"}, timeout=20)
        r.raise_for_status()
        data = r.json()
        if isinstance(data, dict):
            data = [data]
        return {naam: d["current"] for naam, d in zip(namen, data)}
    except (requests.RequestException, KeyError, ValueError, TypeError):
        raise RuntimeError("Geen Europese weerdata")


def _status_nu(c, drone, marge):
    wind, temp = c.get("wind_gusts_10m"), c.get("temperature_2m")
    regen = c.get("precipitation") or 0
    if wind is None or temp is None:
        return "onbekend", "geen gegevens"
    niet, twijfel = [], []
    if wind > drone.max_wind:
        niet.append(f"windstoten {wind:.1f} m/s")
    elif wind > drone.max_wind * marge:
        twijfel.append(f"windstoten {wind:.1f} m/s")
    if temp < drone.min_temp or temp > drone.max_temp:
        niet.append(f"temperatuur {temp:.0f} °C")
    if regen >= 1:
        niet.append(f"neerslag {regen:.1f} mm")
    elif regen > 0:
        twijfel.append(f"neerslag {regen:.1f} mm")
    if niet:
        return "niet vliegen", ", ".join(niet)
    if twijfel:
        return "twijfelachtig", ", ".join(twijfel)
    return "goed", "geen bezwaren nu"


def toon_europa(haal_alles, drone, keuzes, dag_label, zoek_plaats):
    import folium
    from streamlit_folium import st_folium

    try:
        nu = _europa_gecached()
    except RuntimeError:
        nu = None
        st.warning("De Europese weerkaart kon niet worden opgehaald.")

    with st.container(border=True):
        st.markdown("**Weerkaart Europa: nu, voor jouw drone**")
        kaart = folium.Map(location=[54, 15], zoom_start=4)
        rijen = []
        for naam, c in (nu or {}).items():
            status, reden = _status_nu(c, drone, keuzes["marge"])
            folium.CircleMarker(
                location=[EUROPA[naam]["latitude"], EUROPA[naam]["longitude"]],
                radius=9, color=SCORE_KLEUR.get(status, "#9AA5B1"), fill=True,
                fill_opacity=0.85, tooltip=naam,
                popup=folium.Popup(html.escape(f"{naam}: {status}, {reden}"), max_width=250),
            ).add_to(kaart)
            rijen.append({"Stad": naam, "Nu": f"{ICOON.get(status, '')} {status}",
                          "Temperatuur (°C)": c.get("temperature_2m"),
                          "Windstoten (m/s)": c.get("wind_gusts_10m"),
                          "Neerslag (mm)": c.get("precipitation"),
                          "Bewolking (%)": c.get("cloud_cover")})
        uit = st_folium(kaart, width=700, height=450, returned_objects=["last_object_clicked_tooltip"])
        klik = ((uit or {}).get("last_object_clicked_tooltip") or "").strip()
        if klik in EUROPA and klik != st.session_state.get("europa_laatste_klik"):
            st.session_state["europa_laatste_klik"] = klik
            st.session_state["europa_stad"] = klik
        st.caption("🟢 goed · 🟡 twijfelachtig · 🔴 niet vliegen. Dit is een momentopname van nu, "
                   "zonder zonsopgang en zonsondergang. Klik op een stad voor de uurtabel.")
        if rijen:
            with st.expander("Tabel van alle steden"):
                st.dataframe(pd.DataFrame(rijen), hide_index=True)

    with st.container(border=True):
        stad = st.selectbox("Kies een Europese hoofdstad (je kunt typen)", list(EUROPA),
                            key="europa_stad")
        naam, lat, lon = stad, EUROPA[stad]["latitude"], EUROPA[stad]["longitude"]
        zoekterm = st.text_input("Of zoek een andere plaats ter wereld", key="europa_zoek",
                                 placeholder="bijvoorbeeld Göteborg")
        if zoekterm.strip():
            try:
                resultaten = zoek_plaats(zoekterm)
            except RuntimeError:
                st.error("Zoeken is mislukt.")
                resultaten = []
            if resultaten:
                r = st.selectbox("Kies de juiste plaats", resultaten,
                                 format_func=lambda x: x["label"], key="europa_resultaat")
                naam, lat, lon = r["label"], r["latitude"], r["longitude"]
            else:
                st.warning("Geen plaats gevonden.")

    try:
        tabel, zon = haal_alles(lat, lon)
    except RuntimeError:
        st.error("Kon geen weerdata ophalen.")
        return
    tabel = FlightScorer(drone, keuzes).voeg_score_toe(tabel)
    advisor = Advisor(drone, keuzes)

    st.markdown(f"### {naam}")
    with st.container(border=True):
        st.markdown("**Vliegbare uren per dag**")
        uurtabel = advisor.uurtabel(tabel)
        if uurtabel.empty:
            st.info("Er zijn geen uren waarop vliegen mag.")
        else:
            uurtabel.index = [dag_label(d) for d in uurtabel.index]
            uurtabel.index.name = "Dag"
            st.dataframe(uurtabel)
    with st.container(border=True):
        st.markdown("**Weerbericht per dag**")
        bericht = advisor.weerbericht(tabel)
        if bericht.empty:
            st.info("Er zijn geen uren waarop vliegen mag.")
        else:
            dagen = bericht.pop("dag")
            bericht.insert(0, "Dag", [dag_label(d) for d in dagen])
            st.dataframe(bericht, hide_index=True)
    with st.expander("Alle uren"):
        st.dataframe(tabel[["time", "temperature_2m", "wind_speed_10m", "wind_gusts_10m",
                            "precipitation", "visibility", "score", "reden"]], hide_index=True)


# ---------------------------------------------------------------- keuze onthouden per bezoeker
# De keuze wordt in de localStorage van de browser van die bezoeker bewaard. Elke bezoeker heeft
# dus zijn eigen keuze, los van alle anderen. Er staat niets op de server.
BEWAAR_SLEUTEL = "vliegweer_keuze_v1"


def bewaar_lezen():
    """Haalt de bewaarde keuze op uit deze browser.

    None: de browser heeft nog niet geantwoord (de app herlaadt dan vanzelf).
    {} : niets bewaard, of bewaren is niet beschikbaar."""
    try:
        from streamlit_js_eval import streamlit_js_eval
    except ImportError:
        return {}
    js = ("(() => { try { return localStorage.getItem('" + BEWAAR_SLEUTEL + "') || ''; } "
          "catch (e) { return ''; } })()")
    ruw = streamlit_js_eval(js_expressions=js, key="bewaar_lezen")
    if ruw is None:
        return None
    try:
        data = json.loads(ruw) if ruw else {}
    except (ValueError, TypeError):
        data = {}
    return data if isinstance(data, dict) else {}


def pas_bewaard_toe(bewaard, namen, locaties, profielen):
    """Zet de bewaarde keuze klaar als startkeuze. Een link met drone en plaats wint."""
    st.session_state["ls_toegepast"] = True
    st.session_state["bewaard"] = dict(bewaard)
    if st.query_params.get("drone") in namen or st.query_params.get("plaats") in locaties:
        return
    if bewaard.get("drone") in namen:
        st.session_state["start_drone"] = bewaard["drone"]
        st.session_state["landing_drone"] = bewaard["drone"]
    if bewaard.get("plaats") in locaties:
        st.session_state["start_locatie"] = bewaard["plaats"]
        st.session_state["landing_locatie"] = bewaard["plaats"]
    if bewaard.get("profiel") in profielen:
        st.session_state["profiel_keuze"] = bewaard["profiel"]


def bewaar_schrijven(waarden):
    """Bewaart de keuze in de browser van deze bezoeker."""
    try:
        from streamlit_js_eval import streamlit_js_eval
    except ImportError:
        return
    tekst = json.dumps(waarden, sort_keys=True)
    sleutel = hashlib.md5(tekst.encode("utf-8")).hexdigest()[:10]
    js = ("(() => { try { localStorage.setItem('" + BEWAAR_SLEUTEL + "', "
          + json.dumps(tekst) + "); } catch (e) {} return 'ok'; })()")
    streamlit_js_eval(js_expressions=js, key=f"bewaar_schrijven_{sleutel}")
    
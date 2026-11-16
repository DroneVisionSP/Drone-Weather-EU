from datetime import timedelta
from urllib.parse import quote_plus

import streamlit as st
import streamlit.components.v1 as components
import folium
from streamlit_folium import st_folium
import matplotlib.pyplot as plt
import pandas as pd

from settings import laad_settings
from drone import Drone, laad_drone, laad_drone_namen
from locations import laad_locaties
from weather_client import WeatherClient
from flight_scorer import FlightScorer
from advies import Advisor
from geocoding import Geocoder
from achtergrond import banner_html, BANNER_HOOGTE, WEER_INFO
from stijl import (pas_stijl_toe, hero, advies_kaart, kpi_kaart, stijl_grafiek,
                   KLEUR, VERSIE)
from extras import (extra_weer, toon_dag, toon_vergelijking, toon_logboek,
                    toon_export, toon_europa, EUROPA, PROFIELEN, profiel_drempels,
                    profiel_marge, profiel_uitleg, kou_tekst, toon_samenvatting,
                    bewaar_lezen, pas_bewaard_toe, bewaar_schrijven)

st.set_page_config(
    page_title="Vliegweer-assistent",
    page_icon="🚁",
    initial_sidebar_state="expanded",
    menu_items={
        "Get help": None,
        "Report a bug": None,
        "About": "Vliegweer-assistent: een hulpmiddel, geen officieel vliegadvies.",
    },
)
pas_stijl_toe()

DAGEN = ["maandag", "dinsdag", "woensdag", "donderdag", "vrijdag", "zaterdag", "zondag"]
ICONEN = {"goed": "🟢 Goed", "twijfelachtig": "🟡 Twijfelachtig", "niet vliegen": "🔴 Niet vliegen"}

BRONNEN = ("Weerdata en zonnetijden: Open-Meteo.com (CC BY 4.0). Plaatsnamen: Open-Meteo Geocoding. "
           "Kaart: © OpenStreetMap-bijdragers. Geen officieel vliegadvies.")


def dag_label(dag):
    return f"{DAGEN[dag.weekday()]} {dag.strftime('%d/%m')}"


def nacht_tekst(zon, dag):
    rij = zon[zon["dag"] == dag]
    if rij.empty:
        return ""
    van = rij.iloc[0]["vliegen_tot"]
    if pd.isna(van):
        return "geen zonsopgang of zonsondergang"
    volgende = zon[zon["dag"] == dag + timedelta(days=1)]
    if volgende.empty:
        return f"vanaf {van:%H:%M}"
    tot = volgende.iloc[0]["vliegen_van"]
    if pd.isna(tot):
        return f"vanaf {van:%H:%M}"
    return f"{van:%H:%M} → {tot:%H:%M}"


@st.cache_data(ttl=3600)
def haal_alles(latitude, longitude):
    tabel, zon = WeatherClient(latitude, longitude).haal_alles()
    if tabel is None:
        raise RuntimeError("Geen weerdata")
    return tabel, zon


@st.cache_data(ttl=3600)
def zoek_plaats(naam):
    resultaten = Geocoder().zoek(naam)
    if resultaten is None:
        raise RuntimeError("Zoeken mislukt")
    return resultaten


instellingen = laad_settings("instellingen.json")
namen = laad_drone_namen("drones.json")
locaties = laad_locaties("locations.json")

if namen is None or locaties is None:
    st.error("drones.json of locations.json kon niet worden gelezen.")
    st.stop()

# Europese hoofdsteden achter je eigen lijst zetten (je kunt in de lijst typen om te zoeken)
locaties = {**locaties, **{k: v for k, v in EUROPA.items() if k not in locaties}}

# Gedeelde link: drone en plaats uit de URL lezen (alleen bij het eerste laden)
if "url_gelezen" not in st.session_state:
    st.session_state["url_gelezen"] = True
    if st.query_params.get("drone") in namen:
        st.session_state["start_drone"] = st.query_params["drone"]
    if st.query_params.get("plaats") in locaties:
        st.session_state["start_locatie"] = st.query_params["plaats"]

# Eigen keuze uit de browser van deze bezoeker terughalen (één keer per sessie)
if not st.session_state.get("ls_toegepast"):
    bewaard_uit_browser = bewaar_lezen()
    if bewaard_uit_browser is not None:
        pas_bewaard_toe(bewaard_uit_browser, namen, locaties, PROFIELEN)

if "gestart" not in st.session_state:
    st.session_state["gestart"] = False

# --- Beginscherm ---
if not st.session_state["gestart"]:
    hero("🚁 Vliegweer-assistent", "Weet wanneer het goed vliegweer is voor jouw drone")

    components.html(banner_html(), height=BANNER_HOOGTE + 10)

    st.write("Kies je drone en een plek. De app beoordeelt elk uur van de komende week "
             "en toont de beste momenten om te vliegen.")

    kaarten = [
        ("🌬️ Wind", "Windstoten vergeleken met de limiet van jouw drone."),
        ("🌡️ Temperatuur", "Binnen het werkbereik van de drone."),
        ("🌫️ Mist en zicht", "Mist en nevel worden apart beoordeeld."),
        ("🌧️ Neerslag", "Regen, onweer en sneeuw, en de kans erop."),
    ]
    for kolom, (titel, tekst) in zip(st.columns(4), kaarten):
        with kolom:
            with st.container(border=True):
                st.markdown(f"**{titel}**")
                st.caption(tekst)

    st.info("Er wordt alleen beoordeeld van 30 minuten voor zonsopgang tot "
            "30 minuten na zonsondergang.")

    with st.expander("Hoe beïnvloedt het weer je drone?"):
        for titel, tekst in WEER_INFO:
            st.markdown(f"**{titel}**  \n{tekst}")

    with st.container(border=True):
        st.markdown("### Snel starten")
        kolom_a, kolom_b = st.columns(2)

        standaard_drone = st.session_state.get("start_drone", instellingen["drone"])
        if standaard_drone not in namen:
            standaard_drone = namen[0]
        start_drone = kolom_a.selectbox("Drone", namen, index=namen.index(standaard_drone),
                                        key="landing_drone")

        lijst = list(locaties.keys())
        gedeelde_plek = st.session_state.get("start_locatie")
        plek_index = lijst.index(gedeelde_plek) if gedeelde_plek in lijst else 0
        start_locatie = kolom_b.selectbox("Locatie", lijst, index=plek_index,
                                          key="landing_locatie")

        begrepen = st.checkbox(
            "Ik begrijp dat dit een hulpmiddel is en geen officieel vliegadvies. "
            "Ik controleer zelf de omstandigheden en de regels voor ik opstijg.",
            value=st.session_state.get("akkoord", False))

        if st.button("Start", type="primary", disabled=not begrepen):
            st.session_state["akkoord"] = True
            st.session_state["start_drone"] = start_drone
            st.session_state["start_locatie"] = start_locatie
            st.session_state["gestart"] = True
            st.rerun()

    st.caption("In de app kun je ook je eigen drone invullen, een plaats ter wereld zoeken, "
               "op de kaart klikken of coördinaten invoeren.")
    st.divider()
    st.caption(BRONNEN)
    st.stop()

# --- Hoofdscherm ---
hero("🚁 Vliegweer-assistent", "Een hulpmiddel, geen officieel vliegadvies. De piloot beslist zelf.",
     klein=True)

drone = None
latitude = None
longitude = None
locatie_naam = None

# --- Keuzes in de zijbalk ---
with st.sidebar:
    if st.button("← Beginscherm"):
        st.session_state["gestart"] = False
        st.rerun()

    st.markdown("### Drone")
    drone_methode = st.radio("Drone kiezen", ["Uit de lijst", "Eigen drone"],
                             label_visibility="collapsed")

    if drone_methode == "Uit de lijst":
        standaard = st.session_state.get("start_drone", instellingen["drone"])
        index = namen.index(standaard) if standaard in namen else 0
        drone_naam = st.selectbox("Drone", namen, index=index)
        drone = laad_drone("drones.json", drone_naam)

    else:
        eigen_naam = st.text_input("Naam van je drone", placeholder="bijvoorbeeld DJI Matrice 4TD")
        if eigen_naam.strip():
            zoek_url = "https://www.google.com/search?q=" + quote_plus(
                eigen_naam.strip() + " specs max wind speed resistance operating temperature")
            st.link_button("Zoek de specificaties op", zoek_url)

        max_wind = st.number_input("Max. windweerstand (m/s)", min_value=1.0,
                                   max_value=40.0, value=10.0, step=0.1)
        min_temp = st.number_input("Min. werktemperatuur (°C)", min_value=-60.0,
                                   max_value=40.0, value=-10.0, step=1.0)
        max_temp = st.number_input("Max. werktemperatuur (°C)", min_value=0.0,
                                   max_value=80.0, value=40.0, step=1.0)
        st.caption("Neem deze waarden over uit de officiële specificaties van de fabrikant. "
                   "De standaardwaarden hierboven zijn alleen een startpunt.")

        if min_temp >= max_temp:
            st.error("De minimumtemperatuur moet lager zijn dan de maximumtemperatuur.")
        else:
            drone = Drone(eigen_naam.strip() or "Eigen drone", max_wind, min_temp, max_temp)

    st.markdown("### Locatie")
    methode = st.radio("Locatie kiezen",
                       ["Uit de lijst", "Plaats zoeken", "Op de kaart klikken", "Coördinaten"],
                       label_visibility="collapsed")

    if methode == "Uit de lijst":
        lijst = list(locaties.keys())
        start_locatie = st.session_state.get("start_locatie")
        locatie_index = lijst.index(start_locatie) if start_locatie in lijst else 0
        locatie_naam = st.selectbox("Locatie (typ om te zoeken)", lijst, index=locatie_index)
        latitude = locaties[locatie_naam]["latitude"]
        longitude = locaties[locatie_naam]["longitude"]

    elif methode == "Plaats zoeken":
        zoekterm = st.text_input("Plaatsnaam (wereldwijd)", placeholder="bijvoorbeeld Stockholm")
        if zoekterm:
            try:
                resultaten = zoek_plaats(zoekterm)
            except RuntimeError:
                st.error("Zoeken is mislukt. Controleer je internetverbinding.")
                resultaten = []
            if not resultaten and len(zoekterm.strip()) >= 2:
                st.warning("Geen plaats gevonden. Probeer een andere spelling.")
            elif resultaten:
                keuze = st.selectbox("Kies de juiste plaats", resultaten,
                                     format_func=lambda r: r["label"])
                locatie_naam = keuze["label"]
                latitude = keuze["latitude"]
                longitude = keuze["longitude"]

    elif methode == "Op de kaart klikken":
        st.caption("Klik op de kaart in het hoofdscherm om je plek te kiezen.")

    else:
        locatie_naam = st.text_input("Naam van je plek", value="Mijn vliegplek")
        latitude = st.number_input("Latitude", min_value=-90.0, max_value=90.0,
                                   value=51.2093, format="%.4f")
        longitude = st.number_input("Longitude", min_value=-180.0, max_value=180.0,
                                    value=3.2247, format="%.4f")
        st.caption("Tip: klik in Google Maps met rechts op je plek en kopieer de twee getallen.")

    st.markdown("### Voorkeuren")
    profiel_naam = st.selectbox("Profiel", list(PROFIELEN), key="profiel_keuze",
                                help="Stelt de drempels voor wind, zicht en regen in één keer in.")
    st.caption(profiel_uitleg(profiel_naam))
    start, eind = st.slider(
        "Voorkeursuren voor het advies", 0, 23,
        (instellingen["start_uur"], instellingen["eind_uur"]),
        help="Deze uren tellen mee voor het advies en de beste uren. "
             "Het raster toont alle uren waarop vliegen mag.")
    marge = st.slider("Twijfelgrens (deel van max. wind)", 0.3, 1.0,
                      float(profiel_marge(profiel_naam, instellingen["marge"])), 0.05,
                      key=f"marge_{profiel_naam}")

# --- Keuze bewaren in de URL (om te delen) ---
url_waarden = (
    ("drone", drone.naam if (drone_methode == "Uit de lijst" and drone is not None) else None),
    ("plaats", locatie_naam if methode == "Uit de lijst" else None),
)
for sleutel, waarde in url_waarden:
    if waarde:
        st.query_params[sleutel] = waarde
    elif sleutel in st.query_params:
        del st.query_params[sleutel]

# --- Keuze onthouden in de browser van deze bezoeker ---
if st.session_state.get("ls_toegepast"):
    bewaard = dict(st.session_state.get("bewaard", {}))
    if drone_methode == "Uit de lijst" and drone is not None:
        bewaard["drone"] = drone.naam
    if methode == "Uit de lijst" and locatie_naam:
        bewaard["plaats"] = locatie_naam
    bewaard["profiel"] = profiel_naam
    st.session_state["bewaard"] = bewaard
    bewaar_schrijven(bewaard)

# --- Kaart om op te klikken ---
if methode == "Op de kaart klikken":
    with st.container(border=True):
        st.markdown("**Klik op de kaart om je plek te kiezen**")
        gekozen = st.session_state.get("kaart_punt")
        kaart = folium.Map(location=gekozen or [54, 15], zoom_start=11 if gekozen else 4)
        if gekozen:
            folium.Marker(gekozen).add_to(kaart)

        uitkomst = st_folium(kaart, width=700, height=400, returned_objects=["last_clicked"])
        klik = uitkomst.get("last_clicked") if uitkomst else None
        if klik:
            nieuw = [klik["lat"], klik["lng"]]
            if st.session_state.get("kaart_punt") != nieuw:
                st.session_state["kaart_punt"] = nieuw
                st.rerun()

    if "kaart_punt" in st.session_state:
        latitude, longitude = st.session_state["kaart_punt"]
        locatie_naam = f"Kaartpunt ({latitude:.3f}, {longitude:.3f})"

if drone is None:
    st.info("Kies een drone of vul de gegevens van je eigen drone in, in de zijbalk.")
    st.stop()

if latitude is None:
    st.info("Kies of zoek een locatie.")
    st.stop()

keuzes = dict(instellingen)
keuzes.update(profiel_drempels(profiel_naam))
keuzes.update(start_uur=start, eind_uur=eind, marge=marge)

# --- Gegevens ophalen en beoordelen ---
try:
    with st.spinner("Weerdata ophalen…"):
        tabel, zon = haal_alles(latitude, longitude)
except RuntimeError:
    st.error("Kon geen weerdata ophalen. Controleer je internetverbinding.")
    st.stop()

if zon is not None and zon["vliegen_van"].isna().any():
    st.warning("Voor deze plek gaat de zon op sommige dagen niet op of onder "
               "(poolnacht of middernachtzon). De app kan hier geen vliegvenster "
               "bepalen en toont die uren als nacht.")

scorer = FlightScorer(drone, keuzes)
tabel = scorer.voeg_score_toe(tabel)

advisor = Advisor(drone, keuzes)
week = advisor.week(tabel)

# --- Advies bovenaan ---
context = f"{drone.naam} · {locatie_naam}"
venster = f"tussen {start}:00 en {eind}:00"

if week.empty:
    st.info("Er zijn geen toegestane uren binnen je voorkeursuren.")
else:
    top = week.sort_values(["goed", "twijfelachtig"], ascending=False).iloc[0]
    if top["goed"] > 0:
        advies_kaart("goed", f"Beste vliegdag: {dag_label(top['dag'])}",
                     f"{top['goed']} goede uren {venster}.", context)
    elif top["twijfelachtig"] > 0:
        advies_kaart("twijfelachtig", "Geen echt goede dag",
                     f"Het minst slecht is {dag_label(top['dag'])}, met "
                     f"{top['twijfelachtig']} twijfelachtige uren {venster}.", context)
    else:
        advies_kaart("niet vliegen", "Geen vliegbare uren",
                     f"Er zijn {venster} de komende 7 dagen geen uren om te vliegen.", context)

# --- Kerncijfers ---
if week.empty:
    totalen = (0, 0, 0)
else:
    totalen = (int(week["goed"].sum()), int(week["twijfelachtig"].sum()),
               int(week["niet vliegen"].sum()))

k1, k2, k3, k4 = st.columns(4)
kpi_kaart(k1, "Goede uren", totalen[0], KLEUR["goed"])
kpi_kaart(k2, "Twijfelachtig", totalen[1], KLEUR["twijfel"])
kpi_kaart(k3, "Niet vliegen", totalen[2], KLEUR["niet"])
kpi_kaart(k4, "Windlimiet drone", f"{drone.max_wind:g}", KLEUR["blauw"], "m/s")
st.caption(f"Alleen uren tussen {start}:00 en {eind}:00 tellen mee voor deze cijfers. "
           f"Profiel: {profiel_naam}.")

kou = kou_tekst(tabel, start, eind)
if kou:
    st.warning(kou)

(tab_overzicht, tab_europa, tab_bericht, tab_dag, tab_grafieken, tab_uren, tab_vergelijk,
 tab_logboek, tab_export, tab_uitleg, tab_over) = st.tabs(
    ["Overzicht", "Europa", "Weerbericht", "Per dag", "Grafieken", "Alle uren",
     "Vergelijken", "Logboek", "Delen en export", "Uitleg", "Over"])

# --- Tab: overzicht ---
with tab_overzicht:
    if not week.empty:
        with st.container(border=True):
            st.markdown("**De week in één oogopslag**")
            overzicht = pd.DataFrame({
                "Dag": [dag_label(d) for d in week["dag"]],
                "Oordeel": week["oordeel"].map(ICONEN),
                "Goede uren": week["goed"],
                "Max. windstoot (m/s)": week["max_stoot"].round(1),
                "Opmerking": week["opmerking"],
            })
            st.dataframe(overzicht, hide_index=True)

    with st.container(border=True):
        st.markdown("**Vliegbare uren per dag**")
        uurtabel = advisor.uurtabel(tabel)
        if uurtabel.empty:
            st.info("Er zijn geen uren waarop vliegen mag.")
        else:
            if zon is not None:
                uurtabel.insert(1, "Niet vliegen van – tot",
                                [nacht_tekst(zon, dag) for dag in uurtabel.index])
            uurtabel.index = [dag_label(d) for d in uurtabel.index]
            uurtabel.index.name = "Dag"
            st.dataframe(uurtabel)
            st.caption("🟢 goed · 🟡 twijfelachtig · 🔴 niet vliegen · 🌙 buiten het toegestane "
                       "tijdvenster. Het raster toont alle uren van 30 minuten voor zonsopgang "
                       "tot 30 minuten na zonsondergang.")

    with st.container(border=True):
        st.markdown("**Beste uur per dag**")
        beste = scorer.beste_uren(tabel)
        if beste.empty:
            st.info("Geen goed uur gevonden binnen je voorkeursuren.")
        else:
            weergave = beste[["time", "wind_gusts_10m", "temperature_2m"]].rename(columns={
                "time": "Tijdstip",
                "wind_gusts_10m": "Windstoten (m/s)",
                "temperature_2m": "Temperatuur (°C)",
            })
            st.dataframe(weergave, hide_index=True)

    if methode != "Op de kaart klikken":
        with st.expander("Locatie op de kaart"):
            st.map(pd.DataFrame({"lat": [latitude], "lon": [longitude]}), zoom=9)

# --- Tab: Europa ---
with tab_europa:
    toon_europa(haal_alles, drone, keuzes, dag_label, zoek_plaats)

# --- Tab: weerbericht ---
with tab_bericht:
    with st.container(border=True):
        st.markdown("**Weerbericht per dag, voor de uren waarop vliegen mag**")
        bericht = advisor.weerbericht(tabel)
        if bericht.empty:
            st.info("Er zijn geen uren waarop vliegen mag.")
        else:
            dagen = bericht.pop("dag")
            bericht.insert(0, "Dag", [dag_label(d) for d in dagen])
            st.dataframe(bericht, hide_index=True)
            st.caption("🟢 geen bezwaar · 🟡 twijfelachtig · 🔴 niet vliegen. "
                       "Het bolletje toont het slechtste uur van die dag voor die factor.")

# --- Tab: per dag ---
with tab_dag:
    dag_opties = list(tabel["dag"].unique())
    gekozen_dag = st.selectbox("Kies een dag", dag_opties, format_func=dag_label)
    toon_dag(tabel, zon, gekozen_dag, drone, extra_weer(latitude, longitude),
             PROFIELEN[profiel_naam])

# --- Tab: grafieken ---
with tab_grafieken:
    with st.container(border=True):
        st.markdown("**Vliegbare uren per dag**")
        overdag = tabel[tabel["score"] != "nacht"]
        per_dag = pd.crosstab(overdag["dag"], overdag["score"])
        volgorde = ["goed", "twijfelachtig", "niet vliegen"]
        for kolom in volgorde:
            if kolom not in per_dag.columns:
                per_dag[kolom] = 0
        per_dag = per_dag[volgorde]
        per_dag.index = [dag_label(d) for d in per_dag.index]

        fig1, ax1 = plt.subplots(figsize=(10, 4))
        per_dag.plot(kind="bar", stacked=True, ax=ax1,
                     color=[KLEUR["goed"], KLEUR["twijfel"], KLEUR["niet"]])
        ax1.set_xlabel("")
        ax1.set_ylabel("Aantal toegestane uren")
        ax1.legend(title="")
        stijl_grafiek(ax1)
        plt.setp(ax1.get_xticklabels(), rotation=45, ha="right")
        fig1.tight_layout()
        st.pyplot(fig1)

    with st.container(border=True):
        st.markdown("**Wind komende 7 dagen**")
        fig2, ax2 = plt.subplots(figsize=(10, 4))
        ax2.plot(tabel["time"], tabel["wind_speed_10m"], label="Wind", color="#5B9BD5")
        ax2.plot(tabel["time"], tabel["wind_gusts_10m"], label="Windstoten", color=KLEUR["blauw"])
        ax2.axhline(drone.max_wind, color=KLEUR["niet"], linestyle="--", label="Limiet drone")
        ax2.axhline(drone.max_wind * marge, color=KLEUR["twijfel"], linestyle="--",
                    label="Twijfelgrens")
        ax2.set_xlabel("Tijd")
        ax2.set_ylabel("Snelheid (m/s)")
        ax2.legend()
        stijl_grafiek(ax2)
        fig2.tight_layout()
        st.pyplot(fig2)

# --- Tab: alle uren ---
with tab_uren:
    with st.container(border=True):
        st.dataframe(tabel[["time", "temperature_2m", "wind_speed_10m", "wind_gusts_10m",
                            "precipitation", "visibility", "score", "reden"]], hide_index=True)

# --- Tab: vergelijken ---
with tab_vergelijk:
    toon_vergelijking(haal_alles, drone, keuzes, locaties, namen,
                      latitude, longitude, locatie_naam, dag_label)

# --- Tab: logboek ---
with tab_logboek:
    toon_logboek(namen)

# --- Tab: delen en export ---
with tab_export:
    toon_samenvatting(tabel, drone, locatie_naam, start, eind, dag_label,
                      extra_weer(latitude, longitude))
    toon_export(tabel, drone, locatie_naam, start, eind)

# --- Tab: uitleg ---
with tab_uitleg:
    with st.container(border=True):
        st.markdown(f"""
**Hoe wordt de score berekend?**

Elk uur wordt voor vier factoren apart beoordeeld. Het ergste oordeel telt.

1. **Nacht**: buiten het tijdvenster van 30 minuten voor zonsopgang tot 30 minuten na
   zonsondergang wordt er niet gevlogen. Een uur telt mee zodra het dat venster raakt.
2. **Wind**: *niet vliegen* bij windstoten boven {drone.max_wind} m/s,
   *twijfelachtig* boven {drone.max_wind * marge:.1f} m/s ({int(marge * 100)}% van de limiet).
3. **Temperatuur**: *niet vliegen* buiten {drone.min_temp} tot {drone.max_temp} °C,
   *twijfelachtig* binnen {keuzes['temp_marge']} °C van die grenzen.
4. **Mist en zicht**: *niet vliegen* bij zicht onder {keuzes['min_zicht']} m of een weercode
   voor mist, *twijfelachtig* bij zicht onder {keuzes['twijfel_zicht']} m (nevel).
5. **Neerslag**: *niet vliegen* bij meer dan {keuzes['max_regen']} mm per uur, onweer, sneeuw of
   ijzel. *Twijfelachtig* bij lichte neerslag, motregen of een regenkans vanaf {keuzes['regenkans']}%.

Een dag is **goed** als minstens de helft van je voorkeursuren goed is, **twijfelachtig** als er
minstens één goed of twijfelachtig uur is, en anders **niet vliegen**.

**Wat de app niet weet**

- Of je op die plek mag vliegen (luchtruim, no-flyzones, natuurgebieden, regels in jouw land).
  Ook de regels over vliegen rond zonsopgang en zonsondergang verschillen per land en categorie.
- Hoe het lokaal waait: gebouwen, bomen en de kust kunnen windstoten sterk veranderen.
- Hoe de drone zich op de dag zelf gedraagt. De limieten komen uit de specificaties.
- De drempels voor zicht, neerslag en temperatuurmarge zijn voorzichtige eigen keuzes en geen
  regels van de fabrikant. Mist is plaatselijk en wordt door een model soms gemist.

Controleer altijd de omstandigheden ter plaatse en de regels van je land voor je opstijgt.
""")

# --- Tab: over ---
with tab_over:
    with st.container(border=True):
        st.markdown(f"""
**Over de Vliegweer-assistent** (versie {VERSIE})

Een hulpmiddel om te zien wanneer het weer geschikt is om met een drone te vliegen.
De app beoordeelt elk uur voor wind, temperatuur, mist en neerslag, rekening houdend
met de limieten van de gekozen drone.

**Bronnen**

- Weerdata, zonnetijden en plaatsnamen: Open-Meteo.com (CC BY 4.0).
- Geomagnetische activiteit (Kp-index): NOAA Space Weather Prediction Center.
- Kaart: © OpenStreetMap-bijdragers.
- Dronespecificaties: de officiële gegevens van de fabrikanten, handmatig overgenomen.

**Privacy**

De app zelf slaat geen persoonsgegevens, locaties of zoekopdrachten op. Om het weer en
plaatsnamen op te vragen, worden coördinaten en zoektermen wel naar Open-Meteo gestuurd.
Het platform waarop de app draait en externe diensten kunnen eigen logbestanden bijhouden.

**Belangrijk**

Dit is geen officieel vliegadvies. Controleer altijd de omstandigheden ter plaatse en de
regels van je land voor je opstijgt.
""")

st.divider()
st.caption(BRONNEN)
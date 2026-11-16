import html

import streamlit as st

VERSIE = "1.3"

FONT = "'Segoe UI',system-ui,-apple-system,Roboto,Arial,sans-serif"

KLEUR = {
    "marine": "#0B2545",
    "blauw": "#1D4E89",
    "lichtblauw": "#EAF1FA",
    "rand": "#D5DFEC",
    "tekst": "#1F2933",
    "grijs": "#52606D",
    "goed": "#2E7D32",
    "twijfel": "#F2A900",
    "niet": "#C62828",
}

# achtergrond, rand, tekstkleur, icoon
STATUS = {
    "goed": ("#E8F5E9", "#2E7D32", "#1B5E20", "🟢"),
    "twijfelachtig": ("#FFF8E1", "#F2A900", "#7A4F01", "🟡"),
    "niet vliegen": ("#FDECEA", "#C62828", "#8E1B1B", "🔴"),
}

CSS = """
<style>
.block-container { padding-top: 1.5rem; padding-bottom: 3rem; max-width: 1100px; }
[data-testid="stSidebar"] { border-right: 1px solid #D5DFEC; }
[data-testid="stSidebar"] h3 { color: #0B2545; font-size: 1.05rem; margin-top: 0.8rem; }
h2, h3, h4 { color: #0B2545; letter-spacing: -0.2px; }
.stButton > button { border-radius: 10px; font-weight: 600; }
button[data-baseweb="tab"] { font-weight: 600; }
[data-testid="stDataFrame"] { border: 1px solid #D5DFEC; border-radius: 10px; overflow: hidden; }
footer { visibility: hidden; }
@media (max-width: 640px) {
    .block-container { padding-left: 1rem; padding-right: 1rem; }
}
</style>
"""


def pas_stijl_toe():
    st.markdown(CSS, unsafe_allow_html=True)


def hero(titel, ondertitel, klein=False):
    pad = "1rem 1.4rem" if klein else "1.8rem 2rem"
    grootte = "1.6rem" if klein else "2.3rem"
    delen = [
        '<div style="background:linear-gradient(135deg,#0B2545 0%,#1D4E89 100%);',
        f'padding:{pad};border-radius:16px;margin-bottom:1rem;color:#FFFFFF;font-family:{FONT};">',
        f'<div style="font-size:{grootte};font-weight:700;letter-spacing:-0.5px;line-height:1.2;">',
        f'{html.escape(titel)}</div>',
        f'<div style="font-size:1rem;opacity:0.88;margin-top:0.35rem;">{html.escape(ondertitel)}</div>',
        '</div>',
    ]
    st.markdown("".join(delen), unsafe_allow_html=True)


def advies_kaart(niveau, kop, detail="", context=""):
    achtergrond, rand, tekst, icoon = STATUS[niveau]
    delen = [
        f'<div style="background:{achtergrond};border:1px solid {rand}55;border-left:8px solid {rand};',
        f'border-radius:14px;padding:1rem 1.3rem;margin:0.5rem 0 1rem 0;color:{tekst};font-family:{FONT};">',
    ]
    if context:
        delen.append(
            f'<div style="font-size:0.8rem;font-weight:600;letter-spacing:0.5px;'
            f'text-transform:uppercase;opacity:0.8;">{html.escape(context)}</div>')
    delen.append(
        f'<div style="font-size:1.45rem;font-weight:700;margin-top:0.2rem;">'
        f'{icoon} {html.escape(kop)}</div>')
    if detail:
        delen.append(f'<div style="font-size:1rem;margin-top:0.2rem;">{html.escape(detail)}</div>')
    delen.append('</div>')
    st.markdown("".join(delen), unsafe_allow_html=True)


def kpi_kaart(kolom, label, waarde, kleur=KLEUR["blauw"], eenheid=""):
    delen = [
        f'<div style="background:#FFFFFF;border:1px solid {KLEUR["rand"]};border-top:5px solid {kleur};',
        f'border-radius:12px;padding:0.8rem 1rem;box-shadow:0 1px 3px rgba(11,37,69,0.08);font-family:{FONT};">',
        f'<div style="color:{KLEUR["grijs"]};font-size:0.85rem;font-weight:600;">{html.escape(str(label))}</div>',
        f'<div style="color:{KLEUR["marine"]};font-size:1.9rem;font-weight:700;line-height:1.2;">',
        f'{html.escape(str(waarde))}',
        f'<span style="font-size:0.9rem;font-weight:600;color:{KLEUR["grijs"]};"> {html.escape(eenheid)}</span>',
        '</div></div>',
    ]
    kolom.markdown("".join(delen), unsafe_allow_html=True)


def stijl_grafiek(ax):
    ax.spines[["top", "right"]].set_visible(False)
    ax.grid(axis="y", color="#E3E8EF", linewidth=0.8)
    ax.set_axisbelow(True)
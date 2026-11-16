import base64
import os
from functools import lru_cache

FOTO_PADEN = ["assets/header.jpg", "assets/header.jpeg", "assets/header.png"]

BANNER_HOOGTE = 320

ALT_TEKST = "Een drone vliegt tussen wolken, regen, onweer, wind, mist en zon"

WEER_INFO = [
    ("🌬️ Wind en windstoten",
     "Een drone moet tegen de wind in werken om zijn plek te houden. Bij stevige wind of vlagen "
     "gaat de batterij sneller leeg en wordt terugvliegen moeilijker. Op hoogte waait het "
     "meestal harder dan het weerbericht op 10 meter hoogte aangeeft."),
    ("🥶 Kou",
     "Bij lage temperaturen levert de batterij minder vermogen en wordt de vliegtijd korter. "
     "Fabrikanten geven daarom een minimale werktemperatuur op."),
    ("🔥 Hitte",
     "Bij hoge temperaturen kan de drone oververhitten. Ook voor de batterij geldt een "
     "maximale temperatuur."),
    ("🌫️ Mist en nevel",
     "Bij slecht zicht verlies je de drone snel uit het oog. In veel landen moet je de drone "
     "in zicht houden. Vocht in de lucht is bovendien niet goed voor elektronica."),
    ("🌧️ Regen en sneeuw",
     "De meeste consumentendrones zijn niet waterdicht. Neerslag kan de elektronica "
     "beschadigen, en bij vorst kan er ijs op de propellers komen."),
    ("⛈️ Onweer",
     "Vlieg nooit bij onweer: er is kans op felle windvlagen en blikseminslag."),
]

SVG = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1000 300"
     preserveAspectRatio="xMidYMid slice" width="100%" height="100%" role="img">
  <defs>
    <linearGradient id="lucht" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0" stop-color="#2f80c9"/>
      <stop offset="1" stop-color="#bfe3f7"/>
    </linearGradient>
    <linearGradient id="mist" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0" stop-color="#ffffff" stop-opacity="0"/>
      <stop offset="1" stop-color="#ffffff" stop-opacity="0.8"/>
    </linearGradient>
    <g id="wolk">
      <circle cx="0" cy="0" r="22"/>
      <circle cx="26" cy="-10" r="28"/>
      <circle cx="58" cy="0" r="22"/>
      <rect x="-22" y="0" width="102" height="22" rx="11"/>
    </g>
    <g id="drone">
      <line x1="-70" y1="-6" x2="70" y2="-6" stroke="#1f2933" stroke-width="6" stroke-linecap="round"/>
      <path d="M -24 6 L -32 28 M 24 6 L 32 28" stroke="#1f2933" stroke-width="4" stroke-linecap="round" fill="none"/>
      <rect x="-34" y="-20" width="68" height="26" rx="12" fill="#2d3748"/>
      <rect x="-22" y="-16" width="44" height="6" rx="3" fill="#4a5568"/>
      <rect x="-76" y="-18" width="12" height="14" rx="3" fill="#1a202c"/>
      <rect x="64" y="-18" width="12" height="14" rx="3" fill="#1a202c"/>
      <ellipse cx="-70" cy="-22" rx="34" ry="4" fill="#1a202c" opacity="0.55"/>
      <ellipse cx="70" cy="-22" rx="34" ry="4" fill="#1a202c" opacity="0.55"/>
      <line x1="0" y1="6" x2="0" y2="12" stroke="#1a202c" stroke-width="4"/>
      <circle cx="0" cy="16" r="9" fill="#1a202c"/>
      <circle cx="0" cy="16" r="4" fill="#63b3ed"/>
    </g>
  </defs>

  <rect width="1000" height="300" fill="url(#lucht)"/>

  <circle cx="905" cy="62" r="56" fill="#ffe082" opacity="0.35"/>
  <circle cx="905" cy="62" r="34" fill="#ffd54a"/>

  <g fill="#ffffff" opacity="0.92">
    <g>
      <animateTransform attributeName="transform" type="translate" values="0 0;40 0;0 0" dur="40s" repeatCount="indefinite"/>
      <use href="#wolk" transform="translate(120 70)"/>
      <use href="#wolk" transform="translate(560 40) scale(1.2)"/>
    </g>
    <g>
      <animateTransform attributeName="transform" type="translate" values="0 0;-30 0;0 0" dur="50s" repeatCount="indefinite"/>
      <use href="#wolk" transform="translate(790 125) scale(0.9)"/>
    </g>
  </g>

  <use href="#wolk" fill="#64748b" transform="translate(290 70) scale(1.4)"/>
  <g stroke="#dbeafe" stroke-width="3" stroke-linecap="round">
    <animate attributeName="opacity" values="1;0.35;1" dur="1.4s" repeatCount="indefinite"/>
    <line x1="278" y1="112" x2="272" y2="138"/>
    <line x1="300" y1="112" x2="294" y2="138"/>
    <line x1="322" y1="112" x2="316" y2="138"/>
    <line x1="344" y1="112" x2="338" y2="138"/>
    <line x1="366" y1="112" x2="360" y2="138"/>
    <line x1="388" y1="112" x2="382" y2="138"/>
    <line x1="289" y1="140" x2="284" y2="162"/>
    <line x1="311" y1="140" x2="306" y2="162"/>
    <line x1="333" y1="140" x2="328" y2="162"/>
    <line x1="355" y1="140" x2="350" y2="162"/>
    <line x1="377" y1="140" x2="372" y2="162"/>
  </g>

  <use href="#wolk" fill="#475569" transform="translate(660 70) scale(1.3)"/>
  <polygon points="700,100 686,130 698,130 690,158 716,120 703,120 712,100" fill="#ffd54a"/>

  <g fill="none" stroke="#ffffff" stroke-width="4" stroke-linecap="round" opacity="0.85">
    <path d="M 30 190 C 90 170, 150 215, 215 192"/>
    <path d="M 70 222 C 140 202, 200 245, 270 222"/>
    <path d="M 780 205 C 840 185, 900 230, 965 207"/>
  </g>

  <rect x="0" y="205" width="1000" height="95" fill="url(#mist)"/>
  <g fill="#ffffff" opacity="0.45">
    <ellipse cx="200" cy="262" rx="220" ry="16"/>
    <ellipse cx="640" cy="276" rx="260" ry="14"/>
    <ellipse cx="900" cy="252" rx="160" ry="12"/>
  </g>

  <g>
    <animateTransform attributeName="transform" type="translate" values="0 0;0 -10;0 0" dur="4s" repeatCount="indefinite"/>
    <use href="#drone" transform="translate(500 150) scale(1.3)"/>
  </g>
  <g opacity="0.75">
    <animateTransform attributeName="transform" type="translate" values="0 0;0 -6;0 0" dur="5s" repeatCount="indefinite"/>
    <use href="#drone" transform="translate(165 140) scale(0.55)"/>
  </g>
  <g opacity="0.7">
    <animateTransform attributeName="transform" type="translate" values="0 0;0 -5;0 0" dur="6s" repeatCount="indefinite"/>
    <use href="#drone" transform="translate(860 165) scale(0.5)"/>
  </g>
</svg>"""

PAGINA = """<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<style>
  html, body {{ margin: 0; padding: 0; background: transparent; }}
  .banner {{ width: 100%; height: {hoogte}px; border-radius: 14px; overflow: hidden; }}
  .banner svg, .banner img {{ width: 100%; height: 100%; display: block; }}
  .banner img {{ object-fit: cover; }}
</style>
</head>
<body>
  <div class="banner" aria-label="{alt}">{inhoud}</div>
</body>
</html>"""


@lru_cache(maxsize=1)
def banner_html():
    inhoud = SVG
    for pad in FOTO_PADEN:
        if os.path.exists(pad):
            mime = "image/png" if pad.endswith(".png") else "image/jpeg"
            with open(pad, "rb") as bestand:
                b64 = base64.b64encode(bestand.read()).decode("ascii")
            inhoud = f'<img src="data:{mime};base64,{b64}" alt="{ALT_TEKST}">'
            break
    return PAGINA.format(hoogte=BANNER_HOOGTE, alt=ALT_TEKST, inhoud=inhoud)
#Koda deluje za specificen XML dokument

import xml.etree.ElementTree as ET
import pandas as pd
import geopandas as gpd

tree = ET.parse("ones_zrak_dnevni_podatki_zadnji.xml")
root = tree.getroot()

rows = []
for postaja in root.findall("postaja"):
    row = {
        "sifra":        postaja.get("sifra"),
        "lon":          float(postaja.get("wgs84_dolzina")),
        "lat":          float(postaja.get("wgs84_sirina")),
        "nadm_visina":  float(postaja.get("nadm_visina")),
        "d96_e":        float(postaja.get("d96_e")),
        "d96_n":        float(postaja.get("d96_n")),
    }
    for child in postaja:
        val = child.text
        try:
            val = float(val) if val else None
        except ValueError:
            pass
        row[child.tag] = val
    rows.append(row)

df = pd.DataFrame(rows)

gdf = gpd.GeoDataFrame(
    df,
    geometry=gpd.points_from_xy(df["lon"], df["lat"]),
    crs="EPSG:4326"
)

gdf.to_file("zrak_postaje.geojson", driver="GeoJSON")
"""
Pretvori rasterski TIF v vektorski GeoJSON in Shapefile.
Poženi v istem imeniku kot .tif datoteka:
    python tif_to_vector.py

Zahteva: pip install rasterio geopandas shapely numpy
"""

import os
import glob
import numpy as np
import rasterio
from rasterio.features import shapes
from rasterio.enums import Resampling
import geopandas as gpd
from shapely.geometry import shape

# --- Najdi TIF datoteko (brez podvajanja zaradi velike/male črke) ---
found = {}
for pattern in ["*.tif", "*.tiff", "*.TIF", "*.TIFF"]:
    for f in glob.glob(pattern):
        found[os.path.normcase(f)] = f  # normcase odpravi duplikate na Windowsih

tif_files = list(found.values())

if len(tif_files) == 0:
    print("❌ Ni najdene nobene .tif datoteke v tem imeniku.")
    exit(1)
elif len(tif_files) > 1:
    print("Najdene .tif datoteke:")
    for i, f in enumerate(tif_files):
        print(f"  [{i}] {f}")
    idx = int(input("Izberi številko datoteke: "))
    tif_path = tif_files[idx]
else:
    tif_path = tif_files[0]
    print(f"📂 Najdena datoteka: {tif_path}")

base_name = os.path.splitext(tif_path)[0]

# --- Preberi info o rastru ---
with rasterio.open(tif_path) as src:
    orig_res = src.res[0]
    width, height = src.width, src.height
    crs = src.crs
    nodata = src.nodata
    print(f"\n📊 Info:")
    print(f"   CRS: {crs}")
    print(f"   Resolucija: {orig_res}m")
    print(f"   Velikost: {width} x {height} = {width*height:,} pikslov")
    print(f"   Nodata vrednost: {nodata}")

# --- Določi ciljno resolucijo ---
# Pri 5m resoluciji je raster prevelik za direktno vektorizacijo
# Prevzorčimo na 25m (25x manj pikslov skupaj)
TARGET_RES = 25 if orig_res < 10 else orig_res
scale = TARGET_RES / orig_res
new_width = int(width / scale)
new_height = int(height / scale)

print(f"\n⚙️  Prevzorčujem iz {orig_res}m na {TARGET_RES}m resolucijo...")
print(f"   Nova velikost: {new_width} x {new_height} = {new_width*new_height:,} pikslov")

with rasterio.open(tif_path) as src:
    # Prevzorčenje z "mode" (ohrani kategorične vrednosti 0-5)
    data = src.read(
        1,
        out_shape=(new_height, new_width),
        resampling=Resampling.mode
    )
    new_transform = src.transform * src.transform.scale(
        (src.width / new_width),
        (src.height / new_height)
    )
    nodata = src.nodata

print(f"   Unikatne vrednosti v rastru: {np.unique(data)}")

# --- Maska: samo vrednosti 1-5 (izključi 0 = zanemarljivo in nodata) ---
if nodata is not None:
    mask = (data != int(nodata)) & (data > 0) & (data <= 5)
else:
    mask = (data > 0) & (data <= 5)

print(f"\n⚙️  Vektoriziram... (prosim počakaj)")

image = data.astype(np.int16)
results = list(shapes(image, mask=mask.astype(np.uint8), transform=new_transform))
print(f"   Najdenih poligonov pred združitvijo: {len(results):,}")

# --- Pretvori v GeoDataFrame ---
opis_map = {
    1: "Zelo majhna",
    2: "Majhna",
    3: "Srednja",
    4: "Velika",
    5: "Zelo velika"
}

records = []
for geom, val in results:
    v = int(val)
    if v < 1 or v > 5:
        continue
    records.append({
        "geometry": shape(geom),
        "stopnja": v,
        "opis": opis_map.get(v, str(v))
    })

gdf = gpd.GeoDataFrame(records, crs=crs)

# Združi sosednje poligone z isto stopnjo (dissolve) -> manjša datoteka
print(f"⚙️  Združujem poligone po stopnjah...")
gdf_dissolved = gdf.dissolve(by="stopnja", as_index=False)
gdf_dissolved["opis"] = gdf_dissolved["stopnja"].map(opis_map)
print(f"   Poligonov po združitvi: {len(gdf_dissolved):,}")

# --- Shrani GeoJSON (WGS84) ---
gdf_wgs = gdf_dissolved.to_crs(epsg=4326)
geojson_path = base_name + ".geojson"
gdf_wgs.to_file(geojson_path, driver="GeoJSON")
size_mb = os.path.getsize(geojson_path) / 1e6
print(f"\n✅ GeoJSON shranjen: {geojson_path} ({size_mb:.1f} MB)")

# --- Shrani Shapefile (originalni CRS) ---
shp_path = base_name + ".shp"
gdf_dissolved.to_file(shp_path, driver="ESRI Shapefile", encoding="UTF-8")
shp_size = os.path.getsize(shp_path) / 1e6
print(f"✅ Shapefile shranjen: {shp_path} ({shp_size:.1f} MB)")

# --- Statistika ---
print(f"\n📊 Porazdelitev po stopnjah nevarnosti:")
print(f"   {'St.':<5} {'Opis':<15} {'Površina km²':>14}")
print(f"   {'-'*36}")
for _, row in gdf_dissolved.sort_values("stopnja").iterrows():
    area_km2 = row.geometry.area / 1e6
    print(f"   {int(row['stopnja']):<5} {row['opis']:<15} {area_km2:>13.1f}")

print(f"\n🎉 Končano!")
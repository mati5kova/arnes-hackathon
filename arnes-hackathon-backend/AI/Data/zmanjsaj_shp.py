"""
Zmanjša shapefile iz ZIP-a za lažji upload.
Poženi v istem imeniku kot ZIP datoteka:
    python zmanjsaj_shp.py

Zahteva: pip install geopandas
"""

import os
import glob
import zipfile
import geopandas as gpd

# --- Najdi ZIP ---
zips = list({os.path.normcase(f): f for p in ["*.zip","*.ZIP"] for f in glob.glob(p)}.values())

if not zips:
    print("Ni ZIP datoteke v tem imeniku.")
    exit(1)
elif len(zips) > 1:
    for i, f in enumerate(zips): print(f"  [{i}] {f}")
    zips = [zips[int(input("Izberi številko: "))]]

zip_path = zips[0]
print(f"Obdelujem: {zip_path} ({os.path.getsize(zip_path)/1e6:.1f} MB)")

# --- Razpakaj ---
extract_dir = "shp_temp"
os.makedirs(extract_dir, exist_ok=True)
with zipfile.ZipFile(zip_path, 'r') as z:
    z.extractall(extract_dir)
    print(f"   Vsebina: {z.namelist()}")

# --- Najdi .shp ---
shp_files = glob.glob(f"{extract_dir}/**/*.shp", recursive=True) + glob.glob(f"{extract_dir}/*.shp")
if not shp_files:
    print("Ni .shp datoteke v ZIP-u.")
    exit(1)

shp_path = shp_files[0]
print(f"Berem: {shp_path}")
gdf = gpd.read_file(shp_path)
print(f"   CRS: {gdf.crs}")
print(f"   Features: {len(gdf):,}")
print(f"   Stolpci: {list(gdf.columns)}")
print(f"   Unikatne vrednosti:")
for col in gdf.columns:
    if col != 'geometry':
        print(f"     {col}: {sorted(gdf[col].dropna().unique()[:10])}")

# --- Poenostavi geometrije (zmanjša velikost) ---
print(f"Poenostavljam geometrije...")
gdf_orig_crs = gdf.copy()

# Pretvori v metrični CRS za poenostavitev, potem nazaj
if gdf.crs and gdf.crs.to_epsg() != 3794:
    gdf_m = gdf.to_crs(epsg=3794)
else:
    gdf_m = gdf.copy()

# Poenostavi z toleranco 25m (dovolj natančno za vizualizacijo)
gdf_m['geometry'] = gdf_m.geometry.simplify(tolerance=25, preserve_topology=True)

# Pretvori v WGS84 za GeoJSON
gdf_wgs = gdf_m.to_crs(epsg=4326)

# --- Shrani kot GeoJSON ---
out_path = "pozarna_ogrozenost.geojson"
gdf_wgs.to_file(out_path, driver="GeoJSON")
size_mb = os.path.getsize(out_path) / 1e6
print(f"Shranjeno: {out_path} ({size_mb:.1f} MB)")

if size_mb > 30:
    print(f"Še vedno preveliko za upload ({size_mb:.1f} MB). Poskušam z večjo poenostavitvijo...")
    gdf_m['geometry'] = gdf_m.geometry.simplify(tolerance=100, preserve_topology=True)
    gdf_wgs = gdf_m.to_crs(epsg=4326)
    gdf_wgs.to_file(out_path, driver="GeoJSON")
    size_mb = os.path.getsize(out_path) / 1e6
    print(f" Shranjeno: {out_path} ({size_mb:.1f} MB)")

print(f"Končano")

# Počisti temp dir
import shutil
shutil.rmtree(extract_dir)
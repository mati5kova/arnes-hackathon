"""
Zmanjša velikost GeoJSON datoteke za požarno ogroženost.
Poženi v istem imeniku kot GeoJSON:
    python zmanjsaj_geojson.py

Zahteva: pip install geopandas
"""

import os
import glob
import geopandas as gpd

# --- Najdi GeoJSON ---
files = list({os.path.normcase(f): f for p in ["*.geojson", "*.json", "*.GEOJSON"]
              for f in glob.glob(p)}.values())

if not files:
    print("Ni GeoJSON datoteke v tem imeniku.")
    exit(1)
elif len(files) > 1:
    for i, f in enumerate(files):
        print(f"  [{i}] {f}  ({os.path.getsize(f)/1e6:.1f} MB)")
    files = [files[int(input("Izberi številko: "))]]

in_path = files[0]
orig_mb = os.path.getsize(in_path) / 1e6
print(f"\nBerem: {in_path} ({orig_mb:.1f} MB)")

gdf = gpd.read_file(in_path)
print(f"   Features: {len(gdf):,}")
print(f"   CRS: {gdf.crs}")
print(f"   Stolpci: {list(gdf.columns)}")

# Pokaži unikatne vrednosti za vsak ne-geometry stolpec
for col in gdf.columns:
    if col != 'geometry':
        print(f"   {col}: {sorted(gdf[col].dropna().unique()[:10])}")

# Poišči stolpec z majhnim številom unikatnih vrednosti (= kategorija)
cat_col = None
for col in gdf.columns:
    if col == 'geometry':
        continue
    n_unique = gdf[col].nunique()
    if 2 <= n_unique <= 10:
        cat_col = col
        print(f"\nKategorični stolpec: '{cat_col}' ({n_unique} vrednosti)")
        break

if not cat_col:
    print("\nNi jasnega kategoričnega stolpca. Združujem vse v en poligon.")
    cat_col = gdf.columns[0] if len(gdf.columns) > 1 else None

# --- Korak 1: Popravi neveljavne geometrije ---
print(f"\nKorak 1: Popravljam neveljavne geometrije...")
n_invalid = (~gdf.geometry.is_valid).sum()
print(f"   Neveljavnih geometrij: {n_invalid:,}")
if n_invalid > 0:
    gdf["geometry"] = gdf.geometry.buffer(0)
    n_still = (~gdf.geometry.is_valid).sum()
    print(f"   Po popravku še neveljavnih: {n_still:,}")

# --- Korak 2: Dissolve po kategoriji ---
print("\nKorak 2: Združujem poligone po '{cat_col}'...")
if cat_col:
    gdf_d = gdf.dissolve(by=cat_col, as_index=False)
else:
    gdf_d = gdf.copy()
print(f"   Features po dissolve: {len(gdf_d):,}")

# --- Korak 2: Simplify geometrije ---
# Preveri CRS - za simplify rabimo metrični sistem
if gdf_d.crs and gdf_d.crs.is_geographic:
    print(f"Pretvori v metrični CRS za poenostavitev...")
    gdf_m = gdf_d.to_crs(epsg=3794)
else:
    gdf_m = gdf_d.copy()

# Toleranca 50m - dobra za vizualizacijo, ohrani obliko
print("Korak 3: Poenostavljam z 50m toleranco...")
gdf_m['geometry'] = gdf_m.geometry.simplify(tolerance=50, preserve_topology=True)

# --- Korak 3: Pretvori v WGS84 in shrani ---
print("Korak 4: Pretvori v WGS84...")
gdf_out = gdf_m.to_crs(epsg=4326)

base = os.path.splitext(in_path)[0]
out_path = base + "_majhen.geojson"
gdf_out.to_file(out_path, driver="GeoJSON")
out_mb = os.path.getsize(out_path) / 1e6

print(f"\nShranjeno: {out_path}")
print(f"   Pred: {orig_mb:.1f} MB  →  Po: {out_mb:.1f} MB  (zmanjšano za {(1-out_mb/orig_mb)*100:.0f}%)")

# Če je še vedno preveliko, poskusi z večjo toleranco
if out_mb > 30:
    print(f"Še vedno {out_mb:.1f} MB. Poskušam s 100m toleranco...")
    gdf_m['geometry'] = gdf_m.geometry.simplify(tolerance=100, preserve_topology=True)
    gdf_out = gdf_m.to_crs(epsg=4326)
    out_path2 = base + "_majhen_100m.geojson"
    gdf_out.to_file(out_path2, driver="GeoJSON")
    out_mb2 = os.path.getsize(out_path2) / 1e6
    print(f"    Shranjeno: {out_path2} ({out_mb2:.1f} MB)")

print("Končano")

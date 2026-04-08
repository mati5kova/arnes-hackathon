# %%
import geopandas as gpd
import pandas as pd
import numpy as np

# %%
gdf = gpd.read_file("AI/Data/kd_z_nevarnost_enriched_verified.geojson")
gdf = gdf.drop(columns=['geometry'])

# %%


# %%
embed_cols = gdf[['IME', 'SINONIMI', 'OPIS', 'ZVRST', 'TIP', 'GESLA', 'DATACIJA', 'LOKACIJAOPIS', 'prevladujoci_material', 'UE_UIME', 'OBCINA']]
meta_data_cols = gdf[['EID', 'OBCINA', 'STATUS', 'SPOMENIK', 'UE_UIME', 'prevladujoci_material', 'pozar_ocena_popravljena', 'poplave_ocena_popravljena',
       'potres_ocena_popravljena', 'plazovi_ocena_popravljena']]

# %%
def row_to_text(row):
    parts = []
    for col, val in row.items():
        #codex checks za nan value ipd.
        if val is None:
            continue
        if isinstance(val, (list, tuple, np.ndarray, pd.Series)):
            if len(val) == 0 or pd.isna(val).all():
                continue
            text = " ".join(map(str, val)).strip()
            if not text:
                continue
        else:
            if pd.isna(val) or not str(val).strip():
                continue
        
        if col == 'prevladujoci_material':
            parts.append(f"material: {val}")
        elif col == 'UE_UIME':
            parts.append(f"okraj: {val}")
        else:
            parts.append(f"{col.lower()}: {val}")

    return " | ".join(parts)

# %%
gdf['embed_text'] = embed_cols.apply(row_to_text, axis=1)

# %%
# %%
zapisi = []

def clean_metadata(row, columns):
    out = {}
    for col in columns:
        value = row[col]

        if isinstance(value, np.generic):
            value = value.item()

        if isinstance(value, (list, tuple, np.ndarray, pd.Series)):
            items = [str(x) for x in value if pd.notna(x)]
            if items:
                out[col] = ", ".join(items)
            continue

        if pd.isna(value):
            value = ""

        out[col] = value

    return out

for _, row in gdf.iterrows():
    zapisi.append({
        "eid" : row['EID'],
        "text" : row['embed_text'],
        "meta_data": clean_metadata(row, meta_data_cols.columns),
    })

# %%
import os
from dotenv import load_dotenv
from openai import AzureOpenAI
import chromadb

load_dotenv()

deployment_name = os.getenv("MDML-TextEmbedding-003_DEPLOYMENT")
api_key = os.getenv("MDML-TextEmbedding-003_API_KEY")
base_url = os.getenv("MDML-TextEmbedding-003_BASE_URL")

client = AzureOpenAI(
    api_key=os.getenv("MDML-TextEmbedding-003_API_KEY"),
    azure_endpoint=os.getenv("MDML-TextEmbedding-003_BASE_URL"),
    api_version="2024-02-01",
)

EMBED_MODEL = deployment_name
total_embedding_tokens = 0
# %%
chroma_client = chromadb.PersistentClient(path="AI/Data/chroma_db")
collection = chroma_client.get_or_create_collection("kulturna_dediscina")

BATCH_SIZE = 100
for i in range(0, len(zapisi), BATCH_SIZE):
    print(f"batch nr: {i // BATCH_SIZE}\n")
    batch = zapisi[i: i+BATCH_SIZE]
    texts = [r['text'] for r in batch]

    response = client.embeddings.create(
        model=EMBED_MODEL,
        input=texts
    )

    collection.add(
        ids=[str(r['eid']) for r in batch],
        documents=[r['text'] for r in batch],
        metadatas=[r['meta_data'] for r in batch],
        embeddings=[item.embedding for item in response.data]
    )

    total_embedding_tokens += response.usage.total_tokens
    print(f"batch {i // BATCH_SIZE + 1}: {response.usage.total_tokens} tokens")

print("all embedding tokens:", total_embedding_tokens)

# %%




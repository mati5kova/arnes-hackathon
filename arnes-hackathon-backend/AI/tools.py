import geopandas as gpd

gdf = gpd.read_file("kd_z_nevarnost.geojson")

TOOLS = [
    {
        "name": "top_k_endangered_in_region",
        "description": "returns a list of the top k endangered objects in a region of a certain type of endangerment",
        "input_schema": {
            "type": "object",
            "properties": {
                "isRegija": {
                    "type": "boolean",
                    "description" : "True to filter by regija/region, False to filter by manucipality/OBCINA"
                    },
                "regija":{
                    "type":"string",
                    "description": "The region or manucipality to filter by, manucipalities are all uppercase, first letter of region is uppercase"
                },
                "endangerment":{
                    "type":"string",
                    "description":"one of 'poplave', 'pozar', 'plazovi' or 'potres' based on which one you want"
                },
                "k":{
                    "type":"integer",
                    "description":"how many of the top element you get. If left empty, it returns all that have the max value"
                }
            },
            "required": ["isRegija", "regija", "endangerment"],
        }
    },
    {
        "name" : "get_info_by_eid",
        "description": "returns the information about a specific object based on its eid. You can also specify which columns you want",
        "input_schema":{
            "type" : "object",
            "properties": {
                "id":{
                    "type":"string",
                    "description":"the id for which you want info"
                },
                "columns":{
                    "type":"array",
                    "items":{
                        "type":"string"
                    },
                    "description": """name of the columns you want to get. Choose from: 'ESD', 'EID', 'IME', 'SINONIMI', 'OPIS', 'ZVRST', 'TIP', 'GESLA',
       'DATACIJA', 'LOKACIJAOPIS', 'OBCINA', 'ZAVOD', 'USMERITVE', 'STATUS',
       'PREDPIS', 'PREDPISHTTP', 'VELJAVNOST',
       'POVEZAVA1', 'SPOMENIK', 'OBCINAID', 'X', 'Y', 'PHOTOURL',
       'poplave_ocena', 'poplave', 'pozar', 'plazovi', 'regija', 'UE_UIME',
       'potres', 'geometry'"""
                }
            },
            "required":["id"]
        }
    }
]


def top_k_endangered_in_region(isRegija, regija, endangerment,k=-1):
    stolpec = "regija" if isRegija else "OBCINA"
    new = gdf[gdf[stolpec]==regija]

    if k == -1:
        new = new[new[endangerment] == new[endangerment].max()]
    else:
        new = new.nlargest(k, endangerment)

    return new["EID"].to_list()

print(gdf[gdf["OBCINA"]=="LJUBLJANA"]["poplave"].value_counts())

def get_info_by_eid(eid, columns=None):
    ret = gdf[gdf["EID"]==eid].iloc[0]
    if columns is not None:
        ret = ret[columns]

    return ret


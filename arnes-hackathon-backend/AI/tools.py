import geopandas as gpd
import json
import os
from pathlib import Path
from dotenv import load_dotenv
from openai import OpenAI

DATA_DIR = Path(__file__).parent 
load_dotenv()
DEFAULT_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o") #za testiranje spreminjamo model v `.env` da ni treba spreminjat kode

client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])
gdf = gpd.read_file(DATA_DIR / "kd_z_nevarnost.geojson")

TOOLS = [
    {
        "type": "function",
        "name": "top_k_endangered_in_region",
        "description": "Returns a list of the top k endangered objects in a region of a certain type of endangerment.",
        "parameters": {
            "type": "object",
            "properties": {
                "isRegija": {
                    "type": "boolean",
                    "description": "True to filter by regija/region, False to filter by municipality/OBCINA"
                },
                "regija": {
                    "type": "string",
                    "description": "The region or municipality to filter by. Municipalities are ALL UPPERCASE, regions have First Letter Uppercase."
                },
                "endangerment": {
                    "type": "string",
                    "enum": ["poplave", "pozar", "plazovi", "potres"],
                    "description": "The type of endangerment to rank by."
                },
                "k": {
                    "type": "integer",
                    "description": "How many top results to return. If omitted, returns all with the max value."
                }
            },
            "required": ["isRegija", "regija", "endangerment"],
            "additionalProperties": False
        },
        "strict": False
    },
    {
        "type": "function",
        "name": "get_info_by_eid",
        "description": "Returns information about a specific cultural heritage object by its EID.",
        "parameters": {
            "type": "object",
            "properties": {
                "eid": {
                    "type": "string",
                    "description": "The EID of the object."
                },
                "columns": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Columns to return."
                }
            },
            "required": ["eid"],
            "additionalProperties": False
        },
        "strict": False
    },
    {
        "type": "web_search_preview"
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


def get_info_by_eid(eid, columns=None):
    ret = gdf[gdf["EID"]==eid].iloc[0]
    if columns is not None:
        ret = ret[columns]

    return ret.to_dict()

def dispatch_tool(name, args):
    if name == "top_k_endangered_in_region":
        result = top_k_endangered_in_region(**args)
    elif name == "get_info_by_eid":
        result = get_info_by_eid(**args)
    else:
        raise ValueError(f"Unknown tool: {name}")
    return result

#------------------------------------------------------------------------
conversation_history = []
#openai api code 
def run(user_message, model=None):
    model = model or DEFAULT_MODEL
    conversation_history.append({"role":"user", "content":user_message})

    for x in range(15):             #for loop just for loop safety. In general its while True:
        response = client.responses.create(
            model=model,
            tools=TOOLS,
            input=conversation_history
        )

        conversation_history.append({"role":"assistant", "content":response.output})

        tool_calls = [item for item in response.output if item.type == "function_call"]

        if not tool_calls:
            for item in response.output:
                if item.type == "message":
                    for block in item.content:
                        if block.type == "output_text":
                            return block.text
            
            return ""

        for call in tool_calls:
            args = json.loads(call.arguments)
            print(f"[tool] {call.name} ({args})")

            try: 
                result = dispatch_tool(call.name, args)
                output = json.dumps(result, ensure_ascii=False, default=str)
            except Exception as e:
                output = json.dumps({"error": str(e)})

            conversation_history.append({
                "type": "function_call_output",
                "call_id": call.call_id,
                "output": output
            })

#gemini api code
"""
def run(user_message: str, model: str = "gemini-2.0-flash"):
    conversation_history.append({"role": "user", "content": user_message})

    while True:
        response = client.chat.completions.create(
            model=model,
            tools=TOOLS,
            messages=conversation_history,
        )

        message = response.choices[0].message
        conversation_history.append(message)

        if not message.tool_calls:
            return message.content

        for call in message.tool_calls:
            args = json.loads(call.function.arguments)
            print(f"[tool] {call.function.name}({args})")
            try:
                result = dispatch_tool(call.function.name, args)
                output = json.dumps(result, ensure_ascii=False, default=str)
            except Exception as e:
                output = json.dumps({"error": str(e)})

            conversation_history.append({
                "role": "tool",
                "tool_call_id": call.id,
                "content": output,
            })

"""
#-----------------------------------------------------
if __name__ == "__main__":
    answer = run(
        """Kateri spomeniki v komendi so najbolj ogroženi zaradi poplav.
        Poišči po internetu za nedavne poplave v tem okolju in pripni vire"""
    )
    print(answer)

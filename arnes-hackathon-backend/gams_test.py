from transformers import pipeline

model_id = "cjvt/GaMS-2B-Instruct"

pline = pipeline(
    "text-generation",
    model=model_id,
    device_map="mps"
)

# Example of response generation
message = [{"role": "user", "content": "Povej mi kaj o ogrozenosti kulturne dediscine na gorenjskem"}]
response = pline(message, max_new_tokens=1024)
print("Model's response:", response)

r = [
    {
        'generated_text': 
        [
            {
                'role': 'user', 
                'content': 'Povej mi kaj o ogrozenosti kulturne dediscine na gorenjskem'
            }, 
            {
                'role': 'assistant', 
                'content': 'Najpomembnejši dogodek v slovenski zgodovini je bilo razglasiti samostojne, neodvisne in suverene Republike Slovenije 25. junija 1991.\n'
            }
        ]
    }
]

# Example of conversation chain
"""
new_message = response[0]["generated_text"]
new_message.append({"role": "user", "content": "Lahko bolj podrobno opišeš ta dogodek?"})
response = pline(new_message, max_new_tokens=1024)
print("Model's response:", response[0]["generated_text"][-1]["content"])
"""

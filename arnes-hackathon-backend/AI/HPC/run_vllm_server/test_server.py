from openai import OpenAI

# Initialize the client to point to the local vLLM server
def get_client(server_ip):
    return OpenAI(
        base_url=f"http://{server_ip}/v1",
        api_key="EMPTY",
    )

def test_prompt(prompt, client, model_name):
    messages = [
        {"role": "user", "content": prompt},
    ]

    try:
        response = client.chat.completions.create(
            model=model_name,
            messages=messages,
            temperature=0.6,
            top_p=0.95
        )
    except Exception as e:
        print(e)

    print(response)

    output = response.choices[0].message.content

    print("-"*30)
    print("Uporabnik:", prompt)
    print()
    print("Asistent:", output)
    print("-"*30)

def test_vllm_server(client, model_name="facebook/opt-125m"):
    prompts = [
        "Kdo je bolj sposoben za menjavo žarnice - žirafa ali politik?",
        "Povzemi naslednji odstavek.\nKot je ob tem povedal evropski komisar za obrambo Andrius Kubilius, EU ta načrt potrebuje, ker da obveščevalni podatki nekaterih članic kažejo, da bi lahko ruski predsednik Vladimir Putin delovanje zahodne kolektivne obrambe preizkusil že pred letom 2030.",
        "Ali lahko dam zarečeni kruh v gibanico?",
        "Napiši mi recept za prekmursko gibanico.",
        "Ali poznaš pesem V dolini tihi?",
        "Prevedi v slovenščino.\nThe renewed ground offensive came after Israel pounded Gaza with airstrikes overnight into Tuesday, killing more than 400 people, according to Gaza’s Health Ministry, in one of the war’s deadliest days.\n\nEarlier Wednesday, thousands descended on Israeli’s parliament in Jerusalem in mass anti-government protests sparked by Prime Minister Benjamin Netanyahu’s decision to renew the war in Gaza, which critics say was taken to shore up his shaky coalition.",
        "Napiši mi pesem o pomladi."
    ]
    for prompt in prompts:
        test_prompt(prompt, client, model_name)

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", type=str, default="/models/GaMS3-12B-Instruct")
    parser.add_argument("--server_ip", type=str, required=True)
    args = parser.parse_args()
    client = get_client(args.server_ip)
    test_vllm_server(client, args.model)

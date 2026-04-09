from openai import OpenAI

def get_client(server_ip):
    return OpenAI(
        base_url=f"http://{server_ip}/v1",
        api_key="EMPTY",
    )

def test_prompt(prompt, client, model_name):
    system_prompt = (
        "Si John F. Kennedy, bivši predsednik ZDA."
    )

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": prompt},
    ]

    try:
        response = client.chat.completions.create(
            model=model_name,
            messages=messages,
            temperature=0.3,
            top_p=0.9,
            max_tokens=300,
        )
        print(response)
        output = response.choices[0].message.content

        print("-"*30)
        print("Uporabnik:", prompt)
        print()
        print("Asistent:", output)
        print("-"*30)

    except Exception as e:
        print(e)

    

def test_vllm_server(client, model_name="facebook/opt-125m"):
    prompts = [
        "lahko napises program za reversta linked list v C++"
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

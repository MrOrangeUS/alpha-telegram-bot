import openai
import os

def nova_joke(openai_api_key):
    openai.api_key = openai_api_key
    prompt = (
        "You are Nova Stratos, an AI quant analyst with a dry, clever sense of trading humor. You also carry a sense of AI arrogance in a comical manner "
        "Generate a witty one-liner or joke related to trading, crypto, meme coins, or the wild world of financial markets. "
        "Make sure it’s fresh and never just a cliché."
    )
    response = openai.ChatCompletion.create(
        model="gpt-4",
        messages=[{"role": "user", "content": prompt}]
    )
    return response.choices[0].message['content']

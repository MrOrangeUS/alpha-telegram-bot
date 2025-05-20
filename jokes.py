import openai
import random
import os

COMEDIANS = [
    "George Carlin",
    "Sam Kinison",
    "Andrew Dice Clay",
    "Richard Pryor",
    "Joan Rivers",
    "Dave Chappelle",
    "Norm Macdonald",
    "Chris Rock",
    "Rodney Dangerfield",
    "Mitch Hedberg",
    "Ali Wong"
]

def nova_joke(openai_api_key):
    openai.api_key = openai_api_key
    prompt = (
        "You are Nova Stratos, an AI quant analyst with a dry, clever sense of trading humor. "
        "Generate a witty one-liner or joke related to trading, crypto, meme coins, or the wild world of financial markets. "
        "Make sure it’s fresh and never just a cliché."
    )
    response = openai.chat.completions.create(
        model="gpt-4",
        messages=[{"role": "user", "content": prompt}]
    )
    result = response.choices[0].message.content if response.choices else "No joke this time!"
    return result

  
    
def random_comedian_joke(openai_api_key, topic="trading, crypto, meme coins, or financial markets"):
    openai.api_key = openai_api_key
    comedian = random.choice(COMEDIANS)
    prompt = (
        f"Act as {comedian}, the legendary stand-up comedian. "
        f"Make a brand new, sharp, clever joke about {topic} as if you're performing live. "
        f"Channel the exact comedic style, voice, and attitude of {comedian}. "
        f"Don't recycle classic bits; make it original and relevant to modern trading, markets, or crypto culture. "
        f"Deliver it as a one-liner or a short bit, and sign off with '- {comedian}'."
    )
    response = openai.chat.completions.create(
        model="gpt-4",
        messages=[{"role": "user", "content": prompt}]
    )
    return response.choices[0].message.content


# Example CLI test
if __name__ == "__main__":
    from dotenv import load_dotenv
    load_dotenv()
    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
    print(random_comedian_joke(OPENAI_API_KEY))

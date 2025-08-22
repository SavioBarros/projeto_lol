import asyncio
import os
from src.engine import OpeningEngine
# main.py

from dotenv import load_dotenv
import asyncio
from src.engine import OpeningEngine 

# Adicione esta linha para carregar o arquivo .env
load_dotenv() 

print(f"Token da PandaScore carregado: {os.getenv('PANDASCORE_TOKEN')}")

if __name__ == "__main__":
    asyncio.run(OpeningEngine().run())

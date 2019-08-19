import json, logging, os
from core.bots import ScraperBot

format = "%(asctime)s [%(name)s:%(threadName)s] - %(levelname)s: %(message)s"
logging.basicConfig(filename="app.log",
                    level=logging.INFO,
                    format=format)
logger = logging.getLogger(__name__)

logger.info("\n\n/-------------------- STARTING --------------------/")

bots = []
with open('.credentials.json') as creds:
    credentials = json.load(creds)

for index, credential in enumerate(credentials):
    logger.info(f"Creating Bot-{index+1}")
    bots.append(ScraperBot(
        index+1,
        credential['username'],
        credential['password']
    ))

#bots[0]._get_followers("lilkusin")

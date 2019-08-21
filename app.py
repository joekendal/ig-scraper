import json, logging, datetime
from core.bots import ScraperBot

format = "%(asctime)s [%(name)s:%(threadName)s] - %(levelname)s: %(message)s"
logging.basicConfig(filename="app.log",
                    level=logging.INFO,
                    format=format)
logger = logging.getLogger(__name__)

logger.info("\n\n/-------------------- STARTING --------------------/")
start_time = datetime.datetime.now()
print(start_time)
bots = []
with open('.credentials.json') as creds:
    credentials = json.load(creds)

# for index, credential in enumerate(credentials):
#     logger.info(f"Creating Bot-{index+1}")
#     bots.append(ScraperBot(
#         index+1,
#         credential['username'],
#         credential['password']
#     ))

for i in range(1):
    logger.info(f"Creating Bot-{i+1}")
    bots.append(ScraperBot(
        i+1
    ))

#bots[1]._get_followers("fannyamandanilsson")

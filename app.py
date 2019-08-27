import json, logging, datetime, os, redis
from core.bots import AuthScraperBot

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

for index, credential in enumerate(credentials):
    logger.info(f"Creating Bot-{index+1}")
    bots.append(AuthScraperBot(
        index+1,
        credential['username'],
        credential['password']
    ))

def add_followers(username):
    r = redis.Redis(db=0)
    data = {
        'scrape_type': 'followers',
        'username': username
    }
    r.lpush('queue:scrape', json.dumps(data))


#add_followers('fannyamandanilsson')

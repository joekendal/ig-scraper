import json, logging, datetime, os, redis
from core.bots import AuthScraperBot

format = "%(asctime)s [%(name)s:%(threadName)s] - %(levelname)s: %(message)s"
logging.basicConfig(filename="app.log",
                    level=logging.INFO,
                    format=format)
logger = logging.getLogger(__name__)

logger.info("\n\n/-------------------- STARTING --------------------/")
start_time = datetime.datetime.now()
#print(start_time)
bots = []
r = redis.Redis(db=0)

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

    data = {
        'scrape_type': 'followers',
        'username': username
    }
    r.lpush('queue:scrape', json.dumps(data))

def scrape_user(username):
    data = {
        'scrape_type': 'deep',
        'username': username
    }
    r.lpush('queue:scrape', json.dumps(data))



#add_followers('fannyamandanilsson')
#scrape_user('kimkardashian')

def get_comments(shortcode, end_cursor=''):
    comments = list(bots[0].scraper.query_comments_gen(shortcode, end_cursor))
    #print(comments)
    print(len(comments))


#get_comments('B1xBhpGphHm')
# bots[0]._deep_scrape('fannyamandanilsson')
bots[0]._get_stories('bellahadid')

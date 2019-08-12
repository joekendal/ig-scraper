import json

from core.bots import ScraperBot


bots = []
with open('.credentials.json') as creds:
    credentials = json.load(creds)
for index, credential in enumerate(credentials):
    bots.append(ScraperBot(
        index+1,
        credential['username'],
        credential['password']
    ))
    bots[index]._get_followers("")
    quit()

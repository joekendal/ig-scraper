import threading, logging, time, sys, os, json

sys.path.insert(0, os.getcwd())
from core.api import InstagramAPI
from core.api.AWS import EC2Proxy


class ScraperBot():

    def __init__(self, id, username, password):
        self.id = id
        self.proxy_server = EC2Proxy(id=self.id)
        self.api = InstagramAPI(id=id, username=username, password=password)
        self.api.login()


if __name__ == "__main__":
    bots = []
    with open('.credentials.json') as creds:
        credentials = json.load(creds)
    for index, credential in enumerate(credentials):
        bots.append(ScraperBot(
            index+1,
            credential['username'],
            credential['password']
        ))

    # bot1.proxy_server.change_ip_address()
    for bot in bots:
        bot.proxy_server.close()

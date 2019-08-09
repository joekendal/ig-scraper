import threading, logging, time, sys, os, json

sys.path.insert(0, os.getcwd())
from core.api.InstagramAPI import InstagramAPI
from core.api.InstagramScraper import InstagramScraper
from core.api.AWS import EC2Proxy


class ScraperBot():

    def __init__(self, id, username, password):
        self.id = id
        self.proxy_server = EC2Proxy(id=self.id)
        proxies = dict(http=f'socks5h://127.0.0.1:{self.id+1080}',
                       https=f'socks5h://127.0.0.1:{self.id+1080}')

        self.api = InstagramAPI(proxies=proxies, username=username, password=password)
        self.scraper = InstagramScraper(proxies=proxies, login_user=username, login_pass=password)
        self.__login()


    def __login(self):
        print("Logging in...")
        self.api.login()
        self.scraper.authenticate_with_login()
        if not self.api.isLoggedIn or not self.scraper.logged_in:
            print("Changing IP address")
            self.proxy_server.change_ip_address()
            time.sleep(3)
            self.api.login()
            self.scraper.authenticate_with_login()
            if not self.api.isLoggedIn or not self.scraper.logged_in:
                print("Could not log in")
                quit()


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
    # for bot in bots:
    #     bot.proxy_server.close()

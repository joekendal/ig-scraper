import threading, logging, time, sys, os, json, datetime, atexit, logging
import redis

from core import threaded, colours

from core.api.InstagramAPI import InstagramAPI
from core.api.InstagramScraper import InstagramScraper
from core.api.AWS import EC2Proxy

from core.db.models import User, Business, ProfilePicture


class ScraperBot():
    """
    High-level API bootstrapping InstagramAPI-python and InstagramScraper
        1: https://github.com/LevPasha/Instagram-API-python
        2: https://github.com/rarcega/instagram-scraper
    """

    def __init__(self, id, username, password):
        self.id = id
        self.username = username
        self.log = logging.getLogger(__name__)

        self.proxy_server = EC2Proxy(id=self.id, log=self.log)
        proxies = dict(http=f'socks5h://127.0.0.1:{self.id+1080}',
                       https=f'socks5h://127.0.0.1:{self.id+1080}')

        self.api = InstagramAPI(proxies=proxies, username=username, password=password, log=self.log)
        self.scraper = InstagramScraper(proxies=proxies, login_user=username, login_pass=password, log=self.log)
        self.__login()

        self.quit = False
        atexit.register(self.terminate)
        self.lock = threading.RLock
        self.r = redis.Redis(db=0)
        self.__process_queue()


    def __login(self):
        """
        Attempts to log in from proxy. If it fails then retry
        from new IP address. If second attempt fails, quits.
        """
        self.log.info(f"Logging in {self.username}...")
        self.api.login()
        self.scraper.authenticate_with_login()
        if not self.api.isLoggedIn or not self.scraper.logged_in:
            self.log.warning("Changing IP address")
            self.proxy_server.change_ip_address()
            time.sleep(3)
            self.api.login()
            self.scraper.authenticate_with_login()
            if not self.api.isLoggedIn or not self.scraper.logged_in:
                self.log.critical("Could not log in")
                quit()

    def __get_user_info(self, username):
        """
        Uses scraper to get user metadata from
        the public Instagram API (Facebook GraphQL).
        `Required`
        :param str username     Instagram username
        """
        url = "https://www.instagram.com/{0}?__a=1".format(username)
        resp = self.scraper.get_json(url)
        if resp is None:
            self.log.error('Error getting user info for {0}'.format(username))
            return

        user_info = json.loads(resp)['graphql']['user']
        return user_info

    def _get_followers(self, username):
        """
        Get followers list from Instagram and
        update database if necessary.
        `Required`
        :param str username     Instagram username
        """
        user = User.match_username(username) or Business.match_username(username)
        if user:
            user_id = user.user_id
        else:
            with self.lock(): # IMPORTANT! Pause queue processing thread
                #print("INTERUPT lock!")
                user = self._scrape_user(username, returns="user_id")
                user_id = user.user_id
                #print("LOCK CLOSED")

        self.log.info("Getting followers")
        followers = []
        next_max_id = True
        while next_max_id:
            # First iteration
            if next_max_id is True: next_max_id = ''
            # Pagination of followers
            _ = self.api.getUserFollowers(user_id, maxid=next_max_id)
            result = self.api.LastJson.get('users', [])
            followers.extend(result)
            self._add_followers(user, result)
            next_max_id = self.api.LastJson.get('next_max_id', '')

        return followers

    @threaded
    def _add_followers(self, user, followers):
        """
        Adds followers to given user. Saves to database if node doesn't exist.
        If node already exists, update relationship between user and follower.
        `Required`
        :param obj  user        User object
        :param list followers   List of JSON from InstagramAPI getUserFollowers()
        """
        local = threading.local()
        for follower in followers:
            local.found = User.match_username(follower['username']) or Business.match_username(follower['username'])
            if not local.found:
                local.new_user = User(
                    user_id=follower['pk'], is_private=follower['is_private'],
                    full_name=follower['full_name'], username=follower['username'],
                    is_verified=follower['is_verified']
                ).save()
                if follower['has_anonymous_profile_picture'] is False:
                    local.new_profile_pic = ProfilePicture(
                        profile_pic_url=follower['profile_pic_url']
                    ).save()
                    local.new_user.profile_pic.connect(local.new_profile_pic)
                local.new_user.following.connect(user)
                local.data = {
                    'scrape_type': 'basic',
                    'username': local.new_user.username
                }
                self.r.rpush('queue:scrape', json.dumps(local.data))

            else:
                local.found.following.connect(user)


    def _scrape_user(self, username, returns=False):
        """
        Task must not be added to queue or consumer thread must be
        locked to prevent wrong data stored in self.scraper.get result
        `Required`
        :param str  username    Instagram username
        `Optional`
        :param str  returns     User graphql attribute to return
        """
        self.log.info(f"Scraping user {username}")
        user_info = self.__get_user_info(username)
        user = User.match_username(username) or Business.match_username(username)
        if not user:
            # Create new user
            if user_info['is_business_account'] is False:
                user = User(user_id=user_info['id'], full_name=user_info['full_name'],
                        username=username, bio=user_info['biography'],
                        external_url=user_info['external_url'],
                        is_private=user_info['is_private'],
                        connected_fb_page=user_info['connected_fb_page'],
                        last_scraped_timestamp=datetime.datetime.utcnow()
                        ).save()
            else:
                user = Business(external_url=user_info['external_url'],
                    business_category_name=user_info['business_category_name'],
                    user_id=user_info['id'], username=username, bio=user_info['biography'],
                    full_name=user_info['full_name'], is_private=user_info['is_private'],
                    connected_fb_page=user_info['connected_fb_page'],
                    last_scraped_timestamp=datetime.datetime.utcnow()
                ).save()
        else:
            # Update user records
            user.bio = user_info['biography']
            user.external_url = user_info['external_url']
            user.connected_fb_page = user_info['connected_fb_page'],
            user.last_scraped_timestamp=datetime.datetime.utcnow()
            if user_info['is_business_account']:
                user.business_category_name = user_info['business_category_name']
            user.save()

        # Add profile picture if URL isn't saved
        if not user.profile_pic.search(profile_pic_url=user_info['profile_pic_url']):
            profile_picture = ProfilePicture(
                profile_pic_url = user_info['profile_pic_url'],
                profile_pic_url_hd = user_info['profile_pic_url_hd']
            ).save()
            user.profile_pic.connect(profile_picture)

        if returns:
            return user

    @threaded
    def __process_queue(self):
        while True:
            if self.quit is True: break
            packed = self.r.blpop(['queue:scrape'], 30)
            if not packed:
                continue
            data = json.loads(packed[1])
            if data['scrape_type'] == 'basic':
                self._scrape_user(data['username'])

    def terminate(self):
        self.quit = True

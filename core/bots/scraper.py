import threading, logging, time, sys, os, json, datetime, atexit, logging, requests, datetime
import redis

from neomodel import db

from core import colours
from core.bots import threaded
from core.api.InstagramAPI import InstagramAPI
from core.api.InstagramScraper import InstagramScraper
from core.api.AWS import EC2Proxy

from core.db.models import (User, Business, ProfilePicture, Picture, Sidecar,
                            Video, IGTV, Hashtag)


class AuthScraperBot():
    """
    High-level API bootstrapping InstagramAPI-python and InstagramScraper
        1: https://github.com/LevPasha/Instagram-API-python
        2: https://github.com/rarcega/instagram-scraper
    """

    def __init__(self, id, username, password):
        self.id = id
        self.type = "Auth"
        self.username = username
        self.log = logging.getLogger(__name__)
        self.proxy_server = EC2Proxy(id=self.id, log=self.log)
        self.proxies = dict(http=f'socks5h://127.0.0.1:{self.id+1080}',
                       https=f'socks5h://127.0.0.1:{self.id+1080}')

        self.api = InstagramAPI(proxies=self.proxies, username=username, password=password, log=self.log)
        self._api_busy = False

        self.scraper = InstagramScraper(proxies=self.proxies, login_user=username, login_pass=password, log=self.log)

        self.quit = False
        atexit.register(self.terminate)
        self.lock = threading.RLock
        self.r = redis.Redis(db=0)

        self.start()

    def start(self):
        self.__authenticate()
        self.__process_queue()


    def __rotate_ec2(self):
        self.log.warning("Changing IP address")
        self.proxy_server.change_ip_address()
        time.sleep(3)

    def __authenticate(self):
        """
        Attempts to log in from proxy. If it fails then retry
        from new IP address. If second attempt fails, quits.
        """
        self.log.info(f"Logging in {self.username}...")
        try:
            self.api.login()
            self.scraper.authenticate_with_login()
        except:
            self.log.critical(f"Could not authenticate")
            self.terminate()
            quit()

    def __get_user_info(self, username):
        """
        Uses scraper to get user metadata from
        the public Instagram endpoint (Facebook GraphQL).
        `Required`
        :param str username     Instagram username
        """
        url = "https://www.instagram.com/{0}/?__a=1".format(username)
        resp = self.scraper.get_json(url)
        if resp is None: return resp
        user_info = json.loads(resp)['graphql']['user']
        return user_info

    def _scrape_user(self, username, mode='basic', returns=False):
        """
        Task must not be added to queue or consumer thread must be
        locked to prevent wrong data stored in self.scraper.get result
        `Required`
        :param str  username    Instagram username
        `Optional`
        :param str  mode        Basic or deep scrape
        :param bool  returns     User graphql attribute to return
        """
        self.log.info(f"Scraping user {username}")

        user_info = self.__get_user_info(username)
        if not user_info:
            self.log.info(f"No user data found for @{username}")
            return
        with db.read_transaction:
            user = User.match_username(username) or Business.match_username(username)
        if not user:
            # Create new user
            if user_info['is_business_account'] is False:
                if user_info['country_block'] is True:
                    self.log.warning(f"@{username} has country block!")
                with db.write_transaction:
                    user = User(user_id=user_info['id'], full_name=user_info['full_name'],
                            username=username, bio=user_info['biography'],
                            external_url=user_info['external_url'],
                            is_private=user_info['is_private'],
                            connected_fb_page=user_info['connected_fb_page'],
                            last_scraped_timestamp=datetime.datetime.utcnow(),
                            edge_following_count=user_info['edge_follow']['count'],
                            edge_followers_count=user_info['edge_followed_by']['count'],
                            has_channel=user_info['has_channel'],
                            country_block=user_info['country_block'],
                            joined_recently=user_info['is_joined_recently'],
                            edge_timeline_media_count=user_info['edge_owner_to_timeline_media']['count']
                            ).save()
            else:
                with db.write_transaction:
                    user = Business(external_url=user_info['external_url'],
                        business_category_name=user_info['business_category_name'],
                        user_id=user_info['id'], username=username, bio=user_info['biography'],
                        full_name=user_info['full_name'], is_private=user_info['is_private'],
                        connected_fb_page=user_info['connected_fb_page'],
                        last_scraped_timestamp=datetime.datetime.utcnow(),
                        edge_following_count=user_info['edge_follow']['count'],
                        edge_followers_count=user_info['edge_followed_by']['count'],
                        has_channel=user_info['has_channel'],
                        country_block=user_info['country_block'],
                        joined_recently=user_info['is_joined_recently'],
                        edge_timeline_media_count=user_info['edge_owner_to_timeline_media']['count']
                    ).save()
        else:
            # Update user records
            user.bio = user_info['biography']
            user.external_url = user_info['external_url']
            user.connected_fb_page = user_info['connected_fb_page']
            user.last_scraped_timestamp=datetime.datetime.utcnow()
            user.edge_following_count=user_info['edge_follow']['count']
            user.edge_followers_count=user_info['edge_followed_by']['count']
            user.has_channel=user_info['has_channel']
            user.country_block=user_info['country_block']
            user.joined_recently=user_info['is_joined_recently']
            if user_info['is_business_account']:
                user.business_category_name = user_info['business_category_name']
            with db.write_transaction:
                user.save()

        # Add profile picture if URL isn't saved
        with db.read_transaction:
            profile_pic_found = user.profile_pic.search(profile_pic_url=user_info['profile_pic_url'])
        if not profile_pic_found:
            with db.write_transaction:
                profile_picture = ProfilePicture(
                    profile_pic_url = user_info['profile_pic_url'],
                    profile_pic_url_hd = user_info['profile_pic_url_hd']
                ).save()
                user.profile_pic.connect(profile_picture)

        # Add graph media if not exists
        for item in user_info['edge_owner_to_timeline_media']['edges']:
            node = item['node']
            with db.read_transaction:
                if node['__typename'] == 'GraphImage':
                    found = Picture.nodes.first_or_none(media_id=node['id'])
                elif node['__typename'] == 'GraphVideo':
                    if node.get('product_type', '') == 'igtv':
                        found = IGTV.nodes.first_or_none(media_id=node['id'])
                    else:
                        found = Video.nodes.first_or_none(media_id=node['id'])
                elif node['__typename'] == 'GraphSidecar':
                    found = Sidecar.nodes.first_or_none(media_id=node['id'])

            if found: break

            if node['edge_media_to_caption']['edges']:
                caption = node['edge_media_to_caption']['edges'][0]['node']['text']
            else:
                caption = None

            hashtags = self.scraper.extract_tags(node).get('tags')

            if node['__typename'] == 'GraphImage':
                with db.write_transaction:
                    taken_at = datetime.datetime.fromtimestamp(node['taken_at_timestamp'])
                    new_media = Picture(
                        media_id=node['id'],
                        caption=caption,
                        shortcode=node['shortcode'],
                        edge_comments_count=node['edge_media_to_comment']['count'],
                        comments_disabled=node['comments_disabled'],
                        taken_at=taken_at,
                        display_url=node['display_url'],
                        edge_liked_by_count=node['edge_liked_by']['count'],
                        location=node['location'],
                        accessibility_caption=node['accessibility_caption']
                    ).save()
                    user.picture_posts.connect(new_media, {'on_timestamp': taken_at})
            elif mode == 'deep' and node['__typename'] == 'GraphSidecar':
                # TODO:
                pass
            elif mode == 'deep' and node['__typename'] == 'GraphVideo':
                # TODO:
                pass

            if hashtags:
                for hashtag in hashtags:
                    with db.read_transaction:
                        tag_object = Hashtag.nodes.first_or_none(name=hashtag)
                    if not tag_object:
                        with db.write_transaction:
                            tag_object = Hashtag(name=hashtag).save()
                    with db.write_transaction:
                        new_media.hashtags.connect(tag_object)

        if returns:
            return user

    def _get_followers(self, username):
        """
        Get followers list from Instagram and
        update database if necessary.
        `Required`
        :param str username     Instagram username
        """
        self.log.info("Fetching followers for %s" % username)
        with db.read_transaction:
            user = User.match_username(username) or Business.match_username(username)
        if user:
            user_id = user.user_id
        else:
            with self.lock(): # IMPORTANT! Pause queue processing thread
                user = self._scrape_user(username, returns="user_id")
                user_id = user.user_id

        self.log.info("Getting followers")
        self._api_busy = True
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
        self._api_busy = False

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
            with db.read_transaction:
                local.found = User.match_username(follower['username']) or Business.match_username(follower['username'])
            if not local.found:
                with db.write_transaction:
                    local.new_user = User(
                        user_id=follower['pk'], is_private=follower['is_private'],
                        full_name=follower['full_name'], username=follower['username'],
                        is_verified=follower['is_verified']
                    ).save()
                if follower['has_anonymous_profile_picture'] is False:
                    with db.write_transaction:
                        local.new_profile_pic = ProfilePicture(
                            profile_pic_url=follower['profile_pic_url']
                        ).save()
                        local.new_user.profile_pic.connect(local.new_profile_pic)
                with db.write_transaction:
                    local.new_user.following.connect(user)
                local.data = {
                    'scrape_type': 'basic',
                    'username': local.new_user.username
                }
                self.r.rpush('queue:scrape', json.dumps(local.data))
                local.data = {
                    'scrape_type': 'following',
                    'username': local.new_user.username
                }
                self.r.rpush('queue:scrape', json.dumps(local.data))
            else:
                with db.transaction:
                    local.found.following.connect(user)

    def _get_following(self, username):
        with db.read_transaction:
            user = User.match_username(username) or Business.match_username(username)
        if user:
            user_id = user.user_id
        else:
            with self.lock():
                user = self._scrape_user(username, returns="user_id")
                user_id = user.user_id
        self.log.info(f"Getting {username}'s following")
        self._api_busy = True
        following = []
        next_max_id = True
        while next_max_id:
            if next_max_id is True: next_max_id = ''
            _ = self.api.getUserFollowings(user_id, maxid=next_max_id)
            result = self.api.LastJson.get('users', [])
            following.extend(result)
            self._add_following(user, result)
            next_max_id = self.api.LastJson.get('next_max_id', '')
        self._api_busy = False

    @threaded
    def _add_following(self, of_user, following):
        local = threading.local()
        for user in following:
            with db.read_transaction:
                local.found = User.match_username(user['username']) or Business.match_username(user['username'])
            if not local.found:
                with db.write_transaction:
                    local.new_user = User(
                        user_id=user['pk'], is_private=user['is_private'],
                        full_name=user['full_name'], username=user['username'],
                        is_verified=user['is_verified']
                    ).save()
                if user['has_anonymous_profile_picture'] is False:
                    with db.write_transaction:
                        local.new_profile_pic = ProfilePicture(
                            profile_pic_url=user['profile_pic_url']
                        ).save()
                        local.new_user.profile_pic.connect(local.new_profile_pic)
                with db.write_transaction:
                    local.new_user.followers.connect(of_user)
                local.data = {
                    'scrape_type': 'basic',
                    'username': local.new_user.username
                }
                self.r.rpush('queue:scrape', json.dumps(local.data))
            else:
                with db.write_transaction:
                    local.found.followers.connect(of_user)

    @threaded
    def __process_queue(self):
        while True:
            if self.quit is True: break
            if self._api_busy is True:
                time.sleep(1)
                continue
            packed = self.r.blpop(['queue:scrape'], 30)
            if not packed: continue
            data = json.loads(packed[1])
            if data['scrape_type'] == 'following':
                try:
                    self._get_following(data['username'])
                except Exception as e:
                    self.log.exception(e)
                    self.r.rpush('queue:scrape', json.dumps(data))
            elif data['scrape_type'] == 'followers':
                try:
                    self._get_followers(data['username'])
                except Exception as e:
                    self.log.exception(e)
                    #self.r.lpush('queue:scrape', json.dumps(data))

            elif data['scrape_type'] in ['basic', 'deep']:
                try:
                    self._scrape_user(data['username'], mode=data['scrape_type'])
                except Exception as e:
                    self.log.exception(e)
                    self.r.rpush('queue:scrape', json.dumps(data))

    def terminate(self):
        self.quit = True

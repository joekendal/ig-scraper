import threading, logging, time, sys, os, json, datetime, atexit, logging, requests, datetime
import redis

from neomodel import db
from neomodel.contrib.spatial_properties import NeomodelPoint
from tqdm import tqdm

from core import colours
from core.bots import threaded
from core.api.InstagramAPI import InstagramAPI
from core.api.InstagramScraper import InstagramScraper
from core.api.AWS import EC2Proxy
from core.db.models import (User, Business, ProfilePicture, Picture, Sidecar,
                            Video, Hashtag, Comment, Location, Media)


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
        Attempts to log in from proxy.
        """
        self.log.info(f"Logging in {self.username}...")
        try:
            self.scraper.authenticate_with_login()
            self.api.login()
        except Exception as e:
            self.log.exception(e)
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

    def _scrape_user(self, username, returns=False):
        """
        Task must not be added to queue or consumer thread must be
        locked to prevent wrong data stored in self.scraper.get result
        `Required`
        :param str  username    Instagram username
        `Optional`
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
            user_kwargs = {
                'user_id': user_info['id'],
                'full_name': user_info['full_name'],
                'username': username,
                'bio': user_info['biography'],
                'external_url': user_info['external_url'],
                'is_private': user_info['is_private'],
                'connected_fb_page': user_info['connected_fb_page'],
                'last_scraped_timestamp': datetime.datetime.utcnow(),
                'edge_following_count': user_info['edge_follow']['count'],
                'edge_followers_count': user_info['edge_followed_by']['count'],
                'has_channel': user_info['has_channel'],
                'country_block': user_info['country_block'],
                'joined_recently': user_info['is_joined_recently'],
                'edge_timeline_media_count': user_info['edge_owner_to_timeline_media']['count']
            }
            if user_info['country_block'] is True:
                self.log.warning(f"@{username} has country block!")
            if user_info['is_business_account'] is True:
                user_kwargs['business_category_name'] = user_info['business_category_name']
                with db.write_transaction:
                    user = Business(**user_kwargs).save()
            else:
                with db.write_transaction:
                    user = User(**user_kwargs).save()
        else:
            if user.last_scraped_timestamp:
                difference = datetime.datetime.now(datetime.timezone.utc) - user.last_scraped_timestamp
                if difference.days < 7:
                    self.log.warning(f"User {username} already scraped in last 7 days... Skipping")
                    return
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
        # for item in user_info['edge_owner_to_timeline_media']['edges']:
        #     node = item['node']
        #     self.__save_media(node, user)
        #
        #     # Tag location
        #     if node['location']:
        #         location = Location.nodes.first_or_none(location_id=node['location']['id'])
        #         if not location:
        #             with db.write_transaction:
        #                 location = Location(
        #                     location_id=node['location']['id'],
        #                     has_public_page=node['location']['has_public_page'],
        #                     name=node['location']['name'],
        #                     slug=node['location']['slug'],
        #                 ).save()
        #             # Scrape location
        #             data = {
        #                 'scrape_type': 'location',
        #                 'location_id': node['location']['id']
        #             }
        #             self.r.rpush('queue:scrape', json.dumps(data))
        #         with db.write_transaction:
        #             location.medias.connect(new_media)


        if returns is True:
            return user

    def __scrape_location(self, location_id):
        self.log.info('Scraping Geolocation...')
        url = "https://www.instagram.com/explore/locations/{0}/?__a=1".format(location_id)
        resp = self.scraper.get_json(url)
        if resp is None: raise
        location_info = json.loads(resp)['graphql']['location']
        kwargs = {
            'location_id': location_info['id'],
            'name': location_info['name'],
            'has_public_page': location_info['has_public_page'],
            'latitude': location_info['lat'],
            'longitude': location_info['lng'],
            'geospatial': NeomodelPoint((location_info['lng'], location_info['lat']), crs='wgs-84'),
            'slug': location_info['slug'],
            'blurb': location_info['blurb'],
            'website': location_info['website'],
            'phone': location_info['phone'],
            'primary_alias_on_fb': location_info['primary_alias_on_fb'],
            'address_json': json.loads(location_info['address_json'])
        }
        with db.read_transaction:
            db_location = Location.nodes.first_or_none(location_id=location_id)
        if not db_location:
            with db.write_transaction:
                db_location = Location(**kwargs).save()
        else:
            db_location.latitude = kwargs['latitude']
            db_location.longitude = kwargs['longitude']
            db_location.geospatial = kwargs['geospatial']
            db_location.blurb = kwargs['blurb']
            db_location.website = kwargs['website']
            db_location.phone = kwargs['phone']
            db_location.primary_alias_on_fb = kwargs['primary_alias_on_fb']
            db_location.address_json = kwargs['address_json']
            with db.write_transaction:
                db_location.save()

        if location_info['profile_pic_url']:
            with db.read_transaction:
                profile_pic_found = db_location.profile_pic.search(profile_pic_url=location_info['profile_pic_url'])
            if not profile_pic_found:
                with db.write_transaction:
                    profile_picture = ProfilePicture(
                        profile_pic_url = location_info['profile_pic_url'],
                    ).save()
                    db_location.profile_pic.connect(profile_picture)

    def _deep_scrape(self, username, post_depth=150, comment_depth=None):
        # Get user if exists
        user = User.match_username(username)
        if not user:
            user = self._scrape_user(username, returns=True)
        new_media = list(self.scraper.query_media_gen(user, max_number=post_depth))
        m_desc = f"Saving {user.username}'s {max_number} most recent posts"
        for media in tqdm(reversed(new_media), desc=m_desc, ascii=False, total=len(new_media)):
            if self.__save_media(media, user) is False: continue
            if media['comments_disabled']: continue
            num_comments = media['edge_media_to_comment']['count']
            c_desc = f"Saving comments for post https://instagram.com/p/{media['shortcode']}/"
            for comment in tqdm(self.scraper.query_comments_gen(media['shortcode'], max_number=comment_depth),
                                total=num_comments, desc=c_desc, ascii=False):
                self.__save_comment(comment, media['id'])


    def __save_media(self, media, user):
        # Check exists
        with db.read_transaction:
            if Media.nodes.first_or_none(shortcode=media['shortcode']): return False

        # Create new
        if media['edge_media_to_caption']['edges']:
            caption = media['edge_media_to_caption']['edges'][0]['node']['text']
        else:
            caption = None
        taken_at = datetime.datetime.fromtimestamp(media['taken_at_timestamp'])
        media_kwargs = {
            'media_id': media['id'],'caption': caption,
            'shortcode': media['shortcode'], 'comments_disabled': media['comments_disabled'],
            'edge_comments_count': media['edge_media_to_comment'].get('count'),
            'display_url': media['display_url'], 'taken_at': taken_at,
            'edge_liked_by_count': media['edge_media_preview_like']['count'],
            'height': media['dimensions']['height'],
            'width': media['dimensions']['width'],
        }
        if media['__typename'] == 'GraphImage':
            with db.write_transaction:
                new_media = Picture(**media_kwargs).save()
        elif media['__typename'] == 'GraphSidecar':
            media_kwargs['urls'] = media['urls']
            with db.write_transaction:
                new_media = Sidecar(**media_kwargs).save()
        elif media['__typename'] == 'GraphVideo':
            media_kwargs['view_count'] = media['video_view_count']
            if media.get('product_type', '') == 'igtv':
                media_kwargs['title'] = media['title']
                media_kwargs['duration'] = media['video_duration']
                media_kwargs['product_type'] = 'igtv'
            else:
                media_kwargs['urls'] = media['urls']
            with db.write_transaction:
                new_media = Video(**media_kwargs).save()
        else:
            return False
        with db.write_transaction:
            user.all_posts.connect(new_media, {'on_timestamp': taken_at})

        self.__save_hashtags(media, new_media)

        return True

    def __save_hashtags(self, node, media):
        hashtags = self.scraper.extract_tags(node).get('tags')
        if hashtags:
            for hashtag in hashtags:
                with db.transaction:
                    tag_object = Hashtag.nodes.first_or_none(name=hashtag)
                    if not tag_object:
                        tag_object = Hashtag(name=hashtag).save()
                    media.hashtags.connect(tag_object)

    def __save_comment(self, comment, media_id):
        with db.read_transaction:
            if Comment.nodes.first_or_none(comment_id=comment['id']): return
            media = Media.nodes.get(media_id=media_id)
        created_at = datetime.datetime.fromtimestamp(comment['created_at'])
        with db.transaction:
            new_comment = Comment(
                comment_id=comment['id'],
                created_at=created_at,
                text=comment['text']
            ).save()
            comment_owner = User.match_username(comment['owner']['username'])
            if not comment_owner:
                comment_owner = User(
                    user_id=comment['owner']['id'],
                    username=comment['owner']['username']
                ).save()
                pp = ProfilePicture(
                    profile_pic_url=comment['owner']['profile_pic_url']
                ).save()
                comment_owner.profile_pic.connect(pp)
            new_comment.owner.connect(comment_owner, {'created_at': created_at})
            media.comments.connect(new_comment)


    def _surface_scrape(self, username):
        def new_user(user_node):
            user = User(
                user_id=user_node['id'],
                is_verified=user_node['is_verified'],
                username=user_node['username'],
                full_name=user_node.get('full_name')
            ).save()
            new_pp = ProfilePicture(
                profile_pic_url=user_node['profile_pic_url']
            ).save()
            user.profile_pic.connect(new_pp)
            return user

        def get_user_tags(node, post):
            tagged_users = node['edge_media_to_tagged_user']['edges']
            if tagged_users:
                for tagged_user in tagged_users:
                    node = tagged_user['node']
                    with db.transaction:
                        user_tagged = User.match_username(node['user']['username'])
                        if not user_tagged:
                            user_tagged = new_user(node['user'])
                        post.tagged_users.connect(user_tagged, {'x': node['x'], 'y': node['y']})

        def get_top_comments(node, post):
            edges = node['edge_media_to_parent_comment']['edges']
            # edges.extend(node['edge_media_preview_comment'].get('edges', []))
            for edge in edges:
                node = edge['node']
                with db.read_transaction:
                    comment = Comment.nodes.first_or_none(comment_id=node['id'])
                if not comment:
                    created_at = datetime.datetime.fromtimestamp(node['created_at'])
                    with db.transaction:
                        new_comment = Comment(
                            comment_id=node['id'], text=node['text'],
                            edge_liked_by_count=node['edge_liked_by']['count'],
                            edge_threaded_comments_count=node['edge_threaded_comments']['count']
                        ).save()
                        comment_owner = User.match_username(node['owner']['username'])
                        if not comment_owner:
                            comment_owner = new_user(node['owner'])
                        new_comment.owner.connect(comment_owner, {'created_at': created_at})
                        post.comments.connect(new_comment)
            post.last_scraped_top_comments = datetime.datetime.now(datetime.timezone.utc)
            with db.write_transaction:
                post.save()

        def get_sponsors(node, post):
            # Add Sponsor(s) if exists
            if node['edge_media_to_sponsor_user']['edges']:
                for edge in node['edge_media_to_sponsor_user']['edges']:
                    node = edge['node']
                    with db.transaction:
                        sponsor = User.match_username(node['sponsor']['username'])
                        if not sponsor:
                            sponsor = User(
                                user_id=node['sponsor']['id'],
                                username=node['sponsor']['username']
                            ).save()
                        post.sponsors.connect(sponsor)

        self.log.info('Deep scraping...')
        with db.read_transaction:
            user = User.match_username(username)
            graphvideos = user.video_posts.filter(url__isnull=True).all()
            carousels = user.carousel_posts.filter(children_count__lte=0).all()
            pictures = user.picture_posts.filter(last_scraped_top_comments__isnull=True).all()
        for post in carousels:

            for index, child in enumerate(node['edge_sidecar_to_children']['edges']):
                node = child['node']
                if node['__typename'] == 'GraphImage':
                    with db.read_transaction:
                        graphimage = Picture.nodes.first_or_none(shortcode=node['shortcode'])
                    if not graphimage:
                        with db.write_transaction:
                            graphimage = Picture(media_id=node['id'],shortcode=node['shortcode'],
                                height=node['dimensions']['height'],width=node['dimensions']['width'],
                                display_url=node['display_url'],accessibility_caption=node['accessibility_caption']
                            ).save()
                        get_user_tags(node, graphimage)
                    with db.write_transaction:
                        post.children.connect(graphimage, {'index': index})
                elif node['__typename'] == 'GraphVideo':
                    with db.read_transaction:
                        graphvideo = Video.nodes.first_or_none(shortcode=node['shortcode'])
                    if not graphvideo:
                        with db.write_transaction:
                            graphvideo = Video(media_id=node['id'],shortcode=node['shortcode'],
                                width=node['dimensions']['width'],height=node['dimensions']['height'],
                                url=node['video_url'],view_count=node['video_view_count']
                            ).save()
                        get_user_tags(node, graphvideo)
                    with db.write_transaction:
                        post.children.connect(graphvideo, {'index': index})

        for post in pictures:
            node = self.scraper._get_media_details(shortcode=post.shortcode)
            get_user_tags(node, post)
            get_top_comments(node, post)
            get_sponsors(node, post)

        #self.__get_stories(user)

    def __get_stories(self, user):
        self.log.info('Fetching stories...')
        stories = self.scraper.fetch_stories(user_id=user.user_id)
        print(stories)


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
        #local = threading.local()
        for user in following:
            with db.read_transaction:
                found = User.match_username(user['username']) or Business.match_username(user['username'])
            if not found:
                with db.write_transaction:
                    new_user = User(
                        user_id=user['pk'], is_private=user['is_private'],
                        full_name=user['full_name'], username=user['username'],
                        is_verified=user['is_verified'],
                        has_anonymous_profile_pic=user['has_anonymous_profile_picture']
                    ).save()
                if user['has_anonymous_profile_picture'] is False:
                    with db.write_transaction:
                        new_profile_pic = ProfilePicture(
                            profile_pic_url=user['profile_pic_url']
                        ).save()
                        new_user.profile_pic.connect(new_profile_pic)
                with db.write_transaction:
                    new_user.followers.connect(of_user)
                data = {
                    'scrape_type': 'basic',
                    'username': new_user.username
                }
                self.r.rpush('queue:scrape', json.dumps(data))
            else:
                with db.write_transaction:
                    found.followers.connect(of_user)


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
                    #self.r.rpush('queue:scrape', json.dumps(data))

            elif data['scrape_type'] == 'followers':
                try:
                    self._get_followers(data['username'])
                except Exception as e:
                    self.log.exception(e)
                    #self.r.lpush('queue:scrape', json.dumps(data))

            elif data['scrape_type'] in ['basic', 'deep']:
                try:
                    self._scrape_user(data['username'])
                    if data['scrape_type'] == 'deep':
                        self._deep_scrape(data['username'])
                except Exception as e:
                    self.log.exception(e)
                    #self.r.rpush('queue:scrape', json.dumps(data))

            elif data['scrape_type'] == 'location':
                try:
                    self.__scrape_location(data['location_id'])
                except Exception as e:
                    self.log.exception(e)
                    #self.r.rpush('queue:scrape', json.dumps(data))


    def terminate(self):
        self.quit = True

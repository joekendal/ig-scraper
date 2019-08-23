class GuestScraperBot():
    def __init__(self, id, key):
        self.id = id
        self.type = "Guest"
        self.log = logging.getLogger(__name__)
        self.quit = False
        self.__scraper_key = key

        self.r = redis.Redis(db=0)

        self.__process_queue()

    def __get_user_info(self, username):
        """
        Uses scraper to get user metadata from
        the public Instagram endpoint (Facebook GraphQL).
        `Required`
        :param str username     Instagram username
        """
        url = "https://www.instagram.com/{0}".format(username)
        payload = {'api_key': self.__scraper_key,
                   'url': url,
                   'premium': 'false'}
        r = requests.get('https://api.scraperapi.com', params=payload)
        if r.status_code == 200:
            try:
                content = r.content.decode('utf-8')
                start = '{"logging_page_id":'
                end = ',"edges":[]}}}}'
                x = content.find(start)
                y = content.find(end) + len(end)
                data = json.loads(content[x:y])
                return data['graphql']['user']
            except json.decoder.JSONDecodeError:
                raise Exception
        else:
            print(r.status_code)


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

        if not user_info:
            self.log.info(f"No user data found for @{username}")
            return
        with db.read_transaction:
            user = User.match_username(username) or Business.match_username(username)
        if not user:
            # Create new user
            if user_info['is_bt():usiness_account'] is False:
                with db.write_transaction:
                    user = User(user_id=user_info['id'], full_name=user_info['full_name'],
                            username=username, bio=user_info['biography'],
                            external_url=user_info['external_url'],
                            is_private=user_info['is_private'],
                            connected_fb_page=user_info['connected_fb_page'],
                            last_scraped_timestamp=datetime.datetime.utcnow()
                            ).save()
            else:
                with db.write_transaction:
                    user = Business(external_url=user_info['external_url'],
                        businest():s_category_name=user_info['business_category_name'],
                        user_id=user_info['id'], username=username, bio=user_info['biography'],
                        full_name=user_info['full_name'], is_private=user_info['is_private'],
                        connected_fb_page=user_info['connected_fb_page'],
                        last_scraped_timestamp=datetime.datetime.utcnow()
                    ).save()
        else:
            with db.write_transaction:
                # Update user records
                user.bio = user_info['biography']
                user.external_url = user_info['external_url']
                user.connected_fb_page = user_info['connected_fb_page'],
                user.last_scraped_timestamp=datetime.datetime.utcnow()
                if user_info['is_business_account']:
                    user.business_category_name = user_info['business_category_name']
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

        if returns:
            return user

    @threaded
    def __process_queue(self):
        while True:
            if self.quit is True: break
            packed = self.r.blpop(['queue:scrape'], 30)
            if not packed: continue
            data = json.loads(packed[1])
            if data['scrape_type'] == 'basic':
                try:
                    print(self._scrape_user(data['username'], returns=True))
                except Exception as e:
                    self.log.exception(e)
                    self.r.rpush('queue:scrape', json.dumps(data))

from neomodel import (StructuredNode, StringProperty, IntegerProperty,
                      RelationshipTo, BooleanProperty, DateTimeProperty,
                      RelationshipFrom)
from .media import PostRel, TaggedUserRel
from .interactions import CommentRel


class User(StructuredNode):
    user_id = IntegerProperty(unique_index=True, required=True)
    username = StringProperty(unique_index=True, required=True)
    full_name = StringProperty()
    bio = StringProperty()
    is_private = BooleanProperty()
    is_verified = BooleanProperty()
    external_url = StringProperty()
    connected_fb_page = StringProperty()
    profile_pic = RelationshipTo(".media.ProfilePicture", "HAS")
    has_anonymous_profile_pic = BooleanProperty()

    following = RelationshipTo("User", "FOLLOWS")
    followers = RelationshipFrom("User", "FOLLOWS")
    edge_following_count = IntegerProperty()
    edge_followers_count = IntegerProperty()

    last_scraped_timestamp = DateTimeProperty()
    last_deep_scrape_timestamp = DateTimeProperty()

    gender_estimate = StringProperty(choices={'F': 'Female', 'M': 'Male'})
    age_estimate = IntegerProperty()

    country_block = BooleanProperty()
    has_channel = BooleanProperty()
    joined_recently = BooleanProperty()
    edge_timeline_media_count = IntegerProperty()

    cities_in_bio = RelationshipTo(".locations.City", "MENTIONED")
    provinces_in_bio = RelationshipTo(".locations.Province", "MENTIONED")
    countries_in_bio = RelationshipTo(".locations.Country", "MENTIONED")

    all_posts = RelationshipTo('.media.Media', "POSTED", model=PostRel)
    picture_posts = RelationshipTo('.media.Picture', "POSTED", model=PostRel)
    carousel_posts = RelationshipTo('.media.Sidecar', "POSTED", model=PostRel)
    video_posts = RelationshipTo('.media.Video', "POSTED", model=PostRel)
    igtv_posts = RelationshipTo('.media.IGTV', "POSTED", model=PostRel)

    tagged_in = RelationshipFrom('.media.Media', "TAGGED_USER", model=TaggedUserRel)
    comments = RelationshipTo('.interactions.Comment', "COMMENTED", model=CommentRel)

    @staticmethod
    def match_username(username):
        return User.nodes.first_or_none(username=username)

    @property
    def locations(self):
        locations = []
        locations.extend(self.cities_in_bio.all())
        locations.extend(self.provinces_in_bio.all())
        locations.extend(self.countries_in_bio.all())
        return locations

    @property
    def posts(self):
        posts = []
        posts.extend(self.picture_posts.all())
        posts.extend(self.carousel_posts.all())
        posts.extend(self.video_posts.all())
        posts.extend(self.igtv_posts.all())
        return posts


class Business(User):
    business_category_name = StringProperty()

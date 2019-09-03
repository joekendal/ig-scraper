from neomodel import (StructuredNode, StringProperty, IntegerProperty,
                      RelationshipTo, BooleanProperty, DateTimeProperty,
                      RelationshipFrom)
from .media import PostRel, TaggedUserRel
from .interactions import CommentRel


class User(StructuredNode):
    user_id = IntegerProperty(index=True)
    username = StringProperty(unique_index=True)
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

    timeline_posts = RelationshipTo('.media.Media', "POSTED", model=PostRel)
    # picture_posts = RelationshipTo('.media.Picture', "POSTED", model=PostRel)
    # carousel_posts = RelationshipTo('.media.Sidecar', "POSTED", model=PostRel)
    # video_posts = RelationshipTo('.media.Video', "POSTED", model=PostRel)

    stories = RelationshipTo('.media.Story', 'POSTED_STORY', model=PostRel)

    tagged_in = RelationshipFrom('.media.Media', "TAGGED_USER", model=TaggedUserRel)
    comments = RelationshipTo('.interactions.Comment', "COMMENTED", model=CommentRel)

    @property
    def timeline(self):
        # All timeline posts in order of most recent
        return self.timeline_posts.order_by('-taken_at')

    @staticmethod
    def match_username(username):
        return User.nodes.first_or_none(username=username)


class Business(User):
    business_category_name = StringProperty()

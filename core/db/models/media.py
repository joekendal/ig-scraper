from neomodel import (StructuredNode, IntegerProperty, StringProperty,
                      RelationshipFrom, DateTimeProperty, BooleanProperty,
                      ArrayProperty, StructuredRel, RelationshipTo,
                      FloatProperty, One, OneOrMore)


class PostRel(StructuredRel):
    on_timestamp = DateTimeProperty()


class TaggedUserRel(StructuredRel):
    x = FloatProperty()
    y = FloatProperty()


class SidecarRel(StructuredRel):
    index = IntegerProperty()


class Media(StructuredNode):
    media_id = IntegerProperty(unique_index=True)
    caption = StringProperty()
    taken_at = DateTimeProperty()
    comments_disabled = BooleanProperty()
    display_url = StringProperty()
    shortcode = StringProperty()

    location = RelationshipFrom('.locations.Location', 'TAGGED_LOCATION')
    accessibility_caption = StringProperty()

    height = IntegerProperty()
    width = IntegerProperty()

    liked_by = RelationshipFrom('.users.User', "LIKES")
    comments = RelationshipFrom('.interactions.Comment', 'ON')
    hashtags = RelationshipTo('.tags.Hashtag', "MENTIONED")
    tagged_users = RelationshipTo('.users.User', "TAGGED_USER", model=TaggedUserRel)

    edge_liked_by_count = IntegerProperty()
    edge_comments_count = IntegerProperty()

    has_ranked_comments = BooleanProperty()
    is_ad = BooleanProperty()
    caption_is_edited = BooleanProperty()

    owner = RelationshipFrom('.users.User', "POSTED", model=PostRel, cardinality=One)
    sponsors = RelationshipTo('.users.User', "SPONSORED_BY")


class Picture(Media):
    __typename = "GraphImage"
    is_video = False


class ProfilePicture(StructuredNode):
    __typename = "GraphImage"
    profile_pic_url = StringProperty(index=True)
    profile_pic_url_hd = StringProperty()


class Sidecar(Media):
    __typename = "GraphSidecar" # Carousel/Album
    children = RelationshipTo("Media", "HAS", model=SidecarRel, cardinality=OneOrMore)
    children_count = IntegerProperty(default=0)
    urls = ArrayProperty()


class Video(Media):
    __typename = "GraphVideo"
    is_video = True
    product_type = StringProperty()
    duration = FloatProperty()
    view_count = IntegerProperty()
    urls = ArrayProperty()
    title = StringProperty()


class TappableObjectRel(StructuredRel):
    x = FloatProperty()
    y = FloatProperty()
    width = FloatProperty()
    height = FloatProperty()
    rotation = FloatProperty()
    custom_title = StringProperty()
    tappable_type = StringProperty()
    attribution = StringProperty()


class Story(StructuredNode):
    story_id = IntegerProperty(unique_index=True)
    height = IntegerProperty()
    width = IntegerProperty()
    ig_url = StringProperty()
    s3_uri = StringProperty()

    taken_at_timestamp = DateTimeProperty()
    expiring_at_timestamp = DateTimeProperty()

    # Call-to-action link
    story_cta_url = StringProperty()
    # N/A w/o app-auth
    story_view_count = IntegerProperty()
    # E.g. spotify
    story_app_attribution = ArrayProperty()

    tappable_hashtags = RelationshipTo('.tags.Hashtag', 'MENTIONED', model=TappableObjectRel)
    tappable_user = RelationshipTo('.users.User', 'TAGGED_USER', model=TappableObjectRel)
    tappable_locations = RelationshipTo('.locations.Location', 'TAGGED_LOCATION', model=TappableObjectRel)
    tappable_feed = RelationshipTo('.media.Media', 'USES', model=TappableObjectRel)
    tappable_poll = RelationshipTo('.interactions.Poll', 'INCLUDES', model=TappableObjectRel)

    owner = RelationshipFrom('.users.User', 'POSTED_STORY', model=PostRel, cardinality=One)
    sponsors = RelationshipTo('.users.User', 'SPONSORED_BY')

    can_reply = BooleanProperty()
    can_reshare = BooleanProperty()
    has_besties_media = BooleanProperty()
    has_pride_media = BooleanProperty()


class StoryVideo(Story):
    __typename = "GraphStoryVideo"
    is_video = True
    video_duration = FloatProperty()
    has_audio = BooleanProperty()


class StoryImage(Story):
    __typename = "GraphStoryImage"
    is_video = False

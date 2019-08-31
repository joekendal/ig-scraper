from neomodel import (StructuredNode, IntegerProperty, StringProperty,
                      RelationshipFrom, DateTimeProperty, BooleanProperty,
                      ArrayProperty, StructuredRel, RelationshipTo,
                      FloatProperty)

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

    owner = RelationshipFrom('.users.User', "POSTED", model=PostRel)
    sponsors = RelationshipTo('.users.User', "SPONSORED_BY")

    #last_scraped_top_comments = DateTimeProperty()


class Picture(Media):
    __typename = "GraphImage"


class ProfilePicture(StructuredNode):
    __typename = "GraphImage"
    profile_pic_url = StringProperty(index=True)
    profile_pic_url_hd = StringProperty()


class Sidecar(Media):
    __typename = "GraphSidecar" # Carousel/Album
    children = RelationshipTo("Media", "HAS", model=SidecarRel)
    children_count = IntegerProperty(default=0)
    #urls = ArrayProperty()


class Video(Media):
    __typename = "GraphVideo"
    product_type = StringProperty()
    #url = StringProperty()
    duration = FloatProperty()
    view_count = IntegerProperty()
    urls = ArrayProperty()
    title = StringProperty()


# class IGTV(Video):
#     product_type = "igtv"
#     title = StringProperty()

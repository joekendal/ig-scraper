from neomodel import (StructuredNode, IntegerProperty, StringProperty,
                      RelationshipFrom, DateTimeProperty, BooleanProperty,
                      JSONProperty)


class Picture(StructuredNode):
    media_id = IntegerProperty()
    caption = StringProperty()
    taken_at = DateTimeProperty()
    comments_disabled = BooleanProperty()
    display_url = StringProperty()

    location = JSONProperty()
    accessibility_caption = StringProperty()

    liked_by = RelationshipFrom('.users.User', "LIKES")
    # comments = RelationshipFrom('.interactions.Comment', 'ON')

class ProfilePicture(Picture):
    profile_pic_url = StringProperty()
    profile_pic_url_hd = StringProperty()

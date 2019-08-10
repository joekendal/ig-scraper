from neomodel import (StructuredNode, StringProperty, IntegerProperty,
                      RelationshipTo, BooleanProperty, DateTimeProperty,
                      RelationshipFrom)


class User(StructuredNode):
    user_id = IntegerProperty(unique_index=True, required=True)
    username = StringProperty(unique_index=True, required=True)
    full_name = StringProperty()
    bio = StringProperty()
    is_private = BooleanProperty()
    is_verified = BooleanProperty()
    external_url = StringProperty()
    connected_fb_page = StringProperty()

    following = RelationshipTo("User", "FOLLOWS")
    followers = RelationshipFrom("User", "FOLLOWS")

    last_scraped_timestamp = DateTimeProperty()

    gender_estimate = StringProperty(choices={'F': 'Female', 'M': 'Male'})
    age_estimate = IntegerProperty()

    cities_in_bio = RelationshipTo("City", "MENTIONED")
    provinces_in_bio = RelationshipTo("Province", "MENTIONED")
    countries_in_bio = RelationshipTo("Country", "MENTIONED")

    @staticmethod
    def match_username(username):
        return User.nodes.first_or_none(username=username)


class Business(User):
    business_category_name = StringProperty()

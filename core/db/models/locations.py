from neomodel import (StructuredNode, IntegerProperty, StringProperty,
                      BooleanProperty, FloatProperty, JSONProperty,
                      RelationshipTo, RelationshipFrom)
from neomodel.contrib.spatial_properties import PointProperty


class Location(StructuredNode):
    """
    Instagram Geolocation
    endpoint: /explore/locations/{location_id}
    """
    location_id = IntegerProperty(unique_index=True)
    name = StringProperty()
    has_public_page = BooleanProperty()

    latitude = FloatProperty()
    longitude = FloatProperty()
    geospatial = PointProperty(crs='wgs-84')

    slug = StringProperty()
    blurb = StringProperty()

    website = StringProperty()
    phone = StringProperty()
    primary_alias_on_fb = StringProperty()
    address_json = JSONProperty()

    profile_pic = RelationshipTo('.media.ProfilePicture', "HAS")

    medias = RelationshipFrom('.media.Media', 'TAGGED_LOCATION')

from neomodel import StructuredNode, StringProperty, IntegerProperty


class Hashtag(StructuredNode):
    hashtag_id = IntegerProperty(unique=True)
    name = StringProperty(unique_index=True)

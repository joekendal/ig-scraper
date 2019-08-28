from neomodel import (StructuredNode, StructuredRel, DateTimeProperty,
                      RelationshipFrom, IntegerProperty, StringProperty, One,
                      RelationshipTo)


class CommentRel(StructuredRel):
    created_at = DateTimeProperty()


class Comment(StructuredNode):
    comment_id = IntegerProperty(unique_index=True)
    text = StringProperty()
    owner = RelationshipFrom(".users.User", "COMMENTED", model=CommentRel, cardinality=One)
    post = RelationshipTo(".media.Media", "ON", cardinality=One)
    edge_liked_by_count = IntegerProperty()
    edge_threaded_comments_count = IntegerProperty()
    replies = RelationshipTo("ThreadedComment", "REPLY")

class ThreadedComment(Comment):
    parent_comment = RelationshipFrom("Comment", "REPLY", cardinality=One)

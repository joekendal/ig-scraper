import os
from neomodel import config
config.DATABASE_URL = os.environ['NEO4J_BOLT_URL']
config.ENCRYPTED_CONNECTION = False # Development only
config.MAX_POOL_SIZE = 50
from .locations import *
from .users import *
from .media import *
from .tags import *

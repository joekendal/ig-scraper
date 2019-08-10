import os
from neomodel import config
config.DATABASE_URL = os.environ['NEO4J_BOLT_URL']
from .locations import *
from .users import *

"""
heroku app script
"""
import os
from mybrowser.session.config import Config
from mybrowser.browser import get_app
import logging

my_handler = logging.StreamHandler()
my_formatter = logging.Formatter(
    fmt='{asctime}.{msecs:03.0f}: {levelname}:{name}: {message}',
    datefmt='%Y-%m-%d %H:%M:%S',
    style='{'
)
my_handler.setFormatter(my_formatter)

logger = logging.getLogger()
logger.addHandler(my_handler)
logger.setLevel(logging.INFO)

DATABASE_URL = os.environ['DATABASE_URL']

# see stack question - have to edit postgres string:
# https://stackoverflow.com/questions/62688256/sqlalchemy-exc-nosuchmoduleerror-cant-load-plugin-sqlalchemy-dialectspostgre
start = 'postgres://'
if not DATABASE_URL.startswith(start):
    raise Exception(f'expected database URL to start with "{start}", instead got "{DATABASE_URL}"')
url = DATABASE_URL.replace(start, 'postgresql://')

# set url to database url and schema
config = Config()
config.display_config.cache = False
config.display_config.libraries = False
config.display_config.strategy_delete = False
config.display_config.config_reloads = False
schema = 'bettingschema'
config.database_config.db_kwargs['engine_kwargs'] = {
    'url': url,
    'connect_args': {
        'options': f'-c search_path={schema},public'
    }
}
app = get_app(config)

# set server variable to be read by heroku
server = app.server

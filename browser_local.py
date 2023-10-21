import os
from mybrowser.session.config import Config, get_market_filters
from mybrowser.browser import get_app
from mybrowser.exceptions import MyBrowserException
import argparse
import logging
from dotenv import load_dotenv

load_dotenv()  # take environment variables from .env.

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

parser = argparse.ArgumentParser(
    formatter_class=argparse.ArgumentDefaultsHelpFormatter  # show defaults in help
)
parser.add_argument(
    '--debug',
    action='store_true',
    help='run in debug mode'
)
args = parser.parse_args()
logger.info(f'running browser...')
pwd = os.environ['betdb_pwd']
if not pwd:
    raise MyBrowserException('no password found for database')

config = Config()
config.database_config.db_kwargs['db_pwd'] = pwd
app = get_app(config)

# turn of dev tools prop check to disable time input error
app.run_server(debug=args.debug, dev_tools_props_check=False, use_reloader=False)

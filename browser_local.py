from mybrowser.browser import get_app
import argparse
import keyring
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
app = get_app(additional_config={
    'DB_CONFIG': {
        'db_pwd': keyring.get_password('betdb_pwd', 'betting')
    }
})
# turn of dev tools prop check to disable time input error
app.run_server(debug=args.debug, dev_tools_props_check=False, use_reloader=False)

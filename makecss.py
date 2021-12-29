import os
import sass
from myutils import dashutilities
from os import path, chdir
import urllib.request
import zipfile
import logging

SRC_DIR = 'bootstrap_source'
ZIP_FILE = 'bootstrap_source.zip'
BOOTSTRAP_URL = 'https://github.com/twbs/bootstrap/archive/v5.1.3.zip'

logging.basicConfig(level=logging.INFO)
logging.info('navigating into "mybrowser"')
chdir('mybrowser')

logging.info('compiling local scss to assets')
sass.compile(dirname=('scss', 'assets'))

logging.info(f'downloading bootstrap source from "{BOOTSTRAP_URL}" to "{ZIP_FILE}"')
urllib.request.urlretrieve(BOOTSTRAP_URL, ZIP_FILE)

logging.info(f'unzipping to "{SRC_DIR}"')
with zipfile.ZipFile(ZIP_FILE, 'r') as zip_ref:
    zip_ref.extractall(SRC_DIR)

_, dirs, _ = next(os.walk(SRC_DIR))
if not dirs or 'bootstrap' not in dirs[0]:
    logging.error('could not find bootstrap dir in source')
    exit(1)

bootstrap_scss = path.join(SRC_DIR, dirs[0], 'scss')
if not path.isdir(bootstrap_scss):
    logging.error(f'"{bootstrap_scss}" is not a valid directory')
    exit(1)

utils_scss = path.join(dashutilities.__path__[0], 'scss')
logging.info(f'compiling utilities scss at "{utils_scss}"')
logging.info(f'using bootstrap scss source at "{bootstrap_scss}"')

sass.compile(
    dirname=(utils_scss, 'assets'),
    include_paths=[bootstrap_scss]
)

logging.info(f'assets folder now has files: {os.listdir("assets")}')
logging.info(f'done!')

import configparser
import importlib.resources as pkg_resources
import logging

active_logger = logging.getLogger(__name__)
active_logger.setLevel(logging.INFO)

# TODO make config passable as input rather than declared globally
file_name = 'config.txt'
active_logger.info(f'reading configuration from "{file_name}"...')
config = configparser.ConfigParser()
txt = pkg_resources.read_text("mybrowser", file_name)
config.read_string(txt)
for section in config.sections():
    active_logger.info(f'Section {section}, values:')
    for k, v in config[section].items():
        active_logger.info(f'{k}: {v}')
active_logger.info(f'configuration reading done')

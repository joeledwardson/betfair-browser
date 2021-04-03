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

# for k in config['DEFAULT']:
#     print(f'{k}: "{config["DEFAULT"][k]}"')
# config['DEFAULT'] = {'ServerAliveInterval': '45',
#                      'Compression': 'yes',
#                      'CompressionLevel': '9'}
# with open('config.txt', 'w') as c:
#     config.write(c)
# print(__file__)
# config.read('config.txt')
# for k in config['DEFAULT']:
#     print(k)

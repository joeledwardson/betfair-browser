import configparser
import importlib.resources as pkg_resources
import logging

active_logger = logging.getLogger(__name__)
active_logger.setLevel(logging.INFO)

config = configparser.ConfigParser()


def init(config_path=None):
    """
    load configuration file by passing path, or do not pass an arg to use default configuration file

    Parameters
    ----------
    config_path :

    Returns
    -------

    """
    if config_path is not None:
        active_logger.info(f'reading configuration from path: "{config_path}"')
        config.read(config_path)
    else:
        file_name = 'config.txt'
        active_logger.info(f'reading configuration from default "{file_name}"...')
        txt = pkg_resources.read_text("mybrowser", file_name)
        config.read_string(txt)

    for section in config.sections():
        active_logger.info(f'Section {section}, values:')
        for k, v in config[section].items():
            active_logger.info(f'{k}: {v}')
    active_logger.info(f'configuration reading done')

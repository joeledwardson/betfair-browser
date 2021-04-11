import logging
from os import path, makedirs
import zlib
from sqlalchemy.exc import SQLAlchemyError


active_logger = logging.getLogger(__name__)
active_logger.setLevel(logging.INFO)


class CacheException(Exception):
    pass


def cache_decompress(sql_row):
    return zlib.decompress(sql_row).decode()


def cache_compress(data):
    return zlib.compress(data.encode())


def cache_encode(data):
    return data.encode()


def cache_decode(data):
    return data.decode()


def cache_path(root, tbl, filters, col) -> str:
    return path.abspath(path.join(
        root,
        tbl,
        *filters.values(),
        col
    ))


def write_cache_path(root, tbl, filters, col, db, pre_processor=None) -> bool:
    p = cache_path(root, tbl, filters, col)
    d, _ = path.split(p)
    if not path.isdir(d):
        makedirs(d)
    active_logger.info(f'writing db cache file:\n-> {p}')
    if path.isfile(p):
        active_logger.info(f'file already exists, exiting...')
        return True
    try:
        r = db.session.query(
            db.tables[tbl].columns[col]
        ).filter(
            *[db.tables[tbl].columns[k] == v for k, v in filters.items()]
        ).first()
    except SQLAlchemyError as e:
        active_logger.warning(f'failed to write market file\n{e}', exc_info=True)
        return False

    if not len(r):
        active_logger.warning(f'returned row is empty')
        return False

    dat = r[0]
    if pre_processor is not None:
        dat = pre_processor(dat)

    with open(p, 'w') as f:
        f.write(dat)
        active_logger.info(f'successfully wrote market file')
    return True


def read_cache_path(root, tbl, filters, col, post_processor=None):
    p = cache_path(root, tbl, filters, col)
    active_logger.info(f'reading db cache file:\n-> {p}')

    if not path.isfile(p):
        active_logger.warning(f'file does not exist')
        return None

    with open(p) as f:
        data = f.read()

    if post_processor is not None:
        data = post_processor(data)

    return data


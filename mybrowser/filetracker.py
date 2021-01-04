from __future__ import annotations
from os import path
from typing import List, Tuple, Dict, Optional
from natsort import natsorted
from itertools import chain
import logging

from myutils import mypath


class FileTracker:
    def __init__(self, start_dir: str, logger: Optional[logging.Logger]=None):
        self.start_dir = start_dir

        self.root: str = ''
        self.dirs: List[str] = list()
        self.files: List[str] = list()

        # combination of dirs and files
        self.elements: List[str] = list()

        self.display_list = []
        self.update(start_dir)

        if logger is not None:
            self.logger = logger
        else:
            self.logger = logging.getLogger(__name__)

    def _get_update(self, top) -> Tuple[str, List, List, List]:
        """
        returns list:
        1. `top` (arg passed), the root path to get files and dirs from
        2. list of dirs
        3. list of files
        4. list of elements (combination of dirs then files)
        """

        # check top path exists
        if not path.exists(top):

            # reset to original
            self.logger.warning(f'path: "{top}" does not exist, resetting to "{self.start_dir}"')
            top = self.start_dir

        root, dirs, files = mypath.walk_first(top)

        # sort into windows explorer display order
        dirs = natsorted(dirs)
        files = natsorted(files)
        elements = list(chain(dirs, files))
        return root, dirs, files, elements

    def update(self, top):
        """
        update file tracker from `top` new path, setting file tracker root, dirs, files and elements
        """
        self.root, self.dirs, self.files, self.elements = self._get_update(top)
        self.display_list = self.get_display_list()

    def get_display_list(self):
        """list of dirs first, then files with symbols to display in table"""
        return ['📁 ' + f for f in self.dirs] + ['🗎 ' + f for f in self.files]

    def navigate_to(self, index: int):
        """navigate to directory based on its index in display list"""
        if 0 <= index < len(self.dirs):
            selected_dir = self.dirs[index]
            self.update(path.join(self.root, selected_dir))

    def navigate_up(self):
        """return to parent directory"""
        self.update(path.split(self.root)[0])

    def get_file_name(self, file_display_index):
        """get file name from its index in display list"""
        if len(self.dirs) <= file_display_index < len(self.display_list):
            return self.files[file_display_index - len(self.dirs)]
        else:
            return None
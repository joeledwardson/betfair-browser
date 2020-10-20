from __future__ import annotations
from os import path
from typing import List, Tuple, Dict
from natsort import natsorted
from mytrading.utils.storage import walk_first


class FileTracker:
    def __init__(self, start_dir: str):
        self.start_dir = start_dir

        self.root: str = ''
        self.dirs: List[str] = list()
        self.files: List[str] = list()

        self.root, self.dirs, self.files = self.get_update(start_dir)
        self.display_list = self.get_display_list()

    def get_update(self, top):
        root, dirs, files = walk_first(top)
        # sort into windows explorer display order
        dirs = natsorted(dirs)
        files = natsorted(files)
        return root, dirs, files

    def get_display_list(self):
        """list of dirs first, then files with symbols to display in table"""
        return ['📁 ' + f for f in self.dirs] + ['🗎 ' + f for f in self.files]

    def navigate_to(self, index: int):
        """navigate to directory based on its index in display list"""
        if 0 <= index < len(self.dirs):
            selected_dir = self.dirs[index]
            self.root, self.dirs, self.files = self.get_update(path.join(self.root, selected_dir))

            self.display_list = self.get_display_list()

    def navigate_up(self):
        """return to parent directory"""
        self.root, self.dirs, self.files = self.get_update(path.split(self.root)[0])
        self.display_list = self.get_display_list()

    def get_file_name(self, file_display_index):
        """get file name from its index in display list"""
        if len(self.dirs) <= file_display_index < len(self.display_list):
            return self.files[file_display_index - len(self.dirs)]
        else:
            return None
import json
import os.path as osp
from typing import Optional
from labelTrack.defines import SETTINGS_FILE


class Settings(object):

    def __init__(self):
        self._data: Optional[dict] = None
        if not osp.exists(SETTINGS_FILE):
            with open(SETTINGS_FILE, 'w') as f:
                json.dump({}, f)
        self.load()

    def __getitem__(self, key):
        return self._data[key]

    def __setitem__(self, key, value):
        self._data[key] = value

    def load(self):
        with open(SETTINGS_FILE, 'r') as f:
            self._data = json.load(f)
        
    def save(self):
        with open(SETTINGS_FILE, 'w') as f:
            json.dump(self._data, f, indent=4)

    def get(self, keys, default=None):
        if type(keys) is str:
            keys = [keys]
        v = self._data
        for key in keys:
            if key not in v:
                v = None
                break
            v = v[key]
        if v is None:
            return default
        else:
            return v

    def set(self, keys, value):
        if type(keys) is str:
            keys = [keys]
        v = self._data
        for key in keys[:-1]:
            if key not in v:
                v[key] = {}
            v = v[key]
        v[keys[-1]] = value


def initialize():
    global settings
    settings = Settings()

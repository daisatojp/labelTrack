import os
import os.path as osp
from math import sqrt
import re
from PyQt6.QtGui import *
from PyQt6.QtCore import *
from PyQt6.QtWidgets import *
from labelTrack.resource import read_icon


def new_icon(icon):
    if icon is not None:
        return read_icon(icon)
    else:
        return None


def new_action(
        parent: QWidget,
        text: str,
        slot=None,
        shortcut=None,
        icon=None,
        checkable=False):
    """Create a new action and assign callbacks, shortcuts, etc."""
    a = QAction(text, parent)
    if icon is not None:
        a.setIcon(new_icon(icon))
    if shortcut is not None:
        if isinstance(shortcut, (list, tuple)):
            a.setShortcuts(shortcut)
        else:
            a.setShortcut(shortcut)
    if slot is not None:
        a.triggered.connect(slot)
    if checkable:
        a.setCheckable(True)
    return a


def add_actions(widget, actions):
    for action in actions:
        if action is None:
            widget.addSeparator()
        elif isinstance(action, QMenu):
            widget.addMenu(action)
        else:
            widget.addAction(action)


def distance(p):
    return sqrt(p.x() * p.x() + p.y() * p.y())


def natural_sort(list, key=lambda s:s):
    """
    Sort the list into natural alphanumeric order.
    """
    def get_alphanum_key_func(key):
        convert = lambda text: int(text) if text.isdigit() else text
        return lambda s: [convert(c) for c in re.split('([0-9]+)', key(s))]
    sort_key = get_alphanum_key_func(key)
    list.sort(key=sort_key)


def scan_all_images(folder_path):
    extensions = [
        '.{}'.format(fmt.data().decode('ascii').lower())
        for fmt in QImageReader.supportedImageFormats()]
    images = []
    for root, dirs, files in os.walk(folder_path):
        for file in files:
            if file.lower().endswith(tuple(extensions)):
                images.append(osp.abspath(osp.join(root, file)))
        break
    natural_sort(images, key=lambda x: x.lower())
    return images

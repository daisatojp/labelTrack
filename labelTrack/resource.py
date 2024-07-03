import sys
import os.path as osp
from PyQt5.QtGui import *
from PyQt5.QtCore import *


def read_icon(name):
    path = osp.join('icon', name)
    if hasattr(sys, '_MEIPASS'):
        path = osp.join(sys._MEIPASS, path)
    return QIcon(QPixmap(path))

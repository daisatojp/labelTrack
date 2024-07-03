import argparse
import sys

import labelTrack.settings as Settings
Settings.initialize()

from PyQt6.QtWidgets import QApplication
from labelTrack.__init__ import __appname__
from labelTrack.mainwindow import MainWindow


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--image_dir', type=str, default=None)
    parser.add_argument('--label_path', type=str, default=None)
    args = parser.parse_args()

    app = QApplication([])
    app.setApplicationName(__appname__)

    win = MainWindow(args.image_dir, args.label_path)
    win.show()
    return app.exec()


if __name__ == '__main__':
    sys.exit(main())

import copy
from dataclasses import dataclass
from functools import partial
from math import sqrt
import os
import os.path as osp
import re
import sys
from typing import Callable
from typing import Optional
from PyQt6.QtCore import *
from PyQt6.QtGui import *
from PyQt6.QtWidgets import *
from PyQt6.QtWidgets import QMessageBox as QMB
from labelTrack.__init__ import __appname__, __version__
from labelTrack.settings import settings
from labelTrack.defines import *


BBOX_COLOR              = QColor(  0, 255,   0, 128)
BBOX_HIGHLIGHTED_COLOR  = QColor(255,   0,   0, 255)
POINT_COLOR             = QColor(  0, 255,   0, 255)
POINT_HIGHLIGHTED_COLOR = QColor(255,   0,   0, 255)


@dataclass
class BBox:
    x: Optional[float] = None
    y: Optional[float] = None
    w: Optional[float] = None
    h: Optional[float] = None

    def empty(self) -> bool:
        return (self.x is None) or \
               (self.y is None) or \
               (self.w is None) or \
               (self.h is None)

    def xmin(self) -> float:
        return self.x

    def ymin(self) -> float:
        return self.y

    def xmax(self) -> float:
        return self.x + self.w

    def ymax(self) -> float:
        return self.y + self.h

    def cx(self) -> float:
        return self.x + self.w / 2.0

    def cy(self) -> float:
        return self.y + self.h / 2.0

    def move(self, dx: float, dy: float) -> None:
        self.x += dx
        self.y += dy

    def get_xy(self, idx: int) -> tuple[float, float]:
        if idx == 0:
            return self.x, self.y
        if idx == 1:
            return self.x + self.w, self.y
        if idx == 2:
            return self.x + self.w, self.y + self.h
        if idx == 3:
            return self.x, self.y + self.h
        raise IndexError()

    def set_xy(self, pidx: int, x: float, y: float) -> None:
        if not (0 <= pidx < 4):
            raise IndexError()
        x1, y1 = x, y
        x2, y2 = self.get_xy((pidx + 2) % 4)
        self.x = min(x1, x2)
        self.y = min(y1, y2)
        self.w = abs(x2 - x1)
        self.h = abs(y2 - y1)

    def get_point(self, idx: int) -> QPointF:
        x, y = self.get_xy(idx)
        return QPointF(x, y)

    def __str__(self) -> str:
        if self.empty():
            return '-1.00,-1.00,-1.00,-1.00'
        return f'{self.x:.2f},{self.y:.2f},{self.w:.2f},{self.h:.2f}'


class MainWindow(QMainWindow):

    def __init__(self,
                 image_dir: Optional[str] = None,
                 label_file: Optional[str] = None
                 ) -> None:
        super(MainWindow, self).__init__()
        self.setWindowTitle(__appname__)

        self._image_dir: Optional[str] = None
        self._image_files: list[str] = []
        self._label_file: Optional[str] = None
        self._bboxes: list[BBox] = []
        self._dirty: bool = False

        self.img_list = QListWidget()
        self.img_list.currentItemChanged.connect(self.file_current_item_changed)
        self.file_dock = QDockWidget('Image List', self)
        self.file_dock.setObjectName('images')
        self.file_dock.setWidget(self.img_list)
        self.file_dock.setFeatures(QDockWidget.DockWidgetFeature.DockWidgetFloatable)
        self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, self.file_dock)

        self.canvas = Canvas(parent=self)
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidget(self.canvas)
        self.scroll_area.setWidgetResizable(True)
        self.scroll_bars = {
            Qt.Orientation.Vertical: self.scroll_area.verticalScrollBar(),
            Qt.Orientation.Horizontal: self.scroll_area.horizontalScrollBar()}
        self.setCentralWidget(self.scroll_area)

        self.quit_action = self.__new_action('Quit', icon_file='quit', slot=self.close, shortcut='Ctrl+Q')
        self.open_image_dir_action = self.__new_action('Open Image', icon_file='open', slot=self.__open_image_dir_dialog)
        self.open_label_file_action = self.__new_action('Open Label', icon_file='open', slot=self.__open_label_file_dialog)
        self.next_image_action = self.__new_action('Next Image', icon_file='next', slot=self.__open_next_image, shortcut='d')
        self.prev_image_action = self.__new_action('Previous Image', icon_file='prev', slot=self.__open_prev_image, shortcut='a')
        self.save_action = self.__new_action('Save', icon_file='save', slot=self.__save_label_file, shortcut='Ctrl+s')
        self.create_bbox_action = self.__new_action('Create BBox', icon_file='objects', slot=self.__create_bbox, shortcut='w')
        self.delete_bbox_action = self.__new_action('Delete BBox', icon_file='close', slot=self.__delete_bbox, shortcut='c')
        self.copy_bbox_action = self.__new_action('Copy BBox', icon_file='copy', slot=self.__copy_bbox, shortcut='r')
        self.next_image_and_copy_action = self.__new_action('Next Image and Copy', icon_file='next', slot=self.__next_image_and_copy, shortcut='t')
        self.show_info_action = self.__new_action('info', icon_file='help', slot=self.__show_info_dialog)
        self.auto_saving_action = self.__new_action('Auto Save Mode', checkable=True, checked=settings.get(SETTINGS_KEY_AUTO_SAVE, False))
        self.zoom_spinbox = QSpinBox()
        self.zoom_spinbox.setButtonSymbols(QAbstractSpinBox.ButtonSymbols.NoButtons)
        self.zoom_spinbox.setRange(1, 500)
        self.zoom_spinbox.setSuffix(' %')
        self.zoom_spinbox.setValue(100)
        self.zoom_spinbox.setToolTip('Zoom Level')
        self.zoom_spinbox.setStatusTip(self.toolTip())
        self.zoom_spinbox.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.zoom_spinbox.setEnabled(True)
        self.zoom_spinbox.valueChanged.connect(self.__zoom_value_changed)
        self.zoom_in_action = self.__new_action('Zoom In', icon_file='zoom-in', slot=partial(self.__add_zoom, 10), shortcut='Ctrl++')
        self.zoom_out_action = self.__new_action('Zoom Out', icon_file='zoom-out', slot=partial(self.__add_zoom, -10), shortcut='Ctrl+-')
        self.zoom_org_action = self.__new_action('Original Size', icon_file='zoom', slot=self.__reset_zoom, shortcut='Ctrl+=')
        self.fit_window_action = self.__new_action('Fit Window', icon_file='fit-window', slot=self.__set_fit_window, shortcut='Ctrl+F')
        self.menus_file = self.menuBar().addMenu('File')
        self.menus_edit = self.menuBar().addMenu('Edit')
        self.menus_view = self.menuBar().addMenu('View')
        self.menus_help = self.menuBar().addMenu('Help')
        self.menus_file.addAction(self.open_image_dir_action)
        self.menus_file.addAction(self.open_label_file_action)
        self.menus_file.addAction(self.save_action)
        self.menus_file.addAction(self.next_image_action)
        self.menus_file.addAction(self.prev_image_action)
        self.menus_file.addAction(self.quit_action)
        self.menus_edit.addAction(self.create_bbox_action)
        self.menus_edit.addAction(self.delete_bbox_action)
        self.menus_edit.addAction(self.copy_bbox_action)
        self.menus_edit.addAction(self.next_image_and_copy_action)
        self.menus_view.addAction(self.auto_saving_action)
        self.menus_view.addSeparator()
        self.menus_view.addAction(self.zoom_in_action)
        self.menus_view.addAction(self.zoom_out_action)
        self.menus_view.addAction(self.zoom_org_action)
        self.menus_view.addSeparator()
        self.menus_view.addAction(self.fit_window_action)
        self.menus_help.addAction(self.show_info_action)
        self.toolbar = ToolBar('Tools')
        self.toolbar.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextUnderIcon)
        self.addToolBar(Qt.ToolBarArea.LeftToolBarArea, self.toolbar)
        self.toolbar.addAction(self.open_image_dir_action)
        self.toolbar.addAction(self.open_label_file_action)
        self.toolbar.addAction(self.next_image_action)
        self.toolbar.addAction(self.prev_image_action)
        self.toolbar.addAction(self.save_action)
        self.toolbar.addSeparator()
        self.toolbar.addAction(self.create_bbox_action)
        self.toolbar.addAction(self.delete_bbox_action)
        self.toolbar.addSeparator()
        self.toolbar.addAction(self.zoom_in_action)
        self.toolbar.addWidget(self.zoom_spinbox)
        self.toolbar.addAction(self.zoom_out_action)
        self.toolbar.addAction(self.fit_window_action)
        self.statusBar().showMessage(f'{__appname__} started.')
        self.statusBar().show()

        window_x = settings.get(SETTINGS_KEY_WINDOW_X, 0)
        window_y = settings.get(SETTINGS_KEY_WINDOW_Y, 0)
        window_w = settings.get(SETTINGS_KEY_WINDOW_W, 600)
        window_h = settings.get(SETTINGS_KEY_WINDOW_H, 500)
        position = QPoint(window_x, window_y)
        size = QSize(window_w, window_h)
        self.resize(size)
        self.move(position)

        self.__load_image_dir(image_dir)
        self.__load_label_file(label_file)

        self.status_label = QLabel('')
        self.statusBar().addPermanentWidget(self.status_label)

    def closeEvent(self, event: QCloseEvent) -> None:
        if not self.__may_continue():
            event.ignore()
        settings.set(SETTINGS_KEY_IMAGE_DIR, self._image_dir if self._image_dir is not None else '.')
        settings.set(SETTINGS_KEY_LABEL_PATH, self._label_file if self._label_file is not None else '.')
        settings.set(SETTINGS_KEY_WINDOW_X, self.pos().x())
        settings.set(SETTINGS_KEY_WINDOW_Y, self.pos().y())
        settings.set(SETTINGS_KEY_WINDOW_W, self.size().width())
        settings.set(SETTINGS_KEY_WINDOW_H, self.size().height())
        settings.set(SETTINGS_KEY_AUTO_SAVE, self.auto_saving_action.isChecked())
        settings.save()

    def resizeEvent(self, event: QResizeEvent) -> None:
        super(MainWindow, self).resizeEvent(event)

    def status(self, message, delay=5000):
        self.statusBar().showMessage(message, delay)

    def file_current_item_changed(self, item=None):
        self.__load_image()

    def update_bboxes_from_canvas(self):
        idx = self.img_list.currentRow()
        self._bboxes[idx] = copy.copy(self.canvas.bbox)
        self.__set_dirty(True)
        self.__update_img_list()

    def zoom_request(self, delta: int) -> None:
        h_bar = self.scroll_bars[Qt.Orientation.Horizontal]
        v_bar = self.scroll_bars[Qt.Orientation.Vertical]
        h_bar_max = h_bar.maximum()
        v_bar_max = v_bar.maximum()
        cursor = QCursor()
        pos = cursor.pos()
        relative_pos = QWidget.mapFromGlobal(self, pos)
        cursor_x = relative_pos.x()
        cursor_y = relative_pos.y()
        w = self.scroll_area.width()
        h = self.scroll_area.height()
        margin = 0.1
        move_x = (cursor_x - margin * w) / (w - 2 * margin * w)
        move_y = (cursor_y - margin * h) / (h - 2 * margin * h)
        move_x = min(max(move_x, 0), 1)
        move_y = min(max(move_y, 0), 1)
        self.__add_zoom(10 * (delta // 120))
        d_h_bar_max = h_bar.maximum() - h_bar_max
        d_v_bar_max = v_bar.maximum() - v_bar_max
        new_h_bar_value = int(h_bar.value() + move_x * d_h_bar_max)
        new_v_bar_value = int(v_bar.value() + move_y * d_v_bar_max)
        h_bar.setValue(new_h_bar_value)
        v_bar.setValue(new_v_bar_value)

    def scroll_request(self, delta: int | float, orientation: Qt.Orientation) -> None:
        bar = self.scroll_bars[orientation]
        bar.setValue(int(bar.value() + bar.singleStep() * (-delta / 120)))

    def __set_dirty(self, dirty: bool) -> None:
        self._dirty = dirty
        self.save_action.setEnabled(dirty)

    def __may_continue(self):
        if not self._dirty:
            return True
        result = QMB.warning(
            self, 'Attention',
            'You have unsaved changes, would you like to save them and proceed?',
            QMB.StandardButton.Yes | QMB.StandardButton.No | QMB.StandardButton.Cancel)
        if result == QMB.StandardButton.No:
            return True
        if result == QMB.StandardButton.Yes:
            self.__save_label_file()
            return True
        return False

    def __open_image_dir_dialog(self):
        if not self.__may_continue():
            return
        default_image_dir = '.'
        if self._image_dir and osp.exists(self._image_dir):
            default_image_dir = self._image_dir
        image_dir = QFileDialog.getExistingDirectory(
            self, f'{__appname__} - Open Image Directory', default_image_dir,
            QFileDialog.Option.ShowDirsOnly | QFileDialog.Option.DontResolveSymlinks)
        self.__load_image_dir(image_dir)

    def __open_label_file_dialog(self):
        if self._image_dir is None:
            QMB.information(
                self, 'Attention',
                'You have not opened image folder.',
                QMB.StandardButton.Ok)
            return
        if not self.__may_continue():
            return
        default_label_file = '.'
        if self._label_file is not None:
            default_label_file = self._label_file
        label_file = QFileDialog.getSaveFileName(
            self, f'{__appname__} - Save label to the file',
            osp.dirname(default_label_file), 'Text (*.txt)',
            None, QFileDialog.Option.DontConfirmOverwrite)
        label_file = label_file[0]
        if label_file != '':
            self.__load_label_file(label_file)
            self.statusBar().showMessage(f'Label will be saved to {self._label_file}.')
            self.statusBar().show()

    def __open_prev_image(self):
        cnt = self.img_list.count()
        idx = self.img_list.currentRow()
        if self.auto_saving_action.isChecked():
            self.__save_label_file()
        if cnt <= 0:
            return
        if 0 <= idx - 1:
            idx -= 1
            self.img_list.setCurrentRow(idx)
        self.__load_image()

    def __open_next_image(self):
        cnt = self.img_list.count()
        idx = self.img_list.currentRow()
        if self.auto_saving_action.isChecked():
            self.__save_label_file()
        if idx + 1 < cnt:
            idx += 1
            self.img_list.setCurrentRow(idx)
        self.__load_image()

    def __next_image_and_copy(self):
        self.__open_next_image()
        self.__copy_bbox()

    def __show_info_dialog(self):
        msg = f'Name:{__appname__} \nApp Version:{__version__}'
        QMB.information(self, 'Information', msg)

    def __create_bbox(self):
        if self.canvas.pixmap is None:
            return
        self.canvas.set_mode(CANVAS_CREATE_MODE)
        self.create_bbox_action.setEnabled(False)

    def __delete_bbox(self):
        idx = self.img_list.currentRow()
        if idx < 0:
            return
        self._bboxes[idx] = BBox()
        self.canvas.bbox = BBox()
        self.canvas.update()
        self.__update_img_list()

    def __copy_bbox(self):
        idx = self.img_list.currentRow()
        if idx <= 0:
            return
        self._bboxes[idx] = copy.copy(self._bboxes[idx - 1])
        self.canvas.bbox = copy.copy(self._bboxes[idx])
        self.canvas.update()
        self.__update_img_list()

    def __load_image(self) -> None:
        idx = self.img_list.currentRow()
        if idx < 0:
            return
        self.canvas.setEnabled(False)
        file_path = self._image_files[idx]
        reader = QImageReader(file_path)
        reader.setAutoTransform(True)
        img = reader.read()
        if not isinstance(img, QImage):
            img = QImage.fromData(img)
        if img.isNull():
            QMB.critical(
                self, 'Error opening file',
                f'Could not read {file_path}')
            self.status(f'Error reading {file_path}')
            return
        self.canvas.pixmap = QPixmap.fromImage(img)
        self.canvas.bbox = copy.copy(self._bboxes[idx])
        self.status(f'Loaded {osp.basename(file_path)}')
        self.canvas.setEnabled(True)
        self.__set_fit_window()
        idx = self.img_list.currentRow()
        cnt = self.img_list.count()
        self.setWindowTitle(f'{__appname__} {file_path} [{idx + 1} / {cnt}]')
        self.canvas.setFocus()
        self.canvas.update()

    def __load_image_dir(self, image_dir: Optional[str]) -> None:
        self._label_file = None
        self._bboxes.clear()
        self.img_list.clear()
        self.__set_dirty(False)
        self.canvas.pixmap = None
        self.canvas.bbox = BBox()
        if (image_dir is None) or \
           (image_dir == ''):
            self._image_dir = None
            self._image_files.clear()
            self.canvas.update()
            return
        self._image_files = scan_all_images(image_dir)
        if len(self._image_files) == 0:
            QMB.critical(
                self, 'Error.', 'No image found.',
                QMB.StandardButton.Ok)
            self._image_dir = None
            self.canvas.update()
            return
        self._image_dir = image_dir
        self._bboxes = [BBox() for _ in range(len(self._image_files))]
        self.__update_img_list()
        self.img_list.setCurrentRow(0)
        self.__load_image()

    def __update_img_list(self) -> None:
        num = len(self._image_files)
        assert len(self._bboxes) == num
        if self.img_list.count() != num:
            self.img_list.clear()
            for _ in range(num):
                self.img_list.addItem(QListWidgetItem())
        for i, (image_file, bbox) in enumerate(zip(self._image_files, self._bboxes)):
            file = osp.basename(image_file)
            if bbox.empty():
                text = f'{file} (no bbox)'
            else:
                text = f'{file}'
            self.img_list.item(i).setText(text)

    def __load_label_file(self, label_file: Optional[str]) -> None:
        self._label_file = label_file
        self._bboxes = [BBox() for _ in range(len(self._bboxes))]
        if label_file is None:
            return
        with open(label_file, 'r') as f:
            for idx, line in enumerate(f.readlines()):
                s = line.split(',')
                self._bboxes[idx] = BBox(
                    x=float(s[0]), y=float(s[1]), w=float(s[2]), h=float(s[3]))
        self.__update_img_list()

    def __save_label_file(self) -> None:
        if self._label_file is None:
            return
        if self._dirty is False:
            return
        with open(self._label_file, 'w') as f:
            for bbox in self._bboxes:
                f.write(str(bbox) + '\n')
        self.__set_dirty(False)
        self.statusBar().showMessage(f'Saved to {self._label_file}')
        self.statusBar().show()

    def __reset_zoom(self) -> None:
        self.zoom_spinbox.setValue(100)

    def __add_zoom(self, increment: int) -> None:
        self.zoom_spinbox.setValue(int(self.zoom_spinbox.value() + increment))

    def __set_fit_window(self):
        self.zoom_spinbox.setValue(int(100 * self.__scale_fit_window()))

    def __scale_fit_window(self) -> float:
        e = 2.0  # so that no scrollbars are generated.
        w1 = self.centralWidget().width() - e
        h1 = self.centralWidget().height() - e
        a1 = w1 / h1
        w2 = self.canvas.pixmap.width() - 0.0
        h2 = self.canvas.pixmap.height() - 0.0
        a2 = w2 / h2
        return w1 / w2 if a1 <= a2 else h1 / h2

    def __zoom_value_changed(self):
        if self.canvas.pixmap is None:
            return
        self.canvas.adjustSize()
        self.canvas.update()

    def __new_action(
            self,
            text: str,
            icon_file: Optional[str] = None,
            slot: Optional[Callable] = None,
            shortcut: Optional[str] = None,
            checkable: bool = False,
            checked: bool = False
            ) -> QAction:
        action = QAction(text, self)
        if icon_file is not None:
            action.setIcon(read_icon(icon_file))
        if slot is not None:
            action.triggered.connect(slot)
        if shortcut is not None:
            action.setShortcut(shortcut)
        if checkable:
            action.setCheckable(True)
            action.setChecked(checked)
        return action


class ToolBar(QToolBar):

    def __init__(self, title):
        super(ToolBar, self).__init__(title)
        layout = self.layout()
        m = (0, 0, 0, 0)
        layout.setSpacing(0)
        layout.setContentsMargins(*m)
        self.setContentsMargins(*m)
        self.setWindowFlags(self.windowFlags() | Qt.WindowType.FramelessWindowHint)

    def addAction(self, action: QAction) -> None:
        if isinstance(action, QWidgetAction):
            super(ToolBar, self).addAction(action)
        btn = ToolButton()
        btn.setDefaultAction(action)
        btn.setToolButtonStyle(self.toolButtonStyle())
        self.addWidget(btn)


class ToolButton(QToolButton):
    minSize = (60, 60)

    def minimumSizeHint(self):
        ms = super(ToolButton, self).minimumSizeHint()
        w1, h1 = ms.width(), ms.height()
        w2, h2 = self.minSize
        ToolButton.minSize = max(w1, w2), max(h1, h2)
        return QSize(*ToolButton.minSize)


class Canvas(QWidget):

    def __init__(self, parent: MainWindow) -> None:
        super(Canvas, self).__init__(parent)
        self.p = parent
        self.mode = CANVAS_EDIT_MODE
        self.pixmap: Optional[QPixmap] = None
        self.bbox: BBox = BBox()

        self._painter = QPainter()
        self._cursor = Qt.CursorShape.ArrowCursor
        self._mx: Optional[float] = None
        self._my: Optional[float] = None
        self._bbox_sx: Optional[float] = None
        self._bbox_sy: Optional[float] = None
        self._highlighted_bbox: bool = False
        self._highlighted_pidx: Optional[int] = None

        self.setMouseTracking(True)
        self.setFocusPolicy(Qt.FocusPolicy.WheelFocus)

    def enterEvent(self, event: QEnterEvent) -> None:
        self.__override_cursor(self._cursor)

    def focusOutEvent(self, event: QFocusEvent) -> None:
        self.__restore_cursor()

    def keyPressEvent(self, event: QKeyEvent) -> None:
        key = event.key()
        if   key == Qt.Key.Key_Left:
            self.__move_bbox(-1.0, 0.0)
        elif key == Qt.Key.Key_Right:
            self.__move_bbox(+1.0, 0.0)
        elif key == Qt.Key.Key_Up:
            self.__move_bbox(0.0, -1.0)
        elif key == Qt.Key.Key_Down:
            self.__move_bbox(0.0, +1.0)
        self.update()

    def leaveEvent(self, event: QEvent) -> None:
        self.__restore_cursor()

    def mouseDoubleClickEvent(self, event: QMouseEvent) -> None:
        pass

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        if self.pixmap is None:
            return

        pos = self.__transform_pos(event.pos())
        mx = pos.x()
        my = pos.y()
        mx_pre = self._mx
        my_pre = self._my
        dmx = mx - mx_pre if (mx_pre is not None) else None
        dmy = my - my_pre if (my_pre is not None) else None
        self._mx = mx
        self._my = my

        self.p.status_label.setText(f'X: {mx:.2f}; Y: {my:.2f}')

        if event.buttons() == Qt.MouseButton.LeftButton:
            if self.mode == CANVAS_EDIT_MODE:
                if   self._highlighted_bbox:
                    self.__move_bbox(dmx, dmy)
                    self.p.update_bboxes_from_canvas()
                elif self._highlighted_pidx is not None:
                    self._highlighted_pidx = self.__set_point(self._highlighted_pidx, mx, my)
                    self.p.update_bboxes_from_canvas()
                else:
                    self.p.scroll_request(dmx, Qt.Orientation.Horizontal)
                    self.p.scroll_request(dmy, Qt.Orientation.Vertical)
        else:
            if self.mode == CANVAS_EDIT_MODE:
                if not self.bbox.empty():
                    pidx = self.__nearest_point_idx(pos, 20.0 / self.__scale())
                    if   pidx is not None:
                        self._highlighted_bbox = False
                        self._highlighted_pidx = pidx
                        self.__override_cursor(Qt.CursorShape.PointingHandCursor)
                    elif (self.bbox.xmin() <= pos.x() <= self.bbox.xmax()) and \
                         (self.bbox.ymin() <= pos.y() <= self.bbox.ymax()):
                        self._highlighted_bbox = True
                        self._highlighted_pidx = None
                        self.__override_cursor(Qt.CursorShape.PointingHandCursor)
                    else:
                        self._highlighted_bbox = False
                        self._highlighted_pidx = None
                        self.__override_cursor(Qt.CursorShape.ArrowCursor)
                else:
                    self._highlighted_bbox = False
                    self._highlighted_pidx = None
                    self.__override_cursor(Qt.CursorShape.ArrowCursor)

        self.update()

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if self.pixmap is None:
            return

        pos = self.__transform_pos(event.pos())

        if event.button() == Qt.MouseButton.LeftButton:
            if self.mode == CANVAS_CREATE_MODE:
                self._bbox_sx = pos.x()
                self._bbox_sy = pos.y()
            if self.mode == CANVAS_EDIT_MODE:
                if (self._highlighted_bbox) or \
                   (self._highlighted_pidx is not None):
                    self.__override_cursor(Qt.CursorShape.PointingHandCursor)

        self.update()

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        if self.pixmap is None:
            return

        pos = self.__transform_pos(event.pos())

        if event.button() == Qt.MouseButton.LeftButton:
            if (self.mode == CANVAS_CREATE_MODE) and \
               (self._bbox_sx is not None) and \
               (self._bbox_sy is not None):
                self.bbox = BBox(
                    x=min(self._bbox_sx, pos.x()),
                    y=min(self._bbox_sy, pos.y()),
                    w=abs(pos.x() - self._bbox_sx),
                    h=abs(pos.y() - self._bbox_sy))
                self.p.update_bboxes_from_canvas()
                self.p.create_bbox_action.setEnabled(True)
                self.mode = CANVAS_EDIT_MODE
                self._highlighted_bbox = False
                self._highlighted_pidx = None
                self._bbox_sx = None
                self._bbox_sy = None

        self.update()

    def paintEvent(self, event: QPaintEvent) -> None:
        if self.pixmap is None:
            super(Canvas, self).paintEvent(event)
            return

        scale = self.__scale()
        point_size_base: float = 8.0

        p = self._painter
        p.begin(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        p.scale(scale, scale)
        p.translate(self.__offset_to_center())

        p.drawPixmap(0, 0, self.pixmap)

        if not self.bbox.empty():
            line_path = QPainterPath()
            line_path.moveTo(self.bbox.get_point(0))
            for pidx in range(4):
                line_path.lineTo(self.bbox.get_point(pidx))
            line_path.lineTo(self.bbox.get_point(0))
            if self._highlighted_bbox:
                pen = QPen(BBOX_HIGHLIGHTED_COLOR)
            else:
                pen = QPen(BBOX_COLOR)
            pen.setWidth(max(1, int(round(2.0 / scale))))
            p.setPen(pen)
            p.drawPath(line_path)

            for pidx in range(4):
                point = self.bbox.get_point(pidx)
                d = point_size_base / scale
                if pidx == self._highlighted_pidx:
                    d *= 1.0
                    path = QPainterPath()
                    path.addRect(point.x() - d / 2, point.y() - d / 2, d, d)
                    p.drawPath(path)
                    p.fillPath(path, POINT_HIGHLIGHTED_COLOR)
                else:
                    d *= 1.0
                    path = QPainterPath()
                    path.addEllipse(point, d / 2.0, d / 2.0)
                    p.drawPath(path)
                    p.fillPath(path, POINT_COLOR)

        if self.mode == CANVAS_CREATE_MODE:
            if (self._bbox_sx is None) and \
               (self._bbox_sy is None) and \
               (self.__in_pixmap_xy(self._mx, self._my)):
                p.setPen(QColor(0, 0, 0))
                p.drawLine(int(self._mx), 0, int(self._mx), int(self.pixmap.height()))
                p.drawLine(0, int(self._my), int(self.pixmap.width()), int(self._my))
            if (self._bbox_sx is not None) and \
               (self._bbox_sy is not None):
                p.setPen(BBOX_COLOR)
                p.setBrush(QBrush(Qt.BrushStyle.BDiagPattern))
                p.drawRect(int(min(self._bbox_sx, self._mx)),
                           int(min(self._bbox_sy, self._my)),
                           int(abs(self._mx - self._bbox_sx)),
                           int(abs(self._my - self._bbox_sy)))

        self.setAutoFillBackground(True)
        pal = self.palette()
        pal.setColor(self.backgroundRole(), QColor(232, 232, 232, 255))
        self.setPalette(pal)
        p.end()

    def wheelEvent(self, event: QWheelEvent) -> None:
        delta = event.angleDelta()
        h_delta = delta.x()
        v_delta = delta.y()
        modifier = event.modifiers()
        if (Qt.KeyboardModifier.ControlModifier == modifier) and v_delta:
            self.p.zoom_request(v_delta)
        else:
            v_delta and self.p.scroll_request(v_delta, Qt.Orientation.Vertical)
            h_delta and self.p.scroll_request(h_delta, Qt.Orientation.Horizontal)
        event.accept()

    def sizeHint(self):
        return self.minimumSizeHint()

    def minimumSizeHint(self):
        if self.pixmap:
            return self.__scale() * self.pixmap.size()
        return super(Canvas, self).minimumSizeHint()

    def set_mode(self, mode: int) -> None:
        self.mode = mode
        if mode == CANVAS_CREATE_MODE:
            self._highlighted_bbox = False
            self._highlighted_pidx = None

    def __current_cursor(self) -> Optional[QCursor]:
        cursor = QApplication.overrideCursor()
        if cursor is not None:
            cursor = cursor.shape()
        return cursor

    def __override_cursor(self, cursor: Qt.CursorShape) -> None:
        self._cursor = cursor
        if self.__current_cursor() is None:
            QApplication.setOverrideCursor(cursor)
        else:
            QApplication.changeOverrideCursor(cursor)

    def __restore_cursor(self) -> None:
        QApplication.restoreOverrideCursor()

    def __transform_pos(self, point: QPoint) -> QPointF:
        pointf = QPointF(point.x(), point.y())
        return pointf / self.__scale() - self.__offset_to_center()

    def __offset_to_center(self) -> QPointF:
        scale = self.__scale()
        area = super(Canvas, self).size()
        w = self.pixmap.width() * scale
        h = self.pixmap.height() * scale
        aw = area.width()
        ah = area.height()
        x = (aw - w) / (2 * scale) if (w < aw) else 0
        y = (ah - h) / (2 * scale) if (h < ah) else 0
        return QPointF(x, y)

    def __scale(self) -> float:
        return 0.01 * self.p.zoom_spinbox.value()

    def __in_pixmap_xy(self, x: int | float, y: int | float) -> bool:
        w, h = self.pixmap.width(), self.pixmap.height()
        return (0 <= x <= w) and (0 <= y <= h)
    
    def __in_pixmap_bbox(self, bbox: BBox) -> bool:
        return (self.pixmap is not None) and \
               (0 <= bbox.xmin()) and \
               (bbox.xmax() < self.pixmap.width()) and \
               (0 <= bbox.ymin()) and \
               (bbox.ymax() < self.pixmap.height())

    def __move_bbox(self, dx: float, dy: float) -> None:
        if self.bbox.empty():
            return
        bbox = copy.copy(self.bbox)
        bbox.move(dx, dy)
        if self.__in_pixmap_bbox(bbox):
            self.bbox = bbox

    def __set_point(self, pidx: int, x: float, y: float) -> int:
        if self.bbox.empty():
            return
        bbox = copy.copy(self.bbox)
        bbox.set_xy(pidx, x, y)
        if self.__in_pixmap_bbox(bbox):
            self.bbox = bbox
            cx = bbox.cx()
            cy = bbox.cy()
            if (x <= cx) and (y <= cy):
                return 0
            if (cx < x)  and (y <= cy):
                return 1
            if (cx < x)  and (cy < y):
                return 2
            if (x <= cx) and (cy < y):
                return 3

    def __nearest_point_idx(self, point: QPointF, eps: float) -> Optional[int]:
        def distance(p):
            return sqrt(p.x() * p.x() + p.y() * p.y())
        for i in range(4):
            if distance(self.bbox.get_point(i) - point) <= eps:
                return i
        return None


def natural_sort(list: list[str], key = lambda s:s):
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


def read_icon(name):
    path = osp.join('icon', name)
    if hasattr(sys, '_MEIPASS'):
        path = osp.join(sys._MEIPASS, path)
    return QIcon(QPixmap(path))

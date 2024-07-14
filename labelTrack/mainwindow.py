from dataclasses import dataclass
from functools import partial
import os.path as osp
from typing import Callable
from typing import Optional
from PyQt6.QtCore import *
from PyQt6.QtGui import *
from PyQt6.QtWidgets import *
from PyQt6.QtWidgets import QMessageBox as QMB
from labelTrack.__init__ import __appname__, __version__
from labelTrack.settings import settings
from labelTrack.defines import *
from labelTrack.utils import distance
from labelTrack.utils import scan_all_images
from labelTrack.utils import read_icon


CURSOR_DEFAULT = Qt.CursorShape.ArrowCursor
CURSOR_POINT   = Qt.CursorShape.PointingHandCursor
CURSOR_DRAW    = Qt.CursorShape.CrossCursor
CURSOR_MOVE    = Qt.CursorShape.ClosedHandCursor
CURSOR_GRAB    = Qt.CursorShape.OpenHandCursor

DEFAULT_LINE_COLOR = QColor(0, 255, 0, 128)
DEFAULT_FILL_COLOR = QColor(255, 0, 0, 128)
DEFAULT_SELECT_LINE_COLOR = QColor(255, 255, 255)
DEFAULT_SELECT_FILL_COLOR = QColor(0, 128, 255, 155)
DEFAULT_VERTEX_FILL_COLOR = QColor(0, 255, 0, 255)
DEFAULT_HVERTEX_FILL_COLOR = QColor(255, 0, 0)


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
    
    def move(self, dx: float, dy: float) -> None:
        self.x += dx
        self.y += dy

    def get_vertex(self, idx: int) -> tuple[float, float]:
        if idx == 0:
            return self.x, self.y
        if idx == 1:
            return self.x + self.w, self.y
        if idx == 2:
            return self.x + self.w, self.y + self.h
        if idx == 3:
            return self.x, self.y + self.h
        raise IndexError()

    def set_vertex(self, idx: int, x: float, y: float) -> None:
        x1, y1 = (x, y) if idx == 0 else self.get_vertex(0)
        x2, y2 = (x, y) if idx == 1 else self.get_vertex(1)
        x3, y3 = (x, y) if idx == 2 else self.get_vertex(2)
        x4, y4 = (x, y) if idx == 3 else self.get_vertex(3)
        xmin = min(x1, x2, x3, x4)
        ymin = min(y1, y2, y3, y4)
        xmax = max(x1, x2, x3, x4)
        ymax = max(y1, y2, y3, y4)
        self.x = xmin
        self.y = ymin
        self.w = xmax - xmin
        self.h = ymax - ymin

    def __getitem__(self, idx: int) -> QPointF:
        x, y = self.get_vertex(idx)
        return QPointF(x, y)

    def __str__(self) -> str:
        if self.empty():
            return '-1.00,-1.00,-1.00,-1.00'
        return f'{self.x:.2f},{self.y:.2f},{self.w:.2f},{self.h:.2f}'


class Shape:
    P_SQUARE, P_ROUND = range(2)

    MOVE_VERTEX, NEAR_VERTEX = range(2)

    line_color = DEFAULT_LINE_COLOR
    select_line_color = DEFAULT_SELECT_LINE_COLOR
    select_fill_color = DEFAULT_SELECT_FILL_COLOR
    vertex_fill_color = DEFAULT_VERTEX_FILL_COLOR
    h_vertex_fill_color = DEFAULT_HVERTEX_FILL_COLOR
    point_type = P_ROUND
    point_size = 8
    scale = 1.0

    def __init__(self):
        self.bbox = BBox()
        self.selected = False

        self._highlight_index = None
        self._highlight_mode = self.NEAR_VERTEX
        self._highlight_settings = {
            self.NEAR_VERTEX: (4, self.P_ROUND),
            self.MOVE_VERTEX: (1.5, self.P_SQUARE),
        }

    def paint(self, painter):
        if not self.bbox.empty():
            color = self.select_line_color if self.selected else self.line_color
            pen = QPen(color)
            # Try using integer sizes for smoother drawing(?)
            pen.setWidth(max(1, int(round(2.0 / self.scale))))
            painter.setPen(pen)

            line_path = QPainterPath()
            vertex_path = QPainterPath()

            line_path.moveTo(self.bbox[0])
            for i in range(4):
                point = self.bbox[i]
                line_path.lineTo(point)
                d = self.point_size / self.scale
                shape = self.point_type
                if i == self._highlight_index:
                    size, shape = self._highlight_settings[self._highlight_mode]
                    d *= size
                if self._highlight_index is not None:
                    self.vertex_fill_color = self.h_vertex_fill_color
                else:
                    self.vertex_fill_color = Shape.vertex_fill_color
                if shape == self.P_SQUARE:
                    vertex_path.addRect(point.x() - d / 2, point.y() - d / 2, d, d)
                elif shape == self.P_ROUND:
                    vertex_path.addEllipse(point, d / 2.0, d / 2.0)
                else:
                    assert False, "unsupported vertex shape"
            line_path.lineTo(self.bbox[0])

            painter.drawPath(line_path)
            painter.drawPath(vertex_path)
            painter.fillPath(vertex_path, self.vertex_fill_color)

    def nearest_vertex(self, point, epsilon):
        for i in range(4):
            if distance(self.bbox[i] - point) <= epsilon:
                return i
        return None

    def contains_point(self, point):
        return self.make_path().contains(point)

    def make_path(self):
        path = QPainterPath(self.bbox[0])
        for i in range(1, 4):
            path.lineTo(self.bbox[i])
        return path

    def bounding_rect(self):
        return self.make_path().boundingRect()

    def move_by(self, offset):
        self.bbox.move(offset.x(), offset.y())

    def move_vertex_by(self, i, offset):
        p = self.bbox.get_vertex(i)
        self.bbox.set_vertex(i, p[0] + offset.x(), p[1] + offset.y())

    def highlight_vertex(self, i, action):
        self._highlight_index = i
        self._highlight_mode = action

    def highlight_clear(self):
        self._highlight_index = None

    def __getitem__(self, key):
        return self.bbox[key]


class MainWindow(QMainWindow):

    def __init__(self,
                 image_dir: Optional[str] = None,
                 label_file: Optional[str] = None
                 ) -> None:
        super(MainWindow, self).__init__()
        self.setWindowTitle(__appname__)

        self._image_dir: Optional[str] = None
        self._label_file: Optional[str] = None
        self._bboxes: list[BBox] = []
        self._dirty: bool = False

        self.img_list = QListWidget()
        self.img_list.currentItemChanged.connect(self.file_current_item_changed)
        self.file_dock = QDockWidget('Image List', self)
        self.file_dock.setObjectName('images')
        self.file_dock.setWidget(self.img_list)

        self.canvas = Canvas(parent=self)

        self.scroll_area = QScrollArea()
        self.scroll_area.setWidget(self.canvas)
        self.scroll_area.setWidgetResizable(True)
        self.scroll_bars = {
            Qt.Orientation.Vertical: self.scroll_area.verticalScrollBar(),
            Qt.Orientation.Horizontal: self.scroll_area.horizontalScrollBar()}

        self.setCentralWidget(self.scroll_area)
        self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, self.file_dock)
        self.file_dock.setFeatures(QDockWidget.DockWidgetFeature.DockWidgetFloatable)

        self.quit_action = self.__new_action('Quit', icon_file='quit', slot=self.close, shortcut='Ctrl+Q')
        self.open_image_dir_action = self.__new_action('Open Image Dir', icon_file='open', slot=self.__open_image_dir_dialog)
        self.open_label_file_action = self.__new_action('Open Label File', icon_file='open', slot=self.__open_label_file_dialog)
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
        if not self.may_continue():
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

    def toggle_drawing_sensitive(self, drawing=True):
        if not drawing:
            self.canvas.set_editing(True)
            self.canvas.restore_cursor()

    def file_current_item_changed(self, item=None):
        self.__load_image()

    def may_continue(self):
        if not self._dirty:
            return True
        else:
            discard_changes = QMB.warning(
                self, 'Attention',
                'You have unsaved changes, would you like to save them and proceed?',
                QMB.Yes | QMB.No | QMB.Cancel)
            if discard_changes == QMB.No:
                return True
            elif discard_changes == QMB.Yes:
                self.__save_label_file()
                return True
            else:
                return False

    def update_shape(self):
        idx = self.img_list.currentRow()
        bbox = self._bboxes[idx]
        if not bbox.empty():
            shape = Shape()
            shape.bbox = bbox
            shape.line_color = QColor(227, 79, 208, 100)
            self.canvas.load_shape(shape)
        else:
            self.canvas.load_shape(None)

    def update_bbox_list_by_canvas(self):
        idx = self.img_list.currentRow()
        if self.canvas.shape is not None:
            self._bboxes[idx] = self.canvas.shape.bbox
        else:
            self._bboxes[idx] = BBox()
        self.set_dirty(True)

    def set_dirty(self, dirty: bool) -> None:
        self._dirty = dirty
        if dirty:
            self.save_action.setEnabled(True)
        else:
            self.save_action.setEnabled(False)

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

    def __open_image_dir_dialog(self):
        if not self.may_continue():
            return
        default_image_dir = '.'
        if self._image_dir and osp.exists(self._image_dir):
            default_image_dir = self._image_dir
        target_image_dir = QFileDialog.getExistingDirectory(
            self, f'{__appname__} - Open Image Directory', default_image_dir,
            QFileDialog.Option.ShowDirsOnly | QFileDialog.Option.DontResolveSymlinks)
        self.__load_image_dir(target_image_dir)

    def __open_label_file_dialog(self):
        default_label_path = '.'
        if self._label_file is not None:
            default_label_path = self._label_file
        target_file_path = QFileDialog.getSaveFileName(
            self, f'{__appname__} - Save label to the file',
            osp.dirname(default_label_path), 'Text (*.txt)',
            None, QFileDialog.Option.DontConfirmOverwrite)
        if target_file_path is not None and len(target_file_path) > 1:
            self.__load_label_file(target_file_path[0])
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
        self.canvas.set_editing(False)
        self.create_bbox_action.setEnabled(False)

    def __delete_bbox(self):
        self.canvas.shape = None
        self.update_bbox_list_by_canvas()
        self.canvas.update()

    def __copy_bbox(self):
        idx = self.img_list.currentRow()
        if 0 < idx:
            self._bboxes[idx] = self._bboxes[idx - 1]
            self.update_shape()

    def __load_image(self) -> None:
        item = self.img_list.currentItem()
        if item is None:
            return
        self.canvas.reset_state()
        self.canvas.setEnabled(False)
        file_path = osp.join(self._image_dir, item.text())
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
        self.canvas.load_pixmap(QPixmap.fromImage(img))
        self.status(f'Loaded {osp.basename(file_path)}')
        self.update_shape()
        self.set_dirty(False)
        self.canvas.setEnabled(True)
        self.__set_fit_window()
        idx = self.img_list.currentRow()
        cnt = self.img_list.count()
        counter = f'[{idx + 1} / {cnt}]'
        self.setWindowTitle(f'{__appname__} {file_path} {counter}')
        self.canvas.setFocus()
        self.canvas.update()

    def __load_image_dir(self, image_dir: Optional[str]) -> None:
        if not self.may_continue():
            return
        self._image_dir = image_dir
        self._label_file = None
        self._bboxes.clear()
        if image_dir is None:
            return
        img_files = scan_all_images(image_dir)
        self._bboxes = [BBox() for _ in range(len(img_files))]
        self.img_list.clear()
        for img_file in img_files:
            item = QListWidgetItem(osp.basename(img_file))
            self.img_list.addItem(item)
        self.img_list.setCurrentRow(0)
        self.__load_image()

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

    def __save_label_file(self) -> None:
        if self._label_file is None:
            return
        if self._dirty is False:
            return
        with open(self._label_file, 'w') as f:
            for bbox in self._bboxes:
                f.write(str(bbox) + '\n')
        self.set_dirty(False)
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
    epsilon = 11.0

    def __init__(self, parent: MainWindow) -> None:
        super(Canvas, self).__init__(parent)
        self.p = parent
        self.mode = CANVAS_EDIT_MODE
        self.pixmap: Optional[QPixmap] = None
        self.bbox: Optional[BBox] = None

        self._painter = QPainter()
        self._cursor = CURSOR_DEFAULT
        self._mx: Optional[float] = None
        self._my: Optional[float] = None
        self._bbox_sx: Optional[float] = None
        self._bbox_sy: Optional[float] = None
        self._highlighted: bool = False
        self._highlighted_pidx: Optional[int] = None

        self.shape = None
        self.selected_shape = None
        self.prev_point = QPointF()
        self.offsets = QPointF(), QPointF()
        self.h_shape = None
        self.h_vertex = None
        self.setMouseTracking(True)
        self.setFocusPolicy(Qt.FocusPolicy.WheelFocus)

        self.pan_initial_pos = QPoint()

    def enterEvent(self, event: QEnterEvent) -> None:
        self.override_cursor(self._cursor)

    def focusOutEvent(self, event: QFocusEvent) -> None:
        self.restore_cursor()

    def keyPressEvent(self, event: QKeyEvent) -> None:
        key = event.key()
        if   key == Qt.Key.Key_Left and self.selected_shape:
            self.move_one_pixel('Left')
        elif key == Qt.Key.Key_Right and self.selected_shape:
            self.move_one_pixel('Right')
        elif key == Qt.Key.Key_Up and self.selected_shape:
            self.move_one_pixel('Up')
        elif key == Qt.Key.Key_Down and self.selected_shape:
            self.move_one_pixel('Down')

    def leaveEvent(self, event: QEvent) -> None:
        self.restore_cursor()

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
        self._mx = mx
        self._my = my

        self.p.status_label.setText(f'X: {mx:.2f}; Y: {my:.2f}')

        if event.buttons() == Qt.MouseButton.LeftButton:
            if self.selected_vertex():
                self.bounded_move_vertex(pos)
                self.p.set_dirty(True)
                self.repaint()
                point1 = self.h_shape[1]
                point3 = self.h_shape[3]
                current_width = abs(point1.x() - point3.x())
                current_height = abs(point1.y() - point3.y())
                self.p.status_label.setText(f'W: {current_width:.2f}, H: {current_height:.2f} / X: {mx:.2f}; Y: {my:.2f}')
            elif self.selected_shape and self.prev_point:
                self.override_cursor(CURSOR_MOVE)
                self.bounded_move_shape(self.selected_shape, pos)
                self.p.set_dirty(True)
                self.repaint()
                point1 = self.selected_shape[1]
                point3 = self.selected_shape[3]
                current_width = abs(point1.x() - point3.x())
                current_height = abs(point1.y() - point3.y())
                self.p.status_label.setText(f'W: {current_width:.2f}, H: {current_height:.2f} / X: {mx:.2f}; Y: {my:.2f}')
            else:
                delta_x = pos.x() - self.pan_initial_pos.x()
                delta_y = pos.y() - self.pan_initial_pos.y()
                self.p.scroll_request(delta_x, Qt.Orientation.Horizontal)
                self.p.scroll_request(delta_y, Qt.Orientation.Vertical)
                self.update()
            self.p.update_bbox_list_by_canvas()
            return

        if self.shape is not None:
            index = self.shape.nearest_vertex(pos, self.epsilon)
            if index is not None:
                if self.selected_vertex():
                    self.h_shape.highlight_clear()
                self.h_vertex, self.h_shape = index, self.shape
                self.shape.highlight_vertex(index, self.shape.MOVE_VERTEX)
                self.override_cursor(CURSOR_POINT)
                self.setStatusTip(self.toolTip())
                self.update()
            elif self.shape.contains_point(pos):
                if self.selected_vertex():
                    self.h_shape.highlight_clear()
                self.h_vertex, self.h_shape = None, self.shape
                self.override_cursor(CURSOR_GRAB)
                self.update()
                # Display annotation width and height while hovering inside
                point1 = self.h_shape[1]
                point3 = self.h_shape[3]
                current_width = abs(point1.x() - point3.x())
                current_height = abs(point1.y() - point3.y())
                self.p.status_label.setText(f'W: {current_width:.2f}, H: {current_height:.2f} / X: {pos.x():.2f}; Y: {pos.y():.2f}')
        else:  # Nothing found, clear highlights, reset state.
            if self.h_shape:
                self.h_shape.highlight_clear()
                self.update()
            self.h_vertex, self.h_shape = None, None
            self.override_cursor(CURSOR_DEFAULT)

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
                selection = self.select_shape_point(pos)
                self.prev_point = pos
                if selection is None:
                    QApplication.setOverrideCursor(QCursor(Qt.CursorShape.OpenHandCursor))
                    self.pan_initial_pos = pos
        self.update()

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        if self.pixmap is None:
            return

        pos = self.__transform_pos(event.pos())
        if   event.button() == Qt.MouseButton.LeftButton and self.selected_shape:
            if self.selected_vertex():
                self.override_cursor(CURSOR_POINT)
            else:
                self.override_cursor(CURSOR_GRAB)
        elif event.button() == Qt.MouseButton.LeftButton:
            if (self.mode == CANVAS_CREATE_MODE) and \
               (self._bbox_sx is not None) and \
               (self._bbox_sy is not None):
                x1 = self._bbox_sx
                y1 = self._bbox_sy
                x2 = pos.x()
                y2 = pos.y()
                self.shape = Shape()
                self.shape.bbox = BBox(
                    x=min(x1, x2),
                    y=min(y1, y2),
                    w=abs(x2 - x1),
                    h=abs(y2 - y1))
                self.p.update_bbox_list_by_canvas()
                self.set_editing(True)
                self.p.create_bbox_action.setEnabled(True)
                self.p.set_dirty(True)
                self.update()
            else:
                QApplication.restoreOverrideCursor()

    def paintEvent(self, event: QPaintEvent) -> None:
        if self.pixmap is None:
            super(Canvas, self).paintEvent(event)
            return

        scale = self.__scale()

        p = self._painter
        p.begin(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        p.scale(scale, scale)
        p.translate(self.__offset_to_center())

        p.drawPixmap(0, 0, self.pixmap)
        Shape.scale = scale
        if self.shape is not None:
            self.shape.paint(p)
        
        if self.mode == CANVAS_CREATE_MODE:
            if (self._bbox_sx is None) and \
               (self._bbox_sy is None) and \
               (self.__in_pixmap(self._mx, self._my)):
                p.setPen(QColor(0, 0, 0))
                p.drawLine(int(self._mx), 0, int(self._mx), int(self.pixmap.height()))
                p.drawLine(0, int(self._my), int(self.pixmap.width()), int(self._my))
            if (self._bbox_sx is not None) and \
               (self._bbox_sy is not None):
                p.setPen(DEFAULT_LINE_COLOR)
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

    def set_editing(self, value=True):
        self.mode = CANVAS_EDIT_MODE if value else CANVAS_CREATE_MODE
        if not value:  # Create
            self.un_highlight()
            self.de_select_shape()
        self.prev_point = QPointF()
        self.repaint()

    def un_highlight(self, shape=None):
        if shape == None or shape == self.h_shape:
            if self.h_shape:
                self.h_shape.highlight_clear()
            self.h_vertex = self.h_shape = None

    def selected_vertex(self):
        return self.h_vertex is not None

    def select_shape(self, shape):
        self.de_select_shape()
        shape.selected = True
        self.selected_shape = shape
        self.update()

    def select_shape_point(self, point):
        """Select the first shape created which contains this point."""
        self.de_select_shape()
        if self.selected_vertex():  # A vertex is marked for selection.
            index, shape = self.h_vertex, self.h_shape
            shape.highlight_vertex(index, shape.MOVE_VERTEX)
            self.select_shape(shape)
            return self.h_vertex
        if self.shape is not None:
            if self.shape.contains_point(point):
                self.select_shape(self.shape)
                self.calculate_offsets(self.shape, point)
                return self.selected_shape
        return None

    def calculate_offsets(self, shape, point):
        rect = shape.bounding_rect()
        x1 = rect.x() - point.x()
        y1 = rect.y() - point.y()
        x2 = (rect.x() + rect.width()) - point.x()
        y2 = (rect.y() + rect.height()) - point.y()
        self.offsets = QPointF(x1, y1), QPointF(x2, y2)

    def bounded_move_vertex(self, pos):
        index, shape = self.h_vertex, self.h_shape
        point = shape[index]
        if not self.__in_pixmap(pos.x(), pos.y()):
            size = self.pixmap.size()
            clipped_x = min(max(0, pos.x()), size.width())
            clipped_y = min(max(0, pos.y()), size.height())
            pos = QPointF(clipped_x, clipped_y)
        shift_pos = pos - point
        shape.move_vertex_by(index, shift_pos)
        left_index = (index + 1) % 4
        right_index = (index + 3) % 4
        if index % 2 == 0:
            right_shift = QPointF(shift_pos.x(), 0)
            left_shift = QPointF(0, shift_pos.y())
        else:
            left_shift = QPointF(shift_pos.x(), 0)
            right_shift = QPointF(0, shift_pos.y())
        shape.move_vertex_by(right_index, right_shift)
        shape.move_vertex_by(left_index, left_shift)

    def bounded_move_shape(self, shape, pos):
        if not self.__in_pixmap(pos.x(), pos.y()):
            return False  # No need to move
        o1 = pos + self.offsets[0]
        if not self.__in_pixmap(o1.x(), o1.y()):
            pos -= QPointF(min(0, o1.x()), min(0, o1.y()))
        o2 = pos + self.offsets[1]
        if not self.__in_pixmap(o2.x(), o2.y()):
            pos += QPointF(min(0, self.pixmap.width() - o2.x()),
                           min(0, self.pixmap.height() - o2.y()))
        # The next line tracks the new position of the cursor
        # relative to the shape, but also results in making it
        # a bit "shaky" when nearing the border and allows it to
        # go outside of the shape's area for some reason. XXX
        # self.calculateOffsets(self.selectedShape, pos)
        dp = pos - self.prev_point
        if dp:
            shape.move_by(dp)
            self.prev_point = pos
            return True
        return False

    def de_select_shape(self):
        if self.selected_shape:
            self.selected_shape.selected = False
            self.selected_shape = None
            self.update()

    def close_enough(self, p1, p2):
        # d = distance(p1 - p2)
        # m = (p1-p2).manhattanLength()
        # print "d %.2f, m %d, %.2f" % (d, m, d - m)
        return distance(p1 - p2) < self.epsilon

    def move_one_pixel(self, direction):
        # print(self.selectedShape.points)
        if direction == 'Left' and not self.move_out_of_bound(QPointF(-1.0, 0)):
            # print("move Left one pixel")
            self.selected_shape.points[0] += QPointF(-1.0, 0)
            self.selected_shape.points[1] += QPointF(-1.0, 0)
            self.selected_shape.points[2] += QPointF(-1.0, 0)
            self.selected_shape.points[3] += QPointF(-1.0, 0)
        elif direction == 'Right' and not self.move_out_of_bound(QPointF(1.0, 0)):
            # print("move Right one pixel")
            self.selected_shape.points[0] += QPointF(1.0, 0)
            self.selected_shape.points[1] += QPointF(1.0, 0)
            self.selected_shape.points[2] += QPointF(1.0, 0)
            self.selected_shape.points[3] += QPointF(1.0, 0)
        elif direction == 'Up' and not self.move_out_of_bound(QPointF(0, -1.0)):
            # print("move Up one pixel")
            self.selected_shape.points[0] += QPointF(0, -1.0)
            self.selected_shape.points[1] += QPointF(0, -1.0)
            self.selected_shape.points[2] += QPointF(0, -1.0)
            self.selected_shape.points[3] += QPointF(0, -1.0)
        elif direction == 'Down' and not self.move_out_of_bound(QPointF(0, 1.0)):
            # print("move Down one pixel")
            self.selected_shape.points[0] += QPointF(0, 1.0)
            self.selected_shape.points[1] += QPointF(0, 1.0)
            self.selected_shape.points[2] += QPointF(0, 1.0)
            self.selected_shape.points[3] += QPointF(0, 1.0)
        self.p.set_dirty(True)
        self.repaint()

    def move_out_of_bound(self, step):
        points = [p1 + p2 for p1, p2 in zip(self.selected_shape.points, [step] * 4)]
        return True in map(self.__in_pixmap, points)

    def load_pixmap(self, pixmap):
        self.pixmap = pixmap
        self.repaint()

    def load_shape(self, shape):
        self.shape = shape
        self.repaint()

    def current_cursor(self):
        cursor = QApplication.overrideCursor()
        if cursor is not None:
            cursor = cursor.shape()
        return cursor

    def override_cursor(self, cursor):
        self._cursor = cursor
        if self.current_cursor() is None:
            QApplication.setOverrideCursor(cursor)
        else:
            QApplication.changeOverrideCursor(cursor)

    def restore_cursor(self):
        QApplication.restoreOverrideCursor()

    def reset_state(self):
        self.restore_cursor()
        self.pixmap = None
        self.update()

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

    def __in_pixmap(self, x: int | float, y: int | float) -> bool:
        w, h = self.pixmap.width(), self.pixmap.height()
        return (0 <= x <= w) and (0 <= y <= h)

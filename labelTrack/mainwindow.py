from functools import partial
import os.path as osp
from PyQt6.QtCore import *
from PyQt6.QtGui import *
from PyQt6.QtWidgets import *
from PyQt6.QtWidgets import QMessageBox as QMB
from labelTrack.__init__ import __appname__, __version__
from labelTrack.settings import settings
from labelTrack.defines import *
from labelTrack.shape import Shape, DEFAULT_LINE_COLOR
from labelTrack.utils import distance
from labelTrack.utils import scan_all_images
from labelTrack.utils import read_icon


CURSOR_DEFAULT = Qt.CursorShape.ArrowCursor
CURSOR_POINT = Qt.CursorShape.PointingHandCursor
CURSOR_DRAW = Qt.CursorShape.CrossCursor
CURSOR_MOVE = Qt.CursorShape.ClosedHandCursor
CURSOR_GRAB = Qt.CursorShape.OpenHandCursor


class MainWindow(QMainWindow):
    FIT_WINDOW, FIT_WIDTH, MANUAL_ZOOM = list(range(3))

    def __init__(self, image_dir, label_path):
        super(MainWindow, self).__init__()
        self.setWindowTitle(__appname__)

        self.image_dir = image_dir
        self.label_path = label_path
        self.bbox_list = []
        self.dirty = False

        self.img_list_widget = QListWidget()
        self.img_list_widget.currentItemChanged.connect(self.file_current_item_changed)
        file_list_layout = QVBoxLayout()
        file_list_layout.setContentsMargins(0, 0, 0, 0)
        file_list_layout.addWidget(self.img_list_widget)
        file_list_container = QWidget()
        file_list_container.setLayout(file_list_layout)
        self.file_dock = QDockWidget('Image List', self)
        self.file_dock.setObjectName('images')
        self.file_dock.setWidget(file_list_container)

        self.canvas = Canvas(parent=self)
        self.canvas.zoomRequest.connect(self.zoom_request)
        self.canvas.set_drawing_color(DEFAULT_LINE_COLOR)

        scroll = QScrollArea()
        scroll.setWidget(self.canvas)
        scroll.setWidgetResizable(True)
        self.scroll_bars = {
            Qt.Orientation.Vertical: scroll.verticalScrollBar(),
            Qt.Orientation.Horizontal: scroll.horizontalScrollBar()}
        self.scroll_area = scroll
        self.canvas.scrollRequest.connect(self.scroll_request)

        self.canvas.newShape.connect(self.new_shape)
        self.canvas.shapeMoved.connect(self.set_dirty)
        self.canvas.drawingPolygon.connect(self.toggle_drawing_sensitive)

        self.setCentralWidget(scroll)
        self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, self.file_dock)
        self.file_dock.setFeatures(QDockWidget.DockWidgetFeature.DockWidgetFloatable)

        self.quit_action = QAction('Quit', self)
        self.quit_action.setIcon(read_icon('quit'))
        self.quit_action.setShortcut('Ctrl+Q')
        self.quit_action.triggered.connect(self.close)
        self.open_image_dir_action = QAction('Open Image Dir', self)
        self.open_image_dir_action.setIcon(read_icon('open'))
        self.open_image_dir_action.triggered.connect(self.open_image_dir_dialog)
        self.open_label_file_action = QAction('Open Label File', self)
        self.open_label_file_action.setIcon(read_icon('open'))
        self.open_label_file_action.triggered.connect(self.open_label_file_dialog)
        self.next_image_action = QAction('Next Image', self)
        self.next_image_action.setIcon(read_icon('next'))
        self.next_image_action.setShortcut('d')
        self.next_image_action.triggered.connect(self.open_next_image)
        self.prev_image_action = QAction('Previous Image', self)
        self.prev_image_action.setIcon(read_icon('prev'))
        self.prev_image_action.setShortcut('a')
        self.prev_image_action.triggered.connect(self.open_prev_image)
        self.save_action = QAction('Save', self)
        self.save_action.setIcon(read_icon('save'))
        self.save_action.setShortcut('Ctrl+s')
        self.save_action.triggered.connect(self.save_file)
        self.create_object_action = QAction('Create Object', self)
        self.create_object_action.setIcon(read_icon('objects'))
        self.create_object_action.setShortcut('w')
        self.create_object_action.triggered.connect(self.create_object)
        self.delete_object_action = QAction('Delete Object', self)
        self.delete_object_action.setIcon(read_icon('close'))
        self.delete_object_action.setShortcut('c')
        self.delete_object_action.triggered.connect(self.delete_object)
        self.copy_object_action = QAction('Copy Object', self)
        self.copy_object_action.setIcon(read_icon('copy'))
        self.copy_object_action.setShortcut('r')
        self.copy_object_action.triggered.connect(self.copy_object)
        self.next_image_and_copy_action = QAction('Next Image and Copy', self)
        self.next_image_and_copy_action.setIcon(read_icon('next'))
        self.next_image_and_copy_action.setShortcut('t')
        self.next_image_and_copy_action.triggered.connect(self.next_image_and_copy)
        self.next_image_and_delete_action = QAction('Next Image and Delete', self)
        self.next_image_and_delete_action.setIcon(read_icon('next'))
        self.next_image_and_delete_action.setShortcut('v')
        self.next_image_and_delete_action.triggered.connect(self.next_image_and_delete)
        self.show_info_action = QAction('info', self)
        self.show_info_action.setIcon(read_icon('help'))
        self.show_info_action.triggered.connect(self.show_info_dialog)
        self.auto_saving_action = QAction('autoSaveMode', self)
        self.auto_saving_action.setCheckable(True)
        self.auto_saving_action.setChecked(settings.get(SETTINGS_KEY_AUTO_SAVE, True))
        self.zoom_widget = ZoomWidget()
        self.zoom_widget.setEnabled(True)
        self.zoom_widget.valueChanged.connect(self.paint_canvas)
        self.zoom_action = QWidgetAction(self)
        self.zoom_action.setDefaultWidget(self.zoom_widget)
        self.zoom_in_action = QAction('Zoom In', self)
        self.zoom_in_action.setIcon(read_icon('zoom-in'))
        self.zoom_in_action.setShortcut('Ctrl++')
        self.zoom_in_action.triggered.connect(partial(self.add_zoom, 10))
        self.zoom_out_action = QAction('Zoom Out', self)
        self.zoom_out_action.setIcon(read_icon('zoom-out'))
        self.zoom_out_action.setShortcut('Ctrl+-')
        self.zoom_out_action.triggered.connect(partial(self.add_zoom, -10))
        self.zoom_org_action = QAction('Original Size', self)
        self.zoom_org_action.setIcon(read_icon('zoom'))
        self.zoom_org_action.setShortcut('Ctrl+=')
        self.zoom_org_action.triggered.connect(partial(self.set_zoom, 100))
        self.fit_window_action = QAction('Fit Window', self)
        self.fit_window_action.setIcon(read_icon('fit-window'))
        self.fit_window_action.setShortcut('Ctrl+F')
        self.fit_window_action.triggered.connect(self.set_fit_window)
        self.fit_window_action.setCheckable(True)
        self.fit_width_action = QAction('Fit Width', self)
        self.fit_width_action.setIcon(read_icon('fit-width'))
        self.fit_width_action.setShortcut('Ctrl+Shift+F')
        self.fit_width_action.triggered.connect(self.set_fit_width)
        self.fit_width_action.setCheckable(True)
        self.zoom_mode = self.MANUAL_ZOOM
        self.scalers = {
            self.FIT_WINDOW: self.scale_fit_window,
            self.FIT_WIDTH: self.scale_fit_width,
            self.MANUAL_ZOOM: lambda: 1}
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
        self.menus_edit.addAction(self.create_object_action)
        self.menus_edit.addAction(self.delete_object_action)
        self.menus_edit.addAction(self.copy_object_action)
        self.menus_edit.addAction(self.next_image_and_copy_action)
        self.menus_edit.addAction(self.next_image_and_delete_action)
        self.menus_view.addAction(self.auto_saving_action)
        self.menus_view.addSeparator()
        self.menus_view.addAction(self.zoom_in_action)
        self.menus_view.addAction(self.zoom_out_action)
        self.menus_view.addAction(self.zoom_org_action)
        self.menus_view.addSeparator()
        self.menus_view.addAction(self.fit_window_action)
        self.menus_view.addAction(self.fit_width_action)
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
        self.toolbar.addAction(self.create_object_action)
        self.toolbar.addAction(self.delete_object_action)
        self.toolbar.addSeparator()
        self.toolbar.addAction(self.zoom_in_action)
        self.toolbar.addAction(self.zoom_action)
        self.toolbar.addAction(self.zoom_out_action)
        self.toolbar.addAction(self.fit_window_action)
        self.toolbar.addAction(self.fit_width_action)
        self.statusBar().showMessage(f'{__appname__} started.')
        self.statusBar().show()
        self.image = QImage()
        self.zoom_level = 100
        self.fit_window = False

        window_x = settings.get(SETTINGS_KEY_WINDOW_X, 0)
        window_y = settings.get(SETTINGS_KEY_WINDOW_Y, 0)
        window_w = settings.get(SETTINGS_KEY_WINDOW_W, 600)
        window_h = settings.get(SETTINGS_KEY_WINDOW_H, 500)
        position = QPoint(window_x, window_y)
        size = QSize(window_w, window_h)
        self.resize(size)
        self.move(position)

        self.load_label()
        self.load_image_dir()

        self.label_coordinates = QLabel('')
        self.statusBar().addPermanentWidget(self.label_coordinates)

    def closeEvent(self, event: QCloseEvent) -> None:
        if not self.may_continue():
            event.ignore()
        settings.set(SETTINGS_KEY_IMAGE_DIR, self.image_dir if self.image_dir is not None else '.')
        settings.set(SETTINGS_KEY_LABEL_PATH, self.label_path if self.label_path is not None else '.')
        settings.set(SETTINGS_KEY_WINDOW_X, self.pos().x())
        settings.set(SETTINGS_KEY_WINDOW_Y, self.pos().y())
        settings.set(SETTINGS_KEY_WINDOW_W, self.size().width())
        settings.set(SETTINGS_KEY_WINDOW_H, self.size().height())
        settings.set(SETTINGS_KEY_AUTO_SAVE, self.auto_saving_action.isChecked())
        settings.save()

    def resizeEvent(self, event: QResizeEvent) -> None:
        if (self.canvas) and \
           (not self.image.isNull()) and \
           (self.zoom_mode != self.MANUAL_ZOOM):
            self.adjust_scale()
        super(MainWindow, self).resizeEvent(event)

    def status(self, message, delay=5000):
        self.statusBar().showMessage(message, delay)

    def toggle_drawing_sensitive(self, drawing=True):
        if not drawing:
            self.canvas.set_editing(True)
            self.canvas.restore_cursor()

    def file_current_item_changed(self, item=None):
        self.load_image()

    def new_shape(self):
        self.update_bbox_list_by_canvas()
        self.canvas.set_editing(True)
        self.create_object_action.setEnabled(True)
        self.set_dirty()

    def toggle_polygons(self, value):
        for item, shape in self.items_to_shapes.items():
            item.setCheckState(Qt.CheckState.Checked if value else Qt.CheckState.Unchecked)

    def load_image_dir(self):
        if not self.may_continue() or self.image_dir is None:
            return
        self.img_list_widget.clear()
        img_paths = scan_all_images(self.image_dir)
        for img_path in img_paths:
            item = QListWidgetItem(osp.basename(img_path))
            self.img_list_widget.addItem(item)
        self.img_list_widget.setCurrentRow(0)
        self.load_image()

    def open_image_dir_dialog(self, _value=False):
        if not self.may_continue():
            return
        default_image_dir = '.'
        if self.image_dir and osp.exists(self.image_dir):
            default_image_dir = self.image_dir
        target_image_dir = QFileDialog.getExistingDirectory(
            self, f'{__appname__} - Open Image Directory', default_image_dir,
            QFileDialog.Option.ShowDirsOnly | QFileDialog.Option.DontResolveSymlinks)
        self.image_dir = target_image_dir
        self.load_image_dir()

    def open_label_file_dialog(self, _value=False):
        default_label_path = '.'
        if self.label_path is not None:
            default_label_path = self.label_path
        target_file_path = QFileDialog.getSaveFileName(
            self, f'{__appname__} - Save label to the file',
            osp.dirname(default_label_path), 'Text (*.txt)',
            None, QFileDialog.Option.DontConfirmOverwrite)
        if target_file_path is not None and len(target_file_path) > 1:
            self.label_path = target_file_path[0]
            self.load_label()
        self.statusBar().showMessage(f'Label will be saved to {self.label_path}.')
        self.statusBar().show()

    def open_prev_image(self, _value=False):
        cnt = self.img_list_widget.count()
        idx = self.img_list_widget.currentRow()
        if self.auto_saving_action.isChecked():
            self.save_file()
        if cnt <= 0:
            return
        if 0 <= idx - 1:
            idx -= 1
            self.img_list_widget.setCurrentRow(idx)
        self.load_image()

    def open_next_image(self, _value=False):
        cnt = self.img_list_widget.count()
        idx = self.img_list_widget.currentRow()
        if self.auto_saving_action.isChecked():
            self.save_file()
        if idx + 1 < cnt:
            idx += 1
            self.img_list_widget.setCurrentRow(idx)
        self.load_image()

    def save_file(self, _value=False):
        if self.label_path is None:
            return
        if self.dirty is False:
            return
        with open(self.label_path, 'w') as f:
            for box in self.bbox_list:
                f.write(box)
        self.set_clean()
        self.statusBar().showMessage(f'Saved to {self.label_path}')
        self.statusBar().show()
        self.dirty = False

    def create_object(self):
        if self.image.isNull():
            return
        self.canvas.set_editing(False)
        self.create_object_action.setEnabled(False)

    def delete_object(self):
        self.canvas.shape = None
        self.update_bbox_list_by_canvas()
        self.canvas.update()

    def copy_object(self):
        if self.img_list_widget is None:
            return
        idx = self.img_list_widget.currentRow()
        if 0 < idx:
            self.bbox_list[idx] = self.bbox_list[idx - 1]
            self.update_shape()

    def next_image_and_copy(self):
        self.open_next_image()
        self.copy_object()

    def next_image_and_delete(self):
        self.open_next_image()
        self.delete_object()

    def show_info_dialog(self):
        msg = f'Name:{__appname__} \nApp Version:{__version__}'
        QMB.information(self, 'Information', msg)

    def scroll_request(self, delta, orientation):
        units = - delta / (8 * 15)
        bar = self.scroll_bars[orientation]
        bar.setValue(int(bar.value() + bar.singleStep() * units))

    def set_zoom(self, value):
        self.fit_width_action.setChecked(False)
        self.fit_window_action.setChecked(False)
        self.zoom_mode = self.MANUAL_ZOOM
        self.zoom_widget.setValue(int(value))

    def add_zoom(self, increment=10):
        self.set_zoom(self.zoom_widget.value() + increment)

    def zoom_request(self, delta):
        # get the current scrollbar positions
        # calculate the percentages ~ coordinates
        h_bar = self.scroll_bars[Qt.Orientation.Horizontal]
        v_bar = self.scroll_bars[Qt.Orientation.Vertical]
        # get the current maximum, to know the difference after zooming
        h_bar_max = h_bar.maximum()
        v_bar_max = v_bar.maximum()
        # get the cursor position and canvas size
        # calculate the desired movement from 0 to 1
        # where 0 = move left
        #       1 = move right
        # up and down analogous
        cursor = QCursor()
        pos = cursor.pos()
        relative_pos = QWidget.mapFromGlobal(self, pos)
        cursor_x = relative_pos.x()
        cursor_y = relative_pos.y()
        w = self.scroll_area.width()
        h = self.scroll_area.height()
        # the scaling from 0 to 1 has some padding
        # you don't have to hit the very leftmost pixel for a maximum-left movement
        margin = 0.1
        move_x = (cursor_x - margin * w) / (w - 2 * margin * w)
        move_y = (cursor_y - margin * h) / (h - 2 * margin * h)
        # clamp the values from 0 to 1
        move_x = min(max(move_x, 0), 1)
        move_y = min(max(move_y, 0), 1)
        # zoom in
        units = delta // (8 * 15)
        scale = 10
        self.add_zoom(scale * units)
        # get the difference in scrollbar values
        # this is how far we can move
        d_h_bar_max = h_bar.maximum() - h_bar_max
        d_v_bar_max = v_bar.maximum() - v_bar_max
        # get the new scrollbar values
        new_h_bar_value = int(h_bar.value() + move_x * d_h_bar_max)
        new_v_bar_value = int(v_bar.value() + move_y * d_v_bar_max)
        h_bar.setValue(new_h_bar_value)
        v_bar.setValue(new_v_bar_value)

    def set_fit_window(self, value=True):
        if self.image.isNull():
            self.fit_window_action.setChecked(False)
            return
        self.fit_width_action.setChecked(False)
        self.zoom_mode = self.FIT_WINDOW
        self.adjust_scale()

    def set_fit_width(self, value=True):
        if self.image.isNull():
            self.fit_width_action.setChecked(False)
            return
        self.fit_window_action.setChecked(False)
        self.zoom_mode = self.FIT_WIDTH
        self.adjust_scale()

    def paint_canvas(self):
        if self.image.isNull():
            return
        self.canvas.scale = 0.01 * self.zoom_widget.value()
        self.canvas.adjustSize()
        self.canvas.update()

    def adjust_scale(self, initial=False):
        value = self.scalers[self.FIT_WINDOW if initial else self.zoom_mode]()
        self.zoom_widget.setValue(int(100 * value))

    def scale_fit_window(self):
        """Figure out the size of the pixmap in order to fit the main widget."""
        e = 2.0  # So that no scrollbars are generated.
        w1 = self.centralWidget().width() - e
        h1 = self.centralWidget().height() - e
        a1 = w1 / h1
        # Calculate a new scale value based on the pixmap's aspect ratio.
        w2 = self.canvas.pixmap.width() - 0.0
        h2 = self.canvas.pixmap.height() - 0.0
        a2 = w2 / h2
        return w1 / w2 if a2 >= a1 else h1 / h2

    def scale_fit_width(self):
        # The epsilon does not seem to work too well here.
        w = self.centralWidget().width() - 2.0
        return w / self.canvas.pixmap.width()

    def may_continue(self):
        if not self.dirty:
            return True
        else:
            discard_changes = QMB.warning(
                self, 'Attention',
                'You have unsaved changes, would you like to save them and proceed?',
                QMB.Yes | QMB.No | QMB.Cancel)
            if discard_changes == QMB.No:
                return True
            elif discard_changes == QMB.Yes:
                self.save_file()
                return True
            else:
                return False

    def load_image(self):
        item = self.img_list_widget.currentItem()
        if item is None:
            return
        self.canvas.reset_state()
        self.canvas.setEnabled(False)
        file_path = osp.join(self.image_dir, item.text())
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
        self.image = img
        self.canvas.load_pixmap(QPixmap.fromImage(img))
        self.status(f'Loaded {osp.basename(file_path)}')
        self.update_shape()
        self.set_clean()
        self.canvas.setEnabled(True)
        self.adjust_scale(initial=True)
        self.paint_canvas()
        idx = self.img_list_widget.currentRow()
        cnt = self.img_list_widget.count()
        counter = f'[{idx + 1} / {cnt}]'
        self.setWindowTitle(f'{__appname__} {file_path} {counter}')
        self.canvas.setFocus()

    def load_label(self):
        if self.label_path is None:
            return
        if not osp.exists(self.label_path):
            with open(self.label_path, 'w') as f:
                pass
            self.bbox_list = []
            return
        with open(self.label_path) as f:
            self.bbox_list = f.readlines()

    def update_shape(self):
        idx = self.img_list_widget.currentRow()
        x, y, w, h = self.read_bbox_list(idx)
        xmin, ymin, xmax, ymax = x, y, x + w, y + h
        if 0.0 < w and 0.0 < h:
            shape = Shape()
            shape.add_point(QPointF(xmin, ymin))
            shape.add_point(QPointF(xmax, ymin))
            shape.add_point(QPointF(xmax, ymax))
            shape.add_point(QPointF(xmin, ymax))
            shape.close()
            shape.line_color = QColor(227, 79, 208, 100)
            shape.fill_color = QColor(227, 79, 208, 100)
            self.canvas.load_shape(shape)
        else:
            self.canvas.load_shape(None)

    def read_bbox_list(self, idx):
        while len(self.bbox_list) <= idx:
            self.bbox_list.append(f'-1.00,-1.00,-1.00,-1.00\n')
        r = self.bbox_list[idx].split(',')
        x, y, w, h = float(r[0]), float(r[1]), float(r[2]), float(r[3])
        return x, y, w, h

    def update_bbox_list(self, idx, x, y, h, w):
        if self.bbox_list is None:
            return
        while len(self.bbox_list) <= idx:
            self.bbox_list.append(f'-1.00,-1.00,-1.00,-1.00\n')
        self.bbox_list[idx] = f'{x:0.2f},{y:0.2f},{w:0.2f},{h:0.2f}\n'

    def update_bbox_list_by_canvas(self):
        idx = self.img_list_widget.currentRow()
        if self.bbox_list is None:
            return
        s = self.canvas.shape
        if s is not None:
            pts = [(p.x(), p.y()) for p in s.points]
            x1, y1, x2, y2 = pts[0][0], pts[0][1], pts[2][0], pts[2][1]
            xmin, ymin, xmax, ymax = min(x1, x2), min(y1, y2), max(x1, x2), max(y1, y2)
            x, y, w, h = xmin, ymin, xmax - xmin, ymax - ymin
            self.update_bbox_list(idx, x, y, h, w)
        else:
            self.update_bbox_list(idx, -1.0, -1.0, -1.0, -1.0)
        self.set_dirty()

    def set_dirty(self):
        self.dirty = True
        self.save_action.setEnabled(True)

    def set_clean(self):
        self.dirty = False
        self.save_action.setEnabled(False)


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


class ZoomWidget(QSpinBox):

    def __init__(self, value=100):
        super(ZoomWidget, self).__init__()
        self.setButtonSymbols(QAbstractSpinBox.ButtonSymbols.NoButtons)
        self.setRange(1, 500)
        self.setSuffix(' %')
        self.setValue(value)
        self.setToolTip(u'Zoom Level')
        self.setStatusTip(self.toolTip())
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)


class Canvas(QWidget):
    zoomRequest = pyqtSignal(int)
    scrollRequest = pyqtSignal(int, object)
    newShape = pyqtSignal()
    selectionChanged = pyqtSignal(bool)
    shapeMoved = pyqtSignal()
    drawingPolygon = pyqtSignal(bool)

    CREATE, EDIT = list(range(2))

    epsilon = 11.0

    def __init__(self, parent):
        super(Canvas, self).__init__(parent)
        self.p = parent
        self.mode = self.EDIT
        self.shape = None
        self.current = None
        self.selected_shape = None
        self.drawing_line_color = QColor(0, 0, 255)
        self.drawing_rect_color = QColor(0, 0, 255)
        self.line = Shape()
        self.prev_point = QPointF()
        self.offsets = QPointF(), QPointF()
        self.scale = 1.0
        self.pixmap = QPixmap()
        self.h_shape = None
        self.h_vertex = None
        self._painter = QPainter()
        self._cursor = CURSOR_DEFAULT
        self.setMouseTracking(True)
        self.setFocusPolicy(Qt.FocusPolicy.WheelFocus)

        # initialisation for panning
        self.pan_initial_pos = QPoint()

    def enterEvent(self, event: QEnterEvent) -> None:
        self.override_cursor(self._cursor)

    def focusOutEvent(self, event: QFocusEvent) -> None:
        self.restore_cursor()

    def keyPressEvent(self, event: QKeyEvent) -> None:
        key = event.key()
        if   key == Qt.Key.Key_Escape and self.current:
            print('ESC press')
            self.current = None
            self.drawingPolygon.emit(False)
            self.update()
        elif key == Qt.Key.Key_Return and self.can_close_shape():
            self.finalise()
        elif key == Qt.Key.Key_Left and self.selected_shape:
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
        """Update line with last point and current coordinates."""
        pos = self.transform_pos(event.pos())
        self.p.label_coordinates.setText(
            f'X: {pos.x():.1f}; Y: {pos.y():.1f}')
        # Polygon drawing.
        if self.drawing():
            self.override_cursor(CURSOR_DRAW)
            if self.current:
                # Display annotation width and height while drawing
                current_width = abs(self.current[0].x() - pos.x())
                current_height = abs(self.current[0].y() - pos.y())
                self.parent().window().label_coordinates.setText(
                    f'Width: {current_width}, Height: {current_height} / X: {pos.x()}; Y: {pos.y()}')
                color = self.drawing_line_color
                if self.out_of_pixmap(pos):
                    # Don't allow the user to draw outside the pixmap.
                    # Clip the coordinates to 0 or max,
                    # if they are outside the range [0, max]
                    size = self.pixmap.size()
                    clipped_x = min(max(0, pos.x()), size.width())
                    clipped_y = min(max(0, pos.y()), size.height())
                    pos = QPointF(clipped_x, clipped_y)
                elif len(self.current) > 1 and self.close_enough(pos, self.current[0]):
                    # Attract line to starting point and colorise to alert the
                    # user:
                    pos = self.current[0]
                    color = self.current.line_color
                    self.override_cursor(CURSOR_POINT)
                    self.current.highlight_vertex(0, Shape.NEAR_VERTEX)
                self.line[1] = pos
                self.line.line_color = color
                self.prev_point = QPointF()
                self.current.highlight_clear()
            else:
                self.prev_point = pos
            self.repaint()
            return

        # Polygon/Vertex moving.
        if event.buttons() == Qt.MouseButton.LeftButton:
            if self.selected_vertex():
                self.bounded_move_vertex(pos)
                self.shapeMoved.emit()
                self.repaint()
                # Display annotation width and height while moving vertex
                point1 = self.h_shape[1]
                point3 = self.h_shape[3]
                current_width = abs(point1.x() - point3.x())
                current_height = abs(point1.y() - point3.y())
                self.parent().window().label_coordinates.setText(
                    f'Width: {current_width}, Height: {current_height} / X: {pos.x()}; Y: {pos.y()}')
            elif self.selected_shape and self.prev_point:
                self.override_cursor(CURSOR_MOVE)
                self.bounded_move_shape(self.selected_shape, pos)
                self.shapeMoved.emit()
                self.repaint()
                # Display annotation width and height while moving shape
                point1 = self.selected_shape[1]
                point3 = self.selected_shape[3]
                current_width = abs(point1.x() - point3.x())
                current_height = abs(point1.y() - point3.y())
                self.parent().window().label_coordinates.setText(
                    f'Width: {current_width}, Height: {current_height} / X: {pos.x()}; Y: {pos.y()}')
            else:
                # pan
                delta_x = pos.x() - self.pan_initial_pos.x()
                delta_y = pos.y() - self.pan_initial_pos.y()
                self.scrollRequest.emit(delta_x, Qt.Orientation.Horizontal)
                self.scrollRequest.emit(delta_y, Qt.Orientation.Vertical)
                self.update()
            self.p.update_bbox_list_by_canvas()
            return

        # Just hovering over the canvas, 2 possibilities:
        # - Highlight shapes
        # - Highlight vertex
        # Update shape/vertex fill and tooltip value accordingly.
        self.setToolTip("Image")
        if self.shape is not None:
            # Look for a nearby vertex to highlight. If that fails,
            # check if we happen to be inside a shape.
            index = self.shape.nearest_vertex(pos, self.epsilon)
            if index is not None:
                if self.selected_vertex():
                    self.h_shape.highlight_clear()
                self.h_vertex, self.h_shape = index, self.shape
                self.shape.highlight_vertex(index, self.shape.MOVE_VERTEX)
                self.override_cursor(CURSOR_POINT)
                self.setToolTip("Click & drag to move point")
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
                self.parent().window().label_coordinates.setText(
                    f'Width: {current_width}, Height: {current_height} / X: {pos.x()}; Y: {pos.y()}')
        else:  # Nothing found, clear highlights, reset state.
            if self.h_shape:
                self.h_shape.highlight_clear()
                self.update()
            self.h_vertex, self.h_shape = None, None
            self.override_cursor(CURSOR_DEFAULT)

    def mousePressEvent(self, event: QMouseEvent) -> None:
        pos = self.transform_pos(event.pos())
        if event.button() == Qt.MouseButton.LeftButton:
            if self.drawing():
                self.handle_drawing(pos)
            else:
                selection = self.select_shape_point(pos)
                self.prev_point = pos
                if selection is None:
                    QApplication.setOverrideCursor(QCursor(Qt.CursorShape.OpenHandCursor))
                    self.pan_initial_pos = pos
        self.update()

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        if   event.button() == Qt.MouseButton.LeftButton and self.selected_shape:
            if self.selected_vertex():
                self.override_cursor(CURSOR_POINT)
            else:
                self.override_cursor(CURSOR_GRAB)
        elif event.button() == Qt.MouseButton.LeftButton:
            pos = self.transform_pos(event.pos())
            if self.drawing():
                self.handle_drawing(pos)
            else:
                # pan
                QApplication.restoreOverrideCursor()

    def paintEvent(self, event: QPaintEvent) -> None:
        if not self.pixmap:
            return super(Canvas, self).paintEvent(event)

        p = self._painter
        p.begin(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)

        p.scale(self.scale, self.scale)
        p.translate(self.offset_to_center())

        p.drawPixmap(0, 0, self.pixmap)
        Shape.scale = self.scale
        if self.shape is not None:
            self.shape.paint(p)
        if self.current:
            self.current.paint(p)
            self.line.paint(p)

        # Paint rect
        if self.current is not None and len(self.line) == 2:
            left_top = self.line[0]
            right_bottom = self.line[1]
            rect_width = right_bottom.x() - left_top.x()
            rect_height = right_bottom.y() - left_top.y()
            p.setPen(self.drawing_rect_color)
            brush = QBrush(Qt.BrushStyle.BDiagPattern)
            p.setBrush(brush)
            p.drawRect(int(left_top.x()), int(left_top.y()), int(rect_width), int(rect_height))

        if self.drawing() and not self.prev_point.isNull() and not self.out_of_pixmap(self.prev_point):
            p.setPen(QColor(0, 0, 0))
            p.drawLine(int(self.prev_point.x()), 0, int(self.prev_point.x()), int(self.pixmap.height()))
            p.drawLine(0, int(self.prev_point.y()), int(self.pixmap.width()), int(self.prev_point.y()))

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
            self.zoomRequest.emit(v_delta)
        else:
            v_delta and self.scrollRequest.emit(v_delta, Qt.Orientation.Vertical)
            h_delta and self.scrollRequest.emit(h_delta, Qt.Orientation.Horizontal)
        event.accept()

    def sizeHint(self):
        return self.minimumSizeHint()

    def minimumSizeHint(self):
        if self.pixmap:
            return self.scale * self.pixmap.size()
        return super(Canvas, self).minimumSizeHint()

    def set_drawing_color(self, qcolor):
        self.drawing_line_color = qcolor
        self.drawing_rect_color = qcolor

    def drawing(self):
        return self.mode == self.CREATE

    def editing(self):
        return self.mode == self.EDIT

    def set_editing(self, value=True):
        self.mode = self.EDIT if value else self.CREATE
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

    def handle_drawing(self, pos):
        if self.current and self.current.reach_max_points() is False:
            init_pos = self.current[0]
            min_x = init_pos.x()
            min_y = init_pos.y()
            target_pos = self.line[1]
            max_x = target_pos.x()
            max_y = target_pos.y()
            self.current.add_point(QPointF(max_x, min_y))
            self.current.add_point(target_pos)
            self.current.add_point(QPointF(min_x, max_y))
            self.finalise()
        elif not self.out_of_pixmap(pos):
            self.current = Shape()
            self.current.add_point(pos)
            self.line.points = [pos, pos]
            self.drawingPolygon.emit(True)
            self.update()

    def can_close_shape(self):
        return self.drawing() and self.current and len(self.current) > 2

    def select_shape(self, shape):
        self.de_select_shape()
        shape.selected = True
        self.selected_shape = shape
        # self.selectionChanged.emit(True)
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
        if self.out_of_pixmap(pos):
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
        if self.out_of_pixmap(pos):
            return False  # No need to move
        o1 = pos + self.offsets[0]
        if self.out_of_pixmap(o1):
            pos -= QPointF(min(0, o1.x()), min(0, o1.y()))
        o2 = pos + self.offsets[1]
        if self.out_of_pixmap(o2):
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
            self.selectionChanged.emit(False)
            self.update()

    def transform_pos(self, point):
        """Convert from widget-logical coordinates to painter-logical coordinates."""
        pointf = QPointF(point.x(), point.y())
        return pointf / self.scale - self.offset_to_center()

    def offset_to_center(self):
        s = self.scale
        area = super(Canvas, self).size()
        w, h = self.pixmap.width() * s, self.pixmap.height() * s
        aw, ah = area.width(), area.height()
        x = (aw - w) / (2 * s) if aw > w else 0
        y = (ah - h) / (2 * s) if ah > h else 0
        return QPointF(x, y)

    def out_of_pixmap(self, p):
        w, h = self.pixmap.width(), self.pixmap.height()
        return not (0 <= p.x() <= w and 0 <= p.y() <= h)

    def finalise(self):
        assert self.current
        if self.current.points[0] == self.current.points[-1]:
            self.current = None
            self.drawingPolygon.emit(False)
            self.update()
            return
        self.current.close()
        self.shape = self.current
        self.current = None
        self.newShape.emit()
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
        self.shapeMoved.emit()
        self.repaint()

    def move_out_of_bound(self, step):
        points = [p1 + p2 for p1, p2 in zip(self.selected_shape.points, [step] * 4)]
        return True in map(self.out_of_pixmap, points)

    def load_pixmap(self, pixmap):
        self.pixmap = pixmap
        self.repaint()

    def load_shape(self, shape):
        self.shape = shape
        self.current = None
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

from functools import partial
import os.path as osp
from PyQt6.QtCore import *
from PyQt6.QtGui import *
from PyQt6.QtWidgets import *
from PyQt6.QtWidgets import QMessageBox as QMB
from labelTrack.__init__ import __appname__, __version__
from labelTrack.settings import settings
from labelTrack.defines import *
from labelTrack.utils import *
from labelTrack.shape import Shape, DEFAULT_LINE_COLOR, DEFAULT_FILL_COLOR
from labelTrack.canvas import Canvas


class MainWindow(QMainWindow):
    FIT_WINDOW, FIT_WIDTH, MANUAL_ZOOM = list(range(3))

    def __init__(self, image_dir, label_path):
        super(MainWindow, self).__init__()
        self.setWindowTitle(__appname__)

        self.image_dir = image_dir
        self.label_path = label_path
        self.bbox_list = []
        self.dirty = False

        self.label_list = QListWidget()
        label_list_container = QWidget()
        list_layout = QVBoxLayout()
        list_layout.setContentsMargins(0, 0, 0, 0)
        label_list_container.setLayout(list_layout)
        list_layout.addWidget(self.label_list)

        self.dock = QDockWidget('Object List', self)
        self.dock.setObjectName('objects')
        self.dock.setWidget(label_list_container)

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
        self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, self.dock)
        self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, self.file_dock)
        self.file_dock.setFeatures(QDockWidget.DockWidgetFeature.DockWidgetFloatable)

        self.dock.setFeatures(
            QDockWidget.DockWidgetFeature.DockWidgetClosable |
            QDockWidget.DockWidgetFeature.DockWidgetFloatable)

        self.action_quit = new_action(
            self, 'Quit', self.close)
        self.action_quit.setIcon(read_icon('quit'))
        self.action_quit.setShortcut('Ctrl+Q')
        self.action_open_image_dir = new_action(
            self, 'Open Image Dir', self.open_image_dir_dialog)
        self.action_open_image_dir.setIcon(read_icon('open'))
        self.action_open_label_file = new_action(
            self, 'Open Label File', self.open_label_file_dialog)
        self.action_open_label_file.setIcon(read_icon('open'))
        self.action_next_image = new_action(
            self, 'Next Image', self.open_next_image)
        self.action_next_image.setIcon(read_icon('next'))
        self.action_next_image.setShortcut('d')
        self.action_prev_image = new_action(
            self, 'Previous Image', self.open_prev_image)
        self.action_prev_image.setIcon(read_icon('prev'))
        self.action_prev_image.setShortcut('a')
        self.action_save = new_action(
            self, 'Save', self.save_file)
        self.action_save.setIcon(read_icon('save'))
        self.action_save.setShortcut('Ctrl+s')
        self.action_create_object = new_action(
            self, 'Create Object', self.create_object)
        self.action_create_object.setIcon(read_icon('objects'))
        self.action_create_object.setShortcut('w')
        self.action_delete_object = new_action(
            self, 'Delete Object', self.delete_object)
        self.action_delete_object.setIcon(read_icon('close'))
        self.action_delete_object.setShortcut('c')
        self.action_copy_object = new_action(
            self, 'Copy Object', self.copy_object)
        self.action_copy_object.setIcon(read_icon('copy'))
        self.action_copy_object.setShortcut('r')
        self.action_next_image_and_copy = new_action(
            self, 'Next Image and Copy', self.next_image_and_copy)
        self.action_next_image_and_copy.setIcon(read_icon('next'))
        self.action_next_image_and_copy.setShortcut('t')
        self.action_next_image_and_delete = new_action(
            self, 'Next Image and Delete', self.next_image_and_delete)
        self.action_next_image_and_delete.setIcon(read_icon('next'))
        self.action_next_image_and_delete.setShortcut('v')
        self.action_show_info = new_action(
            self, 'info', self.show_info_dialog)
        self.action_show_info.setIcon(read_icon('help'))
        self.zoom_widget = ZoomWidget()
        self.zoom_widget.setEnabled(True)
        self.zoom_widget.valueChanged.connect(self.paint_canvas)
        self.action_zoom = QWidgetAction(self)
        self.action_zoom.setDefaultWidget(self.zoom_widget)
        self.action_zoom_in = new_action(
            self, 'Zoom In', partial(self.add_zoom, 10))
        self.action_zoom_in.setIcon(read_icon('zoom-in'))
        self.action_zoom_in.setShortcut('Ctrl++')
        self.action_zoom_out = new_action(
            self, 'Zoom Out', partial(self.add_zoom, -10))
        self.action_zoom_out.setIcon(read_icon('zoom-out'))
        self.action_zoom_out.setShortcut('Ctrl+-')
        self.action_zoom_org = new_action(
            self, 'Original Size', partial(self.set_zoom, 100))
        self.action_zoom_org.setIcon(read_icon('zoom'))
        self.action_zoom_org.setShortcut('Ctrl+=')
        self.action_fit_window = new_action(
            self, 'Fit Window', self.set_fit_window)
        self.action_fit_window.setIcon(read_icon('fit-window'))
        self.action_fit_window.setShortcut('Ctrl+F')
        self.action_fit_window.setCheckable(True)
        self.action_fit_width = new_action(
            self, 'Fit Width', self.set_fit_width)
        self.action_fit_width.setIcon(read_icon('fit-width'))
        self.action_fit_width.setShortcut('Ctrl+Shift+F')
        self.action_fit_width.setCheckable(True)
        self.zoom_actions = (
            self.zoom_widget,
            self.action_zoom_in,
            self.action_zoom_out,
            self.action_zoom_org,
            self.action_fit_window,
            self.action_fit_width)
        self.zoom_mode = self.MANUAL_ZOOM
        self.scalers = {
            self.FIT_WINDOW: self.scale_fit_window,
            self.FIT_WIDTH: self.scale_fit_width,
            self.MANUAL_ZOOM: lambda: 1}
        self.menus_file = self.menuBar().addMenu('File')
        self.menus_edit = self.menuBar().addMenu('Edit')
        self.menus_view = self.menuBar().addMenu('View')
        self.menus_help = self.menuBar().addMenu('Help')
        self.auto_saving = QAction('autoSaveMode', self)
        self.auto_saving.setCheckable(True)
        self.auto_saving.setChecked(settings.get(SETTINGS_KEY_AUTO_SAVE, True))
        add_actions(
            self.menus_file,
            (self.action_open_image_dir,
             self.action_open_label_file,
             self.action_save,
             self.action_next_image,
             self.action_prev_image,
             self.action_quit))
        add_actions(
            self.menus_edit,
            (self.action_create_object,
             self.action_delete_object,
             self.action_copy_object,
             self.action_next_image_and_copy,
             self.action_next_image_and_delete,))
        add_actions(
            self.menus_view,
            (self.auto_saving,
             None,
             self.action_zoom_in,
             self.action_zoom_out,
             self.action_zoom_org,
             None,
             self.action_fit_window,
             self.action_fit_width))
        add_actions(
            self.menus_help,
            (self.action_show_info,))
        self.toolbar = ToolBar('Tools')
        self.toolbar.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextUnderIcon)
        self.addToolBar(Qt.ToolBarArea.LeftToolBarArea, self.toolbar)
        add_actions(
            self.toolbar,
            (self.action_open_image_dir,
             self.action_open_label_file,
             self.action_next_image,
             self.action_prev_image,
             self.action_save,
             None,
             self.action_create_object,
             self.action_delete_object,
             None,
             self.action_zoom_in,
             self.action_zoom,
             self.action_zoom_out,
             self.action_fit_window,
             self.action_fit_width))
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
        settings.set(SETTINGS_KEY_AUTO_SAVE, self.auto_saving.isChecked())
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
        self.add_object_to_label_list()
        self.update_bbox_list_by_canvas()
        self.canvas.set_editing(True)
        self.action_create_object.setEnabled(True)
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
        if self.auto_saving.isChecked():
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
        if self.auto_saving.isChecked():
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
        self.action_create_object.setEnabled(False)

    def delete_object(self):
        self.canvas.shape = None
        self.remove_object_from_label_list()
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
        msg = f'Name:{__appname__} \nApp Version:{__version__} \n{sys.version_info}'
        QMB.information(self, 'Information', msg)

    def scroll_request(self, delta, orientation):
        units = - delta / (8 * 15)
        bar = self.scroll_bars[orientation]
        bar.setValue(int(bar.value() + bar.singleStep() * units))

    def set_zoom(self, value):
        self.action_fit_width.setChecked(False)
        self.action_fit_window.setChecked(False)
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
            self.action_fit_window.setChecked(False)
            return
        self.action_fit_width.setChecked(False)
        self.zoom_mode = self.FIT_WINDOW
        self.adjust_scale()

    def set_fit_width(self, value=True):
        if self.image.isNull():
            self.action_fit_width.setChecked(False)
            return
        self.action_fit_window.setChecked(False)
        self.zoom_mode = self.FIT_WIDTH
        self.adjust_scale()

    def paint_canvas(self):
        if self.image.isNull():
            return
        self.canvas.scale = 0.01 * self.zoom_widget.value()
        self.canvas.label_font_size = int(0.02 * max(self.image.width(), self.image.height()))
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
        if self.label_list.count():
            self.label_list.setCurrentItem(self.label_list.item(self.label_list.count() - 1))
            self.label_list.item(self.label_list.count() - 1).setSelected(True)
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
            shape = Shape(label='object')
            shape.add_point(QPointF(xmin, ymin))
            shape.add_point(QPointF(xmax, ymin))
            shape.add_point(QPointF(xmax, ymax))
            shape.add_point(QPointF(xmin, ymax))
            shape.close()
            shape.line_color = QColor(227, 79, 208, 100)
            shape.fill_color = QColor(227, 79, 208, 100)
            self.canvas.load_shape(shape)
            self.add_object_to_label_list()
        else:
            self.canvas.load_shape(None)
            self.remove_object_from_label_list()

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

    def add_object_to_label_list(self):
        item = QListWidgetItem('object')
        item.setBackground(QColor(227, 79, 208, 100))
        self.remove_object_from_label_list()
        self.label_list.addItem(item)

    def remove_object_from_label_list(self):
        self.label_list.clear()

    def set_dirty(self):
        self.dirty = True
        self.action_save.setEnabled(True)

    def set_clean(self):
        self.dirty = False
        self.action_save.setEnabled(False)


class ToolBar(QToolBar):

    def __init__(self, title):
        super(ToolBar, self).__init__(title)
        layout = self.layout()
        m = (0, 0, 0, 0)
        layout.setSpacing(0)
        layout.setContentsMargins(*m)
        self.setContentsMargins(*m)
        self.setWindowFlags(self.windowFlags() | Qt.WindowType.FramelessWindowHint)

    def addAction(self, action):
        if isinstance(action, QWidgetAction):
            return super(ToolBar, self).addAction(action)
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

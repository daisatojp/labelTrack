import os
import os.path as osp
import argparse
from functools import partial
from PyQt5.QtCore import *
from PyQt5.QtGui import *
from PyQt5.QtWidgets import *
from PyQt5.QtWidgets import QMessageBox as QMB
from libs.constants import *
from libs.utils import *
from libs.settings import Settings
from libs.shape import Shape, DEFAULT_LINE_COLOR, DEFAULT_FILL_COLOR
from libs.canvas import Canvas
from libs.zoomwidget import ZoomWidget
from libs.toolbar import ToolBar


__appname__ = 'labelTrack'


class WindowMixin(object):

    def menu(self, title, actions=None):
        menu = self.menuBar().addMenu(title)
        if actions:
            add_actions(menu, actions)
        return menu

    def toolbar(self, title, actions=None):
        toolbar = ToolBar(title)
        toolbar.setObjectName(f'{title}ToolBar')
        toolbar.setToolButtonStyle(Qt.ToolButtonTextUnderIcon)
        if actions:
            add_actions(toolbar, actions)
        self.addToolBar(Qt.LeftToolBarArea, toolbar)
        return toolbar


class MainWindow(QMainWindow, WindowMixin):
    FIT_WINDOW, FIT_WIDTH, MANUAL_ZOOM = list(range(3))

    def __init__(self, image_dir, label_path):
        super(MainWindow, self).__init__()
        self.setWindowTitle(__appname__)

        self.settings = Settings()
        self.settings.load()

        self.image_dir = image_dir
        self.label_path = label_path
        self.bbox_list = None
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
            Qt.Vertical: scroll.verticalScrollBar(),
            Qt.Horizontal: scroll.horizontalScrollBar()}
        self.scroll_area = scroll
        self.canvas.scrollRequest.connect(self.scroll_request)

        self.canvas.newShape.connect(self.new_shape)
        self.canvas.shapeMoved.connect(self.set_dirty)
        self.canvas.drawingPolygon.connect(self.toggle_drawing_sensitive)

        self.setCentralWidget(scroll)
        self.addDockWidget(Qt.RightDockWidgetArea, self.dock)
        self.addDockWidget(Qt.RightDockWidgetArea, self.file_dock)
        self.file_dock.setFeatures(QDockWidget.DockWidgetFloatable)

        self.dock_features = QDockWidget.DockWidgetClosable | QDockWidget.DockWidgetFloatable
        self.dock.setFeatures(self.dock.features() ^ self.dock_features)

        self.action_quit = new_action(
            self, 'Quit', self.close,
            'Ctrl+Q', icon='quit', tip=None)
        self.action_open_image_dir = new_action(
            self, 'Open Image Dir', self.open_image_dir_dialog,
            shortcut=None, icon='open', tip=None)
        self.action_open_label_file = new_action(
            self, 'Open Label File', self.open_label_file_dialog,
            shortcut=None, icon='open', tip=None)
        self.action_next_image = new_action(
            self, 'Next Image', self.open_next_image,
            shortcut='d', icon='next', tip=None)
        self.action_prev_image = new_action(
            self, 'Previous Image', self.open_prev_image,
            shortcut='a', icon='prev', tip=None)
        self.action_save = new_action(
            self, 'Save', self.save_file,
            shortcut='Ctrl+s', icon='save', tip=None)
        self.action_create_object = new_action(
            self, 'Create Object', self.create_object,
            shortcut='w', icon='objects', tip=None)
        self.action_delete_object = new_action(
            self, 'Delete Object', self.delete_object,
            shortcut='c', icon='close', tip=None)
        self.action_copy_object = new_action(
            self, 'Copy Object', self.copy_object,
            shortcut='r', icon='copy', tip=None)
        self.action_next_image_and_copy = new_action(
            self, 'Next Image and Copy', self.next_image_and_copy,
            shortcut='t', icon='next', tip=None)
        self.action_next_image_and_delete = new_action(
            self, 'Next Image and Delete', self.next_image_and_delete,
            shortcut='v', icon='next', tip=None)
        self.action_show_info = new_action(
            self, 'info', self.show_info_dialog,
            shortcut=None, icon='help', tip=None)
        self.zoom_widget = ZoomWidget()
        self.zoom_widget.setEnabled(True)
        self.zoom_widget.valueChanged.connect(self.paint_canvas)
        self.action_zoom = QWidgetAction(self)
        self.action_zoom.setDefaultWidget(self.zoom_widget)
        self.action_zoom_in = new_action(
            self, 'Zoom In', partial(self.add_zoom, 10),
            shortcut='Ctrl++', icon='zoom-in', tip=None)
        self.action_zoom_out = new_action(
            self, 'Zoom Out', partial(self.add_zoom, -10),
            shortcut='Ctrl+-', icon='zoom-out', tip=None)
        self.action_zoom_org = new_action(
            self, 'Original Size', partial(self.set_zoom, 100),
            shortcut='Ctrl+=', icon='zoom', tip=None)
        self.action_fit_window = new_action(
            self, 'Fit Window', self.set_fit_window,
            shortcut='Ctrl+F', icon='fit-window', tip=None,
            checkable=True)
        self.action_fit_width = new_action(
            self, 'Fit Width', self.set_fit_width,
            shortcut='Ctrl+Shift+F', icon='fit-width', tip=None,
            checkable=True)
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
        self.menus = Struct(
            file=self.menu('File'),
            edit=self.menu('Edit'),
            view=self.menu('View'),
            help=self.menu('Help'))
        self.auto_saving = QAction('autoSaveMode', self)
        self.auto_saving.setCheckable(True)
        self.auto_saving.setChecked(self.settings.get(SETTING_AUTO_SAVE, True))
        add_actions(
            self.menus.file,
            (self.action_open_image_dir,
             self.action_open_label_file,
             self.action_save,
             self.action_next_image,
             self.action_prev_image,
             self.action_quit))
        add_actions(
            self.menus.edit,
            (self.action_create_object,
             self.action_delete_object,
             self.action_copy_object,
             self.action_next_image_and_copy,
             self.action_next_image_and_delete,))
        add_actions(
            self.menus.view,
            (self.auto_saving,
             None,
             self.action_zoom_in,
             self.action_zoom_out,
             self.action_zoom_org,
             None,
             self.action_fit_window,
             self.action_fit_width))
        add_actions(
            self.menus.help,
            (self.action_show_info,))
        self.tools = self.toolbar('Tools')
        add_actions(
            self.tools,
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

        size = self.settings.get(SETTING_WINDOW_SIZE, QSize(600, 500))
        position = QPoint(0, 0)
        saved_position = self.settings.get(SETTING_WINDOW_POSE, position)
        # Fix the multiple monitors issue
        for i in range(QApplication.desktop().screenCount()):
            if QApplication.desktop().availableGeometry(i).contains(saved_position):
                position = saved_position
                break
        self.resize(size)
        self.move(position)
        self.restoreState(self.settings.get(SETTING_WINDOW_STATE, QByteArray()))

        self.load_label()
        self.load_image_dir()

        self.label_coordinates = QLabel('')
        self.statusBar().addPermanentWidget(self.label_coordinates)

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
            item.setCheckState(Qt.Checked if value else Qt.Unchecked)

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

    def resizeEvent(self, event):
        if self.canvas and not self.image.isNull()\
           and self.zoom_mode != self.MANUAL_ZOOM:
            self.adjust_scale()
        super(MainWindow, self).resizeEvent(event)

    def closeEvent(self, event):
        if not self.may_continue():
            event.ignore()
        self.settings[SETTING_IMAGE_DIR] = self.image_dir if self.image_dir is not None else '.'
        self.settings[SETTING_LABEL_PATH] = self.label_path if self.label_path is not None else '.'
        self.settings[SETTING_WINDOW_SIZE] = self.size()
        self.settings[SETTING_WINDOW_POSE] = self.pos()
        self.settings[SETTING_WINDOW_STATE] = self.saveState()
        self.settings[SETTING_AUTO_SAVE] = self.auto_saving.isChecked()
        self.settings.save()

    def open_image_dir_dialog(self, _value=False):
        if not self.may_continue():
            return
        default_image_dir = '.'
        if self.image_dir and osp.exists(self.image_dir):
            default_image_dir = self.image_dir
        target_image_dir = QFileDialog.getExistingDirectory(
            self, f'{__appname__} - Open Image Directory', default_image_dir,
            QFileDialog.ShowDirsOnly | QFileDialog.DontResolveSymlinks)
        self.image_dir = target_image_dir
        self.load_image_dir()

    def open_label_file_dialog(self, _value=False):
        default_label_path = '.'
        if self.label_path is not None:
            default_label_path = self.label_path
        target_file_path = QFileDialog.getSaveFileName(
            self, f'{__appname__} - Save label to the file',
            osp.dirname(default_label_path), 'Text (*.txt)',
            None, QFileDialog.DontConfirmOverwrite)
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
        from libs.__init__ import __version__
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
        h_bar = self.scroll_bars[Qt.Horizontal]
        v_bar = self.scroll_bars[Qt.Vertical]
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
        self.canvas.setFocus(True)

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


def main():
    app = QApplication(sys.argv)
    app.setApplicationName(__appname__)
    app.setWindowIcon(new_icon('app'))
    parser = argparse.ArgumentParser()
    parser.add_argument('--image_dir', type=str, default=None)
    parser.add_argument('--label_path', type=str, default=None)
    args = parser.parse_args()
    win = MainWindow(args.image_dir, args.label_path)
    win.show()
    return app.exec_()


if __name__ == '__main__':
    sys.exit(main())

from PyQt6.QtGui import *
from PyQt6.QtCore import *
from PyQt6.QtWidgets import *
from labelTrack.shape import Shape
from labelTrack.utils import distance


CURSOR_DEFAULT = Qt.CursorShape.ArrowCursor
CURSOR_POINT = Qt.CursorShape.PointingHandCursor
CURSOR_DRAW = Qt.CursorShape.CrossCursor
CURSOR_MOVE = Qt.CursorShape.ClosedHandCursor
CURSOR_GRAB = Qt.CursorShape.OpenHandCursor


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
        self.selected_shape = None  # save the selected shape here
        self.selected_shape_copy = None
        self.drawing_line_color = QColor(0, 0, 255)
        self.drawing_rect_color = QColor(0, 0, 255)
        self.line = Shape(line_color=self.drawing_line_color)
        self.prev_point = QPointF()
        self.offsets = QPointF(), QPointF()
        self.scale = 1.0
        self.label_font_size = 8
        self.pixmap = QPixmap()
        self.visible = {}
        self._hide_background = False
        self.hide_background = False
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
                self.setToolTip(
                    "Click & drag to move shape '%s'" % self.shape.label)
                self.setStatusTip(self.toolTip())
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
        Shape.label_font_size = self.label_font_size
        if self.shape is not None:
            self.shape.paint(p)
        if self.current:
            self.current.paint(p)
            self.line.paint(p)
        if self.selected_shape_copy:
            self.selected_shape_copy.paint(p)

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
        qt_version = 4 if hasattr(event, "delta") else 5
        if qt_version == 4:
            if event.orientation() == Qt.Orientation.Vertical:
                v_delta = event.delta()
                h_delta = 0
            else:
                h_delta = event.delta()
                v_delta = 0
        else:
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

    def isVisible(self, shape):
        return self.visible.get(shape, True)

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
            self.set_hiding()
            self.drawingPolygon.emit(True)
            self.update()

    def set_hiding(self, enable=True):
        self._hide_background = self.hide_background if enable else False

    def can_close_shape(self):
        return self.drawing() and self.current and len(self.current) > 2

    def select_shape(self, shape):
        self.de_select_shape()
        shape.selected = True
        self.selected_shape = shape
        self.set_hiding()
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
            if self.isVisible(self.shape) and self.shape.contains_point(point):
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
            self.set_hiding(False)
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
        self.set_hiding(False)
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

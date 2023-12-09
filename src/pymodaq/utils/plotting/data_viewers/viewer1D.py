import sys
import datetime
from collections import OrderedDict
from typing import List, Iterable, Union, Dict

from qtpy import QtWidgets
from qtpy.QtCore import QObject, Slot, Signal, Qt, QRectF
import pyqtgraph as pg
import numpy as np

from pymodaq.utils.data import DataRaw, DataFromRoi, Axis, DataToExport, DataCalculated, DataWithAxes
from pymodaq.utils.logger import set_logger, get_module_name
from pymodaq.utils.parameter import utils as putils
from pymodaq.utils.plotting.items.crosshair import Crosshair
from pymodaq.utils import daq_utils as utils
import pymodaq.utils.math_utils as mutils
from pymodaq.utils.managers.action_manager import ActionManager
from pymodaq.utils.plotting.data_viewers.viewer import ViewerBase
from pymodaq.utils.plotting.utils.plot_utils import make_dashed_pens
from pymodaq.utils.managers.roi_manager import ROIManager
from pymodaq.utils.plotting.utils.filter import Filter1DFromCrosshair, Filter1DFromRois
from pymodaq.utils.plotting.widgets import PlotWidget
from pymodaq.utils.plotting.data_viewers.viewer0D import Viewer0D

logger = set_logger(get_module_name(__file__))

PLOT_COLORS = utils.plot_colors


class DataDisplayer(QObject):
    """
    This Object deals with the display of 1D data  on a plotitem
    """

    updated_item = Signal(list)
    labels_changed = Signal(list)

    def __init__(self, plotitem: pg.PlotItem, flip_axes=False, plot_colors=PLOT_COLORS):
        super().__init__()
        self._flip_axes = flip_axes
        self._plotitem = plotitem
        self._plotitem.addLegend()
        self._plot_items: List[pg.PlotDataItem] = []
        self._overlay_items: List[pg.PlotDataItem] = []
        self._axis: Axis = None
        self._data: DataRaw = None
        self._plot_colors = plot_colors

    def update_colors(self, colors: list):
        self._plot_colors[0:len(colors)] = colors
        self.update_data(self._data, force_update=True)

        self._doxy = False
        self._do_sort = False

    @property
    def legend(self):
        return self._plotitem.legend

    def update_axis(self, axis: Axis):
        self._axis = axis.copy()
        if self._axis.get_data() is None:  # create real data vector once here for subsequent use
            self._axis.create_linear_data(axis.size)

    def get_axis(self) -> Axis:
        return self._axis

    def get_plot_items(self):
        return self._plot_items

    def get_plot_item(self, index: int):
        return self._plot_items[index]

    def update_data(self, data: DataRaw, do_xy=False, sort_data=False, force_update=False):
        if data is not None:
            if data.labels != self.labels:
                force_update = True
        self._data = data
        if len(data) != len(self._plot_items) or force_update:
            self.update_display_items(data)
        self.update_plot(do_xy, data, sort_data)

    def update_xy(self, do_xy=False):
        self._doxy = do_xy
        self.update_plot(do_xy, sort_data=self._do_sort)

    def update_sort(self, do_sort=False):
        self._do_sort = do_sort
        self.update_plot(self._doxy, sort_data=self._do_sort)

    def update_plot(self, do_xy=True, data=None, sort_data=False):
        if data is None:
            data = self._data
        if sort_data:
            data = data.sort_data()
            if len(data.axes) == 0:
                data.create_missing_axes()
        self._doxy = do_xy
        self._do_sort = sort_data

        self.update_xyplot(do_xy, data)

    def update_xyplot(self, do_xy=True, dwa: DataWithAxes=None):
        if dwa is None:
            dwa = self._data
        _axis = dwa.get_axis_from_index(0)[0]
        _axis_array = _axis.get_data()
        for ind_data, dat in enumerate(dwa.data):
            if dwa.size > 0:
                if not do_xy:
                    if self._flip_axes:
                        self._plot_items[ind_data].setData(dat, _axis_array)
                    else:
                        self._plot_items[ind_data].setData(_axis_array, dat)
                else:
                    self._plot_items[ind_data].setData(np.array([]), np.array([]))

        if do_xy:
            for ind, data_array in enumerate(dwa[1:]):
                self._plot_items[ind].setData(dwa.data[0], data_array)
                axis = self._plotitem.getAxis('bottom')
                axis.setLabel(text=dwa.labels[0], units='')
                axis = self._plotitem.getAxis('left')
                axis.setLabel(text=' / '.join(dwa.labels[1:]), units='')
                self.legend.setVisible(False)

        else:
            axis = self._plotitem.getAxis('bottom')
            axis.setLabel(text=_axis.label, units=_axis.units)
            axis = self._plotitem.getAxis('left')
            axis.setLabel(text='', units='')
            self.legend.setVisible(True)

    def plot_with_scatter(self, with_scatter=True):
        symbol_size = 5
        for ind, plot_item in enumerate(self.get_plot_items()):
            if with_scatter:
                pen = None
                symbol = 'o'
                brush = self._plot_colors[ind]

            else:
                pen = self._plot_colors[ind]
                symbol = None
                brush = None

            plot_item.setPen(pen)
            plot_item.setSymbolBrush(brush)
            plot_item.setSymbol(symbol)
            plot_item.setSymbolSize(symbol_size)

    def update_display_items(self, data: DataWithAxes = None):
        while len(self._plot_items) > 0:
            self._plotitem.removeItem(self._plot_items.pop(0))
        if data is not None:
            for ind in range(len(data)):
                self._plot_items.append(pg.PlotDataItem(pen=self._plot_colors[ind]))
                self._plotitem.addItem(self._plot_items[-1])
                self.legend.addItem(self._plot_items[-1], data.labels[ind])
            self.updated_item.emit(self._plot_items)
            self.labels_changed.emit(data.labels)

    @property
    def labels(self):
        if self._data is None:
            return []
        else:
            return self._data.labels

    def legend_items(self):
        return [item[1].text for item in self.legend.items]

    def show_overlay(self, show=True):
        if not show:
            while len(self._overlay_items) > 0:
                self._plotitem.removeItem(self._overlay_items.pop(0))
        else:
            for ind in range(len(self._data)):
                pen = pg.mkPen(color=self._plot_colors[ind], style=Qt.CustomDashLine)
                pen.setDashPattern([10, 10])
                self._overlay_items.append(pg.PlotDataItem(pen=pen))
                self._plotitem.addItem(self._overlay_items[-1])
                if self._do_sort:
                    self._overlay_items[ind].setData(self._axis.get_data(),
                                                     self._data.sort_data()[ind])
                else:
                    self._overlay_items[ind].setData(self._axis.get_data(), self._data[ind])



class View1D(ActionManager, QObject):
    def __init__(self, parent_widget: QtWidgets.QWidget = None, show_toolbar=True,
                 no_margins=False, flip_axes=False):
        QObject.__init__(self)
        ActionManager.__init__(self, toolbar=QtWidgets.QToolBar())

        self.no_margins = no_margins
        self.flip_axes = flip_axes

        self.data_displayer: DataDisplayer = None
        self.plot_widget: PlotWidget = None
        self.lineout_widgets: QtWidgets.QWidget = None
        self.lineout_viewers: Viewer0D = None
        self.crosshair: Crosshair = None

        self.roi_target = pg.InfiniteLine(pen='w')
        self.ROIselect = pg.LinearRegionItem(pen='w')

        self.setup_actions()

        self.parent_widget = parent_widget
        if self.parent_widget is None:
            self.parent_widget = QtWidgets.QWidget()
            self.parent_widget.show()

        self.plot_widget = PlotWidget()
        self.roi_manager = ROIManager('1D')
        self.data_displayer = DataDisplayer(self.plotitem, flip_axes=self.flip_axes)
        self.other_data_displayers: Dict[str, DataDisplayer] = {}
        self.setup_widgets()

        self.connect_things()
        self.prepare_ui()

        self.plotitem.addItem(self.roi_target)
        self.plotitem.addItem(self.ROIselect)
        self.roi_target.setVisible(False)
        self.ROIselect.setVisible(False)

        if not show_toolbar:
            self.splitter_ver.setSizes([0, 1])

    def add_data_displayer(self, displayer_name: str, plot_colors=PLOT_COLORS):
        self.other_data_displayers[displayer_name] = DataDisplayer(self.plotitem, self.flip_axes, plot_colors)

    def remove_data_displayer(self, displayer_name: str):
        displayer = self.other_data_displayers.pop(displayer_name, None)
        if displayer is not None:
            displayer.update_display_items()

    @Slot(int, str, str)
    def add_roi_displayer(self, index, roi_type='', roi_name=''):
        color = self.roi_manager.ROIs[roi_name].color
        self.lineout_viewers.view.add_data_displayer(roi_name, make_dashed_pens(color))

    @Slot(str)
    def remove_roi_displayer(self, roi_name=''):
        self.lineout_viewers.view.remove_data_displayer(roi_name)

    def move_roi_target(self, pos: Iterable[float], **kwargs):
        if not self.roi_target.isVisible():
            self.roi_target.setVisible(True)
        self.roi_target.setPos(pos[0])

    def get_double_clicked(self):
        return self.plot_widget.view.sig_double_clicked

    def display_roi_lineouts(self, roi_dte: DataToExport):
        for roi_name in roi_dte.get_origins('Data0D'):
            self.lineout_viewers.view.display_data(
                roi_dte.get_data_from_name_origin('IntData', roi_name), displayer=roi_name)

    @property
    def axis(self):
        """Get the current axis used to display data"""
        return self.data_displayer.get_axis()

    @property
    def plotitem(self):
        return self.plot_widget.plotItem

    def get_crosshair_signal(self):
        """Convenience function from the Crosshair"""
        return self.crosshair.crosshair_dragged

    def get_crosshair_position(self):
        """Convenience function from the Crosshair"""
        return self.crosshair.get_positions()

    def set_crosshair_position(self, *positions):
        """Convenience function from the Crosshair"""
        self.crosshair.set_crosshair_position(*positions)

    def display_data(self, data: Union[DataWithAxes, DataToExport], displayer: str = None):
        if displayer is None:
            if isinstance(data, DataWithAxes):
                self.set_action_visible('xyplot', len(data) == 2)
                self.data_displayer.update_data(data, self.is_action_checked('xyplot'),
                                                self.is_action_checked('sort'))
            elif isinstance(data, DataToExport):
                self.set_action_visible('xyplot', len(data[0]) == 2)
                self.data_displayer.update_data(data.pop(0), self.is_action_checked('xyplot'),
                                                self.is_action_checked('sort'))
                if len(data) > 0:
                    self.data_displayer.add_other_data(data)
        elif displayer in self.other_data_displayers:
            self.other_data_displayers[displayer].update_data(data,
                                                              self.is_action_checked('xyplot'),
                                                              self.is_action_checked('sort'))

    def prepare_ui(self):
        self.show_hide_crosshair(False)

    def do_math(self):
        try:
            if self.is_action_checked('do_math'):
                self.roi_manager.roiwidget.show()
                self.lineout_widgets.show()
            else:
                self.lineout_widgets.hide()
                self.roi_manager.roiwidget.hide()

        except Exception as e:
            logger.exception(str(e))

    @Slot(int, str)
    def update_roi_channels(self, index, roi_type=''):
        """Update the use_channel setting each time a ROI is added"""
        self.roi_manager.update_use_channel(self.data_displayer.labels.copy())

    def setup_widgets(self):
        self.parent_widget.setLayout(QtWidgets.QVBoxLayout())
        if self.no_margins:
            self.parent_widget.layout().setContentsMargins(0, 0, 0, 0)
        splitter_hor = QtWidgets.QSplitter(Qt.Horizontal)
        self.parent_widget.layout().addWidget(splitter_hor)

        self.splitter_ver = QtWidgets.QSplitter(Qt.Vertical)
        splitter_hor.addWidget(self.splitter_ver)
        splitter_hor.addWidget(self.roi_manager.roiwidget)
        self.roi_manager.roiwidget.hide()

        self.splitter_ver.addWidget(self.toolbar)

        self.lineout_widgets = QtWidgets.QWidget()
        self.lineout_viewers = Viewer0D(self.lineout_widgets, show_toolbar=False,
                                        no_margins=True)
        self.lineout_widgets.setContentsMargins(0, 0, 0, 0)
        self.lineout_widgets.hide()

        self.splitter_ver.addWidget(self.plot_widget)
        self.splitter_ver.addWidget(self.lineout_widgets)
        self.roi_manager.viewer_widget = self.plot_widget

        self.crosshair = Crosshair(self.plotitem, orientation='vertical')
        self.show_hide_crosshair()

    def connect_things(self):
        self.connect_action('aspect_ratio', self.lock_aspect_ratio)

        self.connect_action('do_math', self.do_math)
        self.connect_action('scatter', self.data_displayer.plot_with_scatter)
        self.connect_action('xyplot', self.data_displayer.update_xy)
        self.connect_action('sort', self.data_displayer.update_sort)
        self.connect_action('crosshair', self.show_hide_crosshair)
        self.connect_action('overlay', self.data_displayer.show_overlay)
        self.connect_action('ROIselect', self.show_ROI_select)

        self.roi_manager.new_ROI_signal.connect(self.update_roi_channels)
        self.roi_manager.new_ROI_signal.connect(self.add_roi_displayer)
        self.roi_manager.new_ROI_signal.connect(self.lineout_viewers.get_action('clear').click)
        self.roi_manager.remove_ROI_signal.connect(self.remove_roi_displayer)

        self.roi_manager.color_signal.connect(self.update_colors)
        self.data_displayer.labels_changed.connect(self.roi_manager.update_use_channel)

    def update_colors(self, colors: list):
        for ind, roi_name in enumerate(self.roi_manager.ROIs):
            self.lineout_viewers.update_colors(make_dashed_pens(colors[ind]), displayer=roi_name)

    def show_ROI_select(self):
        self.ROIselect.setVisible(self.is_action_checked('ROIselect'))

    def setup_actions(self):
        self.add_action('do_math', 'Math', 'Calculator', 'Do Math using ROI', checkable=True)
        self.add_action('crosshair', 'Crosshair', 'reset', 'Show data cursor', checkable=True)
        self.add_action('aspect_ratio', 'AspectRatio', 'Zoom_1_1', 'Fix the aspect ratio', checkable=True)
        self.add_action('scatter', 'Scatter', 'Marker', 'Switch between line or scatter plots', checkable=True)
        self.add_action('xyplot', 'XYPlotting', '2d',
                        'Switch between normal or XY representation (valid for 2 channels)', checkable=True,
                        visible=False)
        self.add_action('overlay', 'Overlay', 'overlay', 'Plot overlays of current data', checkable=True)
        self.add_action('sort', 'Sort Data', 'sort_ascend', 'Display data in a sorted fashion with respect to axis',
                        checkable=True)
        self.add_action('ROIselect', 'ROI Select', 'Select_24',
                        tip='Show/Hide ROI selection area', checkable=True)
        self.add_action('x_label', 'x:')
        self.add_action('y_label', 'y:')

    def lock_aspect_ratio(self):
        if self.is_action_checked('aspect_ratio'):
            self.plotitem.vb.setAspectLocked(lock=True, ratio=1)
        else:
            self.plotitem.vb.setAspectLocked(lock=False)

    def update_crosshair_data(self, crosshair_dte: DataToExport):
        if len(crosshair_dte) > 0:
            dwa = crosshair_dte[0]
            string = "y="
            for data_array in dwa:
                string += f"{float(data_array[0]):.3e} / "
            self.get_action('y_label').setText(string)
            self.get_action('x_label').setText(f"x={float(dwa.axes[0].get_data()[0]):.3e} ")

    @Slot(bool)
    def show_hide_crosshair(self, show=True):
        self.crosshair.setVisible(show)
        self.set_action_visible('x_label', show)
        self.set_action_visible('y_label', show)
        if self.is_action_checked('crosshair'):
            range = self.plotitem.vb.viewRange()
            self.crosshair.set_crosshair_position(xpos=np.mean(np.array(range[0])))

    def add_plot_item(self, item):
        self.plotitem.addItem(item)


class Viewer1D(ViewerBase):
    """this plots 1D data on a plotwidget. Math and measurement can be done on it.

    Data and measurements are then exported with the signal data_to_export_signal
    """
    ROI_select_signal = Signal(QRectF)

    def __init__(self, parent: QtWidgets.QWidget = None, title='', show_toolbar=True, no_margins=False,
                 flip_axes=False):
        super().__init__(parent=parent, title=title)

        self.view = View1D(self.parent, show_toolbar=show_toolbar, no_margins=no_margins, flip_axes=flip_axes)

        self.filter_from_rois = Filter1DFromRois(self.view.roi_manager)
        self.filter_from_rois.register_activation_signal(self.view.get_action('do_math').triggered)
        self.filter_from_rois.register_target_slot(self.process_roi_lineouts)

        self.filter_from_crosshair = Filter1DFromCrosshair(self.view.crosshair)
        self.filter_from_crosshair.register_activation_signal(self.view.get_action('crosshair').triggered)
        self.filter_from_crosshair.register_target_slot(self.process_crosshair_lineouts)

        self.prepare_connect_ui()

        self._labels = []

    def update_colors(self, colors: List, displayer=None):
        if displayer is None:
            self.view.data_displayer.update_colors(colors)
        elif displayer in self.view.other_data_displayers:
            self.view.other_data_displayers[displayer].update_colors(colors)

    @property
    def roi_manager(self):
        """Convenience method """
        return self.view.roi_manager

    @property
    def roi_target(self) -> pg.InfiniteLine:
        return self.view.roi_target

    def move_roi_target(self, pos: Iterable[float] = None):
        """move a specific read only ROI at the given position on the viewer"""
        self.view.move_roi_target(pos)

    @property
    def crosshair(self):
        """Convenience method """
        return self.view.crosshair

    def set_crosshair_position(self, xpos, ypos=0):
        """Convenience method to set the crosshair positions"""
        self.view.crosshair.set_crosshair_position(xpos=xpos, ypos=ypos)

    def add_plot_item(self, item):
        self.view.add_plot_item(item)

    def process_crosshair_lineouts(self, crosshair_dte: DataToExport):
        self.view.update_crosshair_data(crosshair_dte)
        self.crosshair_dragged.emit(*self.view.crosshair.get_positions())

    def process_roi_lineouts(self, roi_dte: DataToExport):
        self.view.display_roi_lineouts(roi_dte)
        self.measure_data_dict = dict([])
        if not self._display_temporary:
            self.data_to_export.append(roi_dte.data)

        self.measure_data_dict = roi_dte.merge_as_dwa('Data0D').to_dict()

        QtWidgets.QApplication.processEvents()

        self.view.roi_manager.settings.child('measurements').setValue(self.measure_data_dict)
        if not self._display_temporary:
            self.data_to_export_signal.emit(self.data_to_export)
        self.ROI_changed.emit()

    def prepare_connect_ui(self):
        self.view.ROIselect.sigRegionChangeFinished.connect(self.selected_region_changed)
        self._data_to_show_signal.connect(self.view.display_data)
        self.roi_manager.roi_changed.connect(self.roi_changed)
        self.roi_manager.roi_value_changed.connect(self.roi_changed)

        self.view.get_crosshair_signal().connect(self.crosshair_changed)
        self.view.get_double_clicked().connect(self.double_clicked)

    def selected_region_changed(self):
        if self.view.is_action_checked('ROIselect'):
            pos = self.view.ROIselect.getRegion()
            self.ROI_select_signal.emit(QRectF(pos[0], pos[1], 0, 0))

    @Slot(float, float)
    def double_clicked(self, posx, posy=0):
        if self.view.is_action_checked('crosshair'):
            self.view.crosshair.set_crosshair_position(posx)
            self.crosshair_changed()
        self.sig_double_clicked.emit(posx, posy)

    def roi_changed(self):
        self.filter_from_rois.filter_data(self._raw_data)

    def crosshair_changed(self):
        self.filter_from_crosshair.filter_data(self._raw_data)

    def activate_roi(self, activate=True):
        self.view.set_action_checked('do_math', activate)
        self.view.get_action('do_math').triggered.emit(activate)

    @property
    def labels(self):
        return self._labels

    @labels.setter
    def labels(self, labels):
        if labels != self._labels:
            self._labels = labels

    def _show_data(self, data: DataWithAxes):
        self.labels = data.labels
        if len(data.axes) == 0:
            self.get_axis_from_view(data)

        if len(self.view.roi_manager.ROIs) == 0:
            self.data_to_export_signal.emit(self.data_to_export)
        else:
            self.roi_changed()
        if self.view.is_action_checked('crosshair'):
            self.crosshair_changed()

    def get_axis_from_view(self, data: DataWithAxes):
        if self.view.axis is not None:
            data.axes = [self.view.axis]

    def update_status(self, txt):
        logger.info(txt)


def main():
    app = QtWidgets.QApplication(sys.argv)
    Form = QtWidgets.QWidget()
    prog = Viewer1D(Form)

    from pymodaq.utils.math_utils import gauss1D

    x = np.linspace(0, 200, 201)
    y1 = gauss1D(x, 75, 25)
    y2 = gauss1D(x, 120, 50, 2)
    tau_half = 27
    tau2 = 100
    x0 = 50
    dx = 20
    ydata_expodec = np.zeros((len(x)))
    ydata_expodec[:50] = 1 * gauss1D(x[:50], x0, dx, 2)
    ydata_expodec[50:] = 1 * np.exp(-(x[50:] - x0) / (tau_half / np.log(2)))  # +1*np.exp(-(x[50:]-x0)/tau2)
    ydata_expodec += 0.1 * np.random.rand(len(x))

    # x = np.sin(np.linspace(0,6*np.pi,201))
    # y = np.sin(np.linspace(0, 6*np.pi, 201)+np.pi/2)
    data = DataRaw('mydata', data=[y1, ydata_expodec],
                   axes=[Axis('myaxis', 'units', data=x)])

    Form.show()
    prog.view.get_action('do_math').trigger()

    def print_data(data: DataToExport):
        print(data.data)
        print('******')
        print(data.get_data_from_dim('Data1D'))
        print('******')
        print(data.get_data_from_dim('Data0D'))
        print('***********************************')

    #prog.data_to_export_signal.connect(print_data)


    QtWidgets.QApplication.processEvents()
    prog.show_data(data)
    QtWidgets.QApplication.processEvents()
    sys.exit(app.exec_())


def main_unsorted():
    app = QtWidgets.QApplication(sys.argv)
    widget = QtWidgets.QWidget()
    prog = Viewer1D(widget)

    from pymodaq.utils.daq_utils import gauss1D

    x = np.linspace(0, 200, 201)
    xaxis = np.concatenate((x, x[::-1]))
    y = gauss1D(x, 75, 25)
    yaxis = np.concatenate((y, -y))
    data = DataRaw('mydata', data=[yaxis],
                   axes=[Axis('myaxis', 'units', data=xaxis)])
    widget.show()
    prog.show_data(data)

    sys.exit(app.exec_())

def main_random():
    app = QtWidgets.QApplication(sys.argv)
    widget = QtWidgets.QWidget()
    prog = Viewer1D(widget)

    from pymodaq.utils.math_utils import gauss1D
    x = np.random.randint(201, size=201)
    y1 = gauss1D(x, 75, 25)
    y2 = gauss1D(x, 120, 50, 2)

    QtWidgets.QApplication.processEvents()
    data = DataRaw('mydata', data=[y1, y2],
                   axes=[Axis('myaxis', 'units', data=x, index=0, spread_order=0)],
                   nav_indexes=(0, ))

    widget.show()
    prog.show_data(data)
    QtWidgets.QApplication.processEvents()
    sys.exit(app.exec_())


def main_view1D():
    app = QtWidgets.QApplication(sys.argv)
    widget = QtWidgets.QWidget()
    prog = View1D(widget)
    widget.show()
    sys.exit(app.exec_())


def main_nans():
    app = QtWidgets.QApplication(sys.argv)
    widget = QtWidgets.QWidget()
    prog = Viewer1D(widget)

    from pymodaq.utils.daq_utils import gauss1D

    x = np.linspace(0, 200, 201)
    y = gauss1D(x, 75, 25)

    y[100:150] = np.nan
    data = DataRaw('mydata', data=[y],
                   axes=[Axis('myaxis', 'units', data=x)])

    widget.show()
    prog.show_data(data)

    sys.exit(app.exec_())


if __name__ == '__main__':  # pragma: no cover
    # main()
    main_random()
    #main_view1D()
    #main_nans()

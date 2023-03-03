from typing import List, Union
from numbers import Real

from qtpy import QtWidgets, QtGui
from qtpy.QtCore import QObject, Slot, Signal, Qt
import sys
import pyqtgraph

import pymodaq.utils.daq_utils as utils
from pymodaq.utils import data as data_mod
from pymodaq.utils.logger import set_logger, get_module_name
from pymodaq.utils.plotting.data_viewers.viewer import ViewerBase
from pymodaq.utils.managers.action_manager import ActionManager
from pymodaq.utils.plotting.widgets import PlotWidget
from pymodaq.utils.plotting.utils.plot_utils import Data0DWithHistory

import numpy as np
from collections import OrderedDict
import datetime

logger = set_logger(get_module_name(__file__))
PLOT_COLORS = utils.plot_colors


class DataDisplayer(QObject):
    """
    This Object deals with the display of 1D data  on a plotitem
    """

    updated_item = Signal(list)
    labels_changed = Signal(list)

    def __init__(self, plotitem: pyqtgraph.PlotItem):
        super().__init__()
        self._plotitem = plotitem
        self._plotitem.addLegend()
        self._plot_items: List[pyqtgraph.PlotDataItem] = []
        self._data = Data0DWithHistory()

        axis = self._plotitem.getAxis('bottom')
        axis.setLabel(text='Samples', units='S')

    @property
    def legend(self):
        return self._plotitem.legend

    @property
    def axis(self):
        return self._data.xaxis

    def clear_data(self):
        self._data.clear_data()

    def update_axis(self, history_length: int):
        self._data.length = history_length

    def update_data(self, data: data_mod.DataRaw):
        if len(data) != len(self._plot_items):
            self.update_display_items(data)

        self._data.add_datas(data)
        for ind, data_str in enumerate(self._data.datas):
            self._plot_items[ind].setData(self._data.xaxis, self._data.datas[data_str])

    def update_display_items(self, data: data_mod.DataRaw):
        while len(self._plot_items) > 0:
            self._plotitem.removeItem(self._plot_items.pop(0))
            self.legend.removeItem(self.legend_items[0])

        for ind in range(len(data)):
            self._plot_items.append(pyqtgraph.PlotDataItem(pen=PLOT_COLORS[ind]))
            self._plotitem.addItem(self._plot_items[-1])
            self.legend.addItem(self._plot_items[-1], data.labels[ind])
        self.updated_item.emit(self._plot_items)
        self.labels_changed.emit(data.labels)


class View0D(ActionManager, QObject):
    def __init__(self, parent_widget: QtWidgets.QWidget = None):
        QObject.__init__(self)
        ActionManager.__init__(self, toolbar=QtWidgets.QToolBar())

        self.data_displayer: DataDisplayer = None
        self.plot_widget: PlotWidget = PlotWidget()
        self.values_list = QtWidgets.QListWidget()

        self.setup_actions()

        self.parent_widget = parent_widget
        if self.parent_widget is None:
            self.parent_widget = QtWidgets.QWidget()
            self.parent_widget.show()

        self.data_displayer = DataDisplayer(self.plotitem)

        self._setup_widgets()
        self._connect_things()
        self._prepare_ui()

    def setup_actions(self):
        self.add_action('clear', 'Clear plot', 'clear2', 'Clear the current plots')
        self.add_widget('Nhistory', pyqtgraph.SpinBox, tip='Set the history length of the plot',
                        setters=dict(setMaximumWidth=100))
        self.add_action('show_data_as_list', 'Show numbers', 'ChnNum', 'It triggered will display last data as numbers'
                                                                       'in a side panel', checkable=True)

    def _setup_widgets(self):
        self.parent_widget.setLayout(QtWidgets.QVBoxLayout())
        self.parent_widget.layout().addWidget(self.toolbar)

        splitter_hor = QtWidgets.QSplitter(Qt.Horizontal)
        self.parent_widget.layout().addWidget(splitter_hor)

        splitter_hor.addWidget(self.plot_widget)
        splitter_hor.addWidget(self.values_list)

        font = QtGui.QFont()
        font.setPointSize(20)
        self.values_list.setFont(font)

    def _connect_things(self):
        self.connect_action('clear', self.data_displayer.clear_data)
        self.connect_action('show_data_as_list', self.show_data_list)
        self.connect_action('Nhistory', self.data_displayer.update_axis, signal_name='valueChanged')

    def _prepare_ui(self):
        """add here everything needed at startup"""
        self.values_list.setVisible(False)

    def get_double_clicked(self):
        return self.plot_widget.view.sig_double_clicked

    @property
    def plotitem(self):
        return self.plot_widget.plotItem

    def display_data(self, data: data_mod.DataRaw):
        self.data_displayer.update_data(data)
        if self.is_action_checked('show_data_as_list'):
            self.values_list.clear()
            self.values_list.addItems(['{:.03e}'.format(dat[0]) for dat in data])
            QtWidgets.QApplication.processEvents()

    def show_data_list(self, state=None):
        if state is None:
            state = self.is_action_checked('show_data_as_list')
        self.values_list.setVisible(state)


class Viewer0D(ViewerBase):
    """this plots 0D data on a plotwidget with history. Display as numbers in a table is possible.

    Datas and measurements are then exported with the signal data_to_export_signal
    """
    convenience_attributes = ('has_action', 'is_action_checked', 'is_action_visible', 'set_action_checked',
                              'set_action_visible', 'get_action', 'addAction', 'toolbar',
                              'viewer', 'roi_manager')

    def __init__(self, parent=None, title=''):
        super().__init__(parent, title)
        self.view = View0D(self.parent)
        self._labels = []
        self.add_attributes_from_view()

    @property
    def labels(self):
        return self._labels

    @labels.setter
    def labels(self, labels):
        if labels != self._labels:
            self._labels = labels

    @Slot(list)
    def _show_data(self, data: data_mod.DataRaw):
        self.labels = data.labels
        self.view.display_data(data)
        self.data_to_export_signal.emit(self.data_to_export)


def main_view():
    app = QtWidgets.QApplication(sys.argv)
    widget = QtWidgets.QWidget()
    prog = View0D(widget)
    widget.show()
    sys.exit(app.exec_())


def main():
    app = QtWidgets.QApplication(sys.argv)
    widget = QtWidgets.QWidget()
    prog = Viewer0D(widget)
    from pymodaq.utils.daq_utils import gauss1D

    x = np.linspace(0, 200, 201)
    y1 = gauss1D(x, 75, 25)
    y2 = gauss1D(x, 120, 50, 2)
    widget.show()
    prog.get_action('show_data_as_list').trigger()
    for ind, data in enumerate(y1):
        prog.show_data(data_mod.DataRaw('mydata', data=[np.array([data]), np.array([y2[ind]])],
                                        labels=['lab1', 'lab2']))
        QtWidgets.QApplication.processEvents()

    sys.exit(app.exec_())


if __name__ == '__main__':  # pragma: no cover
    #main_view()
    main()

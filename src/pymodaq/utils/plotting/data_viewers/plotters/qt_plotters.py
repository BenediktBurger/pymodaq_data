from typing import List, Tuple, Any, TYPE_CHECKING
import sys

from qtpy import QtWidgets

from pymodaq.utils.logger import set_logger, get_module_name
from pymodaq.utils import config as configmod
from pymodaq.utils.gui_utils.utils import start_qapplication
from pymodaq.utils.plotting.data_viewers.plotter import PlotterBase, PlotterFactory

from pymodaq.utils.plotting.data_viewers import Viewer1D, Viewer2D, ViewerND
from pymodaq.utils.plotting.data_viewers.viewer import ViewerBase

if TYPE_CHECKING:
    from pymodaq.utils.data import DataWithAxes, DataDim

logger = set_logger(get_module_name(__file__))
config = configmod.Config()


class Plotter(PlotterBase):
    backend = 'qt'

    def __init__(self, **_ignored):
        super().__init__()

    def plot(self, data: DataWithAxes) -> ViewerBase:
        do_exit = False
        qapp = QtWidgets.QApplication.instance()
        if qapp is None:
            do_exit = True
            qapp = start_qapplication()

        viewer = None
        widget = QtWidgets.QWidget()

        if data.dim.name == 'Data1D':
            viewer = Viewer1D(widget)
        elif data.dim.name == 'Data2D':
            viewer = Viewer2D(widget)
        elif data.dim.name == 'DataND':
            viewer = ViewerND(widget)

        if viewer is not None:
            widget.show()
            viewer.show_data(data)

        if do_exit:
            sys.exit(qapp.exec())
        return viewer


@PlotterFactory.register()
class Plotter1D(Plotter):
    """ """
    data_dim = 'Data1D'


@PlotterFactory.register()
class Plotter2D(Plotter):
    """ """
    data_dim = 'Data2D'


@PlotterFactory.register()
class PlotterND(Plotter):
    """ """
    data_dim = 'DataND'


if __name__ == '__main__':
    from pymodaq.utils import data as data_mod
    import numpy as np
    from pymodaq.utils.math_utils import gauss1D
    from pymodaq.utils.plotting.data_viewers.plotter import PlotterFactory
    plotter_factory = PlotterFactory()

    x = np.random.randint(201, size=201)
    y1 = gauss1D(x, 75, 25)
    y2 = gauss1D(x, 120, 50, 2)

    QtWidgets.QApplication.processEvents()
    dwa = data_mod.DataRaw('mydata', data=[y1, y2],
                            axes=[data_mod.Axis('myaxis', 'units', data=x, index=0,
                                                spread_order=0)],
                            nav_indexes=())

    plotter_factory.get('qt', dwa.dim).plot(dwa)
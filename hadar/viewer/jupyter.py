from typing import Dict, List

import matplotlib
import ipywidgets as widgets
from IPython.display import display, clear_output

from hadar.aggregator.result import *
from hadar.viewer.html import HTMLPlotting


class JupyterPlotting(HTMLPlotting):
    """
    Plotting implementation to use with Jupyter.
    Graphics are generated by HTMLPlotting, then jupyter widgets are used to be more flexible.
    """
    def __init__(self, agg, unit_symbol: str = '',
                 time_start=None, time_end=None,
                 cmap=matplotlib.cm.coolwarm,
                 node_coord: Dict[str, List[float]] = None,
                 map_element_size: int = 1):
        """
        Create instance.

        :param agg: ResultAggragator instance to use
        :param unit_symbol: symbol on quantity unit used. ex. MW, litter, Go, ...
        :param time_start: time to use as the start of study horizon
        :param time_end: time to use as the end of study horizon
        :param cmap: matplotlib color map to use (coolwarm as default)
        :param node_coord: nodes coordinates to use for map plotting
        :param map_element_size: size on element draw on map. default as 1.
        """

        HTMLPlotting.__init__(self, agg, unit_symbol, time_start, time_end, cmap, node_coord, map_element_size)

    def _dropmenu(self, plot, items):
        """
        Wrap html graphics with dropdown menu.

        :param plot: plot function to call when value change
        :param items: list of items present in drop down menu
        :return:
        """
        menu = widgets.Dropdown(options=items, value=items[0],
                                description='Node:', disabled=False)
        output = widgets.Output()

        def _plot(select):
            with output:
                clear_output()
                fig = plot(self, select)
                fig.show()

        def _on_event(event):
            if event['name'] == 'value' and event['type'] == 'change':
                _plot(event['new'])

        menu.observe(_on_event)
        display(menu, output)
        _plot(items[0])

    def stack(self, node: str = None):
        """
        Plot with production stacked with area and consumptions stacked by dashed lines.

        :param node: select node to plot. If None, use a dropdown menu to select inside notebook
        :return: plotly figure or jupyter widget to plot
        """
        if node is not None:
            return HTMLPlotting.stack(self, node).show()
        else:
            nodes = list(self.agg.nodes)
            self._dropmenu(HTMLPlotting.stack, nodes)

    def _intslider(self, plot, size):
        """
        Wrap plot with a intslider.

        :param plot: plot to call when value change
        :param size: size of intslider (min=0, step=1)
        :return:
        """
        slider = widgets.IntSlider(value=0, min=0, max=size, step=1, description='Timestep:', disabled=False,
                                   continuous_update=False, orientation='horizontal', readout=True, readout_format='d')
        output = widgets.Output()

        def _plot(select):
            with output:
                clear_output()
                fig = plot(self, select)
                fig.show()

        def _on_event(event):
            if event['name'] == 'value' and event['type'] == 'change':
                _plot(event['new'])

        slider.observe(_on_event)
        display(slider, output)
        _plot(0)

    def exchanges_map(self, t: int = None):
        """
        Plot a map with node (color are balance) and arrow between nodes (color for quantity).

        :param t: timestep to plot
        :return: plotly figure or jupyter widget to plot
        """
        if t is not None:
            HTMLPlotting.exchanges_map(self, t)
        else:
            h = self.agg.horizon -1
            self._intslider(HTMLPlotting.exchanges_map, h)

# -*- coding: utf-8 -*-
"""GeoSketch - plugin QGIS com fluxo de trabalho estilo Google Earth."""


def classFactory(iface):  # pylint: disable=invalid-name
    from .earth_tools import EarthTools
    return EarthTools(iface)

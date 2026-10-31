# -*- coding: utf-8 -*-
"""Janela "Ir para coordenadas": centraliza o mapa num ponto digitado.

Fica aberta o tempo todo, como as outras janelas do plugin - digitar uma
coordenada nova e clicar em Ir recentraliza de novo, sem precisar reabrir.
"""

from qgis.core import QgsPointXY
from qgis.PyQt.QtCore import Qt
from qgis.PyQt.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLineEdit,
    QMessageBox,
    QVBoxLayout,
)

from . import utils


class GotoDialog(QDialog):
    def __init__(self, iface, parent=None):
        super(GotoDialog, self).__init__(parent)
        self.iface = iface
        self.canvas = iface.mapCanvas()

        self.setWindowTitle("GeoSketch - Ir para coordenadas")
        self.setWindowFlags(self.windowFlags() | Qt.WindowStaysOnTopHint)
        self.setModal(False)
        self.setMinimumWidth(360)

        layout = QVBoxLayout(self)
        form = QFormLayout()
        self.lat_edit = QLineEdit()
        self.lon_edit = QLineEdit()
        self.lat_edit.setPlaceholderText("Ex.: -23.5769 ou 23°34.616'S")
        self.lon_edit.setPlaceholderText("Ex.: -46.6560 ou 46°39.360'O")
        form.addRow("Latitude:", self.lat_edit)
        form.addRow("Longitude:", self.lon_edit)
        layout.addLayout(form)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.button(QDialogButtonBox.Ok).setText("Ir")
        buttons.button(QDialogButtonBox.Cancel).setText("Fechar")
        buttons.accepted.connect(self._goto)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        self.lat_edit.setFocus()

    def _goto(self):
        lat = utils.parse_coordinate(self.lat_edit.text())
        lon = utils.parse_coordinate(self.lon_edit.text())
        if lat is None or lon is None:
            QMessageBox.warning(
                self,
                "GeoSketch",
                "Não foi possível interpretar a latitude/longitude digitadas.",
            )
            return
        if not (-90.0 <= lat <= 90.0) or not (-180.0 <= lon <= 180.0):
            QMessageBox.warning(
                self,
                "GeoSketch",
                "Latitude precisa estar entre -90 e 90, e longitude entre -180 e 180.",
            )
            return
        try:
            point = utils.from_wgs84(
                QgsPointXY(lon, lat), self.canvas.mapSettings().destinationCrs()
            )
        except Exception as exc:
            QMessageBox.warning(
                self, "GeoSketch", "Erro ao converter a coordenada:\n{}".format(exc)
            )
            return
        self.canvas.setCenter(point)
        self.canvas.refresh()

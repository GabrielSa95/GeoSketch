# -*- coding: utf-8 -*-
"""Janela "Dividir polígono..." (Fase F3): corta um polígono existente com
uma linha desenhada no mapa, gerando as partes resultantes. O polígono
original só é apagado depois de o usuário confirmar o resultado.
"""

from qgis.core import QgsGeometry, QgsProject, QgsWkbTypes
from qgis.PyQt.QtCore import Qt
from qgis.PyQt.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
)

from . import geoprocessing, storage, utils
from .maptools import DrawTool


class SplitDialog(QDialog):
    def __init__(self, iface, layer, parent=None):
        """layer: UM QgsVectorLayer de polígono (lugar do plugin) - ver
        layeractions._on_split()."""
        super(SplitDialog, self).__init__(parent)
        self.iface = iface
        self.layer = layer
        self.canvas = iface.mapCanvas()
        self._previous_tool = self.canvas.mapTool()
        self._parts = None

        self.setWindowTitle("GeoSketch - Dividir polígono")
        self.setWindowFlags(self.windowFlags() | Qt.WindowStaysOnTopHint)
        self.setModal(False)
        self.setMinimumWidth(420)

        layout = QVBoxLayout(self)
        hint = QLabel(
            'Desenhe no mapa a linha de corte que atravessa "{}" de um lado ao outro. '
            "Botão direito ou duplo clique para encerrar o desenho.".format(layer.name())
        )
        hint.setWordWrap(True)
        layout.addWidget(hint)

        self.status = QLabel("Aguardando o desenho da linha de corte...")
        self.status.setStyleSheet("color: #555; font-style: italic;")
        self.status.setWordWrap(True)
        layout.addWidget(self.status)

        footer = QHBoxLayout()
        self.btn_preview = QPushButton("Pré-visualizar divisão")
        self.btn_preview.setEnabled(False)
        self.btn_confirm = QPushButton("Confirmar divisão")
        self.btn_confirm.setEnabled(False)
        self.btn_cancel = QPushButton("Cancelar")
        footer.addWidget(self.btn_preview)
        footer.addWidget(self.btn_confirm)
        footer.addWidget(self.btn_cancel)
        layout.addLayout(footer)

        self.btn_preview.clicked.connect(self._preview)
        self.btn_confirm.clicked.connect(self._confirm)
        self.btn_cancel.clicked.connect(self.close)

        self.tool = DrawTool(self.canvas, "line", iface=self.iface)
        self.tool.set_snapping_enabled(False)
        self.tool.pointsChanged.connect(self._points_changed)
        self.tool.finished.connect(self._points_changed)
        self.canvas.setMapTool(self.tool)

    def _points_changed(self, points):
        self._parts = None
        self.btn_confirm.setEnabled(False)
        self.btn_preview.setEnabled(len(points) >= 2)
        if len(points) >= 2:
            self.status.setText("Linha com {} vértice(s) - clique em Pré-visualizar.".format(len(points)))

    def _cut_geometry(self):
        points = self.tool.geometry_points()
        if len(points) < 2:
            return None
        return QgsGeometry.fromPolylineXY(points)

    def _preview(self):
        cut = self._cut_geometry()
        if cut is None:
            return
        features = list(self.layer.getFeatures())
        if not features:
            QMessageBox.warning(self, "GeoSketch", "O polígono de origem não tem geometria.")
            return
        polygon_geom = features[0].geometry()
        canvas_crs = self.canvas.mapSettings().destinationCrs()
        try:
            parts = geoprocessing.split_polygon(
                polygon_geom, self.layer.crs(), cut, canvas_crs, self.layer.crs()
            )
        except geoprocessing.GeoprocessingError as exc:
            QMessageBox.warning(self, "GeoSketch", str(exc))
            self._parts = None
            self.btn_confirm.setEnabled(False)
            return
        self._parts = parts
        self.status.setText(
            "Pré-visualização: a divisão produziria {} partes. Confirme para gravar.".format(
                len(parts)
            )
        )
        self.btn_confirm.setEnabled(True)

    def _confirm(self):
        if not self._parts:
            return
        base_name = self.layer.name()
        attributes = {
            "cor_linha": storage.get_style(self.layer)["cor_linha"],
            "cor_preenchimento": storage.get_style(self.layer)["cor_preenchimento"],
            "largura_linha": storage.get_style(self.layer)["largura_linha"],
        }
        criadas = []
        try:
            for i, geom in enumerate(self._parts):
                nome = "{} ({})".format(base_name, i + 1)
                layer = storage.create_place(
                    "polygon", nome, geom, attributes, crs=self.layer.crs()
                )
                criadas.append(layer)
        except Exception as exc:
            utils.log("Falha ao gravar partes da divisao: {}".format(exc), "critical")
            QMessageBox.critical(
                self, "GeoSketch",
                "Não foi possível gravar as partes da divisão:\n{}".format(exc),
            )
            return

        # Só apaga o original DEPOIS de todas as partes terem sido gravadas
        # com sucesso - requisito explícito de preservar o original até a
        # confirmação (e até aqui, a confirmação só vale se a gravação
        # realmente funcionou).
        try:
            storage.delete_place(self.layer)
        except Exception as exc:
            utils.log("Falha ao apagar o poligono original apos a divisao: {}".format(exc), "warning")
            QMessageBox.warning(
                self, "GeoSketch",
                "As partes foram criadas, mas não foi possível remover o polígono "
                "original automaticamente:\n{}".format(exc),
            )

        self.iface.messageBar().pushSuccess(
            "GeoSketch",
            "Polígono dividido em {} partes.".format(len(criadas)),
        )
        self.close()

    def closeEvent(self, event):
        try:
            self.tool.reset()
            self.canvas.unsetMapTool(self.tool)
            if self._previous_tool is not None:
                self.canvas.setMapTool(self._previous_tool)
        except Exception:
            pass
        super(SplitDialog, self).closeEvent(event)

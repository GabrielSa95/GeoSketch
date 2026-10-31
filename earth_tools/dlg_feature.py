# -*- coding: utf-8 -*-
"""Janelas Novo Marcador / Novo Caminho / Novo Poligono.

A janela abre ANTES do desenho e fica aberta enquanto o usuario clica os
vertices, como no Google Earth. Ao clicar OK a feicao vira uma camada propria
no painel Camadas, com o nome digitado.
"""

from qgis.core import QgsCoordinateTransform, QgsGeometry, QgsPointXY, QgsProject
from qgis.PyQt.QtCore import Qt
from qgis.PyQt.QtGui import QColor
from qgis.PyQt.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from . import storage, utils
from .maptools import DrawTool
from .widgets import CrsRow, DescriptionTab, SnapRow, StyleTab, UnitRow, VertexEntryPanel

TITLES = {
    "point": "Novo Marcador de local",
    "line": "Novo Caminho",
    "polygon": "Novo Poligono",
}

DEFAULT_NAMES = {
    "point": "Marcador de local sem titulo",
    "line": "Caminho sem titulo",
    "polygon": "Area 1",
}

HINTS = {
    "point": "Clique no mapa para posicionar o marcador, ou digite as coordenadas.",
    "line": "Clique no mapa para tracar o caminho. Botao direito, duplo clique ou "
            "Concluir encerram.",
    "polygon": "Clique no mapa para marcar os cantos. Botao direito, duplo clique ou "
               "Concluir fecham a area.",
}


class FeatureDialog(QDialog):
    def __init__(self, iface, kind, parent_group=None, parent=None):
        super(FeatureDialog, self).__init__(parent)
        self.iface = iface
        self.canvas = iface.mapCanvas()
        self.kind = kind
        self.parent_group = parent_group
        self.points = []
        self._previous_tool = self.canvas.mapTool()

        self.setWindowTitle("GeoSketch - " + TITLES[kind])
        self.setWindowFlags(self.windowFlags() | Qt.WindowStaysOnTopHint)
        self.setModal(False)
        self.setMinimumWidth(560)

        layout = QVBoxLayout(self)

        header = QFormLayout()
        self._default_name = storage.next_default_name(kind)
        self.name_edit = QLineEdit(self._default_name)
        header.addRow("Nome:", self.name_edit)

        if kind == "point":
            self.lat_edit = QLineEdit()
            self.lon_edit = QLineEdit()
            header.addRow("Latitude:", self.lat_edit)
            header.addRow("Longitude:", self.lon_edit)
            self.lat_edit.editingFinished.connect(self._coords_typed)
            self.lon_edit.editingFinished.connect(self._coords_typed)
        else:
            self.lat_edit = None
            self.lon_edit = None
        layout.addLayout(header)

        self.hint = QLabel(HINTS[kind])
        self.hint.setWordWrap(True)
        self.hint.setStyleSheet("color: #555; font-style: italic;")
        layout.addWidget(self.hint)

        self.snap_row = SnapRow()
        layout.addWidget(self.snap_row)

        # SRC/CRS de saida: so o Novo Caminho ganha este seletor (pedido
        # explicito do usuario - nao bastava so na aba Caminho da Regua).
        # Comeca no SRC do projeto; nao afeta marcador nem poligono.
        self.crs_row = None
        if kind == "line":
            self.crs_row = CrsRow(
                QgsProject.instance().crs(), label="SRC/CRS da camada de saída:"
            )
            layout.addWidget(self.crs_row)

        self.tabs = QTabWidget()
        self.description_tab = DescriptionTab()
        self.tabs.addTab(self.description_tab, "Descricao")
        self.style_tab = StyleTab(
            with_fill=(kind in ("point", "polygon")),
            with_width=(kind in ("line", "polygon")),
        )
        if kind == "point":
            self.style_tab.line_color.setColor(QColor(255, 200, 0))
        self.tabs.addTab(self.style_tab, "Estilo/Cor")
        if kind in ("line", "polygon"):
            self.tabs.addTab(self._build_measure_tab(), "Medidas")
            self.vertex_entry = VertexEntryPanel(self.canvas)
            self.vertex_entry.set_last_point_getter(
                lambda: self.points[-1] if self.points else None
            )
            self.vertex_entry.pointComputed.connect(self._add_vertex_from_panel)
            self.tabs.addTab(self.vertex_entry, "Adicionar por medida")
        else:
            self.vertex_entry = None
        layout.addWidget(self.tabs)

        footer = QHBoxLayout()
        self.btn_finish = QPushButton("Concluir desenho")
        self.btn_finish.setToolTip(
            "Fecha o desenho. Equivale ao botao direito ou ao duplo clique no mapa."
        )
        self.btn_finish.setEnabled(False)
        self.btn_restart = QPushButton("Recomecar")
        footer.addWidget(self.btn_finish)
        footer.addWidget(self.btn_restart)
        footer.addStretch()
        self.buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        self.buttons.button(QDialogButtonBox.Ok).setText("OK")
        self.buttons.button(QDialogButtonBox.Cancel).setText("Cancelar")
        footer.addWidget(self.buttons)
        layout.addLayout(footer)

        self.buttons.accepted.connect(self._save)
        self.buttons.rejected.connect(self.reject)
        self.btn_finish.clicked.connect(self._finish_drawing)
        self.btn_restart.clicked.connect(self._restart)

        self.tool = DrawTool(self.canvas, kind, iface=self.iface)
        self.tool.pointsChanged.connect(self._points_changed)
        self.tool.finished.connect(self._points_finished)
        self.snap_row.bind(self.tool)
        self.canvas.setMapTool(self.tool)

        self._update_buttons()
        self.name_edit.setFocus()
        self.name_edit.selectAll()

    # ---------------------------------------------------------------- abas
    def _build_measure_tab(self):
        widget = QWidget()
        layout = QVBoxLayout(widget)
        self.perimeter_row = None
        self.area_row = None
        self.length_row = None
        if self.kind == "polygon":
            self.perimeter_row = UnitRow(
                "Perimetro:", utils.LENGTH_UNITS, utils.DEFAULT_LENGTH
            )
            self.area_row = UnitRow("Area:", utils.AREA_UNITS, utils.DEFAULT_AREA)
            layout.addWidget(self.perimeter_row)
            layout.addWidget(self.area_row)
            self.perimeter_row.unitChanged.connect(self._refresh_measures)
            self.area_row.unitChanged.connect(self._refresh_measures)
        else:
            self.length_row = UnitRow(
                "Comprimento:", utils.LENGTH_UNITS, utils.DEFAULT_LENGTH
            )
            layout.addWidget(self.length_row)
            self.length_row.unitChanged.connect(self._refresh_measures)
        layout.addStretch()
        return widget

    # ------------------------------------------------------------- desenho
    def _points_changed(self, points):
        self.points = points
        if self.kind == "point" and points:
            wgs = utils.to_wgs84(points[0], self.canvas.mapSettings().destinationCrs())
            self.lat_edit.setText(utils.format_dm(wgs.y(), True))
            self.lon_edit.setText(utils.format_dm(wgs.x(), False))
        self._refresh_measures()
        self._update_buttons()

    def _points_finished(self, points):
        self.points = points
        self._refresh_measures()
        self._update_buttons()
        self.hint.setText("Desenho fechado. Confira o nome e clique em OK para salvar.")
        self.hint.setStyleSheet("color: #1B7A2F; font-weight: bold;")
        self.buttons.button(QDialogButtonBox.Ok).setFocus()

    def _finish_drawing(self):
        self.tool.finish()

    def _add_vertex_from_panel(self, point):
        if not self.tool.add_vertex(point):
            QMessageBox.information(
                self,
                "GeoSketch",
                "Conclua ou recomece o desenho antes de adicionar um vértice por medida.",
            )

    def _restart(self):
        self.tool.reset()
        self.hint.setText(HINTS[self.kind])
        self.hint.setStyleSheet("color: #555; font-style: italic;")
        self._update_buttons()

    def _coords_typed(self):
        if self.kind != "point":
            return
        lat = utils.parse_coordinate(self.lat_edit.text())
        lon = utils.parse_coordinate(self.lon_edit.text())
        if lat is None or lon is None:
            return
        try:
            point = utils.from_wgs84(
                QgsPointXY(lon, lat), self.canvas.mapSettings().destinationCrs()
            )
        except Exception:
            return
        self.tool.done = False
        self.tool.points = [point]
        self.tool._refresh()
        self.tool.finish()

    def _refresh_measures(self):
        crs = self.canvas.mapSettings().destinationCrs()
        if self.kind == "polygon" and self.perimeter_row is not None:
            perimeter = utils.measure_perimeter(self.points, crs)
            area = utils.measure_area(self.points, crs)
            self.perimeter_row.setValue(
                utils.format_number(
                    utils.convert_length(perimeter, self.perimeter_row.unit())
                )
            )
            self.area_row.setValue(
                utils.format_number(utils.convert_area(area, self.area_row.unit()))
            )
        elif self.kind == "line" and self.length_row is not None:
            length = utils.measure_length(self.points, crs)
            self.length_row.setValue(
                utils.format_number(utils.convert_length(length, self.length_row.unit()))
            )

    def _update_buttons(self):
        enough = self.tool.can_finish()
        done = getattr(self.tool, "done", False)
        self.btn_finish.setEnabled(enough and not done)
        self.buttons.button(QDialogButtonBox.Ok).setEnabled(enough)

    # -------------------------------------------------------------- gravar
    def _build_geometry(self):
        """Devolve (geometry, crs_de_gravacao). crs_de_gravacao é None quando
        a feição grava em EPSG:4326 (comportamento de sempre - marcador e
        polígono, e também o caminho se o seletor de SRC não foi tocado).

        Para o Novo Caminho, quando o usuário escolhe um SRC diferente do
        CRS do canvas, os pontos são de fato TRANSFORMADOS
        (QgsCoordinateTransform) para esse SRC antes de montar a geometria
        - não é só uma etiqueta trocada; as coordenadas gravadas mudam.
        """
        canvas_crs = self.canvas.mapSettings().destinationCrs()

        if self.kind == "line" and self.crs_row is not None:
            target_crs = self.crs_row.crs()
            if target_crs is None or not target_crs.isValid():
                target_crs = QgsProject.instance().crs()
            if target_crs != canvas_crs:
                transform = QgsCoordinateTransform(canvas_crs, target_crs, QgsProject.instance())
                pts = [transform.transform(p) for p in self.points]
            else:
                pts = list(self.points)
            return QgsGeometry.fromPolylineXY(pts), target_crs

        wgs = [utils.to_wgs84(p, canvas_crs) for p in self.points]
        if self.kind == "point":
            return QgsGeometry.fromPointXY(wgs[0]), None
        ring = list(wgs)
        if ring[0] != ring[-1]:
            ring.append(ring[0])
        return QgsGeometry.fromPolygonXY([ring]), None

    def _save(self):
        if not self.tool.can_finish():
            return
        # Se o usuario clicar OK sem fechar, fechamos por ele.
        if not self.tool.done:
            self.tool.finish()
        name = self.name_edit.text().strip() or self._default_name
        try:
            geometry, save_crs = self._build_geometry()
        except Exception as exc:
            QMessageBox.warning(self, "GeoSketch", "Erro na geometria: {}".format(exc))
            return

        attributes = {
            "descricao": self.description_tab.text(),
            "cor_linha": self.style_tab.line_color_string(),
            "cor_preenchimento": self.style_tab.fill_color_string(),
            "largura_linha": self.style_tab.line_width_value(),
        }
        try:
            layer = storage.create_place(
                self.kind, name, geometry, attributes, self.parent_group, crs=save_crs
            )
        except Exception as exc:
            QMessageBox.critical(
                self,
                "GeoSketch",
                "Nao foi possivel gravar:\n{}\n\nArquivo: {}".format(
                    exc, storage.gpkg_path()
                ),
            )
            return

        self.iface.messageBar().pushSuccess(
            "GeoSketch", '"{}" criado no painel Camadas.'.format(layer.name())
        )
        self.accept()

    # ------------------------------------------------------------ limpeza
    def closeEvent(self, event):
        self._restore_tool()
        super(FeatureDialog, self).closeEvent(event)

    def reject(self):
        self._restore_tool()
        super(FeatureDialog, self).reject()

    def accept(self):
        self._restore_tool()
        super(FeatureDialog, self).accept()

    def _restore_tool(self):
        try:
            self.tool.reset()
            if self._previous_tool is not None:
                self.canvas.setMapTool(self._previous_tool)
            else:
                self.canvas.unsetMapTool(self.tool)
        except Exception:
            pass

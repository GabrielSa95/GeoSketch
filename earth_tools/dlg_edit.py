# -*- coding: utf-8 -*-
"""Janela de edição de um lugar já criado.

Abre pelo botão direito na camada > Editar. Enquanto ela está aberta os pontos
do desenho ficam visíveis e editáveis no mapa; a janela permite mudar nome,
descrição, cor e largura da linha. OK aplica tudo, Cancelar desfaz — inclusive
os pontos que tiverem sido arrastados ou apagados.
"""

from qgis.PyQt.QtCore import Qt
from qgis.PyQt.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from . import storage, utils
from .vertexedit import VertexEditTool
from .widgets import DescriptionTab, SnapRow, StyleTab, UnitRow, VertexEntryPanel

TITLES = {
    "point": "Editar Marcador de local",
    "line": "Editar Caminho",
    "polygon": "Editar Polígono",
}

HINT = (
    "Arraste os pontos vermelhos para mover. Clique num ponto branco para criar "
    "um vértice no meio de um trecho, ou em qualquer lugar vazio do mapa para "
    "estender o desenho com um vértice novo no final. Botão direito em cima de "
    "um ponto apaga aquele ponto."
)


class EditDialog(QDialog):
    def __init__(self, iface, layer, parent=None):
        super(EditDialog, self).__init__(parent)
        self.iface = iface
        self.canvas = iface.mapCanvas()
        self.layer = layer
        self.kind = layer.customProperty(storage.CUSTOM_KEY) or "polygon"
        self._previous_tool = self.canvas.mapTool()
        self._original_name = layer.name()
        self._original_style = storage.get_style(layer)
        self._original_description = storage.get_description(layer)
        self._applied = False

        self.setWindowTitle("GeoSketch - " + TITLES.get(self.kind, "Editar"))
        self.setWindowFlags(self.windowFlags() | Qt.WindowStaysOnTopHint)
        self.setModal(False)
        self.setMinimumWidth(560)

        layout = QVBoxLayout(self)

        header = QFormLayout()
        self.name_edit = QLineEdit(self._original_name)
        header.addRow("Nome:", self.name_edit)
        layout.addLayout(header)

        if self.kind != "point":
            hint = QLabel(HINT)
            hint.setWordWrap(True)
            hint.setStyleSheet("color: #555; font-style: italic;")
            layout.addWidget(hint)
            self.snap_row = SnapRow()
            layout.addWidget(self.snap_row)
        else:
            self.snap_row = None

        self.tabs = QTabWidget()
        self.description_tab = DescriptionTab()
        self.description_tab.setText(self._original_description)
        self.tabs.addTab(self.description_tab, "Descrição")

        self.style_tab = StyleTab(
            with_fill=(self.kind in ("point", "polygon")),
            with_width=(self.kind in ("line", "polygon")),
        )
        self.style_tab.load_values(
            self._original_style["cor_linha"],
            self._original_style["cor_preenchimento"],
            self._original_style["largura_linha"],
        )
        # Prévia ao vivo: mexeu na cor, o mapa muda na hora.
        self.style_tab.changed.connect(self._preview_style)
        self.tabs.addTab(self.style_tab, "Estilo/Cor")

        if self.kind in ("line", "polygon"):
            self.tabs.addTab(self._build_measure_tab(), "Medidas")
            self.vertex_entry = VertexEntryPanel(self.canvas)
            self.vertex_entry.set_last_point_getter(
                lambda: self.tool.points[-1] if self.tool.points else None
            )
            self.vertex_entry.pointComputed.connect(self._add_vertex_from_panel)
            self.tabs.addTab(self.vertex_entry, "Adicionar por medida")
        else:
            self.vertex_entry = None
        layout.addWidget(self.tabs)

        self.buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        self.buttons.button(QDialogButtonBox.Ok).setText("OK")
        self.buttons.button(QDialogButtonBox.Cancel).setText("Cancelar")
        self.buttons.accepted.connect(self._apply)
        self.buttons.rejected.connect(self.reject)
        layout.addWidget(self.buttons)

        self.tool = VertexEditTool(
            self.canvas, layer, self.kind, iface, allow_exit=False
        )
        self.tool.changed.connect(self._refresh_measures)
        if self.snap_row is not None:
            self.snap_row.bind(self.tool)
        self.canvas.setMapTool(self.tool)

        self._refresh_measures()
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
                "Perímetro:", utils.LENGTH_UNITS, utils.DEFAULT_LENGTH
            )
            self.area_row = UnitRow("Área:", utils.AREA_UNITS, utils.DEFAULT_AREA)
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

    def _refresh_measures(self):
        points = getattr(self.tool, "points", [])
        crs = self.canvas.mapSettings().destinationCrs()
        if self.kind == "polygon" and self.perimeter_row is not None:
            self.perimeter_row.setValue(
                utils.format_number(
                    utils.convert_length(
                        utils.measure_perimeter(points, crs), self.perimeter_row.unit()
                    )
                )
            )
            self.area_row.setValue(
                utils.format_number(
                    utils.convert_area(
                        utils.measure_area(points, crs), self.area_row.unit()
                    )
                )
            )
        elif self.kind == "line" and self.length_row is not None:
            self.length_row.setValue(
                utils.format_number(
                    utils.convert_length(
                        utils.measure_length(points, crs), self.length_row.unit()
                    )
                )
            )

    def _add_vertex_from_panel(self, point):
        if not self.tool.add_vertex(point):
            QMessageBox.information(
                self,
                "GeoSketch",
                "Não foi possível adicionar o vértice por medida.",
            )

    # ------------------------------------------------------------- estilo
    def _preview_style(self):
        storage.apply_style(
            self.layer,
            self.kind,
            self.style_tab.line_color_string(),
            self.style_tab.fill_color_string(),
            self.style_tab.line_width_value(),
        )
        self.layer.triggerRepaint()

    # -------------------------------------------------------------- ações
    def _apply(self):
        name = self.name_edit.text().strip() or self._original_name
        try:
            storage.set_style(
                self.layer,
                self.kind,
                self.style_tab.line_color_string(),
                self.style_tab.fill_color_string(),
                self.style_tab.line_width_value(),
            )
            storage.set_description(self.layer, self.description_tab.text())
            if name != self._original_name:
                storage.rename_place(self.layer, storage.unique_display_name(name))
            else:
                storage.rename_place(self.layer, name)
        except Exception as exc:
            QMessageBox.critical(
                self, "GeoSketch", "Não foi possível aplicar:\n{}".format(exc)
            )
            return
        self._applied = True
        self.layer.triggerRepaint()
        self.iface.messageBar().pushSuccess(
            "GeoSketch", '"{}" atualizado.'.format(self.layer.name())
        )
        self.accept()

    def _revert(self):
        try:
            self.tool.restore_original()
        except Exception:
            pass
        try:
            storage.set_style(
                self.layer,
                self.kind,
                self._original_style["cor_linha"],
                self._original_style["cor_preenchimento"],
                self._original_style["largura_linha"],
            )
            self.layer.setName(self._original_name)
            self.layer.triggerRepaint()
        except Exception:
            pass

    # ------------------------------------------------------------ limpeza
    def reject(self):
        self._revert()
        self._restore_tool()
        super(EditDialog, self).reject()

    def accept(self):
        self._restore_tool()
        super(EditDialog, self).accept()

    def closeEvent(self, event):
        if not self._applied:
            self._revert()
        self._restore_tool()
        super(EditDialog, self).closeEvent(event)

    def _restore_tool(self):
        try:
            if self._previous_tool is not None:
                self.canvas.setMapTool(self._previous_tool)
            else:
                self.canvas.unsetMapTool(self.tool)
        except Exception:
            pass

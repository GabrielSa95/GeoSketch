# -*- coding: utf-8 -*-
"""Janela "Diferença..." (Fase F5): remove de um polígono a parte que se
sobrepõe a outro, via o algoritmo nativo native:difference. Distinto do
recorte (F4): o recorte MANTÉM só o que está dentro da máscara; a
diferença REMOVE o que está dentro da segunda geometria.
"""

from qgis.core import QgsProject
from qgis.PyQt.QtCore import Qt
from qgis.PyQt.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QVBoxLayout,
)

from . import geoprocessing, places_model, storage, utils
from .widgets import CrsRow, StyleTab

KIND_LABEL = {"point": "marcador", "line": "caminho", "polygon": "polígono"}


class DifferenceDialog(QDialog):
    def __init__(self, iface, place_layers, base_layer=None, parent=None):
        super(DifferenceDialog, self).__init__(parent)
        self.iface = iface
        self.place_layers = place_layers

        self.setWindowTitle("GeoSketch - Diferença")
        self.setWindowFlags(self.windowFlags() | Qt.WindowStaysOnTopHint)
        self.setModal(True)
        self.setMinimumWidth(460)

        layout = QVBoxLayout(self)
        form = QFormLayout()

        self.base_combo = QComboBox()
        self.subtract_combo = QComboBox()
        for layer in self.place_layers:
            kind = layer.customProperty(storage.CUSTOM_KEY) or ""
            rotulo = "{} ({})".format(layer.name(), KIND_LABEL.get(kind, kind))
            self.base_combo.addItem(rotulo, layer.id())
            self.subtract_combo.addItem(rotulo, layer.id())

        if base_layer is not None:
            index = self.base_combo.findData(base_layer.id())
            if index >= 0:
                self.base_combo.setCurrentIndex(index)

        form.addRow("Camada base:", self.base_combo)
        form.addRow("Subtrair:", self.subtract_combo)

        self.name_edit = QLineEdit()
        form.addRow("Nome do resultado:", self.name_edit)
        layout.addLayout(form)

        project_crs = QgsProject.instance().crs()
        self.output_crs_row = CrsRow(project_crs, label="SRC de saída:")
        layout.addWidget(self.output_crs_row)

        style_box = QGroupBox("Estilo do resultado")
        style_layout = QVBoxLayout(style_box)
        self.style_tab = StyleTab(with_fill=True, with_width=True)
        style_layout.addWidget(self.style_tab)
        layout.addWidget(style_box)

        folder_row = QHBoxLayout()
        folder_row.addWidget(QLabel("Pasta de destino:"))
        self.folder_combo = QComboBox()
        for folder_id, rotulo in places_model.folder_choices():
            self.folder_combo.addItem(rotulo, folder_id)
        folder_row.addWidget(self.folder_combo)
        layout.addLayout(folder_row)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.button(QDialogButtonBox.Ok).setText("Calcular diferença")
        buttons.button(QDialogButtonBox.Cancel).setText("Cancelar")
        buttons.accepted.connect(self._run)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        self._update_default_name()
        self.base_combo.currentIndexChanged.connect(self._update_default_name)
        self.subtract_combo.currentIndexChanged.connect(self._update_default_name)

    def _layer_by_id(self, layer_id):
        return QgsProject.instance().mapLayer(layer_id)

    def _update_default_name(self):
        base = self._layer_by_id(self.base_combo.currentData())
        subtrair = self._layer_by_id(self.subtract_combo.currentData())
        if base is not None and subtrair is not None:
            self.name_edit.setText("{} menos {}".format(base.name(), subtrair.name()))

    def _run(self):
        base = self._layer_by_id(self.base_combo.currentData())
        subtrair = self._layer_by_id(self.subtract_combo.currentData())
        if base is None or subtrair is None:
            QMessageBox.warning(self, "GeoSketch", "Escolha a camada base e a que será subtraída.")
            return
        if base.id() == subtrair.id():
            QMessageBox.warning(
                self, "GeoSketch", "A camada base e a que será subtraída não podem ser a mesma."
            )
            return

        base_features = list(base.getFeatures())
        subtrair_features = list(subtrair.getFeatures())
        if not base_features or not subtrair_features:
            QMessageBox.warning(self, "GeoSketch", "Uma das camadas não tem geometria.")
            return

        output_crs = self.output_crs_row.crs()
        try:
            resultado = geoprocessing.difference_geometry(
                base_features[0].geometry(), base.crs(),
                subtrair_features[0].geometry(), subtrair.crs(),
                output_crs,
            )
        except geoprocessing.GeoprocessingError as exc:
            QMessageBox.critical(self, "GeoSketch", str(exc))
            return
        except Exception as exc:
            utils.log("Diferenca falhou de forma inesperada: {}".format(exc), "critical")
            QMessageBox.critical(
                self, "GeoSketch", "Erro inesperado na diferença:\n{}".format(exc)
            )
            return

        kind = base.customProperty(storage.CUSTOM_KEY) or "polygon"
        name = self.name_edit.text().strip() or "{} menos {}".format(base.name(), subtrair.name())
        attributes = {
            "cor_linha": self.style_tab.line_color_string(),
            "cor_preenchimento": self.style_tab.fill_color_string(),
            "largura_linha": self.style_tab.line_width_value(),
        }
        folder_id = self.folder_combo.currentData()

        try:
            layer = storage.create_place(kind, name, resultado, attributes, crs=output_crs)
            tabela = storage.table_name(layer)
            if tabela and folder_id:
                places_model.set_place_folder(tabela, folder_id)
        except Exception as exc:
            utils.log("Falha ao gravar resultado da diferenca: {}".format(exc), "critical")
            QMessageBox.critical(
                self, "GeoSketch",
                "A diferença foi calculada, mas não foi possível gravar o resultado:\n{}".format(exc),
            )
            return

        if folder_id:
            places_model.rebuild_layer_tree(self.iface)

        self.iface.messageBar().pushSuccess(
            "GeoSketch", 'Diferença "{}" criada no painel Camadas.'.format(layer.name())
        )
        self.accept()

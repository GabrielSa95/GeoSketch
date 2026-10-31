# -*- coding: utf-8 -*-
"""Janela "Unir polígonos..." (Fase F2): combina 2+ polígonos selecionados
numa única geometria, preservando os lugares de origem intactos.
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


class UnionDialog(QDialog):
    def __init__(self, iface, layers, parent=None):
        """layers: lista de 2+ QgsVectorLayer de polígono (lugares do
        plugin) - ver layeractions._on_union()."""
        super(UnionDialog, self).__init__(parent)
        self.iface = iface
        self.layers = layers

        self.setWindowTitle("GeoSketch - Unir polígonos")
        self.setWindowFlags(self.windowFlags() | Qt.WindowStaysOnTopHint)
        self.setModal(True)
        self.setMinimumWidth(460)

        layout = QVBoxLayout(self)

        nomes = ", ".join(layer.name() for layer in self.layers)
        origem = QLabel("Unir: {}".format(nomes))
        origem.setWordWrap(True)
        origem.setStyleSheet("font-weight: bold;")
        layout.addWidget(origem)

        form = QFormLayout()
        self.name_edit = QLineEdit("União de {} polígonos".format(len(self.layers)))
        form.addRow("Nome:", self.name_edit)
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
        buttons.button(QDialogButtonBox.Ok).setText("Unir")
        buttons.button(QDialogButtonBox.Cancel).setText("Cancelar")
        buttons.accepted.connect(self._run)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _run(self):
        output_crs = self.output_crs_row.crs()
        inputs = []
        for layer in self.layers:
            features = list(layer.getFeatures())
            if not features:
                QMessageBox.warning(
                    self, "GeoSketch",
                    '"{}" não tem nenhuma feição - ignorado.'.format(layer.name()),
                )
                continue
            inputs.append((features[0].geometry(), layer.crs()))

        try:
            resultado = geoprocessing.union_polygons(inputs, output_crs)
        except geoprocessing.GeoprocessingError as exc:
            QMessageBox.critical(self, "GeoSketch", str(exc))
            return
        except Exception as exc:
            utils.log("Uniao falhou de forma inesperada: {}".format(exc), "critical")
            QMessageBox.critical(
                self, "GeoSketch", "Erro inesperado na união:\n{}".format(exc)
            )
            return

        name = self.name_edit.text().strip() or "União de {} polígonos".format(len(self.layers))
        attributes = {
            "cor_linha": self.style_tab.line_color_string(),
            "cor_preenchimento": self.style_tab.fill_color_string(),
            "largura_linha": self.style_tab.line_width_value(),
        }
        folder_id = self.folder_combo.currentData()

        try:
            layer = storage.create_place("polygon", name, resultado, attributes, crs=output_crs)
            tabela = storage.table_name(layer)
            if tabela and folder_id:
                places_model.set_place_folder(tabela, folder_id)
        except Exception as exc:
            utils.log("Falha ao gravar resultado da uniao: {}".format(exc), "critical")
            QMessageBox.critical(
                self, "GeoSketch",
                "A união foi calculada, mas não foi possível gravar o resultado:\n{}".format(exc),
            )
            return

        if folder_id:
            places_model.rebuild_layer_tree(self.iface)

        self.iface.messageBar().pushSuccess(
            "GeoSketch", 'União "{}" criada no painel Camadas.'.format(layer.name())
        )
        self.accept()

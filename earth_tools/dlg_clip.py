# -*- coding: utf-8 -*-
"""Janela "Recortar com..." (Fase F4): recorta um lugar usando outro
polígono como máscara, via o algoritmo nativo native:clip.
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


class ClipDialog(QDialog):
    def __init__(self, iface, place_layers, target_layer=None, parent=None):
        """place_layers: todos os lugares do plugin no projeto (para
        escolher alvo/máscara); target_layer: pré-seleciona o alvo, se
        vier do menu de contexto de uma camada específica."""
        super(ClipDialog, self).__init__(parent)
        self.iface = iface
        self.place_layers = place_layers

        self.setWindowTitle("GeoSketch - Recortar com...")
        self.setWindowFlags(self.windowFlags() | Qt.WindowStaysOnTopHint)
        self.setModal(True)
        self.setMinimumWidth(460)

        layout = QVBoxLayout(self)
        form = QFormLayout()

        self.target_combo = QComboBox()
        self.mask_combo = QComboBox()
        for layer in self.place_layers:
            kind = layer.customProperty(storage.CUSTOM_KEY) or ""
            rotulo = "{} ({})".format(layer.name(), KIND_LABEL.get(kind, kind))
            self.target_combo.addItem(rotulo, layer.id())
            if kind == "polygon":
                self.mask_combo.addItem(rotulo, layer.id())

        if target_layer is not None:
            index = self.target_combo.findData(target_layer.id())
            if index >= 0:
                self.target_combo.setCurrentIndex(index)

        form.addRow("Camada a recortar:", self.target_combo)
        form.addRow("Máscara (polígono):", self.mask_combo)

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
        buttons.button(QDialogButtonBox.Ok).setText("Recortar")
        buttons.button(QDialogButtonBox.Cancel).setText("Cancelar")
        buttons.accepted.connect(self._run)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        self._update_default_name()
        self.target_combo.currentIndexChanged.connect(self._update_default_name)
        self.mask_combo.currentIndexChanged.connect(self._update_default_name)

    def _layer_by_id(self, layer_id):
        return QgsProject.instance().mapLayer(layer_id)

    def _update_default_name(self):
        alvo = self._layer_by_id(self.target_combo.currentData())
        mascara = self._layer_by_id(self.mask_combo.currentData())
        if alvo is not None and mascara is not None:
            self.name_edit.setText("{} recortado por {}".format(alvo.name(), mascara.name()))

    def _run(self):
        alvo = self._layer_by_id(self.target_combo.currentData())
        mascara = self._layer_by_id(self.mask_combo.currentData())
        if alvo is None or mascara is None:
            QMessageBox.warning(self, "GeoSketch", "Escolha a camada a recortar e a máscara.")
            return
        if alvo.id() == mascara.id():
            QMessageBox.warning(
                self, "GeoSketch", "A camada a recortar e a máscara não podem ser a mesma."
            )
            return

        alvo_features = list(alvo.getFeatures())
        mascara_features = list(mascara.getFeatures())
        if not alvo_features or not mascara_features:
            QMessageBox.warning(self, "GeoSketch", "Uma das camadas não tem geometria.")
            return

        output_crs = self.output_crs_row.crs()
        try:
            resultado = geoprocessing.clip_geometry(
                alvo_features[0].geometry(), alvo.crs(),
                mascara_features[0].geometry(), mascara.crs(),
                output_crs,
            )
        except geoprocessing.GeoprocessingError as exc:
            QMessageBox.critical(self, "GeoSketch", str(exc))
            return
        except Exception as exc:
            utils.log("Recorte falhou de forma inesperada: {}".format(exc), "critical")
            QMessageBox.critical(
                self, "GeoSketch", "Erro inesperado no recorte:\n{}".format(exc)
            )
            return

        kind = alvo.customProperty(storage.CUSTOM_KEY) or "polygon"
        name = self.name_edit.text().strip() or "{} recortado".format(alvo.name())
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
            utils.log("Falha ao gravar resultado do recorte: {}".format(exc), "critical")
            QMessageBox.critical(
                self, "GeoSketch",
                "O recorte foi calculado, mas não foi possível gravar o resultado:\n{}".format(exc),
            )
            return

        if folder_id:
            places_model.rebuild_layer_tree(self.iface)

        self.iface.messageBar().pushSuccess(
            "GeoSketch", 'Recorte "{}" criado no painel Camadas.'.format(layer.name())
        )
        self.accept()

# -*- coding: utf-8 -*-
"""Janela "Gerar Buffer..." (Fase F1): cria um polígono de Buffer a partir
de um ou mais lugares selecionados, usando o algoritmo nativo do QGIS
Processing (ver geoprocessing.py) - nunca reimplementa o cálculo.
"""

from qgis.core import QgsProject
from qgis.PyQt.QtCore import Qt
from qgis.PyQt.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QSpinBox,
    QVBoxLayout,
)

from . import geoprocessing, places_model, storage, utils
from .widgets import CrsRow, StyleTab

DEFAULT_SEGMENTS = 5


class BufferDialog(QDialog):
    def __init__(self, iface, layers, parent=None):
        """layers: lista de QgsVectorLayer (lugares do plugin), já
        filtrada para conter só camadas válidas com 1 feição cada - ver
        layeractions._on_buffer()."""
        super(BufferDialog, self).__init__(parent)
        self.iface = iface
        self.layers = layers

        self.setWindowTitle("GeoSketch - Gerar Buffer")
        self.setWindowFlags(self.windowFlags() | Qt.WindowStaysOnTopHint)
        self.setModal(True)
        self.setMinimumWidth(480)

        layout = QVBoxLayout(self)

        nomes = ", ".join(layer.name() for layer in self.layers)
        origem = QLabel("Buffer de: {}".format(nomes))
        origem.setWordWrap(True)
        origem.setStyleSheet("font-weight: bold;")
        layout.addWidget(origem)

        form = QFormLayout()
        self.name_edit = QLineEdit(self._default_name())
        form.addRow("Nome:", self.name_edit)

        dist_row = QHBoxLayout()
        self.distance_spin = QDoubleSpinBox()
        self.distance_spin.setRange(-1_000_000.0, 1_000_000.0)
        self.distance_spin.setDecimals(2)
        self.distance_spin.setValue(10.0)
        self.distance_spin.setToolTip(
            "Negativo encolhe o polígono para dentro (Buffer negativo) - só faz "
            "sentido geometricamente para polígonos."
        )
        dist_row.addWidget(self.distance_spin)
        self.distance_unit = QComboBox()
        self.distance_unit.addItems([name for name, _ in utils.LENGTH_UNITS])
        index = self.distance_unit.findText(utils.DEFAULT_LENGTH)
        if index >= 0:
            self.distance_unit.setCurrentIndex(index)
        dist_row.addWidget(self.distance_unit)
        form.addRow("Distância:", dist_row)

        self.segments_spin = QSpinBox()
        self.segments_spin.setRange(1, 100)
        self.segments_spin.setValue(DEFAULT_SEGMENTS)
        self.segments_spin.setToolTip(
            "Número de segmentos usados para aproximar curvas - mais segmentos "
            "deixam o contorno mais suave, com mais vértices."
        )
        form.addRow("Número de segmentos:", self.segments_spin)
        layout.addLayout(form)

        project_crs = QgsProject.instance().crs()
        self.processing_crs_row = CrsRow(project_crs, label="SRC de processamento:")
        self.processing_crs_row.selector.setToolTip(
            "Tem que ser um SRC PROJETADO (em metros) - o Buffer é calculado neste SRC."
        )
        layout.addWidget(self.processing_crs_row)
        self.output_crs_row = CrsRow(project_crs, label="SRC de saída:")
        layout.addWidget(self.output_crs_row)

        self.dissolve_check = QCheckBox("Dissolver resultados numa única geometria")
        self.dissolve_check.setChecked(True)
        if len(self.layers) < 2:
            self.dissolve_check.setChecked(False)
            self.dissolve_check.setEnabled(False)
            self.dissolve_check.setToolTip(
                "Só tem efeito com 2 ou mais lugares selecionados - com 1 só, não há "
                "o que dissolver."
            )
        layout.addWidget(self.dissolve_check)

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
        buttons.button(QDialogButtonBox.Ok).setText("Gerar Buffer")
        buttons.button(QDialogButtonBox.Cancel).setText("Cancelar")
        buttons.accepted.connect(self._run)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _default_name(self):
        if len(self.layers) == 1:
            return "Buffer de {}".format(self.layers[0].name())
        return "Buffer de {} lugares".format(len(self.layers))

    def _run(self):
        distance_m = utils.to_meters(self.distance_spin.value(), self.distance_unit.currentText())
        segments = self.segments_spin.value()
        processing_crs = self.processing_crs_row.crs()
        output_crs = self.output_crs_row.crs()
        dissolve = self.dissolve_check.isChecked()

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

        if not inputs:
            QMessageBox.warning(self, "GeoSketch", "Nenhuma geometria válida para o Buffer.")
            return

        try:
            results = geoprocessing.run_buffer(
                inputs, distance_m, segments, dissolve, processing_crs
            )
        except geoprocessing.GeoprocessingError as exc:
            QMessageBox.critical(self, "GeoSketch", str(exc))
            return
        except Exception as exc:
            utils.log("Buffer falhou de forma inesperada: {}".format(exc), "critical")
            QMessageBox.critical(
                self, "GeoSketch", "Erro inesperado no Buffer:\n{}".format(exc)
            )
            return

        name = self.name_edit.text().strip() or self._default_name()
        attributes = {
            "cor_linha": self.style_tab.line_color_string(),
            "cor_preenchimento": self.style_tab.fill_color_string(),
            "largura_linha": self.style_tab.line_width_value(),
        }
        folder_id = self.folder_combo.currentData()

        created = []
        try:
            for i, geom in enumerate(results):
                if output_crs != processing_crs:
                    geom = geoprocessing.reproject(geom, processing_crs, output_crs)
                display_name = name if len(results) == 1 else "{} ({})".format(name, i + 1)
                layer = storage.create_place(
                    "polygon", display_name, geom, attributes, crs=output_crs
                )
                tabela = storage.table_name(layer)
                if tabela and folder_id:
                    places_model.set_place_folder(tabela, folder_id)
                created.append(layer)
        except Exception as exc:
            utils.log("Falha ao gravar resultado do Buffer: {}".format(exc), "critical")
            QMessageBox.critical(
                self, "GeoSketch",
                "O Buffer foi calculado, mas não foi possível gravar o resultado:\n{}".format(exc),
            )
            return

        if folder_id:
            places_model.rebuild_layer_tree(self.iface)

        self.iface.messageBar().pushSuccess(
            "GeoSketch",
            "Buffer gerado: {} camada(s) criada(s).".format(len(created)),
        )
        self.accept()

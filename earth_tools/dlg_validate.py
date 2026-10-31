# -*- coding: utf-8 -*-
"""Janela "Validar geometrias..." (Fase G1): examina as geometrias reais
dos lugares do plugin e lista os problemas encontrados, com opção de
localizar no mapa e de corrigir numa CÓPIA nova (nunca sobrescreve o
original) quando a correção automática for segura.
"""

from qgis.core import QgsCoordinateTransform, QgsProject
from qgis.PyQt.QtCore import Qt
from qgis.PyQt.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QDialog,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMessageBox,
    QPushButton,
    QRadioButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
)

from . import geometry_validator, storage, utils

KIND_LABEL = {
    geometry_validator.EMPTY: "Geometria vazia",
    geometry_validator.INVALID: "Geometria inválida",
    geometry_validator.DUPLICATE_VERTEX: "Vértices duplicados",
    geometry_validator.UNCLOSED_RING: "Anel não fechado",
    geometry_validator.OUT_OF_BOUNDS: "Fora dos limites",
    geometry_validator.OVERLAP: "Sobreposição",
}

# Correção automática (makeValid) só é oferecida para estes tipos - os
# demais exigem decisão humana (ex.: sobreposição entre dois lugares
# distintos não tem "o certo" óbvio para corrigir automaticamente).
AUTO_FIXABLE = {geometry_validator.INVALID}


class ValidateDialog(QDialog):
    def __init__(self, iface, selected_layers, parent=None):
        super(ValidateDialog, self).__init__(parent)
        self.iface = iface
        self.selected_layers = selected_layers
        self._issues = []

        self.setWindowTitle("GeoSketch - Validar geometrias")
        self.setModal(False)
        self.setMinimumSize(640, 440)

        layout = QVBoxLayout(self)

        scope_row = QHBoxLayout()
        self.radio_selected = QRadioButton(
            "Lugares selecionados no painel Camadas ({})".format(len(self.selected_layers))
        )
        self.radio_all = QRadioButton("Todos os lugares do projeto")
        self.radio_all.setChecked(not self.selected_layers)
        self.radio_selected.setChecked(bool(self.selected_layers))
        self.radio_selected.setEnabled(bool(self.selected_layers))
        scope_row.addWidget(self.radio_selected)
        scope_row.addWidget(self.radio_all)
        layout.addLayout(scope_row)

        self.check_overlaps = QCheckBox("Verificar sobreposições entre polígonos")
        self.check_overlaps.setToolTip(
            "Compara cada par de polígonos - pode ser lento com muitos lugares."
        )
        layout.addWidget(self.check_overlaps)

        self.check_bounds = QCheckBox("Verificar se está dentro da extensão atual do mapa")
        self.check_bounds.setToolTip(
            "Usa a área visível no mapa agora como referência - desmarcado, esta "
            "checagem não é feita (não há referência definida por padrão)."
        )
        layout.addWidget(self.check_bounds)

        self.summary = QLabel("Clique em Verificar para examinar as geometrias.")
        layout.addWidget(self.summary)

        self.table = QTableWidget(0, 3)
        self.table.setHorizontalHeaderLabels(["Lugar", "Problema", "Mensagem"])
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.Stretch)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.cellDoubleClicked.connect(self._goto_selected)
        layout.addWidget(self.table)

        footer = QHBoxLayout()
        self.btn_run = QPushButton("Verificar")
        self.btn_goto = QPushButton("Localizar no mapa")
        self.btn_fix = QPushButton("Corrigir (criar cópia)...")
        self.btn_close = QPushButton("Fechar")
        footer.addWidget(self.btn_run)
        footer.addWidget(self.btn_goto)
        footer.addWidget(self.btn_fix)
        footer.addStretch()
        footer.addWidget(self.btn_close)
        layout.addLayout(footer)

        self.btn_run.clicked.connect(self._run)
        self.btn_goto.clicked.connect(self._goto_selected)
        self.btn_fix.clicked.connect(self._fix_selected)
        self.btn_close.clicked.connect(self.close)

    # -------------------------------------------------------------- escopo
    def _layers_to_check(self):
        if self.radio_selected.isChecked() and self.selected_layers:
            return self.selected_layers
        return [
            layer for layer in QgsProject.instance().mapLayers().values()
            if storage.is_place_layer(layer)
        ]

    # -------------------------------------------------------------- rodar
    def _run(self):
        layers = self._layers_to_check()
        if not layers:
            QMessageBox.information(
                self, "GeoSketch", "Não há lugares do plugin para verificar."
            )
            return
        reference_extent = None
        if self.check_bounds.isChecked():
            canvas = self.iface.mapCanvas()
            canvas_crs = canvas.mapSettings().destinationCrs()
            # geometry_validator.validate_layers() exige o extent de
            # referencia em WGS84 (transforma cada geometria para WGS84
            # antes de comparar, ja que lugares podem estar em SRC
            # diferentes entre si) - transforma aqui, antes de chamar.
            if canvas_crs != geometry_validator.WGS84:
                transform = QgsCoordinateTransform(
                    canvas_crs, geometry_validator.WGS84, QgsProject.instance()
                )
                reference_extent = transform.transformBoundingBox(canvas.extent())
            else:
                reference_extent = canvas.extent()
        issues, total, validos = geometry_validator.validate_layers(
            layers, reference_extent=reference_extent, check_overlaps=self.check_overlaps.isChecked()
        )
        self._issues = issues
        self.summary.setText(
            "{} geometria(s) verificada(s), {} válida(s), {} problema(s) encontrado(s).".format(
                total, validos, len(issues)
            )
        )
        self.table.setRowCount(len(issues))
        for row, issue in enumerate(issues):
            self.table.setItem(row, 0, QTableWidgetItem(issue.layer_name))
            self.table.setItem(row, 1, QTableWidgetItem(KIND_LABEL.get(issue.kind, issue.kind)))
            self.table.setItem(row, 2, QTableWidgetItem(issue.message))
        utils.log(
            "Validador de geometrias: {} verificadas, {} validas, {} problemas.".format(
                total, validos, len(issues)
            ),
            "info",
        )

    # --------------------------------------------------------- localizar
    def _current_issue(self):
        row = self.table.currentRow()
        if row < 0 or row >= len(self._issues):
            return None
        return self._issues[row]

    def _goto_selected(self, *_args):
        issue = self._current_issue()
        if issue is None:
            return
        layer = QgsProject.instance().mapLayer(issue.layer_id)
        if layer is not None:
            utils.zoom_to_layer(self.iface, layer)

    # ----------------------------------------------------------- corrigir
    def _fix_selected(self):
        issue = self._current_issue()
        if issue is None:
            QMessageBox.information(self, "GeoSketch", "Selecione um problema na lista.")
            return
        if issue.kind not in AUTO_FIXABLE:
            QMessageBox.information(
                self, "GeoSketch",
                "Não há correção automática segura para este tipo de problema "
                "(\"{}\") - é preciso decidir manualmente.".format(
                    KIND_LABEL.get(issue.kind, issue.kind)
                ),
            )
            return
        layer = QgsProject.instance().mapLayer(issue.layer_id)
        if layer is None:
            QMessageBox.warning(self, "GeoSketch", "O lugar original não está mais no projeto.")
            return
        features = list(layer.getFeatures())
        if not features:
            return
        original_geom = features[0].geometry()
        corrigida = geometry_validator.make_valid_copy(original_geom)
        if corrigida is None:
            QMessageBox.warning(
                self, "GeoSketch",
                "A correção automática não produziu uma geometria válida - esta geometria "
                "precisa ser corrigida manualmente.",
            )
            return

        resposta = QMessageBox.question(
            self, "GeoSketch",
            'Criar uma CÓPIA corrigida de "{}"? O lugar original NÃO será alterado nem '
            "apagado.".format(layer.name()),
            QMessageBox.Yes | QMessageBox.No,
        )
        if resposta != QMessageBox.Yes:
            return

        kind = layer.customProperty(storage.CUSTOM_KEY) or "polygon"
        estilo = storage.get_style(layer)
        try:
            nova = storage.create_place(
                kind, "{} (corrigido)".format(layer.name()), corrigida, estilo
            )
        except Exception as exc:
            utils.log("Falha ao gravar copia corrigida: {}".format(exc), "critical")
            QMessageBox.critical(
                self, "GeoSketch", "Não foi possível gravar a cópia corrigida:\n{}".format(exc)
            )
            return

        utils.log(
            'Validador de geometrias: criada copia corrigida "{}" a partir de "{}" '
            "(original preservado).".format(nova.name(), layer.name()),
            "info",
        )
        self.iface.messageBar().pushSuccess(
            "GeoSketch",
            'Cópia corrigida "{}" criada. O original foi preservado.'.format(nova.name()),
        )
        self._run()

# -*- coding: utf-8 -*-
"""Janela "Calculadora de área e distância" (Etapa 2): consulta a
área/perímetro/comprimento de um lugar JÁ SALVO, sem precisar abrir
"Editar...". Complementa a medição ao vivo que já existe em Novo/Editar/
Régua - aqui o uso é "escolher um lugar existente e ler o valor", com
opção de copiar o resultado.
"""

from qgis.core import QgsProject
from qgis.PyQt.QtCore import Qt
from qgis.PyQt.QtWidgets import (
    QApplication,
    QComboBox,
    QDialog,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
)

from . import storage, utils
from .widgets import UnitRow

KIND_LABEL = {"point": "Marcador", "line": "Caminho", "polygon": "Polígono"}


class CalculatorDialog(QDialog):
    def __init__(self, iface, parent=None, initial_layer=None):
        super(CalculatorDialog, self).__init__(parent)
        self.iface = iface
        self._current_layer = None
        # Pré-seleção vinda do menu de contexto/painel de propriedades
        # (um lugar específico) - consumida uma única vez por
        # _reload_layers(), que depois volta a só preservar a seleção
        # atual do combo como sempre fez.
        self._pending_initial_id = initial_layer.id() if initial_layer is not None else None

        self.setWindowTitle("GeoSketch - Calculadora de área e distância")
        self.setWindowFlags(self.windowFlags() | Qt.WindowStaysOnTopHint)
        self.setModal(False)
        self.setMinimumWidth(460)

        layout = QVBoxLayout(self)

        pick_row = QHBoxLayout()
        pick_row.addWidget(QLabel("Lugar:"))
        self.layer_combo = QComboBox()
        pick_row.addWidget(self.layer_combo)
        self.btn_refresh_list = QPushButton("Atualizar lista")
        pick_row.addWidget(self.btn_refresh_list)
        layout.addLayout(pick_row)

        self.kind_label = QLabel("")
        self.kind_label.setStyleSheet("color: #555; font-style: italic;")
        layout.addWidget(self.kind_label)

        self.perimeter_row = UnitRow("Perímetro:", utils.LENGTH_UNITS, utils.DEFAULT_LENGTH)
        self.area_row = UnitRow("Área:", utils.AREA_UNITS, utils.DEFAULT_AREA)
        self.length_row = UnitRow("Comprimento:", utils.LENGTH_UNITS, utils.DEFAULT_LENGTH)
        for row in (self.perimeter_row, self.area_row, self.length_row):
            layout.addWidget(row)
            row.unitChanged.connect(self._refresh_values)

        footer = QHBoxLayout()
        self.btn_copy = QPushButton("Copiar resultado")
        self.btn_close = QPushButton("Fechar")
        footer.addWidget(self.btn_copy)
        footer.addStretch()
        footer.addWidget(self.btn_close)
        layout.addLayout(footer)

        self.layer_combo.currentIndexChanged.connect(self._layer_changed)
        self.btn_refresh_list.clicked.connect(self._reload_layers)
        self.btn_copy.clicked.connect(self._copy_result)
        self.btn_close.clicked.connect(self.close)

        self._reload_layers()

    # ------------------------------------------------------------- lugares
    def _reload_layers(self):
        if self._pending_initial_id is not None:
            atual_id = self._pending_initial_id
            self._pending_initial_id = None
        else:
            atual_id = self.layer_combo.currentData()
        self.layer_combo.blockSignals(True)
        self.layer_combo.clear()
        layers = [
            layer for layer in QgsProject.instance().mapLayers().values()
            if storage.is_place_layer(layer)
        ]
        layers.sort(key=lambda l: l.name().lower())
        for layer in layers:
            self.layer_combo.addItem(layer.name(), layer.id())
        index = self.layer_combo.findData(atual_id)
        self.layer_combo.setCurrentIndex(index if index >= 0 else (0 if layers else -1))
        self.layer_combo.blockSignals(False)
        self._layer_changed()

    def _layer_changed(self, *_args):
        layer_id = self.layer_combo.currentData()
        self._current_layer = QgsProject.instance().mapLayer(layer_id) if layer_id else None
        self._refresh_values()

    # ------------------------------------------------------------- calculo
    def _refresh_values(self):
        for row in (self.perimeter_row, self.area_row, self.length_row):
            row.setVisible(False)
            row.setValue("0,00")
        # Estado explicito de quais linhas tem valor valido para o lugar
        # atual - NAO usar QWidget.isVisible() pra isso: reflete a
        # visibilidade real na tela (depende de .show() já ter rodado na
        # janela-mae), nao a relevancia semantica do campo para este tipo
        # de lugar. _copy_result() e os testes usam este atributo, nunca
        # isVisible().
        self._active_rows = set()

        if self._current_layer is None:
            self.kind_label.setText("Nenhum lugar no projeto ainda.")
            return

        layer = self._current_layer
        kind = layer.customProperty(storage.CUSTOM_KEY) or ""
        self.kind_label.setText(KIND_LABEL.get(kind, kind or "?"))

        features = list(layer.getFeatures())
        if not features:
            self.kind_label.setText(self.kind_label.text() + " - sem geometria.")
            return
        # Le a geometria ATUAL da camada agora - se o lugar foi editado
        # desde a ultima vez que esta janela foi aberta, o valor mostrado
        # já reflete a edição (não é um valor congelado), mas também não
        # é "ao vivo": não há aviso automático se a geometria mudar
        # enquanto esta janela está aberta - clique no lugar na lista de
        # novo (ou "Atualizar lista") para reler.
        geometry = features[0].geometry()
        crs = layer.crs()

        if kind == "polygon":
            self.perimeter_row.setVisible(True)
            self.area_row.setVisible(True)
            self._active_rows = {"perimeter", "area"}
            perimetro = utils.measure_perimeter_geometry(geometry, crs)
            area = utils.measure_area_geometry(geometry, crs)
            self.perimeter_row.setValue(
                utils.format_number(utils.convert_length(perimetro, self.perimeter_row.unit()))
            )
            self.area_row.setValue(
                utils.format_number(utils.convert_area(area, self.area_row.unit()))
            )
        elif kind == "line":
            self.length_row.setVisible(True)
            self._active_rows = {"length"}
            comprimento = utils.measure_length_geometry(geometry, crs)
            self.length_row.setValue(
                utils.format_number(utils.convert_length(comprimento, self.length_row.unit()))
            )
        else:
            self.kind_label.setText(
                self.kind_label.text() + " - marcador não tem área nem comprimento."
            )

    # --------------------------------------------------------------- copiar
    def _copy_result(self):
        if self._current_layer is None:
            return
        linhas = ["Lugar: {}".format(self._current_layer.name())]
        if "perimeter" in self._active_rows:
            linhas.append(
                "Perímetro: {} {}".format(self.perimeter_row.value.text(), self.perimeter_row.unit())
            )
        if "area" in self._active_rows:
            linhas.append(
                "Área: {} {}".format(self.area_row.value.text(), self.area_row.unit())
            )
        if "length" in self._active_rows:
            linhas.append(
                "Comprimento: {} {}".format(self.length_row.value.text(), self.length_row.unit())
            )
        QApplication.clipboard().setText("\n".join(linhas))
        self.iface.messageBar().pushSuccess("GeoSketch", "Resultado copiado.")

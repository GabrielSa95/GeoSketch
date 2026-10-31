# -*- coding: utf-8 -*-
"""Painel lateral "Propriedades da Geometria" (GeoSketch).

Mostra, para o lugar selecionado no painel Camadas, nome, tipo, área,
perímetro/comprimento, SRC e situação da validação - sempre lidos da
geometria REAL da camada no momento da exibição (mesmas funções de
medição de dlg_calculator.py/dlg_export_map.py), nunca um valor congelado
ou fictício. Atualiza ao trocar a seleção no painel Camadas e quando a
própria camada é editada/estilizada (sinais nativos do QGIS), sem
polling. Os botões de ação delegam para o código já existente em
earth_tools.py/layeractions.py - este painel não duplica nenhuma lógica
de cálculo, estilo, validação ou exportação.
"""

from qgis.core import QgsProject
from qgis.PyQt.QtWidgets import (
    QDockWidget,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from . import geometry_validator, storage, utils

KIND_LABEL = {"point": "Marcador", "line": "Caminho", "polygon": "Polígono"}

# Sinais do QgsVectorLayer que indicam que o conteúdo mostrado pode ter
# ficado desatualizado - cobre edição de geometria (commitChanges/
# editingStopped), estilo (Estilo..., Gerenciador de Estilos) e
# renomeação. Conectados/desconectados de forma best-effort (alguns
# podem não existir em todas as versões do QGIS 3.22+).
_LAYER_SIGNALS = ("committedGeometriesChanges", "editingStopped", "styleChanged", "nameChanged")


class PropertiesPanel(QDockWidget):
    def __init__(self, iface, plugin, parent=None):
        super(PropertiesPanel, self).__init__("GeoSketch - Propriedades", parent)
        self.setObjectName("FerramentasTerraPropriedades")
        self.iface = iface
        self.plugin = plugin
        self._layer = None

        body = QWidget()
        layout = QVBoxLayout(body)

        form = QFormLayout()
        self.name_label = QLabel("-")
        self.kind_label = QLabel("-")
        self.area_label = QLabel("-")
        self.perimeter_label = QLabel("-")
        self.length_label = QLabel("-")
        self.crs_label = QLabel("-")
        self.validation_label = QLabel("-")
        for label, value in (
            ("Nome:", self.name_label),
            ("Tipo:", self.kind_label),
            ("Área:", self.area_label),
            ("Perímetro:", self.perimeter_label),
            ("Comprimento:", self.length_label),
            ("SRC:", self.crs_label),
            ("Validação:", self.validation_label),
        ):
            value.setWordWrap(True)
            form.addRow(label, value)
        layout.addLayout(form)

        self.hint = QLabel("Selecione um lugar criado pelo GeoSketch no painel Camadas.")
        self.hint.setWordWrap(True)
        self.hint.setStyleSheet("color: #555; font-style: italic;")
        layout.addWidget(self.hint)

        buttons = QHBoxLayout()
        self.btn_calculate = QPushButton("Calcular medidas")
        self.btn_style = QPushButton("Alterar estilo...")
        self.btn_validate = QPushButton("Validar geometria...")
        self.btn_export = QPushButton("Exportar geometria...")
        for btn in (self.btn_calculate, self.btn_style, self.btn_validate, self.btn_export):
            buttons.addWidget(btn)
        layout.addLayout(buttons)
        layout.addStretch()

        self.setWidget(body)

        self.btn_calculate.clicked.connect(self._on_calculate)
        self.btn_style.clicked.connect(self._on_style)
        self.btn_validate.clicked.connect(self._on_validate)
        self.btn_export.clicked.connect(self._on_export)

        self._connect_project_signals()
        self._set_layer(self._read_current_layer())

    # -------------------------------------------------------- selecao/sinais
    def _read_current_layer(self):
        try:
            return self.iface.layerTreeView().currentLayer()
        except Exception:
            return None

    def _connect_project_signals(self):
        try:
            self.iface.layerTreeView().currentLayerChanged.connect(self._on_current_layer_changed)
        except Exception:
            pass
        try:
            QgsProject.instance().layersWillBeRemoved.connect(self._on_layers_removed)
        except Exception:
            pass

    def disconnect_all(self):
        """Chamado por EarthTools.unload() - desliga os sinais do projeto
        e da camada atualmente exibida antes do painel ser destruído."""
        try:
            self.iface.layerTreeView().currentLayerChanged.disconnect(self._on_current_layer_changed)
        except Exception:
            pass
        try:
            QgsProject.instance().layersWillBeRemoved.disconnect(self._on_layers_removed)
        except Exception:
            pass
        self._disconnect_layer_signals()

    def _on_current_layer_changed(self, layer):
        self._set_layer(layer)

    def _on_layers_removed(self, layer_ids):
        if self._layer is not None and self._layer.id() in layer_ids:
            self._set_layer(None)

    def _set_layer(self, layer):
        self._disconnect_layer_signals()
        self._layer = layer if (layer is not None and storage.is_place_layer(layer)) else None
        if self._layer is not None:
            self._connect_layer_signals(self._layer)
        self._refresh()

    def _connect_layer_signals(self, layer):
        for signal_name in _LAYER_SIGNALS:
            signal = getattr(layer, signal_name, None)
            if signal is None:
                continue
            try:
                signal.connect(self._refresh)
            except Exception:
                pass

    def _disconnect_layer_signals(self):
        if self._layer is None:
            return
        for signal_name in _LAYER_SIGNALS:
            signal = getattr(self._layer, signal_name, None)
            if signal is None:
                continue
            try:
                signal.disconnect(self._refresh)
            except Exception:
                pass

    # ------------------------------------------------------------- calculo
    def _refresh(self, *_args):
        layer = self._layer
        has_layer = layer is not None
        for btn in (self.btn_calculate, self.btn_style, self.btn_validate, self.btn_export):
            btn.setEnabled(has_layer)
        self.hint.setVisible(not has_layer)

        if not has_layer:
            for value in (
                self.name_label, self.kind_label, self.area_label,
                self.perimeter_label, self.length_label, self.crs_label,
                self.validation_label,
            ):
                value.setText("-")
            return

        self.name_label.setText(layer.name())
        kind = layer.customProperty(storage.CUSTOM_KEY) or ""
        self.kind_label.setText(KIND_LABEL.get(kind, kind or "?"))
        crs = layer.crs()
        self.crs_label.setText("{} - {}".format(crs.authid(), crs.description()))

        self.area_label.setText("-")
        self.perimeter_label.setText("-")
        self.length_label.setText("-")

        features = list(layer.getFeatures())
        if not features:
            self.validation_label.setText("Sem geometria.")
            return

        geometry = features[0].geometry()
        if kind == "polygon":
            area = utils.measure_area_geometry(geometry, crs)
            perimetro = utils.measure_perimeter_geometry(geometry, crs)
            self.area_label.setText(
                "{} ha".format(utils.format_number(utils.convert_area(area, "Hectares")))
            )
            self.perimeter_label.setText("{} m".format(utils.format_number(perimetro)))
        elif kind == "line":
            comprimento = utils.measure_length_geometry(geometry, crs)
            self.length_label.setText("{} m".format(utils.format_number(comprimento)))

        try:
            issues, _total, _validas = geometry_validator.validate_layers([layer])
            self.validation_label.setText("OK" if not issues else "{} problema(s) encontrado(s)".format(len(issues)))
        except Exception:
            self.validation_label.setText("Não verificado")

    # -------------------------------------------------------------- acoes
    # Cada botão delega para o código já existente (earth_tools.py/
    # layeractions.py) sobre a camada atual - nenhuma lógica nova de
    # cálculo/estilo/validação/exportação é criada aqui.
    def _on_calculate(self):
        if self._layer is not None:
            self.plugin.open_calculator_for(self._layer)

    def _on_style(self):
        if self._layer is not None and self.plugin._layer_actions is not None:
            self.plugin._layer_actions._on_style()

    def _on_validate(self):
        if self._layer is not None:
            self.plugin._open_validate()

    def _on_export(self):
        if self._layer is not None and self.plugin._layer_actions is not None:
            self.plugin._layer_actions._save_as_layer(self._layer)

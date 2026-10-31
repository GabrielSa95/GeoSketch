# -*- coding: utf-8 -*-
"""Janela "Estilo..." (Fase H): edita o estilo de um ou mais lugares
selecionados, com biblioteca de presets nomeados salvos/reutilizáveis
entre projetos (QSettings - por usuário, não por projeto).
"""

from qgis.PyQt.QtCore import QSettings
from qgis.PyQt.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
)

from . import storage, utils
from .widgets import StyleTab

SETTINGS_GROUP = "FerramentasTerra/EstilosSalvos"


def _settings():
    return QSettings()


def list_presets():
    """Nomes dos presets salvos, em ordem alfabética."""
    settings = _settings()
    settings.beginGroup(SETTINGS_GROUP)
    nomes = sorted(settings.childGroups())
    settings.endGroup()
    return nomes


def save_preset(nome, cor_linha, cor_preenchimento, largura_linha):
    settings = _settings()
    settings.beginGroup("{}/{}".format(SETTINGS_GROUP, nome))
    settings.setValue("cor_linha", cor_linha)
    settings.setValue("cor_preenchimento", cor_preenchimento)
    settings.setValue("largura_linha", largura_linha)
    settings.endGroup()


def load_preset(nome):
    settings = _settings()
    settings.beginGroup("{}/{}".format(SETTINGS_GROUP, nome))
    try:
        cor_linha = settings.value("cor_linha", "255,255,0,255")
        cor_preenchimento = settings.value("cor_preenchimento", "255,255,255,90")
        largura_linha = float(settings.value("largura_linha", 1.0))
    finally:
        settings.endGroup()
    return cor_linha, cor_preenchimento, largura_linha


def delete_preset(nome):
    settings = _settings()
    settings.remove("{}/{}".format(SETTINGS_GROUP, nome))


class StyleManagerDialog(QDialog):
    def __init__(self, iface, layers, parent=None):
        """layers: 1+ QgsVectorLayer (lugares do plugin) - o estilo
        exibido inicialmente é o da PRIMEIRA camada; "Aplicar" grava em
        TODAS as camadas selecionadas, sem tocar na geometria de nenhuma."""
        super(StyleManagerDialog, self).__init__(parent)
        self.iface = iface
        self.layers = layers

        self.setWindowTitle("GeoSketch - Estilo")
        self.setModal(True)
        self.setMinimumWidth(460)

        layout = QVBoxLayout(self)

        nomes = ", ".join(layer.name() for layer in self.layers)
        header = QLabel("Estilo de: {}".format(nomes))
        header.setWordWrap(True)
        header.setStyleSheet("font-weight: bold;")
        layout.addWidget(header)

        kinds = {layer.customProperty(storage.CUSTOM_KEY) for layer in self.layers}
        self._mixed_kinds = len(kinds) > 1
        primary_kind = self.layers[0].customProperty(storage.CUSTOM_KEY) or "polygon"
        self.style_tab = StyleTab(
            with_fill=(primary_kind in ("point", "polygon") and not self._mixed_kinds),
            with_width=(primary_kind in ("line", "polygon") and not self._mixed_kinds),
        )
        if self._mixed_kinds:
            # Selecao com tipos diferentes (ex.: caminho + poligono): usa a
            # aba mais completa (preenchimento + largura) em vez de
            # adivinhar por um tipo so - cada camada so recebe os campos
            # que fazem sentido para o SEU tipo na hora de aplicar.
            self.style_tab = StyleTab(with_fill=True, with_width=True)
        existing = storage.get_style(self.layers[0])
        self.style_tab.load_values(
            existing["cor_linha"], existing["cor_preenchimento"], existing["largura_linha"]
        )
        layout.addWidget(self.style_tab)

        preset_row = QHBoxLayout()
        preset_row.addWidget(QLabel("Preset salvo:"))
        self.preset_combo = QComboBox()
        self.preset_combo.addItem("(nenhum)", None)
        for nome in list_presets():
            self.preset_combo.addItem(nome, nome)
        preset_row.addWidget(self.preset_combo)
        self.btn_load_preset = QPushButton("Carregar")
        self.btn_save_preset = QPushButton("Salvar como...")
        self.btn_delete_preset = QPushButton("Excluir")
        preset_row.addWidget(self.btn_load_preset)
        preset_row.addWidget(self.btn_save_preset)
        preset_row.addWidget(self.btn_delete_preset)
        layout.addLayout(preset_row)

        self.btn_load_preset.clicked.connect(self._load_preset)
        self.btn_save_preset.clicked.connect(self._save_preset)
        self.btn_delete_preset.clicked.connect(self._delete_preset)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.button(QDialogButtonBox.Ok).setText("Aplicar")
        buttons.button(QDialogButtonBox.Cancel).setText("Cancelar")
        buttons.accepted.connect(self._apply)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    # ------------------------------------------------------------ presets
    def _load_preset(self):
        nome = self.preset_combo.currentData()
        if not nome:
            return
        cor_linha, cor_preenchimento, largura_linha = load_preset(nome)
        self.style_tab.load_values(cor_linha, cor_preenchimento, largura_linha)

    def _save_preset(self):
        nome, ok = QInputDialog.getText(self, "Salvar preset", "Nome do preset:")
        nome = (nome or "").strip()
        if not ok or not nome:
            return
        save_preset(
            nome,
            self.style_tab.line_color_string(),
            self.style_tab.fill_color_string(),
            self.style_tab.line_width_value(),
        )
        if self.preset_combo.findData(nome) < 0:
            self.preset_combo.addItem(nome, nome)
        self.iface.messageBar().pushSuccess(
            "GeoSketch", 'Preset "{}" salvo - disponível em outros projetos também.'.format(nome)
        )

    def _delete_preset(self):
        nome = self.preset_combo.currentData()
        if not nome:
            return
        delete_preset(nome)
        index = self.preset_combo.currentIndex()
        self.preset_combo.removeItem(index)

    # -------------------------------------------------------------- aplicar
    def _apply(self):
        cor_linha = self.style_tab.line_color_string()
        cor_preenchimento = self.style_tab.fill_color_string()
        largura_linha = self.style_tab.line_width_value()

        falhas = []
        for layer in self.layers:
            kind = layer.customProperty(storage.CUSTOM_KEY) or "polygon"
            try:
                storage.set_style(layer, kind, cor_linha, cor_preenchimento, largura_linha)
                layer.triggerRepaint()
            except Exception as exc:
                utils.log(
                    "Falha ao aplicar estilo em '{}': {}".format(layer.name(), exc), "warning"
                )
                falhas.append(layer.name())

        if falhas:
            QMessageBox.warning(
                self, "GeoSketch",
                "Não foi possível aplicar o estilo em: {}".format(", ".join(falhas)),
            )
        aplicados = len(self.layers) - len(falhas)
        if aplicados:
            self.iface.messageBar().pushSuccess(
                "GeoSketch", "Estilo aplicado em {} lugar(es).".format(aplicados)
            )
        self.accept()

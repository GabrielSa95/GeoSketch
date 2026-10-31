# -*- coding: utf-8 -*-
"""Widgets reutilizados pelas janelas, no mesmo layout do Google Earth."""

from qgis.core import QgsPointXY
from qgis.gui import QgsProjectionSelectionWidget
from qgis.PyQt.QtCore import Qt, pyqtSignal
from qgis.PyQt.QtGui import QColor
from qgis.PyQt.QtWidgets import (
    QCheckBox,
    QColorDialog,
    QComboBox,
    QDoubleSpinBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QSpinBox,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from . import utils


class ColorButton(QPushButton):
    """Botão quadrado que abre o seletor de cor, como o do Google Earth."""

    colorChanged = pyqtSignal(QColor)

    def __init__(self, color=QColor(255, 255, 0), parent=None):
        super(ColorButton, self).__init__(parent)
        self._color = QColor(color)
        self.setFixedSize(28, 22)
        self.clicked.connect(self._pick)
        self._paint()

    def _paint(self):
        self.setStyleSheet(
            "background-color: rgb({},{},{}); border: 1px solid #808080;".format(
                self._color.red(), self._color.green(), self._color.blue()
            )
        )

    def _pick(self):
        chosen = QColorDialog.getColor(self._color, self, "Escolher cor")
        if chosen.isValid():
            self._color = chosen
            self._paint()
            self.colorChanged.emit(chosen)

    def color(self):
        return QColor(self._color)

    def setColor(self, color):
        self._color = QColor(color)
        self._paint()
        self.colorChanged.emit(self._color)


class StyleTab(QWidget):
    """Aba Estilo/Cor: cor, largura e opacidade da linha e do preenchimento."""

    changed = pyqtSignal()

    def __init__(self, with_fill=True, with_width=True, parent=None):
        super(StyleTab, self).__init__(parent)
        self.with_fill = with_fill
        layout = QVBoxLayout(self)

        line_box = QGroupBox("Linhas")
        line_form = QHBoxLayout(line_box)
        line_form.addWidget(QLabel("Cor:"))
        self.line_color = ColorButton(QColor(255, 255, 0))
        line_form.addWidget(self.line_color)
        if with_width:
            line_form.addSpacing(12)
            line_form.addWidget(QLabel("Largura:"))
            self.line_width = QDoubleSpinBox()
            self.line_width.setRange(0.1, 20.0)
            self.line_width.setSingleStep(0.1)
            self.line_width.setValue(1.0)
            self.line_width.setDecimals(1)
            self.line_width.setFixedWidth(70)
            line_form.addWidget(self.line_width)
        else:
            self.line_width = None
        line_form.addSpacing(12)
        line_form.addWidget(QLabel("Opacidade:"))
        self.line_opacity = QSpinBox()
        self.line_opacity.setRange(0, 100)
        self.line_opacity.setValue(100)
        self.line_opacity.setSuffix("%")
        self.line_opacity.setFixedWidth(70)
        line_form.addWidget(self.line_opacity)
        line_form.addStretch()
        layout.addWidget(line_box)

        if with_fill:
            fill_box = QGroupBox("Área")
            fill_form = QHBoxLayout(fill_box)
            fill_form.addWidget(QLabel("Cor:"))
            self.fill_color = ColorButton(QColor(255, 255, 255))
            fill_form.addWidget(self.fill_color)
            fill_form.addSpacing(12)
            self.fill_mode = QComboBox()
            self.fill_mode.addItems(["Preenchido", "Circunscrito", "Preenchido + contorno"])
            self.fill_mode.setCurrentIndex(2)
            self.fill_mode.setFixedWidth(150)
            fill_form.addWidget(self.fill_mode)
            fill_form.addSpacing(12)
            fill_form.addWidget(QLabel("Opacidade:"))
            self.fill_opacity = QSpinBox()
            self.fill_opacity.setRange(0, 100)
            self.fill_opacity.setValue(35)
            self.fill_opacity.setSuffix("%")
            self.fill_opacity.setFixedWidth(70)
            fill_form.addWidget(self.fill_opacity)
            fill_form.addStretch()
            layout.addWidget(fill_box)
        else:
            self.fill_color = None
            self.fill_mode = None
            self.fill_opacity = None

        layout.addStretch()

        for widget in (self.line_color, self.fill_color):
            if widget is not None:
                widget.colorChanged.connect(self.changed)
        for widget in (self.line_width, self.line_opacity, self.fill_opacity):
            if widget is not None:
                widget.valueChanged.connect(self.changed)
        if self.fill_mode is not None:
            self.fill_mode.currentIndexChanged.connect(self.changed)

    # ------------------------------------------------------------ leitura
    def line_color_string(self):
        color = self.line_color.color()
        color.setAlpha(int(self.line_opacity.value() * 2.55))
        return utils.color_to_string(color)

    def fill_color_string(self):
        if self.fill_color is None:
            return "255,255,255,90"
        color = self.fill_color.color()
        alpha = self.fill_opacity.value()
        if self.fill_mode is not None and self.fill_mode.currentIndex() == 1:
            alpha = 0  # "Circunscrito" = só contorno
        color.setAlpha(int(alpha * 2.55))
        return utils.color_to_string(color)

    def line_width_value(self):
        return float(self.line_width.value()) if self.line_width else 1.0

    def load_values(self, line_color, fill_color, line_width):
        """Preenche a aba com o estilo atual de um lugar ja criado."""
        line = utils.string_to_color(line_color)
        self.line_color.setColor(QColor(line.red(), line.green(), line.blue()))
        self.line_opacity.setValue(int(round(line.alpha() / 2.55)))
        if self.line_width is not None:
            try:
                self.line_width.setValue(float(line_width))
            except (TypeError, ValueError):
                pass
        if self.fill_color is not None:
            fill = utils.string_to_color(fill_color, (255, 255, 255, 90))
            self.fill_color.setColor(QColor(fill.red(), fill.green(), fill.blue()))
            self.fill_opacity.setValue(int(round(fill.alpha() / 2.55)))
            if self.fill_mode is not None:
                self.fill_mode.setCurrentIndex(1 if fill.alpha() == 0 else 2)


class DescriptionTab(QWidget):
    """Aba Descrição, com os botões de inserir link e imagem."""

    def __init__(self, parent=None):
        super(DescriptionTab, self).__init__(parent)
        layout = QVBoxLayout(self)

        buttons = QHBoxLayout()
        self.btn_link = QPushButton("Adicionar link…")
        self.btn_web_image = QPushButton("Adicionar imagem da Web…")
        self.btn_local_image = QPushButton("Adicionar imagem local…")
        for btn in (self.btn_link, self.btn_web_image, self.btn_local_image):
            buttons.addWidget(btn)
        buttons.addStretch()
        layout.addLayout(buttons)

        self.editor = QPlainTextEdit()
        self.editor.setTabChangesFocus(True)
        layout.addWidget(self.editor)

        self.btn_link.clicked.connect(self._insert_link)
        self.btn_web_image.clicked.connect(self._insert_web_image)
        self.btn_local_image.clicked.connect(self._insert_local_image)

    def _insert_link(self):
        from qgis.PyQt.QtWidgets import QInputDialog

        url, ok = QInputDialog.getText(self, "Adicionar link", "Endereço (URL):")
        if ok and url:
            self.editor.insertPlainText('<a href="{0}">{0}</a>'.format(url))

    def _insert_web_image(self):
        from qgis.PyQt.QtWidgets import QInputDialog

        url, ok = QInputDialog.getText(self, "Imagem da Web", "Endereço da imagem:")
        if ok and url:
            self.editor.insertPlainText('<img src="{}" width="400"/>'.format(url))

    def _insert_local_image(self):
        from qgis.PyQt.QtWidgets import QFileDialog

        path, _ = QFileDialog.getOpenFileName(
            self, "Escolher imagem", "", "Imagens (*.png *.jpg *.jpeg *.gif *.bmp)"
        )
        if path:
            self.editor.insertPlainText('<img src="file:///{}" width="400"/>'.format(path))

    def text(self):
        return self.editor.toPlainText()

    def setText(self, value):
        self.editor.setPlainText(value or "")


class UnitRow(QWidget):
    """Linha 'rótulo .... valor [unidade]', igual às da Régua."""

    unitChanged = pyqtSignal()

    def __init__(self, label, units, default, parent=None):
        super(UnitRow, self).__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(QLabel(label))
        layout.addStretch()
        self.value = QLabel("0,00")
        self.value.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self.value.setMinimumWidth(140)
        layout.addWidget(self.value)
        self.combo = QComboBox()
        self.combo.addItems([name for name, _ in units])
        index = self.combo.findText(default)
        if index >= 0:
            self.combo.setCurrentIndex(index)
        self.combo.setMinimumWidth(190)
        layout.addWidget(self.combo)
        self.combo.currentIndexChanged.connect(self.unitChanged)

    def unit(self):
        return self.combo.currentText()

    def setValue(self, text):
        self.value.setText(text)


class CrsRow(QWidget):
    """Linha "SRC do caminho: [seletor nativo do QGIS]" (Fase 3).

    Usa QgsProjectionSelectionWidget - o mesmo seletor nativo das janelas de
    Processamento (ex.: parâmetro de SRC do Vetor Geral/Buffer), que já
    mostra o código EPSG e o nome do sistema escolhido no próprio botão, e
    abre o diálogo nativo de escolha de SRC ao clicar. Começa no SRC
    informado (o do projeto, por padrão - ver dlg_ruler.py).
    """

    crsChanged = pyqtSignal()

    def __init__(self, initial_crs, label="SRC do caminho:", parent=None):
        super(CrsRow, self).__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        row = QHBoxLayout()
        row.addWidget(QLabel(label))
        self.selector = QgsProjectionSelectionWidget()
        self.selector.setCrs(initial_crs)
        row.addWidget(self.selector)
        layout.addLayout(row)
        hint = QLabel(
            "Usado para salvar/exportar este caminho (ex.: para usar depois no "
            "Buffer). Não altera a unidade de medida mostrada acima - só o "
            "sistema de coordenadas em que a geometria é gravada."
        )
        hint.setWordWrap(True)
        hint.setStyleSheet("color: #555; font-style: italic;")
        layout.addWidget(hint)

        self.selector.crsChanged.connect(self.crsChanged)

    def crs(self):
        return self.selector.crs()

    def setCrs(self, crs):
        self.selector.setCrs(crs)


class SnapRow(QWidget):
    """Linha "Aderência: [x] | Tolerância: [N] px" (Fase C / C1).

    `bind(tool)` liga a um DrawTool ou VertexEditTool - ambos expõem
    set_snapping_enabled()/set_snap_tolerance() - aplicando o valor atual e
    mantendo sincronizado a cada mudança no checkbox/spin.
    """

    changed = pyqtSignal()

    def __init__(self, parent=None):
        super(SnapRow, self).__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self.checkbox = QCheckBox("Aderência a vértices/segmentos")
        self.checkbox.setChecked(True)
        self.checkbox.setToolTip(
            "Adere a vértices e trechos de qualquer camada do projeto ao "
            "clicar ou arrastar. Desative para posicionar livremente."
        )
        layout.addWidget(self.checkbox)
        layout.addSpacing(12)
        layout.addWidget(QLabel("Tolerância:"))
        self.tolerance_spin = QSpinBox()
        self.tolerance_spin.setRange(1, 100)
        self.tolerance_spin.setValue(12)
        self.tolerance_spin.setSuffix(" px")
        self.tolerance_spin.setToolTip(
            "Em pixels de tela, não em unidades do SRC do projeto - o "
            "comportamento não muda se o SRC for em graus ou em metros."
        )
        self.tolerance_spin.setFixedWidth(70)
        layout.addWidget(self.tolerance_spin)
        layout.addStretch()

        self.checkbox.toggled.connect(self.changed)
        self.tolerance_spin.valueChanged.connect(self.changed)

    def enabled(self):
        return self.checkbox.isChecked()

    def tolerance(self):
        return self.tolerance_spin.value()

    def bind(self, tool):
        tool.set_snapping_enabled(self.enabled())
        tool.set_snap_tolerance(self.tolerance())
        self.checkbox.toggled.connect(tool.set_snapping_enabled)
        self.tolerance_spin.valueChanged.connect(tool.set_snap_tolerance)


class VertexEntryPanel(QWidget):
    """Entrada numérica de vértice: distância+azimute OU coordenadas (Fase
    C / C2). Só para linha/polígono - marcador já tem campos de lat/lon
    próprios na janela de criação.

    Acrescenta o vértice no FINAL do desenho atual, chamando de volta
    `pointComputed` com um QgsPointXY já na CRS do canvas; quem conectar
    decide como aplicar (tool.add_vertex(), que passa pelo mesmo caminho de
    um clique real - undo, medidas, gravação).
    """

    pointComputed = pyqtSignal(object)

    def __init__(self, canvas, parent=None):
        super(VertexEntryPanel, self).__init__(parent)
        self.canvas = canvas
        self._last_point_getter = None

        layout = QVBoxLayout(self)
        hint = QLabel(
            "Acrescenta um vértice no final do desenho atual: pela distância e "
            "azimute a partir do último ponto, ou por coordenadas."
        )
        hint.setWordWrap(True)
        hint.setStyleSheet("color: #555; font-style: italic;")
        layout.addWidget(hint)

        self.mode_combo = QComboBox()
        self.mode_combo.addItems(["Distância e azimute", "Coordenadas (latitude/longitude)"])
        layout.addWidget(self.mode_combo)

        self.stack = QStackedWidget()

        page1 = QWidget()
        form1 = QFormLayout(page1)
        row = QHBoxLayout()
        self.distance_spin = QDoubleSpinBox()
        self.distance_spin.setRange(0.0, 1000000000.0)
        self.distance_spin.setDecimals(3)
        row.addWidget(self.distance_spin)
        self.distance_unit = QComboBox()
        self.distance_unit.addItems([name for name, _ in utils.LENGTH_UNITS])
        index = self.distance_unit.findText(utils.DEFAULT_LENGTH)
        if index >= 0:
            self.distance_unit.setCurrentIndex(index)
        row.addWidget(self.distance_unit)
        form1.addRow("Distância:", row)
        self.azimuth_spin = QDoubleSpinBox()
        self.azimuth_spin.setRange(0.0, 360.0)
        self.azimuth_spin.setDecimals(2)
        self.azimuth_spin.setSuffix("°")
        self.azimuth_spin.setToolTip(
            "A partir do Norte geográfico, sentido horário - mesma convenção "
            "do rumo mostrado na aba Linha da Régua."
        )
        form1.addRow("Azimute:", self.azimuth_spin)
        self.stack.addWidget(page1)

        page2 = QWidget()
        form2 = QFormLayout(page2)
        self.lat_edit = QLineEdit()
        self.lon_edit = QLineEdit()
        form2.addRow("Latitude:", self.lat_edit)
        form2.addRow("Longitude:", self.lon_edit)
        self.stack.addWidget(page2)

        layout.addWidget(self.stack)
        self.mode_combo.currentIndexChanged.connect(self.stack.setCurrentIndex)

        self.btn_add = QPushButton("Adicionar vértice")
        layout.addWidget(self.btn_add)
        layout.addStretch()
        self.btn_add.clicked.connect(self._on_add_clicked)

    def set_last_point_getter(self, func):
        """func: sem argumentos, devolve o último QgsPointXY (CRS do
        canvas) do desenho atual, ou None se ainda não há nenhum vértice."""
        self._last_point_getter = func

    def _on_add_clicked(self):
        if self.mode_combo.currentIndex() == 0:
            self._add_by_distance_azimuth()
        else:
            self._add_by_coordinates()

    def _add_by_distance_azimuth(self):
        if self._last_point_getter is None:
            return
        last = self._last_point_getter()
        if last is None:
            QMessageBox.information(
                self,
                "GeoSketch",
                "Adicione pelo menos um vértice no mapa antes de usar distância e azimute.",
            )
            return
        distance_m = utils.to_meters(self.distance_spin.value(), self.distance_unit.currentText())
        azimuth = self.azimuth_spin.value()
        crs = self.canvas.mapSettings().destinationCrs()
        point = utils.project_point(last, distance_m, azimuth, crs)
        if point is None:
            QMessageBox.warning(self, "GeoSketch", "Não foi possível calcular o ponto.")
            return
        self.pointComputed.emit(point)

    def _add_by_coordinates(self):
        lat = utils.parse_coordinate(self.lat_edit.text())
        lon = utils.parse_coordinate(self.lon_edit.text())
        if lat is None or lon is None:
            QMessageBox.warning(self, "GeoSketch", "Coordenadas inválidas.")
            return
        if not (-90.0 <= lat <= 90.0) or not (-180.0 <= lon <= 180.0):
            QMessageBox.warning(
                self,
                "GeoSketch",
                "Latitude precisa estar entre -90 e 90, e longitude entre -180 e 180.",
            )
            return
        try:
            crs = self.canvas.mapSettings().destinationCrs()
            point = utils.from_wgs84(QgsPointXY(lon, lat), crs)
        except Exception as exc:
            QMessageBox.warning(
                self, "GeoSketch", "Erro ao converter a coordenada:\n{}".format(exc)
            )
            return
        self.pointComputed.emit(point)

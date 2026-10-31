# -*- coding: utf-8 -*-
"""Régua, no formato do Google Earth: abas por tipo de medição.

Cada aba tem sua própria ferramenta de desenho. Trocar de aba troca a
ferramenta e limpa o desenho anterior, que é o comportamento do original.
"""

import math

from qgis.core import QgsCoordinateTransform, QgsGeometry, QgsPointXY, QgsProject
from qgis.PyQt.QtCore import Qt
from qgis.PyQt.QtWidgets import (
    QCheckBox,
    QDialog,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from . import storage, utils
from .maptools import DrawTool
from .widgets import CrsRow, UnitRow

# aba -> (modo de desenho, texto de ajuda, linhas de medida)
TABS = [
    ("Linha", "line2", "Meça a distância em linha reta entre dois pontos.",
     ["comprimento", "rumo"]),
    ("Caminho", "line", "Meça a distância ao longo de vários trechos.",
     ["comprimento"]),
    ("Polígono", "polygon", "Meça o perímetro e a área de uma região.",
     ["perimetro", "area"]),
    ("Círculo", "circle", "Meça o raio, a circunferência e a área de um círculo.",
     ["raio", "diametro", "circunferencia", "area"]),
]

ROW_LABELS = {
    "comprimento": "Comprimento:",
    "rumo": "Rumo:",
    "perimetro": "Perímetro:",
    "area": "Área:",
    "raio": "Raio:",
    "diametro": "Diâmetro:",
    "circunferencia": "Circunferência:",
}


class RulerPage(QWidget):
    def __init__(self, rows, help_text, show_crs=False, parent=None):
        super(RulerPage, self).__init__(parent)
        layout = QVBoxLayout(self)
        label = QLabel(help_text)
        label.setStyleSheet("color: #006400;")
        label.setWordWrap(True)
        layout.addWidget(label)
        layout.addSpacing(6)

        self.rows = {}
        for key in rows:
            if key == "area":
                row = UnitRow(ROW_LABELS[key], utils.AREA_UNITS, utils.DEFAULT_AREA)
            elif key == "rumo":
                row = UnitRow(ROW_LABELS[key], [("Graus", 1.0)], "Graus")
            else:
                row = UnitRow(ROW_LABELS[key], utils.LENGTH_UNITS, utils.DEFAULT_LENGTH)
            self.rows[key] = row
            layout.addWidget(row)

        # SRC do caminho (Fase 3): so a aba Caminho ganha este seletor - as
        # outras continuam gravando em EPSG:4326, como sempre (ver
        # RulerDialog._save()). Comeca no SRC do projeto.
        self.crs_row = None
        if show_crs:
            layout.addSpacing(6)
            self.crs_row = CrsRow(QgsProject.instance().crs())
            layout.addWidget(self.crs_row)

        layout.addStretch()

    def set_value(self, key, text):
        if key in self.rows:
            self.rows[key].setValue(text)

    def unit(self, key):
        return self.rows[key].unit() if key in self.rows else ""


class RulerDialog(QDialog):
    def __init__(self, iface, parent=None, initial_tab=0):
        super(RulerDialog, self).__init__(parent)
        self.iface = iface
        self.canvas = iface.mapCanvas()
        self.points = []
        self.tool = None
        self._previous_tool = self.canvas.mapTool()

        self.setWindowTitle("Régua")
        self.setWindowFlags(self.windowFlags() | Qt.WindowStaysOnTopHint)
        self.setModal(False)
        self.setMinimumWidth(680)

        layout = QVBoxLayout(self)
        self.tabs = QTabWidget()
        self.pages = []
        for title, mode, help_text, rows in TABS:
            page = RulerPage(rows, help_text, show_crs=(mode == "line"))
            for row in page.rows.values():
                row.unitChanged.connect(self._refresh)
            self.tabs.addTab(page, title)
            self.pages.append((mode, rows, page))

        # Fase 5: as duas abas de medição em 3D eram só um placeholder
        # desativado (nunca tiveram lógica de medição real - dependiam de
        # um MDE que o plugin nunca chegou a usar) e saíram da régua para
        # simplificar a interface. Linha, Caminho, Polígono e Círculo (as 4
        # abas acima) são as únicas mantidas.

        layout.addWidget(self.tabs)
        if 0 <= initial_tab < self.tabs.count():
            self.tabs.setCurrentIndex(initial_tab)

        footer = QHBoxLayout()
        self.mouse_nav = QCheckBox("Navegação com mouse")
        self.mouse_nav.setToolTip(
            "Devolve o mouse à navegação do mapa sem fechar a régua."
        )
        footer.addWidget(self.mouse_nav)
        footer.addStretch()
        self.btn_save = QPushButton("Salvar")
        self.btn_clear = QPushButton("Limpar")
        self.btn_close = QPushButton("Fechar")
        footer.addWidget(self.btn_save)
        footer.addWidget(self.btn_clear)
        footer.addWidget(self.btn_close)
        layout.addLayout(footer)

        self.btn_save.setEnabled(False)
        self.btn_save.clicked.connect(self._save)
        self.btn_clear.clicked.connect(self._clear)
        self.btn_close.clicked.connect(self.close)
        self.mouse_nav.toggled.connect(self._toggle_navigation)
        self.tabs.currentChanged.connect(self._tab_changed)

        self._activate_tool()

    # ---------------------------------------------------------- ferramenta
    def _current(self):
        index = self.tabs.currentIndex()
        if index < len(self.pages):
            return self.pages[index]
        return None

    def _activate_tool(self):
        current = self._current()
        if current is None:
            return
        mode, _, _ = current
        draw_mode = "line" if mode == "line2" else mode
        self._release_tool()
        self.tool = DrawTool(self.canvas, draw_mode, iface=self.iface)
        self.tool.restart_on_click = True
        # A regua nao tem controle de aderencia na interface (Fase C e
        # explicita em preservar o comportamento da regua) - desliga por
        # omissao, para o clique continuar caindo exatamente onde o cursor
        # esta, como sempre foi.
        self.tool.set_snapping_enabled(False)
        self.tool.pointsChanged.connect(self._points_changed)
        self.tool.finished.connect(self._points_changed)
        self.canvas.setMapTool(self.tool)

    def _release_tool(self):
        if self.tool is not None:
            try:
                self.tool.reset()
                self.canvas.unsetMapTool(self.tool)
            except Exception:
                pass
            self.tool = None

    def _tab_changed(self, _index):
        self.points = []
        self.mouse_nav.setChecked(False)
        self._activate_tool()
        self._refresh()

    def _toggle_navigation(self, checked):
        if checked:
            self._release_tool()
            try:
                self.iface.actionPan().trigger()
            except Exception:
                pass
        else:
            self._activate_tool()

    # ------------------------------------------------------------- medidas
    def _points_changed(self, points):
        # Fase 5: "Linha" (mode "line2") é medição ponto-a-ponto, não
        # cadastro de vértices - usa o mesmo DrawTool(mode="line") do
        # Caminho, mas sempre travado em 2 pontos. self.points nunca guarda
        # mais que isso para esta aba, então _save() grava UMA única
        # QgsGeometry.fromPolylineXY com 2 vértices (uma feição de linha),
        # nunca dois marcadores de ponto independentes.
        current = self._current()
        if current is not None and current[0] == "line2" and len(points) > 2:
            points = points[:2]
            if self.tool is not None:
                self.tool.points = points
        self.points = points
        self._refresh()

    def _refresh(self):
        current = self._current()
        if current is None:
            return
        mode, rows, page = current
        crs = self.canvas.mapSettings().destinationCrs()
        pts = self.points

        if "comprimento" in rows:
            length = utils.measure_length(pts, crs)
            page.set_value(
                "comprimento",
                utils.format_number(utils.convert_length(length, page.unit("comprimento"))),
            )
        if "rumo" in rows:
            page.set_value("rumo", self._bearing_text(pts, crs))
        if "perimetro" in rows:
            perimeter = utils.measure_perimeter(pts, crs)
            page.set_value(
                "perimetro",
                utils.format_number(utils.convert_length(perimeter, page.unit("perimetro"))),
            )
        if "raio" in rows:
            radius = self.tool.radius() if self.tool is not None else 0.0
            page.set_value(
                "raio", utils.format_number(utils.convert_length(radius, page.unit("raio")))
            )
            if "diametro" in rows:
                page.set_value(
                    "diametro",
                    utils.format_number(utils.convert_length(2 * radius, page.unit("diametro"))),
                )
            page.set_value(
                "circunferencia",
                utils.format_number(
                    utils.convert_length(2 * math.pi * radius, page.unit("circunferencia"))
                ),
            )
        if "area" in rows:
            area = utils.measure_area(pts, crs)
            page.set_value(
                "area", utils.format_number(utils.convert_area(area, page.unit("area")))
            )

        minimum = 3 if mode in ("polygon", "circle") else 2
        self.btn_save.setEnabled(len(pts) >= minimum)

    def _bearing_text(self, points, crs):
        if len(points) < 2:
            return "0,00"
        try:
            start = utils.to_wgs84(points[0], crs)
            end = utils.to_wgs84(points[-1], crs)
            lat1 = math.radians(start.y())
            lat2 = math.radians(end.y())
            dlon = math.radians(end.x() - start.x())
            y = math.sin(dlon) * math.cos(lat2)
            x = math.cos(lat1) * math.sin(lat2) - math.sin(lat1) * math.cos(lat2) * math.cos(dlon)
            bearing = (math.degrees(math.atan2(y, x)) + 360.0) % 360.0
            return utils.format_number(bearing)
        except Exception:
            return "0,00"

    # -------------------------------------------------------------- ações
    def _clear(self):
        self.points = []
        if self.tool is not None:
            self.tool.reset()
        self._refresh()

    def _save(self):
        """Converte a medição em uma feição permanente, como o Salvar do original."""
        current = self._current()
        if current is None or not self.points:
            return
        mode, _, page = current
        canvas_crs = self.canvas.mapSettings().destinationCrs()
        save_crs = None  # None = grava em EPSG:4326, comportamento de sempre.

        if mode == "line" and page.crs_row is not None:
            # Caminho (Fase 3): grava no SRC escolhido no seletor da aba, em
            # vez de sempre converter para WGS84 - é o que permite abrir o
            # resultado direto no Buffer com distância em metros. Linha,
            # Polígono e Círculo não têm este seletor e continuam como
            # antes (ver bloco abaixo).
            save_crs = page.crs_row.crs()
            if save_crs is None or not save_crs.isValid():
                save_crs = QgsProject.instance().crs()
            if save_crs != canvas_crs:
                transform = QgsCoordinateTransform(canvas_crs, save_crs, QgsProject.instance())
                pts = [transform.transform(p) for p in self.points]
            else:
                pts = list(self.points)
            geometry = QgsGeometry.fromPolylineXY(pts)
            kind = "line"
            default_name = "Caminho"
        else:
            wgs = [utils.to_wgs84(p, canvas_crs) for p in self.points]
            if mode in ("polygon", "circle"):
                ring = list(wgs)
                if ring[0] != ring[-1]:
                    ring.append(ring[0])
                geometry = QgsGeometry.fromPolygonXY([ring])
                kind = "polygon"
                default_name = "Medição de área"
            else:
                geometry = QgsGeometry.fromPolylineXY(wgs)
                kind = "line"
                default_name = "Medição de distância"

        from qgis.PyQt.QtWidgets import QInputDialog

        name, ok = QInputDialog.getText(self, "Salvar medição", "Nome:", text=default_name)
        if not ok:
            return

        try:
            layer = storage.create_place(
                kind,
                name or default_name,
                geometry,
                {
                    "cor_linha": "255,60,60,255",
                    "cor_preenchimento": "255,255,255,60",
                    "largura_linha": 1.5,
                },
                crs=save_crs,
            )
        except Exception as exc:
            QMessageBox.critical(self, "Régua", "Não foi possível salvar:\n{}".format(exc))
            return
        self.iface.messageBar().pushSuccess(
            "Régua", 'Medição "{}" criada no painel Camadas.'.format(layer.name())
        )

    # ------------------------------------------------------------ limpeza
    def closeEvent(self, event):
        self._release_tool()
        try:
            if self._previous_tool is not None:
                self.canvas.setMapTool(self._previous_tool)
        except Exception:
            pass
        super(RulerDialog, self).closeEvent(event)

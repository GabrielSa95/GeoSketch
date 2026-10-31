# -*- coding: utf-8 -*-
"""Ferramentas de desenho no mapa, com retorno visual ao vivo.

Comportamento copiado do Google Earth:
  - clique simples adiciona vértice;
  - o desenho aparece enquanto você clica, sem precisar entrar em modo edição;
  - botão direito, duplo clique, Enter ou o botão Concluir encerram;
  - depois de encerrado o desenho CONGELA (não segue mais o cursor);
  - Backspace desfaz o último vértice; Esc recomeça.

Correção de vértices durante o desenho (linha e polígono, nao circulo):
  - clicar com o botão esquerdo sobre um vértice já colocado o SELECIONA e
    permite arrastar (soltar o botão confirma a nova posição);
  - botão direito sobre um vértice o APAGA, sem encerrar o desenho;
  - botão direito fora de um vértice continua encerrando o desenho, como
    sempre. Isso evita qualquer ambiguidade entre "apagar vértice" e
    "concluir o desenho";
  - Ctrl+Z desfaz e Ctrl+Y (ou Ctrl+Shift+Z) refaz a última ação de vértice
    (adicionar, arrastar ou apagar). Também só em linha/polígono: Esc e
    Recomeçar continuam sendo um reinício completo, fora dessa pilha.

Aderência (linha/polígono/marcador, NÃO círculo - ver snapping.py): se
`self.snap.enabled`, cada clique ou arraste que definiria um vértice novo
tenta aderir a um vértice/segmento de qualquer camada do projeto antes de
usar a posição crua do cursor. Um marcador magenta mostra onde aderiria,
antes de clicar.
"""

import math

from qgis.core import QgsPointXY, QgsWkbTypes
from qgis.gui import QgsMapTool, QgsRubberBand, QgsVertexMarker
from qgis.PyQt.QtCore import Qt, pyqtSignal
from qgis.PyQt.QtGui import QColor, QKeySequence

from . import geometry_rules, snapping, utils

LINE_COLOR = QColor(255, 60, 60)
FILL_COLOR = QColor(255, 255, 255, 110)
SELECTED_COLOR = QColor(0, 200, 255)
SNAP_COLOR = QColor(255, 0, 255)

# Quantidade de CLIQUES necessarios, nao de vertices da geometria final.
# O circulo sao dois cliques (centro e borda) que viram um anel de 72 pontos.
MINIMUM = {"point": 1, "line": 2, "polygon": 3, "circle": 2}

# Modos em que vertices ja colocados podem ser selecionados/arrastados/
# apagados individualmente. Circulo e ponto tem logica propria e ficam de
# fora de proposito.
VERTEX_EDIT_MODES = ("line", "polygon")

GRAB_PIXELS = 14


class DrawTool(QgsMapTool):
    """mode: 'point' | 'line' | 'polygon' | 'circle'"""

    pointsChanged = pyqtSignal(list)
    finished = pyqtSignal(list)

    def __init__(self, canvas, mode, iface=None):
        super(DrawTool, self).__init__(canvas)
        self.canvas = canvas
        self.mode = mode
        self.iface = iface
        self.points = []
        self.preview = None
        self.done = False
        # Na regua, clicar de novo depois de pronto comeca outra medicao.
        # Nas janelas de criacao isso seria perigoso: um clique perdido apagaria
        # o desenho que o usuario acabou de fazer.
        self.restart_on_click = False
        self._markers = []
        # Selecao/arraste de vertice (so line/polygon; ver VERTEX_EDIT_MODES).
        self.selected_index = None
        self._dragging = None
        # Quando o botao direito ja apagou um vertice no press, o release
        # (rede de seguranca de contexto de mapa) nao deve encerrar o desenho.
        self._suppress_release_finish = False
        # Desfazer/refazer (so line/polygon; ver VERTEX_EDIT_MODES). Cada item
        # e uma copia de self.points ANTES de uma mudanca de vertice.
        self._history = geometry_rules.UndoStack()
        # Aderencia (nao circulo - ver _snap_applicable()).
        self.snap = snapping.SnapHelper(canvas)
        self._snap_marker = QgsVertexMarker(canvas)
        self._snap_marker.setIconType(QgsVertexMarker.ICON_X)
        self._snap_marker.setColor(SNAP_COLOR)
        self._snap_marker.setIconSize(12)
        self._snap_marker.setPenWidth(3)
        self._snap_marker.hide()

        if mode in ("polygon", "circle"):
            gtype = QgsWkbTypes.PolygonGeometry
        elif mode == "line":
            gtype = QgsWkbTypes.LineGeometry
        else:
            gtype = QgsWkbTypes.PointGeometry
        # QgsRubberBand não expõe geometryType(); guardamos para usar no reset().
        self.gtype = gtype

        self.band = QgsRubberBand(canvas, gtype)
        self.band.setColor(LINE_COLOR)
        self.band.setWidth(2)
        if gtype == QgsWkbTypes.PolygonGeometry:
            self.band.setFillColor(FILL_COLOR)
        self.radius_band = None
        if mode == "circle":
            self.radius_band = QgsRubberBand(canvas, QgsWkbTypes.LineGeometry)
            self.radius_band.setColor(LINE_COLOR)
            self.radius_band.setWidth(2)
            self.radius_band.setLineStyle(Qt.DashLine)

        self.setCursor(Qt.CrossCursor)

    # ------------------------------------------------------------ eventos
    def set_snapping_enabled(self, enabled):
        self.snap.enabled = bool(enabled)
        if not enabled:
            self._snap_marker.hide()

    def set_snap_tolerance(self, pixels):
        self.snap.tolerance_px = int(pixels)

    def _snap_applicable(self):
        # Circulo tem logica propria (raio/centro) e fica de fora, de
        # proposito - preserva o comportamento existente do circulo.
        return self.mode != "circle"

    def canvasPressEvent(self, event):
        raw_point = self.toMapCoordinates(event.pos())
        if self._snap_applicable():
            point, _ = self.snap.resolve(event.pos(), raw_point)
        else:
            point = raw_point

        if event.button() == Qt.RightButton:
            index = self._vertex_at(raw_point)
            if index >= 0:
                # Apaga so aquele vertice; nao e o botao que encerra o desenho.
                self._suppress_release_finish = True
                self._delete_vertex(index)
            else:
                self._suppress_release_finish = False
                # Consumido aqui para o QGIS nao abrir o menu de contexto do mapa.
                self.finish()
            return

        if event.button() == Qt.LeftButton and self.mode in VERTEX_EDIT_MODES:
            index = self._vertex_at(raw_point)
            if index >= 0:
                self._push_undo()
                self.selected_index = index
                self._dragging = index
                self._refresh()
                return

        if self.done:
            if not self.restart_on_click:
                return
            self.reset()

        if self.mode == "point":
            self.points = [point]
            self._refresh()
            self.finish()
            return

        if self.mode == "circle" and len(self.points) >= 2:
            self.points = []

        if self.mode in VERTEX_EDIT_MODES:
            self._push_undo()
        self.selected_index = None
        self.points.append(point)
        self._refresh()

        if self.mode == "circle" and len(self.points) == 2:
            self.finish()

    def canvasReleaseEvent(self, event):
        if event.button() == Qt.LeftButton and self._dragging is not None:
            self._dragging = None
            self._refresh()
            return
        # Rede de seguranca: em algumas versoes o menu de contexto do mapa e
        # disparado no release, nao no press.
        if event.button() == Qt.RightButton:
            if not self.done and not self._suppress_release_finish:
                self.finish()
            self._suppress_release_finish = False

    def canvasMoveEvent(self, event):
        raw_point = self.toMapCoordinates(event.pos())
        if self._snap_applicable():
            point, snapped = self.snap.resolve(event.pos(), raw_point)
            if snapped:
                self._snap_marker.setCenter(QgsPointXY(point))
                self._snap_marker.show()
            else:
                self._snap_marker.hide()
        else:
            point = raw_point
            self._snap_marker.hide()

        if self._dragging is not None:
            # Arrastar um vertice so move ele: nunca cria ponto novo.
            self.points[self._dragging] = point
            self._refresh()
            return
        # Linha e poligono NAO acompanham o cursor: o traco so avanca no clique.
        # O circulo e a excecao, porque so ha o que ver enquanto se arrasta -
        # o raio e o tamanho do circulo dependem de onde o mouse esta agora.
        if self.mode != "circle" or self.done or len(self.points) != 1:
            return
        self.preview = raw_point
        self._refresh()

    def canvasDoubleClickEvent(self, event):
        if self.mode in ("line", "polygon"):
            # O duplo clique gera um press extra antes; remove o vertice repetido.
            if len(self.points) >= 2 and self.points[-1] == self.points[-2]:
                self.points.pop()
            self.finish()

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Escape:
            self.reset()
        elif event.key() in (Qt.Key_Backspace, Qt.Key_Delete):
            if self.done:
                self.done = False
            if self.points:
                if self.mode in VERTEX_EDIT_MODES:
                    self._push_undo()
                self.points.pop()
                self._dragging = None
                if self.selected_index is not None and self.selected_index >= len(self.points):
                    self.selected_index = None
                self._refresh()
        elif event.key() in (Qt.Key_Return, Qt.Key_Enter):
            self.finish()
        elif self.mode in VERTEX_EDIT_MODES and event.matches(QKeySequence.Undo):
            self.undo()
        elif self.mode in VERTEX_EDIT_MODES and (
            event.matches(QKeySequence.Redo)
            or (event.key() == Qt.Key_Y and event.modifiers() & Qt.ControlModifier)
        ):
            self.redo()

    # -------------------------------------------------------------- apoio
    def can_finish(self):
        if self.mode in VERTEX_EDIT_MODES:
            return geometry_rules.unique_count(self.points) >= MINIMUM[self.mode]
        return len(self.points) >= MINIMUM[self.mode]

    def _tolerance(self):
        return self.canvas.mapUnitsPerPixel() * GRAB_PIXELS

    def _vertex_at(self, map_point):
        """Indice do vertice mais proximo dentro do raio de captura, ou -1."""
        if self.mode not in VERTEX_EDIT_MODES:
            return -1
        tolerance = self._tolerance()
        best, best_distance = -1, None
        for i, point in enumerate(self.points):
            distance = math.hypot(point.x() - map_point.x(), point.y() - map_point.y())
            if distance <= tolerance and (best_distance is None or distance < best_distance):
                best, best_distance = i, distance
        return best

    def _delete_vertex(self, index):
        """Remove so o vertice `index`, se isso nao deixar a geometria invalida."""
        if not geometry_rules.can_remove_vertex(self.points, index, MINIMUM[self.mode]):
            if self.iface is not None:
                nome = {"line": "um caminho", "polygon": "um polígono"}.get(
                    self.mode, "esta feição"
                )
                self.iface.messageBar().pushWarning(
                    "GeoSketch",
                    "Não é possível apagar: {} precisa de pelo menos {} vértices "
                    "distintos.".format(nome, MINIMUM[self.mode]),
                )
            return
        self._push_undo()
        self.points.pop(index)
        if self._dragging == index:
            self._dragging = None
        if self.selected_index == index:
            self.selected_index = None
        elif self.selected_index is not None and self.selected_index > index:
            self.selected_index -= 1
        self._refresh()

    def add_vertex(self, point):
        """Acrescenta um vertice calculado (entrada numerica - distancia e
        azimute, ou coordenadas digitadas; ver widgets.VertexEntryPanel),
        passando pelo MESMO caminho de um clique real: undo, refresh,
        sinais. So faz sentido em linha/poligono e enquanto o desenho nao
        tiver sido concluido - mesma regra de um clique no mapa. Devolve
        True se o vertice foi mesmo acrescentado."""
        if self.mode not in VERTEX_EDIT_MODES or self.done:
            return False
        self._push_undo()
        self.selected_index = None
        self.points.append(point)
        self._refresh()
        return True

    # ------------------------------------------------------- desfazer/refazer
    def _push_undo(self):
        """Guarda uma copia de self.points ANTES de uma mudanca de vertice.

        So line/polygon: circulo e ponto tem comportamento proprio e ficam de
        fora, igual a selecao/arraste/exclusao de vertice.
        """
        if self.mode not in VERTEX_EDIT_MODES:
            return
        self._history.push(self.points)

    def undo(self):
        previous = self._history.undo(self.points)
        if previous is None:
            return
        self.points = previous
        self._dragging = None
        self.selected_index = None
        if self.done and not self.can_finish():
            self.done = False
        self._refresh()

    def redo(self):
        nxt = self._history.redo(self.points)
        if nxt is None:
            return
        self.points = nxt
        self._dragging = None
        self.selected_index = None
        self._refresh()

    def finish(self):
        """Congela o desenho. Chamado pelo mouse, pelo teclado ou pelo botao."""
        if self.done or not self.can_finish():
            return
        if self.mode == "circle" and len(self.points) == 1 and self.preview is not None:
            self.points.append(self.preview)
        self.done = True
        self._refresh()
        self.finished.emit(self.geometry_points())

    def _circle_pair(self):
        """(centro, borda) do circulo, usando a previa do cursor se preciso."""
        if self.mode != "circle" or not self.points:
            return None
        if len(self.points) >= 2:
            return self.points[0], self.points[1]
        if self.preview is not None:
            return self.points[0], self.preview
        return None

    def display_points(self):
        """Pontos que devem ser desenhados agora."""
        pair = self._circle_pair()
        if pair is not None:
            ring, _ = utils.circle_points(pair[0], pair[1], crs=self._circle_crs())
            # Nunca cai de volta para [centro, borda]: desenhado como
            # "polígono" de 2 pontos, isso fica visualmente idêntico à linha
            # pontilhada do raio - exatamente o defeito relatado ("só
            # aparece o raio"). Sem anel de verdade, não desenha nada aqui;
            # a linha do raio (radius_band) já dá o retorno visual mínimo.
            return ring
        return list(self.points)

    def _circle_crs(self):
        """CRS do canvas/mapa - o mesmo em que center/edge já estão, para o
        cálculo geodésico do círculo não cair por omissão no CRS do
        projeto (podem divergir; ver utils.circle_points)."""
        try:
            return self.canvas.mapSettings().destinationCrs()
        except Exception:
            return None

    def _refresh(self):
        pts = self.display_points()
        self.band.reset(self.gtype)
        for pt in pts:
            self.band.addPoint(QgsPointXY(pt), False)
        self.band.updatePosition()
        self.band.show()

        if self.radius_band is not None:
            self.radius_band.reset(QgsWkbTypes.LineGeometry)
            pair = self._circle_pair()
            if pair is not None:
                self.radius_band.addPoint(QgsPointXY(pair[0]), False)
                self.radius_band.addPoint(QgsPointXY(pair[1]), False)
                self.radius_band.updatePosition()
                self.radius_band.show()

        self._clear_markers()
        if self.mode == "circle":
            # marca o centro e a ponta do raio
            pair = self._circle_pair()
            marks = [self.points[0]] if self.points else []
            if pair is not None:
                marks = [pair[0], pair[1]]
            for i, pt in enumerate(marks):
                marker = QgsVertexMarker(self.canvas)
                marker.setCenter(QgsPointXY(pt))
                marker.setIconType(
                    QgsVertexMarker.ICON_CROSS if i == 0 else QgsVertexMarker.ICON_BOX
                )
                marker.setColor(LINE_COLOR)
                marker.setIconSize(10)
                marker.setPenWidth(2)
                self._markers.append(marker)
        else:
            for i, pt in enumerate(self.points):
                selected = i == self.selected_index
                marker = QgsVertexMarker(self.canvas)
                marker.setCenter(QgsPointXY(pt))
                marker.setIconType(QgsVertexMarker.ICON_BOX)
                marker.setColor(SELECTED_COLOR if selected else LINE_COLOR)
                marker.setFillColor(SELECTED_COLOR if selected else LINE_COLOR)
                marker.setIconSize(12 if selected else 8)
                marker.setPenWidth(3 if selected else 2)
                self._markers.append(marker)

        self.pointsChanged.emit(self.geometry_points())

    def geometry_points(self):
        """Pontos definitivos (circulo ja expandido em anel).

        Para linha/poligono, vertices repetidos um atras do outro (ex.: dois
        cliques seguidos no mesmo lugar) sao descartados aqui, na saida, sem
        afetar os indices usados para selecionar/arrastar/apagar em
        self.points.
        """
        pair = self._circle_pair()
        if pair is not None:
            ring, _ = utils.circle_points(pair[0], pair[1], crs=self._circle_crs())
            return ring
        if self.mode in VERTEX_EDIT_MODES:
            return geometry_rules.dedup_consecutive(self.points)
        return list(self.points)

    def radius(self):
        pair = self._circle_pair()
        if pair is not None:
            _, r = utils.circle_points(pair[0], pair[1], crs=self._circle_crs())
            return r
        return 0.0

    def _clear_markers(self):
        for marker in self._markers:
            try:
                self.canvas.scene().removeItem(marker)
            except Exception:
                pass
        self._markers = []

    def reset(self):
        self.points = []
        self.preview = None
        self.done = False
        self.selected_index = None
        self._dragging = None
        self._suppress_release_finish = False
        self._history.clear()
        self.band.reset(self.gtype)
        if self.radius_band is not None:
            self.radius_band.reset(QgsWkbTypes.LineGeometry)
        self._clear_markers()
        self.pointsChanged.emit([])

    def deactivate(self):
        self.reset()
        for band in (self.band, self.radius_band):
            if band is None:
                continue
            try:
                self.canvas.scene().removeItem(band)
            except Exception:
                pass
        try:
            self.canvas.scene().removeItem(self._snap_marker)
        except Exception:
            pass
        super(DrawTool, self).deactivate()

    def isZoomTool(self):
        return False

    def isTransient(self):
        return False

    def isEditTool(self):
        return True

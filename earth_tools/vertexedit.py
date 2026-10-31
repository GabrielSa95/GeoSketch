# -*- coding: utf-8 -*-
"""Edição de vértices no estilo Google Earth.

Ao entrar no modo, os pontos do desenho aparecem. Então:
  - arrastar um ponto move o ponto;
  - botão direito em cima de um ponto APAGA aquele ponto;
  - clicar num ponto branco no meio do segmento cria um vértice novo ali;
  - clicar em qualquer lugar vazio do mapa estende o desenho com um vértice
    novo no final (linha ou polígono);
  - Ctrl+Z desfaz e Ctrl+Y (ou Ctrl+Shift+Z) refaz a última mudança de
    vértice (linha ou polígono só);
  - Esc ou botão direito fora de um ponto sai do modo.

Cada alteração é gravada na hora, sem o usuário precisar salvar edições. Por
isso desfazer/refazer aqui não é só visual: regrava a geometria no
GeoPackage a cada passo, pelo mesmo caminho seguro de commit usado em _save().

Aderência (linha/polígono - ver snapping.py, não aplicável a marcador, que
só tem um ponto fixo): mover/inserir/estender um vértice tenta aderir a um
vértice/segmento de qualquer camada do projeto antes de usar a posição crua
do cursor. Um marcador magenta mostra onde aderiria, antes de soltar.
"""

import math

from qgis.core import (
    QgsCoordinateTransform,
    QgsGeometry,
    QgsPointXY,
    QgsProject,
    QgsWkbTypes,
)
from qgis.gui import QgsMapTool, QgsRubberBand, QgsVertexMarker
from qgis.PyQt.QtCore import Qt, pyqtSignal
from qgis.PyQt.QtGui import QColor, QKeySequence

from . import geometry_rules, snapping, utils

VERTEX_COLOR = QColor(255, 60, 60)
SELECTED_COLOR = QColor(0, 200, 255)
MID_COLOR = QColor(255, 255, 255)
BAND_COLOR = QColor(255, 160, 0)
SNAP_COLOR = QColor(255, 0, 255)

MINIMUM = {"point": 1, "line": 2, "polygon": 3}
GRAB_PIXELS = 14


class VertexEditTool(QgsMapTool):
    """Edita a geometria da única feição de uma camada de lugar."""

    changed = pyqtSignal()

    def __init__(self, canvas, layer, kind, iface=None, allow_exit=True):
        super(VertexEditTool, self).__init__(canvas)
        self.canvas = canvas
        self.layer = layer
        self.kind = kind
        self.iface = iface
        # Quando a janela de edicao esta aberta, quem encerra e o OK/Cancelar
        # dela, nao um clique perdido no mapa.
        self.allow_exit = allow_exit
        self.fid = None
        self.points = []
        self.dragging = None
        self.original_geometry = None
        self._vertex_markers = []
        self._mid_markers = []
        # Desfazer/refazer (so line/polygon; ver _push_undo).
        self._history = geometry_rules.UndoStack()
        # Aderencia (so line/polygon - ver _snap_applicable()).
        self.snap = snapping.SnapHelper(canvas)
        self._snap_marker = QgsVertexMarker(canvas)
        self._snap_marker.setIconType(QgsVertexMarker.ICON_X)
        self._snap_marker.setColor(SNAP_COLOR)
        self._snap_marker.setIconSize(12)
        self._snap_marker.setPenWidth(3)
        self._snap_marker.hide()

        gtype = {
            "polygon": QgsWkbTypes.PolygonGeometry,
            "line": QgsWkbTypes.LineGeometry,
            "point": QgsWkbTypes.PointGeometry,
        }[kind]
        self.gtype = gtype
        self.band = QgsRubberBand(canvas, gtype)
        self.band.setColor(BAND_COLOR)
        self.band.setWidth(2)
        if gtype == QgsWkbTypes.PolygonGeometry:
            self.band.setFillColor(QColor(255, 255, 255, 60))

        self.setCursor(Qt.CrossCursor)
        self._load()

    def _snap_applicable(self):
        return self.kind in ("line", "polygon")

    def set_snapping_enabled(self, enabled):
        self.snap.enabled = bool(enabled)
        if not enabled:
            self._snap_marker.hide()

    def set_snap_tolerance(self, pixels):
        self.snap.tolerance_px = int(pixels)

    # ------------------------------------------------------------ carga
    def _to_canvas(self, point):
        try:
            tr = QgsCoordinateTransform(
                self.layer.crs(),
                self.canvas.mapSettings().destinationCrs(),
                QgsProject.instance(),
            )
            return tr.transform(point)
        except Exception:
            return QgsPointXY(point)

    def _to_layer(self, point):
        try:
            tr = QgsCoordinateTransform(
                self.canvas.mapSettings().destinationCrs(),
                self.layer.crs(),
                QgsProject.instance(),
            )
            return tr.transform(point)
        except Exception:
            return QgsPointXY(point)

    def _load(self):
        feature = None
        for candidate in self.layer.getFeatures():
            feature = candidate
            break
        if feature is None:
            self.points = []
            return
        self.fid = feature.id()
        geometry = feature.geometry()
        if self.original_geometry is None:
            self.original_geometry = QgsGeometry(geometry)
        pts = []
        try:
            if self.kind == "polygon":
                ring = geometry.asPolygon()[0]
                if len(ring) > 1 and ring[0] == ring[-1]:
                    ring = ring[:-1]  # o ponto de fechamento não é editável
                pts = list(ring)
            elif self.kind == "line":
                pts = list(geometry.asPolyline())
            else:
                pts = [geometry.asPoint()]
        except Exception:
            pts = []
        self.points = [self._to_canvas(p) for p in pts]
        self._refresh()

    # ----------------------------------------------------------- eventos
    def canvasPressEvent(self, event):
        map_point = self.toMapCoordinates(event.pos())

        if event.button() == Qt.RightButton:
            index = self._nearest_vertex(map_point)
            if index >= 0:
                self._delete_vertex(index)
            elif self.allow_exit:
                self._leave()
            return

        index = self._nearest_vertex(map_point)
        if index >= 0:
            self._push_undo()
            self.dragging = index
            return

        mid = self._nearest_midpoint(map_point)
        if mid >= 0 and self.kind != "point":
            if self._snap_applicable():
                snap_point, _ = self.snap.resolve(event.pos(), map_point)
            else:
                snap_point = map_point
            self._push_undo()
            self.points.insert(mid + 1, snap_point)
            self.dragging = mid + 1
            self._refresh()
            return

        # Clique fora de qualquer vertice ou ponto medio: estende o desenho
        # com um vertice novo no final (apos o ultimo ponto). Para poligono,
        # isso entra antes do fechamento automatico do anel (o ponto de
        # fechamento nunca fica guardado em self.points - ver _load/_save),
        # entao o anel continua fechando certo sozinho.
        if self.kind in ("line", "polygon"):
            if self._snap_applicable():
                snap_point, _ = self.snap.resolve(event.pos(), map_point)
            else:
                snap_point = map_point
            self._push_undo()
            self.points.append(snap_point)
            self.dragging = len(self.points) - 1
            self._refresh()

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

        if self.dragging is None:
            return
        self.points[self.dragging] = point
        self._refresh()

    def add_vertex(self, point):
        """Acrescenta um vertice calculado (entrada numerica - distancia e
        azimute, ou coordenadas digitadas; ver widgets.VertexEntryPanel) no
        final do desenho, mesmo caminho de clicar fora de qualquer vertice/
        ponto medio: com undo e gravacao no GeoPackage."""
        if self.kind not in ("line", "polygon"):
            return False
        self._push_undo()
        self.points.append(point)
        self.dragging = None
        self._refresh()
        self._save()
        return True

    def canvasReleaseEvent(self, event):
        if event.button() == Qt.LeftButton and self.dragging is not None:
            self.dragging = None
            self._save()

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Escape and self.allow_exit:
            self._leave()
        elif event.matches(QKeySequence.Undo):
            self.undo()
        elif event.matches(QKeySequence.Redo) or (
            event.key() == Qt.Key_Y and event.modifiers() & Qt.ControlModifier
        ):
            self.redo()

    # ------------------------------------------------------- desfazer/refazer
    def _push_undo(self):
        """Guarda uma copia de self.points ANTES de uma mudanca de vertice.

        So line/polygon: um marcador de ponto tem um unico vertice fixo e
        fica de fora, igual ao insert-no-meio e a extensao do desenho.
        """
        if self.kind not in ("line", "polygon"):
            return
        self._history.push(self.points)

    def undo(self):
        previous = self._history.undo(self.points)
        if previous is None:
            return
        self.points = previous
        self.dragging = None
        self._refresh()
        self._save()

    def redo(self):
        nxt = self._history.redo(self.points)
        if nxt is None:
            return
        self.points = nxt
        self.dragging = None
        self._refresh()
        self._save()

    # -------------------------------------------------------------- apoio
    def _tolerance(self):
        return self.canvas.mapUnitsPerPixel() * GRAB_PIXELS

    def _nearest_vertex(self, map_point):
        tolerance = self._tolerance()
        best, best_distance = -1, None
        for i, point in enumerate(self.points):
            distance = math.hypot(point.x() - map_point.x(), point.y() - map_point.y())
            if distance <= tolerance and (best_distance is None or distance < best_distance):
                best, best_distance = i, distance
        return best

    def _midpoints(self):
        if self.kind == "point" or len(self.points) < 2:
            return []
        pairs = list(zip(self.points, self.points[1:]))
        if self.kind == "polygon" and len(self.points) >= 3:
            pairs.append((self.points[-1], self.points[0]))
        return [
            QgsPointXY((a.x() + b.x()) / 2.0, (a.y() + b.y()) / 2.0) for a, b in pairs
        ]

    def _nearest_midpoint(self, map_point):
        tolerance = self._tolerance()
        best, best_distance = -1, None
        for i, point in enumerate(self._midpoints()):
            distance = math.hypot(point.x() - map_point.x(), point.y() - map_point.y())
            if distance <= tolerance and (best_distance is None or distance < best_distance):
                best, best_distance = i, distance
        return best

    def _delete_vertex(self, index):
        if not geometry_rules.can_remove_vertex(self.points, index, MINIMUM[self.kind]):
            if self.iface is not None:
                nome = {"polygon": "um polígono", "line": "um caminho"}.get(
                    self.kind, "um marcador"
                )
                self.iface.messageBar().pushWarning(
                    "GeoSketch",
                    "Não dá para apagar: {} precisa de pelo menos {} pontos "
                    "distintos.".format(nome, MINIMUM[self.kind]),
                )
            return
        self._push_undo()
        self.points.pop(index)
        self._refresh()
        self._save()

    def _refresh(self):
        self.band.reset(self.gtype)
        for point in self.points:
            self.band.addPoint(QgsPointXY(point), False)
        self.band.updatePosition()
        self.band.show()

        self._clear_markers()
        for i, point in enumerate(self.points):
            # Vertice em arraste ganha destaque visual proprio (C3: "selecao
            # visual clara do vertice ativo"), mesma cor usada em maptools.py
            # para o vertice selecionado durante a criacao.
            active = i == self.dragging
            marker = QgsVertexMarker(self.canvas)
            marker.setCenter(QgsPointXY(point))
            marker.setIconType(QgsVertexMarker.ICON_BOX)
            marker.setColor(SELECTED_COLOR if active else VERTEX_COLOR)
            marker.setFillColor(SELECTED_COLOR if active else VERTEX_COLOR)
            marker.setIconSize(13 if active else 10)
            marker.setPenWidth(3)
            self._vertex_markers.append(marker)

        for point in self._midpoints():
            marker = QgsVertexMarker(self.canvas)
            marker.setCenter(QgsPointXY(point))
            marker.setIconType(QgsVertexMarker.ICON_CIRCLE)
            marker.setColor(MID_COLOR)
            marker.setIconSize(7)
            marker.setPenWidth(2)
            self._mid_markers.append(marker)

    def _clear_markers(self):
        for marker in self._vertex_markers + self._mid_markers:
            try:
                self.canvas.scene().removeItem(marker)
            except Exception:
                pass
        self._vertex_markers = []
        self._mid_markers = []

    # ------------------------------------------------------------ gravação
    def _save(self):
        if self.fid is None or geometry_rules.unique_count(self.points) < MINIMUM[self.kind]:
            return
        pts = [self._to_layer(p) for p in self.points]
        try:
            if self.kind == "polygon":
                ring = list(pts)
                if ring[0] != ring[-1]:
                    ring.append(ring[0])
                geometry = QgsGeometry.fromPolygonXY([ring])
            elif self.kind == "line":
                geometry = QgsGeometry.fromPolylineXY(pts)
            else:
                geometry = QgsGeometry.fromPointXY(pts[0])
        except Exception:
            self._warn_save_failed("geometria inválida")
            self._load()
            return

        ok = False
        try:
            self.layer.startEditing()
            self.layer.changeGeometry(self.fid, geometry)
            # commitChanges() devolve False em alguns erros do provedor SEM
            # lancar excecao (ex.: arquivo bloqueado). Se so checarmos
            # exceptions, a tela mostra o vertice movido mas o GeoPackage
            # continua com a geometria antiga - falha silenciosa.
            ok = self.layer.commitChanges()
        except Exception:
            ok = False
        if not ok:
            try:
                self.layer.rollBack()
            except Exception:
                pass
            self._warn_save_failed("arquivo pode estar bloqueado por outro programa")
            # Recarrega da camada o que de fato foi gravado, para a tela nao
            # mostrar uma posicao que nunca chegou a ser salva.
            self._load()
            return

        self.layer.updateExtents()
        self.layer.triggerRepaint()
        self.changed.emit()

    def _warn_save_failed(self, detail):
        utils.log(
            "Falha ao gravar vertice da camada '{}' (fid={}): {}".format(
                self.layer.name(), self.fid, detail
            ),
            "critical",
        )
        if self.iface is not None:
            self.iface.messageBar().pushWarning(
                "GeoSketch",
                "Não foi possível gravar a alteração do vértice ({}). A "
                "posição foi revertida para o último estado salvo.".format(detail),
            )

    def restore_original(self):
        """Desfaz todas as mudancas de geometria feitas nesta sessao.

        Devolve True se o arquivo ficou mesmo igual ao original, False se a
        gravacao falhou (nesse caso o usuario ja foi avisado por aqui).
        """
        if self.fid is None or self.original_geometry is None:
            return True
        ok = False
        try:
            self.layer.startEditing()
            self.layer.changeGeometry(self.fid, self.original_geometry)
            ok = self.layer.commitChanges()
        except Exception:
            ok = False
        if not ok:
            try:
                self.layer.rollBack()
            except Exception:
                pass
            utils.log(
                "restore_original() falhou na camada '{}' (fid={}): Cancelar nao "
                "conseguiu reverter o arquivo.".format(self.layer.name(), self.fid),
                "critical",
            )
            if self.iface is not None:
                self.iface.messageBar().pushWarning(
                    "GeoSketch",
                    "Não foi possível desfazer as alterações de vértices no "
                    "arquivo. A geometria no mapa pode não refletir o que "
                    "está gravado - reabra o lugar para conferir.",
                )
            return False
        self.layer.updateExtents()
        self.layer.triggerRepaint()
        return True

    # ------------------------------------------------------------ limpeza
    def _leave(self):
        if self.iface is not None:
            self.iface.messageBar().pushInfo(
                "GeoSketch", "Edição de pontos encerrada."
            )
        self.canvas.unsetMapTool(self)

    def deactivate(self):
        self._clear_markers()
        try:
            self.band.reset(self.gtype)
            self.canvas.scene().removeItem(self.band)
        except Exception:
            pass
        try:
            self.canvas.scene().removeItem(self._snap_marker)
        except Exception:
            pass
        super(VertexEditTool, self).deactivate()

    def isEditTool(self):
        return True

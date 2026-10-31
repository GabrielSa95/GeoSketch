# -*- coding: utf-8 -*-
"""Aderência de vértices/segmentos durante o desenho e a edição (Fase C / C1).

Reaproveita o motor nativo do QGIS (QgsSnappingUtils/QgsSnappingConfig) em
vez de reimplementar um índice espacial - é exatamente o tipo de trabalho
complexo que o QGIS já resolve bem. Mas usa uma instância PRÓPRIA, nunca a
QgsProject.instance().snappingConfig(): escrever na configuração do projeto
mudaria o comportamento das ferramentas nativas de digitalização do QGIS
como efeito colateral, o que a Fase C proíbe explicitamente.

Tolerância em PIXELS de tela, não em unidades do SRC do projeto - mesma
escolha já usada no raio de captura de vértice (GRAB_PIXELS, em maptools.py
e vertexedit.py). Isso é deliberado: uma tolerância em metros se comportaria
de forma inconsistente num projeto com SRC geográfico (graus), e os valores
de pixel continuam corretos em qualquer zoom ou SRC.

A API exata de QgsSnappingConfig mudou entre versões do QGIS (de um enum
antigo QgsSnappingConfig.VertexAndSegment para flags Qgis.SnappingType nas
versões mais novas). Cada chamada aqui está protegida por try/except com
uma segunda tentativa na API antiga: se nenhuma das duas funcionar na
versão instalada, a aderência so se desliga (com um registro no painel de
diagnóstico), nunca quebra o desenho.
"""

from . import utils

DEFAULT_TOLERANCE_PX = 12


class SnapHelper(object):
    def __init__(self, canvas):
        self.canvas = canvas
        self.enabled = True
        self.tolerance_px = DEFAULT_TOLERANCE_PX
        self._utils = None
        self._broken = False

    def _get_utils(self):
        if self._broken:
            return None
        if self._utils is None:
            try:
                from qgis.gui import QgsSnappingUtils

                self._utils = QgsSnappingUtils()
            except Exception as exc:
                self._broken = True
                utils.log(
                    "Aderência nativa indisponível nesta versão do QGIS: {}".format(exc),
                    "warning",
                )
                return None
        try:
            self._utils.setMapSettings(self.canvas.mapSettings())
            self._utils.setConfig(self._build_config())
        except Exception as exc:
            self._broken = True
            utils.log("Falha ao configurar a aderência: {}".format(exc), "warning")
            return None
        return self._utils

    def _build_config(self):
        from qgis.core import QgsSnappingConfig, QgsTolerance

        config = QgsSnappingConfig()
        config.setEnabled(True)
        config.setMode(QgsSnappingConfig.AllLayers)
        try:
            from qgis.core import Qgis

            config.setTypeFlag(Qgis.SnappingTypes(Qgis.SnappingType.Vertex | Qgis.SnappingType.Segment))
        except Exception:
            try:
                config.setType(QgsSnappingConfig.VertexAndSegment)  # API de versoes antigas
            except Exception:
                pass
        config.setTolerance(self.tolerance_px)
        config.setUnits(QgsTolerance.Pixels)
        return config

    def resolve(self, pos, fallback_point):
        """pos = QPoint do evento (pixel na tela). fallback_point = QgsPointXY
        já em coordenadas do mapa, devolvido sem alteração se a aderência
        estiver desativada, indisponível, ou não achar nada perto.

        Devolve (ponto, aderiu: bool).
        """
        if not self.enabled:
            return fallback_point, False
        su = self._get_utils()
        if su is None:
            return fallback_point, False
        try:
            match = su.snapToMap(pos)
        except Exception:
            return fallback_point, False
        if match is not None and match.isValid():
            try:
                return match.point(), True
            except Exception:
                return fallback_point, False
        return fallback_point, False

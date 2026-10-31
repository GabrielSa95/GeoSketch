# -*- coding: utf-8 -*-
"""Regras puras de contagem de vertices, sem depender do PyQGIS.

Isoladas aqui para serem usadas tanto no desenho (maptools.py) quanto na
edicao de feicoes existentes (vertexedit.py), e para poderem ser testadas sem
precisar do ambiente do QGIS. So dependem de == / != entre pontos, entao
funcionam com QgsPointXY ou qualquer outro objeto comparavel por valor.
"""


def unique_count(points):
    """Quantidade de vertices distintos, ignorando repeticoes consecutivas."""
    count = 0
    prev = None
    for point in points:
        if prev is None or point != prev:
            count += 1
        prev = point
    return count


def dedup_consecutive(points):
    """Remove vertices repetidos que aparecem um atras do outro."""
    result = []
    for point in points:
        if not result or point != result[-1]:
            result.append(point)
    return result


def can_remove_vertex(points, index, minimum):
    """True se apagar points[index] ainda deixa vertices distintos suficientes."""
    if not (0 <= index < len(points)):
        return False
    candidate = list(points)
    candidate.pop(index)
    return unique_count(candidate) >= minimum


class UndoStack(object):
    """Pilha de desfazer/refazer sobre copias de uma lista de pontos.

    Generica de proposito: tanto a ferramenta de desenho (DrawTool, durante
    a criacao) quanto a de edicao de feicao existente (VertexEditTool) usam
    o mesmo padrao - guardar um snapshot ANTES de uma mudanca de vertice,
    resgatar no Ctrl+Z/Ctrl+Y - e cada uma decide separadamente o que fazer
    depois (so atualizar a tela, ou tambem regravar no GeoPackage).
    """

    def __init__(self, max_depth=200):
        self.max_depth = max_depth
        self._undo = []
        self._redo = []

    def push(self, points):
        """Chamado ANTES de aplicar uma mudanca, com o estado ainda antigo."""
        self._undo.append(list(points))
        self._redo = []
        if len(self._undo) > self.max_depth:
            self._undo.pop(0)

    def clear(self):
        self._undo = []
        self._redo = []

    def can_undo(self):
        return bool(self._undo)

    def can_redo(self):
        return bool(self._redo)

    def undo(self, current_points):
        """current_points = estado atual, guardado no redo antes de voltar.

        Devolve o estado anterior, ou None se nao havia nada para desfazer.
        """
        if not self._undo:
            return None
        self._redo.append(list(current_points))
        return self._undo.pop()

    def redo(self, current_points):
        if not self._redo:
            return None
        self._undo.append(list(current_points))
        return self._redo.pop()

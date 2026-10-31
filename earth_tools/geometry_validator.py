# -*- coding: utf-8 -*-
"""Validador de geometrias (Fase G1): examina as geometrias REAIS dos
lugares do plugin via a API de validação do próprio QGIS/GEOS
(`QgsGeometry.isGeosValid()`/`validateGeometry()`), nunca uma
reimplementação própria de regras topológicas.

Cada "problema" é uma tupla nomeada (ValidationIssue) com o suficiente
para a interface mostrar, localizar no mapa e decidir se oferece
correção. Nenhuma função aqui modifica a geometria de um lugar - isso é
responsabilidade explícita de quem chama (ver dlg_validate.py), sempre
criando uma cópia, nunca sobrescrevendo em silêncio.
"""

from collections import namedtuple

from qgis.core import (
    QgsCoordinateReferenceSystem,
    QgsCoordinateTransform,
    QgsGeometry,
    QgsProject,
    QgsWkbTypes,
)

from . import geometry_rules, utils

WGS84 = QgsCoordinateReferenceSystem("EPSG:4326")

ValidationIssue = namedtuple(
    "ValidationIssue", ["layer_id", "layer_name", "kind", "message", "location"]
)

# "kind" possiveis, na ordem em que sao checados:
EMPTY = "geometria_vazia"
INVALID = "geometria_invalida"
DUPLICATE_VERTEX = "vertices_duplicados"
UNCLOSED_RING = "anel_nao_fechado"
OUT_OF_BOUNDS = "fora_dos_limites"
OVERLAP = "sobreposicao"


def _extract_points(geometry):
    """Pontos (QgsPointXY) de qualquer geometria simples - usado só para a
    checagem de vértices duplicados consecutivos (reaproveita
    geometry_rules.unique_count/dedup_consecutive, a mesma regra já usada
    no desenho de linha/polígono)."""
    try:
        return [v.point() if hasattr(v, "point") else v for v in geometry.vertices()]
    except Exception:
        return []


def validate_feature_geometry(geometry, layer_id, layer_name):
    """Lista de ValidationIssue para UMA geometria. Não lança exceção -
    geometria realmente problemática (None, corrompida) também é um
    problema a reportar, não um erro de execução."""
    issues = []

    if geometry is None or geometry.isNull() or geometry.isEmpty():
        issues.append(
            ValidationIssue(layer_id, layer_name, EMPTY, "Geometria vazia ou nula.", None)
        )
        return issues

    if not geometry.isGeosValid():
        errors = geometry.validateGeometry()
        if errors:
            for err in errors:
                loc = err.where() if err.hasWhere() else None
                issues.append(
                    ValidationIssue(layer_id, layer_name, INVALID, err.what(), loc)
                )
        else:
            issues.append(
                ValidationIssue(
                    layer_id, layer_name, INVALID, "Geometria inválida (GEOS).", None
                )
            )

    points = _extract_points(geometry)
    if points and geometry_rules.unique_count(
        [(p.x(), p.y()) for p in points]
    ) < len(points):
        issues.append(
            ValidationIssue(
                layer_id, layer_name, DUPLICATE_VERTEX,
                "Há vértices consecutivos duplicados (mesma coordenada repetida).",
                points[0] if points else None,
            )
        )

    if QgsWkbTypes.geometryType(geometry.wkbType()) == QgsWkbTypes.PolygonGeometry:
        rings = geometry.asMultiPolygon() if geometry.isMultipart() else [geometry.asPolygon()]
        for polygon in rings:
            for ring in polygon:
                if ring and ring[0] != ring[-1]:
                    issues.append(
                        ValidationIssue(
                            layer_id, layer_name, UNCLOSED_RING,
                            "Anel do polígono não fecha no primeiro vértice.",
                            ring[0],
                        )
                    )

    return issues


def validate_layers(layers, reference_extent=None, check_overlaps=False):
    """layers: lista de QgsVectorLayer (1 feição cada, lugares do plugin).

    `reference_extent`, se informado, precisa estar em WGS84 (EPSG:4326) -
    cada geometria é transformada para WGS84 antes de comparar, já que os
    lugares podem estar em SRC diferentes entre si (Caminho pode estar num
    SRC escolhido pelo usuário desde a Fase 3; os demais, sempre WGS84).
    Comparar bounding boxes em CRS diferentes sem transformar daria um
    resultado sem sentido - por isso a transformação é feita aqui, nunca
    pulada.

    Devolve (issues, total_verificadas, total_validas) - "válida" = zero
    problemas encontrados para aquele lugar.
    """
    issues = []
    geometries = []  # (layer_id, layer_name, geometry) - só poligonos, pra sobreposicao
    valid_count = 0
    total = 0

    for layer in layers:
        features = list(layer.getFeatures())
        total += 1
        if not features:
            issues.append(
                ValidationIssue(
                    layer.id(), layer.name(), EMPTY, "Camada sem nenhuma feição.", None
                )
            )
            continue
        geometry = features[0].geometry()
        layer_issues = validate_feature_geometry(geometry, layer.id(), layer.name())

        if reference_extent is not None and geometry is not None and not geometry.isEmpty():
            bbox = geometry.boundingBox()
            layer_crs = layer.crs()
            if layer_crs.isValid() and layer_crs != WGS84:
                transform = QgsCoordinateTransform(layer_crs, WGS84, QgsProject.instance())
                try:
                    bbox = transform.transformBoundingBox(bbox)
                except Exception as exc:
                    utils.log(
                        "validate_layers: falha ao transformar bbox de '{}' para WGS84: "
                        "{}".format(layer.name(), exc),
                        "warning",
                    )
                    bbox = None
            if bbox is not None and not reference_extent.contains(bbox):
                layer_issues.append(
                    ValidationIssue(
                        layer.id(), layer.name(), OUT_OF_BOUNDS,
                        "Geometria fora da extensão de referência definida.",
                        bbox.center(),
                    )
                )

        if not layer_issues:
            valid_count += 1
        issues.extend(layer_issues)

        if geometry is not None and not geometry.isEmpty():
            if QgsWkbTypes.geometryType(geometry.wkbType()) == QgsWkbTypes.PolygonGeometry:
                geometries.append((layer.id(), layer.name(), geometry))

    if check_overlaps:
        for i in range(len(geometries)):
            for j in range(i + 1, len(geometries)):
                id1, name1, geom1 = geometries[i]
                id2, name2, geom2 = geometries[j]
                if geom1.intersects(geom2):
                    inter = geom1.intersection(geom2)
                    if inter is not None and not inter.isEmpty() and inter.area() > 0:
                        issues.append(
                            ValidationIssue(
                                id1, name1, OVERLAP,
                                "Sobrepõe \"{}\" em {:.2f} m² (medida planar aproximada, "
                                "só para localizar o problema).".format(name2, inter.area()),
                                inter.boundingBox().center(),
                            )
                        )

    return issues, total, valid_count


def make_valid_copy(geometry):
    """Devolve uma CÓPIA corrigida (QgsGeometry.makeValid(), algoritmo
    nativo do GEOS) - nunca modifica `geometry`. Devolve None se a
    correção automática não for seria segura (resultado ainda inválido ou
    vazio) - quem chama deve avisar que não há correção automática
    disponível nesse caso, não fingir sucesso."""
    corrigida = geometry.makeValid()
    if corrigida is None or corrigida.isEmpty() or not corrigida.isGeosValid():
        return None
    return corrigida

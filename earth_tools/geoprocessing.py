# -*- coding: utf-8 -*-
"""Geoprocessamento (Fase F): usa os algoritmos NATIVOS do QGIS Processing
por baixo dos panos (`processing.run`), nunca reimplementa um algoritmo que
o QGIS já resolve - este módulo só cuida de: reunir a geometria de entrada
(já no CRS certo), montar a camada temporária que o algoritmo espera,
chamar o algoritmo nativo, e devolver o resultado pronto para
`storage.create_place()`.

`import processing` é feito dentro de cada função (não no topo do módulo):
o framework de Processing do QGIS só está totalmente inicializado depois
que o QGIS termina de carregar os plugins núcleo - importar no topo
arriscaria falhar se este módulo for importado antes disso.
"""

from qgis.core import (
    QgsCoordinateTransform,
    QgsFeature,
    QgsGeometry,
    QgsProject,
    QgsVectorLayer,
    QgsWkbTypes,
)

GEOM_TYPE_NAME = {
    QgsWkbTypes.PointGeometry: "Point",
    QgsWkbTypes.LineGeometry: "LineString",
    QgsWkbTypes.PolygonGeometry: "Polygon",
}


class GeoprocessingError(Exception):
    """Erro de geoprocessamento com mensagem já pronta para mostrar ao
    usuário (QMessageBox) - nunca um traceback cru."""


def _memory_layer_for(geometry, crs):
    gtype = QgsWkbTypes.geometryType(geometry.wkbType())
    name = GEOM_TYPE_NAME.get(gtype)
    if name is None:
        raise GeoprocessingError("Tipo de geometria não suportado para geoprocessamento.")
    layer = QgsVectorLayer(name, "entrada", "memory")
    layer.setCrs(crs)
    feature = QgsFeature(layer.fields())
    feature.setGeometry(geometry)
    added, _ = layer.dataProvider().addFeatures([feature])
    if not added:
        raise GeoprocessingError("Não foi possível preparar a geometria de entrada.")
    layer.updateExtents()
    return layer


def _require_metric_crs(crs, campo):
    """Levanta GeoprocessingError se `crs` for geográfico (graus) - nunca
    deixa um algoritmo métrico (Buffer, distância) rodar em graus."""
    if crs is None or not crs.isValid():
        raise GeoprocessingError("{}: SRC inválido.".format(campo))
    if crs.isGeographic():
        raise GeoprocessingError(
            "{}: escolha um SRC PROJETADO (em metros), não geográfico (em graus) - "
            "ex.: SIRGAS 2000 / UTM da sua região. Calcular Buffer em graus geográficos "
            "produziria um resultado incorreto.".format(campo)
        )


def buffer_single(geometry, source_crs, distance_m, segments, processing_crs):
    """Buffer de UMA geometria (já em `source_crs`). Devolve uma
    QgsGeometry de polígono, já em `processing_crs`. Lança
    GeoprocessingError em caso de falha, com mensagem pronta para o
    usuário - nunca devolve um resultado inválido silenciosamente."""
    _require_metric_crs(processing_crs, "SRC de processamento")
    if distance_m == 0:
        raise GeoprocessingError("A distância do Buffer não pode ser zero.")

    geometry = QgsGeometry(geometry)
    if source_crs is not None and source_crs.isValid() and source_crs != processing_crs:
        transform = QgsCoordinateTransform(source_crs, processing_crs, QgsProject.instance())
        try:
            geometry.transform(transform)
        except Exception as exc:
            raise GeoprocessingError(
                "Não foi possível transformar a geometria para o SRC de "
                "processamento: {}".format(exc)
            )

    mem = _memory_layer_for(geometry, processing_crs)

    import processing

    try:
        result = processing.run(
            "native:buffer",
            {
                "INPUT": mem,
                "DISTANCE": distance_m,
                "SEGMENTS": segments,
                "END_CAP_STYLE": 0,
                "JOIN_STYLE": 0,
                "MITER_LIMIT": 2,
                "DISSOLVE": False,
                "OUTPUT": "memory:",
            },
        )
    except Exception as exc:
        raise GeoprocessingError("O algoritmo Buffer do QGIS falhou: {}".format(exc))

    out_layer = result.get("OUTPUT")
    if out_layer is None:
        raise GeoprocessingError("O Buffer não produziu uma camada de saída.")
    features = list(out_layer.getFeatures())
    if not features:
        raise GeoprocessingError("O Buffer não produziu nenhuma geometria.")
    out_geom = features[0].geometry()
    if out_geom is None or out_geom.isEmpty():
        raise GeoprocessingError("O Buffer produziu uma geometria vazia.")
    return out_geom


def run_buffer(inputs, distance_m, segments, dissolve, processing_crs):
    """inputs: lista de (QgsGeometry, QgsCoordinateReferenceSystem) - uma
    por lugar de origem. Devolve lista de QgsGeometry resultado, já em
    `processing_crs` (1 elemento se `dissolve` e houver mais de uma
    entrada; senão, uma por entrada - sem dissolver geometrias de uma
    única entrada, que não tem o que dissolver)."""
    if not inputs:
        raise GeoprocessingError("Nenhuma geometria de entrada para o Buffer.")
    results = [
        buffer_single(geom, crs, distance_m, segments, processing_crs) for geom, crs in inputs
    ]
    if dissolve and len(results) > 1:
        merged = results[0]
        for geom in results[1:]:
            merged = merged.combine(geom)
        if merged is None or merged.isEmpty():
            raise GeoprocessingError("Dissolver os resultados do Buffer produziu geometria vazia.")
        return [merged]
    return results


def union_polygons(inputs, target_crs):
    """União topológica (F2) de 2+ polígonos numa única geometria.

    inputs: lista de (QgsGeometry, QgsCoordinateReferenceSystem). Usa
    QgsGeometry.unaryUnion() - operação nativa do QGIS/GEOS, não uma
    reimplementação própria de união de polígonos. Não precisa de SRC
    métrico (união é puramente topológica, funciona em graus ou metros).
    """
    if len(inputs) < 2:
        raise GeoprocessingError("Selecione pelo menos 2 polígonos para unir.")
    geoms = []
    for geom, crs in inputs:
        g = reproject(geom, crs, target_crs)
        if QgsWkbTypes.geometryType(g.wkbType()) != QgsWkbTypes.PolygonGeometry:
            raise GeoprocessingError(
                "Só é possível unir polígonos - uma das entradas selecionadas não é "
                "um polígono."
            )
        geoms.append(g)
    unido = QgsGeometry.unaryUnion(geoms)
    if unido is None or unido.isEmpty():
        raise GeoprocessingError("A união não produziu uma geometria válida.")
    return unido


def split_polygon(polygon_geometry, polygon_crs, cut_line_geometry, cut_line_crs, target_crs):
    """Divide UM polígono por uma linha de corte (F3) usando o algoritmo
    nativo `native:splitwithlines`. Devolve lista de QgsGeometry (as
    partes resultantes), já em `target_crs`.

    O próprio algoritmo nativo já devolve a geometria ORIGINAL intacta,
    numa única feição, quando a linha não atravessa o polígono (confirmado
    contra o QGIS real: nenhuma exceção, só 1 feição de saída em vez de
    2+) - por isso a validação de "a linha atravessa de verdade" é feita
    checando o NÚMERO de partes devolvidas, não tentando prever a
    geometria antes de chamar o algoritmo.
    """
    polygon_geometry = reproject(polygon_geometry, polygon_crs, target_crs)
    cut_line_geometry = reproject(cut_line_geometry, cut_line_crs, target_crs)

    if QgsWkbTypes.geometryType(polygon_geometry.wkbType()) != QgsWkbTypes.PolygonGeometry:
        raise GeoprocessingError("A geometria a dividir precisa ser um polígono.")
    if QgsWkbTypes.geometryType(cut_line_geometry.wkbType()) != QgsWkbTypes.LineGeometry:
        raise GeoprocessingError("A linha de corte precisa ser uma linha.")

    poly_layer = _memory_layer_for(polygon_geometry, target_crs)
    line_layer = _memory_layer_for(cut_line_geometry, target_crs)

    import processing

    try:
        result = processing.run(
            "native:splitwithlines",
            {"INPUT": poly_layer, "LINES": line_layer, "OUTPUT": "memory:"},
        )
    except Exception as exc:
        raise GeoprocessingError("O algoritmo de divisão do QGIS falhou: {}".format(exc))

    out_layer = result.get("OUTPUT")
    if out_layer is None:
        raise GeoprocessingError("A divisão não produziu uma camada de saída.")
    parts = [f.geometry() for f in out_layer.getFeatures() if f.geometry() and not f.geometry().isEmpty()]
    if len(parts) < 2:
        raise GeoprocessingError(
            "A linha de corte não atravessa o polígono de um lado ao outro - "
            "nenhuma divisão foi produzida."
        )
    return parts


def clip_geometry(target_geometry, target_crs, mask_geometry, mask_crs, output_crs):
    """Recorta `target_geometry` usando `mask_geometry` (precisa ser um
    polígono) como máscara (F4), via `native:clip` - suporta ponto, linha
    e polígono como alvo (confirmado contra o QGIS real). Devolve uma
    única QgsGeometry (combina partes múltiplas com unaryUnion quando o
    recorte produz mais de uma), já em `output_crs`.
    """
    target_geometry = reproject(target_geometry, target_crs, output_crs)
    mask_geometry = reproject(mask_geometry, mask_crs, output_crs)

    if QgsWkbTypes.geometryType(mask_geometry.wkbType()) != QgsWkbTypes.PolygonGeometry:
        raise GeoprocessingError("A máscara de recorte precisa ser um polígono.")

    target_layer = _memory_layer_for(target_geometry, output_crs)
    mask_layer = _memory_layer_for(mask_geometry, output_crs)

    import processing

    try:
        result = processing.run(
            "native:clip",
            {"INPUT": target_layer, "OVERLAY": mask_layer, "OUTPUT": "memory:"},
        )
    except Exception as exc:
        raise GeoprocessingError("O algoritmo de recorte do QGIS falhou: {}".format(exc))

    out_layer = result.get("OUTPUT")
    if out_layer is None:
        raise GeoprocessingError("O recorte não produziu uma camada de saída.")
    parts = [
        f.geometry() for f in out_layer.getFeatures() if f.geometry() and not f.geometry().isEmpty()
    ]
    if not parts:
        raise GeoprocessingError(
            "O recorte não produziu nenhuma geometria - a entrada não intersecta a máscara."
        )
    if len(parts) == 1:
        return parts[0]
    combined = QgsGeometry.unaryUnion(parts)
    if combined is None or combined.isEmpty():
        raise GeoprocessingError("O recorte produziu partes que não puderam ser combinadas.")
    return combined


def difference_geometry(base_geometry, base_crs, subtract_geometry, subtract_crs, output_crs):
    """Diferença (F5): `base_geometry` MENOS a parte que se sobrepõe a
    `subtract_geometry`, via `native:difference`. Distinto do recorte
    (F4/`clip_geometry`): o recorte MANTÉM só o que está dentro da
    máscara; a diferença REMOVE o que está dentro da segunda geometria.
    """
    base_geometry = reproject(base_geometry, base_crs, output_crs)
    subtract_geometry = reproject(subtract_geometry, subtract_crs, output_crs)

    base_layer = _memory_layer_for(base_geometry, output_crs)
    subtract_layer = _memory_layer_for(subtract_geometry, output_crs)

    import processing

    try:
        result = processing.run(
            "native:difference",
            {"INPUT": base_layer, "OVERLAY": subtract_layer, "OUTPUT": "memory:"},
        )
    except Exception as exc:
        raise GeoprocessingError("O algoritmo de diferença do QGIS falhou: {}".format(exc))

    out_layer = result.get("OUTPUT")
    if out_layer is None:
        raise GeoprocessingError("A diferença não produziu uma camada de saída.")
    parts = [
        f.geometry() for f in out_layer.getFeatures() if f.geometry() and not f.geometry().isEmpty()
    ]
    if not parts:
        raise GeoprocessingError(
            "A diferença não deixou nenhuma geometria - a segunda geometria cobre "
            "totalmente a primeira."
        )
    if len(parts) == 1:
        return parts[0]
    combined = QgsGeometry.unaryUnion(parts)
    if combined is None or combined.isEmpty():
        raise GeoprocessingError("A diferença produziu partes que não puderam ser combinadas.")
    return combined


def reproject(geometry, source_crs, target_crs):
    """Transforma `geometry` (em `source_crs`) para `target_crs`. Devolve
    uma CÓPIA - nunca modifica a geometria original (requisito de
    preservar a geometria de entrada)."""
    if source_crs == target_crs:
        return QgsGeometry(geometry)
    geometry = QgsGeometry(geometry)
    transform = QgsCoordinateTransform(source_crs, target_crs, QgsProject.instance())
    geometry.transform(transform)
    return geometry

# -*- coding: utf-8 -*-
"""Ponte entre kml_io.py (puro, sem QGIS) e as camadas/pastas reais do
plugin (Fase D).

Responsabilidades:
  - importar: achatar a árvore neutra de kml_io em candidatos (um por
    geometria - MultiGeometry vira vários lugares, igual à exportação),
    marcar os já importados antes (tabela de controle própria, pelo mesmo
    padrão de bootstrap de places_model.py), criar as pastas do caminho do
    KML dentro da pasta de destino escolhida, e chamar storage.create_place
    para cada um.
  - exportar: ler uma camada existente (ou uma pasta canônica inteira, com
    subpastas) e devolver a mesma árvore neutra, para kml_io.build_kml/
    build_kmz serializar.

Coordenadas do KML já são WGS84 (lon, lat) por especificação - o mesmo CRS
que storage.create_place já exige. Na exportação, a conversão para WGS84
reaproveita utils.to_wgs84, já usada para isso em todo o resto do plugin.
"""

import os

from qgis.core import (
    QgsFeature,
    QgsField,
    QgsFields,
    QgsGeometry,
    QgsLayerTree,
    QgsPointXY,
    QgsProject,
    QgsVectorFileWriter,
    QgsVectorLayer,
)
from qgis.PyQt.QtCore import QVariant

from . import export_rules, kml_io, places_model, storage, utils

IMPORTS_TABLE = "_ferramentas_terra_importados"


class ExportError(Exception):
    """Erro de exportacao com uma categoria, para a janela escolher a
    mensagem certa (pasta invalida x pasta vazia x falha de leitura/
    escrita sao coisas diferentes para o usuario)."""

    def __init__(self, kind, message):
        super(ExportError, self).__init__(message)
        self.kind = kind  # "pasta_invalida" | "falha_leitura"


# ---------------------------------------------------------- tabela de controle
def _imports_fields():
    fields = QgsFields()
    fields.append(QgsField("fingerprint", QVariant.String, "", 64))
    fields.append(QgsField("tabela", QVariant.String, "", 254))
    fields.append(QgsField("origem", QVariant.String, "", 254))
    return fields


def _open_imports_table():
    path = storage.gpkg_path()
    if not os.path.exists(path):
        return None
    layer = QgsVectorLayer(
        "{}|layername={}".format(path, IMPORTS_TABLE), IMPORTS_TABLE, "ogr"
    )
    return layer if layer.isValid() else None


def _ensure_imports_table():
    if _open_imports_table() is not None:
        return
    path = storage.gpkg_path()
    mem = QgsVectorLayer("None", IMPORTS_TABLE, "memory")
    mem.dataProvider().addAttributes(_imports_fields())
    mem.updateFields()

    options = QgsVectorFileWriter.SaveVectorOptions()
    options.driverName = "GPKG"
    options.layerName = IMPORTS_TABLE
    options.fileEncoding = "UTF-8"
    if os.path.exists(path):
        options.actionOnExistingFile = QgsVectorFileWriter.CreateOrOverwriteLayer

    context = QgsProject.instance().transformContext()
    if hasattr(QgsVectorFileWriter, "writeAsVectorFormatV3"):
        result = QgsVectorFileWriter.writeAsVectorFormatV3(mem, path, context, options)
    else:
        result = QgsVectorFileWriter.writeAsVectorFormatV2(mem, path, context, options)
    if result[0] != QgsVectorFileWriter.NoError:
        raise IOError(result[1] or "erro ao criar tabela de controle de importação")


def already_imported_fingerprints():
    layer = _open_imports_table()
    if layer is None:
        return set()
    return {f["fingerprint"] for f in layer.getFeatures() if f["fingerprint"]}


def _register_import(fingerprint, tabela, origem):
    _ensure_imports_table()
    layer = _open_imports_table()
    if layer is None:
        return
    feature = QgsFeature(layer.fields())
    feature["fingerprint"] = fingerprint
    feature["tabela"] = tabela
    feature["origem"] = origem or ""
    layer.startEditing()
    try:
        if not layer.addFeature(feature):
            raise IOError("não foi possível registrar o item importado")
    except Exception:
        try:
            layer.rollBack()
        except Exception:
            pass
        raise
    storage._commit(layer)


# ------------------------------------------------------------------ importar
def flatten_candidates(folder):
    """Árvore neutra de kml_io -> lista de candidatos a lugar, um POR
    GEOMETRIA (um Placemark com MultiGeometry gera vários, com nomes
    desambiguados - mesma convenção usada em kml_io._placemark_xml)."""
    already = already_imported_fingerprints()
    out = []
    for path, placemark in kml_io.iter_placemarks(folder):
        geometries = placemark["geometries"]
        multi = len(geometries) > 1
        for i, geometry in enumerate(geometries):
            name = placemark.get("name") or "Sem título"
            if multi:
                name = "{} ({})".format(name, i + 1)
            fingerprint = kml_io.fingerprint(geometry["kind"], name, geometry["rings"])
            out.append(
                {
                    "path": path,
                    "name": name,
                    "description": placemark.get("description", ""),
                    "kind": geometry["kind"],
                    "rings": geometry["rings"],
                    "style": geometry.get("style") or {},
                    "fingerprint": fingerprint,
                    "already_imported": fingerprint in already,
                }
            )
    return out


def _build_geometry(kind, rings):
    if kind == "point":
        lon, lat = rings[0][0]
        return QgsGeometry.fromPointXY(QgsPointXY(lon, lat))
    if kind == "line":
        pts = [QgsPointXY(lon, lat) for lon, lat in rings[0]]
        return QgsGeometry.fromPolylineXY(pts)
    # polygon: primeiro anel = externo, os demais = buracos.
    ring_lists = []
    for ring in rings:
        pts = [QgsPointXY(lon, lat) for lon, lat in ring]
        if pts[0] != pts[-1]:
            pts.append(pts[0])
        ring_lists.append(pts)
    return QgsGeometry.fromPolygonXY(ring_lists)


def import_candidates(candidates, dest_folder_id, origem, iface=None):
    """Importa os candidatos selecionados (ver flatten_candidates) para
    dentro de dest_folder_id, recriando o caminho de pastas do KML como
    subpastas. Nenhuma exceção escapa: cada falha é registrada e reportada,
    o resto da importação continua. Devolve (quantidade_ok, falhas), onde
    falhas = [(nome, motivo), ...].
    """
    path_to_folder_id = {(): dest_folder_id or ""}

    def resolve_path(path):
        if path in path_to_folder_id:
            return path_to_folder_id[path]
        parent_id = resolve_path(path[:-1])
        try:
            fid = places_model.create_folder(path[-1] or "Sem nome", pai_id=parent_id)
        except Exception as exc:
            utils.log(
                "Falha ao criar pasta '{}' durante importação KML: {}".format(path, exc),
                "critical",
            )
            fid = parent_id  # degrada: usa o pai, nao trava a importacao inteira
        path_to_folder_id[path] = fid
        return fid

    ok = 0
    failures = []
    for candidate in candidates:
        try:
            folder_id = resolve_path(candidate["path"])
            geometry = _build_geometry(candidate["kind"], candidate["rings"])
            style = candidate.get("style") or {}
            attributes = {
                "descricao": candidate.get("description", ""),
                "cor_linha": style.get("line_color", storage.DEFAULT_STYLE["cor_linha"]),
                "cor_preenchimento": style.get(
                    "fill_color", storage.DEFAULT_STYLE["cor_preenchimento"]
                ),
                "largura_linha": style.get(
                    "line_width", storage.DEFAULT_STYLE["largura_linha"]
                ),
            }
            layer = storage.create_place(
                candidate["kind"], candidate["name"], geometry, attributes
            )
            table = storage.table_name(layer)
            if folder_id and table:
                places_model.set_place_folder(table, folder_id)
            if table:
                _register_import(candidate["fingerprint"], table, origem)
            ok += 1
        except Exception as exc:
            utils.log(
                "Falha ao importar '{}' do KML '{}': {}".format(
                    candidate.get("name"), origem, exc
                ),
                "critical",
            )
            failures.append((candidate.get("name", "?"), str(exc)))

    try:
        places_model.rebuild_layer_tree(iface)
    except Exception as exc:
        utils.log("rebuild_layer_tree falhou apos importacao KML: {}".format(exc), "warning")

    return ok, failures


# ------------------------------------------------------------------ exportar
def _geometry_to_rings(geometry, kind, crs):
    def to_wgs(point):
        wgs = utils.to_wgs84(QgsPointXY(point), crs)
        return (wgs.x(), wgs.y())

    if kind == "point":
        return [[to_wgs(geometry.asPoint())]]
    if kind == "line":
        return [[to_wgs(p) for p in geometry.asPolyline()]]
    try:
        rings = geometry.asPolygon()
    except Exception:
        rings = []
    return [[to_wgs(p) for p in ring] for ring in rings] or [[]]


def export_layer(layer):
    """Uma camada de lugar -> {"name", "folders": [], "placemarks": [um]}
    (árvore neutra de kml_io, pronta para build_kml/build_kmz). None se a
    camada não tiver feição (nao deveria acontecer, mas defensivo)."""
    kind = layer.customProperty(storage.CUSTOM_KEY) or "point"
    feature = next(layer.getFeatures(), None)
    if feature is None:
        return None
    rings = _geometry_to_rings(feature.geometry(), kind, layer.crs())
    style = storage.get_style(layer)
    placemark = {
        "name": layer.name(),
        "description": storage.get_description(layer),
        "geometries": [
            {
                "kind": kind,
                "rings": rings,
                "style": {
                    "line_color": style["cor_linha"],
                    "fill_color": style["cor_preenchimento"],
                    "line_width": style["largura_linha"],
                },
            }
        ],
    }
    return {"name": layer.name(), "folders": [], "placemarks": [placemark]}


def _tree_name_of(node):
    if QgsLayerTree.isGroup(node):
        return node.name()
    layer = node.layer()
    return layer.name() if layer is not None else ""


def _tree_children_of(node):
    return node.children()


def _tree_is_group(node):
    return QgsLayerTree.isGroup(node)


def _tree_is_place_layer(node):
    layer = node.layer()
    return layer is not None and storage.is_place_layer(layer)


def _tree_export_one(node):
    return export_layer(node.layer())


def export_folder_tree(folder_id, root_name=None, iface=None, include_subfolders=True):
    """Pasta (identificada por folder_id, nunca pelo nome exibido) + tudo
    visível dentro dela agora -> árvore neutra de kml_io.

    Lê a ÁRVORE VISÍVEL DO QGIS diretamente (QgsLayerTreeGroup/Layer), não
    a tabela de membership de places_model.py: aquela tabela só é
    atualizada quando o usuário usa "Mover para pasta..." ou salva o
    projeto, então um lugar criado pela barra e só arrastado visualmente
    para dentro de uma pasta ficava invisível para a exportação mesmo
    aparecendo na tela - esse era o defeito corrigido aqui. A árvore viva
    é a fonte da verdade no momento da exportação.

    folder_id="" exporta a partir da raiz do projeto (toda a
    "propriedade"). Levanta ExportError("pasta_invalida", ...) se
    folder_id não vazio não corresponder a nenhum grupo na árvore atual.
    Nunca devolve uma árvore "vazia" por engano de leitura: falhas ao
    exportar um item especifico viram entradas em `errors` (ver
    export_folder_tree_with_errors), nao silencio.
    """
    tree, _errors = export_folder_tree_with_errors(
        folder_id, root_name=root_name, iface=iface, include_subfolders=include_subfolders
    )
    return tree


def export_folder_tree_with_errors(folder_id, root_name=None, iface=None, include_subfolders=True):
    """Igual a export_folder_tree, mas também devolve a lista de falhas de
    leitura por item (nome, motivo) - para a janela avisar sem mascarar."""
    # Sincronizacoes de graca, nenhuma exigida para a exportacao funcionar
    # (que agora le a arvore direto): rebuild materializa uma pasta
    # canonica que por algum motivo ainda nao tenha um grupo na arvore
    # (ex.: criada mas o QGIS ainda nao foi reaberto); capture grava no
    # GeoPackage o que o usuario arrastou, para sobreviver a reabrir o
    # projeto sem salvar depois.
    if iface is not None:
        try:
            places_model.rebuild_layer_tree(iface)
        except Exception as exc:
            utils.log("rebuild_layer_tree falhou antes da exportacao: {}".format(exc), "warning")
        try:
            places_model.capture_layer_tree(iface)
        except Exception as exc:
            utils.log("capture_layer_tree falhou antes da exportacao: {}".format(exc), "warning")

    root = QgsProject.instance().layerTreeRoot()
    if not folder_id:
        group = root
        name = root_name or "Lugares"
    else:
        group = places_model.find_group_by_folder_id(root, folder_id)
        if group is None:
            raise ExportError(
                "pasta_invalida",
                "A pasta selecionada não foi encontrada na árvore de camadas. Ela "
                "pode ter sido removida ou renomeada - escolha a pasta novamente.",
            )
        name = root_name if root_name is not None else group.name()

    tree, errors = export_rules.collect_tree(
        group,
        _tree_name_of,
        _tree_children_of,
        _tree_is_group,
        _tree_is_place_layer,
        _tree_export_one,
        include_subfolders,
    )
    tree["name"] = name
    return tree, errors

# -*- coding: utf-8 -*-
"""Organizacao de lugares em pastas e subpastas (Fase B).

Decisao de arquitetura, deliberada: a hierarquia de pastas NAO e tratada
como a arvore de camadas do QGIS. A arvore de camadas (QgsLayerTreeGroup) e
so uma VISAO dessa hierarquia, descartavel e reconstruivel. A fonte da
verdade fica em duas tabelas sem geometria, dentro do MESMO GeoPackage
"Meus Lugares" que ja guarda os lugares:

  _ferramentas_terra_pastas   (id, nome, pai_id, modelo, visivel)
  _ferramentas_terra_lugares  (tabela, pasta_id)

Por que no GeoPackage e nao no projeto QGIS: um QgsLayerTreeGroup e as
propriedades customizadas de um no so sobrevivem se o PROJETO for salvo. O
GeoPackage e gravado a cada alteracao de lugar, independente do projeto.
Guardar a hierarquia ali garante que ela sobrevive mesmo se o usuario so
fechar o QGIS sem salvar o projeto, e permite reconstruir a organizacao em
qualquer projeto que carregue esse GeoPackage - exatamente o motivo de nao
tratar "pasta" como sinonimo de "grupo de camadas".

Duas direcoes de sincronizacao, cada uma com uma funcao dedicada:
  - rebuild_layer_tree(iface): GeoPackage -> arvore visivel. Roda ao abrir
    um projeto e depois de qualquer acao feita pelos dialogos do plugin.
    So MATERIALIZA o que falta; nunca apaga nem sobrescreve nome/visibilidade
    de um grupo que ja existe e ja esta ligado (evita desfazer uma mudanca
    feita na hora pelo usuario direto na arvore).
  - capture_layer_tree(iface): arvore visivel -> GeoPackage. Roda ao salvar
    o projeto. Captura o que o usuario arrastou/renomeou/mostrou-ocultou
    direto na arvore nativa, SO para grupos e lugares que o plugin criou/
    atribuiu (grupos nativos quaisquer, nao rastreados, ficam de fora -
    o plugin nao opina sobre organizacao que nao e dele).
"""

import os
import uuid

from qgis.core import (
    QgsExpression,
    QgsFeature,
    QgsFeatureRequest,
    QgsField,
    QgsFields,
    QgsLayerTree,
    QgsProject,
    QgsVectorFileWriter,
    QgsVectorLayer,
)
from qgis.PyQt.QtCore import QVariant

from . import folder_rules, storage, utils

FOLDERS_TABLE = "_ferramentas_terra_pastas"
MEMBERSHIP_TABLE = "_ferramentas_terra_lugares"
GROUP_FOLDER_KEY = "ferramentas_terra_pasta_id"

# Modelo inicial de organizacao de propriedade rural: (slug, nome exibido).
PROPERTY_TEMPLATE = [
    ("sede", "Sede"),
    ("area_imovel", "Área do Imóvel"),
    ("app", "APP"),
    ("reserva_legal", "Reserva Legal"),
    ("nascentes", "Nascentes"),
    ("outros", "Outros"),
]


# ---------------------------------------------------------------- tabelas
def _folder_fields():
    fields = QgsFields()
    fields.append(QgsField("id", QVariant.String, "", 32))
    fields.append(QgsField("nome", QVariant.String, "", 254))
    fields.append(QgsField("pai_id", QVariant.String, "", 32))
    fields.append(QgsField("modelo", QVariant.String, "", 32))
    fields.append(QgsField("visivel", QVariant.Int, "", 1))
    return fields


def _membership_fields():
    fields = QgsFields()
    fields.append(QgsField("tabela", QVariant.String, "", 254))
    fields.append(QgsField("pasta_id", QVariant.String, "", 32))
    return fields


def _open_table(table):
    """Abre (sem criar) uma tabela de gerenciamento, se ela ja existir."""
    path = storage.gpkg_path()
    if not os.path.exists(path):
        return None
    layer = QgsVectorLayer("{}|layername={}".format(path, table), table, "ogr")
    return layer if layer.isValid() else None


def _create_table(table, fields):
    path = storage.gpkg_path()
    mem = QgsVectorLayer("None", table, "memory")
    mem.dataProvider().addAttributes(fields)
    mem.updateFields()

    options = QgsVectorFileWriter.SaveVectorOptions()
    options.driverName = "GPKG"
    options.layerName = table
    options.fileEncoding = "UTF-8"
    if os.path.exists(path):
        options.actionOnExistingFile = QgsVectorFileWriter.CreateOrOverwriteLayer

    context = QgsProject.instance().transformContext()
    if hasattr(QgsVectorFileWriter, "writeAsVectorFormatV3"):
        result = QgsVectorFileWriter.writeAsVectorFormatV3(mem, path, context, options)
    else:
        result = QgsVectorFileWriter.writeAsVectorFormatV2(mem, path, context, options)
    if result[0] != QgsVectorFileWriter.NoError:
        raise IOError(result[1] or "erro desconhecido ao criar '{}'".format(table))


def _ensure_tables():
    """Cria as tabelas de gerenciamento se ainda nao existirem. So acontece
    quando uma funcao de pasta e de fato chamada - nunca no carregamento do
    plugin - para nao tocar em um GeoPackage que o usuario nunca organizou."""
    if _open_table(FOLDERS_TABLE) is None:
        _create_table(FOLDERS_TABLE, _folder_fields())
    if _open_table(MEMBERSHIP_TABLE) is None:
        _create_table(MEMBERSHIP_TABLE, _membership_fields())


def _find(layer, field, value):
    expr = QgsExpression.createFieldEqualityExpression(field, value)
    request = QgsFeatureRequest(QgsExpression(expr))
    for feature in layer.getFeatures(request):
        return feature
    return None


# ----------------------------------------------------------------- leitura
def list_folders():
    """{} se nenhuma pasta foi criada ainda (tabela nem existe)."""
    layer = _open_table(FOLDERS_TABLE)
    if layer is None:
        return {}
    out = {}
    for f in layer.getFeatures():
        visivel = f["visivel"]
        out[f["id"]] = {
            "nome": f["nome"] or "",
            "pai_id": f["pai_id"] or "",
            "modelo": f["modelo"] or "",
            "visivel": True if visivel is None else bool(visivel),
        }
    return out


def list_memberships():
    """{tabela: pasta_id} SO para lugares ja atribuidos a uma pasta alguma
    vez (ainda que a pasta_id seja "" = raiz). Ausencia na lista = o plugin
    nunca opinou sobre aquele lugar, e deve deixa-lo onde esta."""
    layer = _open_table(MEMBERSHIP_TABLE)
    if layer is None:
        return {}
    return {f["tabela"]: (f["pasta_id"] or "") for f in layer.getFeatures() if f["tabela"]}


def folder_choices():
    """[(id, "nome com indentacao por profundidade")], para popular um
    combo/lista de escolha, com os pais sempre antes dos filhos."""
    return folder_rules.build_folder_choices(list_folders())


def find_property_root(folder_id):
    """Id da pasta-mae "propriedade rural" que contem folder_id (ou a
    propria, se ja for a raiz), None se nao achar - usado pelo menu de
    contexto para oferecer "Exportar propriedade completa" a partir de
    qualquer subpasta do modelo (Sede, APP, Reserva Legal...)."""
    return folder_rules.find_property_root(list_folders(), folder_id)


# ------------------------------------------------------------------ pastas
def create_folder(nome, pai_id="", modelo=""):
    """Cria uma pasta nova e devolve o id gerado. Nao toca na arvore visivel
    - quem chamar deve rodar rebuild_layer_tree() depois para materializar."""
    nome = (nome or "").strip()
    if not nome:
        raise ValueError("nome da pasta nao pode ser vazio")
    _ensure_tables()
    layer = _open_table(FOLDERS_TABLE)
    if layer is None:
        raise IOError("não foi possível abrir a tabela de pastas")
    folder_id = uuid.uuid4().hex[:12]
    feature = QgsFeature(layer.fields())
    feature["id"] = folder_id
    feature["nome"] = nome
    feature["pai_id"] = pai_id or ""
    feature["modelo"] = modelo or ""
    feature["visivel"] = 1
    layer.startEditing()
    try:
        if not layer.addFeature(feature):
            raise IOError("não foi possível preparar a nova pasta")
    except Exception:
        try:
            layer.rollBack()
        except Exception:
            pass
        raise
    storage._commit(layer)
    return folder_id


def create_property_template(nome_imovel, pai_id=""):
    """Cria a pasta do imovel com as subpastas padrao (Sede, Área do
    Imóvel, APP, Reserva Legal, Nascentes, Outros). Devolve o id da pasta-mae."""
    raiz_id = create_folder(nome_imovel, pai_id=pai_id, modelo="propriedade_rural")
    for slug, nome in PROPERTY_TEMPLATE:
        create_folder(nome, pai_id=raiz_id, modelo=slug)
    return raiz_id


def rename_folder(folder_id, novo_nome):
    novo_nome = (novo_nome or "").strip()
    if not novo_nome:
        raise ValueError("nome da pasta nao pode ser vazio")
    layer = _open_table(FOLDERS_TABLE)
    if layer is None:
        return
    feature = _find(layer, "id", folder_id)
    if feature is None:
        return
    idx = layer.fields().indexOf("nome")
    layer.startEditing()
    try:
        if not layer.changeAttributeValue(feature.id(), idx, novo_nome):
            raise IOError("não foi possível renomear a pasta")
    except Exception:
        try:
            layer.rollBack()
        except Exception:
            pass
        raise
    storage._commit(layer)


def set_folder_visible(folder_id, visivel):
    layer = _open_table(FOLDERS_TABLE)
    if layer is None:
        return
    feature = _find(layer, "id", folder_id)
    if feature is None:
        return
    idx = layer.fields().indexOf("visivel")
    layer.startEditing()
    try:
        layer.changeAttributeValue(feature.id(), idx, 1 if visivel else 0)
    except Exception:
        try:
            layer.rollBack()
        except Exception:
            pass
        raise
    storage._commit(layer)


def delete_folder_record(folder_id):
    """Remove so a LINHA canonica da pasta (usado pela exclusao em
    layeractions.py, que ja decide o que fazer com o conteudo antes de
    chamar isto). Nao toca na arvore visivel."""
    layer = _open_table(FOLDERS_TABLE)
    if layer is None:
        return
    feature = _find(layer, "id", folder_id)
    if feature is None:
        return
    layer.startEditing()
    try:
        if not layer.deleteFeature(feature.id()):
            raise IOError("não foi possível apagar o registro da pasta")
    except Exception:
        try:
            layer.rollBack()
        except Exception:
            pass
        raise
    storage._commit(layer)
    _delete_memberships_of(folder_id)


def _delete_memberships_of(folder_id):
    """Remove as atribuicoes de lugar que apontavam para essa pasta (o
    lugar em si pode ja ter sido apagado tambem, ou nao - nao e decidido
    aqui)."""
    layer = _open_table(MEMBERSHIP_TABLE)
    if layer is None:
        return
    to_delete = [f.id() for f in layer.getFeatures() if (f["pasta_id"] or "") == folder_id]
    if not to_delete:
        return
    layer.startEditing()
    try:
        layer.deleteFeatures(to_delete)
    except Exception:
        try:
            layer.rollBack()
        except Exception:
            pass
        raise
    storage._commit(layer)


# ----------------------------------------------------------- lugares/pastas
def set_place_folder(tabela, pasta_id):
    """Atribui (ou remove, com pasta_id="") a pasta de um lugar, pela chave
    estavel storage.table_name(layer)."""
    if not tabela:
        return
    _ensure_tables()
    layer = _open_table(MEMBERSHIP_TABLE)
    if layer is None:
        raise IOError("não foi possível abrir a tabela de organização de lugares")
    feature = _find(layer, "tabela", tabela)
    layer.startEditing()
    try:
        if feature is None:
            novo = QgsFeature(layer.fields())
            novo["tabela"] = tabela
            novo["pasta_id"] = pasta_id or ""
            if not layer.addFeature(novo):
                raise IOError("não foi possível gravar a organização do lugar")
        else:
            idx = layer.fields().indexOf("pasta_id")
            if not layer.changeAttributeValue(feature.id(), idx, pasta_id or ""):
                raise IOError("não foi possível atualizar a organização do lugar")
    except Exception:
        try:
            layer.rollBack()
        except Exception:
            pass
        raise
    storage._commit(layer)


def remove_place_membership(tabela):
    """Chamado quando um lugar e apagado, para nao deixar linha orfa."""
    if not tabela:
        return
    layer = _open_table(MEMBERSHIP_TABLE)
    if layer is None:
        return
    feature = _find(layer, "tabela", tabela)
    if feature is None:
        return
    layer.startEditing()
    try:
        layer.deleteFeature(feature.id())
    except Exception:
        try:
            layer.rollBack()
        except Exception:
            pass
        raise
    storage._commit(layer)


def resolve_group_folder_id(group_node):
    """Id canonico da pasta ligada a esse grupo, ou "" se o grupo for None
    ou um grupo nativo qualquer, nao rastreado pelo plugin. Usado para
    decidir o pai de uma pasta nova a partir do grupo selecionado na arvore."""
    if group_node is None:
        return ""
    try:
        return group_node.customProperty(GROUP_FOLDER_KEY) or ""
    except Exception:
        return ""


# ------------------------------------------------------- arvore: materializar
def find_group_by_folder_id(node, folder_id):
    """Acha o QgsLayerTreeGroup ligado a folder_id (via GROUP_FOLDER_KEY),
    buscando recursivamente a partir de `node`. Publica de proposito: e
    reaproveitada por kml_bridge.py para resolver a pasta escolhida na
    exportacao pelo id estavel, nunca pelo nome exibido."""
    for child in node.children():
        if QgsLayerTree.isGroup(child):
            if child.customProperty(GROUP_FOLDER_KEY) == folder_id:
                return child
            found = find_group_by_folder_id(child, folder_id)
            if found is not None:
                return found
    return None


def _move_layer_to_group(root, layer, target_group):
    node = root.findLayer(layer.id())
    if node is None or node.parent() is target_group:
        return
    clone = node.clone()
    target_group.insertChildNode(0, clone)
    node.parent().removeChildNode(node)


def rebuild_layer_tree(iface):
    """GeoPackage -> arvore visivel. So cria o que falta e move lugares que
    tem pasta atribuida explicitamente; nunca apaga, renomeia ou re-oculta
    um grupo que ja existe (evita desfazer uma mudanca feita direto na
    arvore desde a ultima vez que isto rodou)."""
    try:
        folders = list_folders()
        if not folders:
            return
        root = QgsProject.instance().layerTreeRoot()
        created = {}
        for fid in folder_rules.resolution_order(folders):
            info = folders[fid]
            pai_id = info["pai_id"]
            parent_group = created.get(pai_id, root) if pai_id else root
            existing = find_group_by_folder_id(root, fid)
            if existing is None:
                existing = parent_group.insertGroup(0, info["nome"])
                existing.setCustomProperty(GROUP_FOLDER_KEY, fid)
                existing.setItemVisibilityChecked(bool(info["visivel"]))
            created[fid] = existing
        # Pastas fora de resolution_order (presas num ciclo de pai_id) ficam
        # sem materializar - dado corrompido, nao travamos o QGIS por isso.

        membership = list_memberships()
        for layer in QgsProject.instance().mapLayers().values():
            if not storage.is_place_layer(layer):
                continue
            table = storage.table_name(layer)
            if table is None or table not in membership:
                continue  # nunca foi atribuido pelo plugin - nao move
            pasta_id = membership[table]
            target = created.get(pasta_id, root) if pasta_id else root
            _move_layer_to_group(root, layer, target)
    except Exception as exc:
        utils.log("rebuild_layer_tree falhou: {}".format(exc), "critical")


# ---------------------------------------------------------- arvore: capturar
def capture_layer_tree(iface):
    """Arvore visivel -> GeoPackage. So para grupos com GROUP_FOLDER_KEY e
    para lugares cujo pai atual e um desses grupos (ou a raiz). Grupos
    nativos nao rastreados sao ignorados de proposito."""
    try:
        folders_layer = _open_table(FOLDERS_TABLE)
        membership_layer = _open_table(MEMBERSHIP_TABLE)
        if folders_layer is None and membership_layer is None:
            return  # pastas nunca foram usadas; nada para capturar

        root = QgsProject.instance().layerTreeRoot()
        tracked = {}  # python id do no -> folder_id

        def index_groups(node, parent_folder_id):
            for child in node.children():
                if not QgsLayerTree.isGroup(child):
                    continue
                fid = child.customProperty(GROUP_FOLDER_KEY)
                if fid:
                    tracked[id(child)] = fid
                    if folders_layer is not None:
                        _upsert_folder_from_tree(folders_layer, fid, child, parent_folder_id)
                    index_groups(child, fid)
                else:
                    index_groups(child, parent_folder_id)

        index_groups(root, "")

        if membership_layer is not None:
            for layer in QgsProject.instance().mapLayers().values():
                if not storage.is_place_layer(layer):
                    continue
                node = root.findLayer(layer.id())
                if node is None:
                    continue
                parent = node.parent()
                if parent is root:
                    pasta_id = ""
                elif id(parent) in tracked:
                    pasta_id = tracked[id(parent)]
                else:
                    continue  # dentro de um grupo nao rastreado - nao opina
                table = storage.table_name(layer)
                if table:
                    _upsert_membership(membership_layer, table, pasta_id)
    except Exception as exc:
        utils.log("capture_layer_tree falhou: {}".format(exc), "critical")


def _upsert_folder_from_tree(layer, folder_id, group_node, parent_folder_id):
    nome = group_node.name()
    visivel = 1 if group_node.itemVisibilityChecked() else 0
    feature = _find(layer, "id", folder_id)
    layer.startEditing()
    try:
        if feature is None:
            novo = QgsFeature(layer.fields())
            novo["id"] = folder_id
            novo["nome"] = nome
            novo["pai_id"] = parent_folder_id or ""
            novo["modelo"] = ""
            novo["visivel"] = visivel
            layer.addFeature(novo)
        else:
            fields = layer.fields()
            layer.changeAttributeValue(feature.id(), fields.indexOf("nome"), nome)
            layer.changeAttributeValue(
                feature.id(), fields.indexOf("pai_id"), parent_folder_id or ""
            )
            layer.changeAttributeValue(feature.id(), fields.indexOf("visivel"), visivel)
    except Exception:
        try:
            layer.rollBack()
        except Exception:
            pass
        raise
    storage._commit(layer)


def _upsert_membership(layer, tabela, pasta_id):
    feature = _find(layer, "tabela", tabela)
    layer.startEditing()
    try:
        if feature is None:
            novo = QgsFeature(layer.fields())
            novo["tabela"] = tabela
            novo["pasta_id"] = pasta_id
            layer.addFeature(novo)
        else:
            idx = layer.fields().indexOf("pasta_id")
            layer.changeAttributeValue(feature.id(), idx, pasta_id)
    except Exception:
        try:
            layer.rollBack()
        except Exception:
            pass
        raise
    storage._commit(layer)

# -*- coding: utf-8 -*-
"""Gravacao no GeoPackage "Meus Lugares".

Cada feicao vira SUA PROPRIA camada, com o nome que o usuario digitou. E o que
faz o polígono aparecer no painel Camadas como um item nomeado, igual ao item
"Area do Imovel" do Google Earth, em vez de sumir dentro de uma camada generica.

O GeoPackage aguenta centenas de camadas no mesmo arquivo, entao continua sendo
um arquivo so para levar embora ou mandar por e-mail.
"""

import os
import re
import unicodedata
from datetime import datetime

from qgis.core import (
    Qgis,
    QgsCoordinateReferenceSystem,
    QgsEditorWidgetSetup,
    QgsFeature,
    QgsField,
    QgsFields,
    QgsFillSymbol,
    QgsLineSymbol,
    QgsMarkerSymbol,
    QgsPalLayerSettings,
    QgsProject,
    QgsSingleSymbolRenderer,
    QgsTextBufferSettings,
    QgsTextFormat,
    QgsVectorFileWriter,
    QgsVectorLayer,
    QgsVectorLayerSimpleLabeling,
)
from qgis.PyQt.QtCore import QVariant
from qgis.PyQt.QtGui import QColor

from . import utils

GPKG_NAME = "Meus Lugares.gpkg"
CUSTOM_KEY = "ferramentas_terra"

WKB = {"point": "Point", "line": "LineString", "polygon": "Polygon"}


# ------------------------------------------------------------------ apoio
def gpkg_path():
    """Fica ao lado do projeto salvo; senao, na pasta do usuario."""
    project_file = QgsProject.instance().fileName()
    folder = os.path.dirname(project_file) if project_file else os.path.join(
        os.path.expanduser("~"), "Meus Lugares QGIS"
    )
    if not os.path.isdir(folder):
        try:
            os.makedirs(folder)
        except OSError:
            folder = os.path.expanduser("~")
    return os.path.join(folder, GPKG_NAME)


def slug(text):
    """Nome interno seguro para tabela do GeoPackage."""
    text = unicodedata.normalize("NFKD", str(text or ""))
    text = text.encode("ascii", "ignore").decode("ascii")
    text = re.sub(r"[^A-Za-z0-9]+", "_", text).strip("_").lower()
    return text[:48] or "feicao"


def existing_layer_names(path):
    """Nomes de tabela já usados, olhando TRÊS fontes.

    O ogr.Open sozinho não serve: ele falha quando o QGIS já está com o
    GeoPackage aberto, devolve conjunto vazio, e aí o nome se repete e a
    gravação sobrescreve a feição anterior. Somamos as camadas carregadas no
    projeto e um registro no próprio projeto para nunca ficar cego.
    """
    names = set()

    try:
        from osgeo import ogr

        ds = ogr.Open(path) if os.path.exists(path) else None
        if ds is not None:
            names |= {ds.GetLayerByIndex(i).GetName() for i in range(ds.GetLayerCount())}
            ds = None
    except Exception:
        pass

    for layer in QgsProject.instance().mapLayers().values():
        try:
            source = layer.source()
            if "layername=" in source:
                names.add(source.split("layername=")[-1].split("|")[0])
        except Exception:
            continue

    try:
        registered, _ = QgsProject.instance().readListEntry("FerramentasTerra", "tabelas")
        names |= set(registered or [])
    except Exception:
        pass

    return names


def _register_table(name):
    """Guarda o nome no projeto, para sobreviver a falhas de leitura do arquivo."""
    try:
        registered, _ = QgsProject.instance().readListEntry("FerramentasTerra", "tabelas")
        registered = list(registered or [])
        if name not in registered:
            registered.append(name)
        QgsProject.instance().writeEntry("FerramentasTerra", "tabelas", registered)
    except Exception:
        pass


def unique_table_name(path, base):
    """Nome único por construção: base + carimbo de tempo + contador se preciso."""
    taken = existing_layer_names(path)
    stamp = datetime.now().strftime("%Y%m%d%H%M%S")
    name = "{}_{}".format(base, stamp)
    counter = 2
    while name in taken:
        name = "{}_{}_{}".format(base, stamp, counter)
        counter += 1
    _register_table(name)
    return name


def next_default_name(kind):
    """Sugere 'Área 1', 'Área 2'… olhando o que já existe no projeto."""
    prefix = {"polygon": "Área", "line": "Caminho", "point": "Marcador"}[kind]
    highest = 0
    pattern = re.compile(r"^" + re.escape(prefix) + r"\s+(\d+)$", re.IGNORECASE)
    for layer in QgsProject.instance().mapLayers().values():
        try:
            match = pattern.match(layer.name().strip())
            if match:
                highest = max(highest, int(match.group(1)))
        except Exception:
            continue
    return "{} {}".format(prefix, highest + 1)


def unique_display_name(name):
    """Se já existe uma camada com esse nome, acrescenta (2), (3)…"""
    taken = set()
    for layer in QgsProject.instance().mapLayers().values():
        try:
            taken.add(layer.name())
        except Exception:
            continue
    if name not in taken:
        return name
    counter = 2
    while "{} ({})".format(name, counter) in taken:
        counter += 1
    return "{} ({})".format(name, counter)


def _fields():
    fields = QgsFields()
    fields.append(QgsField("nome", QVariant.String, "", 254))
    fields.append(QgsField("descricao", QVariant.String, "", 2000))
    fields.append(QgsField("criado_em", QVariant.String, "", 32))
    return fields


def _commit(layer):
    """Confirma uma edicao em andamento e verifica o retorno de verdade.

    layer.commitChanges() devolve False em alguns erros do provedor (ex.:
    arquivo bloqueado por outro programa) SEM lancar excecao. Um `try/except`
    sozinho nao pega isso, e o chamador acaba reportando sucesso para uma
    gravacao que nao aconteceu. Por isso aqui SEMPRE verificamos o booleano e
    propagamos a falha como excecao, para quem chamou decidir o que avisar.
    """
    if layer.commitChanges():
        return
    errors = layer.commitErrors()
    detail = "; ".join(errors) if errors else "falha ao gravar no GeoPackage"
    try:
        layer.rollBack()
    except Exception:
        pass
    utils.log("commitChanges() falhou em '{}': {}".format(layer.name(), detail), "critical")
    raise IOError(detail)


def _parse_color(text, fallback):
    try:
        parts = [int(p) for p in str(text).split(",")]
        if len(parts) == 3:
            parts.append(255)
        return QColor(*parts[:4])
    except Exception:
        return QColor(fallback)


# ------------------------------------------------------------- aparencia
def apply_style(layer, kind, line_color, fill_color, line_width, show_label=True):
    line = _parse_color(line_color, QColor(255, 255, 0))
    fill = _parse_color(fill_color, QColor(255, 255, 255, 90))

    try:
        if kind == "polygon":
            symbol = QgsFillSymbol.createSimple(
                {
                    "color": "{},{},{},{}".format(
                        fill.red(), fill.green(), fill.blue(), fill.alpha()
                    ),
                    "outline_color": "{},{},{},{}".format(
                        line.red(), line.green(), line.blue(), line.alpha()
                    ),
                    "outline_width": str(line_width),
                    "outline_width_unit": "MM",
                }
            )
        elif kind == "line":
            symbol = QgsLineSymbol.createSimple(
                {
                    "color": "{},{},{},{}".format(
                        line.red(), line.green(), line.blue(), line.alpha()
                    ),
                    "width": str(line_width),
                    "width_unit": "MM",
                }
            )
        else:
            symbol = QgsMarkerSymbol.createSimple(
                {
                    "name": "circle",
                    "color": "{},{},{},{}".format(
                        fill.red(), fill.green(), fill.blue(), 255
                    ),
                    "outline_color": "{},{},{},255".format(
                        line.red(), line.green(), line.blue()
                    ),
                    "size": "3.4",
                }
            )
        layer.setRenderer(QgsSingleSymbolRenderer(symbol))
    except Exception:
        pass

    if show_label:
        try:
            settings = QgsPalLayerSettings()
            settings.fieldName = "nome"
            text_format = QgsTextFormat()
            text_format.setSize(9)
            text_format.setColor(QColor(255, 255, 255))
            buffer_settings = QgsTextBufferSettings()
            buffer_settings.setEnabled(True)
            buffer_settings.setSize(0.8)
            buffer_settings.setColor(QColor(0, 0, 0))
            text_format.setBuffer(buffer_settings)
            settings.setFormat(text_format)
            layer.setLabeling(QgsVectorLayerSimpleLabeling(settings))
            layer.setLabelsEnabled(True)
        except Exception:
            pass

    try:
        idx = layer.fields().indexOf("descricao")
        if idx >= 0:
            layer.setEditorWidgetSetup(
                idx, QgsEditorWidgetSetup("TextEdit", {"IsMultiline": True})
            )
    except Exception:
        pass


# -------------------------------------------------------------- gravacao
def create_place(kind, display_name, geometry, attributes, parent_group=None, crs=None):
    """Cria uma camada nova com uma unica feicao e devolve a camada carregada.

    Por padrao (`crs=None`), `geometry` precisa estar em EPSG:4326 - mesmo
    comportamento de sempre, usado por marcador/caminho/poligono/regua.

    Quando `crs` e informado (Fase 3 - SRC do caminho na Regua), `geometry`
    precisa ja estar expressa NESSE SRC: a tabela e gravada no GeoPackage
    com esse SRC declarado, em vez de reprojetar para WGS84, para a camada
    sair pronta para uma operacao de Buffer sem distancia em graus.
    """
    path = gpkg_path()
    display_name = unique_display_name(display_name)
    table = unique_table_name(path, slug(display_name))

    target_crs = crs if crs is not None and crs.isValid() else QgsCoordinateReferenceSystem("EPSG:4326")

    uri = WKB[kind]
    if target_crs.authid():
        uri = "{}?crs={}".format(uri, target_crs.authid())
    mem = QgsVectorLayer(uri, table, "memory")
    # setCrs() de novo, de proposito: garante o SRC certo mesmo se o provedor
    # memory nao tiver aceitado o "?crs=" da URI (ex.: SRC sem authid EPSG).
    mem.setCrs(target_crs)
    mem.dataProvider().addAttributes(_fields())
    mem.updateFields()

    feature = QgsFeature(mem.fields())
    feature.setGeometry(geometry)
    feature["nome"] = display_name
    feature["descricao"] = attributes.get("descricao", "")
    feature["criado_em"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    added, _ = mem.dataProvider().addFeatures([feature])
    if not added:
        raise IOError("não foi possível preparar a feição antes de gravar")
    mem.updateExtents()

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
        raise IOError(result[1] or "erro desconhecido ao gravar")

    layer = QgsVectorLayer("{}|layername={}".format(path, table), display_name, "ogr")
    if not layer.isValid():
        raise IOError("camada gravada mas nao pode ser aberta: {}".format(table))

    layer.setCustomProperty(CUSTOM_KEY, kind)
    set_style(
        layer,
        kind,
        attributes.get("cor_linha", DEFAULT_STYLE["cor_linha"]),
        attributes.get("cor_preenchimento", DEFAULT_STYLE["cor_preenchimento"]),
        attributes.get("largura_linha", DEFAULT_STYLE["largura_linha"]),
    )

    QgsProject.instance().addMapLayer(layer, False)
    root = QgsProject.instance().layerTreeRoot()
    target = parent_group if parent_group is not None else root
    target.insertLayer(0, layer)
    return layer


DEFAULT_STYLE = {
    "cor_linha": "255,255,0,255",
    "cor_preenchimento": "255,255,255,90",
    "largura_linha": 1.0,
}


def set_style(layer, kind, line_color, fill_color, line_width):
    """Aplica o estilo E o guarda na camada, para a janela de edicao reabrir
    com os mesmos valores em vez de adivinhar a partir do simbolo."""
    apply_style(layer, kind, line_color, fill_color, line_width)
    try:
        layer.setCustomProperty(CUSTOM_KEY + "_cor_linha", str(line_color))
        layer.setCustomProperty(CUSTOM_KEY + "_cor_preenchimento", str(fill_color))
        layer.setCustomProperty(CUSTOM_KEY + "_largura_linha", str(line_width))
    except Exception:
        pass
    # Grava o estilo DENTRO do proprio GeoPackage (tabela layer_styles do
    # provedor), nao so no customProperty (que so sobrevive se o PROJETO
    # QGIS for salvo e reaberto). Confirmado contra o QGIS 3.44.15 real:
    # uma camada reaberta do ZERO (sem projeto nenhum) a partir do mesmo
    # .gpkg ja chega com este estilo aplicado automaticamente, porque
    # useAsDefault=True. Sem isso, abrir o GeoPackage fora do projeto
    # salvo perderia a cor/espessura escolhidas.
    try:
        caps = layer.dataProvider().styleStorageCapabilities()
        # NAO usar "in" aqui: Qgis.ProviderStyleStorageCapabilities nao e'
        # iteravel/container nesse binding (confirmado contra o QGIS real -
        # "in" lanca TypeError, que o except abaixo engoliria em silencio,
        # fazendo esta funcao parecer persistir o estilo sem persistir de
        # verdade). Checagem de flag bit a bit, com "&".
        if caps & Qgis.ProviderStyleStorageCapability.SaveToDatabase:
            layer.saveStyleToDatabase("default", "GeoSketch", True, "")
    except Exception as exc:
        utils.log(
            "Nao foi possivel gravar o estilo no GeoPackage (so no projeto, se salvo): "
            "{}".format(exc),
            "warning",
        )


def get_style(layer):
    style = dict(DEFAULT_STYLE)
    try:
        for key in ("cor_linha", "cor_preenchimento", "largura_linha"):
            value = layer.customProperty(CUSTOM_KEY + "_" + key)
            if value not in (None, ""):
                style[key] = value
        style["largura_linha"] = float(style["largura_linha"])
    except Exception:
        pass
    return style


def get_description(layer):
    try:
        for feature in layer.getFeatures():
            return feature["descricao"] or ""
    except Exception:
        pass
    return ""


def set_description(layer, text):
    """Grava a descricao. Lanca excecao se a gravacao falhar, em vez de
    engolir o erro - quem chamar precisa saber que nao foi salvo."""
    idx = layer.fields().indexOf("descricao")
    if idx < 0:
        return
    layer.startEditing()
    try:
        for feature in layer.getFeatures():
            layer.changeAttributeValue(feature.id(), idx, text)
    except Exception:
        try:
            layer.rollBack()
        except Exception:
            pass
        raise
    _commit(layer)


def is_place_layer(layer):
    try:
        return layer is not None and layer.customProperty(CUSTOM_KEY) is not None
    except Exception:
        return False


def rename_place(layer, new_name):
    """Renomeia a camada e o atributo nome da feicao.

    Lanca excecao se a gravacao do atributo falhar - a camada ja teria o
    nome novo no painel, mas o arquivo ficaria com o nome antigo, o que
    confundiria quem reabrisse o lugar depois.
    """
    layer.setName(new_name)
    idx = layer.fields().indexOf("nome")
    if idx < 0:
        return
    layer.startEditing()
    try:
        for feature in layer.getFeatures():
            layer.changeAttributeValue(feature.id(), idx, new_name)
    except Exception:
        try:
            layer.rollBack()
        except Exception:
            pass
        raise
    _commit(layer)
    layer.triggerRepaint()


def table_name(layer):
    """Nome da tabela daquele lugar dentro do GeoPackage, ou None.

    E a chave estavel usada para associar um lugar a uma pasta (ver
    places_model.py): nao muda quando o usuario renomeia o lugar, so quando
    a tabela em si e recriada.
    """
    try:
        source = layer.source()
    except Exception:
        return None
    if "layername=" in source:
        return source.split("layername=")[-1].split("|")[0]
    return None


def delete_place(layer):
    """Tira do projeto e apaga a tabela do GeoPackage.

    Devolve True se a tabela foi mesmo removida do arquivo; False se a
    camada saiu do painel mas a tabela continua la (ex.: arquivo bloqueado
    por outro programa) - nesse caso o chamador precisa avisar o usuario,
    em vez de dar a entender que a exclusao foi completa.
    """
    source = layer.source()
    table = table_name(layer)
    path = source.split("|")[0]

    QgsProject.instance().removeMapLayer(layer.id())

    if not table:
        return True

    removed = False
    try:
        from osgeo import ogr

        ds = ogr.Open(path, 1)
        if ds is not None:
            for i in range(ds.GetLayerCount()):
                if ds.GetLayerByIndex(i).GetName() == table:
                    removed = ds.DeleteLayer(i) == 0
                    break
            ds = None
    except Exception as exc:
        utils.log(
            "Falha ao apagar a tabela '{}' do GeoPackage '{}': {}".format(table, path, exc),
            "critical",
        )
        return False
    if not removed:
        utils.log(
            "DeleteLayer nao confirmou a remocao da tabela '{}' em '{}'.".format(table, path),
            "warning",
        )
    return removed

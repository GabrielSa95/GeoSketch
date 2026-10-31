# -*- coding: utf-8 -*-
"""Leitura e escrita de KML/KMZ, sem depender do PyQGIS (Fase D).

Zero import de qgis.* de propósito - mesmo motivo de geometry_rules.py,
folder_rules.py e measure_rules.py: fica testável com `python -m unittest`
puro, e é a maior parte da lógica desta fase que realmente pode ser
automatizada (o resto depende do QGIS para virar camada/feição de verdade -
ver kml_bridge.py).

Árvore neutra devolvida pelo parser (dicts simples, sem classes):

    folder = {
        "name": str,
        "folders": [folder, ...],
        "placemarks": [placemark, ...],
    }
    placemark = {
        "name": str,
        "description": str,
        "geometries": [geometry, ...],   # >1 = MultiGeometry
    }
    geometry = {
        "kind": "point" | "line" | "polygon",
        "rings": [[(lon, lat), ...], ...],  # 1 anel p/ ponto/linha;
                                             # p/ poligono: [externo, buraco1, ...]
        "style": {"line_color": "r,g,b,a", "fill_color": "r,g,b,a",
                   "line_width": float, "icon_href": str|None},
    }

Coordenadas sempre em graus decimais WGS84 (lon, lat), exatamente como o
KML define e exatamente o que storage.create_place já espera - por isso
nenhuma transformação de CRS é necessária na ponte com o QGIS.
"""

import hashlib
import re
import xml.etree.ElementTree as ET
import zipfile
from io import BytesIO

KML_NS = "{http://www.opengis.net/kml/2.2}"
# Alguns arquivos nao declaram o namespace 2.2 explicitamente, ou usam 2.0/2.1.
NS_CANDIDATES = [
    "http://www.opengis.net/kml/2.2",
    "http://www.opengis.net/kml/2.1",
    "http://www.opengis.net/kml/2.0",
    "",
]


class KmlError(Exception):
    """Arquivo ilegível ou malformado - mensagem já pensada para o usuário."""


# ------------------------------------------------------------- utilitarios
def _local(tag):
    """Remove o namespace de uma tag ('{ns}Folder' -> 'Folder')."""
    return tag.rsplit("}", 1)[-1]


def _find_root(data):
    try:
        root = ET.fromstring(data)
    except ET.ParseError as exc:
        raise KmlError("XML malformado: {}".format(exc))
    if _local(root.tag) != "kml":
        # Alguns arquivos (raros) comecam direto no Document/Folder.
        return root
    for child in root:
        if _local(child.tag) in ("Document", "Folder"):
            return child
    # KML valido sem Document/Folder (Placemark direto sob <kml>): o
    # proprio elemento <kml> e tratado como raiz - _parse_folder so olha
    # para os filhos, nao para a tag do container.
    return root


def _child(elem, name):
    for c in elem:
        if _local(c.tag) == name:
            return c
    return None


def _children(elem, name):
    return [c for c in elem if _local(c.tag) == name]


def _text(elem, name, default=""):
    c = _child(elem, name)
    if c is None or c.text is None:
        return default
    return c.text.strip()


# ------------------------------------------------------------------- cores
def kml_color_to_rgba(value):
    """KML usa 'aabbggrr' (alfa, azul, verde, vermelho - ordem invertida
    da usual). Devolve 'r,g,b,a' (0-255), formato já usado em storage.py.
    Valor ausente/invalido -> None (quem chamar decide o padrao)."""
    if not value:
        return None
    text = value.strip().lstrip("#")
    if len(text) != 8 or not re.match(r"^[0-9a-fA-F]{8}$", text):
        return None
    aa, bb, gg, rr = text[0:2], text[2:4], text[4:6], text[6:8]
    r, g, b, a = int(rr, 16), int(gg, 16), int(bb, 16), int(aa, 16)
    return "{},{},{},{}".format(r, g, b, a)


def rgba_to_kml_color(value):
    """Inverso de kml_color_to_rgba: 'r,g,b,a' -> 'aabbggrr'."""
    try:
        parts = [int(p) for p in str(value).split(",")]
        if len(parts) == 3:
            parts.append(255)
        r, g, b, a = parts[:4]
    except Exception:
        r, g, b, a = 255, 255, 0, 255
    return "{:02x}{:02x}{:02x}{:02x}".format(a, b, g, r)


# -------------------------------------------------------------- coordenadas
def _parse_coordinates_text(text):
    """'lon,lat,alt lon,lat,alt ...' -> [(lon, lat), ...]. Altitude
    ignorada (o plugin e 2D). Tuplas com coordenada fora do intervalo
    valido (lon fora de -180..180 ou lat fora de -90..90) sao descartadas,
    nao travam o parse inteiro."""
    if not text:
        return []
    points = []
    for token in text.split():
        parts = token.split(",")
        if len(parts) < 2:
            continue
        try:
            lon, lat = float(parts[0]), float(parts[1])
        except ValueError:
            continue
        if -180.0 <= lon <= 180.0 and -90.0 <= lat <= 90.0:
            points.append((lon, lat))
    return points


def _parse_point(elem):
    coords = _child(elem, "coordinates")
    pts = _parse_coordinates_text(coords.text if coords is not None else "")
    if not pts:
        return None
    return {"kind": "point", "rings": [[pts[0]]]}


def _parse_linestring(elem):
    coords = _child(elem, "coordinates")
    pts = _parse_coordinates_text(coords.text if coords is not None else "")
    if len(pts) < 2:
        return None
    return {"kind": "line", "rings": [pts]}


def _parse_polygon(elem):
    outer_tag = _child(elem, "outerBoundaryIs")
    if outer_tag is None:
        return None
    outer_ring_tag = _child(outer_tag, "LinearRing")
    coords = _child(outer_ring_tag, "coordinates") if outer_ring_tag is not None else None
    outer = _parse_coordinates_text(coords.text if coords is not None else "")
    if len(outer) < 3:
        return None
    rings = [outer]
    for inner_tag in _children(elem, "innerBoundaryIs"):
        inner_ring_tag = _child(inner_tag, "LinearRing")
        inner_coords = _child(inner_ring_tag, "coordinates") if inner_ring_tag is not None else None
        inner = _parse_coordinates_text(inner_coords.text if inner_coords is not None else "")
        if len(inner) >= 3:
            rings.append(inner)
    return {"kind": "polygon", "rings": rings}


_GEOMETRY_PARSERS = {
    "Point": _parse_point,
    "LineString": _parse_linestring,
    "LinearRing": _parse_linestring,
    "Polygon": _parse_polygon,
}


def _parse_geometry_element(elem, unsupported):
    tag = _local(elem.tag)
    if tag == "MultiGeometry":
        out = []
        for child in elem:
            out.extend(_parse_geometry_element(child, unsupported))
        return out
    parser = _GEOMETRY_PARSERS.get(tag)
    if parser is None:
        if tag not in ("Point", "LineString", "LinearRing", "Polygon", "MultiGeometry"):
            unsupported.append(tag)
        return []
    geom = parser(elem)
    return [geom] if geom else []


# ------------------------------------------------------------------ estilos
def _parse_style(styles_by_id, style_url):
    if not style_url:
        return {}
    key = style_url.lstrip("#")
    return styles_by_id.get(key, {})


def _collect_styles(root):
    """{id: {line_color, fill_color, line_width, icon_href}} - so estilos
    simples (Style); StyleMap normal/highlight usa o primeiro Pair (normal),
    ja e o suficiente para o que o plugin preserva."""
    styles = {}
    style_map_refs = {}
    for elem in root.iter():
        tag = _local(elem.tag)
        if tag == "Style":
            style_id = elem.get("id")
            if not style_id:
                continue
            entry = {}
            line_tag = _child(elem, "LineStyle")
            if line_tag is not None:
                color = kml_color_to_rgba(_text(line_tag, "color"))
                if color:
                    entry["line_color"] = color
                width = _text(line_tag, "width")
                if width:
                    try:
                        entry["line_width"] = float(width)
                    except ValueError:
                        pass
            poly_tag = _child(elem, "PolyStyle")
            if poly_tag is not None:
                color = kml_color_to_rgba(_text(poly_tag, "color"))
                if color:
                    entry["fill_color"] = color
            icon_tag = _child(elem, "IconStyle")
            if icon_tag is not None:
                icon = _child(icon_tag, "Icon")
                href = _text(icon, "href") if icon is not None else ""
                if href:
                    entry["icon_href"] = href
            styles[style_id] = entry
        elif tag == "StyleMap":
            style_id = elem.get("id")
            if not style_id:
                continue
            for pair in _children(elem, "Pair"):
                if _text(pair, "key") == "normal":
                    style_map_refs[style_id] = _text(pair, "styleUrl").lstrip("#")
    for style_id, target in style_map_refs.items():
        if target in styles:
            styles[style_id] = styles[target]
    return styles


# ------------------------------------------------------------------- folder
def _parse_placemark(elem, styles_by_id, unsupported):
    name = _text(elem, "name", "")
    description = _text(elem, "description", "")
    style = _parse_style(styles_by_id, _text(elem, "styleUrl"))
    inline_style_tag = _child(elem, "Style")
    if inline_style_tag is not None:
        inline = _collect_styles_from_single(inline_style_tag)
        style = dict(style)
        style.update(inline)

    geometries = []
    for child in elem:
        tag = _local(child.tag)
        if tag in ("Point", "LineString", "LinearRing", "Polygon", "MultiGeometry"):
            for geom in _parse_geometry_element(child, unsupported):
                geom["style"] = style
                geometries.append(geom)
    if not geometries:
        return None
    return {"name": name, "description": description, "geometries": geometries}


def _collect_styles_from_single(style_elem):
    entry = {}
    line_tag = _child(style_elem, "LineStyle")
    if line_tag is not None:
        color = kml_color_to_rgba(_text(line_tag, "color"))
        if color:
            entry["line_color"] = color
        width = _text(line_tag, "width")
        if width:
            try:
                entry["line_width"] = float(width)
            except ValueError:
                pass
    poly_tag = _child(style_elem, "PolyStyle")
    if poly_tag is not None:
        color = kml_color_to_rgba(_text(poly_tag, "color"))
        if color:
            entry["fill_color"] = color
    return entry


def _parse_folder(elem, styles_by_id, unsupported):
    name = _text(elem, "name", "")
    folders, placemarks = [], []
    for child in elem:
        tag = _local(child.tag)
        if tag in ("Folder", "Document"):
            folders.append(_parse_folder(child, styles_by_id, unsupported))
        elif tag == "Placemark":
            placemark = _parse_placemark(child, styles_by_id, unsupported)
            if placemark is not None:
                placemarks.append(placemark)
        elif tag in ("NetworkLink", "PhotoOverlay", "GroundOverlay", "ScreenOverlay", "Tour"):
            unsupported.append(tag)
    return {"name": name, "folders": folders, "placemarks": placemarks}


def parse_kml(data):
    """bytes/str de um .kml -> (folder_raiz, lista_de_tags_nao_suportadas).

    Lanca KmlError se o XML nao puder ser interpretado. Elementos
    desconhecidos/nao suportados sao reportados na lista, nao travam o
    resto do parse.
    """
    if isinstance(data, bytes):
        text = data
    else:
        text = data.encode("utf-8")
    root = _find_root(text)
    styles_by_id = _collect_styles(root)
    unsupported = []
    folder = _parse_folder(root, styles_by_id, unsupported)
    return folder, unsupported


def parse_kmz(data):
    """bytes de um .kmz -> (folder_raiz, unsupported, assets).

    assets = {nome_dentro_do_zip: bytes}, para os arquivos que NAO sejam o
    .kml principal (ex.: imagens de icone referenciadas por IconStyle/href).
    """
    try:
        zf = zipfile.ZipFile(BytesIO(data))
    except zipfile.BadZipFile as exc:
        raise KmlError("Arquivo KMZ corrompido ou não é um ZIP válido: {}".format(exc))
    names = zf.namelist()
    kml_names = [n for n in names if n.lower().endswith(".kml")]
    if not kml_names:
        raise KmlError("O KMZ não contém nenhum arquivo .kml dentro.")
    main = "doc.kml" if "doc.kml" in kml_names else kml_names[0]
    kml_bytes = zf.read(main)
    assets = {n: zf.read(n) for n in names if n != main and not n.endswith("/")}
    folder, unsupported = parse_kml(kml_bytes)
    return folder, unsupported, assets


def load_file(path):
    """Caminho .kml ou .kmz -> (folder_raiz, unsupported, assets).

    Detecta o tipo pelo conteúdo (assinatura ZIP), não só pela extensão -
    um .kml que na verdade é um .kmz renomeado (ou vice-versa) ainda abre
    certo. Lança KmlError com uma mensagem pensada para o usuário se o
    arquivo não puder ser lido de nenhuma forma.
    """
    try:
        with open(path, "rb") as f:
            data = f.read()
    except OSError as exc:
        raise KmlError("Não foi possível abrir o arquivo:\n{}".format(exc))
    if not data:
        raise KmlError("O arquivo está vazio.")
    if data[:2] == b"PK":  # assinatura de arquivo ZIP
        folder, unsupported, assets = parse_kmz(data)
        return folder, unsupported, assets
    folder, unsupported = parse_kml(data)
    return folder, unsupported, {}


# --------------------------------------------------------------- contagem
def count_placemarks(folder):
    total = len(folder["placemarks"])
    for sub in folder["folders"]:
        total += count_placemarks(sub)
    return total


def iter_placemarks(folder, path=()):
    """Gera (caminho_de_pastas, placemark) para cada placemark na árvore,
    caminho_de_pastas = tupla de nomes de pasta da raiz até o placemark."""
    for placemark in folder["placemarks"]:
        yield path, placemark
    for sub in folder["folders"]:
        sub_path = path + (sub["name"] or "",)
        for item in iter_placemarks(sub, sub_path):
            yield item


# -------------------------------------------------------------- deduplicacao
def fingerprint(kind, name, rings):
    """Hash estavel para detectar reimportacao do mesmo item. Arredonda a
    coordenada a 7 casas decimais (~1 cm) para nao variar por ruido de
    ponto flutuante entre exportacao e reimportacao."""
    parts = [kind, name or ""]
    for ring in rings:
        for lon, lat in ring:
            parts.append("{:.7f},{:.7f}".format(lon, lat))
    digest = hashlib.sha1("|".join(parts).encode("utf-8")).hexdigest()
    return digest


# -------------------------------------------------------------- serializacao
def _escape(text):
    return (
        (text or "")
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )


def _coords_text(ring):
    return " ".join("{:.8f},{:.8f},0".format(lon, lat) for lon, lat in ring)


def _geometry_xml(geometry):
    kind = geometry["kind"]
    rings = geometry["rings"]
    if kind == "point":
        return "<Point><coordinates>{}</coordinates></Point>".format(
            _coords_text(rings[0])
        )
    if kind == "line":
        return "<LineString><coordinates>{}</coordinates></LineString>".format(
            _coords_text(rings[0])
        )
    # polygon
    outer = "<outerBoundaryIs><LinearRing><coordinates>{}</coordinates>" \
            "</LinearRing></outerBoundaryIs>".format(_coords_text(rings[0]))
    inners = "".join(
        "<innerBoundaryIs><LinearRing><coordinates>{}</coordinates>"
        "</LinearRing></innerBoundaryIs>".format(_coords_text(r))
        for r in rings[1:]
    )
    return "<Polygon>{}{}</Polygon>".format(outer, inners)


def _style_xml(style, style_id):
    if not style:
        return ""
    line_color = style.get("line_color")
    fill_color = style.get("fill_color")
    width = style.get("line_width")
    parts = ["<Style id=\"{}\">".format(style_id)]
    if line_color:
        parts.append(
            "<LineStyle><color>{}</color><width>{}</width></LineStyle>".format(
                rgba_to_kml_color(line_color), width if width else 1.0
            )
        )
    if fill_color:
        parts.append("<PolyStyle><color>{}</color></PolyStyle>".format(rgba_to_kml_color(fill_color)))
    parts.append("</Style>")
    return "".join(parts)


def _placemark_xml(placemark, index):
    pieces = []
    for gi, geometry in enumerate(placemark["geometries"]):
        style_id = "s{}_{}".format(index, gi)
        name = placemark["name"]
        if len(placemark["geometries"]) > 1:
            name = "{} ({})".format(name, gi + 1)
        pieces.append(
            "<Placemark>"
            "<name>{}</name>"
            "<description><![CDATA[{}]]></description>"
            "{}"
            "<styleUrl>#{}</styleUrl>"
            "{}"
            "</Placemark>".format(
                _escape(name),
                placemark.get("description") or "",
                _style_xml(geometry.get("style"), style_id),
                style_id,
                _geometry_xml(geometry),
            )
        )
    return "".join(pieces)


def _folder_xml(folder, counter):
    pieces = ["<Folder><name>{}</name>".format(_escape(folder["name"]))]
    for placemark in folder["placemarks"]:
        pieces.append(_placemark_xml(placemark, next(counter)))
    for sub in folder["folders"]:
        pieces.append(_folder_xml(sub, counter))
    pieces.append("</Folder>")
    return "".join(pieces)


def build_kml(folder):
    """Árvore neutra (mesmo formato de parse_kml) -> string KML completa."""

    def _counter():
        i = 0
        while True:
            yield i
            i += 1

    counter = _counter()
    body = _folder_xml(folder, counter)
    return (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<kml xmlns="http://www.opengis.net/kml/2.2">{}</kml>'
    ).format(body)


def build_kmz(folder):
    """Árvore neutra -> bytes de um .kmz (doc.kml dentro de um ZIP)."""
    kml_text = build_kml(folder)
    buf = BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("doc.kml", kml_text.encode("utf-8"))
    return buf.getvalue()

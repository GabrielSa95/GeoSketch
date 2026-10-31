# -*- coding: utf-8 -*-
"""Conversões de unidade, medição elipsoidal e formatação de coordenadas."""

import math
import re

from qgis.core import (
    QgsCoordinateReferenceSystem,
    QgsCoordinateTransform,
    QgsDistanceArea,
    QgsGeometry,
    QgsPointXY,
    QgsProject,
    QgsUnitTypes,
)

from . import measure_rules

WGS84 = QgsCoordinateReferenceSystem("EPSG:4326")

LOG_LEVELS = {"info": 0, "warning": 1, "critical": 2}


def log(message, level="warning"):
    """Grava no painel nativo "Mensagens de registro" do QGIS (Ver > Paineis).

    Complementa os avisos de messageBar/QMessageBox: aqueles desaparecem ou
    exigem que alguem esteja olhando a tela no momento da falha; isto aqui
    fica registrado para diagnostico posterior, sem precisar de um arquivo
    de log proprio do plugin.
    """
    try:
        from qgis.core import Qgis, QgsMessageLog

        levels = {
            "info": Qgis.Info,
            "warning": Qgis.Warning,
            "critical": Qgis.Critical,
        }
        QgsMessageLog.logMessage(
            str(message), "GeoSketch", levels.get(level, Qgis.Warning)
        )
    except Exception:
        pass


def zoom_to_layer(iface, layer):
    """Amplia o mapa até aquela camada usando o zoom nativo do QGIS, que já
    trata bem o caso de uma feição pontual (extensão zero), aplicando um
    buffer razoável em vez de tentar ampliar ao infinito."""
    try:
        iface.setActiveLayer(layer)
        iface.actionZoomToLayer().trigger()
    except Exception:
        pass


# ---------------------------------------------------------------- unidades
# Cada item: (rótulo, fator em relação à unidade base do SI)
# Comprimento: fator converte METROS -> unidade.
LENGTH_UNITS = [
    ("Metros", 1.0),
    ("Quilômetros", 0.001),
    ("Centímetros", 100.0),
    ("Pés", 3.280839895013123),
    ("Jardas", 1.093613298337708),
    ("Milhas", 0.0006213711922373339),
    ("Milhas náuticas", 0.0005399568034557235),
]

# Área: fator converte METROS QUADRADOS -> unidade.
# Alqueire paulista = 24.200 m²; alqueire mineiro (geométrico) = 48.400 m².
AREA_UNITS = [
    ("Metros quadrados", 1.0),
    ("Hectares", 0.0001),
    ("Quilômetros quadrados", 0.000001),
    ("Alqueire paulista", 1.0 / 24200.0),
    ("Alqueire mineiro", 1.0 / 48400.0),
    ("Acres", 0.0002471053814671653),
    ("Pés quadrados", 10.76391041670972),
]

DEFAULT_LENGTH = "Metros"
DEFAULT_AREA = "Hectares"


def convert_length(meters, label):
    for name, factor in LENGTH_UNITS:
        if name == label:
            return meters * factor
    return meters


def to_meters(value, label):
    """Inverso de convert_length: `value` na unidade `label` -> metros."""
    return measure_rules.to_meters(value, label, LENGTH_UNITS)


def convert_area(square_meters, label):
    for name, factor in AREA_UNITS:
        if name == label:
            return square_meters * factor
    return square_meters


def format_number(value):
    """Formata no padrão brasileiro: milhar com ponto, decimal com vírgula."""
    if value is None:
        return "0,00"
    if abs(value) >= 1000:
        text = "{:,.2f}".format(value)
    else:
        text = "{:.2f}".format(value)
    return text.replace(",", "\x00").replace(".", ",").replace("\x00", ".")


# --------------------------------------------------------------- medição
def make_distance_area(crs=None):
    """QgsDistanceArea configurado para medir sobre o elipsoide WGS84.

    Forçamos o elipsoide em vez de herdar do projeto porque muitos projetos
    vêm com elipsoide 'NONE', o que faria a medição virar cartesiana e dar
    resultados errados em graus decimais.
    """
    da = QgsDistanceArea()
    src = crs if crs is not None else QgsProject.instance().crs()
    da.setSourceCrs(src, QgsProject.instance().transformContext())
    da.setEllipsoid("WGS84")
    return da


def measure_length(points, crs=None):
    """Comprimento em metros de uma lista de QgsPointXY."""
    if not points or len(points) < 2:
        return 0.0
    da = make_distance_area(crs)
    try:
        return float(da.measureLine(points))
    except Exception:
        return 0.0


def measure_area(points, crs=None):
    """Área em metros quadrados do anel formado pelos pontos."""
    if not points or len(points) < 3:
        return 0.0
    da = make_distance_area(crs)
    ring = list(points)
    if ring[0] != ring[-1]:
        ring.append(ring[0])
    try:
        return float(da.measureArea(QgsGeometry.fromPolygonXY([ring])))
    except Exception:
        return 0.0


def measure_perimeter(points, crs=None):
    """Perímetro em metros (fecha o anel automaticamente)."""
    if not points or len(points) < 3:
        return measure_length(points, crs)
    ring = list(points)
    if ring[0] != ring[-1]:
        ring.append(ring[0])
    return measure_length(ring, crs)


def measure_area_geometry(geometry, crs=None):
    """Área em metros quadrados de uma QgsGeometry já pronta (qualquer
    polígono/multipolígono, inclusive com buracos) - diferente de
    measure_area(), que só sabe montar um anel simples a partir de uma
    lista de pontos. Usado pela Calculadora (Etapa 2) para medir um lugar
    JÁ SALVO (a geometria pode ter vindo de um recorte/diferença da Fase
    F, por exemplo, com partes múltiplas)."""
    if geometry is None or geometry.isEmpty():
        return 0.0
    da = make_distance_area(crs)
    try:
        return float(da.measureArea(geometry))
    except Exception:
        return 0.0


def measure_perimeter_geometry(geometry, crs=None):
    """Perímetro em metros de uma QgsGeometry já pronta - ver
    measure_area_geometry()."""
    if geometry is None or geometry.isEmpty():
        return 0.0
    da = make_distance_area(crs)
    try:
        return float(da.measurePerimeter(geometry))
    except Exception:
        return 0.0


def measure_length_geometry(geometry, crs=None):
    """Comprimento em metros de uma QgsGeometry já pronta (linha ou
    multilinha) - ver measure_area_geometry()."""
    if geometry is None or geometry.isEmpty():
        return 0.0
    da = make_distance_area(crs)
    try:
        return float(da.measureLength(geometry))
    except Exception:
        return 0.0


def project_point(start, distance_m, azimuth_deg, crs=None):
    """Ponto a `distance_m` metros de `start`, no azimute `azimuth_deg`.

    Convenção do azimute: graus a partir do Norte geográfico, sentido
    horário - a MESMA já usada no rumo da aba Linha da Régua
    (dlg_ruler.py._bearing_text) e em circle_points, abaixo. `start` e o
    ponto devolvido estão no mesmo SRC (o de `crs`, ou o do projeto se
    omitido). Devolve None se o cálculo falhar (ex.: SRC inválido).

    MESMA CAUSA RAIZ do círculo (ver circle_points, acima), confirmada
    empiricamente contra o QGIS 3.44.15 real: antes desta correção, com
    `crs` projetado (ex.: SIRGAS 2000/UTM), `QgsDistanceArea.
    computeSpheroidProject()` devolvia `(nan, nan)` SILENCIOSAMENTE - sem
    lançar exceção, então `except Exception: return None` nunca disparava
    - e esta função devolvia um QgsPointXY(nan, nan) como se fosse um
    ponto válido. Usada por `widgets.VertexEntryPanel._add_by_distance_
    azimuth()` (aba "Adicionar por medida" de Novo Caminho/Novo Polígono):
    o vértice NaN entraria na geometria em qualquer projeto com SRC
    projetado (o caso comum no Brasil - SIRGAS 2000/UTM). Corrigido com a
    mesma técnica do círculo: a projeção geodésica sempre roda em WGS84
    (onde `computeSpheroidProject` é correto, confirmado) e o ponto
    resultante é transformado de volta para `crs` antes de devolver.
    """
    azimuth = measure_rules.normalize_azimuth(azimuth_deg)
    source_crs = crs if (crs is not None and crs.isValid()) else QgsProject.instance().crs()
    need_transform = source_crs.isValid() and source_crs != WGS84
    try:
        if need_transform:
            to_wgs = QgsCoordinateTransform(source_crs, WGS84, QgsProject.instance())
            from_wgs = QgsCoordinateTransform(WGS84, source_crs, QgsProject.instance())
            start_calc = QgsPointXY(to_wgs.transform(start))
        else:
            start_calc = QgsPointXY(start)
        da_wgs = make_distance_area(WGS84)
        p = da_wgs.computeSpheroidProject(start_calc, distance_m, math.radians(azimuth))
        point_final = (
            QgsPointXY(from_wgs.transform(QgsPointXY(p))) if need_transform else QgsPointXY(p)
        )
        if math.isnan(point_final.x()) or math.isnan(point_final.y()):
            return None
        return point_final
    except Exception:
        return None


def circle_points(center, edge, segments=72, crs=None):
    """Gera o anel de um círculo geodésico a partir do centro e de um ponto da borda.

    `crs` precisa ser o CRS em que `center`/`edge` já estão expressos (o
    CRS do canvas/mapa).

    CAUSA RAIZ CONFIRMADA EMPIRICAMENTE contra o QGIS 3.44.15 real (não só
    por leitura de código): `QgsDistanceArea.computeSpheroidProject()`
    devolve `(nan, nan)` SILENCIOSAMENTE - sem lançar exceção - quando o
    CRS de origem configurado via `setSourceCrs()` é um CRS PROJETADO (ex.:
    SIRGAS 2000/UTM, o caso comum deste plugin no Brasil). Só funciona
    corretamente quando o CRS de origem é geográfico (graus). Por isso o
    anel vinha todo em NaN sempre que o SRC do canvas era projetado -
    `QgsGeometry.fromPolygonXY` com pontos NaN produz uma geometria
    inválida (daí a circunferência não aparecer e a Área dar NaN), e como
    não há exceção, nenhuma defesa baseada em try/except pegava isso.

    Correção: a projeção geodésica de cada segmento SEMPRE roda em WGS84
    (onde `computeSpheroidProject` é correto, confirmado), independente do
    CRS do canvas. `center`/`edge` são transformados para WGS84 antes de
    projetar e o anel resultante é transformado de volta para `crs` antes
    de devolver - assim a geometria final continua no CRS do canvas/mapa,
    só o cálculo intermediário usa WGS84. O raio (`radius`, em metros) é
    medido uma única vez no CRS original via `measureLine()` - que, ao
    contrário de `computeSpheroidProject()`, já funciona corretamente em
    qualquer CRS (confirmado) - e não precisa ser remedido.
    """
    da = make_distance_area(crs)
    try:
        radius = da.measureLine(center, edge)
    except Exception:
        radius = 0.0
    if radius <= 0:
        return [], 0.0

    source_crs = crs if (crs is not None and crs.isValid()) else QgsProject.instance().crs()
    need_transform = source_crs.isValid() and source_crs != WGS84

    if need_transform:
        to_wgs = QgsCoordinateTransform(source_crs, WGS84, QgsProject.instance())
        from_wgs = QgsCoordinateTransform(WGS84, source_crs, QgsProject.instance())
        try:
            center_calc = QgsPointXY(to_wgs.transform(center))
        except Exception as exc:
            log(
                "circle_points: falha ao transformar o centro para WGS84: {}".format(exc),
                "warning",
            )
            return [], radius
    else:
        center_calc = QgsPointXY(center)

    da_wgs = make_distance_area(WGS84)
    pts = []
    for i in range(segments):
        azimuth = (360.0 / segments) * i
        try:
            p = da_wgs.computeSpheroidProject(center_calc, radius, math.radians(azimuth))
            point_wgs = QgsPointXY(p)
            point_final = QgsPointXY(from_wgs.transform(point_wgs)) if need_transform else point_wgs
            if math.isnan(point_final.x()) or math.isnan(point_final.y()):
                raise ValueError("coordenada NaN apos projecao/transformacao")
            pts.append(point_final)
        except Exception as exc:
            log(
                "circle_points: falha ao projetar o segmento {} de {} (azimute {:.1f}°): "
                "{}".format(i, segments, azimuth, exc),
                "warning",
            )
    if len(pts) < 3:
        if pts:
            log(
                "circle_points: anel descartado - só {} de {} segmentos foram "
                "projetados com sucesso.".format(len(pts), segments),
                "warning",
            )
        return [], radius
    pts.append(pts[0])
    return pts, radius


# ---------------------------------------------------- coordenadas / DMS
def to_wgs84(point, source_crs):
    """Converte um QgsPointXY para latitude/longitude WGS84."""
    if source_crs == WGS84:
        return QgsPointXY(point)
    tr = QgsCoordinateTransform(source_crs, WGS84, QgsProject.instance())
    return tr.transform(point)


def from_wgs84(point, target_crs):
    if target_crs == WGS84:
        return QgsPointXY(point)
    tr = QgsCoordinateTransform(WGS84, target_crs, QgsProject.instance())
    return tr.transform(point)


def format_dm(value, is_latitude):
    """Formata em grau + minuto decimal, como o Google Earth: 23° 34.616'S."""
    if is_latitude:
        hemi = "S" if value < 0 else "N"
    else:
        hemi = "O" if value < 0 else "L"
    value = abs(value)
    degrees = int(value)
    minutes = (value - degrees) * 60.0
    return "{}° {:.3f}'{}".format(degrees, minutes, hemi)


_DM_RE = re.compile(
    r"^\s*(-?\d+(?:[.,]\d+)?)\s*[°º]?\s*"
    r"(?:(\d+(?:[.,]\d+)?)\s*['′]?\s*)?"
    r"(?:(\d+(?:[.,]\d+)?)\s*[\"″]?\s*)?"
    r"([NSELWOnselwo])?\s*$"
)


def parse_coordinate(text):
    """Aceita '23.5769', '-23,5769', \"23° 34.616'S\" ou \"23 34 37 S\".

    Devolve float em graus decimais ou None se não conseguir interpretar.
    """
    if text is None:
        return None
    match = _DM_RE.match(str(text).strip())
    if not match:
        return None
    deg_txt, min_txt, sec_txt, hemi = match.groups()
    try:
        value = abs(float(deg_txt.replace(",", ".")))
        negative = deg_txt.strip().startswith("-")
        if min_txt:
            value += float(min_txt.replace(",", ".")) / 60.0
        if sec_txt:
            value += float(sec_txt.replace(",", ".")) / 3600.0
    except (TypeError, ValueError):
        return None
    if hemi and hemi.upper() in ("S", "W", "O"):
        negative = True
    return -value if negative else value


def string_to_color(text, fallback=(255, 255, 0, 255)):
    """'r,g,b,a' -> QColor. Usado para recarregar o estilo na janela de edicao."""
    from qgis.PyQt.QtGui import QColor

    try:
        parts = [int(p) for p in str(text).split(",")]
        if len(parts) == 3:
            parts.append(255)
        return QColor(*parts[:4])
    except Exception:
        return QColor(*fallback)


def color_to_string(qcolor):
    """QColor -> 'r,g,b,a' (formato que o QGIS lê em propriedades definidas por dados)."""
    return "{},{},{},{}".format(
        qcolor.red(), qcolor.green(), qcolor.blue(), qcolor.alpha()
    )

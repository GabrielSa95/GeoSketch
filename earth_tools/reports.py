# -*- coding: utf-8 -*-
"""Exportação de mapas (Etapa 5): monta um QgsPrintLayout de verdade
(mapa + título + legenda + barra de escala + seta de norte + texto de
informações), usando sempre os componentes nativos de layout do QGIS
(QgsLayoutItemMap/Legend/ScaleBar/Picture/Label e QgsLayoutExporter) -
nunca uma captura crua do canvas sem organização cartográfica.
"""

import os

from qgis.PyQt.QtCore import QRectF
from qgis.core import (
    QgsApplication,
    QgsLayout,
    QgsLayoutExporter,
    QgsLayoutItemLabel,
    QgsLayoutItemLegend,
    QgsLayoutItemMap,
    QgsLayoutItemPage,
    QgsLayoutItemPicture,
    QgsLayoutItemScaleBar,
    QgsLayoutPoint,
    QgsPrintLayout,
    QgsUnitTypes,
)

NORTH_ARROW_SVG = os.path.join(
    QgsApplication.pkgDataPath(), "svg", "arrows", "NorthArrow_02.svg"
)

PAGE_SIZES = ["A4", "A3"]
ORIENTATIONS = {
    "Retrato": QgsLayoutItemPage.Portrait,
    "Paisagem": QgsLayoutItemPage.Landscape,
}

MARGIN_MM = 10.0
TITLE_HEIGHT_MM = 14.0
FOOTER_HEIGHT_MM = 8.0
INFO_LINE_HEIGHT_MM = 5.0
NORTH_ARROW_SIZE_MM = 14.0
SCALEBAR_HEIGHT_MM = 12.0


class ReportError(Exception):
    """Erro de montagem/exportação do mapa, com mensagem pronta para o usuário."""


def build_layout(
    project,
    map_layers,
    extent,
    map_crs,
    title="",
    subtitle="",
    info_lines=None,
    page_size="A4",
    orientation="Retrato",
    scale=None,
    show_legend=True,
    show_scalebar=True,
    show_north_arrow=True,
    layout_name="Mapa GeoSketch",
):
    """Monta um QgsPrintLayout completo e o registra no gerenciador de
    layouts do projeto (para poder ser aberto no Layout Designer nativo
    do QGIS como pré-visualização). Devolve o QgsPrintLayout.
    """
    if orientation not in ORIENTATIONS:
        raise ReportError("Orientação inválida: {}".format(orientation))
    if page_size not in PAGE_SIZES:
        raise ReportError("Formato de página inválido: {}".format(page_size))

    layout = QgsPrintLayout(project)
    layout.initializeDefaults()
    layout.setName(layout_name)

    page = layout.pageCollection().page(0)
    if not page.setPageSize(page_size, ORIENTATIONS[orientation]):
        raise ReportError("Não foi possível aplicar o formato {}.".format(page_size))
    page_w = page.pageSize().width()
    page_h = page.pageSize().height()

    y = MARGIN_MM
    if title:
        title_item = QgsLayoutItemLabel(layout)
        title_item.setText(title)
        title_item.attemptSetSceneRect(
            QRectF(MARGIN_MM, y, page_w - 2 * MARGIN_MM, TITLE_HEIGHT_MM)
        )
        font = title_item.font()
        font.setPointSize(16)
        font.setBold(True)
        title_item.setFont(font)
        layout.addLayoutItem(title_item)
        y += TITLE_HEIGHT_MM

    if subtitle:
        subtitle_item = QgsLayoutItemLabel(layout)
        subtitle_item.setText(subtitle)
        subtitle_item.attemptSetSceneRect(
            QRectF(MARGIN_MM, y, page_w - 2 * MARGIN_MM, INFO_LINE_HEIGHT_MM + 2)
        )
        layout.addLayoutItem(subtitle_item)
        y += INFO_LINE_HEIGHT_MM + 2

    map_top = y
    footer_lines = list(info_lines or [])
    footer_h = FOOTER_HEIGHT_MM + INFO_LINE_HEIGHT_MM * max(len(footer_lines), 1)
    map_bottom_margin = MARGIN_MM + footer_h + (SCALEBAR_HEIGHT_MM if show_scalebar else 0)
    map_h = page_h - map_top - map_bottom_margin
    if map_h <= 10:
        raise ReportError("Página pequena demais para o conteúdo escolhido.")

    map_item = QgsLayoutItemMap(layout)
    map_item.attemptSetSceneRect(
        QRectF(MARGIN_MM, map_top, page_w - 2 * MARGIN_MM, map_h)
    )
    map_item.setFrameEnabled(True)
    if map_crs is not None and map_crs.isValid():
        map_item.setCrs(map_crs)
    map_item.setLayers(list(map_layers))
    map_item.zoomToExtent(extent)
    if scale:
        map_item.setScale(scale)
    layout.addLayoutItem(map_item)

    if show_north_arrow and os.path.exists(NORTH_ARROW_SVG):
        north = QgsLayoutItemPicture(layout)
        north.setPicturePath(NORTH_ARROW_SVG)
        north.attemptSetSceneRect(
            QRectF(
                page_w - MARGIN_MM - NORTH_ARROW_SIZE_MM, map_top + 2,
                NORTH_ARROW_SIZE_MM, NORTH_ARROW_SIZE_MM,
            )
        )
        layout.addLayoutItem(north)

    if show_legend:
        legend = QgsLayoutItemLegend(layout)
        legend.setLinkedMap(map_item)
        legend.setTitle("Legenda")
        legend.attemptSetSceneRect(
            QRectF(page_w - MARGIN_MM - 45, map_top + NORTH_ARROW_SIZE_MM + 4, 45, map_h * 0.4)
        )
        layout.addLayoutItem(legend)

    y = map_top + map_h + 2
    if show_scalebar:
        scalebar = QgsLayoutItemScaleBar(layout)
        scalebar.setLinkedMap(map_item)
        scalebar.setStyle("Single Box")
        scalebar.setUnits(QgsUnitTypes.DistanceMeters)
        scalebar.applyDefaultSize()
        scalebar.attemptMove(QgsLayoutPoint(MARGIN_MM, y))
        layout.addLayoutItem(scalebar)
        y += SCALEBAR_HEIGHT_MM

    for line in footer_lines:
        label = QgsLayoutItemLabel(layout)
        label.setText(line)
        label.attemptSetSceneRect(
            QRectF(MARGIN_MM, y, page_w - 2 * MARGIN_MM, INFO_LINE_HEIGHT_MM)
        )
        layout.addLayoutItem(label)
        y += INFO_LINE_HEIGHT_MM

    manager = project.layoutManager()
    existing = manager.layoutByName(layout_name)
    if existing is not None:
        manager.removeLayout(existing)
    manager.addLayout(layout)
    return layout


def export_pdf(layout, path):
    """Devolve (ok, mensagem). Nunca lança exceção para erro de
    exportação - só para erro de programação (layout None, por exemplo)."""
    if layout is None:
        raise ReportError("Nenhum layout para exportar.")
    exporter = QgsLayoutExporter(layout)
    settings = QgsLayoutExporter.PdfExportSettings()
    result = exporter.exportToPdf(path, settings)
    if result == QgsLayoutExporter.Success:
        return True, path
    return False, "Falha ao exportar PDF (código {}).".format(result)


def export_png(layout, path, dpi=200):
    """Devolve (ok, mensagem). Ver export_pdf()."""
    if layout is None:
        raise ReportError("Nenhum layout para exportar.")
    exporter = QgsLayoutExporter(layout)
    settings = QgsLayoutExporter.ImageExportSettings()
    settings.dpi = dpi
    result = exporter.exportToImage(path, settings)
    if result == QgsLayoutExporter.Success:
        return True, path
    return False, "Falha ao exportar PNG (código {}).".format(result)

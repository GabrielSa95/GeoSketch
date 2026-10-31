# -*- coding: utf-8 -*-
"""Janela "Exportar mapa..." (Etapa 5): monta um QgsPrintLayout real
(título, SRC, área/perímetro, legenda, escala, norte) e exporta para
PDF/PNG, ou abre o Layout Designer NATIVO do QGIS para pré-visualizar e
ajustar antes de exportar.
"""

from datetime import datetime

from qgis.core import QgsProject
from qgis.PyQt.QtCore import Qt
from qgis.PyQt.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
)

from . import reports, storage, utils


class ExportMapDialog(QDialog):
    def __init__(self, iface, parent=None, initial_layer=None):
        super(ExportMapDialog, self).__init__(parent)
        self.iface = iface
        self._layout = None

        self.setWindowTitle("GeoSketch - Exportar mapa")
        self.setWindowFlags(self.windowFlags() | Qt.WindowStaysOnTopHint)
        self.setModal(False)
        self.setMinimumWidth(460)

        layout = QVBoxLayout(self)
        form = QFormLayout()

        self.title_edit = QLineEdit("Mapa da propriedade")
        form.addRow("Título do mapa:", self.title_edit)
        self.property_edit = QLineEdit()
        form.addRow("Nome da propriedade/área:", self.property_edit)

        self.page_combo = QComboBox()
        self.page_combo.addItems(reports.PAGE_SIZES)
        form.addRow("Formato da página:", self.page_combo)

        self.orientation_combo = QComboBox()
        self.orientation_combo.addItems(list(reports.ORIENTATIONS.keys()))
        form.addRow("Orientação:", self.orientation_combo)

        self.extent_combo = QComboBox()
        self.extent_combo.addItem("Extensão atual do mapa", None)
        for layer in self._place_layers():
            self.extent_combo.addItem("Ajustar ao lugar: {}".format(layer.name()), layer.id())
        form.addRow("Extensão do mapa:", self.extent_combo)

        if initial_layer is not None:
            # Vindo do menu de contexto/painel de propriedades de um lugar
            # específico: já ajusta a extensão a ele e sugere o nome.
            idx = self.extent_combo.findData(initial_layer.id())
            if idx >= 0:
                self.extent_combo.setCurrentIndex(idx)
            self.property_edit.setText(initial_layer.name())

        layout.addLayout(form)

        options_box = QGroupBox("Elementos do mapa")
        options_layout = QVBoxLayout(options_box)
        self.check_legend = QCheckBox("Legenda")
        self.check_legend.setChecked(True)
        self.check_scalebar = QCheckBox("Barra de escala")
        self.check_scalebar.setChecked(True)
        self.check_north = QCheckBox("Seta de norte")
        self.check_north.setChecked(True)
        self.check_crs = QCheckBox("SRC utilizado")
        self.check_crs.setChecked(True)
        self.check_measurements = QCheckBox("Área e perímetro (do lugar escolhido na extensão, quando houver)")
        self.check_measurements.setChecked(True)
        for cb in (
            self.check_legend, self.check_scalebar, self.check_north,
            self.check_crs, self.check_measurements,
        ):
            options_layout.addWidget(cb)
        layout.addWidget(options_box)

        self.status = QLabel("")
        self.status.setWordWrap(True)
        layout.addWidget(self.status)

        self.btn_preview = QPushButton("Pré-visualizar (abre o Layout Designer do QGIS)")
        self.btn_pdf = QPushButton("Exportar PDF...")
        self.btn_png = QPushButton("Exportar PNG...")
        self.btn_close = QPushButton("Fechar")
        for btn in (self.btn_preview, self.btn_pdf, self.btn_png, self.btn_close):
            layout.addWidget(btn)

        self.btn_preview.clicked.connect(self._preview)
        self.btn_pdf.clicked.connect(self._export_pdf)
        self.btn_png.clicked.connect(self._export_png)
        self.btn_close.clicked.connect(self.close)

    # ------------------------------------------------------------- apoio
    def _place_layers(self):
        return [
            layer for layer in QgsProject.instance().mapLayers().values()
            if storage.is_place_layer(layer)
        ]

    def _info_lines(self, reference_layer):
        linhas = []
        if self.check_crs.isChecked():
            crs = self.iface.mapCanvas().mapSettings().destinationCrs()
            linhas.append("SRC: {} - {}".format(crs.authid(), crs.description()))
        if self.check_measurements.isChecked() and reference_layer is not None:
            kind = reference_layer.customProperty(storage.CUSTOM_KEY) or ""
            features = list(reference_layer.getFeatures())
            if features:
                geometry = features[0].geometry()
                crs = reference_layer.crs()
                if kind == "polygon":
                    area = utils.measure_area_geometry(geometry, crs)
                    perimetro = utils.measure_perimeter_geometry(geometry, crs)
                    linhas.append(
                        "Área: {} ha | Perímetro: {} m".format(
                            utils.format_number(utils.convert_area(area, "Hectares")),
                            utils.format_number(perimetro),
                        )
                    )
                elif kind == "line":
                    comprimento = utils.measure_length_geometry(geometry, crs)
                    linhas.append("Comprimento: {} m".format(utils.format_number(comprimento)))
        linhas.append("Gerado em {}".format(datetime.now().strftime("%d/%m/%Y %H:%M")))
        return linhas

    def _build(self):
        canvas = self.iface.mapCanvas()
        layer_id = self.extent_combo.currentData()
        reference_layer = QgsProject.instance().mapLayer(layer_id) if layer_id else None
        extent = reference_layer.extent() if reference_layer is not None else canvas.extent()
        map_crs = canvas.mapSettings().destinationCrs()
        visible_layers = [
            layer for layer in canvas.layers()
        ] or list(QgsProject.instance().mapLayers().values())

        try:
            self._layout = reports.build_layout(
                QgsProject.instance(),
                visible_layers,
                extent,
                map_crs,
                title=self.title_edit.text().strip(),
                subtitle=self.property_edit.text().strip(),
                info_lines=self._info_lines(reference_layer),
                page_size=self.page_combo.currentText(),
                orientation=self.orientation_combo.currentText(),
                show_legend=self.check_legend.isChecked(),
                show_scalebar=self.check_scalebar.isChecked(),
                show_north_arrow=self.check_north.isChecked(),
            )
        except reports.ReportError as exc:
            QMessageBox.warning(self, "GeoSketch", str(exc))
            return False
        except Exception as exc:
            utils.log("Falha ao montar o layout do mapa: {}".format(exc), "critical")
            QMessageBox.critical(
                self, "GeoSketch", "Erro inesperado ao montar o mapa:\n{}".format(exc)
            )
            return False
        return True

    # -------------------------------------------------------------- acoes
    def _preview(self):
        if not self._build():
            return
        try:
            self.iface.openLayoutDesignerDialog(self._layout)
        except Exception as exc:
            utils.log("Falha ao abrir o Layout Designer: {}".format(exc), "warning")
            QMessageBox.information(
                self, "GeoSketch",
                "O mapa foi montado e está disponível em Projeto > Layouts > \"{}\", mas não "
                "foi possível abri-lo automaticamente:\n{}".format(self._layout.name(), exc),
            )

    def _export_pdf(self):
        if not self._build():
            return
        path, _filter = QFileDialog.getSaveFileName(
            self, "Exportar mapa em PDF", "", "PDF (*.pdf)"
        )
        if not path:
            return
        if not path.lower().endswith(".pdf"):
            path += ".pdf"
        ok, msg = reports.export_pdf(self._layout, path)
        if ok:
            self.status.setText("PDF exportado: {}".format(path))
            self.iface.messageBar().pushSuccess("GeoSketch", "Mapa exportado em PDF.")
        else:
            utils.log("Exportacao de PDF falhou: {}".format(msg), "critical")
            QMessageBox.critical(self, "GeoSketch", msg)

    def _export_png(self):
        if not self._build():
            return
        path, _filter = QFileDialog.getSaveFileName(
            self, "Exportar mapa em PNG", "", "PNG (*.png)"
        )
        if not path:
            return
        if not path.lower().endswith(".png"):
            path += ".png"
        ok, msg = reports.export_png(self._layout, path)
        if ok:
            self.status.setText("PNG exportado: {}".format(path))
            self.iface.messageBar().pushSuccess("GeoSketch", "Mapa exportado em PNG.")
        else:
            utils.log("Exportacao de PNG falhou: {}".format(msg), "critical")
            QMessageBox.critical(self, "GeoSketch", msg)

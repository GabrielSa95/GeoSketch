# -*- coding: utf-8 -*-
"""Janela "Importar KML/KMZ" (Fase D).

Mostra todo elemento encontrado no arquivo, numa lista marcável (tudo
marcado por padrão, exceto o que já foi importado antes - detectado por
impressão digital da geometria/nome, não só pelo nome do arquivo). O
usuário escolhe a pasta de destino (ou cria uma nova) antes de confirmar.
"""

from qgis.PyQt.QtCore import Qt
from qgis.PyQt.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
)

from . import kml_bridge, kml_io, places_model


class ImportKmlDialog(QDialog):
    def __init__(self, iface, parent=None, preselect_folder_id=None):
        """preselect_folder_id: id estável de pasta (places_model) já
        escolhida por quem abriu a janela - ex. clique direito em "Importar
        KML/KMZ para esta pasta..." no menu de contexto. Quando informado,
        a pasta de destino já vem selecionada e trancada (a escolha já foi
        feita; reabrir a decisão aqui seria confuso)."""
        super(ImportKmlDialog, self).__init__(parent)
        self.iface = iface
        self.candidates = []
        self.origem = ""
        self._preselect_folder_id = preselect_folder_id

        self.setWindowTitle("GeoSketch - Importar KML/KMZ")
        self.setModal(False)
        self.setMinimumSize(480, 520)

        layout = QVBoxLayout(self)

        top = QHBoxLayout()
        self.path_label = QLabel("Nenhum arquivo escolhido.")
        self.path_label.setWordWrap(True)
        top.addWidget(self.path_label)
        self.btn_choose = QPushButton("Escolher arquivo...")
        top.addWidget(self.btn_choose)
        layout.addLayout(top)

        self.summary_label = QLabel("")
        self.summary_label.setWordWrap(True)
        layout.addWidget(self.summary_label)

        self.list_widget = QListWidget()
        layout.addWidget(self.list_widget)

        dest_row = QHBoxLayout()
        dest_row.addWidget(QLabel("Importar para:"))
        self.dest_combo = QComboBox()
        self.dest_combo.setMinimumWidth(220)
        dest_row.addWidget(self.dest_combo)
        self.btn_new_folder = QPushButton("Nova pasta...")
        dest_row.addWidget(self.btn_new_folder)
        dest_row.addStretch()
        layout.addLayout(dest_row)

        self.unsupported_box = QPlainTextEdit()
        self.unsupported_box.setReadOnly(True)
        self.unsupported_box.setMaximumHeight(60)
        self.unsupported_box.hide()
        layout.addWidget(self.unsupported_box)

        buttons = QDialogButtonBox(QDialogButtonBox.Cancel)
        self.btn_import = QPushButton("Importar selecionados")
        self.btn_import.setEnabled(False)
        buttons.addButton(self.btn_import, QDialogButtonBox.ActionRole)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        self.btn_choose.clicked.connect(self._choose_file)
        self.btn_new_folder.clicked.connect(self._new_folder)
        self.btn_import.clicked.connect(self._do_import)

        self._reload_folders()
        self._apply_preselected_folder()

    # -------------------------------------------------------------- pastas
    def _reload_folders(self):
        self.dest_combo.clear()
        for folder_id, label in places_model.folder_choices():
            self.dest_combo.addItem(label, folder_id)

    def _apply_preselected_folder(self):
        if self._preselect_folder_id is None:
            return
        index = self.dest_combo.findData(self._preselect_folder_id)
        if index >= 0:
            self.dest_combo.setCurrentIndex(index)
        # a pasta ja foi escolhida pelo clique direito - tranca a escolha
        # (inclusive "Nova pasta...", que criaria na raiz, nao dentro dela).
        self.dest_combo.setEnabled(False)
        self.btn_new_folder.setEnabled(False)

    def _new_folder(self):
        name, ok = QInputDialog.getText(self, "Nova pasta", "Nome da pasta:")
        if not ok or not name.strip():
            return
        try:
            places_model.create_folder(name.strip())
        except Exception as exc:
            QMessageBox.critical(
                self, "GeoSketch", "Não foi possível criar a pasta:\n{}".format(exc)
            )
            return
        self._reload_folders()
        index = self.dest_combo.findText(name.strip())
        if index >= 0:
            self.dest_combo.setCurrentIndex(index)

    # -------------------------------------------------------------- arquivo
    def _choose_file(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Escolher arquivo KML/KMZ", "", "KML/KMZ (*.kml *.kmz)"
        )
        if not path:
            return
        try:
            folder, unsupported, _assets = kml_io.load_file(path)
        except kml_io.KmlError as exc:
            QMessageBox.critical(
                self, "GeoSketch", "Não foi possível ler o arquivo:\n{}".format(exc)
            )
            return
        except Exception as exc:
            QMessageBox.critical(
                self, "GeoSketch", "Erro inesperado ao ler o arquivo:\n{}".format(exc)
            )
            return

        self.origem = path
        self.candidates = kml_bridge.flatten_candidates(folder)
        self.path_label.setText(path)
        total = len(self.candidates)
        ja_importados = sum(1 for c in self.candidates if c["already_imported"])
        aviso = ""
        if ja_importados:
            aviso = " ({} já importado(s) antes - desmarcado(s) por padrão)".format(ja_importados)
        self.summary_label.setText("{} elemento(s) encontrado(s){}.".format(total, aviso))

        self.list_widget.clear()
        for candidate in self.candidates:
            caminho = " / ".join(p for p in candidate["path"] if p)
            rotulo = "{} ({})".format(candidate["name"], candidate["kind"])
            if caminho:
                rotulo = "{}  [{}]".format(rotulo, caminho)
            if candidate["already_imported"]:
                rotulo += "  — já importado"
            item = QListWidgetItem(rotulo)
            item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
            item.setCheckState(Qt.Unchecked if candidate["already_imported"] else Qt.Checked)
            self.list_widget.addItem(item)

        unique_unsupported = sorted(set(unsupported))
        if unique_unsupported:
            self.unsupported_box.setPlainText(
                "Elementos não suportados e ignorados: {}".format(", ".join(unique_unsupported))
            )
            self.unsupported_box.show()
        else:
            self.unsupported_box.hide()

        self.btn_import.setEnabled(total > 0)
        if total == 0:
            QMessageBox.information(
                self,
                "GeoSketch",
                "Nenhum marcador, caminho ou polígono foi encontrado neste arquivo.",
            )

    # -------------------------------------------------------------- acao
    def _do_import(self):
        selected = [
            candidate
            for i, candidate in enumerate(self.candidates)
            if self.list_widget.item(i).checkState() == Qt.Checked
        ]
        if not selected:
            QMessageBox.information(self, "GeoSketch", "Nenhum elemento selecionado.")
            return
        dest_folder_id = self.dest_combo.currentData()
        self.btn_import.setEnabled(False)
        try:
            ok, failures = kml_bridge.import_candidates(
                selected, dest_folder_id, self.origem, self.iface
            )
        finally:
            self.btn_import.setEnabled(True)

        if failures:
            detail = "\n".join("- {}: {}".format(n, m) for n, m in failures[:10])
            if len(failures) > 10:
                detail += "\n... e mais {}.".format(len(failures) - 10)
            QMessageBox.warning(
                self,
                "GeoSketch",
                "{} importado(s) com sucesso, {} com falha:\n{}".format(
                    ok, len(failures), detail
                ),
            )
        elif self.iface is not None:
            self.iface.messageBar().pushSuccess(
                "GeoSketch", "{} elemento(s) importado(s).".format(ok)
            )
        self.accept()

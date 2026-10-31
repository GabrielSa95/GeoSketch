# -*- coding: utf-8 -*-
"""Janela "Exportar para KML/KMZ" de uma pasta (com subpastas) ou de tudo
(Fase D). Exportar UMA feição isolada continua pelo "Salvar lugar como..."
já existente no menu de botão direito da camada.

Este diálogo também é aberto, já com a pasta pré-selecionada e trancada
(preselect_folder_id), pelo botão direito numa pasta no painel Camadas
(Fase F - ver layeractions._on_group_context_menu); aberto pelo menu
Vetor > GeoSketch, pede a escolha da pasta/escopo normalmente.
"""

from qgis.PyQt.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QLabel,
    QMessageBox,
    QVBoxLayout,
)

from . import export_rules, kml_bridge, kml_io, places_model, utils


class ExportKmlDialog(QDialog):
    def __init__(self, iface, parent=None, preselect_folder_id=None):
        """preselect_folder_id: id estável de pasta (places_model) já
        escolhida por quem abriu a janela - ex. clique direito em "Exportar
        esta pasta..."/"Exportar propriedade completa..." no menu de
        contexto. Quando informado, o escopo já vem em "Uma pasta" com essa
        pasta selecionada e o escolhedor trancado (a escolha já foi feita
        pelo clique direito); só o formato (KML/KMZ) continua livre."""
        super(ExportKmlDialog, self).__init__(parent)
        self.iface = iface
        self._preselect_folder_id = preselect_folder_id

        self.setWindowTitle("GeoSketch - Exportar para KML/KMZ")
        self.setModal(True)
        self.setMinimumWidth(380)

        layout = QVBoxLayout(self)
        form = QFormLayout()

        self.scope_combo = QComboBox()
        self.scope_combo.addItems(["Uma pasta (com subpastas)", "Tudo (propriedade completa)"])
        form.addRow("O que exportar:", self.scope_combo)

        self.folder_combo = QComboBox()
        self._folder_options = [
            (fid, label) for fid, label in places_model.folder_choices() if fid
        ]
        for folder_id, label in self._folder_options:
            self.folder_combo.addItem(label, folder_id)
        form.addRow("Pasta:", self.folder_combo)

        self.format_combo = QComboBox()
        self.format_combo.addItems(["KML (.kml)", "KMZ (.kmz)"])
        form.addRow("Formato:", self.format_combo)

        layout.addLayout(form)

        note = QLabel(
            "Nomes, descrições e cores/largura suportadas são preservados. Ícones "
            "personalizados e alguns recursos visuais do Google Earth não têm "
            "equivalente garantido neste formato."
        )
        note.setWordWrap(True)
        note.setStyleSheet("color: #555; font-style: italic;")
        layout.addWidget(note)

        self.scope_combo.currentIndexChanged.connect(self._update_folder_visibility)
        self._update_folder_visibility()

        if not self._folder_options:
            self.folder_combo.setEnabled(False)

        if self._preselect_folder_id:
            index = self.folder_combo.findData(self._preselect_folder_id)
            if index >= 0:
                self.scope_combo.setCurrentIndex(0)  # "Uma pasta (com subpastas)"
                self.folder_combo.setCurrentIndex(index)
                # a pasta ja foi escolhida pelo clique direito - so o formato continua livre.
                self.scope_combo.setEnabled(False)
                self.folder_combo.setEnabled(False)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.button(QDialogButtonBox.Ok).setText("Exportar...")
        buttons.button(QDialogButtonBox.Cancel).setText("Cancelar")
        buttons.accepted.connect(self._do_export)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _update_folder_visibility(self):
        is_single_folder = self.scope_combo.currentIndex() == 0
        self.folder_combo.setVisible(is_single_folder)
        if is_single_folder and not self._folder_options:
            QMessageBox.information(
                self,
                "GeoSketch",
                "Não há nenhuma pasta criada ainda. Use 'Tudo' ou crie uma pasta primeiro.",
            )

    def _do_export(self):
        if self.scope_combo.currentIndex() == 0:
            if not self._folder_options:
                return
            folder_id = self.folder_combo.currentData()
        else:
            folder_id = ""

        try:
            if folder_id:
                tree, errors = kml_bridge.export_folder_tree_with_errors(
                    folder_id, iface=self.iface
                )
            else:
                tree, errors = kml_bridge.export_folder_tree_with_errors(
                    "", root_name="Meus Lugares", iface=self.iface
                )
        except kml_bridge.ExportError as exc:
            # Selecao invalida (ex.: pasta apagada entre abrir a janela e
            # clicar em Exportar) - mensagem distinta de "pasta vazia".
            QMessageBox.warning(self, "GeoSketch", str(exc))
            return
        except Exception as exc:
            # Falha de leitura real (ex.: arvore de camadas inacessivel) -
            # nunca mascarada como "nada para exportar".
            utils.log("Falha ao ler a arvore para exportacao KML: {}".format(exc), "critical")
            QMessageBox.critical(
                self,
                "GeoSketch",
                "Não foi possível ler os lugares para exportar:\n{}".format(exc),
            )
            return

        if errors:
            detail = "\n".join("- {}: {}".format(n, m) for n, m in errors[:10])
            utils.log(
                "Falhas ao exportar itens para KML: {}".format(
                    "; ".join("{}: {}".format(n, m) for n, m in errors)
                ),
                "warning",
            )
            resposta = QMessageBox.warning(
                self,
                "GeoSketch",
                "{} item(ns) não puderam ser lidos e serão omitidos:\n{}\n\n"
                "Continuar exportando o restante?".format(len(errors), detail),
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.Yes,
            )
            if resposta != QMessageBox.Yes:
                return

        if export_rules.is_empty(tree):
            QMessageBox.information(
                self,
                "GeoSketch",
                "Esta pasta não tem nenhum lugar para exportar.",
            )
            return

        is_kmz = self.format_combo.currentIndex() == 1
        suffix = ".kmz" if is_kmz else ".kml"
        path, _ = QFileDialog.getSaveFileName(
            self,
            "Exportar para " + ("KMZ" if is_kmz else "KML"),
            tree["name"] + suffix,
            "KMZ (*.kmz)" if is_kmz else "KML (*.kml)",
        )
        if not path:
            return
        if not path.lower().endswith(suffix):
            path += suffix

        try:
            data = kml_io.build_kmz(tree) if is_kmz else kml_io.build_kml(tree).encode("utf-8")
            with open(path, "wb") as f:
                f.write(data)
        except Exception as exc:
            QMessageBox.critical(
                self, "GeoSketch", "Não foi possível gravar o arquivo:\n{}".format(exc)
            )
            return

        total = kml_io.count_placemarks(tree)
        if self.iface is not None:
            self.iface.messageBar().pushSuccess(
                "GeoSketch",
                "{} lugar(es) exportado(s) para {}.".format(total, path),
            )
        self.accept()

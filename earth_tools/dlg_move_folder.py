# -*- coding: utf-8 -*-
"""Janela "Mover para pasta...": alternativa garantida pelo menu de contexto
para organizar um lugar, sem depender de arrastar-e-soltar na árvore.
"""

from qgis.PyQt.QtWidgets import QComboBox, QDialog, QDialogButtonBox, QLabel, QVBoxLayout

from . import places_model, storage, utils


class MoveFolderDialog(QDialog):
    def __init__(self, iface, layer, parent=None):
        super(MoveFolderDialog, self).__init__(parent)
        self.iface = iface
        self.layer = layer

        self.setWindowTitle("GeoSketch - Mover para pasta")
        self.setModal(True)
        self.setMinimumWidth(320)

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel('Mover "{}" para:'.format(layer.name())))

        self.combo = QComboBox()
        self._options = places_model.folder_choices()
        for folder_id, rotulo in self._options:
            self.combo.addItem(rotulo, folder_id)

        tabela = storage.table_name(layer)
        atual = places_model.list_memberships().get(tabela, "") if tabela else ""
        for i, (folder_id, _rotulo) in enumerate(self._options):
            if folder_id == atual:
                self.combo.setCurrentIndex(i)
                break
        layout.addWidget(self.combo)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.button(QDialogButtonBox.Ok).setText("Mover")
        buttons.button(QDialogButtonBox.Cancel).setText("Cancelar")
        buttons.accepted.connect(self._apply)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _apply(self):
        tabela = storage.table_name(self.layer)
        if not tabela:
            self.reject()
            return
        folder_id = self.combo.currentData()
        try:
            places_model.set_place_folder(tabela, folder_id)
            places_model.rebuild_layer_tree(self.iface)
        except Exception as exc:
            from qgis.PyQt.QtWidgets import QMessageBox

            QMessageBox.critical(
                self, "GeoSketch", "Não foi possível mover:\n{}".format(exc)
            )
            return
        self.accept()

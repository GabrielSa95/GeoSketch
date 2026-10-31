# -*- coding: utf-8 -*-
"""Barra de ferramentas principal e instalacao do menu de contexto."""

import os
import webbrowser

from qgis.core import QgsProject
from qgis.PyQt.QtCore import Qt
from qgis.PyQt.QtGui import QIcon
from qgis.PyQt.QtWidgets import QAction, QMessageBox

from . import places_model, storage
from .dlg_edit import EditDialog
from .dlg_export_kml import ExportKmlDialog
from .dlg_feature import FeatureDialog
from .dlg_goto import GotoDialog
from .dlg_import_kml import ImportKmlDialog
from .dlg_ruler import RulerDialog
from .layeractions import LayerActions

PLUGIN_DIR = os.path.dirname(__file__)


def icon(name):
    return QIcon(os.path.join(PLUGIN_DIR, "icons", name))


class EarthTools(object):
    def __init__(self, iface):
        self.iface = iface
        self.actions = []
        self.toolbar = None
        self._dialogs = []
        self._layer_actions = None
        self._vertex_tool = None
        self._properties_panel = None

    # -------------------------------------------------------------- ciclo
    def initGui(self):
        self.toolbar = self.iface.addToolBar("GeoSketch")
        self.toolbar.setObjectName("FerramentasTerra")

        # "Selecionar" reaproveita a MESMA ação nativa do QGIS (não uma
        # cópia) - mesmo ícone/tooltip/atalho/estado da barra de
        # Digitalização, só disponível também aqui para não obrigar a
        # trocar de barra.
        try:
            self.toolbar.addAction(self.iface.actionSelectFeatures())
            self.toolbar.addSeparator()
        except Exception:
            pass

        self._add("placemark.svg", "Adicionar marcador de local",
                  lambda: self.open_feature("point"))
        self._add("polygon.svg", "Adicionar poligono",
                  lambda: self.open_feature("polygon"))
        self._add("path.svg", "Adicionar caminho",
                  lambda: self.open_feature("line"))
        self._add("circle.svg", "Desenhar círculo (abre a Régua na aba Círculo)",
                  self._open_circle)
        self.toolbar.addSeparator()
        self._add("ruler.svg", "Medir / Régua", self._open_ruler)
        # Calculadora de área e distância e Gerenciar estilos NÃO têm mais
        # ícone nesta barra (ajuste de identidade visual GeoSketch) - as
        # funcionalidades continuam intactas (_open_calculator/
        # open_calculator_for, _open_style_manager, LayerActions._on_style)
        # e acessíveis exclusivamente pelo menu de contexto da camada,
        # dentro do submenu "GeoSketch" ("Calcular medidas...", "Estilo...").
        self.toolbar.addSeparator()
        self._add("folder.svg", "Nova pasta", self._new_group)
        self._add("maps.svg", "Ver no Google Maps", self._open_google_maps)
        self.toolbar.addSeparator()
        self._add("goto.svg", "Ir para coordenadas", self._open_goto)
        self._add("export_map.svg", "Exportar mapa...", self._open_export_map)
        self.toolbar.addSeparator()
        # Importar/Exportar KML/KMZ (Fase F): tirados da barra para reduzir a
        # quantidade de botões - continuam acessíveis pelo menu Vetor >
        # GeoSketch, e agora também pelo botão direito numa pasta
        # específica no painel Camadas (ver layeractions._on_group_context_menu).
        self._add_menu_only("Importar KML/KMZ...", self._open_import_kml)
        self._add_menu_only("Exportar pasta para KML/KMZ...", self._open_export_kml)
        self._add_menu_only("Validar geometrias...", self._open_validate)

        self._layer_actions = LayerActions(self.iface, self)
        self._layer_actions.install()

        from .dlg_properties_panel import PropertiesPanel

        self._properties_panel = PropertiesPanel(self.iface, self, self.iface.mainWindow())
        self.iface.addDockWidget(Qt.RightDockWidgetArea, self._properties_panel)
        self.iface.addPluginToVectorMenu(
            "&GeoSketch", self._properties_panel.toggleViewAction()
        )

        # Organizacao de pastas (Fase B): a arvore de camadas e so uma visao
        # da hierarquia guardada no GeoPackage (ver places_model.py). Ao
        # abrir um projeto, materializa o que estiver la; ao salvar,
        # registra o que o usuario arrastou/renomeou/mostrou-ocultou direto
        # na arvore nativa.
        project = QgsProject.instance()
        try:
            project.readProject.connect(self._rebuild_folders)
            project.writeProject.connect(self._capture_folders)
        except Exception:
            pass
        self._rebuild_folders()

    def unload(self):
        try:
            QgsProject.instance().readProject.disconnect(self._rebuild_folders)
        except Exception:
            pass
        try:
            QgsProject.instance().writeProject.disconnect(self._capture_folders)
        except Exception:
            pass
        if self._layer_actions is not None:
            self._layer_actions.uninstall()
            self._layer_actions = None
        if self._properties_panel is not None:
            try:
                self.iface.removePluginVectorMenu(
                    "&GeoSketch", self._properties_panel.toggleViewAction()
                )
            except Exception:
                pass
            self._properties_panel.disconnect_all()
            try:
                self.iface.removeDockWidget(self._properties_panel)
            except Exception:
                pass
            self._properties_panel.deleteLater()
            self._properties_panel = None
        for dialog in list(self._dialogs):
            try:
                dialog.close()
            except Exception:
                pass
        self._dialogs = []
        for action in self.actions:
            # Ações criadas por _add_menu_only() nunca entraram numa barra -
            # removeToolBarIcon() é no-op nesse caso, mas sem try/except uma
            # mudança de comportamento entre versões do QGIS não travaria o
            # unload() inteiro por causa de uma ação só.
            try:
                self.iface.removeToolBarIcon(action)
            except Exception:
                pass
            self.iface.removePluginVectorMenu("&GeoSketch", action)
        self.actions = []
        if self.toolbar is not None:
            del self.toolbar
            self.toolbar = None

    def _add(self, icon_name, text, callback):
        action = QAction(icon(icon_name), text, self.iface.mainWindow())
        action.setToolTip(text)
        action.triggered.connect(callback)
        self.toolbar.addAction(action)
        self.iface.addPluginToVectorMenu("&GeoSketch", action)
        self.actions.append(action)
        return action

    def _add_menu_only(self, text, callback):
        """Como _add(), mas só no menu Vetor > GeoSketch, sem botão
        na barra - para acções que já têm outro caminho rápido (ex.: menu
        de contexto da pasta) e não precisam de mais um ícone na barra
        principal."""
        action = QAction(text, self.iface.mainWindow())
        action.triggered.connect(callback)
        self.iface.addPluginToVectorMenu("&GeoSketch", action)
        self.actions.append(action)
        return action

    # -------------------------------------------------------------- acoes
    def _track(self, dialog):
        self._dialogs.append(dialog)
        dialog.finished.connect(lambda _: self._untrack(dialog))
        return dialog

    def _untrack(self, dialog):
        if dialog in self._dialogs:
            self._dialogs.remove(dialog)

    def open_feature(self, kind, group=None):
        """Abre a janela de criacao. group = grupo da arvore que recebe a camada."""
        dialog = FeatureDialog(self.iface, kind, group, self.iface.mainWindow())
        self._track(dialog)
        dialog.show()

    def edit_place(self, layer):
        """Abre a janela de edicao daquele lugar (nome, estilo e pontos)."""
        if not storage.is_place_layer(layer):
            QMessageBox.information(
                self.iface.mainWindow(),
                "GeoSketch",
                "Selecione um lugar criado pelo plugin para editar.",
            )
            return
        dialog = EditDialog(self.iface, layer, self.iface.mainWindow())
        self._track(dialog)
        dialog.show()

    def _open_ruler(self):
        dialog = RulerDialog(self.iface, self.iface.mainWindow())
        self._track(dialog)
        dialog.show()

    def _open_goto(self):
        dialog = GotoDialog(self.iface, self.iface.mainWindow())
        self._track(dialog)
        dialog.show()

    def _new_group(self):
        from qgis.PyQt.QtWidgets import QInputDialog

        name, ok = QInputDialog.getText(
            self.iface.mainWindow(), "Nova pasta", "Nome da pasta:", text="Nova pasta"
        )
        if not ok or not name.strip():
            return
        try:
            places_model.create_folder(name.strip())
            places_model.rebuild_layer_tree(self.iface)
        except Exception as exc:
            QMessageBox.critical(
                self.iface.mainWindow(),
                "GeoSketch",
                "Não foi possível criar a pasta:\n{}".format(exc),
            )

    def _open_import_kml(self):
        dialog = ImportKmlDialog(self.iface, self.iface.mainWindow())
        self._track(dialog)
        dialog.show()

    def _open_export_kml(self):
        dialog = ExportKmlDialog(self.iface, self.iface.mainWindow())
        dialog.exec_()

    def _open_validate(self):
        from .dlg_validate import ValidateDialog

        selected = self._layer_actions._selected_places() if self._layer_actions else []
        dialog = ValidateDialog(self.iface, selected, self.iface.mainWindow())
        self._track(dialog)
        dialog.show()

    def _open_calculator(self):
        self.open_calculator_for(None)

    def open_calculator_for(self, layer):
        """Como _open_calculator(), mas pré-seleciona `layer` (ou o
        primeiro lugar da lista, se None) - usada pelo menu de contexto da
        camada e pelo painel de propriedades. Separada do callback ligado
        ao QAction (_open_calculator, sem parâmetros extras) porque
        QAction.triggered emite um bool (checked) que o PyQt passaria para
        um parâmetro opcional posicional de _open_calculator() se ela
        aceitasse um, confundindo esse bool com a camada."""
        from .dlg_calculator import CalculatorDialog

        dialog = CalculatorDialog(self.iface, self.iface.mainWindow(), initial_layer=layer)
        self._track(dialog)
        dialog.show()

    def _open_export_map(self):
        self.open_export_map_for(None)

    def open_export_map_for(self, layer):
        """Como open_calculator_for(), para Exportar mapa."""
        from .dlg_export_map import ExportMapDialog

        dialog = ExportMapDialog(self.iface, self.iface.mainWindow(), initial_layer=layer)
        self._track(dialog)
        dialog.show()

    def _open_circle(self):
        """Botao 'Desenhar circulo' da barra: abre a Regua ja na aba
        Circulo, reaproveitando RulerDialog (Fase 5 documenta que a Regua
        é a única ferramenta de círculo do plugin - não existe 'kind'
        próprio de círculo em dlg_feature.py)."""
        dialog = RulerDialog(self.iface, self.iface.mainWindow(), initial_tab=3)
        self._track(dialog)
        dialog.show()

    def _open_style_manager(self):
        """Botao 'Gerenciar estilos' da barra: reaproveita a mesma acao
        'Estilo...' do menu de contexto, sobre o(s) lugar(es)
        selecionado(s) no painel Camadas agora."""
        if self._layer_actions is not None:
            self._layer_actions._on_style()

    def _rebuild_folders(self):
        places_model.rebuild_layer_tree(self.iface)

    def _capture_folders(self, *_args):
        places_model.capture_layer_tree(self.iface)

    def _open_google_maps(self):
        canvas = self.iface.mapCanvas()
        try:
            from . import utils

            wgs = utils.to_wgs84(canvas.center(), canvas.mapSettings().destinationCrs())
        except Exception:
            QMessageBox.warning(
                self.iface.mainWindow(),
                "GeoSketch",
                "Nao foi possivel converter o centro do mapa.",
            )
            return
        scale = canvas.scale()
        zoom = 3
        for level in range(1, 22):
            if 591657550.5 / (2 ** (level - 1)) < scale * 2:
                zoom = level
                break
        webbrowser.open(
            "https://www.google.com/maps/@{:.6f},{:.6f},{}z/data=!3m1!1e3".format(
                wgs.y(), wgs.x(), zoom
            )
        )

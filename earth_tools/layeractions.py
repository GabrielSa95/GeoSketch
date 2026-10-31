# -*- coding: utf-8 -*-
"""Itens do plugin no menu de botao direito do painel Camadas.

NAO usamos QgsLayerTreeView.setMenuProvider(): esse metodo ASSUME A POSSE do
provedor e DELETA o anterior. Guardar o provedor original e chamar
createContextMenu() nele acessa memoria liberada e derruba o QGIS inteiro.

Para CAMADAS (lugares), usamos addCustomActionForLayerType /
addCustomActionForLayer, que e a API feita para isso: o QGIS continua dono
do menu e apenas encaixa nossas acoes.

Para PASTAS (grupos da arvore), essa API nao serve - e so para camadas. Fase
F: usamos o sinal QgsLayerTreeView.contextMenuAboutToShow(menu), disponivel
a partir do QGIS 3.32, que e a mesma ideia (so ACRESCENTA itens ao QMenu que
o QGIS continua controlando, nunca assume posse dele) aplicada a grupos.
Conexao best-effort (try/except), porque o qgisMinimumVersion deste plugin
(3.22) e anterior a esse sinal - ver LayerActions.install()/_on_group_context_menu.
"""

import os
import subprocess
import sys
import tempfile
import webbrowser

from qgis.core import QgsLayerTree, QgsProject, QgsVectorFileWriter
from qgis.PyQt.QtCore import QEvent, QObject, Qt
from qgis.PyQt.QtGui import QIcon
from qgis.PyQt.QtWidgets import (
    QAbstractItemView,
    QAction,
    QFileDialog,
    QInputDialog,
    QMenu,
    QMessageBox,
)

from . import kml_bridge, kml_io, places_model, storage, utils
from .dlg_buffer import BufferDialog
from .dlg_clip import ClipDialog
from .dlg_style_manager import StyleManagerDialog
from .dlg_difference import DifferenceDialog
from .dlg_split import SplitDialog
from .dlg_union import UnionDialog

PLUGIN_DIR = os.path.dirname(__file__)


def _vector_type():
    """O enum de tipo de camada mudou de lugar entre versoes."""
    try:
        from qgis.core import Qgis

        return Qgis.LayerType.Vector
    except Exception:
        from qgis.core import QgsMapLayerType

        return QgsMapLayerType.VectorLayer


def icon(name):
    return QIcon(os.path.join(PLUGIN_DIR, "icons", name))


class DeleteKeyFilter(QObject):
    """Captura a tecla Delete no painel Camadas.

    Filtro de evento em vez de atalho global de propósito: precisamos deixar o
    Delete passar quando a árvore está em modo de renomear, senão o usuário não
    consegue apagar uma letra do nome sem apagar a camada inteira.
    """

    def __init__(self, view, handler):
        super(DeleteKeyFilter, self).__init__(view)
        self.view = view
        self.handler = handler

    def eventFilter(self, obj, event):
        try:
            if event.type() != QEvent.KeyPress:
                return False
            if event.key() not in (Qt.Key_Delete, Qt.Key_Backspace):
                return False
            if self.view.state() == QAbstractItemView.EditingState:
                return False  # está renomeando: a tecla é do campo de texto
            self.handler()
            return True
        except Exception:
            return False


class LayerActions(object):
    def __init__(self, iface, plugin):
        self.iface = iface
        self.plugin = plugin
        self.actions = []
        self.place_actions = []  # so aparecem nos lugares criados pelo plugin
        self._delete_filter = None
        self._group_menu_connected = False
        self._add_menu = None

    # ---------------------------------------------------------- instalacao
    def install(self):
        window = self.iface.mainWindow()
        vector = _vector_type()

        def make(text, ico, callback, menu, all_layers):
            action = QAction(icon(ico) if ico else QIcon(), text, window)
            action.triggered.connect(callback)
            self.iface.addCustomActionForLayerType(action, menu, vector, all_layers)
            self.actions.append(action)
            if not all_layers:
                self.place_actions.append(action)
            return action

        def header(text):
            """Rotulo de secao dentro do submenu 'GeoSketch': um
            QAction desabilitado (sem callback), so para separar visualmente
            as categorias - addCustomActionForLayerType não expõe uma forma
            de inserir um QMenu.addSeparator() real dentro do submenu que o
            próprio QGIS continua controlando, então um item desabilitado é
            a forma segura de sinalizar a categoria sem arriscar o aviso no
            topo deste arquivo sobre nunca assumir posse do menu."""
            action = make(text, None, lambda: None, SUBMENU, False)
            action.setEnabled(False)
            return action

        # Todas as ações de lugar (exceto Excluir) ficam dentro de UM
        # submenu "GeoSketch" no menu de contexto da camada, em vez
        # de soltas na raiz - organizadas por categoria com rótulos de seção
        # (desabilitados, não clicáveis). Reduz a quantidade de itens
        # expostos de uma vez no menu de contexto sem remover nenhuma ação.
        SUBMENU = "GeoSketch"

        make("Editar...", "vertex.svg", self._edit_points, SUBMENU, False)
        make("Ir para", "goto.svg", self._goto_layer, SUBMENU, False)
        make("Mover para pasta...", "folder.svg", self._move_to_folder, SUBMENU, False)
        make("Estilo...", "style.svg", self._on_style, SUBMENU, False)

        header("— GEOPROCESSAMENTO —")
        make("Gerar Buffer...", None, self._on_buffer, SUBMENU, False)
        make("Unir polígonos...", None, self._on_union, SUBMENU, False)
        make("Dividir polígono...", None, self._on_split, SUBMENU, False)
        make("Recortar com...", None, self._on_clip, SUBMENU, False)
        make("Diferença...", None, self._on_difference, SUBMENU, False)

        header("— MEDIÇÕES —")
        make("Calcular medidas...", "calculator.svg", self._on_calculate, SUBMENU, False)

        header("— VALIDAÇÃO —")
        make("Validar geometria...", None, self._on_validate, SUBMENU, False)

        header("— EXPORTAÇÃO —")
        make("Salvar lugar como...", None, self._save_as, SUBMENU, False)
        make("Enviar por e-mail...", None, self._email, SUBMENU, False)
        make("Exportar mapa...", "export_map.svg", self._on_export_map, SUBMENU, False)

        # Excluir fica FORA do submenu, na raiz do menu de contexto - ação
        # destrutiva, não deve ficar escondida junto das demais.
        make("Excluir", None, self.delete_selected, "", False)

        # Submenu "Adicionar", disponivel em qualquer camada vetorial.
        #
        # Correcao (ajuste pontual pedido pelo usuario): antes, cada uma das
        # 6 acoes abaixo era registrada com uma chamada SEPARADA a
        # addCustomActionForLayerType(acao, "Adicionar", vector, True) - a
        # API do QGIS nao garante mesclar essas 6 chamadas num unico
        # submenu (confirmado: a interface real mostrava varias entradas
        # de topo repetindo o nome "Adicionar", uma por acao, em vez de uma
        # so com 6 itens dentro). A correcao usa um QMenu proprio: criamos
        # UM QMenu("Adicionar") e cada acao e adicionada a ELE diretamente
        # (QMenu.addAction - API nativa do Qt, nao a da API de agrupamento
        # por nome do QGIS); so o QAction do proprio menu
        # (QMenu.menuAction()) e registrado no QGIS, com menu="" (raiz) -
        # o Qt desenha a seta de submenu sozinho porque esse QAction tem
        # um QMenu associado. Textos, icones, callbacks, parametros e
        # ordem das 6 acoes abaixo sao exatamente os mesmos de antes.
        self._add_menu = QMenu("Adicionar", window)

        def make_add(text, ico, callback):
            action = QAction(icon(ico) if ico else QIcon(), text, window)
            action.triggered.connect(callback)
            self._add_menu.addAction(action)
            return action

        make_add("Pasta", "folder.svg", self._new_group)
        make_add("Modelo de propriedade rural", "folder.svg",
                 self._new_property_template)
        make_add("Marcador de local", "placemark.svg",
                 lambda: self.plugin.open_feature("point", self._current_group()))
        make_add("Caminho", "path.svg",
                 lambda: self.plugin.open_feature("line", self._current_group()))
        make_add("Poligono", "polygon.svg",
                 lambda: self.plugin.open_feature("polygon", self._current_group()))
        make_add("Sobreposicao de imagem", None, self._image_overlay)

        self.iface.addCustomActionForLayerType(self._add_menu.menuAction(), "", vector, True)
        self.actions.append(self._add_menu.menuAction())

        # Registra o que ja existe e o que vier depois.
        for layer in QgsProject.instance().mapLayers().values():
            self.register_layer(layer)
        try:
            QgsProject.instance().layersAdded.connect(self._layers_added)
        except Exception:
            pass

        try:
            view = self.iface.layerTreeView()
            self._delete_filter = DeleteKeyFilter(view, self.delete_selected)
            view.installEventFilter(self._delete_filter)
        except Exception:
            self._delete_filter = None

        # Importar/Exportar KML/KMZ no menu de contexto da pasta (Fase F).
        # QgsLayerTreeView.contextMenuAboutToShow só existe a partir do QGIS
        # 3.32 (qgisMinimumVersion deste plugin é 3.22) - conexão best-effort,
        # igual ao resto deste arquivo; em versões mais antigas o menu de
        # contexto simplesmente não ganha esses itens, mas o menu Vetor >
        # GeoSketch continua dando acesso a importar/exportar. É
        # seguro porque só ACRESCENTA itens ao QMenu que o QGIS continua
        # controlando - nunca assume posse dele (ver o aviso no topo deste
        # arquivo sobre por que setMenuProvider() foi evitado).
        try:
            self.iface.layerTreeView().contextMenuAboutToShow.connect(
                self._on_group_context_menu
            )
            self._group_menu_connected = True
        except Exception:
            self._group_menu_connected = False

    def uninstall(self):
        if getattr(self, "_delete_filter", None) is not None:
            try:
                self.iface.layerTreeView().removeEventFilter(self._delete_filter)
            except Exception:
                pass
            self._delete_filter = None
        try:
            QgsProject.instance().layersAdded.disconnect(self._layers_added)
        except Exception:
            pass
        if self._group_menu_connected:
            try:
                self.iface.layerTreeView().contextMenuAboutToShow.disconnect(
                    self._on_group_context_menu
                )
            except Exception:
                pass
            self._group_menu_connected = False
        for action in self.actions:
            try:
                self.iface.removeCustomActionForLayerType(action)
            except Exception:
                pass
        self.actions = []
        self.place_actions = []
        self._add_menu = None

    def _layers_added(self, layers):
        for layer in layers:
            self.register_layer(layer)

    def register_layer(self, layer):
        """Libera as acoes de lugar naquela camada especifica."""
        if not storage.is_place_layer(layer):
            return
        for action in self.place_actions:
            try:
                self.iface.addCustomActionForLayer(action, layer)
            except Exception:
                pass

    # --------------------------------------------------------------- apoio
    def _current_layer(self):
        try:
            return self.iface.layerTreeView().currentLayer()
        except Exception:
            return None

    def _current_group(self):
        try:
            node = self.iface.layerTreeView().currentNode()
            if node is not None and hasattr(node, "addGroup"):
                return node
            group = self.iface.layerTreeView().currentGroupNode()
            root = QgsProject.instance().layerTreeRoot()
            return group if group is not None and group != root else None
        except Exception:
            return None

    # --------------------------------------------------------------- acoes
    def _edit_points(self):
        layer = self._current_layer()
        if layer is None:
            return
        self.plugin.edit_place(layer)

    def _goto_layer(self):
        layer = self._current_layer()
        if layer is None:
            return
        utils.zoom_to_layer(self.iface, layer)

    def _on_buffer(self):
        """Gera Buffer do(s) lugar(es) selecionados (Fase F1). Seleção
        múltipla via _selected_places() - selecionar vários lugares e
        pedir Buffer dissolve todos de uma vez, em vez de só considerar a
        camada 'atual'."""
        places = self._selected_places()
        if not places:
            QMessageBox.information(
                self.iface.mainWindow(),
                "GeoSketch",
                "Selecione um ou mais lugares criados pelo plugin para gerar o Buffer.",
            )
            return
        dialog = BufferDialog(self.iface, places, self.iface.mainWindow())
        dialog.exec_()

    def _selected_places(self):
        """Lugares do plugin selecionados no painel Camadas agora (igual a
        _on_buffer()/delete_selected()) - cai para a camada 'atual' se a
        API de seleção múltipla não devolver nada."""
        try:
            view = self.iface.layerTreeView()
            nodes = view.selectedNodes(True)
        except Exception:
            nodes = []
        places, _others, _groups = _collect(nodes)
        if not places:
            layer = self._current_layer()
            if layer is not None and storage.is_place_layer(layer):
                places = [layer]
        return places

    def _on_union(self):
        places = self._selected_places()
        poligonos = [
            layer for layer in places if layer.customProperty(storage.CUSTOM_KEY) == "polygon"
        ]
        if len(poligonos) < 2:
            QMessageBox.information(
                self.iface.mainWindow(),
                "GeoSketch",
                "Selecione pelo menos 2 polígonos criados pelo plugin para unir.",
            )
            return
        if len(poligonos) != len(places):
            QMessageBox.warning(
                self.iface.mainWindow(),
                "GeoSketch",
                "{} lugar(es) selecionado(s) não são polígonos e foram ignorados.".format(
                    len(places) - len(poligonos)
                ),
            )
        dialog = UnionDialog(self.iface, poligonos, self.iface.mainWindow())
        dialog.exec_()

    def _on_split(self):
        """Divide um único polígono por uma linha de corte (Fase F3). Só
        faz sentido com UM polígono - usa a camada 'atual', não a seleção
        múltipla (diferente de Buffer/União)."""
        layer = self._current_layer()
        if layer is None or layer.customProperty(storage.CUSTOM_KEY) != "polygon":
            QMessageBox.information(
                self.iface.mainWindow(),
                "GeoSketch",
                "Selecione um único polígono criado pelo plugin para dividir.",
            )
            return
        dialog = SplitDialog(self.iface, layer, self.iface.mainWindow())
        self.plugin._track(dialog)
        dialog.show()

    def _on_clip(self):
        """Recorta a camada atual usando outro polígono como máscara
        (Fase F4). Precisa de pelo menos 1 polígono no projeto para servir
        de máscara."""
        all_places = [
            layer for layer in QgsProject.instance().mapLayers().values()
            if storage.is_place_layer(layer)
        ]
        tem_poligono = any(
            layer.customProperty(storage.CUSTOM_KEY) == "polygon" for layer in all_places
        )
        if not tem_poligono:
            QMessageBox.information(
                self.iface.mainWindow(),
                "GeoSketch",
                "É preciso ter pelo menos um polígono no projeto para usar como máscara.",
            )
            return
        layer = self._current_layer()
        target = layer if layer is not None and storage.is_place_layer(layer) else None
        dialog = ClipDialog(self.iface, all_places, target, self.iface.mainWindow())
        dialog.exec_()

    def _on_difference(self):
        """Diferenca (Fase F5): remove de um lugar a parte que se
        sobrepoe a outro. Precisa de pelo menos 2 lugares no projeto."""
        all_places = [
            layer for layer in QgsProject.instance().mapLayers().values()
            if storage.is_place_layer(layer)
        ]
        if len(all_places) < 2:
            QMessageBox.information(
                self.iface.mainWindow(),
                "GeoSketch",
                "É preciso ter pelo menos 2 lugares no projeto para calcular a diferença.",
            )
            return
        layer = self._current_layer()
        base = layer if layer is not None and storage.is_place_layer(layer) else None
        dialog = DifferenceDialog(self.iface, all_places, base, self.iface.mainWindow())
        dialog.exec_()

    def _on_style(self):
        """Abre o Gerenciador de Estilos (Fase H) para o(s) lugar(es)
        selecionados - mesma seleção múltipla de Buffer/União."""
        places = self._selected_places()
        if not places:
            QMessageBox.information(
                self.iface.mainWindow(),
                "GeoSketch",
                "Selecione um ou mais lugares criados pelo plugin para editar o estilo.",
            )
            return
        dialog = StyleManagerDialog(self.iface, places, self.iface.mainWindow())
        dialog.exec_()

    def _on_calculate(self):
        """Abre a Calculadora de área e distância (menu de contexto) já
        pré-selecionada no lugar clicado, reaproveitando a mesma janela
        aberta pelo menu Vetor > GeoSketch (earth_tools._open_calculator)."""
        places = self._selected_places()
        if not places:
            QMessageBox.information(
                self.iface.mainWindow(),
                "GeoSketch",
                "Selecione um lugar criado pelo plugin para calcular as medidas.",
            )
            return
        self.plugin.open_calculator_for(places[0])

    def _on_validate(self):
        """Abre o Validador de geometrias (menu de contexto) com o(s)
        lugar(es) selecionado(s) já marcados - reaproveita earth_tools.
        _open_validate(), que já lê _selected_places() internamente."""
        self.plugin._open_validate()

    def _on_export_map(self):
        """Abre Exportar mapa (menu de contexto) com a extensão já
        ajustada ao lugar clicado, reaproveitando earth_tools.open_export_map_for()."""
        places = self._selected_places()
        self.plugin.open_export_map_for(places[0] if places else None)

    def delete_selected(self):
        """Confirma e exclui o que estiver selecionado no painel Camadas."""
        try:
            view = self.iface.layerTreeView()
            nodes = view.selectedNodes(True)
        except Exception:
            return
        if not nodes:
            return

        places, others, groups = _collect(nodes)
        if not places and not others and not groups:
            return

        texto = _confirm_text(places, others, groups)
        box = QMessageBox(self.iface.mainWindow())
        box.setIcon(QMessageBox.Warning)
        box.setWindowTitle("Confirmar exclusao")
        box.setText("Deseja mesmo excluir?")
        box.setInformativeText(texto)
        box.setStandardButtons(QMessageBox.Yes | QMessageBox.No)
        box.setDefaultButton(QMessageBox.No)
        box.button(QMessageBox.Yes).setText("Excluir")
        box.button(QMessageBox.No).setText("Cancelar")
        if box.exec_() != QMessageBox.Yes:
            return

        failed_names = []
        for layer in places:
            nome = layer.name()
            # Captura a chave ANTES de apagar: depois de delete_place() o
            # objeto Python pode nao ser mais seguro de consultar.
            tabela = storage.table_name(layer)
            try:
                removed = storage.delete_place(layer)
            except Exception:
                removed = False
            if not removed:
                failed_names.append(nome)
            try:
                places_model.remove_place_membership(tabela)
            except Exception as exc:
                utils.log(
                    "Falha ao limpar organizacao do lugar '{}': {}".format(nome, exc),
                    "warning",
                )
        for layer in others:
            try:
                QgsProject.instance().removeMapLayer(layer.id())
            except Exception:
                pass
        for node in groups:
            # Captura os ids canonicos da pasta E de qualquer subpasta
            # aninhada ANTES de remover o no - apagar o grupo apaga a
            # subarvore inteira, e cada subpasta rastreada precisa do
            # proprio registro limpo, senao fica orfao no GeoPackage.
            folder_ids = []
            top_fid = places_model.resolve_group_folder_id(node)
            if top_fid:
                folder_ids.append(top_fid)
            folder_ids.extend(_nested_folder_ids(node))
            try:
                parent = node.parent()
                if parent is not None:
                    parent.removeChildNode(node)
            except Exception:
                pass
            for fid in folder_ids:
                try:
                    places_model.delete_folder_record(fid)
                except Exception as exc:
                    utils.log(
                        "Falha ao limpar registro da pasta '{}': {}".format(fid, exc),
                        "warning",
                    )

        total = len(places) + len(others) + len(groups)
        self.iface.messageBar().pushInfo(
            "GeoSketch", "{} item(ns) excluido(s).".format(total)
        )
        if failed_names:
            # Saiu do painel, mas a tabela pode ter ficado orfa no GeoPackage
            # (ex.: arquivo bloqueado por outro programa). Avisa quais, para
            # nao dar a falsa impressao de exclusao completa. storage.delete_place
            # ja registrou o detalhe tecnico de cada uma; aqui so o resumo.
            utils.log(
                "Exclusao incompleta no GeoPackage para: {}".format(", ".join(failed_names)),
                "warning",
            )
            QMessageBox.warning(
                self.iface.mainWindow(),
                "GeoSketch",
                "{} saiu do painel, mas a tabela não pôde ser apagada do "
                "arquivo:\n{}\n\nArquivo: {}".format(
                    "Estes itens" if len(failed_names) > 1 else "Este item",
                    ", ".join(failed_names),
                    storage.gpkg_path(),
                ),
            )

    def _new_group(self):
        name, ok = QInputDialog.getText(
            self.iface.mainWindow(), "Nova pasta", "Nome da pasta:", text="Nova pasta"
        )
        if not ok or not name.strip():
            return
        pai_id = places_model.resolve_group_folder_id(self._current_group())
        try:
            places_model.create_folder(name.strip(), pai_id=pai_id)
            places_model.rebuild_layer_tree(self.iface)
        except Exception as exc:
            QMessageBox.critical(
                self.iface.mainWindow(),
                "GeoSketch",
                "Não foi possível criar a pasta:\n{}".format(exc),
            )

    def _new_property_template(self):
        name, ok = QInputDialog.getText(
            self.iface.mainWindow(),
            "Modelo de propriedade rural",
            "Nome do imóvel:",
            text="Imóvel sem título",
        )
        if not ok or not name.strip():
            return
        pai_id = places_model.resolve_group_folder_id(self._current_group())
        try:
            places_model.create_property_template(name.strip(), pai_id=pai_id)
            places_model.rebuild_layer_tree(self.iface)
        except Exception as exc:
            QMessageBox.critical(
                self.iface.mainWindow(),
                "GeoSketch",
                "Não foi possível criar o modelo:\n{}".format(exc),
            )

    def _move_to_folder(self):
        layer = self._current_layer()
        if layer is None:
            return
        from .dlg_move_folder import MoveFolderDialog

        dialog = MoveFolderDialog(self.iface, layer, self.iface.mainWindow())
        dialog.exec_()

    # ----------------------------------------------- menu de contexto (pasta)
    def _on_group_context_menu(self, menu):
        """Acrescenta "Importar/Exportar KML/KMZ" ao menu de contexto do
        painel Camadas quando o item clicado é uma PASTA rastreada pelo
        plugin (Fase F). Só ACRESCENTA ao QMenu que o QGIS continua
        controlando (ver o comentário no topo do arquivo) - nunca cria ou
        assume posse de um menu próprio."""
        try:
            node = self.iface.layerTreeView().currentNode()
        except Exception:
            return
        if node is None or not QgsLayerTree.isGroup(node):
            return
        folder_id = places_model.resolve_group_folder_id(node)
        if not folder_id:
            return  # grupo nativo, nao rastreado pelo plugin - nao opina

        menu.addSeparator()
        act_import = menu.addAction(
            icon("import_kml.svg"), "Importar KML/KMZ para esta pasta..."
        )
        act_import.triggered.connect(lambda: self._import_into_folder(folder_id))

        act_export = menu.addAction(
            icon("export_kml.svg"), "Exportar esta pasta para KML/KMZ..."
        )
        act_export.triggered.connect(lambda: self._export_folder(folder_id))

        try:
            property_root = places_model.find_property_root(folder_id)
        except Exception:
            property_root = None
        if property_root and property_root != folder_id:
            act_property = menu.addAction("Exportar propriedade completa...")
            act_property.triggered.connect(lambda: self._export_folder(property_root))

    def _import_into_folder(self, folder_id):
        from .dlg_import_kml import ImportKmlDialog

        dialog = ImportKmlDialog(self.iface, self.iface.mainWindow(), preselect_folder_id=folder_id)
        self.plugin._track(dialog)
        dialog.show()

    def _export_folder(self, folder_id):
        from .dlg_export_kml import ExportKmlDialog

        dialog = ExportKmlDialog(self.iface, self.iface.mainWindow(), preselect_folder_id=folder_id)
        dialog.exec_()

    def _export(self, layer, path, driver):
        options = QgsVectorFileWriter.SaveVectorOptions()
        options.driverName = driver
        options.fileEncoding = "UTF-8"
        context = QgsProject.instance().transformContext()
        if hasattr(QgsVectorFileWriter, "writeAsVectorFormatV3"):
            result = QgsVectorFileWriter.writeAsVectorFormatV3(layer, path, context, options)
        else:
            result = QgsVectorFileWriter.writeAsVectorFormatV2(layer, path, context, options)
        return result[0] == QgsVectorFileWriter.NoError, result[1]

    def _export_place_kml(self, layer, path, as_kmz):
        """KML/KMZ de UM lugar, pelo escritor proprio (kml_io), nao pelo
        driver generico do GDAL - preserva nome/descricao/estilo de forma
        mais fiel (Fase D). Usado tanto por 'Salvar lugar como...' quanto
        por 'Enviar por e-mail...', para nao ter dois geradores de KML
        divergentes."""
        tree = kml_bridge.export_layer(layer)
        if tree is None:
            return False, "lugar sem feição para exportar"
        try:
            data = kml_io.build_kmz(tree) if as_kmz else kml_io.build_kml(tree).encode("utf-8")
            with open(path, "wb") as f:
                f.write(data)
        except Exception as exc:
            return False, str(exc)
        return True, None

    def _save_as(self):
        self._save_as_layer(self._current_layer())

    def _save_as_layer(self, layer):
        """Separado de _save_as() para poder ser chamado com uma camada
        explícita (painel de propriedades) sem o truque de argumento
        opcional do Qt: QAction.triggered emite um bool (checked) que o
        PyQt passaria para um parâmetro opcional posicional de _save_as()
        se ela aceitasse um, confundindo esse bool com a camada - por isso
        o callback ligado ao QAction (_save_as, sem parâmetros extras)
        fica separado deste método, que sempre recebe a camada de forma
        explícita."""
        if layer is None:
            return
        path, selected = QFileDialog.getSaveFileName(
            self.iface.mainWindow(),
            "Salvar lugar como",
            layer.name(),
            "Google Earth (*.kml);;Google Earth compactado (*.kmz);;"
            "GeoPackage (*.gpkg);;Shapefile (*.shp);;GeoJSON (*.geojson)",
        )
        if not path:
            return
        low = selected.lower()
        if "kmz" in low:
            ok, message = self._export_place_kml(layer, path, as_kmz=True)
        elif "kml" in low:
            ok, message = self._export_place_kml(layer, path, as_kmz=False)
        else:
            driver = "GPKG" if "gpkg" in low else "ESRI Shapefile" if "shp" in low else "GeoJSON"
            ok, message = self._export(layer, path, driver)
        if ok:
            self.iface.messageBar().pushSuccess("GeoSketch", "Salvo em " + path)
        else:
            QMessageBox.warning(self.iface.mainWindow(), "Salvar lugar como", message)

    def _email(self):
        layer = self._current_layer()
        if layer is None:
            return
        folder = tempfile.gettempdir()
        path = os.path.join(folder, storage.slug(layer.name()) + ".kml")
        ok, message = self._export_place_kml(layer, path, as_kmz=False)
        if not ok:
            QMessageBox.warning(self.iface.mainWindow(), "Enviar por e-mail", message)
            return
        try:
            if sys.platform.startswith("win"):
                subprocess.Popen(["explorer", "/select,", os.path.normpath(path)])
            elif sys.platform == "darwin":
                subprocess.Popen(["open", "-R", path])
            else:
                subprocess.Popen(["xdg-open", folder])
        except Exception:
            pass
        webbrowser.open(
            "mailto:?subject={}&body=Segue%20o%20arquivo%20{}".format(
                layer.name().replace(" ", "%20"), os.path.basename(path)
            )
        )
        self.iface.messageBar().pushInfo(
            "GeoSketch", "Arquivo gerado em {}. Anexe-o ao e-mail.".format(path)
        )

    def _image_overlay(self):
        path, _ = QFileDialog.getOpenFileName(
            self.iface.mainWindow(),
            "Sobreposicao de imagem",
            "",
            "Imagens (*.tif *.tiff *.jpg *.jpeg *.png *.ecw *.sid)",
        )
        if not path:
            return
        layer = self.iface.addRasterLayer(path, os.path.basename(path))
        if layer is None or not layer.isValid():
            answer = QMessageBox.question(
                self.iface.mainWindow(),
                "Sobreposicao de imagem",
                "A imagem nao tem coordenadas. Abrir o Georreferenciador?",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.Yes,
            )
            if answer == QMessageBox.Yes:
                QMessageBox.information(
                    self.iface.mainWindow(),
                    "Sobreposicao de imagem",
                    "Abra em Raster > Georreferenciador.",
                )


# --------------------------------------------------------------------------
# Exclusao com confirmacao (tecla Delete ou item do menu)
# --------------------------------------------------------------------------
def _collect(nodes):
    """Separa o que foi selecionado em lugares, camadas comuns e pastas.

    Precisa entrar nas pastas: apagar uma pasta tem que apagar os lugares que
    estao dentro dela, senao ficariam tabelas orfas no GeoPackage.
    """
    places, others, groups = [], [], []
    seen = set()

    def add_layer(layer):
        if layer is None or layer.id() in seen:
            return
        seen.add(layer.id())
        if storage.is_place_layer(layer):
            places.append(layer)
        else:
            others.append(layer)

    for node in nodes:
        try:
            if QgsLayerTree.isGroup(node):
                groups.append(node)
                for child in node.findLayers():
                    add_layer(child.layer())
            elif QgsLayerTree.isLayer(node):
                add_layer(node.layer())
        except Exception:
            continue
    return places, others, groups


def _nested_folder_ids(node):
    """Ids canonicos de pasta de qualquer subgrupo dentro de node, em
    qualquer profundidade - usado para limpar o registro das subpastas
    quando o grupo-mae e apagado de uma vez."""
    ids = []
    for child in node.children():
        if QgsLayerTree.isGroup(child):
            fid = places_model.resolve_group_folder_id(child)
            if fid:
                ids.append(fid)
            ids.extend(_nested_folder_ids(child))
    return ids


def _confirm_text(places, others, groups):
    linhas = []
    if places:
        nomes = ", ".join(l.name() for l in places[:4])
        if len(places) > 4:
            nomes += " e mais {}".format(len(places) - 4)
        linhas.append(
            "{} lugar(es) serao APAGADOS do arquivo Meus Lugares, sem volta:\n{}".format(
                len(places), nomes
            )
        )
    if others:
        linhas.append(
            "{} camada(s) serao removidas do projeto. Os arquivos de origem "
            "delas NAO serao apagados.".format(len(others))
        )
    if groups:
        linhas.append("{} pasta(s) serao removidas.".format(len(groups)))
    return "\n\n".join(linhas)

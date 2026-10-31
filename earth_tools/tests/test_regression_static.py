# -*- coding: utf-8 -*-
"""Testes de regressão por inspeção de código-fonte (sem PyQGIS).

Cobrem os itens da Fase 7 que são fatos sobre o CÓDIGO em si (arquivo
existe/não existe, string removida, padrão perigoso não reintroduzido),
não sobre o comportamento em tempo de execução do QGIS - esses últimos
estão em test_qgis_integration.py (precisa do módulo `qgis`) ou no roteiro
de validação manual (Fase 8). Roda com `python -m unittest`, sem PyQGIS,
igual a test_geometry_rules.py e test_measure_rules.py.
"""

import os
import unittest

PLUGIN_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _read(relative_path):
    with open(os.path.join(PLUGIN_DIR, relative_path), "r", encoding="utf-8") as handle:
        return handle.read()


class HistoricoDeImagensSuspensoTests(unittest.TestCase):
    """Fase 2 / item 14 da Fase 7: nenhuma consulta de satélite automática."""

    REMOVIDOS = [
        "dlg_imagery.py",
        "imagery_bridge.py",
        "imagery_cache.py",
        "imagery_timeline.py",
        "stac_client.py",
        os.path.join("tests", "test_imagery_cache.py"),
        os.path.join("tests", "test_imagery_timeline.py"),
        os.path.join("tests", "test_stac_client.py"),
        os.path.join("icons", "imagery.svg"),
    ]

    def test_modulos_de_imagem_nao_existem_mais(self):
        for relative_path in self.REMOVIDOS:
            path = os.path.join(PLUGIN_DIR, relative_path)
            self.assertFalse(os.path.exists(path), "{} deveria ter sido removido".format(relative_path))

    def test_earth_tools_nao_referencia_mais_imagery(self):
        source = _read("earth_tools.py").lower()
        self.assertNotIn("imagery", source)
        self.assertNotIn("stac_client", source)
        self.assertNotIn("sentinel", source)
        self.assertNotIn("landsat", source)


class BarraSimplificadaTests(unittest.TestCase):
    """Fase 6 / itens 13 da Fase 7: tela cheia e pesquisar lugares fora da barra."""

    def test_dlg_search_e_icone_nao_existem_mais(self):
        self.assertFalse(os.path.exists(os.path.join(PLUGIN_DIR, "dlg_search.py")))
        self.assertFalse(os.path.exists(os.path.join(PLUGIN_DIR, "icons", "search.svg")))

    def test_earth_tools_sem_pesquisar_lugares(self):
        source = _read("earth_tools.py")
        self.assertNotIn("SearchDialog", source)
        self.assertNotIn("_open_search", source)
        self.assertNotIn("dlg_search", source)

    def test_earth_tools_sem_tela_cheia(self):
        source = _read("earth_tools.py").lower()
        self.assertNotIn("fullscreen", source)
        self.assertNotIn("tela cheia", source)

    def test_pesquisa_de_atributos_nativa_nao_foi_tocada(self):
        # Garantia negativa: nada no earth_tools.py tenta desligar/remover
        # qualquer acao nativa de pesquisa/identificacao do proprio QGIS -
        # só a SearchDialog (pesquisa só entre lugares do plugin) saiu.
        source = _read("earth_tools.py")
        self.assertNotIn("actionIdentify", source)
        self.assertNotIn("MapToolIdentify", source)


class AbasDaReguaTests(unittest.TestCase):
    """Fase 5 / item 12 da Fase 7: abas 3D removidas, as 4 reais preservadas."""

    def setUp(self):
        self.source = _read("dlg_ruler.py")

    def test_abas_3d_nao_existem_mais(self):
        self.assertNotIn("Caminho em 3D", self.source)
        self.assertNotIn("Polígono em 3D", self.source)
        self.assertNotIn("setTabEnabled", self.source)

    def test_quatro_abas_reais_preservadas(self):
        for titulo in ('"Linha"', '"Caminho"', '"Polígono"', '"Círculo"'):
            self.assertIn(titulo, self.source)


class CirculoRegressaoTests(unittest.TestCase):
    """Fase 4 / item 7 da Fase 7: a correção não pode ser revertida sem

    que este teste quebre - trava a ausência do padrão que causava o
    defeito (anel descartado inteiro + fallback para [centro, borda]).
    """

    def setUp(self):
        self.maptools_source = _read("maptools.py")
        self.utils_source = _read("utils.py")

    def test_fallback_para_par_centro_borda_nao_existe_mais(self):
        self.assertNotIn("ring if ring else list(pair)", self.maptools_source)

    def test_circle_points_recebe_o_crs_do_canvas(self):
        self.assertIn("circle_points(pair[0], pair[1], crs=self._circle_crs())", self.maptools_source)

    def test_circle_points_aceita_parametro_crs(self):
        self.assertIn("def circle_points(center, edge, segments=72, crs=None):", self.utils_source)

    def test_circle_points_nao_descarta_o_anel_na_primeira_falha(self):
        # O bug original tinha "return [], radius" DENTRO do laço de
        # projeção de cada segmento - a correção move isso para fora,
        # tentando os 72 segmentos antes de desistir.
        self.assertNotIn("except Exception:\n            return [], radius", self.utils_source)

    def test_computeSpheroidProject_so_e_chamado_em_wgs84(self):
        # Causa raiz CONFIRMADA EMPIRICAMENTE contra o QGIS 3.44.15 real:
        # QgsDistanceArea.computeSpheroidProject() devolve (nan, nan) em
        # SILENCIO (sem exceção) quando o CRS de origem é projetado (ex.:
        # SIRGAS 2000/UTM) - só funciona corretamente em CRS geográfico.
        # A correção projeta sempre via uma QgsDistanceArea em WGS84
        # (`da_wgs`), nunca com `da` (que pode estar no CRS projetado) -
        # travar isso aqui evita reintroduzir o defeito.
        self.assertIn("da_wgs = make_distance_area(WGS84)", self.utils_source)
        self.assertIn("da_wgs.computeSpheroidProject(", self.utils_source)
        self.assertNotIn("da.computeSpheroidProject(", self.utils_source)

    def test_anel_e_transformado_de_volta_para_o_crs_de_origem(self):
        self.assertIn("QgsCoordinateTransform(source_crs, WGS84", self.utils_source)
        self.assertIn("QgsCoordinateTransform(WGS84, source_crs", self.utils_source)

    def test_ponto_nan_e_detectado_mesmo_sem_excecao(self):
        # A falha original não lançava exceção (daí o try/except nunca
        # disparar) - a correção verifica NaN explicitamente, não só
        # exceção.
        self.assertEqual(self.utils_source.count("math.isnan(point_final.x())"), 2)

    def test_project_point_tem_a_mesma_correcao_do_circulo(self):
        # project_point() (usada por "Adicionar por medida" em Novo
        # Caminho/Novo Polígono) tinha a MESMA causa raiz do círculo -
        # descoberta ao corrigir o círculo, confirmada empiricamente contra
        # o QGIS 3.44.15 real. Trava que não volta a chamar
        # computeSpheroidProject fora de uma QgsDistanceArea em WGS84.
        self.assertNotIn("da.computeSpheroidProject(", self.utils_source)
        self.assertEqual(self.utils_source.count("da_wgs.computeSpheroidProject("), 2)


class LinhaUnicaGeometriaTests(unittest.TestCase):
    """Fase 5 / itens 10-11 da Fase 7: Linha grava 1 feição, sem marcadores
    independentes."""

    def setUp(self):
        self.source = _read("dlg_ruler.py")

    def test_save_chama_create_place_uma_unica_vez(self):
        self.assertEqual(self.source.count("storage.create_place("), 1)

    def test_linha_trunca_para_dois_pontos(self):
        self.assertIn('current[0] == "line2"', self.source)
        self.assertIn("points = points[:2]", self.source)


class NovoCaminhoCrsTests(unittest.TestCase):
    """Correção 2: SRC/CRS precisa estar na janela "Novo Caminho"
    (dlg_feature.py), não só na aba Caminho da Régua - pedido explícito do
    usuário após a v0.14.0 não resolver isso."""

    def setUp(self):
        self.source = _read("dlg_feature.py")

    def test_crsrow_importado_e_usado_so_para_caminho(self):
        self.assertIn("from .widgets import CrsRow,", self.source)
        self.assertIn('if kind == "line":', self.source)
        self.assertIn("self.crs_row = CrsRow(", self.source)

    def test_build_geometry_transforma_de_verdade_nao_so_rotula(self):
        # "Não alterar apenas a declaração do CRS sem transformar as
        # coordenadas": tem que existir uma QgsCoordinateTransform real
        # aplicada ponto a ponto antes de montar a geometria do caminho.
        self.assertIn("QgsCoordinateTransform(canvas_crs, target_crs", self.source)
        self.assertIn("transform.transform(p) for p in self.points", self.source)

    def test_save_propaga_o_crs_escolhido_para_o_storage(self):
        self.assertIn("geometry, save_crs = self._build_geometry()", self.source)
        self.assertIn(
            "self.kind, name, geometry, attributes, self.parent_group, crs=save_crs",
            self.source,
        )

    def test_marcador_e_poligono_nao_ganham_o_seletor(self):
        # Escopo: só "Novo Caminho" (kind == "line"). O trecho que cria o
        # self.crs_row fica a poucas linhas de "if kind == "line":" e de
        # mais nenhuma outra condição de kind - garante que não foi
        # ampliado para "point"/"polygon" por engano.
        trecho = self.source.split("self.crs_row = None")[1].split("self.tabs = QTabWidget()")[0]
        self.assertIn('if kind == "line":', trecho)
        self.assertNotIn('"polygon"', trecho)
        self.assertNotIn('"point"', trecho)


class FaseFBufferTests(unittest.TestCase):
    """Fase F1: Buffer usa o algoritmo nativo do QGIS, rejeita SRC
    geográfico para processamento, e não modifica a geometria de origem."""

    def setUp(self):
        self.geoprocessing_source = _read("geoprocessing.py")
        self.layeractions_source = _read("layeractions.py")
        self.dlg_buffer_source = _read("dlg_buffer.py")

    def test_usa_o_algoritmo_nativo_native_buffer(self):
        self.assertIn('"native:buffer"', self.geoprocessing_source)

    def test_rejeita_crs_de_processamento_geografico(self):
        self.assertIn("crs.isGeographic()", self.geoprocessing_source)

    def test_reproject_nao_modifica_a_geometria_original(self):
        self.assertIn("geometry = QgsGeometry(geometry)", self.geoprocessing_source)

    def test_acao_gerar_buffer_esta_cadastrada_no_menu_de_contexto(self):
        self.assertIn('"Gerar Buffer...", None, self._on_buffer', self.layeractions_source)

    def test_on_buffer_reusa_a_mesma_leitura_de_selecao_multipla_do_excluir(self):
        self.assertIn("view.selectedNodes(True)", self.layeractions_source)
        self.assertIn("_collect(nodes)", self.layeractions_source)

    def test_dissolve_so_fica_habilitado_com_2_ou_mais_lugares(self):
        self.assertIn("if len(self.layers) < 2:", self.dlg_buffer_source)
        self.assertIn("self.dissolve_check.setEnabled(False)", self.dlg_buffer_source)


class FaseFUnionTests(unittest.TestCase):
    """Fase F2: União de polígonos."""

    def setUp(self):
        self.geoprocessing_source = _read("geoprocessing.py")
        self.layeractions_source = _read("layeractions.py")

    def test_usa_unaryunion_nativo(self):
        self.assertIn("QgsGeometry.unaryUnion(geoms)", self.geoprocessing_source)

    def test_rejeita_menos_de_2_entradas(self):
        self.assertIn("if len(inputs) < 2:", self.geoprocessing_source)

    def test_rejeita_entrada_que_nao_e_poligono(self):
        self.assertIn("QgsWkbTypes.PolygonGeometry", self.geoprocessing_source)

    def test_acao_unir_poligonos_esta_cadastrada(self):
        self.assertIn('"Unir polígonos...", None, self._on_union', self.layeractions_source)

    def test_on_union_filtra_so_poligonos(self):
        self.assertIn('customProperty(storage.CUSTOM_KEY) == "polygon"', self.layeractions_source)

    def test_on_buffer_e_on_union_reusam_o_mesmo_helper_de_selecao(self):
        # Evita duplicacao de logica de selecao multipla entre as duas acoes.
        self.assertEqual(self.layeractions_source.count("def _selected_places(self):"), 1)
        self.assertIn("places = self._selected_places()", self.layeractions_source)


class FaseFSplitTests(unittest.TestCase):
    """Fase F3: Divisão de polígono por linha de corte."""

    def setUp(self):
        self.geoprocessing_source = _read("geoprocessing.py")
        self.layeractions_source = _read("layeractions.py")
        self.dlg_split_source = _read("dlg_split.py")

    def test_usa_native_splitwithlines(self):
        self.assertIn('"native:splitwithlines"', self.geoprocessing_source)

    def test_detecta_ausencia_de_divisao_pelo_numero_de_partes(self):
        self.assertIn("if len(parts) < 2:", self.geoprocessing_source)

    def test_acao_dividir_poligono_esta_cadastrada(self):
        self.assertIn('"Dividir polígono...", None, self._on_split', self.layeractions_source)

    def test_original_so_e_apagado_depois_de_gravar_as_partes(self):
        # Requisito explicito: preservar o original ATE a confirmacao -
        # o delete_place() tem que vir DEPOIS do loop que cria as partes,
        # nunca antes.
        idx_criacao = self.dlg_split_source.index("for i, geom in enumerate(self._parts):")
        idx_delete = self.dlg_split_source.index("storage.delete_place(self.layer)")
        self.assertLess(idx_criacao, idx_delete)

    def test_pre_visualizacao_nao_grava_nada_antes_da_confirmacao(self):
        preview_start = self.dlg_split_source.index("def _preview(self):")
        preview_end = self.dlg_split_source.index("def _confirm(self):")
        trecho_preview = self.dlg_split_source[preview_start:preview_end]
        self.assertNotIn("create_place", trecho_preview)
        self.assertNotIn("delete_place", trecho_preview)


class FaseFClipTests(unittest.TestCase):
    """Fase F4: Recorte de geometrias com máscara (native:clip)."""

    def setUp(self):
        self.geoprocessing_source = _read("geoprocessing.py")
        self.layeractions_source = _read("layeractions.py")
        self.dlg_clip_source = _read("dlg_clip.py")

    def test_usa_native_clip(self):
        self.assertIn('"native:clip"', self.geoprocessing_source)

    def test_mascara_precisa_ser_poligono(self):
        self.assertIn("A máscara de recorte precisa ser um polígono.", self.geoprocessing_source)

    def test_sem_intersecao_e_erro_claro_nao_resultado_vazio_silencioso(self):
        self.assertIn("if not parts:", self.geoprocessing_source)

    def test_acao_recortar_com_esta_cadastrada(self):
        self.assertIn('"Recortar com...", None, self._on_clip', self.layeractions_source)

    def test_alvo_e_mascara_nao_podem_ser_a_mesma_camada(self):
        self.assertIn("if alvo.id() == mascara.id():", self.dlg_clip_source)


class FaseFDifferenceAndNegativeBufferTests(unittest.TestCase):
    """Fase F5: Diferença e Buffer negativo."""

    def setUp(self):
        self.geoprocessing_source = _read("geoprocessing.py")
        self.layeractions_source = _read("layeractions.py")
        self.dlg_buffer_source = _read("dlg_buffer.py")

    def test_usa_native_difference(self):
        self.assertIn('"native:difference"', self.geoprocessing_source)

    def test_segunda_geometria_cobrir_tudo_e_erro_claro(self):
        self.assertIn("if not parts:", self.geoprocessing_source)

    def test_acao_diferenca_esta_cadastrada(self):
        self.assertIn('"Diferença...", None, self._on_difference', self.layeractions_source)

    def test_buffer_aceita_distancia_negativa(self):
        self.assertIn("setRange(-1_000_000.0, 1_000_000.0)", self.dlg_buffer_source)
        self.assertIn("if distance_m == 0:", self.geoprocessing_source)
        self.assertNotIn("if distance_m <= 0:", self.geoprocessing_source)


class StylePersistenceRegressionTests(unittest.TestCase):
    """Auditoria: storage.set_style() grava no GeoPackage via
    saveStyleToDatabase, checando a capacidade com '&' (bit a bit), nunca
    com 'in' (TypeError nesse binding do QGIS, engolido pelo except)."""

    def setUp(self):
        self.source = _read("storage.py")

    def test_usa_bitwise_and_nao_in_para_checar_capacidade(self):
        self.assertIn("caps & Qgis.ProviderStyleStorageCapability.SaveToDatabase", self.source)
        self.assertNotIn(
            "Qgis.ProviderStyleStorageCapability.SaveToDatabase in", self.source
        )

    def test_salva_estilo_no_banco_do_geopackage(self):
        self.assertIn('layer.saveStyleToDatabase("default"', self.source)


class StyleManagerTests(unittest.TestCase):
    """Fase H: Gerenciador de Estilos."""

    def setUp(self):
        self.source = _read("dlg_style_manager.py")
        self.layeractions_source = _read("layeractions.py")

    def test_acao_estilo_esta_cadastrada(self):
        self.assertIn('"Estilo...", "style.svg", self._on_style', self.layeractions_source)

    def test_presets_usam_qsettings_nativo_nao_arquivo_proprio(self):
        self.assertIn("from qgis.PyQt.QtCore import QSettings", self.source)

    def test_aplicar_nao_toca_na_geometria(self):
        # So storage.set_style()/triggerRepaint() dentro de _apply() -
        # nenhuma chamada a setGeometry/changeGeometry.
        apply_start = self.source.index("def _apply(self):")
        trecho = self.source[apply_start:]
        self.assertNotIn("setGeometry", trecho)
        self.assertNotIn("changeGeometry", trecho)


class GeometryValidatorTests(unittest.TestCase):
    """Fase G1: Validador de Geometrias."""

    def setUp(self):
        self.source = _read("geometry_validator.py")
        self.dlg_source = _read("dlg_validate.py")
        self.earth_tools_source = _read("earth_tools.py")

    def test_usa_validategeometry_nativo_nao_regras_proprias(self):
        self.assertIn("geometry.validateGeometry()", self.source)
        self.assertIn("geometry.isGeosValid()", self.source)

    def test_correcao_usa_makevalid_nativo_e_nunca_sobrescreve_original(self):
        self.assertIn("geometry.makeValid()", self.source)
        fix_start = self.dlg_source.index("def _fix_selected(self):")
        trecho = self.dlg_source[fix_start:]
        self.assertNotIn("delete_place", trecho)
        self.assertIn("create_place(", trecho)
        self.assertIn("QMessageBox.question(", trecho)

    def test_bbox_de_referencia_e_transformado_para_wgs84(self):
        # Lugares podem estar em CRS diferentes entre si (Caminho - Fase
        # 3); comparar bounding boxes sem transformar daria falso
        # positivo/negativo. Trava que a transformacao existe.
        self.assertIn("transformBoundingBox(bbox)", self.source)
        self.assertIn("transformBoundingBox(canvas.extent())", self.dlg_source)

    def test_acao_validar_geometrias_esta_cadastrada(self):
        self.assertIn(
            '"Validar geometrias...", self._open_validate', self.earth_tools_source
        )


class CalculatorTests(unittest.TestCase):
    """Etapa 2: Calculadora de área e distância."""

    def setUp(self):
        self.utils_source = _read("utils.py")
        self.dlg_source = _read("dlg_calculator.py")
        self.ruler_source = _read("dlg_ruler.py")
        self.earth_tools_source = _read("earth_tools.py")
        self.layeractions_source = _read("layeractions.py")

    def test_mede_a_geometria_de_verdade_nao_uma_lista_de_pontos_proprias(self):
        self.assertIn("def measure_area_geometry(geometry, crs=None):", self.utils_source)
        self.assertIn("da.measureArea(geometry)", self.utils_source)

    def test_nao_usa_isvisible_para_decidir_o_que_copiar(self):
        # isVisible() do Qt reflete a tela (depende de .show() ja ter
        # rodado), nao a relevancia semantica do campo - usa um estado
        # proprio (_active_rows) em vez disso.
        copy_start = self.dlg_source.index("def _copy_result(self):")
        trecho = self.dlg_source[copy_start:]
        self.assertNotIn("isVisible()", trecho)
        self.assertIn("_active_rows", trecho)

    def test_acao_calculadora_esta_cadastrada(self):
        # Ajuste de identidade GeoSketch: a Calculadora perdeu o ícone da
        # barra/entrada no menu Vetor (_open_calculator() continua
        # definido, só sem callback ligado por .connect() nenhum) - a
        # única entrada registrada agora é "Calcular medidas..." no menu
        # de contexto (submenu GeoSketch), que delega para
        # open_calculator_for().
        self.assertIn("def _open_calculator(self):", self.earth_tools_source)
        self.assertNotIn('self._add("calculator.svg"', self.earth_tools_source)
        self.assertIn(
            '"Calcular medidas...", "calculator.svg", self._on_calculate',
            self.layeractions_source,
        )

    def test_circulo_mostra_diametro(self):
        self.assertIn('"raio", "diametro", "circunferencia", "area"', self.ruler_source)


class ExportMapTests(unittest.TestCase):
    """Etapa 5: Exportação de mapas usa os recursos nativos de layout do QGIS."""

    def setUp(self):
        self.reports_source = _read("reports.py")
        self.dlg_source = _read("dlg_export_map.py")
        self.earth_tools_source = _read("earth_tools.py")

    def test_usa_qgsprintlayout_nativo(self):
        self.assertIn("QgsPrintLayout(project)", self.reports_source)
        self.assertIn("QgsLayoutItemMap(layout)", self.reports_source)
        self.assertIn("QgsLayoutItemLegend(layout)", self.reports_source)
        self.assertIn("QgsLayoutItemScaleBar(layout)", self.reports_source)
        self.assertIn("QgsLayoutExporter(layout)", self.reports_source)

    def test_usa_svg_de_seta_de_norte_nativo_do_qgis(self):
        self.assertIn("pkgDataPath()", self.reports_source)
        self.assertIn("NorthArrow", self.reports_source)

    def test_preview_abre_o_layout_designer_nativo_nao_um_preview_proprio(self):
        self.assertIn("openLayoutDesignerDialog", self.dlg_source)

    def test_acao_exportar_mapa_esta_cadastrada(self):
        self.assertIn('"Exportar mapa...", self._open_export_map', self.earth_tools_source)

    def test_a4_e_a3_suportados(self):
        self.assertIn('PAGE_SIZES = ["A4", "A3"]', self.reports_source)

    def test_retrato_e_paisagem_suportados(self):
        self.assertIn('"Retrato": QgsLayoutItemPage.Portrait', self.reports_source)
        self.assertIn('"Paisagem": QgsLayoutItemPage.Landscape', self.reports_source)


class SubmenuFerramentasTerraTests(unittest.TestCase):
    """Reorganização do menu de contexto (auditoria de UI): todas as ações
    de lugar (exceto Excluir, que é destrutiva) ficam dentro de UM submenu
    "GeoSketch", organizadas por categoria com rótulos de seção -
    nenhuma ação deixa de existir, só muda de onde aparece."""

    def setUp(self):
        self.source = _read("layeractions.py")

    def test_submenu_unico_declarado(self):
        self.assertIn('SUBMENU = "GeoSketch"', self.source)

    def test_quatro_categorias_tem_cabecalho(self):
        for categoria in ("GEOPROCESSAMENTO", "MEDIÇÕES", "VALIDAÇÃO", "EXPORTAÇÃO"):
            self.assertIn(categoria, self.source)

    def test_acoes_de_geoprocessamento_estao_no_submenu(self):
        for chamada in (
            'self._on_buffer, SUBMENU, False)',
            'self._on_union, SUBMENU, False)',
            'self._on_split, SUBMENU, False)',
            'self._on_clip, SUBMENU, False)',
            'self._on_difference, SUBMENU, False)',
        ):
            self.assertIn(chamada, self.source)

    def test_excluir_fica_fora_do_submenu_na_raiz(self):
        self.assertIn('make("Excluir", None, self.delete_selected, "", False)', self.source)

    def test_nenhuma_acao_de_lugar_antiga_foi_removida(self):
        # Garantia negativa desta reorganização: as 12 ações que existiam
        # soltas na raiz do menu antes desta mudança continuam todas
        # cadastradas (só mudou o `menu` para onde apontam).
        for callback in (
            "self._edit_points", "self._goto_layer", "self._move_to_folder",
            "self._on_style", "self._on_buffer", "self._on_union",
            "self._on_split", "self._on_clip", "self._on_difference",
            "self.delete_selected", "self._save_as", "self._email",
        ):
            self.assertIn(callback, self.source)

    def test_novas_acoes_de_contexto_calculo_validacao_exportacao(self):
        self.assertIn('self._on_calculate, SUBMENU, False)', self.source)
        self.assertIn('self._on_validate, SUBMENU, False)', self.source)
        self.assertIn('self._on_export_map, SUBMENU, False)', self.source)

    def test_calcular_medidas_delega_para_earth_tools_sem_duplicar_logica(self):
        start = self.source.index("def _on_calculate(self):")
        trecho = self.source[start:self.source.index("\n\n", start)]
        self.assertIn("self.plugin.open_calculator_for(", trecho)

    def test_validar_geometria_delega_para_earth_tools_sem_duplicar_logica(self):
        start = self.source.index("def _on_validate(self):")
        trecho = self.source[start:self.source.index("\n\n", start)]
        self.assertIn("self.plugin._open_validate()", trecho)

    def test_save_as_separado_de_save_as_layer_por_causa_do_bool_do_qaction(self):
        # QAction.triggered emite um bool (checked); se _save_as() aceitasse
        # um parâmetro opcional de camada, o PyQt passaria esse bool para
        # ele. O callback ligado ao QAction (_save_as) precisa continuar
        # sem nenhum parâmetro extra - só _save_as_layer() recebe a camada,
        # e só é chamado diretamente (nunca via .connect()).
        self.assertIn("def _save_as(self):\n        self._save_as_layer(self._current_layer())", self.source)
        self.assertIn("def _save_as_layer(self, layer):", self.source)
        self.assertNotIn("def _save_as(self, layer", self.source)


class PropertiesPanelTests(unittest.TestCase):
    """Painel lateral novo "Propriedades da Geometria" - não existia antes
    desta auditoria de UI. Confirma que foi criado, registrado/desligado
    no ciclo de vida do plugin e que delega ações para o código já
    existente em vez de duplicar lógica de cálculo/estilo/validação/
    exportação."""

    def setUp(self):
        self.panel_source = _read("dlg_properties_panel.py")
        self.earth_tools_source = _read("earth_tools.py")

    def test_e_um_dockwidget_nativo(self):
        self.assertIn("class PropertiesPanel(QDockWidget):", self.panel_source)

    def test_registrado_e_desligado_no_ciclo_de_vida_do_plugin(self):
        self.assertIn("self.iface.addDockWidget(Qt.RightDockWidgetArea, self._properties_panel)", self.earth_tools_source)
        self.assertIn("self.iface.removeDockWidget(self._properties_panel)", self.earth_tools_source)
        self.assertIn("self._properties_panel.disconnect_all()", self.earth_tools_source)

    def test_nao_duplica_logica_so_delega(self):
        self.assertIn("self.plugin.open_calculator_for(self._layer)", self.panel_source)
        self.assertIn("self.plugin._layer_actions._on_style()", self.panel_source)
        self.assertIn("self.plugin._open_validate()", self.panel_source)
        self.assertIn("self.plugin._layer_actions._save_as_layer(self._layer)", self.panel_source)

    def test_calculo_usa_as_mesmas_funcoes_de_medicao_da_calculadora(self):
        # Mesma fonte de verdade de dlg_calculator.py/dlg_export_map.py -
        # nunca um valor fictício ou uma reimplementação própria.
        self.assertIn("utils.measure_area_geometry(geometry, crs)", self.panel_source)
        self.assertIn("utils.measure_perimeter_geometry(geometry, crs)", self.panel_source)
        self.assertIn("utils.measure_length_geometry(geometry, crs)", self.panel_source)
        self.assertIn("geometry_validator.validate_layers([layer])", self.panel_source)

    def test_atualiza_ao_trocar_selecao_e_ao_editar_a_camada(self):
        self.assertIn("currentLayerChanged.connect(self._on_current_layer_changed)", self.panel_source)
        self.assertIn('_LAYER_SIGNALS = ("committedGeometriesChanges", "editingStopped", "styleChanged", "nameChanged")', self.panel_source)


class ToolbarNaoRemoveNadaExistenteTests(unittest.TestCase):
    """Barra de ferramentas (auditoria de UI): novos botões entram, mas os
    7 botões que já existiam antes desta mudança continuam todos
    cadastrados - nenhum removido."""

    def setUp(self):
        self.source = _read("earth_tools.py")

    def test_botoes_antigos_preservados(self):
        for chamada in (
            'self._add("placemark.svg", "Adicionar marcador de local",',
            'self._add("polygon.svg", "Adicionar poligono",',
            'self._add("path.svg", "Adicionar caminho",',
            'self._add("folder.svg", "Nova pasta", self._new_group)',
            'self._add("maps.svg", "Ver no Google Maps", self._open_google_maps)',
            'self._add("goto.svg", "Ir para coordenadas", self._open_goto)',
        ):
            self.assertIn(chamada, self.source)

    def test_botoes_novos_pedidos_na_auditoria(self):
        self.assertIn('self.iface.actionSelectFeatures()', self.source)
        self.assertIn('self._add("circle.svg",', self.source)
        self.assertIn('self._add("export_map.svg", "Exportar mapa...", self._open_export_map)', self.source)

    def test_calculadora_e_estilos_nao_tem_mais_icone_na_barra(self):
        # Ajuste de identidade GeoSketch: os dois ícones saem da barra (e
        # do menu Vetor, que o mesmo _add() também alimentava) - só
        # continuam acessíveis pelo menu de contexto (submenu GeoSketch em
        # layeractions.py: "Calcular medidas...", "Estilo...").
        self.assertNotIn('self._add("calculator.svg"', self.source)
        self.assertNotIn('self._add("style.svg"', self.source)

    def test_exportar_mapa_nao_fica_duplicada_no_menu(self):
        # Antes desta mudança era _add_menu_only (só menu); agora é
        # _add() (menu + barra) - não pode aparecer das DUAS formas, ou
        # ficaria duplicada no menu Vetor > GeoSketch.
        self.assertNotIn('self._add_menu_only("Exportar mapa...",', self.source)

    def test_open_calculator_e_open_export_map_sem_parametro_extra_no_callback(self):
        # Mesmo motivo do _save_as/_save_as_layer em layeractions.py: o
        # callback ligado por .connect() não pode aceitar um parâmetro
        # opcional de camada, senão o PyQt empurraria o bool do
        # QAction.triggered para dentro dele.
        self.assertIn("def _open_calculator(self):\n        self.open_calculator_for(None)", self.source)
        self.assertIn("def _open_export_map(self):\n        self.open_export_map_for(None)", self.source)


class PreSelecaoOpcionalTests(unittest.TestCase):
    """CalculatorDialog/ExportMapDialog/RulerDialog ganham um parâmetro
    opcional de pré-seleção (chamado do menu de contexto/painel), sem
    quebrar o comportamento padrão de quando são abertos sem argumento
    extra (menu Vetor > GeoSketch / barra)."""

    def setUp(self):
        self.calc_source = _read("dlg_calculator.py")
        self.export_source = _read("dlg_export_map.py")
        self.ruler_source = _read("dlg_ruler.py")

    def test_calculator_aceita_initial_layer_opcional(self):
        self.assertIn("def __init__(self, iface, parent=None, initial_layer=None):", self.calc_source)

    def test_export_map_aceita_initial_layer_opcional(self):
        self.assertIn("def __init__(self, iface, parent=None, initial_layer=None):", self.export_source)

    def test_ruler_aceita_initial_tab_opcional(self):
        self.assertIn("def __init__(self, iface, parent=None, initial_tab=0):", self.ruler_source)


class SubmenuAdicionarUnificadoTests(unittest.TestCase):
    """Ajuste pontual: as 6 ações do submenu "Adicionar" eram registradas
    com 6 chamadas SEPARADAS a addCustomActionForLayerType(acao,
    "Adicionar", vector, True) - a API do QGIS não garantia mesclar isso
    num único submenu (a interface real mostrava várias entradas de topo
    repetindo "Adicionar"). A correção usa um único QMenu("Adicionar")
    nativo do Qt, com as 6 ações como filhas diretas, registrado uma única
    vez via QMenu.menuAction()."""

    def setUp(self):
        self.source = _read("layeractions.py")

    def test_addcustomactionforlayertype_chamado_uma_unica_vez_para_adicionar(self):
        # Antes desta correção, "Adicionar" aparecia como argumento de
        # addCustomActionForLayerType 6 vezes (uma por ação). Agora só o
        # QMenu.menuAction() é registrado assim - a string literal
        # '"Adicionar", True)' não deve mais aparecer (ela só existia
        # nas 6 chamadas antigas, uma por ação).
        self.assertNotIn('"Adicionar", True)', self.source)
        self.assertIn('self._add_menu = QMenu("Adicionar", window)', self.source)
        self.assertIn(
            'self.iface.addCustomActionForLayerType(self._add_menu.menuAction(), "", vector, True)',
            self.source,
        )

    def test_as_6_acoes_sao_filhas_diretas_do_qmenu_nao_da_api_do_qgis(self):
        self.assertEqual(self.source.count("self._add_menu.addAction(action)"), 1)
        start = self.source.index("def make_add(")
        trecho = self.source[start:self.source.index("self.iface.addCustomActionForLayerType(self._add_menu.menuAction()")]
        # make_add("..." - só as 6 CHAMADAS (com aspas logo depois do
        # parêntese); a definição da função (sem aspas ali) não conta.
        self.assertEqual(trecho.count('make_add("'), 6)

    def test_nenhuma_das_6_acoes_antigas_foi_removida_mesmo_texto_icone_callback(self):
        for chamada in (
            'make_add("Pasta", "folder.svg", self._new_group)',
            'make_add("Modelo de propriedade rural", "folder.svg",\n                 self._new_property_template)',
            'make_add("Marcador de local", "placemark.svg",\n                 lambda: self.plugin.open_feature("point", self._current_group()))',
            'make_add("Caminho", "path.svg",\n                 lambda: self.plugin.open_feature("line", self._current_group()))',
            'make_add("Poligono", "polygon.svg",\n                 lambda: self.plugin.open_feature("polygon", self._current_group()))',
            'make_add("Sobreposicao de imagem", None, self._image_overlay)',
        ):
            self.assertIn(chamada, self.source)

    def test_restante_do_menu_de_contexto_nao_foi_tocado(self):
        # Garantia negativa: a correção é isolada ao bloco "Adicionar" -
        # o submenu "GeoSketch" categorizado (da auditoria
        # anterior) e o Excluir na raiz continuam exatamente como estavam.
        self.assertIn('SUBMENU = "GeoSketch"', self.source)
        self.assertIn('make("Excluir", None, self.delete_selected, "", False)', self.source)
        self.assertIn("— GEOPROCESSAMENTO —", self.source)
        self.assertIn("— MEDIÇÕES —", self.source)
        self.assertIn("— VALIDAÇÃO —", self.source)
        self.assertIn("— EXPORTAÇÃO —", self.source)


class RebrandingGeoSketchTests(unittest.TestCase):
    """Identidade visual GeoSketch: só o texto exibido ao usuário muda.

    Garantia mais importante desta correção: nenhum identificador interno
    persistido (CUSTOM_KEY gravado em toda camada do GeoPackage, grupo de
    QSettings dos presets de estilo, nome do pacote/classe/classFactory,
    objectName dos widgets Qt) foi alterado - só renomear esses
    quebraria o reconhecimento de lugares já criados por qualquer versão
    anterior ("Ferramentas Terra") e apagaria a biblioteca de presets de
    estilo já salva pelo usuário.
    """

    def setUp(self):
        self.storage_source = _read("storage.py")
        self.style_source = _read("dlg_style_manager.py")
        self.earth_tools_source = _read("earth_tools.py")
        self.panel_source = _read("dlg_properties_panel.py")
        self.layeractions_source = _read("layeractions.py")
        self.init_source = _read("__init__.py")
        self.metadata_source = _read("metadata.txt")

    def test_custom_key_persistido_no_geopackage_nao_foi_alterado(self):
        self.assertIn('CUSTOM_KEY = "ferramentas_terra"', self.storage_source)

    def test_grupo_de_qsettings_dos_presets_de_estilo_nao_foi_alterado(self):
        self.assertIn('SETTINGS_GROUP = "FerramentasTerra/EstilosSalvos"', self.style_source)

    def test_objectnames_internos_do_qt_nao_foram_alterados(self):
        self.assertIn('self.toolbar.setObjectName("FerramentasTerra")', self.earth_tools_source)
        self.assertIn('self.setObjectName("FerramentasTerraPropriedades")', self.panel_source)

    def test_classe_e_classfactory_nao_foram_renomeados(self):
        self.assertIn("class EarthTools(object):", self.earth_tools_source)
        self.assertIn("from .earth_tools import EarthTools", self.init_source)
        self.assertIn("return EarthTools(iface)", self.init_source)

    def test_texto_exibido_ao_usuario_agora_e_geosketch(self):
        # Barra de ferramentas (título exibido, não o objectName), menu
        # Vetor, submenu do menu de contexto, painel lateral e nome no
        # Gerenciador de Complementos.
        self.assertIn('self.iface.addToolBar("GeoSketch")', self.earth_tools_source)
        self.assertIn('"&GeoSketch"', self.earth_tools_source)
        self.assertNotIn('"&Ferramentas Terra"', self.earth_tools_source)
        self.assertIn('SUBMENU = "GeoSketch"', self.layeractions_source)
        self.assertIn('"GeoSketch - Propriedades"', self.panel_source)
        self.assertIn("name=GeoSketch", self.metadata_source)

    def test_nenhum_texto_exibido_restante_com_o_nome_antigo(self):
        for source in (
            self.earth_tools_source, self.panel_source, self.layeractions_source,
        ):
            self.assertNotIn("Ferramentas Terra", source)


if __name__ == "__main__":
    unittest.main()

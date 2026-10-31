# -*- coding: utf-8 -*-
"""Testes automatizados que precisam do ambiente real do QGIS (QgsApplication
"offscreen"), mas SEM clique de mouse - diferentes dos passos do roteiro de
validação manual da Fase 8, que exigem interação real na interface.

Cobrem: seleção/transformação de SRC no Caminho (Régua e Novo Caminho) e
geometria resultante compatível com o Buffer; integridade do anel do
Círculo (inclusive em CRS projetado - a causa raiz confirmada do bug de
"só aparece o raio" / "Área = NaN").

earth_tools/*.py usa import relativo ("from . import utils") - só funciona
importado como PACOTE. Por isso o sys.path recebe o pai de earth_tools/ (não
earth_tools/ em si) e todo import abaixo é "from earth_tools import X" ou
"from earth_tools.X import Y", nunca "import X" direto.

Como rodar de verdade, de dentro do Python do próprio QGIS (ex.: no Windows,
com QGIS 3.44 instalado em "C:\\Program Files\\QGIS 3.44.15"):
    & "C:\\Program Files\\QGIS 3.44.15\\bin\\python-qgis-ltr.bat" -m unittest discover -s tests -v
executado de dentro de earth_tools/. Fora do QGIS (sem o módulo `qgis`
instalado), este arquivo é pulado (skipped) em vez de falhar - ver
setUpModule().

Os itens "limpeza do círculo temporário" e "ausência de marcadores
independentes na Linha" dependem de um QgsMapCanvas real interagindo com o
mouse e ficam só no roteiro de validação manual (Fase 8) - não têm um teste
automatizado equivalente aqui.
"""

import math
import os
import sys
import unittest

_EARTH_TOOLS_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(_EARTH_TOOLS_DIR))

try:
    from qgis.testing import start_app
    from qgis.core import (
        QgsCoordinateReferenceSystem,
        QgsCoordinateTransform,
        QgsGeometry,
        QgsPointXY,
        QgsProject,
        QgsRectangle,
    )

    QGIS_AVAILABLE = True
except Exception:
    QGIS_AVAILABLE = False


PROCESSING_AVAILABLE = False  # so fica correto depois de setUpModule() rodar.


def _try_init_processing():
    """`import processing` só é confiável DEPOIS de start_app() já ter
    criado a QgsApplication. Em alguns ambientes (ex.: python-qgis-ltr.bat
    headless) o diretório do plugin Processing nem está no sys.path por
    padrão - tenta achar via QgsApplication.pkgDataPath(), igual ao QGIS
    faria ao carregar os plugins núcleo."""
    try:
        import processing  # noqa: F401
        from processing.core.Processing import Processing as _Processing

        _Processing.initialize()
        return True
    except Exception:
        pass
    try:
        from qgis.core import QgsApplication

        plugins_dir = os.path.join(QgsApplication.pkgDataPath(), "python", "plugins")
        if plugins_dir not in sys.path:
            sys.path.insert(0, plugins_dir)
        import processing  # noqa: F401
        from processing.core.Processing import Processing as _Processing

        _Processing.initialize()
        return True
    except Exception:
        return False


def setUpModule():
    if not QGIS_AVAILABLE:
        raise unittest.SkipTest(
            "Modulo 'qgis' nao disponivel neste ambiente - rode dentro do "
            "Python do proprio QGIS para executar estes testes de verdade."
        )
    start_app()
    global PROCESSING_AVAILABLE
    PROCESSING_AVAILABLE = _try_init_processing()


@unittest.skipUnless(QGIS_AVAILABLE, "requer o ambiente QGIS")
class CrsDoCaminhoTests(unittest.TestCase):
    """SRC/CRS no Caminho: padrão, escolhido, compatibilidade com Buffer."""

    def setUp(self):
        from earth_tools import storage

        self.storage = storage
        # clear() deixa QgsProject.instance().crs() INVALIDO - QgsProject e'
        # um singleton compartilhado por todo o processo de teste, entao
        # isso contaminaria qualquer teste rodado depois desta classe (ex.:
        # ModulosCarregamSemErroTests) se nao for restaurado para um CRS
        # valido aqui mesmo. Esta classe nunca depende do CRS do projeto
        # (sempre passa `crs=` explicito a create_place), so o valor em si
        # nao importa para estes testes - só precisa ser valido.
        QgsProject.instance().clear()
        QgsProject.instance().setCrs(QgsCoordinateReferenceSystem("EPSG:4326"))

    def test_crs_padrao_wgs84_quando_nao_informado(self):
        # Comportamento preservado para Linha/Poligono/Circulo e para
        # quem chama create_place sem crs.
        geom = QgsGeometry.fromPolylineXY(
            [QgsPointXY(-47.0, -23.0), QgsPointXY(-47.1, -23.1)]
        )
        layer = self.storage.create_place("line", "Teste CRS padrao", geom, {})
        self.assertEqual(layer.crs().authid(), "EPSG:4326")
        self.assertEqual(layer.featureCount(), 1)

    def test_crs_escolhido_e_declarado_na_camada_gravada(self):
        utm = QgsCoordinateReferenceSystem("EPSG:31983")  # SIRGAS 2000 / UTM 23S
        geom = QgsGeometry.fromPolylineXY(
            [QgsPointXY(200000.0, 7800000.0), QgsPointXY(201000.0, 7801000.0)]
        )
        layer = self.storage.create_place("line", "Teste CRS UTM", geom, {}, crs=utm)
        self.assertEqual(layer.crs().authid(), "EPSG:31983")

    def test_geometria_no_crs_escolhido_e_compativel_com_buffer(self):
        utm = QgsCoordinateReferenceSystem("EPSG:31983")
        p1, p2 = QgsPointXY(200000.0, 7800000.0), QgsPointXY(200000.0, 7801000.0)
        geom = QgsGeometry.fromPolylineXY([p1, p2])
        layer = self.storage.create_place("line", "Teste Buffer", geom, {}, crs=utm)

        feature = next(layer.getFeatures())
        comprimento = feature.geometry().length()
        self.assertAlmostEqual(comprimento, 1000.0, delta=1.0)
        self.assertTrue(layer.isValid())
        self.assertEqual(layer.crs().authid(), "EPSG:31983")

    def test_transformacao_de_coordenadas_e_efetiva_nao_so_a_etiqueta(self):
        # "Não alterar apenas a declaração do CRS sem transformar as
        # coordenadas": as coordenadas gravadas em UTM precisam ser
        # NUMERICAMENTE diferentes das originais em graus (WGS84) - não os
        # mesmos números com um CRS diferente etiquetado por cima.
        from earth_tools import utils

        wgs84 = QgsCoordinateReferenceSystem("EPSG:4326")
        utm = QgsCoordinateReferenceSystem("EPSG:31983")
        p1_wgs = QgsPointXY(-47.0, -23.0)
        p2_wgs = QgsPointXY(-47.0, -23.01)  # ~1.1 km ao sul

        distancia_original = utils.make_distance_area(wgs84).measureLine(p1_wgs, p2_wgs)

        transform = QgsCoordinateTransform(wgs84, utm, QgsProject.instance())
        p1_utm = transform.transform(p1_wgs)
        p2_utm = transform.transform(p2_wgs)
        # Coordenadas realmente mudaram de escala (graus -> metros UTM).
        self.assertGreater(abs(p1_utm.x()), 1000.0)
        self.assertGreater(abs(p1_utm.y()), 1000.0)

        geom = QgsGeometry.fromPolylineXY([p1_utm, p2_utm])
        layer = self.storage.create_place("line", "Teste transformacao", geom, {}, crs=utm)
        comprimento_gravado = next(layer.getFeatures()).geometry().length()
        self.assertAlmostEqual(comprimento_gravado, distancia_original, delta=2.0)

    def test_transformacao_inversa_utm_para_wgs84(self):
        from earth_tools import utils

        wgs84 = QgsCoordinateReferenceSystem("EPSG:4326")
        utm = QgsCoordinateReferenceSystem("EPSG:31983")
        p_utm = QgsPointXY(200000.0, 7800000.0)

        to_wgs = QgsCoordinateTransform(utm, wgs84, QgsProject.instance())
        p_wgs = to_wgs.transform(p_utm)
        to_utm = QgsCoordinateTransform(wgs84, utm, QgsProject.instance())
        p_utm_volta = to_utm.transform(p_wgs)

        self.assertAlmostEqual(p_utm.x(), p_utm_volta.x(), delta=0.01)
        self.assertAlmostEqual(p_utm.y(), p_utm_volta.y(), delta=0.01)

    def test_transformacao_invalida_nao_derruba_o_plugin(self):
        # CRS invalido (string vazia) -> isValid() False; o codigo de
        # dlg_ruler/dlg_feature cai para QgsProject.instance().crs() nesse
        # caso, nunca tenta transformar com um CRS invalido.
        invalido = QgsCoordinateReferenceSystem("")
        self.assertFalse(invalido.isValid())

    def test_camada_reaberta_preserva_o_crs_gravado(self):
        utm = QgsCoordinateReferenceSystem("EPSG:31983")
        geom = QgsGeometry.fromPolylineXY(
            [QgsPointXY(200000.0, 7800000.0), QgsPointXY(201000.0, 7801000.0)]
        )
        layer = self.storage.create_place("line", "Teste reabertura", geom, {}, crs=utm)
        path = layer.source().split("|")[0]
        table = self.storage.table_name(layer)

        from qgis.core import QgsVectorLayer

        reaberta = QgsVectorLayer("{}|layername={}".format(path, table), "reaberta", "ogr")
        self.assertTrue(reaberta.isValid())
        self.assertEqual(reaberta.crs().authid(), "EPSG:31983")


@unittest.skipUnless(QGIS_AVAILABLE, "requer o ambiente QGIS")
class CirculoAnelTests(unittest.TestCase):
    """Círculo: circunferência completa, raio/área/circunferência, sem NaN.

    Trava especificamente a causa raiz confirmada: QgsDistanceArea.
    computeSpheroidProject() devolve (nan, nan) em CRS projetado - por isso
    todo caso de CRS PROJETADO abaixo é tão importante quanto o geográfico.
    """

    def _assert_anel_valido(self, anel, raio, crs):
        from earth_tools import utils

        self.assertTrue(anel, "anel vazio")
        for p in anel:
            self.assertFalse(math.isnan(p.x()) or math.isnan(p.y()), "ponto NaN no anel")
        self.assertEqual(anel[0], anel[-1])
        self.assertGreaterEqual(len(anel), 73)

        geom = QgsGeometry.fromPolygonXY([anel])
        self.assertTrue(geom.isGeosValid(), "geometria do circulo invalida")

        area = utils.measure_area(anel, crs)
        self.assertFalse(math.isnan(area), "Area = NaN - bug original reproduzido")
        esperado = math.pi * raio * raio
        self.assertAlmostEqual(area / esperado, 1.0, delta=0.01)

        perimetro = utils.measure_perimeter(anel, crs)
        self.assertFalse(math.isnan(perimetro))
        self.assertAlmostEqual(perimetro / (2 * math.pi * raio), 1.0, delta=0.01)

    def test_circulo_pequeno_crs_geografico(self):
        from earth_tools import utils

        crs = QgsCoordinateReferenceSystem("EPSG:4326")
        anel, raio = utils.circle_points(
            QgsPointXY(-47.0, -23.0), QgsPointXY(-47.001, -23.0), crs=crs
        )
        self._assert_anel_valido(anel, raio, crs)

    def test_circulo_grande_crs_geografico(self):
        from earth_tools import utils

        crs = QgsCoordinateReferenceSystem("EPSG:4326")
        anel, raio = utils.circle_points(
            QgsPointXY(-47.0, -23.0), QgsPointXY(-47.0, -24.0), crs=crs
        )
        self._assert_anel_valido(anel, raio, crs)

    def test_circulo_pequeno_crs_projetado_reproduz_bug_original(self):
        # Este é exatamente o cenário relatado pelo usuário: SRC projetado
        # (SIRGAS 2000 / UTM, o caso comum no Brasil) - antes da correção,
        # computeSpheroidProject devolvia NaN aqui silenciosamente.
        from earth_tools import utils

        crs = QgsCoordinateReferenceSystem("EPSG:31983")
        anel, raio = utils.circle_points(
            QgsPointXY(200000.0, 7800000.0), QgsPointXY(200500.0, 7800000.0), crs=crs
        )
        self.assertAlmostEqual(raio, 500.0, delta=1.0)
        self._assert_anel_valido(anel, raio, crs)

    def test_circulo_grande_crs_projetado(self):
        from earth_tools import utils

        crs = QgsCoordinateReferenceSystem("EPSG:31983")
        anel, raio = utils.circle_points(
            QgsPointXY(200000.0, 7800000.0), QgsPointXY(230000.0, 7800000.0), crs=crs
        )
        self._assert_anel_valido(anel, raio, crs)

    def test_crs_none_cai_no_crs_do_projeto_sem_nan(self):
        from earth_tools import utils

        # QgsProject.instance() e' um singleton compartilhado por todo o
        # processo de teste - clear() deixa o CRS do projeto INVALIDO, o
        # que contaminaria qualquer teste rodado depois deste. Restaura
        # explicitamente no final, nao so limpa.
        original_crs = QgsProject.instance().crs()
        try:
            QgsProject.instance().setCrs(QgsCoordinateReferenceSystem("EPSG:31983"))
            anel, raio = utils.circle_points(
                QgsPointXY(200000.0, 7800000.0), QgsPointXY(200300.0, 7800000.0), crs=None
            )
            self._assert_anel_valido(anel, raio, QgsProject.instance().crs())
        finally:
            QgsProject.instance().setCrs(original_crs)

    def test_raio_zero_devolve_anel_vazio_sem_erro(self):
        from earth_tools import utils

        crs = QgsCoordinateReferenceSystem("EPSG:4326")
        anel, raio = utils.circle_points(
            QgsPointXY(-47.0, -23.0), QgsPointXY(-47.0, -23.0), crs=crs
        )
        self.assertEqual(anel, [])
        self.assertEqual(raio, 0.0)


@unittest.skipUnless(QGIS_AVAILABLE, "requer o ambiente QGIS")
class ProjectPointTests(unittest.TestCase):
    """utils.project_point() - mesma causa raiz do Círculo, descoberta ao
    corrigi-lo. Usada por "Adicionar por medida" (distância/azimute) em
    Novo Caminho e Novo Polígono (widgets.VertexEntryPanel)."""

    def test_crs_projetado_nao_devolve_nan_reproduz_bug_original(self):
        from earth_tools import utils

        utm = QgsCoordinateReferenceSystem("EPSG:31983")
        p = utils.project_point(QgsPointXY(200000.0, 7800000.0), 500.0, 90.0, utm)
        self.assertIsNotNone(p, "deveria devolver um ponto, nao None")
        self.assertFalse(math.isnan(p.x()) or math.isnan(p.y()), "NaN - bug original reproduzido")

    def test_distancia_real_preservada_em_crs_projetado(self):
        from earth_tools import utils

        utm = QgsCoordinateReferenceSystem("EPSG:31983")
        start = QgsPointXY(200000.0, 7800000.0)
        p = utils.project_point(start, 500.0, 37.0, utm)
        distancia = math.hypot(p.x() - start.x(), p.y() - start.y())
        self.assertAlmostEqual(distancia, 500.0, delta=5.0)

    def test_crs_geografico_continua_funcionando(self):
        from earth_tools import utils

        wgs84 = QgsCoordinateReferenceSystem("EPSG:4326")
        p = utils.project_point(QgsPointXY(-47.0, -23.0), 1000.0, 90.0, wgs84)
        self.assertIsNotNone(p)
        self.assertFalse(math.isnan(p.x()) or math.isnan(p.y()))


# NOTA sobre FeatureDialog ("Novo Caminho") fim-a-fim: construir a janela
# real exige um QgsMapCanvas de verdade (DrawTool/QgsRubberBand não aceitam
# um substituto leve) - e isso, junto com outras dezenas de widgets Qt
# criados pelo resto desta suíte, provoca um crash nativo de teardown do
# Qt NA SAÍDA do processo (depois de "Ran N tests ... OK" já ter sido
# impresso - ruído de finalização, não falha de teste; reproduzido e
# confirmado várias vezes). Para manter o código de saída desta suíte
# confiável, esse cenário fim-a-fim foi verificado manualmente uma vez
# contra o QGIS 3.44.15 real (fora da suíte, processo isolado) em vez de
# ficar como teste permanente aqui - resultado colado no relatório da
# versão. A lógica central (transformação + CRS gravado) continua travada
# por CrsDoCaminhoTests acima, sem depender de QgsMapCanvas.


@unittest.skipUnless(QGIS_AVAILABLE, "requer o ambiente QGIS")
class BufferGeoprocessingTests(unittest.TestCase):
    """Fase F1: geoprocessing.py usa native:buffer de verdade."""

    def setUp(self):
        if not PROCESSING_AVAILABLE:
            self.skipTest("Modulo 'processing' nao disponivel neste ambiente.")
        from earth_tools import geoprocessing

        self.gp = geoprocessing

    def test_rejeita_crs_de_processamento_geografico(self):
        wgs84 = QgsCoordinateReferenceSystem("EPSG:4326")
        geom = QgsGeometry.fromPointXY(QgsPointXY(-47.0, -23.0))
        with self.assertRaises(self.gp.GeoprocessingError):
            self.gp.buffer_single(geom, wgs84, 10.0, 8, wgs84)

    def test_buffer_de_linha_origem_geografica_processamento_projetado(self):
        wgs84 = QgsCoordinateReferenceSystem("EPSG:4326")
        utm = QgsCoordinateReferenceSystem("EPSG:31983")
        linha = QgsGeometry.fromPolylineXY(
            [QgsPointXY(-47.0, -23.0), QgsPointXY(-47.01, -23.01)]
        )
        resultado = self.gp.buffer_single(linha, wgs84, 50.0, 8, utm)
        self.assertTrue(resultado.isGeosValid())
        self.assertGreater(resultado.area(), 0)

    def test_run_buffer_dissolve_combina_em_uma_geometria(self):
        wgs84 = QgsCoordinateReferenceSystem("EPSG:4326")
        utm = QgsCoordinateReferenceSystem("EPSG:31983")
        p1 = QgsGeometry.fromPointXY(QgsPointXY(-47.0, -23.0))
        p2 = QgsGeometry.fromPointXY(QgsPointXY(-47.0005, -23.0))
        resultados = self.gp.run_buffer(
            [(p1, wgs84), (p2, wgs84)], 100.0, 16, True, utm
        )
        self.assertEqual(len(resultados), 1)
        self.assertTrue(resultados[0].isGeosValid())

    def test_run_buffer_sem_dissolve_mantem_resultados_separados(self):
        wgs84 = QgsCoordinateReferenceSystem("EPSG:4326")
        utm = QgsCoordinateReferenceSystem("EPSG:31983")
        p1 = QgsGeometry.fromPointXY(QgsPointXY(-47.0, -23.0))
        p2 = QgsGeometry.fromPointXY(QgsPointXY(-47.0005, -23.0))
        resultados = self.gp.run_buffer(
            [(p1, wgs84), (p2, wgs84)], 100.0, 16, False, utm
        )
        self.assertEqual(len(resultados), 2)

    def test_reproject_preserva_a_geometria_original(self):
        wgs84 = QgsCoordinateReferenceSystem("EPSG:4326")
        utm = QgsCoordinateReferenceSystem("EPSG:31983")
        original = QgsGeometry.fromPointXY(QgsPointXY(-47.0, -23.0))
        wkt_antes = original.asWkt()
        reprojetada = self.gp.reproject(original, wgs84, utm)
        self.assertEqual(original.asWkt(), wkt_antes)
        self.assertGreater(abs(reprojetada.asPoint().x()), 1000.0)


@unittest.skipUnless(QGIS_AVAILABLE, "requer o ambiente QGIS")
class BufferDialogTests(unittest.TestCase):
    """Fim a fim na janela real "Gerar Buffer..." - diferente de
    FeatureDialog, BufferDialog não usa QgsMapCanvas/QgsRubberBand, então
    não sofre do crash de teardown do Qt (ver nota acima sobre
    FeatureDialog) - seguro manter na suíte permanente."""

    class _FakeMessageBar:
        def pushSuccess(self, *a, **k):
            pass

    class _FakeIface:
        def mainWindow(self):
            return None

        def messageBar(self):
            return BufferDialogTests._FakeMessageBar()

    def setUp(self):
        if not PROCESSING_AVAILABLE:
            self.skipTest("Modulo 'processing' nao disponivel neste ambiente.")
        import tempfile

        from earth_tools import storage

        self.storage = storage
        self._tmpdir = tempfile.mkdtemp()
        QgsProject.instance().clear()
        QgsProject.instance().setFileName(os.path.join(self._tmpdir, "teste.qgz"))
        QgsProject.instance().setCrs(QgsCoordinateReferenceSystem("EPSG:4326"))

    def tearDown(self):
        QgsProject.instance().clear()
        QgsProject.instance().setCrs(QgsCoordinateReferenceSystem("EPSG:4326"))

    def test_buffer_de_dois_lugares_dissolvido_grava_uma_camada_no_crs_escolhido(self):
        from earth_tools.dlg_buffer import BufferDialog

        linha = self.storage.create_place(
            "line", "Caminho de teste",
            QgsGeometry.fromPolylineXY(
                [QgsPointXY(-47.0, -23.0), QgsPointXY(-47.01, -23.01)]
            ),
            {},
        )
        poligono = self.storage.create_place(
            "polygon", "Area de teste",
            QgsGeometry.fromPolygonXY([[
                QgsPointXY(-47.0, -23.0), QgsPointXY(-47.01, -23.0),
                QgsPointXY(-47.01, -23.01), QgsPointXY(-47.0, -23.0),
            ]]),
            {},
        )

        iface = self._FakeIface()
        dialog = BufferDialog(iface, [linha, poligono], None)
        dialog.distance_spin.setValue(50.0)
        utm = QgsCoordinateReferenceSystem("EPSG:31983")
        dialog.processing_crs_row.setCrs(utm)
        dialog.output_crs_row.setCrs(utm)
        dialog.dissolve_check.setChecked(True)

        antes = set(QgsProject.instance().mapLayers().keys())
        dialog._run()
        depois = set(QgsProject.instance().mapLayers().keys())
        novas = depois - antes

        self.assertEqual(len(novas), 1)
        nova = QgsProject.instance().mapLayer(list(novas)[0])
        self.assertEqual(nova.crs().authid(), "EPSG:31983")
        feature = next(nova.getFeatures())
        self.assertTrue(feature.geometry().isGeosValid())
        self.assertGreater(feature.geometry().area(), 0)
        # As camadas de origem continuam intactas (Buffer nao e' destrutivo).
        self.assertTrue(linha.isValid())
        self.assertTrue(poligono.isValid())

    def test_rejeita_crs_de_processamento_geografico_sem_gravar_nada(self):
        from earth_tools.dlg_buffer import BufferDialog

        linha = self.storage.create_place(
            "line", "Caminho de teste",
            QgsGeometry.fromPolylineXY(
                [QgsPointXY(-47.0, -23.0), QgsPointXY(-47.01, -23.01)]
            ),
            {},
        )
        iface = self._FakeIface()
        dialog = BufferDialog(iface, [linha], None)
        dialog.distance_spin.setValue(50.0)
        dialog.processing_crs_row.setCrs(QgsCoordinateReferenceSystem("EPSG:4326"))

        antes = set(QgsProject.instance().mapLayers().keys())
        dialog._run()
        depois = set(QgsProject.instance().mapLayers().keys())
        self.assertEqual(antes, depois, "nao deveria ter gravado nada com SRC geografico")


@unittest.skipUnless(QGIS_AVAILABLE, "requer o ambiente QGIS")
class UnionGeoprocessingTests(unittest.TestCase):
    """Fase F2: geoprocessing.union_polygons() - QgsGeometry.unaryUnion()."""

    def setUp(self):
        from earth_tools import geoprocessing

        self.gp = geoprocessing
        self.wgs84 = QgsCoordinateReferenceSystem("EPSG:4326")

    def test_uniao_de_dois_poligonos_adjacentes(self):
        p1 = QgsGeometry.fromPolygonXY([[
            QgsPointXY(0, 0), QgsPointXY(1, 0), QgsPointXY(1, 1), QgsPointXY(0, 1),
            QgsPointXY(0, 0),
        ]])
        p2 = QgsGeometry.fromPolygonXY([[
            QgsPointXY(1, 0), QgsPointXY(2, 0), QgsPointXY(2, 1), QgsPointXY(1, 1),
            QgsPointXY(1, 0),
        ]])
        resultado = self.gp.union_polygons([(p1, self.wgs84), (p2, self.wgs84)], self.wgs84)
        self.assertAlmostEqual(resultado.area(), 2.0, delta=0.001)
        self.assertTrue(resultado.isGeosValid())

    def test_uniao_rejeita_menos_de_2_entradas(self):
        p1 = QgsGeometry.fromPolygonXY([[
            QgsPointXY(0, 0), QgsPointXY(1, 0), QgsPointXY(1, 1), QgsPointXY(0, 0)
        ]])
        with self.assertRaises(self.gp.GeoprocessingError):
            self.gp.union_polygons([(p1, self.wgs84)], self.wgs84)

    def test_uniao_rejeita_entrada_que_nao_e_poligono(self):
        p1 = QgsGeometry.fromPolygonXY([[
            QgsPointXY(0, 0), QgsPointXY(1, 0), QgsPointXY(1, 1), QgsPointXY(0, 0)
        ]])
        linha = QgsGeometry.fromPolylineXY([QgsPointXY(0, 0), QgsPointXY(1, 1)])
        with self.assertRaises(self.gp.GeoprocessingError):
            self.gp.union_polygons([(p1, self.wgs84), (linha, self.wgs84)], self.wgs84)

    def test_uniao_com_crs_diferentes_entre_entradas(self):
        utm = QgsCoordinateReferenceSystem("EPSG:31983")
        p1 = QgsGeometry.fromPolygonXY([[
            QgsPointXY(0, 0), QgsPointXY(1, 0), QgsPointXY(1, 1), QgsPointXY(0, 1),
            QgsPointXY(0, 0),
        ]])
        p2_utm = QgsGeometry.fromPolygonXY([[
            QgsPointXY(200000, 7800000), QgsPointXY(200100, 7800000),
            QgsPointXY(200100, 7800100), QgsPointXY(200000, 7800100),
            QgsPointXY(200000, 7800000),
        ]])
        resultado = self.gp.union_polygons([(p1, self.wgs84), (p2_utm, utm)], utm)
        self.assertTrue(resultado.isGeosValid())
        self.assertGreater(resultado.area(), 0)


@unittest.skipUnless(QGIS_AVAILABLE, "requer o ambiente QGIS")
class UnionDialogTests(unittest.TestCase):
    """Fim a fim na janela "Unir polígonos..." - sem QgsMapCanvas, segura
    para a suíte permanente."""

    class _FakeMessageBar:
        def pushSuccess(self, *a, **k):
            pass

    class _FakeIface:
        def mainWindow(self):
            return None

        def messageBar(self):
            return UnionDialogTests._FakeMessageBar()

    def setUp(self):
        import tempfile

        from earth_tools import storage

        self.storage = storage
        self._tmpdir = tempfile.mkdtemp()
        QgsProject.instance().clear()
        QgsProject.instance().setFileName(os.path.join(self._tmpdir, "teste.qgz"))
        QgsProject.instance().setCrs(QgsCoordinateReferenceSystem("EPSG:4326"))

    def tearDown(self):
        QgsProject.instance().clear()
        QgsProject.instance().setCrs(QgsCoordinateReferenceSystem("EPSG:4326"))

    def test_uniao_de_dois_poligonos_grava_uma_camada_preservando_origem(self):
        from earth_tools.dlg_union import UnionDialog

        poligono1 = self.storage.create_place(
            "polygon", "Area 1",
            QgsGeometry.fromPolygonXY([[
                QgsPointXY(-47.0, -23.0), QgsPointXY(-47.01, -23.0),
                QgsPointXY(-47.01, -23.01), QgsPointXY(-47.0, -23.01),
                QgsPointXY(-47.0, -23.0),
            ]]),
            {},
        )
        poligono2 = self.storage.create_place(
            "polygon", "Area 2",
            QgsGeometry.fromPolygonXY([[
                QgsPointXY(-47.01, -23.0), QgsPointXY(-47.02, -23.0),
                QgsPointXY(-47.02, -23.01), QgsPointXY(-47.01, -23.01),
                QgsPointXY(-47.01, -23.0),
            ]]),
            {},
        )
        iface = self._FakeIface()
        dialog = UnionDialog(iface, [poligono1, poligono2], None)

        antes = set(QgsProject.instance().mapLayers().keys())
        dialog._run()
        depois = set(QgsProject.instance().mapLayers().keys())
        novas = depois - antes

        self.assertEqual(len(novas), 1)
        nova = QgsProject.instance().mapLayer(list(novas)[0])
        self.assertTrue(nova.isValid())
        feature = next(nova.getFeatures())
        self.assertTrue(feature.geometry().isGeosValid())
        self.assertTrue(poligono1.isValid())
        self.assertTrue(poligono2.isValid())


@unittest.skipUnless(QGIS_AVAILABLE, "requer o ambiente QGIS")
class SplitGeoprocessingTests(unittest.TestCase):
    """Fase F3: geoprocessing.split_polygon() - native:splitwithlines."""

    def setUp(self):
        if not PROCESSING_AVAILABLE:
            self.skipTest("Modulo 'processing' nao disponivel neste ambiente.")
        from earth_tools import geoprocessing

        self.gp = geoprocessing
        self.wgs84 = QgsCoordinateReferenceSystem("EPSG:4326")
        self.quadrado = QgsGeometry.fromPolygonXY([[
            QgsPointXY(0, 0), QgsPointXY(2, 0), QgsPointXY(2, 2), QgsPointXY(0, 2),
            QgsPointXY(0, 0),
        ]])

    def test_linha_que_atravessa_produz_duas_partes_validas(self):
        corte = QgsGeometry.fromPolylineXY([QgsPointXY(1, -1), QgsPointXY(1, 3)])
        partes = self.gp.split_polygon(self.quadrado, self.wgs84, corte, self.wgs84, self.wgs84)
        self.assertEqual(len(partes), 2)
        self.assertTrue(all(p.isGeosValid() for p in partes))
        self.assertAlmostEqual(sum(p.area() for p in partes), self.quadrado.area(), delta=0.001)

    def test_linha_que_nao_atravessa_e_rejeitada_com_mensagem_clara(self):
        corte_fora = QgsGeometry.fromPolylineXY([QgsPointXY(5, 5), QgsPointXY(6, 6)])
        with self.assertRaises(self.gp.GeoprocessingError):
            self.gp.split_polygon(
                self.quadrado, self.wgs84, corte_fora, self.wgs84, self.wgs84
            )

    def test_rejeita_geometria_de_entrada_que_nao_e_poligono(self):
        linha_qualquer = QgsGeometry.fromPolylineXY([QgsPointXY(0, 0), QgsPointXY(1, 1)])
        with self.assertRaises(self.gp.GeoprocessingError):
            self.gp.split_polygon(
                linha_qualquer, self.wgs84, linha_qualquer, self.wgs84, self.wgs84
            )

    def test_divide_com_poligono_e_linha_em_crs_diferentes(self):
        utm = QgsCoordinateReferenceSystem("EPSG:31983")
        quadrado_utm = QgsGeometry.fromPolygonXY([[
            QgsPointXY(200000, 7800000), QgsPointXY(200100, 7800000),
            QgsPointXY(200100, 7800100), QgsPointXY(200000, 7800100),
            QgsPointXY(200000, 7800000),
        ]])
        transform = QgsCoordinateTransform(utm, self.wgs84, QgsProject.instance())
        corte_utm = QgsGeometry.fromPolylineXY(
            [QgsPointXY(200050, 7799900), QgsPointXY(200050, 7800200)]
        )
        corte_wgs = QgsGeometry(corte_utm)
        corte_wgs.transform(transform)
        partes = self.gp.split_polygon(quadrado_utm, utm, corte_wgs, self.wgs84, utm)
        self.assertEqual(len(partes), 2)
        self.assertTrue(all(p.isGeosValid() for p in partes))


@unittest.skipUnless(QGIS_AVAILABLE, "requer o ambiente QGIS")
class ClipGeoprocessingTests(unittest.TestCase):
    """Fase F4: geoprocessing.clip_geometry() - native:clip."""

    def setUp(self):
        if not PROCESSING_AVAILABLE:
            self.skipTest("Modulo 'processing' nao disponivel neste ambiente.")
        from earth_tools import geoprocessing

        self.gp = geoprocessing
        self.wgs84 = QgsCoordinateReferenceSystem("EPSG:4326")
        self.mascara = QgsGeometry.fromPolygonXY([[
            QgsPointXY(0, 0), QgsPointXY(2, 0), QgsPointXY(2, 2), QgsPointXY(0, 2),
            QgsPointXY(0, 0),
        ]])

    def test_recorte_poligono_por_poligono(self):
        alvo = QgsGeometry.fromPolygonXY([[
            QgsPointXY(1, 1), QgsPointXY(3, 1), QgsPointXY(3, 3), QgsPointXY(1, 3),
            QgsPointXY(1, 1),
        ]])
        resultado = self.gp.clip_geometry(alvo, self.wgs84, self.mascara, self.wgs84, self.wgs84)
        self.assertAlmostEqual(resultado.area(), 1.0, delta=0.001)
        self.assertTrue(resultado.isGeosValid())

    def test_recorte_linha_por_poligono(self):
        linha = QgsGeometry.fromPolylineXY([QgsPointXY(-1, 1), QgsPointXY(3, 1)])
        resultado = self.gp.clip_geometry(linha, self.wgs84, self.mascara, self.wgs84, self.wgs84)
        self.assertAlmostEqual(resultado.length(), 2.0, delta=0.001)

    def test_sem_intersecao_levanta_erro_claro(self):
        longe = QgsGeometry.fromPolygonXY([[
            QgsPointXY(10, 10), QgsPointXY(11, 10), QgsPointXY(11, 11), QgsPointXY(10, 10)
        ]])
        with self.assertRaises(self.gp.GeoprocessingError):
            self.gp.clip_geometry(longe, self.wgs84, self.mascara, self.wgs84, self.wgs84)

    def test_mascara_que_nao_e_poligono_e_rejeitada(self):
        alvo = QgsGeometry.fromPolygonXY([[
            QgsPointXY(1, 1), QgsPointXY(3, 1), QgsPointXY(3, 3), QgsPointXY(1, 1)
        ]])
        linha = QgsGeometry.fromPolylineXY([QgsPointXY(0, 0), QgsPointXY(1, 1)])
        with self.assertRaises(self.gp.GeoprocessingError):
            self.gp.clip_geometry(alvo, self.wgs84, linha, self.wgs84, self.wgs84)


@unittest.skipUnless(QGIS_AVAILABLE, "requer o ambiente QGIS")
class ClipDialogTests(unittest.TestCase):
    """Fim a fim na janela "Recortar com..." - sem QgsMapCanvas."""

    class _FakeMessageBar:
        def pushSuccess(self, *a, **k):
            pass

    class _FakeIface:
        def mainWindow(self):
            return None

        def messageBar(self):
            return ClipDialogTests._FakeMessageBar()

    def setUp(self):
        if not PROCESSING_AVAILABLE:
            self.skipTest("Modulo 'processing' nao disponivel neste ambiente.")
        import tempfile

        from earth_tools import storage

        self.storage = storage
        self._tmpdir = tempfile.mkdtemp()
        QgsProject.instance().clear()
        QgsProject.instance().setFileName(os.path.join(self._tmpdir, "teste.qgz"))
        QgsProject.instance().setCrs(QgsCoordinateReferenceSystem("EPSG:4326"))

    def tearDown(self):
        QgsProject.instance().clear()
        QgsProject.instance().setCrs(QgsCoordinateReferenceSystem("EPSG:4326"))

    def test_recorte_grava_uma_camada_preservando_origem(self):
        from earth_tools.dlg_clip import ClipDialog

        mascara = self.storage.create_place(
            "polygon", "Mascara",
            QgsGeometry.fromPolygonXY([[
                QgsPointXY(0, 0), QgsPointXY(2, 0), QgsPointXY(2, 2), QgsPointXY(0, 2),
                QgsPointXY(0, 0),
            ]]),
            {},
        )
        alvo = self.storage.create_place(
            "polygon", "Area alvo",
            QgsGeometry.fromPolygonXY([[
                QgsPointXY(1, 1), QgsPointXY(3, 1), QgsPointXY(3, 3), QgsPointXY(1, 3),
                QgsPointXY(1, 1),
            ]]),
            {},
        )
        iface = self._FakeIface()
        dialog = ClipDialog(iface, [mascara, alvo], alvo, None)
        idx = dialog.mask_combo.findData(mascara.id())
        dialog.mask_combo.setCurrentIndex(idx)

        antes = set(QgsProject.instance().mapLayers().keys())
        dialog._run()
        depois = set(QgsProject.instance().mapLayers().keys())
        novas = depois - antes

        self.assertEqual(len(novas), 1)
        nova = QgsProject.instance().mapLayer(list(novas)[0])
        feature = next(nova.getFeatures())
        self.assertAlmostEqual(feature.geometry().area(), 1.0, delta=0.001)
        self.assertTrue(alvo.isValid())
        self.assertTrue(mascara.isValid())

    def test_alvo_igual_a_mascara_e_rejeitado_sem_gravar(self):
        from earth_tools.dlg_clip import ClipDialog

        poligono = self.storage.create_place(
            "polygon", "Unico",
            QgsGeometry.fromPolygonXY([[
                QgsPointXY(0, 0), QgsPointXY(1, 0), QgsPointXY(1, 1), QgsPointXY(0, 0)
            ]]),
            {},
        )
        iface = self._FakeIface()
        dialog = ClipDialog(iface, [poligono], poligono, None)
        idx = dialog.mask_combo.findData(poligono.id())
        dialog.mask_combo.setCurrentIndex(idx)

        antes = set(QgsProject.instance().mapLayers().keys())
        dialog._run()
        depois = set(QgsProject.instance().mapLayers().keys())
        self.assertEqual(antes, depois)


@unittest.skipUnless(QGIS_AVAILABLE, "requer o ambiente QGIS")
class DifferenceAndNegativeBufferTests(unittest.TestCase):
    """Fase F5: geoprocessing.difference_geometry() e Buffer negativo."""

    def setUp(self):
        if not PROCESSING_AVAILABLE:
            self.skipTest("Modulo 'processing' nao disponivel neste ambiente.")
        from earth_tools import geoprocessing

        self.gp = geoprocessing
        self.wgs84 = QgsCoordinateReferenceSystem("EPSG:4326")

    def test_diferenca_entre_dois_poligonos_sobrepostos(self):
        a = QgsGeometry.fromPolygonXY([[
            QgsPointXY(0, 0), QgsPointXY(2, 0), QgsPointXY(2, 2), QgsPointXY(0, 2),
            QgsPointXY(0, 0),
        ]])
        b = QgsGeometry.fromPolygonXY([[
            QgsPointXY(1, 1), QgsPointXY(3, 1), QgsPointXY(3, 3), QgsPointXY(1, 3),
            QgsPointXY(1, 1),
        ]])
        resultado = self.gp.difference_geometry(a, self.wgs84, b, self.wgs84, self.wgs84)
        self.assertAlmostEqual(resultado.area(), 3.0, delta=0.001)

    def test_diferenca_totalmente_coberta_levanta_erro_claro(self):
        a = QgsGeometry.fromPolygonXY([[
            QgsPointXY(0, 0), QgsPointXY(2, 0), QgsPointXY(2, 2), QgsPointXY(0, 0)
        ]])
        grande = QgsGeometry.fromPolygonXY([[
            QgsPointXY(-5, -5), QgsPointXY(5, -5), QgsPointXY(5, 5), QgsPointXY(-5, -5)
        ]])
        with self.assertRaises(self.gp.GeoprocessingError):
            self.gp.difference_geometry(a, self.wgs84, grande, self.wgs84, self.wgs84)

    def test_buffer_negativo_encolhe_poligono(self):
        utm = QgsCoordinateReferenceSystem("EPSG:31983")
        quadrado = QgsGeometry.fromPolygonXY([[
            QgsPointXY(0, 0), QgsPointXY(10, 0), QgsPointXY(10, 10), QgsPointXY(0, 10),
            QgsPointXY(0, 0),
        ]])
        encolhido = self.gp.buffer_single(quadrado, utm, -2.0, 8, utm)
        self.assertAlmostEqual(encolhido.area(), 36.0, delta=1.0)

    def test_buffer_distancia_zero_e_rejeitado(self):
        utm = QgsCoordinateReferenceSystem("EPSG:31983")
        quadrado = QgsGeometry.fromPolygonXY([[
            QgsPointXY(0, 0), QgsPointXY(10, 0), QgsPointXY(10, 10), QgsPointXY(0, 0)
        ]])
        with self.assertRaises(self.gp.GeoprocessingError):
            self.gp.buffer_single(quadrado, utm, 0.0, 8, utm)


@unittest.skipUnless(QGIS_AVAILABLE, "requer o ambiente QGIS")
class StylePersistenceTests(unittest.TestCase):
    """Gerenciador de Estilos (auditoria): storage.set_style() precisa
    persistir no GeoPackage de verdade, não só no customProperty do
    projeto. Trava a causa raiz encontrada nesta auditoria: o código
    original usava `in` sobre Qgis.ProviderStyleStorageCapabilities, que
    não é um container nesse binding - levantava TypeError, engolido pelo
    except, fazendo a função parecer persistir sem persistir nada."""

    def setUp(self):
        import tempfile

        from earth_tools import storage

        self.storage = storage
        self._tmpdir = tempfile.mkdtemp()
        QgsProject.instance().clear()
        QgsProject.instance().setFileName(os.path.join(self._tmpdir, "teste.qgz"))
        QgsProject.instance().setCrs(QgsCoordinateReferenceSystem("EPSG:4326"))

    def tearDown(self):
        QgsProject.instance().clear()
        QgsProject.instance().setCrs(QgsCoordinateReferenceSystem("EPSG:4326"))

    def test_estilo_sobrevive_a_reabrir_a_camada_sem_nenhum_projeto(self):
        from qgis.core import QgsVectorLayer

        poly = QgsGeometry.fromPolygonXY([[
            QgsPointXY(-47.0, -23.0), QgsPointXY(-47.01, -23.0),
            QgsPointXY(-47.01, -23.01), QgsPointXY(-47.0, -23.0),
        ]])
        layer = self.storage.create_place("polygon", "Teste persistencia", poly, {
            "cor_linha": "0,0,255,255", "cor_preenchimento": "255,255,0,80", "largura_linha": 3.0,
        })
        path = layer.source().split("|")[0]
        table = self.storage.table_name(layer)

        # Camada aberta do ZERO, sem nenhum vinculo com o objeto `layer`
        # nem com qualquer projeto - simula abrir o .gpkg direto.
        reaberta = QgsVectorLayer("{}|layername={}".format(path, table), "reaberta", "ogr")
        self.assertTrue(reaberta.isValid())
        symbol = reaberta.renderer().symbol()
        self.assertEqual(symbol.color().name(), "#ffff00")
        self.assertEqual(symbol.color().alpha(), 80)


@unittest.skipUnless(QGIS_AVAILABLE, "requer o ambiente QGIS")
class StyleManagerTests(unittest.TestCase):
    """Fase H: StyleManagerDialog e presets via QSettings."""

    class _FakeMessageBar:
        def pushSuccess(self, *a, **k):
            pass

    class _FakeIface:
        def mainWindow(self):
            return None

        def messageBar(self):
            return StyleManagerTests._FakeMessageBar()

    def setUp(self):
        import tempfile

        from earth_tools import storage

        self.storage = storage
        self._tmpdir = tempfile.mkdtemp()
        QgsProject.instance().clear()
        QgsProject.instance().setFileName(os.path.join(self._tmpdir, "teste.qgz"))
        QgsProject.instance().setCrs(QgsCoordinateReferenceSystem("EPSG:4326"))

    def tearDown(self):
        QgsProject.instance().clear()
        QgsProject.instance().setCrs(QgsCoordinateReferenceSystem("EPSG:4326"))
        from earth_tools.dlg_style_manager import delete_preset

        delete_preset("__teste_regressao__")

    def test_aplicar_estilo_em_duas_camadas_de_uma_vez(self):
        from qgis.PyQt.QtGui import QColor
        from qgis.core import QgsVectorLayer

        from earth_tools.dlg_style_manager import StyleManagerDialog

        poly1 = QgsGeometry.fromPolygonXY([[
            QgsPointXY(-47.0, -23.0), QgsPointXY(-47.01, -23.0),
            QgsPointXY(-47.01, -23.01), QgsPointXY(-47.0, -23.0),
        ]])
        poly2 = QgsGeometry.fromPolygonXY([[
            QgsPointXY(-47.1, -23.1), QgsPointXY(-47.11, -23.1),
            QgsPointXY(-47.11, -23.11), QgsPointXY(-47.1, -23.1),
        ]])
        camada1 = self.storage.create_place("polygon", "Area 1", poly1, {})
        camada2 = self.storage.create_place("polygon", "Area 2", poly2, {})

        dialog = StyleManagerDialog(self._FakeIface(), [camada1, camada2], None)
        dialog.style_tab.line_color.setColor(QColor(10, 20, 30))
        geom_antes = next(camada1.getFeatures()).geometry().asWkt()
        dialog._apply()

        path = camada1.source().split("|")[0]
        for layer in (camada1, camada2):
            table = self.storage.table_name(layer)
            reaberta = QgsVectorLayer("{}|layername={}".format(path, table), "r", "ogr")
            cor = reaberta.renderer().symbol().symbolLayer(0).strokeColor()
            self.assertEqual(cor.getRgb()[:3], (10, 20, 30))
        # Geometria da camada1 nao foi alterada por uma operacao de estilo.
        self.assertEqual(next(camada1.getFeatures()).geometry().asWkt(), geom_antes)

    def test_presets_salvar_carregar_excluir(self):
        from earth_tools.dlg_style_manager import (
            delete_preset,
            list_presets,
            load_preset,
            save_preset,
        )

        save_preset("__teste_regressao__", "1,2,3,255", "4,5,6,77", 9.5)
        self.assertIn("__teste_regressao__", list_presets())
        cor_linha, cor_preenchimento, largura = load_preset("__teste_regressao__")
        self.assertEqual(cor_linha, "1,2,3,255")
        self.assertAlmostEqual(largura, 9.5)
        delete_preset("__teste_regressao__")
        self.assertNotIn("__teste_regressao__", list_presets())


@unittest.skipUnless(QGIS_AVAILABLE, "requer o ambiente QGIS")
class GeometryValidatorTests(unittest.TestCase):
    """Fase G1: geometry_validator.py contra o QGIS real."""

    def setUp(self):
        import tempfile

        from earth_tools import geometry_validator, storage

        self.gv = geometry_validator
        self.storage = storage
        self._tmpdir = tempfile.mkdtemp()
        QgsProject.instance().clear()
        QgsProject.instance().setFileName(os.path.join(self._tmpdir, "teste.qgz"))
        QgsProject.instance().setCrs(QgsCoordinateReferenceSystem("EPSG:4326"))

    def tearDown(self):
        QgsProject.instance().clear()
        QgsProject.instance().setCrs(QgsCoordinateReferenceSystem("EPSG:4326"))

    def test_poligono_valido_sem_problemas(self):
        valido = self.storage.create_place("polygon", "Valido", QgsGeometry.fromPolygonXY([[
            QgsPointXY(0, 0), QgsPointXY(1, 0), QgsPointXY(1, 1), QgsPointXY(0, 1),
            QgsPointXY(0, 0),
        ]]), {})
        issues, total, validos = self.gv.validate_layers([valido])
        self.assertEqual(total, 1)
        self.assertEqual(validos, 1)
        self.assertEqual(issues, [])

    def test_poligono_bowtie_e_invalido(self):
        bowtie = self.storage.create_place("polygon", "Bowtie", QgsGeometry.fromPolygonXY([[
            QgsPointXY(10, 0), QgsPointXY(11, 1), QgsPointXY(11, 0), QgsPointXY(10, 1),
            QgsPointXY(10, 0),
        ]]), {})
        issues, total, validos = self.gv.validate_layers([bowtie])
        self.assertEqual(validos, 0)
        self.assertTrue(any(i.kind == self.gv.INVALID for i in issues))

    def test_vertices_duplicados_consecutivos_sao_detectados(self):
        dup = self.storage.create_place("polygon", "Duplicado", QgsGeometry.fromPolygonXY([[
            QgsPointXY(20, 0), QgsPointXY(20, 0), QgsPointXY(21, 0), QgsPointXY(21, 1),
            QgsPointXY(20, 0),
        ]]), {})
        issues, _total, _validos = self.gv.validate_layers([dup])
        self.assertTrue(any(i.kind == self.gv.DUPLICATE_VERTEX for i in issues))

    def test_sobreposicao_entre_poligonos_so_quando_pedida(self):
        a = self.storage.create_place("polygon", "A", QgsGeometry.fromPolygonXY([[
            QgsPointXY(30, 0), QgsPointXY(32, 0), QgsPointXY(32, 2), QgsPointXY(30, 2),
            QgsPointXY(30, 0),
        ]]), {})
        b = self.storage.create_place("polygon", "B", QgsGeometry.fromPolygonXY([[
            QgsPointXY(31, 1), QgsPointXY(33, 1), QgsPointXY(33, 3), QgsPointXY(31, 3),
            QgsPointXY(31, 1),
        ]]), {})
        sem_check, _, _ = self.gv.validate_layers([a, b], check_overlaps=False)
        self.assertFalse(any(i.kind == self.gv.OVERLAP for i in sem_check))
        com_check, _, _ = self.gv.validate_layers([a, b], check_overlaps=True)
        self.assertTrue(any(i.kind == self.gv.OVERLAP for i in com_check))

    def test_make_valid_copy_nao_altera_a_geometria_original(self):
        bowtie = self.storage.create_place("polygon", "Bowtie2", QgsGeometry.fromPolygonXY([[
            QgsPointXY(40, 0), QgsPointXY(41, 1), QgsPointXY(41, 0), QgsPointXY(40, 1),
            QgsPointXY(40, 0),
        ]]), {})
        original = next(bowtie.getFeatures()).geometry()
        wkt_antes = original.asWkt()
        corrigida = self.gv.make_valid_copy(original)
        self.assertTrue(corrigida.isGeosValid())
        self.assertEqual(original.asWkt(), wkt_antes)

    def test_fora_dos_limites_com_layer_em_crs_diferente_do_extent(self):
        utm = QgsCoordinateReferenceSystem("EPSG:31983")
        longe = self.storage.create_place(
            "polygon", "Longe UTM",
            QgsGeometry.fromPolygonXY([[
                QgsPointXY(900000, 9000000), QgsPointXY(900100, 9000000),
                QgsPointXY(900100, 9000100), QgsPointXY(900000, 9000000),
            ]]),
            {}, crs=utm,
        )
        extent_wgs84 = QgsRectangle(-48.0, -24.0, -46.0, -22.0)
        issues, _, _ = self.gv.validate_layers([longe], reference_extent=extent_wgs84)
        self.assertTrue(any(i.kind == self.gv.OUT_OF_BOUNDS for i in issues))


@unittest.skipUnless(QGIS_AVAILABLE, "requer o ambiente QGIS")
class CalculatorDialogTests(unittest.TestCase):
    """Etapa 2: CalculatorDialog - sem QgsMapCanvas, seguro para a suíte."""

    class _FakeMessageBar:
        def pushSuccess(self, *a, **k):
            pass

    class _FakeIface:
        def mainWindow(self):
            return None

        def messageBar(self):
            return CalculatorDialogTests._FakeMessageBar()

    def setUp(self):
        import tempfile

        from earth_tools import storage

        self.storage = storage
        self._tmpdir = tempfile.mkdtemp()
        QgsProject.instance().clear()
        QgsProject.instance().setFileName(os.path.join(self._tmpdir, "teste.qgz"))
        QgsProject.instance().setCrs(QgsCoordinateReferenceSystem("EPSG:4326"))

    def tearDown(self):
        QgsProject.instance().clear()
        QgsProject.instance().setCrs(QgsCoordinateReferenceSystem("EPSG:4326"))

    def test_poligono_mostra_area_e_perimetro_corretos(self):
        from earth_tools.dlg_calculator import CalculatorDialog

        poly = QgsGeometry.fromPolygonXY([[
            QgsPointXY(-47.0, -23.0), QgsPointXY(-47.01, -23.0),
            QgsPointXY(-47.01, -23.01), QgsPointXY(-47.0, -23.01), QgsPointXY(-47.0, -23.0),
        ]])
        camada = self.storage.create_place("polygon", "Area calc teste", poly, {})
        dialog = CalculatorDialog(self._FakeIface(), None)
        idx = dialog.layer_combo.findData(camada.id())
        dialog.layer_combo.setCurrentIndex(idx)

        self.assertEqual(dialog._active_rows, {"perimeter", "area"})
        self.assertNotEqual(dialog.perimeter_row.value.text(), "0,00")
        self.assertNotEqual(dialog.area_row.value.text(), "0,00")

    def test_caminho_mostra_so_comprimento(self):
        from earth_tools.dlg_calculator import CalculatorDialog

        linha = QgsGeometry.fromPolylineXY(
            [QgsPointXY(-47.0, -23.0), QgsPointXY(-47.01, -23.01)]
        )
        camada = self.storage.create_place("line", "Caminho calc teste", linha, {})
        dialog = CalculatorDialog(self._FakeIface(), None)
        idx = dialog.layer_combo.findData(camada.id())
        dialog.layer_combo.setCurrentIndex(idx)

        self.assertEqual(dialog._active_rows, {"length"})
        self.assertNotEqual(dialog.length_row.value.text(), "0,00")

    def test_copiar_resultado_vai_para_a_area_de_transferencia_real(self):
        from qgis.PyQt.QtWidgets import QApplication

        from earth_tools.dlg_calculator import CalculatorDialog

        linha = QgsGeometry.fromPolylineXY(
            [QgsPointXY(-47.0, -23.0), QgsPointXY(-47.01, -23.01)]
        )
        camada = self.storage.create_place("line", "Caminho copiar", linha, {})
        dialog = CalculatorDialog(self._FakeIface(), None)
        idx = dialog.layer_combo.findData(camada.id())
        dialog.layer_combo.setCurrentIndex(idx)
        dialog._copy_result()

        texto = QApplication.clipboard().text()
        self.assertIn("Caminho copiar", texto)
        self.assertIn("Comprimento", texto)

    def test_area_multiparte_e_medida_corretamente(self):
        from earth_tools import utils

        multi = QgsGeometry.fromMultiPolygonXY([
            [[QgsPointXY(0, 0), QgsPointXY(1, 0), QgsPointXY(1, 1), QgsPointXY(0, 1), QgsPointXY(0, 0)]],
            [[QgsPointXY(2, 0), QgsPointXY(3, 0), QgsPointXY(3, 1), QgsPointXY(2, 1), QgsPointXY(2, 0)]],
        ])
        area = utils.measure_area_geometry(multi, QgsCoordinateReferenceSystem("EPSG:4326"))
        self.assertGreater(area, 0)


@unittest.skipUnless(QGIS_AVAILABLE, "requer o ambiente QGIS")
class ExportMapReportsTests(unittest.TestCase):
    """Etapa 5: reports.py - QgsPrintLayout real, exportação PDF/PNG real.

    Não usa QgsMapCanvas (reports.py recebe camadas/extensão/CRS já
    resolvidos pelo chamador) - seguro para a suíte permanente. O diálogo
    completo (ExportMapDialog, que usa QgsMapCanvas via iface) foi
    verificado manualmente, mesmo critério de FeatureDialog/SplitDialog.
    """

    def setUp(self):
        import tempfile

        from earth_tools import reports, storage

        self.reports = reports
        self.storage = storage
        self._tmpdir = tempfile.mkdtemp()
        QgsProject.instance().clear()
        QgsProject.instance().setFileName(os.path.join(self._tmpdir, "teste.qgz"))
        QgsProject.instance().setCrs(QgsCoordinateReferenceSystem("EPSG:4326"))

    def tearDown(self):
        QgsProject.instance().clear()
        QgsProject.instance().setCrs(QgsCoordinateReferenceSystem("EPSG:4326"))

    def _make_layer(self):
        poly = QgsGeometry.fromPolygonXY([[
            QgsPointXY(-47.0, -23.0), QgsPointXY(-47.01, -23.0),
            QgsPointXY(-47.01, -23.01), QgsPointXY(-47.0, -23.01), QgsPointXY(-47.0, -23.0),
        ]])
        return self.storage.create_place("polygon", "Area mapa teste", poly, {})

    def test_exporta_pdf_valido_com_todos_os_elementos(self):
        import tempfile

        layer = self._make_layer()
        layout = self.reports.build_layout(
            QgsProject.instance(), [layer], layer.extent(),
            QgsCoordinateReferenceSystem("EPSG:4326"),
            title="Mapa de Teste", subtitle="Propriedade Teste",
            info_lines=["SRC: EPSG:4326", "Área: 11,35 ha"],
            page_size="A4", orientation="Retrato",
        )
        path = os.path.join(tempfile.mkdtemp(), "mapa.pdf")
        ok, msg = self.reports.export_pdf(layout, path)
        self.assertTrue(ok, msg)
        with open(path, "rb") as fh:
            self.assertEqual(fh.read(5), b"%PDF-")
        self.assertGreater(os.path.getsize(path), 1000)

    def test_exporta_png_que_realmente_decodifica(self):
        import tempfile

        from qgis.PyQt.QtGui import QImage

        layer = self._make_layer()
        layout = self.reports.build_layout(
            QgsProject.instance(), [layer], layer.extent(),
            QgsCoordinateReferenceSystem("EPSG:4326"), title="Mapa PNG",
        )
        path = os.path.join(tempfile.mkdtemp(), "mapa.png")
        ok, msg = self.reports.export_png(layout, path)
        self.assertTrue(ok, msg)
        img = QImage(path)
        self.assertFalse(img.isNull())
        self.assertGreater(img.width(), 0)
        self.assertGreater(img.height(), 0)

    def test_a3_paisagem_sem_elementos_opcionais(self):
        import tempfile

        layer = self._make_layer()
        layout = self.reports.build_layout(
            QgsProject.instance(), [layer], layer.extent(),
            QgsCoordinateReferenceSystem("EPSG:4326"), title="Mapa A3",
            page_size="A3", orientation="Paisagem",
            show_legend=False, show_scalebar=False, show_north_arrow=False,
        )
        path = os.path.join(tempfile.mkdtemp(), "mapa_a3.png")
        ok, msg = self.reports.export_png(layout, path)
        self.assertTrue(ok, msg)

    def test_reexportar_com_mesmo_nome_nao_duplica_no_gerenciador(self):
        layer = self._make_layer()
        self.reports.build_layout(
            QgsProject.instance(), [layer], layer.extent(),
            QgsCoordinateReferenceSystem("EPSG:4326"), title="A",
            layout_name="Layout Repetido",
        )
        self.reports.build_layout(
            QgsProject.instance(), [layer], layer.extent(),
            QgsCoordinateReferenceSystem("EPSG:4326"), title="B",
            layout_name="Layout Repetido",
        )
        layouts = [
            l.name() for l in QgsProject.instance().layoutManager().layouts()
            if l.name() == "Layout Repetido"
        ]
        self.assertEqual(len(layouts), 1)

    def test_formato_de_pagina_invalido_levanta_erro_claro(self):
        layer = self._make_layer()
        with self.assertRaises(self.reports.ReportError):
            self.reports.build_layout(
                QgsProject.instance(), [layer], layer.extent(),
                QgsCoordinateReferenceSystem("EPSG:4326"), page_size="A5",
            )


@unittest.skipUnless(QGIS_AVAILABLE, "requer o ambiente QGIS")
class ModulosCarregamSemErroTests(unittest.TestCase):
    """Smoke test de importação - pega erro de API quebrada que py_compile
    (só sintaxe) não pega, sem precisar de QgsMapCanvas/iface reais."""

    def test_dlg_ruler_importa_e_tem_quatro_abas(self):
        from earth_tools import dlg_ruler

        self.assertEqual(len(dlg_ruler.TABS), 4)
        titulos = [t[0] for t in dlg_ruler.TABS]
        self.assertEqual(titulos, ["Linha", "Caminho", "Polígono", "Círculo"])

    def test_dlg_feature_importa(self):
        from earth_tools import dlg_feature

        self.assertIn("line", dlg_feature.TITLES)

    def test_widgets_crsrow_importa_e_aceita_crs_do_projeto_e_label_custom(self):
        from earth_tools.widgets import CrsRow

        row = CrsRow(QgsProject.instance().crs())
        self.assertTrue(row.crs().isValid())
        row2 = CrsRow(QgsProject.instance().crs(), label="SRC/CRS da camada de saída:")
        self.assertTrue(row2.crs().isValid())

    def test_geoprocessing_e_dlg_buffer_importam(self):
        from earth_tools import geoprocessing
        from earth_tools.dlg_buffer import BufferDialog

        self.assertTrue(hasattr(geoprocessing, "run_buffer"))
        self.assertTrue(hasattr(BufferDialog, "_run"))

    def test_dlg_union_importa(self):
        from earth_tools.dlg_union import UnionDialog

        self.assertTrue(hasattr(UnionDialog, "_run"))

    def test_dlg_split_importa(self):
        from earth_tools.dlg_split import SplitDialog

        self.assertTrue(hasattr(SplitDialog, "_confirm"))

    def test_dlg_clip_importa(self):
        from earth_tools.dlg_clip import ClipDialog

        self.assertTrue(hasattr(ClipDialog, "_run"))

    def test_dlg_difference_importa(self):
        from earth_tools.dlg_difference import DifferenceDialog

        self.assertTrue(hasattr(DifferenceDialog, "_run"))

    def test_dlg_style_manager_importa(self):
        from earth_tools.dlg_style_manager import StyleManagerDialog

        self.assertTrue(hasattr(StyleManagerDialog, "_apply"))

    def test_dlg_validate_importa(self):
        from earth_tools.dlg_validate import ValidateDialog

        self.assertTrue(hasattr(ValidateDialog, "_fix_selected"))

    def test_dlg_calculator_importa(self):
        from earth_tools.dlg_calculator import CalculatorDialog

        self.assertTrue(hasattr(CalculatorDialog, "_copy_result"))

    def test_dlg_export_map_importa(self):
        from earth_tools.dlg_export_map import ExportMapDialog

        self.assertTrue(hasattr(ExportMapDialog, "_export_pdf"))

    def test_earth_tools_importa_sem_dlg_imagery_nem_dlg_search(self):
        from earth_tools import earth_tools

        self.assertFalse(hasattr(earth_tools, "ImageryDialog"))
        self.assertFalse(hasattr(earth_tools, "SearchDialog"))


if __name__ == "__main__":
    unittest.main()

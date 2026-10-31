# -*- coding: utf-8 -*-
"""Testes de kml_io.py - parse/serializacao de KML/KMZ, sem PyQGIS.

Cobre a maior parte dos cenarios pedidos na Fase D que NAO dependem de
criar uma camada real no QGIS: importar marcadores/linhas/poligonos,
pastas aninhadas, KMZ, nomes/descricoes, estilos, arquivo invalido,
elementos nao suportados, geometria multipla, e o ciclo exportar->
reimportar (round trip).
"""

import os
import sys
import unittest
import zipfile
from io import BytesIO

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import kml_io  # noqa: E402


def _kml(body):
    return (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<kml xmlns="http://www.opengis.net/kml/2.2">{}</kml>'
    ).format(body)


class ColorConversionTests(unittest.TestCase):
    def test_kml_para_rgba_ordem_invertida(self):
        # aabbggrr: alfa=ff, azul=00, verde=00, vermelho=ff -> vermelho opaco
        self.assertEqual(kml_io.kml_color_to_rgba("ff0000ff"), "255,0,0,255")

    def test_rgba_para_kml_e_o_inverso(self):
        self.assertEqual(kml_io.rgba_to_kml_color("255,0,0,255"), "ff0000ff")

    def test_ida_e_volta_preserva_a_cor(self):
        original = "120,200,30,180"
        self.assertEqual(
            kml_io.kml_color_to_rgba(kml_io.rgba_to_kml_color(original)), original
        )

    def test_valor_invalido_devolve_none(self):
        self.assertIsNone(kml_io.kml_color_to_rgba("nao-e-uma-cor"))

    def test_valor_ausente_devolve_none(self):
        self.assertIsNone(kml_io.kml_color_to_rgba(""))
        self.assertIsNone(kml_io.kml_color_to_rgba(None))


class ParsePlacemarksTests(unittest.TestCase):
    def test_marcador_simples(self):
        data = _kml(
            "<Placemark><name>Casa</name><description>Minha casa</description>"
            "<Point><coordinates>-46.65,-23.56,0</coordinates></Point></Placemark>"
        )
        folder, unsupported = kml_io.parse_kml(data)
        self.assertEqual(len(folder["placemarks"]), 1)
        p = folder["placemarks"][0]
        self.assertEqual(p["name"], "Casa")
        self.assertEqual(p["description"], "Minha casa")
        self.assertEqual(len(p["geometries"]), 1)
        self.assertEqual(p["geometries"][0]["kind"], "point")
        self.assertEqual(p["geometries"][0]["rings"], [[(-46.65, -23.56)]])
        self.assertEqual(unsupported, [])

    def test_linha(self):
        data = _kml(
            "<Placemark><name>Trilha</name>"
            "<LineString><coordinates>-46.0,-23.0,0 -46.1,-23.1,0 -46.2,-23.2,0"
            "</coordinates></LineString></Placemark>"
        )
        folder, _ = kml_io.parse_kml(data)
        geom = folder["placemarks"][0]["geometries"][0]
        self.assertEqual(geom["kind"], "line")
        self.assertEqual(len(geom["rings"][0]), 3)

    def test_poligono_com_buraco(self):
        data = _kml(
            "<Placemark><name>Area</name><Polygon>"
            "<outerBoundaryIs><LinearRing><coordinates>"
            "0,0,0 10,0,0 10,10,0 0,10,0 0,0,0"
            "</coordinates></LinearRing></outerBoundaryIs>"
            "<innerBoundaryIs><LinearRing><coordinates>"
            "2,2,0 4,2,0 4,4,0 2,4,0 2,2,0"
            "</coordinates></LinearRing></innerBoundaryIs>"
            "</Polygon></Placemark>"
        )
        folder, _ = kml_io.parse_kml(data)
        geom = folder["placemarks"][0]["geometries"][0]
        self.assertEqual(geom["kind"], "polygon")
        self.assertEqual(len(geom["rings"]), 2)  # externo + 1 buraco
        self.assertEqual(len(geom["rings"][0]), 5)
        self.assertEqual(len(geom["rings"][1]), 5)

    def test_multigeometry_gera_varias_geometrias(self):
        data = _kml(
            "<Placemark><name>Varios</name><MultiGeometry>"
            "<Point><coordinates>0,0,0</coordinates></Point>"
            "<Point><coordinates>1,1,0</coordinates></Point>"
            "</MultiGeometry></Placemark>"
        )
        folder, _ = kml_io.parse_kml(data)
        self.assertEqual(len(folder["placemarks"][0]["geometries"]), 2)

    def test_coordenada_fora_do_intervalo_e_descartada(self):
        data = _kml(
            "<Placemark><name>Ruim</name>"
            "<LineString><coordinates>0,0,0 999,999,0 1,1,0</coordinates></LineString>"
            "</Placemark>"
        )
        folder, _ = kml_io.parse_kml(data)
        geom = folder["placemarks"][0]["geometries"][0]
        self.assertEqual(geom["rings"][0], [(0.0, 0.0), (1.0, 1.0)])

    def test_placemark_sem_geometria_e_ignorado(self):
        data = _kml("<Placemark><name>Vazio</name></Placemark>")
        folder, _ = kml_io.parse_kml(data)
        self.assertEqual(folder["placemarks"], [])


class ParseFoldersTests(unittest.TestCase):
    def test_pastas_aninhadas(self):
        data = _kml(
            "<Document><name>Fazenda</name>"
            "<Folder><name>APP</name>"
            "<Folder><name>Nascente 1</name>"
            "<Placemark><name>P1</name><Point><coordinates>0,0,0</coordinates></Point>"
            "</Placemark>"
            "</Folder></Folder>"
            "</Document>"
        )
        folder, _ = kml_io.parse_kml(data)
        self.assertEqual(folder["name"], "Fazenda")
        app = folder["folders"][0]
        self.assertEqual(app["name"], "APP")
        nascente = app["folders"][0]
        self.assertEqual(nascente["name"], "Nascente 1")
        self.assertEqual(len(nascente["placemarks"]), 1)

    def test_iter_placemarks_devolve_caminho_a_partir_da_raiz_analisada(self):
        # parse_kml devolve como raiz o primeiro Folder/Document encontrado
        # (aqui, "A"); o caminho de iter_placemarks e relativo a essa raiz,
        # nao inclui o nome dela mesma - so dos descendentes.
        data = _kml(
            "<Folder><name>A</name><Folder><name>B</name>"
            "<Placemark><name>P</name><Point><coordinates>0,0,0</coordinates></Point>"
            "</Placemark></Folder></Folder>"
        )
        folder, _ = kml_io.parse_kml(data)
        self.assertEqual(folder["name"], "A")
        items = list(kml_io.iter_placemarks(folder))
        self.assertEqual(len(items), 1)
        path, placemark = items[0]
        self.assertEqual(path, ("B",))
        self.assertEqual(placemark["name"], "P")

    def test_count_placemarks_soma_subpastas(self):
        data = _kml(
            "<Folder><name>Raiz</name>"
            "<Placemark><name>P1</name><Point><coordinates>0,0,0</coordinates></Point></Placemark>"
            "<Folder><name>Sub</name>"
            "<Placemark><name>P2</name><Point><coordinates>1,1,0</coordinates></Point></Placemark>"
            "</Folder></Folder>"
        )
        folder, _ = kml_io.parse_kml(data)
        self.assertEqual(kml_io.count_placemarks(folder), 2)


class StyleTests(unittest.TestCase):
    def test_estilo_por_styleurl(self):
        data = _kml(
            "<Document>"
            "<Style id=\"linha_vermelha\"><LineStyle><color>ff0000ff</color>"
            "<width>3</width></LineStyle></Style>"
            "<Placemark><name>P</name><styleUrl>#linha_vermelha</styleUrl>"
            "<LineString><coordinates>0,0,0 1,1,0</coordinates></LineString>"
            "</Placemark></Document>"
        )
        folder, _ = kml_io.parse_kml(data)
        style = folder["placemarks"][0]["geometries"][0]["style"]
        self.assertEqual(style.get("line_color"), "255,0,0,255")
        self.assertEqual(style.get("line_width"), 3.0)

    def test_estilo_inline_tem_prioridade_sobre_styleurl(self):
        data = _kml(
            "<Document>"
            "<Style id=\"base\"><LineStyle><color>ff0000ff</color></LineStyle></Style>"
            "<Placemark><name>P</name><styleUrl>#base</styleUrl>"
            "<Style><LineStyle><color>ff00ff00</color></LineStyle></Style>"
            "<LineString><coordinates>0,0,0 1,1,0</coordinates></LineString>"
            "</Placemark></Document>"
        )
        folder, _ = kml_io.parse_kml(data)
        style = folder["placemarks"][0]["geometries"][0]["style"]
        self.assertEqual(style.get("line_color"), "0,255,0,255")

    def test_stylemap_usa_o_par_normal(self):
        data = _kml(
            "<Document>"
            "<Style id=\"n\"><PolyStyle><color>ff0000ff</color></PolyStyle></Style>"
            "<Style id=\"h\"><PolyStyle><color>ff00ff00</color></PolyStyle></Style>"
            "<StyleMap id=\"mapa\">"
            "<Pair><key>normal</key><styleUrl>#n</styleUrl></Pair>"
            "<Pair><key>highlight</key><styleUrl>#h</styleUrl></Pair>"
            "</StyleMap>"
            "<Placemark><name>P</name><styleUrl>#mapa</styleUrl>"
            "<Polygon><outerBoundaryIs><LinearRing><coordinates>"
            "0,0,0 1,0,0 1,1,0 0,0,0</coordinates></LinearRing></outerBoundaryIs>"
            "</Polygon></Placemark></Document>"
        )
        folder, _ = kml_io.parse_kml(data)
        style = folder["placemarks"][0]["geometries"][0]["style"]
        self.assertEqual(style.get("fill_color"), "255,0,0,255")


    def test_icon_href_e_extraido_do_iconstyle(self):
        data = _kml(
            "<Document>"
            "<Style id=\"icone\"><IconStyle><Icon>"
            "<href>files/marcador.png</href></Icon></IconStyle></Style>"
            "<Placemark><name>P</name><styleUrl>#icone</styleUrl>"
            "<Point><coordinates>0,0,0</coordinates></Point></Placemark>"
            "</Document>"
        )
        folder, _ = kml_io.parse_kml(data)
        style = folder["placemarks"][0]["geometries"][0]["style"]
        self.assertEqual(style.get("icon_href"), "files/marcador.png")


class UnsupportedAndInvalidTests(unittest.TestCase):
    def test_elemento_desconhecido_e_reportado_sem_travar(self):
        data = _kml(
            "<Folder><name>F</name>"
            "<NetworkLink><name>Externo</name></NetworkLink>"
            "<Placemark><name>P</name><Point><coordinates>0,0,0</coordinates></Point>"
            "</Placemark></Folder>"
        )
        folder, unsupported = kml_io.parse_kml(data)
        self.assertIn("NetworkLink", unsupported)
        self.assertEqual(len(folder["placemarks"]), 1)

    def test_xml_malformado_lanca_kmlerror(self):
        with self.assertRaises(kml_io.KmlError):
            kml_io.parse_kml(b"<kml><Document><Placemark>")

    def test_kmz_que_nao_e_zip_lanca_kmlerror(self):
        with self.assertRaises(kml_io.KmlError):
            kml_io.parse_kmz(b"isto nao e um zip")

    def test_kmz_sem_kml_dentro_lanca_kmlerror(self):
        buf = BytesIO()
        with zipfile.ZipFile(buf, "w") as zf:
            zf.writestr("leia.txt", "nada de kml aqui")
        with self.assertRaises(kml_io.KmlError):
            kml_io.parse_kmz(buf.getvalue())


class KmzTests(unittest.TestCase):
    def test_kmz_com_doc_kml_e_assets(self):
        kml_text = _kml(
            "<Placemark><name>P</name><Point><coordinates>0,0,0</coordinates></Point>"
            "</Placemark>"
        )
        buf = BytesIO()
        with zipfile.ZipFile(buf, "w") as zf:
            zf.writestr("doc.kml", kml_text)
            zf.writestr("files/icone.png", b"conteudo-fake-de-imagem")
        folder, unsupported, assets = kml_io.parse_kmz(buf.getvalue())
        self.assertEqual(len(folder["placemarks"]), 1)
        self.assertIn("files/icone.png", assets)
        self.assertEqual(assets["files/icone.png"], b"conteudo-fake-de-imagem")

    def test_load_file_detecta_kmz_pela_assinatura_mesmo_com_extensao_kml(self):
        import tempfile

        kml_text = _kml(
            "<Placemark><name>P</name><Point><coordinates>0,0,0</coordinates></Point>"
            "</Placemark>"
        )
        buf = BytesIO()
        with zipfile.ZipFile(buf, "w") as zf:
            zf.writestr("doc.kml", kml_text)
        with tempfile.NamedTemporaryFile(suffix=".kml", delete=False) as f:
            f.write(buf.getvalue())
            path = f.name
        try:
            folder, unsupported, assets = kml_io.load_file(path)
            self.assertEqual(len(folder["placemarks"]), 1)
        finally:
            os.remove(path)

    def test_load_file_arquivo_vazio_lanca_kmlerror(self):
        import tempfile

        with tempfile.NamedTemporaryFile(suffix=".kml", delete=False) as f:
            path = f.name
        try:
            with self.assertRaises(kml_io.KmlError):
                kml_io.load_file(path)
        finally:
            os.remove(path)


class FingerprintTests(unittest.TestCase):
    def test_mesma_entrada_mesmo_fingerprint(self):
        a = kml_io.fingerprint("point", "Casa", [[(-46.65, -23.56)]])
        b = kml_io.fingerprint("point", "Casa", [[(-46.65, -23.56)]])
        self.assertEqual(a, b)

    def test_nome_diferente_fingerprint_diferente(self):
        a = kml_io.fingerprint("point", "Casa", [[(-46.65, -23.56)]])
        b = kml_io.fingerprint("point", "Outra", [[(-46.65, -23.56)]])
        self.assertNotEqual(a, b)

    def test_ruido_de_ponto_flutuante_nao_muda_o_fingerprint(self):
        a = kml_io.fingerprint("point", "Casa", [[(-46.6500000, -23.5600000)]])
        b = kml_io.fingerprint("point", "Casa", [[(-46.65000001, -23.55999999)]])
        self.assertEqual(a, b)


class RoundTripTests(unittest.TestCase):
    def test_exportar_e_reimportar_preserva_nome_descricao_e_coordenada(self):
        folder = {
            "name": "Raiz",
            "folders": [],
            "placemarks": [
                {
                    "name": "Sede",
                    "description": "Casa principal",
                    "geometries": [
                        {
                            "kind": "point",
                            "rings": [[(-46.123456, -23.654321)]],
                            "style": {"line_color": "255,0,0,255"},
                        }
                    ],
                }
            ],
        }
        kml_text = kml_io.build_kml(folder)
        reparsed, unsupported = kml_io.parse_kml(kml_text)
        self.assertEqual(unsupported, [])
        p = reparsed["placemarks"][0]
        self.assertEqual(p["name"], "Sede")
        self.assertEqual(p["description"], "Casa principal")
        lon, lat = p["geometries"][0]["rings"][0][0]
        self.assertAlmostEqual(lon, -46.123456, places=6)
        self.assertAlmostEqual(lat, -23.654321, places=6)

    def test_exportar_poligono_com_buraco_preserva_aneis(self):
        folder = {
            "name": "Raiz",
            "folders": [],
            "placemarks": [
                {
                    "name": "Area",
                    "description": "",
                    "geometries": [
                        {
                            "kind": "polygon",
                            "rings": [
                                [(0, 0), (10, 0), (10, 10), (0, 10), (0, 0)],
                                [(2, 2), (4, 2), (4, 4), (2, 4), (2, 2)],
                            ],
                            "style": {},
                        }
                    ],
                }
            ],
        }
        kml_text = kml_io.build_kml(folder)
        reparsed, _ = kml_io.parse_kml(kml_text)
        geom = reparsed["placemarks"][0]["geometries"][0]
        self.assertEqual(len(geom["rings"]), 2)

    def test_build_kmz_produz_zip_com_doc_kml(self):
        folder = {"name": "R", "folders": [], "placemarks": []}
        data = kml_io.build_kmz(folder)
        zf = zipfile.ZipFile(BytesIO(data))
        self.assertIn("doc.kml", zf.namelist())

    def test_pastas_aninhadas_sobrevivem_ao_ciclo_completo(self):
        folder = {
            "name": "Fazenda",
            "folders": [
                {
                    "name": "APP",
                    "folders": [],
                    "placemarks": [
                        {
                            "name": "P1",
                            "description": "",
                            "geometries": [
                                {"kind": "point", "rings": [[(0, 0)]], "style": {}}
                            ],
                        }
                    ],
                }
            ],
            "placemarks": [],
        }
        kml_text = kml_io.build_kml(folder)
        reparsed, _ = kml_io.parse_kml(kml_text)
        self.assertEqual(reparsed["folders"][0]["name"], "APP")
        self.assertEqual(len(reparsed["folders"][0]["placemarks"]), 1)

    def test_nomes_de_multigeometria_na_exportacao_sao_desambiguados(self):
        folder = {
            "name": "R",
            "folders": [],
            "placemarks": [
                {
                    "name": "Duplo",
                    "description": "",
                    "geometries": [
                        {"kind": "point", "rings": [[(0, 0)]], "style": {}},
                        {"kind": "point", "rings": [[(1, 1)]], "style": {}},
                    ],
                }
            ],
        }
        kml_text = kml_io.build_kml(folder)
        reparsed, _ = kml_io.parse_kml(kml_text)
        names = sorted(p["name"] for p in reparsed["placemarks"])
        self.assertEqual(names, ["Duplo (1)", "Duplo (2)"])


if __name__ == "__main__":
    unittest.main()

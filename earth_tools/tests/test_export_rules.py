# -*- coding: utf-8 -*-
"""Testes de export_rules.py - percurso de árvore para exportação, sem
PyQGIS. Reproduz a forma do bug relatado na 0.11.0: itens presentes na
árvore (aqui, objetos Fake*) devem aparecer no resultado mesmo sem
depender de nenhuma tabela de cache - a função nunca recebe uma tabela de
membership, só a árvore em si, então "esquecer de atualizar o cache" não
é um jeito possível de o teste passar escondendo o bug.
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import export_rules  # noqa: E402


class FakeLayer(object):
    """Simula uma camada de lugar: name_of()/export_one() atuam sobre ela."""

    def __init__(self, name, kind="point", broken=False):
        self.name = name
        self.kind = kind
        self.broken = broken

    def export(self):
        if self.broken:
            raise RuntimeError("falha simulada de leitura de geometria")
        return {
            "placemarks": [
                {"name": self.name, "description": "", "geometries": [{"kind": self.kind, "rings": [[(0, 0)]], "style": {}}]}
            ]
        }


class FakeGroup(object):
    """Simula uma pasta (QgsLayerTreeGroup): children = mistura de
    FakeLayer e FakeGroup, exatamente como na árvore real do QGIS."""

    def __init__(self, name, children=None, outsider_names=()):
        self.name = name
        self.children = list(children or [])
        # Nomes que, se aparecerem como FakeLayer, representam camadas QUE
        # NAO sao lugares do plugin (ex.: uma camada base qualquer) - para
        # testar que is_place_layer filtra corretamente.
        self.outsider_names = set(outsider_names)


def _callbacks():
    def name_of(node):
        return node.name

    def children_of(node):
        return node.children

    def is_group(node):
        return isinstance(node, FakeGroup)

    def is_place_layer(node):
        return node.name not in _CURRENT_OUTSIDERS

    def export_one(node):
        return node.export()

    return name_of, children_of, is_group, is_place_layer, export_one


_CURRENT_OUTSIDERS = set()


def _collect(root, include_subfolders=True, outsiders=()):
    global _CURRENT_OUTSIDERS
    _CURRENT_OUTSIDERS = set(outsiders)
    name_of, children_of, is_group, is_place_layer, export_one = _callbacks()
    return export_rules.collect_tree(
        root, name_of, children_of, is_group, is_place_layer, export_one, include_subfolders
    )


class CollectTreeTests(unittest.TestCase):
    def test_pasta_com_um_marcador(self):
        root = FakeGroup("Pasta", [FakeLayer("Casa", "point")])
        tree, errors = _collect(root)
        self.assertEqual(errors, [])
        self.assertEqual(len(tree["placemarks"]), 1)
        self.assertEqual(tree["placemarks"][0]["name"], "Casa")

    def test_pasta_com_uma_linha(self):
        root = FakeGroup("Pasta", [FakeLayer("Trilha", "line")])
        tree, _ = _collect(root)
        self.assertEqual(tree["placemarks"][0]["geometries"][0]["kind"], "line")

    def test_pasta_com_um_poligono(self):
        root = FakeGroup("Pasta", [FakeLayer("Área", "polygon")])
        tree, _ = _collect(root)
        self.assertEqual(tree["placemarks"][0]["geometries"][0]["kind"], "polygon")

    def test_pasta_com_varios_tipos_de_feicao(self):
        root = FakeGroup(
            "Pasta",
            [FakeLayer("Casa", "point"), FakeLayer("Trilha", "line"), FakeLayer("Área", "polygon")],
        )
        tree, errors = _collect(root)
        self.assertEqual(errors, [])
        nomes = sorted(p["name"] for p in tree["placemarks"])
        self.assertEqual(nomes, sorted(["Casa", "Trilha", "Área"]))

    def test_subpastas_aninhadas_sao_percorridas_recursivamente(self):
        neto = FakeGroup("Nascente 1", [FakeLayer("Ponto de água", "point")])
        filho = FakeGroup("APP", [neto])
        root = FakeGroup("Fazenda", [filho])
        tree, errors = _collect(root)
        self.assertEqual(errors, [])
        self.assertEqual(tree["placemarks"], [])
        self.assertEqual(tree["folders"][0]["name"], "APP")
        self.assertEqual(tree["folders"][0]["folders"][0]["name"], "Nascente 1")
        self.assertEqual(
            tree["folders"][0]["folders"][0]["placemarks"][0]["name"], "Ponto de água"
        )

    def test_pasta_que_so_tem_subpastas_ainda_traz_o_conteudo_delas(self):
        sub = FakeGroup("Sub", [FakeLayer("P1")])
        root = FakeGroup("Raiz", [sub])
        tree, _ = _collect(root)
        self.assertEqual(tree["placemarks"], [])
        self.assertEqual(len(tree["folders"]), 1)
        self.assertFalse(export_rules.is_empty(tree))

    def test_pasta_vazia_de_verdade(self):
        root = FakeGroup("Pasta", [])
        tree, errors = _collect(root)
        self.assertEqual(errors, [])
        self.assertTrue(export_rules.is_empty(tree))

    def test_sem_subpastas_quando_include_subfolders_e_falso(self):
        sub = FakeGroup("Sub", [FakeLayer("Escondido")])
        root = FakeGroup("Raiz", [FakeLayer("Visivel"), sub])
        tree, _ = _collect(root, include_subfolders=False)
        self.assertEqual(tree["folders"], [])
        self.assertEqual(len(tree["placemarks"]), 1)
        self.assertEqual(tree["placemarks"][0]["name"], "Visivel")

    def test_camada_que_nao_e_lugar_do_plugin_e_ignorada(self):
        root = FakeGroup("Pasta", [FakeLayer("Base cartográfica"), FakeLayer("Marco")])
        tree, _ = _collect(root, outsiders={"Base cartográfica"})
        nomes = [p["name"] for p in tree["placemarks"]]
        self.assertEqual(nomes, ["Marco"])

    def test_falha_ao_exportar_um_item_nao_interrompe_os_outros(self):
        root = FakeGroup(
            "Pasta",
            [FakeLayer("Bom1"), FakeLayer("Quebrado", broken=True), FakeLayer("Bom2")],
        )
        tree, errors = _collect(root)
        nomes = sorted(p["name"] for p in tree["placemarks"])
        self.assertEqual(nomes, ["Bom1", "Bom2"])
        self.assertEqual(len(errors), 1)
        self.assertEqual(errors[0][0], "Quebrado")
        self.assertIn("falha simulada", errors[0][1])

    def test_nao_depende_de_nenhuma_tabela_de_cache(self):
        # Reproducao direta da forma do bug relatado: itens presentes na
        # arvore (aqui, a unica fonte de dados que este modulo conhece)
        # aparecem no resultado - nao ha como "esquecer de atualizar um
        # cache" aqui, porque a funcao nunca recebe um cache.
        root = FakeGroup(
            "Nova pasta",
            [FakeLayer("Marcador 1"), FakeLayer("Caminho 1", "line"), FakeLayer("Polígono 1", "polygon")],
        )
        tree, errors = _collect(root)
        self.assertEqual(errors, [])
        self.assertEqual(len(tree["placemarks"]), 3)
        self.assertFalse(export_rules.is_empty(tree))


class IsEmptyTests(unittest.TestCase):
    def test_arvore_com_placemark_nao_e_vazia(self):
        tree = {"name": "x", "placemarks": [{"name": "p"}], "folders": []}
        self.assertFalse(export_rules.is_empty(tree))

    def test_arvore_so_com_subpasta_vazia_e_vazia(self):
        tree = {
            "name": "x",
            "placemarks": [],
            "folders": [{"name": "y", "placemarks": [], "folders": []}],
        }
        self.assertTrue(export_rules.is_empty(tree))

    def test_arvore_com_placemark_em_subpasta_nao_e_vazia(self):
        tree = {
            "name": "x",
            "placemarks": [],
            "folders": [{"name": "y", "placemarks": [{"name": "p"}], "folders": []}],
        }
        self.assertFalse(export_rules.is_empty(tree))


if __name__ == "__main__":
    unittest.main()

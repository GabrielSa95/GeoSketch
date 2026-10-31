# -*- coding: utf-8 -*-
"""Testes da lógica pura de hierarquia de pastas (Fase B).

Roda com `python -m unittest` puro, sem depender do PyQGIS - igual a
test_geometry_rules.py. folder_rules.py só manipula dicts/listas simples.
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import folder_rules  # noqa: E402


def _pasta(nome, pai_id="", modelo=""):
    return {"nome": nome, "pai_id": pai_id, "modelo": modelo, "visivel": True}


class ResolutionOrderTests(unittest.TestCase):
    def test_pastas_de_raiz_resolvem_direto(self):
        folders = {"a": _pasta("A"), "b": _pasta("B")}
        order = folder_rules.resolution_order(folders)
        self.assertEqual(set(order), {"a", "b"})

    def test_filho_vem_depois_do_pai(self):
        folders = {"pai": _pasta("Pai"), "filho": _pasta("Filho", pai_id="pai")}
        order = folder_rules.resolution_order(folders)
        self.assertEqual(order.index("pai"), 0)
        self.assertEqual(order.index("filho"), 1)

    def test_tres_niveis_mantem_a_ordem(self):
        folders = {
            "neto": _pasta("Neto", pai_id="filho"),
            "pai": _pasta("Pai"),
            "filho": _pasta("Filho", pai_id="pai"),
        }
        order = folder_rules.resolution_order(folders)
        self.assertLess(order.index("pai"), order.index("filho"))
        self.assertLess(order.index("filho"), order.index("neto"))

    def test_pai_id_orfao_e_tratado_como_raiz(self):
        # pai_id aponta para algo que nao existe em `folders`.
        folders = {"solta": _pasta("Solta", pai_id="nao-existe")}
        order = folder_rules.resolution_order(folders)
        self.assertEqual(order, ["solta"])

    def test_ciclo_fica_de_fora_sem_travar(self):
        # a eh pai de b, b eh pai de a: nenhum dos dois se resolve nunca.
        folders = {"a": _pasta("A", pai_id="b"), "b": _pasta("B", pai_id="a")}
        order = folder_rules.resolution_order(folders)
        self.assertEqual(order, [])

    def test_ciclo_parcial_nao_impede_o_resto(self):
        folders = {
            "raiz": _pasta("Raiz"),
            "a": _pasta("A", pai_id="b"),
            "b": _pasta("B", pai_id="a"),
        }
        order = folder_rules.resolution_order(folders)
        self.assertEqual(order, ["raiz"])

    def test_dict_vazio(self):
        self.assertEqual(folder_rules.resolution_order({}), [])


class BuildFolderChoicesTests(unittest.TestCase):
    def test_primeira_opcao_e_sempre_raiz(self):
        options = folder_rules.build_folder_choices({})
        self.assertEqual(options[0][0], "")

    def test_filhos_aparecem_indentados_depois_do_pai(self):
        folders = {"pai": _pasta("Pai"), "filho": _pasta("Filho", pai_id="pai")}
        options = folder_rules.build_folder_choices(folders)
        labels = dict(options)
        self.assertIn("Pai", labels["pai"])
        self.assertTrue(labels["filho"].startswith("    "))
        # pai aparece antes do filho na lista.
        ids = [fid for fid, _ in options]
        self.assertLess(ids.index("pai"), ids.index("filho"))

    def test_ordem_alfabetica_entre_irmaos(self):
        folders = {"z": _pasta("Zebra"), "a": _pasta("Abacate")}
        options = folder_rules.build_folder_choices(folders)
        ids_na_ordem = [fid for fid, _ in options if fid]
        self.assertEqual(ids_na_ordem, ["a", "z"])

    def test_pasta_em_ciclo_nao_aparece_na_lista(self):
        folders = {"a": _pasta("A", pai_id="b"), "b": _pasta("B", pai_id="a")}
        options = folder_rules.build_folder_choices(folders)
        ids = [fid for fid, _ in options]
        self.assertEqual(ids, [""])  # so a opcao de raiz


class FindPropertyRootTests(unittest.TestCase):
    def test_acha_a_raiz_a_partir_de_uma_subpasta(self):
        folders = {
            "fazenda": _pasta("Fazenda X", modelo="propriedade_rural"),
            "app": _pasta("APP", pai_id="fazenda", modelo="app"),
        }
        self.assertEqual(folder_rules.find_property_root(folders, "app"), "fazenda")

    def test_a_propria_pasta_ja_e_a_raiz(self):
        folders = {"fazenda": _pasta("Fazenda X", modelo="propriedade_rural")}
        self.assertEqual(folder_rules.find_property_root(folders, "fazenda"), "fazenda")

    def test_pasta_fora_de_qualquer_propriedade_devolve_none(self):
        folders = {"solta": _pasta("Solta")}
        self.assertIsNone(folder_rules.find_property_root(folders, "solta"))

    def test_folder_id_desconhecido_devolve_none(self):
        folders = {"fazenda": _pasta("Fazenda X", modelo="propriedade_rural")}
        self.assertIsNone(folder_rules.find_property_root(folders, "nao-existe"))

    def test_ciclo_nao_trava_e_devolve_none(self):
        folders = {"a": _pasta("A", pai_id="b"), "b": _pasta("B", pai_id="a")}
        self.assertIsNone(folder_rules.find_property_root(folders, "a"))

    def test_subpasta_profunda_sobe_varios_niveis(self):
        folders = {
            "fazenda": _pasta("Fazenda X", modelo="propriedade_rural"),
            "reserva": _pasta("Reserva Legal", pai_id="fazenda", modelo="reserva_legal"),
            "nascente_1": _pasta("Nascente 1", pai_id="reserva"),
        }
        self.assertEqual(folder_rules.find_property_root(folders, "nascente_1"), "fazenda")


if __name__ == "__main__":
    unittest.main()

# -*- coding: utf-8 -*-
"""Testes da lógica pura de conversão de unidade/azimute (Fase C).

Roda com `python -m unittest` puro, sem depender do PyQGIS, igual a
test_geometry_rules.py e test_folder_rules.py.
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import measure_rules  # noqa: E402

# Mesmo formato de utils.LENGTH_UNITS (nome, fator METROS->unidade), mas
# copiado aqui como tabela de teste - este módulo não importa utils.py de
# propósito (utils.py depende do PyQGIS).
LENGTH_UNITS = [
    ("Metros", 1.0),
    ("Quilômetros", 0.001),
    ("Pés", 3.280839895013123),
]


class ToMetersTests(unittest.TestCase):
    def test_metros_para_metros_e_identidade(self):
        self.assertAlmostEqual(measure_rules.to_meters(10.0, "Metros", LENGTH_UNITS), 10.0)

    def test_quilometros_para_metros(self):
        self.assertAlmostEqual(measure_rules.to_meters(2.5, "Quilômetros", LENGTH_UNITS), 2500.0)

    def test_pes_para_metros_e_inverso_de_metros_para_pes(self):
        pes = 100.0
        metros = measure_rules.to_meters(pes, "Pés", LENGTH_UNITS)
        # ida e volta: metros -> pes usando o mesmo fator da tabela.
        fator = dict(LENGTH_UNITS)["Pés"]
        self.assertAlmostEqual(metros * fator, pes, places=6)

    def test_unidade_desconhecida_devolve_valor_sem_conversao(self):
        self.assertEqual(measure_rules.to_meters(42.0, "Luas", LENGTH_UNITS), 42.0)

    def test_zero_e_identidade(self):
        self.assertEqual(measure_rules.to_meters(0.0, "Metros", LENGTH_UNITS), 0.0)


class NormalizeAzimuthTests(unittest.TestCase):
    def test_dentro_do_intervalo_fica_igual(self):
        self.assertEqual(measure_rules.normalize_azimuth(90.0), 90.0)

    def test_360_normaliza_para_zero(self):
        self.assertEqual(measure_rules.normalize_azimuth(360.0), 0.0)

    def test_acima_de_360_enrola(self):
        self.assertAlmostEqual(measure_rules.normalize_azimuth(370.0), 10.0)

    def test_negativo_enrola_para_positivo(self):
        self.assertAlmostEqual(measure_rules.normalize_azimuth(-10.0), 350.0)

    def test_zero_fica_zero(self):
        self.assertEqual(measure_rules.normalize_azimuth(0.0), 0.0)


if __name__ == "__main__":
    unittest.main()

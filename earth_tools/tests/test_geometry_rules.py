# -*- coding: utf-8 -*-
"""Testes da lógica pura de contagem/remoção de vértices.

Roda com `python -m unittest` puro, sem depender do PyQGIS - por isso usa
tuplas (x, y) como pontos, em vez de QgsPointXY: o módulo testado só exige
que os pontos suportem == / !=, e tuplas já suportam isso nativamente.
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import geometry_rules  # noqa: E402


class UniqueCountTests(unittest.TestCase):
    def test_sem_repeticao(self):
        self.assertEqual(geometry_rules.unique_count([(0, 0), (1, 0), (1, 1)]), 3)

    def test_repeticao_consecutiva_conta_uma_vez(self):
        self.assertEqual(geometry_rules.unique_count([(0, 0), (0, 0), (1, 1)]), 2)

    def test_repeticao_nao_consecutiva_conta_as_duas(self):
        # clique em A, B, A de novo: nao sao consecutivos, entao contam 3.
        self.assertEqual(geometry_rules.unique_count([(0, 0), (1, 1), (0, 0)]), 3)

    def test_lista_vazia(self):
        self.assertEqual(geometry_rules.unique_count([]), 0)

    def test_todos_iguais(self):
        self.assertEqual(geometry_rules.unique_count([(0, 0)] * 5), 1)


class DedupConsecutiveTests(unittest.TestCase):
    def test_remove_so_repeticao_adjacente(self):
        pts = [(0, 0), (0, 0), (1, 1), (2, 2), (2, 2)]
        self.assertEqual(geometry_rules.dedup_consecutive(pts), [(0, 0), (1, 1), (2, 2)])

    def test_nao_remove_repeticao_distante(self):
        pts = [(0, 0), (1, 1), (0, 0)]
        self.assertEqual(geometry_rules.dedup_consecutive(pts), pts)

    def test_lista_vazia(self):
        self.assertEqual(geometry_rules.dedup_consecutive([]), [])


class CanRemoveVertexTests(unittest.TestCase):
    def test_linha_nao_pode_cair_abaixo_de_dois(self):
        self.assertFalse(geometry_rules.can_remove_vertex([(0, 0), (1, 1)], 0, minimum=2))

    def test_linha_pode_remover_com_sobra(self):
        pts = [(0, 0), (1, 1), (2, 2)]
        self.assertTrue(geometry_rules.can_remove_vertex(pts, 1, minimum=2))

    def test_poligono_nao_pode_cair_abaixo_de_tres(self):
        pts = [(0, 0), (1, 0), (1, 1)]
        self.assertFalse(geometry_rules.can_remove_vertex(pts, 2, minimum=3))

    def test_remover_vertice_duplicado_nao_conta_como_perda_real(self):
        # A, A, B, C: remover um dos A ainda deixa 3 distintos (A,B,C).
        pts = [(0, 0), (0, 0), (1, 0), (1, 1)]
        self.assertTrue(geometry_rules.can_remove_vertex(pts, 0, minimum=3))

    def test_indice_fora_do_intervalo(self):
        pts = [(0, 0), (1, 1), (2, 2)]
        self.assertFalse(geometry_rules.can_remove_vertex(pts, 5, minimum=2))
        self.assertFalse(geometry_rules.can_remove_vertex(pts, -1, minimum=2))


class UndoStackTests(unittest.TestCase):
    def test_undo_sem_historico_devolve_none(self):
        stack = geometry_rules.UndoStack()
        self.assertIsNone(stack.undo(current_points=[(0, 0)]))

    def test_redo_sem_historico_devolve_none(self):
        stack = geometry_rules.UndoStack()
        self.assertIsNone(stack.redo(current_points=[(0, 0)]))

    def test_push_depois_undo_restaura_estado_anterior(self):
        stack = geometry_rules.UndoStack()
        estado_a = [(0, 0), (1, 1)]
        stack.push(estado_a)
        estado_b = [(0, 0), (1, 1), (2, 2)]  # usuario adicionou um vertice
        self.assertEqual(stack.undo(current_points=estado_b), estado_a)

    def test_undo_depois_redo_volta_ao_estado_seguinte(self):
        stack = geometry_rules.UndoStack()
        estado_a = [(0, 0), (1, 1)]
        stack.push(estado_a)
        estado_b = [(0, 0), (1, 1), (2, 2)]
        voltou = stack.undo(current_points=estado_b)
        self.assertEqual(voltou, estado_a)
        refez = stack.redo(current_points=voltou)
        self.assertEqual(refez, estado_b)

    def test_novo_push_depois_de_undo_limpa_o_redo(self):
        # Desfazer uma acao e depois fazer uma acao DIFERENTE (nao um redo)
        # deve descartar o "futuro" antigo - padrao comum de undo/redo.
        stack = geometry_rules.UndoStack()
        estado_a = [(0, 0)]
        stack.push(estado_a)
        estado_b = [(0, 0), (1, 1)]
        stack.undo(current_points=estado_b)
        self.assertTrue(stack.can_redo())
        estado_c = [(0, 0), (9, 9)]  # acao nova, diferente de estado_b
        stack.push(estado_c)
        self.assertFalse(stack.can_redo())

    def test_pilha_limitada_por_max_depth(self):
        stack = geometry_rules.UndoStack(max_depth=3)
        for i in range(10):
            stack.push([(i, i)])
        # so os 3 mais recentes sobrevivem; desfazer 3 vezes esgota a pilha.
        for _ in range(3):
            self.assertTrue(stack.can_undo())
            stack.undo(current_points=[(99, 99)])
        self.assertFalse(stack.can_undo())

    def test_push_guarda_copia_independente(self):
        # Mutar a lista original depois do push nao deve afetar o snapshot.
        stack = geometry_rules.UndoStack()
        pontos = [(0, 0), (1, 1)]
        stack.push(pontos)
        pontos.append((2, 2))
        restaurado = stack.undo(current_points=pontos)
        self.assertEqual(restaurado, [(0, 0), (1, 1)])


if __name__ == "__main__":
    unittest.main()

# -*- coding: utf-8 -*-
"""Regras puras de conversão de unidade e azimute (Fase C / C2), sem
depender do PyQGIS - mesmo motivo de geometry_rules.py e folder_rules.py:
utils.py importa qgis.core no topo, o que impede testar isto fora do QGIS.

Não duplica os fatores de conversão: recebe a tabela (lista de
(nome, fator METROS->unidade), o mesmo formato de utils.LENGTH_UNITS) como
parâmetro, para as duas fontes nunca poderem ficar dessincronizadas.
"""


def to_meters(value, unit_label, length_units):
    """Converte `value` (na unidade unit_label) para metros, usando a
    tabela `length_units` no formato [(nome, fator_metros_para_unidade), ...].

    Unidade desconhecida ou fator zero: devolve o valor sem conversão,
    mesma defensividade de utils.convert_length/convert_area.
    """
    for name, factor in length_units:
        if name == unit_label and factor:
            return value / factor
    return value


def normalize_azimuth(degrees):
    """Normaliza um azimute para o intervalo [0, 360). Convenção: graus a
    partir do Norte geográfico, sentido horário - a mesma já usada no rumo
    da Régua (dlg_ruler.py) e em utils.circle_points."""
    return degrees % 360.0

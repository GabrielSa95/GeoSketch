# -*- coding: utf-8 -*-
"""Regra pura de percurso da árvore para exportação KML/KMZ, sem depender
do PyQGIS (correção da Fase D - mesmo motivo de geometry_rules.py,
folder_rules.py e measure_rules.py).

Causa raiz do bug corrigido aqui: a exportação lia só a tabela canônica de
pastas/lugares (places_model), que só é atualizada quando o usuário usa
"Mover para pasta..." ou salva o projeto. Um lugar criado pela barra de
ferramentas e arrastado visualmente para dentro de uma pasta nunca gerava
essa linha, e a exportação achava a pasta "vazia" mesmo com itens visíveis
na árvore. A correção lê a ÁRVORE VISÍVEL diretamente (fonte da verdade no
momento da exportação) em vez do cache - esta função é o percurso em si,
testável sem QGIS; kml_bridge.py só fornece os callbacks que sabem andar na
árvore real.
"""


def collect_tree(group, name_of, children_of, is_group, is_place_layer, export_one,
                  include_subfolders=True):
    """Percorre `group` (um nó de árvore - pasta ou raiz do projeto) e monta
    a árvore neutra no formato de kml_io (name/folders/placemarks).

    Callbacks (recebem um nó da árvore real, nunca são chamados aqui com
    valor nenhum fixo - isolam este módulo do PyQGIS):
      name_of(node) -> str
      children_of(node) -> lista de nós filhos
      is_group(node) -> bool (True = subpasta; False = item de camada)
      is_place_layer(node) -> bool, só chamado quando is_group(node) é False;
        filtra itens que não são lugares do plugin (outras camadas do projeto)
      export_one(node) -> dict no formato de kml_io.build_kml, com pelo
        menos a chave "placemarks" (lista) - normalmente o placemark daquele
        lugar. Pode levantar excecao: é capturada e reportada em `errors`,
        sem interromper o resto do percurso.

    Devolve (tree, errors): tree é a árvore neutra; errors é
    [(nome, motivo), ...] de itens que existiam mas falharam ao exportar -
    nunca descartados em silêncio.
    """
    tree = {"name": name_of(group), "folders": [], "placemarks": []}
    errors = []
    for child in children_of(group):
        if is_group(child):
            if not include_subfolders:
                continue
            sub_tree, sub_errors = collect_tree(
                child, name_of, children_of, is_group, is_place_layer, export_one,
                include_subfolders,
            )
            tree["folders"].append(sub_tree)
            errors.extend(sub_errors)
            continue
        if not is_place_layer(child):
            continue
        try:
            result = export_one(child)
        except Exception as exc:
            errors.append((name_of(child), str(exc)))
            continue
        if result:
            tree["placemarks"].extend(result.get("placemarks", []))
    return tree, errors


def is_empty(tree):
    """True se não há nenhum placemark em `tree` nem em nenhuma subpasta -
    usado para distinguir "pasta realmente vazia" de erro de leitura."""
    if tree["placemarks"]:
        return False
    return all(is_empty(sub) for sub in tree["folders"])

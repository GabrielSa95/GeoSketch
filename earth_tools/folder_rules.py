# -*- coding: utf-8 -*-
"""Regras puras de hierarquia de pastas, sem depender do PyQGIS.

Isoladas aqui pelo mesmo motivo de geometry_rules.py: places_model.py importa
qgis.core no topo do arquivo, o que impede testar sua lógica fora do QGIS.
As funções daqui só recebem/devolvem dicts e listas simples, então podem ser
testadas com `python -m unittest` puro.

`folders` em toda esta API é um dict {id: {"nome": str, "pai_id": str, ...}},
no mesmo formato devolvido por places_model.list_folders().
"""


def resolution_order(folders):
    """Ordem em que as pastas podem ser materializadas: cada pai_id não
    vazio só é resolvido depois do próprio pai já ter entrado na lista.

    - pai_id vazio ("") = pasta de raiz, resolvida de imediato.
    - pai_id que não existe em `folders` (órfão) é tratado como raiz.
    - pastas presas num ciclo (A é pai de B que é pai de A) nunca se
      resolvem e são DEIXADAS DE FORA do resultado, para quem for
      materializar a árvore não entrar em loop infinito nem travar o QGIS
      por causa de um dado corrompido.
    """
    order = []
    resolved = set()
    pending = dict(folders)
    limit = len(folders) + 1
    guard = 0
    while pending and guard <= limit:
        guard += 1
        progressed = False
        for fid in list(pending.keys()):
            pai_id = pending[fid].get("pai_id", "")
            if pai_id and pai_id in folders and pai_id not in resolved:
                continue  # espera o pai ser resolvido primeiro
            order.append(fid)
            resolved.add(fid)
            del pending[fid]
            progressed = True
        if not progressed:
            break
    return order


def find_property_root(folders, folder_id, property_model="propriedade_rural"):
    """Sobe pela cadeia de pai_id a partir de `folder_id` até achar uma
    pasta com modelo == `property_model` (a pasta-mãe criada por
    places_model.create_property_template) e devolve o id dela.

    Devolve None se `folder_id` não existir, se nenhum ancestral (incluindo
    a própria pasta) tiver esse modelo, ou se a cadeia estiver presa num
    ciclo - nesse último caso, assim como em resolution_order(), não
    trava: simplesmente para de subir e devolve None.
    """
    visited = set()
    current = folder_id
    while current and current in folders and current not in visited:
        visited.add(current)
        info = folders[current]
        if info.get("modelo") == property_model:
            return current
        current = info.get("pai_id", "")
    return None


def build_folder_choices(folders, root_label="(Sem pasta / raiz)", indent="    "):
    """[(id, "nome com indentação por profundidade")], pais antes dos
    filhos, para popular uma lista/combo de escolha de pasta.
    """
    options = [("", root_label)]
    visited = set()

    def walk(pai_id, depth):
        if depth > len(folders):
            return  # protecao extra contra ciclo, alem do `visited`
        children = sorted(
            (item for item in folders.items() if item[1].get("pai_id", "") == pai_id),
            key=lambda item: item[1].get("nome", "").lower(),
        )
        for fid, info in children:
            if fid in visited:
                continue
            visited.add(fid)
            options.append((fid, indent * depth + info.get("nome", "")))
            walk(fid, depth + 1)

    walk("", 0)
    return options

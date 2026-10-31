# Relatório da versão 0.9.0 — Ferramentas Terra

**Data de geração:** 2026-10-24.

## Confirmação recebida sobre a versão anterior (0.8.0)

Antes de iniciar esta fase, o usuário confirmou validação manual real no QGIS 3.44.15
para a 0.8.0: desenho, edição de vértices, Ctrl+Z/Ctrl+Y, gravação no GeoPackage,
navegação por coordenadas, ação "Ir para" e tela cheia funcionaram, e o complemento
carregou sem erro de metadados. Isso está registrado aqui porque o relatório da 0.8.0
havia sido escrito antes dessa confirmação chegar.

## Decisão de arquitetura (pedida explicitamente antes de implementar)

**Como as feições são registradas/exibidas hoje:** cada lugar é a única feição de uma
tabela própria dentro de `Meus Lugares.gpkg`, carregada como uma camada no painel
Camadas (`storage.create_place`). Pastas, até a 0.8.0, eram só `QgsLayerTreeGroup`
nativos do QGIS — existiam apenas enquanto o *projeto* fosse salvo; o GeoPackage nunca
sabia que "pastas" existiam.

**Decisão para a Fase B:** a hierarquia de pastas passou a ter uma fonte de verdade
própria, em duas tabelas sem geometria dentro do MESMO `Meus Lugares.gpkg`:

- `_ferramentas_terra_pastas` (id, nome, pai_id, modelo, visivel)
- `_ferramentas_terra_lugares` (tabela, pasta_id) — liga cada lugar à sua pasta pela
  chave estável `storage.table_name(layer)` (o nome da tabela do lugar, que não muda
  quando o lugar é renomeado).

A árvore de camadas do QGIS passou a ser só uma **visão** dessa hierarquia, não a fonte
dela — por isso a organização sobrevive mesmo se o usuário só fechar o QGIS sem salvar o
projeto. Nenhuma tabela de lugar existente foi alterada; as duas tabelas novas são
puramente aditivas no mesmo arquivo. Detalhe completo da decisão, com o raciocínio
inteiro, está no docstring de `places_model.py`.

## Resumo das funcionalidades implementadas

- Criação de pastas e subpastas persistentes (`places_model.create_folder`).
- Modelo reutilizável de propriedade rural: Sede, Área do Imóvel, APP, Reserva Legal,
  Nascentes, Outros (`places_model.create_property_template`).
- Mover lugar entre pastas por dois caminhos: menu "Mover para pasta..." (grava na hora)
  e arrastar-e-soltar nativo do QGIS na árvore (gravado no GeoPackage quando o projeto é
  salvo — ver limitação abaixo).
- Mostrar/ocultar pasta inteira e lugar individual: recurso nativo do QGIS (caixa de
  seleção na árvore), com o estado persistido na pasta.
- Exclusão de pasta (reaproveitando a confirmação já existente de `delete_selected`)
  agora também limpa o registro da pasta e de qualquer subpasta aninhada no GeoPackage,
  evitando dado órfão.
- Renomear pasta: recurso nativo do QGIS (duplo clique no grupo); sincronizado com o
  GeoPackage ao salvar o projeto.
- Pesquisa de lugares por nome com navegação direta até a feição (`dlg_search.py`).
- Sincronização em duas direções: `rebuild_layer_tree` (GeoPackage → árvore, ao abrir
  projeto) e `capture_layer_tree` (árvore → GeoPackage, ao salvar o projeto), cada uma
  deliberadamente limitada a nunca sobrescrever uma mudança recente do usuário nem opinar
  sobre grupos nativos que o plugin não criou.

## Arquivos modificados/criados

Novos: `places_model.py`, `folder_rules.py`, `dlg_search.py`, `dlg_move_folder.py`,
`icons/search.svg`, `tests/test_folder_rules.py`.
Modificados: `storage.py` (`table_name()` extraído), `utils.py` (`zoom_to_layer()`
compartilhado), `layeractions.py` (novas ações, limpeza na exclusão), `earth_tools.py`
(botão de pesquisa, ganchos de sincronização), `LEIAME.md`, `metadata.txt`.

## Testes automatizados executados e resultados

`python -m unittest discover -s tests` → **31/31 testes passaram**: os 20 anteriores
(regressão confirmada, nenhum ficou vermelho) + 11 novos em
`tests/test_folder_rules.py` — ordem de resolução de hierarquia (pai antes do filho,
órfão tratado como raiz, ciclo detectado e excluído sem travar) e montagem da lista de
escolha de pastas (indentação, ordem alfabética entre irmãos, ciclo não aparece).
`python -m py_compile` em todos os 18 módulos `.py` → sem erro de sintaxe.
Validação de `metadata.txt` via `configparser`: campos obrigatórios presentes,
`version=0.9.0`.

**O que não pôde ser automatizado:** toda a lógica que manipula `QgsLayerTreeGroup`,
`QgsVectorLayer` reais e o GeoPackage (bootstrap das tabelas de gerenciamento, criar
pasta de fato, mover nó na árvore, capturar/reconstruir) depende do PyQGIS, que não está
disponível neste ambiente de shell. Só a lógica pura de ordenação/hierarquia
(`folder_rules.py`) foi extraída de propósito para poder ser testada sem o QGIS — o
resto só é verificável no QGIS real.

## Testes manuais pendentes no QGIS (nenhum executado até agora)

1. Criar uma pasta, uma subpasta dentro dela, renomear e excluir ambas.
2. Criar o modelo de propriedade rural e confirmar as 6 subpastas.
3. Criar dois lugares e mover um deles para dentro de uma pasta pelo menu "Mover para
   pasta...".
4. Arrastar um lugar entre pastas direto na árvore, salvar o projeto, fechar e reabrir o
   QGIS, e confirmar que a posição se manteve.
5. Desmarcar a caixa de uma pasta e confirmar que os lugares dentro dela somem do mapa;
   marcar de novo e confirmar que voltam.
6. Excluir uma pasta com lugares dentro, confirmar o aviso, e checar que a tabela de
   cada lugar saiu do GeoPackage (ou que o aviso de falha apareceu, se não saiu).
7. Confirmar que mover um lugar entre pastas (pelo menu ou por arrastar) não muda sua
   geometria nem sua posição no mapa — só a organização.
8. Cancelar a janela "Mover para pasta..." e confirmar que nada muda.
9. Pesquisar um lugar pelo nome na janela de busca e confirmar que o duplo clique navega
   até ele.
10. Reexecutar o roteiro de validação da 0.8.0 (Ctrl+Z/Y, Ir para coordenadas, Ir para,
    tela cheia) para confirmar que nada regrediu com a Fase B.

## Problemas conhecidos / limitações deliberadas

- **Arrastar-e-soltar entre pastas não é capturado em tempo real.** A movimentação
  visual funciona imediatamente (é o comportamento nativo do QGIS, nenhum código do
  plugin precisa rodar para isso), mas a gravação no GeoPackage só acontece quando o
  projeto é salvo (sinal `QgsProject.writeProject`). Por isso a ação "Mover para
  pasta..." é oferecida como alternativa que grava na hora — exatamente a alternativa
  pedida caso o arrastar-e-soltar não pudesse ser garantido em tempo real.
- Renomear uma pasta usa o recurso nativo do QGIS (duplo clique); a sincronização com o
  GeoPackage também só acontece ao salvar o projeto, pelo mesmo motivo acima.
- A ordem dos lugares dentro de uma mesma pasta não é preservada entre sessões — só a
  relação "está dentro de qual pasta" é. Documentado no `LEIAME.md`.
- Pastas criadas pelo plugin só reconhecem como pai outra pasta também criada pelo
  plugin; um grupo nativo qualquer do QGIS não é adotado automaticamente.
- As duas tabelas de gerenciamento (`_ferramentas_terra_pastas`,
  `_ferramentas_terra_lugares`) ficam visíveis como tabelas comuns se alguém abrir o
  GeoPackage num navegador de banco de dados — não foram marcadas como tabelas internas
  do GDAL. Cosmético, não afeta a integridade dos dados.
- Mesma limitação já registrada nos relatórios anteriores: não foi possível validar o
  carregamento do plugin via Python embutido do QGIS nesta máquina (DLLs do Qt5/GDAL),
  por isso toda validação de comportamento real depende do QGIS aberto pelo usuário.

## Commit Git de referência

`2e05c38` — "Versao 0.9.0: changelog da Fase B" — HEAD no momento da geração deste
pacote, árvore de trabalho limpa.

## Caminho completo do ZIP

`C:\Users\Usuário\Desktop\ferramentas_terra\releases\v0.9.0\earth_tools_v0.9.0.zip`

## Confirmação de estrutura do pacote

Validado programaticamente nesta tarefa, com o ZIP gerado primeiro em arquivo temporário
e só movido para `releases/v0.9.0/` depois de passar todas as checagens:
- Integridade do ZIP (`zipfile.testzip()`): OK.
- Raiz única `earth_tools/`, sem pasta duplicada `earth_tools/earth_tools/`.
- 28 entradas, incluindo `places_model.py`, `folder_rules.py`, `dlg_search.py`,
  `dlg_move_folder.py` e `icons/search.svg`.
- Sem `.git`, `.gitignore`, `__pycache__`, `.pyc`, `tests/` ou qualquer `.gpkg`.
- `earth_tools/__init__.py` contém `def classFactory(iface)`.
- `earth_tools/metadata.txt` contém todos os campos obrigatórios, `version=0.9.0`.
- `releases/v0.7.0/` e `releases/v0.8.0/` confirmados intactos (nenhum arquivo
  sobrescrito).

# Relatório da versão 0.11.1 — Ferramentas Terra (correção crítica)

**Data de geração:** 2026-10-24.

## Evidência reportada pelo usuário

Testando a 0.11.0 no QGIS 3.44.15: a janela "Exportar para KML/KMZ" abria normalmente,
"Uma pasta (com subpastas)" estava disponível, a pasta "Nova pasta" foi selecionada, e
tanto KML quanto KMZ resultavam em "Não há nada para exportar nessa seleção" — ou, numa
outra tentativa, a pasta era exportada mas o arquivo ficava vazio. A árvore do painel
Camadas mostrava a pasta com marcadores, caminhos e polígonos dentro dela.

## Diagnóstico (código real, antes de qualquer alteração)

**Arquivos examinados:** `kml_bridge.py` (função `export_folder_tree`, linhas 271-298 da
0.11.0), `places_model.py` (`list_memberships`, `list_folders`), `dlg_export_kml.py`.

**Rastreamento do fluxo:** `dlg_export_kml.py._do_export()` → `kml_bridge.
export_folder_tree(folder_id)` → função interna `build(fid, name)`, que decidia o
conteúdo de uma pasta assim:

```python
for table, pasta_id in membership.items():
    if pasta_id == fid and table in layer_by_table:
        ...
```

onde `membership = places_model.list_memberships()` lê **só** a tabela canônica
`_ferramentas_terra_lugares`.

**Causa raiz:** essa tabela só recebe uma linha para um lugar em dois casos: o usuário
usa explicitamente "Mover para pasta..." (`dlg_move_folder.py` → `places_model.
set_place_folder`), **ou** o projeto é salvo (sinal `QgsProject.writeProject` →
`places_model.capture_layer_tree`, que só então lê a árvore visível e grava o que
encontra). Um lugar criado pela barra de ferramentas e simplesmente arrastado
visualmente para dentro de uma pasta — o fluxo mais comum, e exatamente o que a árvore
do usuário mostrava — nunca passa por nenhum desses dois gatilhos. A árvore do QGIS
exibe os itens corretamente porque é renderizada pelo próprio QGIS a partir do estado
real da sessão; a exportação nunca consultava esse estado real, só o cache.

Isso explica os dois sintomas relatados (lista vazia / arquivo vazio) e, mais grave,
também afetava **"Tudo (propriedade completa)"**: `build(fid="")` só incluía um lugar
se existisse uma linha explícita com `pasta_id==""`, então um lugar nunca tocado pela
Fase B também desaparecia dali. **Não afetava** a exportação de uma feição individual
("Salvar lugar como..."/"Enviar por e-mail..."), que lê a camada diretamente, sem
depender dessa tabela — confirmado no código e preservado sem alteração.

Nenhum identificador incompatível, filtro de nome ou exceção silenciosa estava
envolvido: o filtro simplesmente consultava uma fonte de dados que ficava desatualizada
em relação à árvore visível na maioria dos fluxos de uso reais.

## Correção implementada

`kml_bridge.export_folder_tree` (e a nova `export_folder_tree_with_errors`) passaram a
ler a **árvore de camadas visível do QGIS diretamente** (`QgsLayerTreeGroup`/
`QgsLayerTreeLayer`), em vez da tabela de cache:

- A pasta selecionada é resolvida pelo identificador interno estável
  (`places_model.find_group_by_folder_id`, via a propriedade customizada do grupo —
  nunca pelo nome exibido), tornado público nesta correção (antes era uma função
  "privada" de `places_model.py`, de uso só interno).
- O percurso recursivo (coleta de lugares e subpastas) foi extraído para um módulo novo
  e puro, `export_rules.py` (sem nenhum import de `qgis.*`), para poder ser testado sem
  QGIS e para não ficar emaranhado com a leitura real da árvore.
- Falhas ao exportar um item específico (ex.: geometria ilegível) são coletadas em vez
  de interromper ou mascarar o resto — `dlg_export_kml.py` agora avisa quantos itens
  falharam e pergunta se deve continuar com o restante.
- Seleção de pasta inválida (removida/renomeada entre abrir a janela e clicar em
  Exportar) levanta `kml_bridge.ExportError("pasta_invalida", ...)`, com mensagem
  distinta de "pasta vazia" (checada agora com `export_rules.is_empty`, que olha
  recursivamente as subpastas, não só o nível raiz).
- De brinde, antes de exportar a função também roda `places_model.rebuild_layer_tree`/
  `capture_layer_tree`, sincronizando a tabela canônica com o que foi encontrado — não é
  necessário para a correção funcionar, mas beneficia quem reabrir o projeto depois sem
  ter salvo.
- Nenhum dado existente foi modificado ou excluído: a correção é só na LEITURA para
  exportação; a gravação de lugares/pastas (Fases A-D) não foi tocada.

## Arquivos modificados/criados

Novos: `export_rules.py`, `tests/test_export_rules.py`.
Modificados: `kml_bridge.py` (`export_folder_tree` reescrita, `ExportError` novo),
`places_model.py` (`find_group_by_folder_id` tornada pública), `dlg_export_kml.py`
(trata `ExportError`, falhas parciais e pasta vazia distintamente), `metadata.txt`.

## Testes automatizados executados e resultados

`python -m unittest discover -s tests` → **88/88 testes passaram**: os 74 das fases
anteriores (regressão confirmada, nada quebrou) + 14 novos em
`tests/test_export_rules.py`, reproduzindo a FORMA do defeito com objetos falsos (que
nunca recebem nenhuma tabela de cache — só a árvore em si, então "esquecer de
sincronizar um cache" não é um jeito possível de o teste passar escondendo o bug):

- Pasta com um marcador / uma linha / um polígono / vários tipos de feição.
- Subpastas aninhadas percorridas recursivamente.
- Pasta que só tem subpastas ainda traz o conteúdo delas.
- Pasta realmente vazia (`is_empty` confirma recursivamente).
- `include_subfolders=False` não desce às subpastas.
- Camada que não é lugar do plugin é ignorada.
- Falha ao exportar um item específico não interrompe os demais, e é reportada.
- Teste nomeado explicitamente "não depende de nenhuma tabela de cache", reproduzindo a
  forma exata do bug relatado.

`python -m py_compile` em todos os 25 módulos `.py` → sem erro de sintaxe.

**O que não pôde ser automatizado:** a integração real com `QgsLayerTreeGroup`/
`QgsProject` (a parte que de fato lê a árvore do QGIS) depende do PyQGIS, indisponível
neste shell — mesma limitação de todas as fases anteriores. `export_rules.py` isola e
testa exatamente o algoritmo de percurso que estava faltando; a ligação com a árvore
real do QGIS (as funções `_tree_*` em `kml_bridge.py`) precisa de verificação manual.

## Teste de regressão (Etapa 4)

Reexecutados nesta correção, todos passando: regras geométricas (`test_geometry_rules`),
histórico de desfazer/refazer (incluído em `test_geometry_rules.UndoStackTests`),
entrada numérica e aderência (`test_measure_rules`), pastas e hierarquia
(`test_folder_rules`), importação KML/KMZ (`test_kml_io`). Nenhuma regressão.

## Roteiro de validação manual no QGIS 3.44.15 (nenhum executado até agora)

1. Criar uma pasta nova, criar um marcador/caminho/polígono pela barra de ferramentas
   (sem usar "Mover para pasta..."), arrastá-los visualmente para dentro da pasta no
   painel Camadas, **sem salvar o projeto**, e exportar essa pasta — confirmar que o
   KML/KMZ resultante contém os três itens. Este é o cenário exato relatado.
2. Repetir o item 1 com "Tudo (propriedade completa)".
3. Criar uma pasta com só uma subpasta dentro (sem itens diretos) e confirmar que
   exportar essa pasta traz o conteúdo da subpasta.
4. Exportar uma pasta genuinamente vazia e confirmar a mensagem "não tem nenhum lugar",
   distinta de qualquer erro.
5. Selecionar uma pasta no diálogo, apagá-la na árvore sem fechar o diálogo, clicar em
   Exportar, e confirmar a mensagem específica de pasta não encontrada.
6. Exportar uma feição individual (Salvar lugar como.../Enviar por e-mail) e confirmar
   que continua funcionando exatamente como na 0.11.0.
7. Reimportar o arquivo exportado no passo 1 e comparar nomes, descrições, estilos e
   coordenadas com os originais.
8. Confirmar que, após a exportação, os lugares/pastas originais no GeoPackage não foram
   alterados (nome, geometria, organização).
9. Repetir o roteiro de validação das fases A, B, C e D para confirmar ausência de
   regressão.

## Commit Git de referência

`aff90e7` — "Versao 0.11.1: changelog da correcao critica de exportacao" — HEAD no
momento da geração deste pacote, árvore de trabalho limpa.

## Caminho completo do ZIP

`C:\Users\Usuário\Desktop\ferramentas_terra\releases\v0.11.1\earth_tools_v0.11.1.zip`

## Confirmação de estrutura do pacote

- Integridade do ZIP (`zipfile.testzip()`): OK.
- Raiz única `earth_tools/`, sem pasta duplicada.
- 37 entradas, incluindo `export_rules.py`.
- Sem `.git`, `__pycache__`, `.pyc`, `tests/` ou `.gpkg`.
- `earth_tools/__init__.py` contém `def classFactory(iface)`.
- `earth_tools/metadata.txt`: todos os campos obrigatórios, `version=0.11.1`.
- `releases/v0.7.0/` a `v0.11.0/` confirmados intactos, nenhum arquivo sobrescrito.

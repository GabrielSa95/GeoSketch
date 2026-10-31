# Relatório da versão 0.14.0 — Ferramentas Terra

**Data de geração:** 2026-10-30.

## Pedido do usuário

Reescopo da prioridade do plugin: suspender o desenvolvimento do histórico temporal de
imagens de satélite (Sentinel-2/Landsat) e priorizar desenho, medição e geoprocessamento,
aproximando a experiência do Google Earth Pro. Pedido explícito de: melhorar a Régua,
adicionar seleção de SRC/CRS para caminhos, corrigir o desenho de círculos, simplificar a
interface e preservar as funcionalidades já aprovadas — sem reescrever o plugin nem fazer
downgrade indiscriminado do código.

## Auditoria inicial (Fase 1)

- Versão de partida: `0.13.1` (`metadata.txt`), HEAD `b749c48` dentro de
  `earth_tools/.git` (o repositório Git vive dentro de `earth_tools/`, não na raiz do
  projeto — decisão documentada em `README.md`), árvore limpa.
- ZIP e relatório da 0.13.1 confirmados intactos em `releases/v0.13.1/`.
- Funcionalidades adicionadas desde a 0.11.1: Fase E (0.12.0 — busca/carregamento
  Sentinel-2/Landsat), Fase F (0.13.0 — correção de cobertura/NoData/contraste, linha do
  tempo anual, menu de contexto de pasta para KML, simplificação da barra), 0.13.1
  (paginação e validação de coleção/sensor da busca STAC).
- Módulos do histórico de imagens identificados como isolados (sem dependência de
  nenhum outro módulo do plugin): `dlg_imagery.py`, `imagery_bridge.py`,
  `imagery_cache.py`, `imagery_timeline.py`, `stac_client.py`, e os testes
  correspondentes. Único ponto de acoplamento: a importação e o botão em
  `earth_tools.py`.
- Régua/Caminho/Círculo/Polígono: `dlg_ruler.py`, `maptools.py` (compartilhado com
  `dlg_feature.py` — marcador/caminho/polígono "de cadastro", não a régua), `utils.py`,
  `widgets.py`.
- Botão de tela cheia (`earth_tools.py._add_fullscreen_toggle`, só reaproveitava
  `iface.actionToggleFullScreen()`) e "Pesquisar lugares" (`dlg_search.py`, busca só
  entre camadas criadas pelo próprio plugin — não é a pesquisa de atributos nativa do
  QGIS) identificados e confirmados sem dependência cruzada com o resto do código.
- Achado avulso: um `earth_tools.zip` obsoleto (versão 0.8.0) na raiz do projeto, fora da
  política de `releases/` — removido a pedido do usuário.
- Decisão de arquitetura confirmada com o usuário antes de implementar: o Caminho da
  Régua passa a gravar a tabela do GeoPackage **no SRC escolhido**, não mais sempre em
  WGS84 (opção que toca `storage.create_place()`, compartilhada por todos os tipos de
  lugar, em vez de criar uma camada paralela só para o Caminho).

## Suspensão do histórico de imagens (Fase 2)

- Marca de segurança `pre-fase2-historico-imagens` e branch
  `feature/historico-imagens-suspenso` criadas em `b749c48`, **antes** de qualquer
  remoção — preserva o código completo das Fases E/F para retomada futura.
- Removidos de `master`: `dlg_imagery.py`, `imagery_bridge.py`, `imagery_cache.py`,
  `imagery_timeline.py`, `stac_client.py`, `tests/test_imagery_cache.py`,
  `tests/test_imagery_timeline.py`, `tests/test_stac_client.py`, `icons/imagery.svg`.
- `earth_tools.py`: removida a importação de `ImageryDialog`, o botão "Imagens de
  satélite..." e o método `_open_imagery`.
- `LEIAME.md`: removida a seção "Imagens de satélite e histórico temporal" e a entrada
  correspondente na tabela de botões; acrescentada uma nota em "Limitações conhecidas"
  explicando a suspensão e onde o código foi preservado.
- Confirmado por busca textual em todos os módulos: nenhum outro arquivo (armazenamento,
  pastas, KML, régua, desenho) tinha qualquer referência aos módulos removidos.

## SRC/CRS no Caminho da Régua (Fase 3)

- `widgets.py`: novo `CrsRow`, usando `QgsProjectionSelectionWidget` — o seletor nativo
  do QGIS, o mesmo das ferramentas de Processamento (ex.: parâmetro de SRC do Buffer em
  Vetor Geral). Mostra EPSG + nome do SRC escolhido no próprio botão.
- `dlg_ruler.py`: a aba **Caminho** (e só ela — Linha, Polígono e Círculo não mudam)
  ganha esse seletor, começando no SRC do projeto. `_save()` transforma os pontos do CRS
  do canvas para o CRS escolhido (`QgsCoordinateTransform`) antes de montar a geometria,
  e passa esse CRS para `storage.create_place()`.
- `storage.py`: `create_place()` ganha o parâmetro opcional `crs`. Quando omitido
  (comportamento de todo o resto do plugin, inclusive Linha/Polígono/Círculo da própria
  Régua), nada muda — grava em EPSG:4326 como sempre. Quando informado, a camada de
  memória é criada com `mem.setCrs(crs)` e a tabela do GeoPackage é escrita nesse SRC
  (sem reprojeção para WGS84).
- `LEIAME.md`: nova seção "Régua - SRC do caminho e uso no Buffer" documentando o fluxo
  completo (escolher um SRC projetado em metros, salvar, confirmar o SRC na camada,
  abrir no Buffer).
- A medição de comprimento mostrada na aba continua sempre geodésica (elipsoide WGS84,
  via `QgsDistanceArea`) independente do SRC escolhido para gravação — unidade de
  exibição e SRC de armazenamento são conceitos deliberadamente separados, documentado.

## Correção do Círculo (Fase 4)

**Causa raiz identificada por leitura de código** (não foi possível reproduzir
visualmente nesta máquina, sem PyQGIS — ver seção de limitações): `utils.circle_points()`
chamava `make_distance_area()` sem informar o CRS, caindo por omissão no CRS do
**projeto** em vez do CRS do **canvas/mapa** onde os pontos clicados realmente estão (os
outros métodos de medição em `dlg_ruler.py` já passavam esse CRS explicitamente; só o
círculo não). Além disso, qualquer exceção na projeção geodésica de **um único** dos 72
segmentos do anel descartava a função inteira (`return [], radius`), e
`maptools.display_points()` caía de volta para desenhar `[centro, borda]` como um
"polígono" de 2 pontos — visualmente idêntico à linha pontilhada do raio, reproduzindo
exatamente o sintoma relatado.

- `utils.circle_points()`: ganhou o parâmetro `crs`; cada um dos 72 segmentos é tentado de
  forma independente (uma falha isolada não derruba o anel inteiro); só desiste —
  registrando no log nativo do QGIS — se sobrarem menos de 3 pontos projetados com
  sucesso.
- `maptools.py`: `display_points()`, `geometry_points()` e `radius()` agora passam o CRS
  do canvas (`self._circle_crs()`) explicitamente. `display_points()` nunca mais cai de
  volta para o par `[centro, borda]`.

## Simplificação da Régua (Fase 5)

- `dlg_ruler.py`: removidas as abas placeholder "Caminho em 3D" e "Polígono em 3D" (nunca
  tiveram lógica de medição real — dependiam de um MDE que o plugin nunca chegou a usar).
  Linha, Caminho, Polígono e Círculo são as 4 abas mantidas.
- Linha (`mode="line2"`): confirmado por leitura de código que já gravava **uma única**
  `QgsGeometry.fromPolylineXY` por medição (um só ponto de chamada a
  `storage.create_place()` em `_save()`); os `QgsVertexMarker` mostrados durante o
  desenho são temporários, nunca vão ao GeoPackage, e são limpos em
  `reset()`/`closeEvent()`. Não foi identificado o defeito de "dois marcadores
  independentes" no código atual — comentário explicativo adicionado e trancado por
  teste de regressão; se o comportamento observado pelo usuário for diferente do descrito
  aqui, preciso do passo a passo exato para reproduzir.
- `LEIAME.md` atualizado (remoção da limitação das abas 3D).

## Simplificação da barra principal (Fase 6)

- `earth_tools.py`: removidos o botão/importação de `SearchDialog` e o método
  `_add_fullscreen_toggle()` (só reaproveitava `iface.actionToggleFullScreen()`, sem
  lógica própria).
- Removidos `dlg_search.py` e o ícone `icons/search.svg`.
- Confirmado por busca textual: nenhum atalho de teclado dedicado a nenhum dos dois;
  nenhuma referência a `actionIdentify`/`MapToolIdentify` ou qualquer pesquisa nativa do
  QGIS foi tocada.
- `LEIAME.md` atualizado.

## Arquivos alterados (resumo)

Removidos: `dlg_imagery.py`, `imagery_bridge.py`, `imagery_cache.py`,
`imagery_timeline.py`, `stac_client.py`, `dlg_search.py`, `icons/imagery.svg`,
`icons/search.svg`, `tests/test_imagery_cache.py`, `tests/test_imagery_timeline.py`,
`tests/test_stac_client.py`.

Modificados: `earth_tools.py`, `dlg_ruler.py`, `maptools.py`, `utils.py`, `storage.py`,
`widgets.py`, `LEIAME.md`, `metadata.txt`.

Novos: `tests/test_regression_static.py`, `tests/test_qgis_integration.py`.

**Intocados** (confirma que "não reescrever o plugin" foi cumprido): `places_model.py`,
`folder_rules.py`, `kml_io.py`, `kml_bridge.py`, `layeractions.py`, `vertexedit.py`,
`snapping.py`, `geometry_rules.py`, `export_rules.py`, `dlg_edit.py`, `dlg_feature.py`,
`dlg_goto.py`, `dlg_import_kml.py`, `dlg_export_kml.py`, `dlg_move_folder.py`,
`__init__.py` — toda a organização de pastas, KML, edição de vértices, undo/redo e as
janelas de criação Novo Marcador/Caminho/Polígono.

## Testes automatizados executados e resultados

`python -m unittest discover -s tests` → **108 testes passaram, 1 módulo pulado**
(94 preexistentes + 14 novos em `test_regression_static.py`):

- `test_regression_static.py` (sem PyQGIS, executado de verdade neste ambiente): trava
  por inspeção de código-fonte a ausência dos módulos de imagem, a ausência de
  "Tela cheia"/"Pesquisar lugares"/abas 3D no código, a chamada única a
  `storage.create_place()` na Linha, e — mais importante — a ausência do padrão exato do
  bug do Círculo (fallback `ring if ring else list(pair)` e `except Exception: return
  [], radius` dentro do laço). Se algum desses padrões for reintroduzido por um commit
  futuro, este teste quebra.
- `test_qgis_integration.py` (CRS padrão/escolhido no Caminho, transformação de
  coordenadas, compatibilidade da geometria com o Buffer, integridade geométrica do anel
  do Círculo em CRS geográfico e projetado, smoke test de importação dos módulos
  alterados): **escrito e revisado, mas não executado de verdade** — o ambiente onde
  este trabalho foi feito não tem o módulo `qgis` instalado (não é uma instalação do
  QGIS). `setUpModule()` pula o arquivo inteiro via `SkipTest` em vez de fingir sucesso.
  **Precisa ser executado dentro do Python do próprio QGIS antes de considerar esta
  versão validada.**

`python -m py_compile` em todos os módulos `.py` do plugin → sem erro de sintaxe.

**O que não pôde ser automatizado nem verificado nesta máquina:** qualquer interação real
com `QgsMapCanvas`/`QgsRubberBand`/`QgsVertexMarker` (desenho do círculo na tela,
limpeza de geometria temporária, ausência visual de marcadores na Linha), o seletor de
SRC nativo (`QgsProjectionSelectionWidget`) dentro de uma janela real, e o fluxo completo
Régua → Salvar → Buffer dentro da interface do QGIS. A causa raiz do bug do Círculo foi
identificada por leitura cuidadosa de código e corrigida de forma defensiva, mas **não
pôde ser visualmente confirmada nem antes nem depois da correção** nesta máquina — por
isso o roteiro manual abaixo é obrigatório antes de aprovar a versão.

## Roteiro de validação manual no QGIS 3.44.15 (nenhum executado até agora)

Roteiro completo em `ROTEIRO_VALIDACAO_MANUAL_v0.14.0.md`, na raiz do projeto. Cobre:
ausência de qualquer busca de imagens de satélite; SRC padrão e SRC escolhido no Caminho
(com conferência do SRC gravado na camada); uso do Caminho resultante no Buffer;
desenho completo da circunferência (inclusive em zoom diferente e em círculos grandes),
valores de raio/circunferência/área, limpeza do círculo; Linha como feição única (uma
linha, não dois marcadores) e as 4 abas restantes da Régua; ausência dos botões de tela
cheia e pesquisar lugares, com confirmação de que o tela cheia nativo e a pesquisa de
atributos nativa do QGIS continuam funcionando; checagem rápida de regressão (marcador,
polígono, caminho, pastas, edição de vértice, KML/KMZ, ir-para-coordenadas, Google Maps,
reabertura do projeto).

**Esta versão não está aprovada** até esse roteiro ser executado pelo usuário e o
resultado real (não o esperado) ser registrado.

## Problemas conhecidos / limitações deliberadas

- A causa do bug do Círculo foi corrigida por análise de código e hardening defensivo
  (CRS explícito + resiliência por segmento), não por reprodução visual confirmada nesta
  máquina — ver seção de testes acima.
- Não foi possível identificar no código atual o defeito de "dois marcadores
  independentes" na Linha descrito no pedido original; o comportamento encontrado já
  salva uma única geometria de linha. Se o usuário observar esse comportamento na
  validação manual, preciso do passo a passo exato para investigar mais a fundo.
- `test_qgis_integration.py` não foi executado de verdade (sem ambiente QGIS disponível
  nesta máquina) — ver seção de testes.
- Histórico de imagens: suspenso, não removido definitivamente. Código no branch
  `feature/historico-imagens-suspenso` (a partir da marca
  `pre-fase2-historico-imagens`), ambos em `b749c48`.

## Commit Git de referência

`339bdeb` — "Versao 0.14.0: changelog do reescopo (Fases 2-6)" — HEAD no momento da
geração deste pacote, árvore de trabalho limpa. Commits desta versão, em ordem:
`19db8f6` (Fase 2 — suspende histórico de imagens), `41e216e` (Fase 3 — SRC no Caminho),
`e3a4347` (Fase 4 — corrige o Círculo), `59a74c7` (Fase 5 — remove abas 3D), `72ac7fc`
(Fase 6 — remove Tela cheia/Pesquisar lugares), `a3bf38b` (Fase 7 — testes automatizados),
`339bdeb` (versão). Marca de segurança: `pre-fase2-historico-imagens`; branch de
preservação: `feature/historico-imagens-suspenso` — ambos em `b749c48` (0.13.1, ponto de
partida).

## Caminho completo do ZIP

`C:\Users\Usuário\Desktop\ferramentas_terra\releases\v0.14.0\earth_tools_v0.14.0.zip`

## Confirmação de estrutura do pacote

- Integridade do ZIP (`zipfile.testzip()`): OK.
- Raiz única `earth_tools/`, sem pasta duplicada. 35 entradas (43 da 0.13.1, menos os 9
  arquivos de imagem/busca e os 2 ícones removidos, menos `.gitignore` — que também não
  entrava nos pacotes anteriores).
- Sem `.git`, `.gitignore`, `__pycache__`, `.pyc`, `tests/` ou `.gpkg`.
- Confirmado ausentes: `dlg_imagery.py`, `imagery_bridge.py`, `imagery_cache.py`,
  `imagery_timeline.py`, `stac_client.py`, `dlg_search.py`, `icons/imagery.svg`,
  `icons/search.svg`.
- `earth_tools/metadata.txt`: `version=0.14.0`.
- `releases/v0.7.0/` a `v0.13.1/` confirmados intactos, nenhum arquivo sobrescrito.
- `earth_tools.zip` obsoleto (v0.8.0) removido da raiz do projeto, a pedido do usuário.

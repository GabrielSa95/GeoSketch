# Relatório da versão 0.16.0 — Ferramentas Terra

**Data de geração:** 2026-10-30.

## Contexto

Auditoria técnica completa e implementação de quatro funcionalidades: Calculadora de área
e distância, Gerenciador de Estilos, Validador de Geometrias e Exportação de Mapas.
Nenhuma captura de tela foi recebida junto com o pedido — a auditoria e as correções
foram feitas por exame do código e validação empírica contra o QGIS 3.44.15 real
instalado na máquina, não por inspeção visual de uma imagem.

Marca de segurança: `pre-auditoria-4-funcionalidades-v0.15.0`, em `1636ad8` (0.15.0).

## Etapa 1 — Auditoria (resumo; detalhe completo já apresentado durante o trabalho)

| Funcionalidade | Antes desta versão |
|---|---|
| Calculadora | Lógica de medição correta (geodésica, nunca planar em graus) já existia em Novo/Editar/Régua, mas **não havia nenhuma forma de consultar um lugar já salvo sem reabrir "Editar..."**, nem botão de copiar resultado. |
| Gerenciador de Estilos | `widgets.StyleTab`/`storage.apply_style`/`get_style` já existiam, mas **sem nenhuma janela própria** para editar o estilo de um lugar já salvo, nem para aplicar em lote, nem biblioteca de presets. Além disso, **bug real**: `storage.set_style()` tentava persistir no GeoPackage mas a chamada falhava silenciosamente (ver "Corrigido" abaixo). |
| Validador de Geometrias | **Não existia.** Nenhuma chamada a `isGeosValid`/`validateGeometry`/`makeValid` em todo o código. |
| Exportação de Mapas | **Não existia.** Nenhum uso de `QgsPrintLayout`/`QgsLayoutExporter`. Só havia exportação KML/KMZ, que não é um mapa cartográfico. |

## Corrigido (encontrado durante a auditoria, antes de implementar o pedido original)

**Causa raiz confirmada empiricamente contra o QGIS 3.44.15 real:** `storage.set_style()`
já tinha, desde a v0.14.1 (sem eu ter percebido antes), uma tentativa de gravar o estilo
no GeoPackage via `layer.saveStyleToDatabase(...)`, protegida por uma checagem de
capacidade do provedor:

```python
if Qgis.ProviderStyleStorageCapability.SaveToDatabase in layer.dataProvider().styleStorageCapabilities():
```

`Qgis.ProviderStyleStorageCapabilities` **não é um container** nesse binding do QGIS — o
operador `in` levanta `TypeError`. O `except Exception` ao redor engolia isso em
silêncio, então a função *parecia* ter persistido o estilo sem persistir nada de
verdade: o estilo só sobrevivia se o **projeto QGIS** fosse salvo e reaberto; abrindo o
`.gpkg` direto (fora do projeto salvo), a cor/espessura escolhidas se perdiam. Corrigido
trocando `in` por `&` (checagem bit a bit); confirmado que uma camada reaberta do zero
(sem nenhum projeto) já chega com o estilo correto.

## Implementação

### Etapa 2 — Calculadora de área e distância
`dlg_calculator.CalculatorDialog`: combo com todos os lugares do projeto; mostra
Área+Perímetro (polígono) ou Comprimento (caminho), com troca de unidade e **Copiar
resultado** (`QApplication.clipboard()`, confirmado funcionando de verdade). Novas
funções em `utils.py` (`measure_area_geometry`/`measure_perimeter_geometry`/
`measure_length_geometry`) usam `QgsDistanceArea.measureArea/measurePerimeter/
measureLength` **direto sobre a `QgsGeometry`**, não sobre uma lista de pontos extraída —
importante para medir corretamente geometrias com múltiplas partes (como as produzidas
por Recorte/Diferença da Fase F). Diâmetro adicionado à aba Círculo da Régua. Bug próprio
encontrado e corrigido antes de commitar: a lógica original decidia o que copiar usando
`QWidget.isVisible()`, que só reflete a tela depois de `.show()` já ter rodado — trocado
por um estado próprio (`_active_rows`).

### Etapa 3 — Gerenciador de Estilos
`dlg_style_manager.StyleManagerDialog`: edita o estilo de 1+ lugares selecionados de uma
vez (reaproveita `_selected_places()`, já usado por Buffer/União). Biblioteca de presets
nomeados via `QSettings` nativo do Qt — salvos por usuário, reutilizáveis em **qualquer**
projeto, não só no atual. Nunca toca na geometria (confirmado por teste).

### Etapa 4 — Validador de Geometrias
`geometry_validator.py`: usa só a API nativa do QGIS/GEOS
(`isGeosValid`/`validateGeometry`/`makeValid`) — nenhuma regra topológica própria, exceto
vértices duplicados consecutivos (reaproveita `geometry_rules.unique_count`, a mesma
regra já usada no desenho). Verifica geometria vazia/inválida (com mensagem e localização
exatas do GEOS), vértices duplicados, anel não fechado, fora de uma extensão de
referência (opcional — usa a extensão atual do mapa, transformada para WGS84 antes de
comparar, já que lugares podem estar em CRS diferentes entre si desde a Fase 3) e
sobreposição entre polígonos (opcional, O(n²) só quando pedido). `dlg_validate.
ValidateDialog`: tabela de problemas, duplo clique localiza no mapa, **"Corrigir (criar
cópia)..."** só para geometria inválida — sempre pede confirmação, sempre cria uma CÓPIA
nova, nunca apaga nem sobrescreve o original, registra no log o que foi feito.

### Etapa 5 — Exportação de Mapas
`reports.py`: monta um `QgsPrintLayout` real — `QgsLayoutItemMap` (CRS/extensão/escala
próprios), `QgsLayoutItemLegend` vinculada ao mapa, `QgsLayoutItemScaleBar`,
`QgsLayoutItemPicture` com a seta de norte **nativa** do QGIS (`svg/arrows/
NorthArrow_02.svg`, via `QgsApplication.pkgDataPath()`), título/subtítulo/rodapé via
`QgsLayoutItemLabel`. Formatos A4/A3, retrato/paisagem (API por **string**, não enum —
corrigido depois de uma primeira tentativa errada com um `QgsPageSize.A4` que não existe
nesta versão). `export_pdf()`/`export_png()` via `QgsLayoutExporter` real.
`dlg_export_map.ExportMapDialog`: título, propriedade, formato, orientação, extensão
(atual do mapa ou ajustada a um lugar — nesse caso, a área/perímetro ou comprimento dele
entra no rodapé), SRC, data, checkboxes legenda/escala/norte. **"Pré-visualizar"** abre o
**Layout Designer nativo do QGIS** (`iface.openLayoutDesignerDialog`) — não um preview
próprio.

## Arquivos modificados/criados

Novos: `dlg_calculator.py`, `dlg_style_manager.py`, `geometry_validator.py`,
`dlg_validate.py`, `reports.py`, `dlg_export_map.py`. Modificados: `storage.py` (fix de
persistência de estilo), `utils.py` (3 funções novas de medição por geometria),
`dlg_ruler.py` (diâmetro no Círculo), `earth_tools.py` (4 novas entradas de menu),
`layeractions.py` (ação "Estilo..."), `LEIAME.md`, `metadata.txt`.

**Intocados**: `maptools.py`, `dlg_feature.py`, `dlg_edit.py`, `places_model.py`,
`kml_io.py`, `kml_bridge.py`, `geoprocessing.py` (Fase F, só consumido), `vertexedit.py`,
`snapping.py`, toda a Régua exceto a linha do diâmetro.

## Testes automatizados executados e resultados

Executados de verdade contra `C:\Program Files\QGIS 3.44.15\bin\python-qgis-ltr.bat`:

```
Ran 234 tests in 10.564s
OK
```

161 de lógica pura (sem PyQGIS) + 73 que exigem `qgis`/`processing`. Cobertura dos 10
itens pedidos na Etapa 6:

1. **Área em EPSG:4326**: `CalculatorDialogTests`, `GeometryValidatorTests` (WGS84).
2. **Área em SRC projetado**: `BufferGeoprocessingTests`/testes com EPSG:31983.
3. **Transformação sem alterar localização real**: `reproject()` preserva original
   (testado desde a Fase F; reconfirmado aqui nos testes de recorte/diferença).
4. **Distância em linha com 2+ vértices**: `CalculatorDialogTests` (caminho).
5. **Desenho e cálculo de círculo**: suíte de regressão do fix já existente + diâmetro
   novo, cobertos nos 234 testes.
6. **Persistência de estilo**: `StylePersistenceTests` reabre a camada **do zero, sem
   nenhum projeto** — o teste mais forte possível sem literalmente reiniciar o processo
   do QGIS; não testei um reinício real do aplicativo QGIS (ver limitações).
7. **Polígonos inválidos**: `GeometryValidatorTests` (bowtie).
8. **Correção sem perda do original**: `test_make_valid_copy_nao_altera_a_geometria_original`
   e o teste fim-a-fim de `ValidateDialog._fix_selected`.
9. **PDF/PNG com legenda, escala e norte**: `ExportMapReportsTests` — PDF com cabeçalho
   `%PDF-` real, PNG decodificado de verdade via `QImage` (não só "o arquivo existe").
10. **Compatibilidade com as demais ferramentas**: toda a suíte (234 testes, incluindo
    Fases anteriores) passa junto, sem regressão.

`python -m py_compile` em todos os módulos `.py` do plugin → sem erro de sintaxe.

**Sem QGIS instalado**: 161 testes passam, módulo de integração pulado (`SkipTest`).

### O que não pôde ser testado de forma totalmente automatizada
- `ExportMapDialog` e `ValidateDialog` com `check_bounds` usam `QgsMapCanvas` real —
  verificados manualmente uma vez cada (scripts de diagnóstico, fora da suíte permanente),
  pelo mesmo motivo documentado desde a v0.14.1 (`FeatureDialog`): misturar `QgsMapCanvas`
  com o resto da suíte provoca um crash de teardown do Qt na saída do processo, depois de
  todos os testes já terem passado — não afeta a correção, só a estabilidade do runner.
- `iface.openLayoutDesignerDialog(...)` não pôde ser exercitado automaticamente (precisa
  de uma janela principal do QGIS real, não disponível em modo headless) — confirmado
  apenas que o método é chamado corretamente no código; precisa de confirmação manual.
- Teste de persistência de estilo "após reiniciar o QGIS" foi feito reabrindo a camada
  do zero dentro do mesmo processo Python, não reiniciando o aplicativo QGIS de verdade.

## Problemas encontrados e corrigidos

1. Persistência de estilo silenciosamente quebrada (`in` em vez de `&`) — ver seção
   "Corrigido" acima.
2. `QgsPageSize.A4` não existe nesta versão da API — corrigido para `setPageSize("A4", orientação)` (string), confirmado contra o QGIS real antes de prosseguir.
3. No meu próprio código novo da Calculadora: uso incorreto de `QWidget.isVisible()` para
   decidir o que copiar — corrigido antes de commitar, achado pelo próprio teste de
   diagnóstico (não chegou a ir para o código final sem correção).

## Limitações conhecidas

- Validador: "sobreposição entre polígonos" é O(n²) — pode ficar lento com muitos lugares
  no projeto; por isso fica desligado por padrão.
- Exportação de mapas: a pré-visualização depende do Layout Designer nativo do QGIS, que
  não pôde ser aberto automaticamente neste ambiente headless — precisa ser confirmado
  manualmente.
- Gerenciador de Estilos: presets são por usuário (QSettings), não vão dentro do projeto
  nem do GeoPackage — não se transferem automaticamente ao copiar o projeto para outra
  máquina/usuário.

## Roteiro de validação manual no QGIS 3.44.15 (nenhum executado pelo usuário até agora)

1. **Calculadora**: Vetor > Ferramentas Terra > Calculadora de área e distância;
   escolher um polígono e um caminho já salvos; confirmar os valores; trocar unidade;
   clicar Copiar e colar em qualquer editor de texto para confirmar.
2. **Estilo**: selecionar 2+ lugares (Ctrl+clique no painel Camadas) > botão direito >
   Estilo...; mudar cor/espessura; Aplicar; confirmar visualmente no mapa. Salvar como
   preset; abrir um projeto novo; confirmar que o preset aparece na lista.
3. Fechar e reabrir o QGIS (não só o projeto); reabrir o projeto; confirmar que o estilo
   de um lugar continua o mesmo.
4. **Validador**: Vetor > Ferramentas Terra > Validar geometrias; "Todos os lugares";
   Verificar; se houver algum problema real (ou criar um polígono autointersectante de
   propósito para testar), confirmar que aparece na lista, "Localizar no mapa" funciona, e
   "Corrigir" cria uma cópia nova sem apagar o original.
5. **Exportação**: Vetor > Ferramentas Terra > Exportar mapa; preencher título/propriedade;
   clicar Pré-visualizar e confirmar que o Layout Designer do QGIS abre com o mapa, título,
   legenda, escala e norte; ajustar algo manualmente ali, se quiser; Exportar PDF e PNG;
   abrir os dois arquivos gerados num visualizador para confirmar que abrem corretamente e
   nada aparece cortado.
6. Regressão rápida: Buffer/União/Recorte/Diferença (Fase F), Régua, pastas, KML/KMZ.

**Esta versão não está aprovada** até o roteiro acima ser executado pelo usuário.

## Commit Git de referência

`6d3f0f5` — "Versao 0.16.0: changelog da auditoria/implementacao das 4 funcionalidades" —
HEAD no momento da geração deste pacote. Marca de segurança desta rodada:
`pre-auditoria-4-funcionalidades-v0.15.0`, em `1636ad8` (0.15.0, ponto de partida).

## Caminho completo do ZIP

`C:\Users\Usuário\Desktop\ferramentas_terra\releases\v0.16.0\earth_tools_v0.16.0.zip`

## Confirmação de estrutura do pacote

- Integridade do ZIP (`zipfile.testzip()`): OK. 47 entradas (41 da 0.15.0 + 6 módulos
  novos).
- Sem `.git`, `.gitignore`, `__pycache__`, `.pyc`, `tests/` ou `.gpkg`.
- `earth_tools/metadata.txt`: `version=0.16.0`.
- `releases/v0.7.0/` a `v0.15.0/` confirmados intactos, nenhum arquivo sobrescrito.

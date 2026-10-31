# Relatório da versão 0.15.0 — Ferramentas Terra

**Data de geração:** 2026-10-30.

## Contexto

Início do "Projeto Mestre": evolução do Ferramentas Terra para geoprocessamento, gestão
geométrica, estilos, relatórios e integração (Fases F a K). Esta versão entrega a **Fase F
completa** (geoprocessamento). As Fases G, H, I, J e K ainda não foram implementadas.

## Auditoria inicial (Etapa 0)

- Partida: `0.14.1`, HEAD `34314f7`, árvore limpa. Marca de segurança
  `pre-projeto-mestre-v0.14.1` criada antes de qualquer alteração.
- **Fato arquitetural central identificado** (vale para todas as fases seguintes): cada
  lugar é sua própria camada de **1 única feição** (`storage.create_place()`) — não existe
  uma camada "Marcadores" com N feições. Seleção múltipla de lugares significa selecionar
  múltiplas **camadas** na árvore, não múltiplas feições numa camada — padrão já existente
  em `layeractions.delete_selected()`, reaproveitado em todas as novas ferramentas.
- Esquema de atributos mínimo (`nome`, `descricao`, `criado_em`) — área/perímetro nunca
  persistidos, sempre recalculados. Estilo fica em `customProperty()` da camada, não em
  atributo.
- **Zero integração com QGIS Processing** antes desta versão (confirmado por busca em
  todo o código). Toda a Fase F parte do zero nesse ponto.
- Nenhum módulo duplicado ou erro crítico novo encontrado na auditoria estática.

## Decisão de ambiente: QGIS real disponível

Esta máquina tem QGIS 3.44.15 instalado (`C:\Program Files\QGIS 3.44.15`). Diferente de
boa parte do histórico deste projeto, **toda** a lógica de geoprocessamento foi escrita
*depois* de confirmada empiricamente contra a API real — incluindo o framework de
Processing, inicializado via `Processing.initialize()` (não confiável sem isso num
processo headless). Script de diagnóstico típico, por operação, antes de qualquer linha
de código final: reproduzir a chamada real a `processing.run(...)`, conferir o resultado,
só então implementar `geoprocessing.py`.

## Implementação

### F1 — Gerar Buffer (`native:buffer`)
`geoprocessing.buffer_single()`/`run_buffer()`: transforma a entrada para o SRC de
processamento (rejeita SRC geográfico com `GeoprocessingError` — nunca calcula em graus),
monta uma camada de memória de 1 feição, chama o algoritmo nativo. `dlg_buffer.
BufferDialog`: distância (aceita negativo — Buffer negativo, só com sentido geométrico em
polígono), unidade, segmentos, SRC de processamento/saída (`widgets.CrsRow`, reaproveitado
da Régua), dissolver (2+ lugares), estilo (`widgets.StyleTab`, reaproveitado), pasta de
destino (`places_model.folder_choices()`, mesmo padrão de `dlg_move_folder.py`). Ação
"Gerar Buffer..." no menu de contexto, com seleção múltipla.

### F2 — Unir polígonos (`QgsGeometry.unaryUnion`)
`geoprocessing.union_polygons()`: união topológica nativa do GEOS via API do QGIS — não é
uma reimplementação própria. Rejeita menos de 2 entradas e qualquer entrada que não seja
polígono.

### F3 — Dividir polígono (`native:splitwithlines`)
`geoprocessing.split_polygon()`: a validação de "a linha atravessa de verdade" é feita
pelo **número de partes devolvidas pelo próprio algoritmo** (1 parte = sem divisão, 2+ =
dividiu) — confirmado contra o QGIS real que o algoritmo nunca lança exceção nesse caso,
só devolve a geometria original intacta. `dlg_split.SplitDialog` desenha a linha no mapa
(reaproveita `maptools.DrawTool`), separa **Pré-visualizar** (não grava nada) de
**Confirmar** (grava as partes e só então apaga o original — nunca antes, nunca se a
gravação falhar).

### F4 — Recortar com... (`native:clip`) e F5 — Diferença (`native:difference`)
`geoprocessing.clip_geometry()`/`difference_geometry()`: suportam marcador, caminho e
polígono como entrada (a máscara/subtraendo precisa ser polígono). Sem interseção/segunda
geometria cobrindo tudo = erro claro, nunca resultado vazio silencioso. `dlg_clip.
ClipDialog`/`dlg_difference.DifferenceDialog`: dois seletores de camada com papéis
distintos (alvo vs. máscara/subtraendo), reaproveitando os mesmos widgets de SRC/estilo/
pasta das ferramentas anteriores.

### Buffer negativo (parte da F5)
`buffer_single()` passou a rejeitar só distância exatamente zero (antes rejeitava
qualquer valor ≤ 0); o spinbox da interface aceita negativo, com aviso de que só faz
sentido em polígonos (encolhe para dentro).

### Escopo não implementado nesta fase (com justificativa, conforme pedido)
- **Interseção** como ferramenta separada: o Recorte (F4) já cobre o caso prático de
  sobrepor dois polígonos nesta arquitetura (1 lugar = 1 camada de 1 feição) — uma
  ferramenta de "Interseção" produziria, na prática, o mesmo resultado.
- **Eliminar sobreposições**: pensada para editar uma camada com muitas feições vizinhas
  entre si (sliver polygons de uma digitalização em lote) — não se aplica à arquitetura
  deste plugin, onde cada lugar é uma camada isolada de 1 feição.

## Arquivos modificados/criados

Novos: `geoprocessing.py`, `dlg_buffer.py`, `dlg_union.py`, `dlg_split.py`, `dlg_clip.py`,
`dlg_difference.py`. Modificados: `layeractions.py` (5 novas ações de menu de contexto,
mais o helper `_selected_places()` compartilhado), `LEIAME.md`, `metadata.txt`.

**Intocados**: `storage.py` (nenhuma mudança de esquema foi necessária — Buffer/União/
Divisão/Recorte/Diferença usam o `create_place()` já existente, com o parâmetro `crs`
introduzido na v0.14.0), `places_model.py`, `widgets.py`, `maptools.py` (só consumido por
`dlg_split.py`, não alterado), toda a Régua, KML/KMZ, pastas e edição de vértices.

## Testes automatizados executados e resultados

**Executados de verdade** contra `C:\Program Files\QGIS 3.44.15\bin\python-qgis-ltr.bat`,
com o framework de Processing inicializado:

```
Ran 193 tests in 9.349s
OK
```

142 testes de lógica pura (sem PyQGIS) + 51 que exigem `qgis`/`processing`. Destaques dos
testes de integração: Buffer em CRS geográfico/projetado, pequeno/grande, com/sem
dissolve, rejeição de SRC geográfico; União de polígonos adjacentes e em CRS diferentes;
Divisão com linha que atravessa/não atravessa; Recorte e Diferença ponto-a-ponto e
linha-por-polígono; Buffer negativo encolhendo polígono; fim-a-fim de `BufferDialog`,
`UnionDialog`, `ClipDialog` e `DifferenceDialog` (sem `QgsMapCanvas` — por isso seguros
para a suíte permanente; `SplitDialog` e `FeatureDialog`, que usam canvas real, foram
verificados manualmente uma vez fora da suíte, por um crash de teardown do Qt já
documentado desde a v0.14.1).

Sem QGIS instalado: 142 testes passam, módulo de integração pulado (`SkipTest`).

`python -m py_compile` em todos os módulos `.py` do plugin → sem erro de sintaxe.

### Observação não bloqueante
Um aviso (não erro) do GDAL aparece ao gravar o resultado de Recorte/Diferença no
GeoPackage: `"A geometry of type MULTIPOLYGON is inserted into layer ... of geometry type
POLYGON"`. O driver grava corretamente mesmo assim (confirmado: área e validade da
geometria gravada estão certas nos testes) — `native:clip`/`native:difference` podem
devolver MultiPolygon mesmo quando o resultado prático é uma única região. Documentado
aqui; não bloqueia nenhuma funcionalidade.

## Teste de regressão

Toda a suíte anterior (desenho, Régua, pastas, KML/KMZ, SRC do Caminho, correção do
Círculo) foi reexecutada dentro dos 193 testes — nenhuma regressão.

## Roteiro de validação manual no QGIS 3.44.15 (nenhum executado pelo usuário até agora)

1. Selecionar um caminho e um polígono já existentes, botão direito > Gerar Buffer,
   escolher um SRC projetado, confirmar que o resultado aparece com a distância certa.
2. Testar Buffer negativo num polígono (distância negativa) e confirmar que ele encolhe.
3. Selecionar 2+ polígonos, Unir polígonos, confirmar a geometria combinada.
4. Botão direito num polígono > Dividir polígono, desenhar uma linha que atravessa,
   Pré-visualizar, Confirmar — checar que o original foi substituído pelas partes.
5. Repetir tentando dividir com uma linha que NÃO atravessa — confirmar o aviso, sem
   nenhuma alteração no polígono original.
6. Recortar com... um caminho usando um polígono como máscara; repetir para Diferença.
7. Confirmar em todos os casos que as camadas de origem (exceto a dividida, após
   confirmação) continuam no painel Camadas, intactas.
8. Regressão rápida: Régua, pastas, KML/KMZ, marcador/caminho/polígono normais.

## Problemas conhecidos / limitações deliberadas

- `SplitDialog` (desenho da linha de corte no mapa) não tem teste automatizado fim-a-fim
  na suíte permanente, pela mesma razão documentada desde a v0.14.1 para `FeatureDialog`
  (crash de teardown do Qt ao misturar `QgsMapCanvas` com o resto da suíte) — a lógica
  central (`geoprocessing.split_polygon`) está coberta.
- Aviso benigno do GDAL sobre MultiPolygon em camada Polygon (ver seção de testes).
- Interseção e Eliminar sobreposições não implementadas, com justificativa (ver seção de
  implementação).
- Fases G, H, I, J, K do Projeto Mestre ainda não implementadas.

## Commit Git de referência

`1636ad8` — "Versao 0.15.0: changelog da Fase F (geoprocessamento)" — HEAD no momento da
geração deste pacote. Marca de segurança: `pre-projeto-mestre-v0.14.1`, em `34314f7`
(0.14.1, ponto de partida desta fase).

## Caminho completo do ZIP

`C:\Users\Usuário\Desktop\ferramentas_terra\releases\v0.15.0\earth_tools_v0.15.0.zip`

## Confirmação de estrutura do pacote

- Integridade do ZIP (`zipfile.testzip()`): OK. 41 entradas (35 da 0.14.1 + 6 módulos
  novos de geoprocessamento).
- Sem `.git`, `.gitignore`, `__pycache__`, `.pyc`, `tests/` ou `.gpkg`.
- `earth_tools/metadata.txt`: `version=0.15.0`.
- `releases/v0.7.0/` a `v0.14.1/` confirmados intactos, nenhum arquivo sobrescrito.

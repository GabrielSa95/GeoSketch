# Relatório da versão 0.14.1 — Ferramentas Terra

**Data de geração:** 2026-10-30.

## Confirmação recebida sobre a versão anterior (0.14.0)

O usuário testou a 0.14.0 no QGIS 3.44.15 e relatou, com capturas de tela: (1) o Círculo
continua desenhando só a linha do raio, a circunferência completa não aparece, e o campo
**Área mostra NaN**; (2) a janela **Novo Caminho** continua sem nenhuma opção de SRC/CRS
— a correção anterior só tinha adicionado o seletor na aba Caminho da **Régua**, não na
janela de criação. As duas correções da v0.14.0 (Fases 3 e 4) não resolveram nenhum dos
dois problemas reais.

## Diagnóstico — causa raiz confirmada empiricamente, não só por leitura de código

Diferente de todas as rodadas anteriores deste projeto, **esta máquina tem uma instalação
real do QGIS 3.44.15** em `C:\Program Files\QGIS 3.44.15` (e também 3.40.14). Isso permitiu
rodar código contra o PyQGIS de verdade pela primeira vez, em vez de só ler o código-fonte
e presumir o comportamento da API — e foi assim que a causa raiz real foi encontrada.

**Causa raiz (Círculo e Área = NaN):** `QgsDistanceArea.computeSpheroidProject()` devolve
`(nan, nan)` **silenciosamente** — sem lançar exceção — quando o CRS de origem configurado
via `setSourceCrs()` é um CRS **projetado** (ex.: SIRGAS 2000/UTM, o caso comum no Brasil).
Confirmado com um script de diagnóstico rodado contra o QGIS real:

```
=== Teste 2: setSourceCrs com CRS projetado (EPSG:31983) ===
radius2 (deveria ser ~500, em metros): 499.6448978795185
computeSpheroidProject(center_utm, radius2, 90) = nan nan
```

A correção da v0.14.0 (Fase 4) presumia que uma falha de projeção lançaria uma exceção, e
protegia o anel inteiro com `try/except` por segmento — mas como a falha real nunca lança
exceção, essa defesa nunca disparava. O raio (`measureLine()`) funciona corretamente em
qualquer CRS (confirmado), por isso "Raio" e "Circunferência" mostravam valores plausíveis
— só a construção do **anel** (72 chamadas a `computeSpheroidProject`) voltava toda em NaN,
tornando a geometria do círculo inválida: daí a circunferência não aparecer e a Área
(`QgsDistanceArea.measureArea` sobre uma geometria com coordenadas NaN) dar NaN.

**Mesma causa raiz encontrada numa função vizinha, não relacionada ao círculo:**
`utils.project_point()` (usada por `widgets.VertexEntryPanel._add_by_distance_azimuth()`,
a aba "Adicionar por medida" de Novo Caminho/Novo Polígono) tinha o mesmo padrão exato:

```
=== project_point em CRS projetado (EPSG:31983) ===
resultado: <QgsPointXY: POINT(nan nan)> | x= nan | y= nan
CONFIRMADO: NaN devolvido como ponto 'valido' (nao None) - bug real
```

Qualquer projeto com SRC projetado (o caso comum) teria um vértice `NaN` inserido
silenciosamente na geometria ao usar distância+azimute — o `point is None` check em
`widgets.py` não pega isso, porque `QgsPointXY(nan, nan)` não é `None`.

**Problema 2 (Novo Caminho sem SRC):** confirmado por leitura de `dlg_feature.py` — a
v0.14.0 só tinha tocado `dlg_ruler.py` (a aba Caminho da Régua). A janela "Novo Caminho"
(`FeatureDialog`, `kind="line"`), que é o fluxo mais comum de criar um caminho, nunca
recebeu o seletor.

## Correções implementadas

**Círculo e project_point (`utils.py`)**
- `circle_points()` e `project_point()`: a projeção geodésica agora roda **sempre** com
  uma `QgsDistanceArea` configurada em **WGS84** internamente — confirmado correto em 5
  cenários reais (geográfico/projetado, raio pequeno/grande) — e o resultado é
  transformado de volta para o CRS de origem (`QgsCoordinateTransform`) antes de devolver.
  O raio continua medido uma única vez no CRS nativo via `measureLine()` (já correto,
  confirmado; não precisa ser remedido).
- Verificação explícita de `math.isnan()` por ponto/segmento, já que a falha original não
  lançava exceção — nenhuma defesa baseada só em `try/except` seria suficiente.
- `maptools.display_points()` já não caía mais para `[centro, borda]` desde a v0.14.0;
  mantido.

**Novo Caminho (`dlg_feature.py`, `widgets.py`)**
- `widgets.CrsRow` ganha o parâmetro opcional `label` (reaproveitado pela Régua e pelo
  Novo Caminho, cada um com seu próprio texto).
- `FeatureDialog.__init__`: novo `self.crs_row` (só para `kind == "line"`), posicionado
  logo após a caixa de aderência, antes das abas — começa no SRC do projeto.
- `_build_geometry()` passa a devolver `(geometry, crs)`: quando o SRC escolhido difere do
  CRS do canvas, os pontos são **de fato transformados** via `QgsCoordinateTransform`
  antes de montar a geometria — confirmado contra o QGIS real (ver seção de testes):
  coordenadas em graus tornam-se coordenadas em metros ao escolher um SRC UTM.
- `_save()` propaga esse CRS para `storage.create_place(..., crs=save_crs)` (parâmetro já
  existente desde a Fase 3/v0.14.0).

## Arquivos modificados

`utils.py`, `dlg_feature.py`, `widgets.py`, `LEIAME.md`, `metadata.txt`,
`tests/test_regression_static.py`, `tests/test_qgis_integration.py`. Nenhum outro módulo
foi tocado (confirmado: `maptools.py`, `storage.py`, `dlg_ruler.py` e todo o resto
permanecem exatamente como na v0.14.0).

## Testes automatizados executados e resultados

**Diferente de todas as rodadas anteriores, os testes que dependem do PyQGIS foram
EXECUTADOS DE VERDADE nesta rodada**, usando a instalação real do QGIS 3.44.15 encontrada
na máquina:

```
& "C:\Program Files\QGIS 3.44.15\bin\python-qgis-ltr.bat" -m unittest discover -s tests -v
...
Ran 136 tests in 1.608s
OK
```

(136 = 116 de lógica pura + 20 que precisam do módulo `qgis`.) Destaques:

- **Reprodução exata do bug original**: círculo pequeno em CRS projetado (EPSG:31983)
  devolvendo anel válido, sem NaN, com área correta (erro < 1% — a aproximação esperada de
  um polígono de 72 lados) — onde antes devolvia `(nan, nan)`.
- Círculo pequeno/grande em CRS geográfico e projetado; `project_point()` em CRS
  projetado e geográfico; transformação de coordenadas efetiva (não só a etiqueta do CRS)
  no Caminho; compatibilidade da geometria gravada com o Buffer; reabertura da camada
  preservando o CRS gravado.
- **Fluxo completo da janela real "Novo Caminho"** (`FeatureDialog`, com um `QgsMapCanvas`
  de verdade e um `iface` simulado): confirmado que `self.crs_row` existe, começa no SRC
  do projeto, e que `_build_geometry()` realmente transforma as coordenadas ao escolher
  outro SRC — verificado manualmente contra o QGIS real (fora da suíte permanente; ver
  nota abaixo) com resultado:
  ```
  === Apos escolher EPSG:31983 ===
  crs2: EPSG:31983
  geom2 primeiro ponto (deveria estar em metros UTM, nao graus):
  <QgsPointXY: POINT(295007.82751287776045501 7455081.89574041403830051)>
  ```
- Dois bugs de isolamento encontrados e corrigidos **nos próprios testes** (não no
  plugin): `QgsProject.instance().clear()` deixava o CRS do projeto inválido para o teste
  seguinte; e o `sys.path` apontava para dentro de `earth_tools/`, forçando um import
  relativo (`from . import utils`) a falhar fora do contexto de pacote.

`python -m py_compile` em todos os módulos `.py` do plugin → sem erro de sintaxe (rodado
tanto no Python padrão quanto no Python do QGIS).

**Nota sobre a suíte permanente vs. o teste manual do Novo Caminho:** um teste automatizado
que constrói `FeatureDialog` com um `QgsMapCanvas` real foi escrito e executado com sucesso
(resultado colado acima), mas construí-lo junto com o resto da suíte (136 testes, muitos
outros widgets Qt) provoca um **crash nativo de teardown do Qt na saída do processo** —
depois de `Ran 139 tests ... OK` já ter sido impresso, não uma falha de teste. Para manter
o código de saída da suíte permanente confiável (0, sempre), esse cenário específico foi
removido da suíte e verificado manualmente uma vez (resultado acima, real e reproduzível);
a lógica central (transformação + CRS gravado) continua travada por testes permanentes que
não usam `QgsMapCanvas` (`CrsDoCaminhoTests`).

**Sem QGIS instalado** (ambiente padrão, sem a pasta QGIS): 116 testes passam, o módulo de
integração é pulado (`SkipTest`), como nas versões anteriores — nada regrediu nesse modo.

## Teste de regressão

Reexecutados dentro da suíte de 136: `test_geometry_rules.py`, `test_measure_rules.py`,
`test_folder_rules.py`, `test_kml_io.py`, `test_export_rules.py`,
`test_regression_static.py` (inclusive os testes da v0.14.0 — abas 3D, barra simplificada,
histórico de imagens suspenso). Nenhuma regressão: desenho de linhas/polígonos, edição de
vértices, aderência, desfazer/refazer, pastas e subpastas, KML/KMZ e GeoPackage continuam
cobertos e passando.

## Roteiro de validação manual no QGIS 3.44.15 (nenhum executado pelo usuário até agora)

`ROTEIRO_VALIDACAO_MANUAL_v0.14.0.md` (raiz do projeto) foi atualizado com os itens
específicos desta correção (círculo sem NaN, campo de SRC em Novo Caminho). **Esta versão
não está aprovada** até o usuário confirmar manualmente:

1. Círculo: circunferência completa aparece (não só a linha do raio); Área **não** mostra
   NaN; valores de raio/circunferência/área coerentes entre si.
2. Testar o Círculo especificamente com o **projeto em um SRC projetado** (ex.: SIRGAS
   2000/UTM) — o cenário exato relatado — não só em WGS84.
3. Janela **Novo Caminho**: campo "SRC/CRS da camada de saída" visível, mostrando o SRC do
   projeto; escolher outro SRC, desenhar, salvar, e confirmar no painel Camadas que a
   camada salva está de fato no SRC escolhido (Propriedades > Informações).
4. Usar o caminho salvo em SRC projetado na ferramenta **Buffer** do QGIS.
5. Aba "Adicionar por medida" (distância/azimute) em Novo Caminho/Novo Polígono, com o
   projeto em SRC projetado — confirmar que o vértice aparece na posição esperada (não
   em branco, não fora do mapa).
6. Regressão rápida: marcador, polígono, pastas, KML/KMZ, edição de vértice.

## Problemas conhecidos / limitações deliberadas

- O teste fim-a-fim automatizado da janela "Novo Caminho" não ficou na suíte permanente
  por instabilidade de teardown do Qt (ver seção de testes) — foi verificado manualmente
  com sucesso, mas depende de repetição manual se o código de `dlg_feature.py` mudar
  novamente no futuro.
- A aproximação poligonal do círculo (72 segmentos) tem um erro de área de ~0,13% frente
  ao círculo matemático exato — esperado e inerente a qualquer polígono regular inscrito;
  não é um defeito.

## Commit Git de referência

`34314f7` — "Versao 0.14.1: changelog da correcao critica Circulo/Novo Caminho" — HEAD no
momento da geração deste pacote, árvore de trabalho limpa. Commits desta correção, em
ordem: `68f4760` (Correção 1 — causa raiz do Círculo/project_point), `a983f01` (Correção 2
— SRC no Novo Caminho), `4d99f1b` (testes executados contra QGIS real), `5ffd978`
(documentação), `34314f7` (versão). Marca de segurança desta rodada:
`pre-correcao-circulo-caminho-v0.14.0`, em `339bdeb` (0.14.0, ponto de partida).

## Caminho completo do ZIP

`C:\Users\Usuário\Desktop\ferramentas_terra\releases\v0.14.1\earth_tools_v0.14.1.zip`

## Confirmação de estrutura do pacote

- Integridade do ZIP (`zipfile.testzip()`): OK.
- Raiz única `earth_tools/`, sem pasta duplicada. 35 entradas (mesmo conjunto da 0.14.0).
- Sem `.git`, `.gitignore`, `__pycache__`, `.pyc`, `tests/` ou `.gpkg`.
- `earth_tools/metadata.txt`: `version=0.14.1`.
- Confirmado dentro do ZIP: `dlg_feature.py` contém `CrsRow`; `utils.py` contém
  `da_wgs.computeSpheroidProject` (a correção real, não só a intenção documentada).
- `releases/v0.7.0/` a `v0.14.0/` confirmados intactos, nenhum arquivo sobrescrito.

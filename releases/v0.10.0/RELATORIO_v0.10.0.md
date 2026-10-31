# Relatório da versão 0.10.0 — Ferramentas Terra

**Data de geração:** 2026-10-24.

## Confirmação recebida sobre a versão anterior (0.9.0)

O usuário confirmou validação manual real no QGIS 3.44.15 para a 0.9.0, com os testes
da Fase B aprovados, antes de iniciar esta fase.

## Auditoria prévia (preparação obrigatória)

Antes de escrever código novo, reli por completo `maptools.py`, `vertexedit.py` e
`dlg_ruler.py` para confirmar o que já existia:

- **Já implementado e preservado sem reescrita:** seleção/arraste/exclusão de vértice,
  extensão a partir do último vértice, validação de vértices distintos, atualização de
  medidas em tempo real, Ctrl+Z/Ctrl+Y persistindo no GeoPackage (via
  `geometry_rules.UndoStack`, já confirmado funcionando pelo usuário na 0.8.0), e o
  comportamento isolado do círculo e da Régua.
- **Único gap real encontrado em C3:** `VertexEditTool._refresh()` desenhava todos os
  vértices na mesma cor — sem destaque do vértice em arraste, ao contrário de
  `maptools.DrawTool` (que já tinha essa cor desde a 0.7.0). Corrigido.
- **Gap documentado em C4, não implementado por decisão de escopo:** Ctrl+Z/Ctrl+Y cobre
  edição de vértice dentro de uma sessão de desenho/edição já aberta. **Não existe**
  desfazer para criar ou excluir uma feição inteira (isso exigiria uma lixeira/
  versionamento do GeoPackage — mudança de arquitetura fora do pedido explícito desta
  fase, não implementada sem aprovação).

## Resumo das funcionalidades implementadas

**C1 — Aderência inteligente**
- Checkbox "Aderência a vértices/segmentos" + tolerância em pixels, nas janelas de
  criação e edição (`widgets.SnapRow`), ligada a um novo módulo `snapping.py`.
- Usa `QgsSnappingUtils`/`QgsSnappingConfig` nativos do QGIS, numa instância PRÓPRIA —
  nunca escreve em `QgsProject.instance().snappingConfig()`, para não alterar o
  comportamento das ferramentas nativas de digitalização do QGIS como efeito colateral.
- Tolerância em pixels de tela (não em unidades do SRC): decisão deliberada e
  documentada, pelo mesmo motivo que o raio de captura de vértice já era em pixels desde
  a 0.7.0 — mantém o comportamento consistente em qualquer SRC/zoom.
- Marcador em X magenta mostra onde aderiria antes do clique.
- Aplica-se a marcador, linha e polígono; **não** se aplica ao círculo nem à Régua
  (`dlg_ruler.py` desliga explicitamente por padrão, preservando o comportamento
  existente, já que não há controle de aderência na interface da Régua).
- Cada chamada à API nativa está protegida por try/except com fallback para a API mais
  antiga e depois para "aderência desligada" — nunca quebra o desenho se a versão do
  QGIS tiver uma API um pouco diferente.

**C2 — Entrada numérica de medidas**
- Nova aba "Adicionar por medida" (linha/polígono) nas janelas de criação e edição, com
  dois modos: distância + azimute, ou coordenadas.
- Azimute: graus de 0 a 360, a partir do Norte geográfico, sentido horário — a MESMA
  convenção já usada no rumo da aba Linha da Régua (`dlg_ruler.py._bearing_text`).
- Cálculo geodésico sobre o elipsoide WGS84, reaproveitando `QgsDistanceArea.
  computeSpheroidProject` — a mesma função já usada em `utils.circle_points` desde antes
  desta fase. Funciona igual em SRC geográfico ou projetado, pelo mesmo motivo que o
  círculo já funciona hoje.
- O vértice calculado entra pelo MESMO caminho de um clique real
  (`DrawTool.add_vertex`/`VertexEditTool.add_vertex`): undo, atualização de medidas e
  prévia, e gravação no GeoPackage (na edição), sem lógica paralela arriscada — conforme
  pedido explicitamente ("implemente primeiro uma etapa funcional e bem testada").

**C3 — Precisão na edição**
- Corrigido o único gap encontrado (destaque visual do vértice em arraste em
  `VertexEditTool`). Todo o resto já estava correto e não foi reescrito.

**C4 — Desfazer e refazer**
- Auditoria concluída, sem necessidade de código novo. Limitação de escopo (criação/
  exclusão de feição inteira) documentada acima e no `LEIAME.md`/changelog.

## Arquivos modificados/criados

Novos: `snapping.py`, `measure_rules.py`, `tests/test_measure_rules.py`.
Modificados: `utils.py` (`project_point`, `to_meters`), `maptools.py` (aderência,
`add_vertex`), `vertexedit.py` (aderência, `add_vertex`, destaque do vértice em arraste),
`widgets.py` (`SnapRow`, `VertexEntryPanel`), `dlg_feature.py`, `dlg_edit.py`,
`dlg_ruler.py` (desliga aderência por padrão), `LEIAME.md`, `metadata.txt`.

## Testes automatizados executados e resultados

`python -m unittest discover -s tests` → **41/41 testes passaram**: os 31 anteriores
(regressão confirmada) + 10 novos em `tests/test_measure_rules.py` (conversão de unidade
para metros, incluindo ida-e-volta com o fator da tabela, unidade desconhecida, zero; e
normalização de azimute, incluindo 360°, valores acima de 360° e negativos).
`python -m py_compile` em todos os 20 módulos `.py` → sem erro de sintaxe.
Validação de `metadata.txt`: campos obrigatórios presentes, `version=0.10.0`.

**O que não pôde ser automatizado:** toda a lógica que depende de `QgsSnappingUtils`,
`QgsMapTool`, eventos de mouse reais e `QgsDistanceArea.computeSpheroidProject` precisa
do PyQGIS, indisponível neste shell. A lógica pura extraída (`measure_rules.py`) é a
única parte desta fase testável sem o QGIS — mesma limitação já registrada nos
relatórios anteriores.

## Testes manuais pendentes no QGIS (nenhum executado até agora)

1. Aderência a ponto: criar um marcador próximo a outro já existente e confirmar que o
   clique adere exatamente ao vértice dele, com o X magenta aparecendo antes de clicar.
2. Aderência a vértice: desenhar um polígono com um vértice encostado no vértice de um
   polígono vizinho já salvo.
3. Aderência a segmento: encostar um vértice novo no meio de uma linha/borda existente
   (não num vértice dela).
4. Geometria distante: confirmar que nada adere quando não há nada dentro da tolerância.
5. Aderência desativada: desmarcar a caixa e confirmar que o clique cai exatamente onde
   o cursor está, sem ajuste.
6. Mudar o SRC do projeto (geográfico ↔ projetado) e confirmar que a tolerância em
   pixels continua se comportando igual (mesmo raio de captura na tela).
7. Entrada numérica: adicionar um vértice por distância+azimute e confirmar o ponto
   resultante contra uma medição manual (ex.: na Régua, em linha reta entre os dois
   pontos, comparando distância e rumo).
8. Entrada numérica por coordenadas: digitar uma lat/lon conhecida e confirmar a posição.
9. Confirmar que o vértice adicionado por medida aparece na pilha de desfazer (Ctrl+Z).
10. Reexecutar o roteiro de validação das fases anteriores (A, B) para confirmar que nada
    regrediu: desenho, edição de vértices, Ctrl+Z/Y, pastas, régua e círculo.

## Problemas conhecidos / limitações deliberadas

- Ctrl+Z/Ctrl+Y não desfazem a criação nem a exclusão de uma feição inteira — só edições
  de vértice dentro de uma sessão já aberta. Documentado, não implementado por decisão de
  escopo (exigiria uma arquitetura de lixeira/versionamento do GeoPackage).
- A aderência depende da API `QgsSnappingUtils`/`QgsSnappingConfig`, que mudou de forma
  entre versões do QGIS. O código tenta a API nova e cai para a antiga; se nenhuma
  funcionar na versão instalada, a aderência simplesmente fica desativada (com um
  registro no painel de diagnóstico) em vez de quebrar o desenho — mas o comportamento
  exato só é confirmável no QGIS 3.44.15 real.
- Círculo e Régua não têm controle de aderência na interface, por decisão de preservar o
  comportamento existente deles sem introduzir uma mudança não solicitada.
- Mesma limitação já registrada nos relatórios anteriores: não foi possível validar o
  carregamento do plugin via Python embutido do QGIS nesta máquina.

## Commit Git de referência

`d098a7e` — "Versao 0.10.0: changelog da Fase C" — HEAD no momento da geração deste
pacote, árvore de trabalho limpa.

## Caminho completo do ZIP

`C:\Users\Usuário\Desktop\ferramentas_terra\releases\v0.10.0\earth_tools_v0.10.0.zip`

## Confirmação de estrutura do pacote

Validado programaticamente nesta tarefa, com o ZIP gerado primeiro em arquivo temporário
e só movido para `releases/v0.10.0/` depois de passar todas as checagens:
- Integridade do ZIP (`zipfile.testzip()`): OK.
- Raiz única `earth_tools/`, sem pasta duplicada `earth_tools/earth_tools/`.
- 30 entradas, incluindo `snapping.py` e `measure_rules.py`.
- Sem `.git`, `.gitignore`, `__pycache__`, `.pyc`, `tests/` ou qualquer `.gpkg`.
- `earth_tools/__init__.py` contém `def classFactory(iface)`.
- `earth_tools/metadata.txt` contém todos os campos obrigatórios, `version=0.10.0`.
- `releases/v0.7.0/`, `v0.8.0/` e `v0.9.0/` confirmados intactos.

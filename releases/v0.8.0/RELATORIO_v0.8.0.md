# Relatório da versão 0.8.0 — Ferramentas Terra

**Data de geração:** 2026-10-24.

## Resumo das funcionalidades implementadas

Fase A do plano de evolução "estilo Google Earth Pro":

- Desfazer/Refazer (`Ctrl+Z` / `Ctrl+Y` ou `Ctrl+Shift+Z`) para operações de vértice
  (adicionar, arrastar, apagar), tanto durante a **criação** de linha/polígono
  (`maptools.py`) quanto na **edição de um lugar já existente** (`vertexedit.py`). Nesse
  segundo caso, desfazer/refazer regrava a geometria no GeoPackage a cada passo, pelo
  mesmo caminho seguro de commit usado em `_save()` — não é só um efeito visual.
- Lógica de pilha de desfazer/refazer extraída para uma classe `UndoStack` compartilhada
  em `geometry_rules.py`, para não duplicar o mesmo comportamento em dois arquivos.
- Novo botão "Ir para coordenadas" (`dlg_goto.py`, novo): digita latitude/longitude e
  centraliza o mapa.
- Nova ação "Ir para" no menu de botão direito dos lugares (`layeractions.py`): amplia o
  mapa até a feição selecionada, reaproveitando o zoom nativo do QGIS
  (`iface.actionZoomToLayer()`), que já trata bem o caso de uma feição pontual.
- Novo botão de tela cheia na barra de ferramentas (`earth_tools.py`): reaproveita a ação
  nativa do QGIS (`iface.actionToggleFullScreen()`) em vez de reimplementar um modo de
  visualização ampliada próprio.
- Diagnóstico: falhas de gravação/exclusão (já tratadas desde a 0.7.0) agora também ficam
  registradas no painel nativo "Mensagens de registro" do QGIS (`utils.log`), além do
  aviso na tela — complementa, não substitui, os avisos existentes.

## Arquivos modificados/criados nesta versão

Modificados: `maptools.py`, `vertexedit.py`, `geometry_rules.py`, `earth_tools.py`,
`layeractions.py`, `utils.py`, `storage.py`, `tests/test_geometry_rules.py`,
`metadata.txt`.
Novos: `dlg_goto.py`, `icons/goto.svg`.

## Testes automatizados executados e resultados

`python -m unittest discover -s tests` → **20/20 testes passaram**: os 13 testes da
versão anterior (contagem/remoção de vértices) + 7 testes novos da classe `UndoStack`
(desfazer sem histórico, refazer sem histórico, restaurar estado anterior, ida-e-volta
undo→redo, limpeza do redo ao surgir uma ação nova, limite de profundidade da pilha,
cópia independente do snapshot).
`python -m py_compile` em todos os 13 módulos `.py` → sem erro de sintaxe.
Validação de `metadata.txt` via `configparser`: todos os campos obrigatórios presentes,
`version=0.8.0`.

## Testes manuais pendentes no QGIS

**Nenhum destes foi confirmado como executado pelo usuário até o momento deste
relatório** — ficam como roteiro de validação manual, pedido explicitamente ao usuário na
entrega da Fase A:

- Confirmar que a reinstalação a partir do ZIP carrega sem erro no QGIS 3.44.15.
- `Ctrl+Z`/`Ctrl+Y` repetidos durante a criação de um caminho/polígono (adicionar, mover,
  apagar vértice) — e confirmar que o atalho não é interceptado pelo Undo nativo do QGIS.
- `Ctrl+Z` na janela Editar de um lugar salvo, confirmando que o mapa **e** o arquivo
  GeoPackage voltam ao estado anterior (não só a tela).
- Botão "Ir para coordenadas" e ação "Ir para" (inclusive sobre um marcador/ponto).
- Botão de tela cheia na barra, comparado ao item equivalente do menu Ver.
- Forçar uma falha de gravação (ex.: arquivo aberto em outro programa) e confirmar o
  registro em Ver → Painéis → Mensagens de registro → aba "Ferramentas Terra".

## Problemas conhecidos

- **Risco não verificado:** a suposição de que `Ctrl+Z`/`Ctrl+Y` chegam até a ferramenta
  de mapa (em vez de serem interceptados pelo `QAction` nativo de Undo/Redo do QGIS)
  parte do fato de que, durante o uso dessas ferramentas, nenhuma camada fica em sessão
  de edição aberta — o que mantém a ação nativa desabilitada. Isso é uma inferência sobre
  o comportamento do QGIS, não uma observação direta; só o teste manual confirma.
- Validação de carregamento real do plugin via Python embutido do QGIS não foi concluída
  nesta máquina (mesma limitação de DLLs já registrada no relatório da 0.7.0).
- Nenhuma funcionalidade das Fases B–F (pastas persistentes, KML/KMZ, imagens de
  satélite, 3D) foi implementada; esta versão cobre só a Fase A.

## Commit Git de referência

`1220acf` — "Versao 0.8.0: changelog da Fase A" — HEAD no momento da geração deste
pacote, árvore de trabalho limpa (`git status` sem pendências).

## Caminho completo do ZIP

`C:\Users\Usuário\Desktop\ferramentas_terra\releases\v0.8.0\earth_tools_v0.8.0.zip`

## Confirmação de estrutura do pacote

Validado programaticamente nesta tarefa:
- Integridade do ZIP (`zipfile.testzip()`): OK.
- Raiz única `earth_tools/`, sem pasta duplicada `earth_tools/earth_tools/`.
- 23 entradas, incluindo `dlg_goto.py` e `icons/goto.svg`.
- Sem `.git`, `.gitignore`, `__pycache__`, `.pyc`, `tests/` ou qualquer `.gpkg`.
- `earth_tools/__init__.py` contém `def classFactory(iface)`.
- `earth_tools/metadata.txt` contém todos os campos obrigatórios, `version=0.8.0`.

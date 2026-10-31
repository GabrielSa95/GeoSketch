# Roteiro de validação manual — v0.14.0 (QGIS 3.44.15)

Este roteiro cobre só o que mudou nas Fases 2–6 (reescopo: régua, SRC do caminho,
círculo, simplificação da interface). Não é um teste de regressão completo do
plugin — a lista de "continuam funcionando" no fim cobre o que precisa só de uma
checagem rápida, não um roteiro passo a passo.

Pré-requisito: instalar o ZIP de `releases/v0.14.0/earth_tools_v0.14.0.zip` num
QGIS 3.44.15 limpo (ou com uma versão anterior do plugin desinstalada antes).

Marque cada item como OK / FALHOU ao executar. Não marque como aprovado sem
executar de fato — se algum item falhar, pare e registre o comportamento
observado antes de continuar.

## 1. Histórico de imagens suspenso

- [ ] Abrir a barra **Ferramentas Terra**: não deve haver nenhum botão/ícone de
  "Imagens de satélite".
- [ ] Menu **Vetor > Ferramentas Terra**: não deve haver nenhuma entrada de
  imagens de satélite, Sentinel-2 ou Landsat.
- [ ] Com o **Painel de Mensagens de registro** aberto (Ver > Painéis), usar o
  plugin normalmente por alguns minutos (desenhar, salvar, abrir pastas) e
  confirmar que nenhuma mensagem de rede relacionada a Earth Search/STAC/
  Sentinel/Landsat aparece.
- [ ] (Opcional, se quiser confirmar isolamento de rede) Desconectar a internet
  e repetir o uso normal do plugin — nada deve falhar por falta de conexão,
  porque nenhuma funcionalidade restante depende de rede.

## 2. Régua — aba Caminho com SRC/CRS

- [ ] Abrir a **Régua**, ir para a aba **Caminho**.
- [ ] Confirmar que aparece um seletor **"SRC do caminho"** mostrando o SRC do
  projeto atual (código EPSG + nome), igual ao seletor de SRC usado no Buffer
  (Processar > Vetor Geral > Buffer).
- [ ] Clicar no seletor e escolher um **SRC diferente, projetado em metros**
  (ex.: SIRGAS 2000 / UTM 23S — EPSG:31983, se a área de trabalho for
  compatível). Confirmar que o seletor nativo do QGIS abre e permite buscar
  por nome ou código.
- [ ] Desenhar um caminho de 3–4 vértices no mapa (clique simples por vértice,
  botão direito ou duplo clique para encerrar).
- [ ] Confirmar que o campo **Comprimento** mostra um valor plausível (não em
  branco, não zero) e que trocar a unidade (metros/km/pés) no combo ao lado
  não altera o SRC escolhido no seletor.
- [ ] Clicar em **Salvar**, dar um nome, confirmar.
- [ ] No painel **Camadas**, clicar com o botão direito na camada salva >
  **Propriedades > Informações** (ou o SRC mostrado no rodapé ao selecionar a
  camada) e confirmar que o SRC gravado é **exatamente o escolhido no
  seletor**, não o do projeto nem WGS84 (a menos que tenha escolhido WGS84
  de propósito).
- [ ] Repetir sem tocar no seletor (deixando o padrão = SRC do projeto): o
  caminho deve salvar normalmente, sem erro, com o SRC do projeto.

## 3. Caminho + Buffer

- [ ] Com a camada de caminho salva no passo anterior (num SRC projetado em
  metros), abrir **Processar > Caixa de ferramentas > Vetor Geral > Buffer**.
- [ ] Selecionar essa camada como **Camada de entrada**.
- [ ] Confirmar que o campo de distância aceita um valor em **metros** (ex.:
  `10`) sem exigir conversão manual, e que o resultado do Buffer aparece como
  uma faixa de ~10 m ao redor do caminho, visualmente coerente no mapa (não
  um buffer gigante ou minúsculo por confusão de unidade/grau).

## 4. Círculo — circunferência completa

- [ ] Na Régua, ir para a aba **Círculo**.
- [ ] Clicar para definir o **centro**.
- [ ] Mover o mouse: a prévia deve mostrar uma **circunferência inteira**
  acompanhando o raio (não só uma linha do centro até o cursor).
- [ ] Clicar de novo para fixar a **borda** (raio).
- [ ] Confirmar que o círculo completo (contorno + preenchimento leve)
  permanece desenhado no mapa, não apenas a linha pontilhada do raio.
- [ ] Conferir os valores de **Raio**, **Circunferência** e **Área** no
  painel — devem ser plausíveis e coerentes entre si (circunferência ≈
  2πraio; área ≈ πraio²).
- [ ] Aplicar **zoom in** e **zoom out** no mapa várias vezes: o círculo deve
  continuar aparecendo completo e sem deformação visível.
- [ ] Clicar em **Limpar**: o círculo (contorno, preenchimento e a linha do
  raio) deve desaparecer completamente do mapa.
- [ ] Desenhar outro círculo bem maior (ex.: vários quilômetros de raio, se a
  área de trabalho permitir) e confirmar que ainda aparece como um círculo
  reconhecível, sem "achatar" ou formar um polígono irregular.
- [ ] Clicar em **Salvar**, confirmar que a feição salva no painel Camadas
  também aparece como um círculo completo (não um polígono de 2 vértices).
- [ ] Fechar a janela da Régua com um círculo desenhado na tela: o círculo
  temporário deve sair do mapa (nenhuma geometria "fantasma" para trás).

## 5. Régua — abas restantes e Linha

- [ ] Confirmar que a Régua tem **exatamente 4 abas**: Linha, Caminho,
  Polígono, Círculo — sem "Caminho em 3D" nem "Polígono em 3D".
- [ ] Na aba **Linha**: clicar um primeiro ponto, depois um segundo ponto.
  Confirmar que aparece **uma única linha** entre os dois pontos (não dois
  marcadores separados sem conexão).
- [ ] Clicar em **Salvar**: no painel Camadas, abrir a tabela de atributos da
  camada salva e confirmar que há **uma única feição** (uma linha), não duas
  feições de ponto.
- [ ] Clicar em **Limpar**: a linha temporária deve sair do mapa.
- [ ] Repetir o mesmo desenho na aba **Polígono** (3+ cliques) e confirmar que
  perímetro e área continuam sendo calculados e salvos como antes (sem
  mudança de comportamento nesta aba).

## 6. Barra principal simplificada

- [ ] Confirmar que **não há** botão de **Tela cheia** na barra Ferramentas
  Terra.
- [ ] Confirmar que **não há** botão de **Pesquisar lugares** (ícone de lupa)
  na barra.
- [ ] Confirmar que o modo tela cheia nativo do QGIS continua funcionando pelo
  menu **Ver > Tela cheia** (ou atalho padrão do QGIS) — não foi removido do
  QGIS, só o botão duplicado saiu da barra do plugin.
- [ ] Confirmar que a pesquisa de atributos nativa do QGIS (painel Identificar
  resultados, pesquisa na tabela de atributos, etc.) continua funcionando
  normalmente — não foi afetada.

## 7. Regressão — funcionalidades preservadas (checagem rápida)

- [ ] Criar um **marcador**, um **polígono** e um **caminho** pelos botões da
  barra (não pela Régua) e confirmar que salvam normalmente.
- [ ] Criar uma **pasta** nova e mover um lugar para dentro dela.
- [ ] Editar vértices (arrastar, apagar com botão direito, Ctrl+Z/Ctrl+Y) de
  um caminho ou polígono já salvo.
- [ ] Importar um arquivo **KML/KMZ** de teste e confirmar que os elementos
  aparecem na árvore de camadas.
- [ ] Exportar uma pasta para **KML/KMZ** (menu Vetor > Ferramentas Terra, ou
  botão direito na pasta) e confirmar que o arquivo é gerado.
- [ ] Botão **"Ir para coordenadas"** e botão **"Ver no Google Maps"**
  continuam abrindo normalmente.
- [ ] Reabrir o projeto salvo e confirmar que pastas, marcadores, caminhos e
  polígonos (inclusive os criados nesta sessão de teste) continuam
  aparecendo corretamente.

## Registro do resultado

Depois de executar: preencher `releases/v0.14.0/RELATORIO_v0.14.0.md` com o
resultado real de cada seção (OK/FALHOU + observações), não com o resultado
esperado. Só depois disso a versão pode ser considerada validada.

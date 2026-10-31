# Roteiro de validação manual — v0.17.0 (QGIS 3.44.15)

Cobre a auditoria/reorganização de interface desta versão (menu de contexto
categorizado, barra de ferramentas, painel lateral de propriedades). Os roteiros
anteriores (`ROTEIRO_VALIDACAO_MANUAL_v0.14.0.md`/`v0.14.1.md`) continuam válidos para os
itens deles e não precisam ser repetidos se já foram confirmados.

Pré-requisito: instalar o ZIP de `releases/v0.17.0/earth_tools_v0.17.0.zip` num QGIS
3.44.15 limpo (ou atualizar uma instalação da 0.16.0 existente).

**Importante:** esta versão foi desenvolvida sem uma instalação local do QGIS disponível
no ambiente de implementação - só a auditoria estática (testes automatizados de
string/import/compilação) pôde ser executada. Os passos abaixo são a validação funcional
de verdade, pendente.

Marque cada item como OK / FALHOU ao executar de fato.

## 0. Preparação

- [ ] Abrir o QGIS 3.44.15, criar um projeto novo.
- [ ] Confirmar que o complemento carrega sem erro (**Complementos > Gerenciar e Instalar
  Complementos**, aba Instalados - "Ferramentas Terra" aparece marcado, versão 0.17.0).
- [ ] Abrir o **Painel de mensagens de registro do Python** (ou o console) e confirmar
  **nenhum erro/traceback** durante o carregamento.
- [ ] Criar ao menos um Marcador, um Caminho e um Polígono com o plugin, para ter lugares
  reais para testar os itens abaixo.

## 1. Barra de ferramentas

- [ ] A barra "Ferramentas Terra" aparece com, nesta ordem: Selecionar (ícone nativo do
  QGIS, mesmo da barra de Digitalização), Marcador, Polígono, Caminho, Círculo, Régua,
  Calculadora, Estilos (paleta), Pasta, Google Maps, Ir para coordenadas, Exportar mapa.
- [ ] Passar o mouse sobre cada ícone mostra um tooltip em português explicando a função.
- [ ] Clicar em **Selecionar** ativa a mesma ferramenta nativa de seleção do QGIS (clicar
  numa feição no mapa a seleciona, igual a usar a barra de Digitalização nativa).
- [ ] Clicar em **Círculo** abre a janela Régua já na aba **Círculo** (não na aba Linha).
- [ ] Clicar em **Calculadora** abre a Calculadora de área e distância (igual à já
  existente no menu Vetor).
- [ ] Com um ou mais lugares selecionados no painel Camadas, clicar em **Estilos** abre o
  Gerenciador de Estilos já com esses lugares.
- [ ] Clicar em **Exportar mapa** abre a janela de Exportação de mapas (igual à já
  existente no menu Vetor).
- [ ] Nenhum botão que já existia antes desta versão (Marcador, Polígono, Caminho, Régua,
  Pasta, Google Maps, Ir para coordenadas) foi removido ou mudou de posição.

## 2. Menu de contexto da camada (botão direito num lugar, painel Camadas)

- [ ] O menu mostra um único submenu **"Ferramentas Terra"** (em vez das ~12 ações
  soltas de antes) e, fora dele, **Excluir** e o submenu **Adicionar** (inalterados).
- [ ] Abrindo o submenu "Ferramentas Terra": no topo, **Editar..., Ir para, Mover para
  pasta..., Estilo...**; depois um rótulo **"— GEOPROCESSAMENTO —"** (cinza, não
  clicável) seguido de Gerar Buffer..., Unir polígonos..., Dividir polígono..., Recortar
  com..., Diferença...; depois **"— MEDIÇÕES —"** com Calcular medidas...; depois
  **"— VALIDAÇÃO —"** com Validar geometria...; depois **"— EXPORTAÇÃO —"** com Salvar
  lugar como..., Enviar por e-mail..., Exportar mapa....
- [ ] Clicar nos rótulos de categoria (ex.: "— GEOPROCESSAMENTO —") não faz nada (estão
  desabilitados/acinzentados) - são só separadores visuais.
- [ ] Num **Polígono**: clicar em **Calcular medidas...** abre a Calculadora já com esse
  lugar escolhido no combo (não precisa selecionar manualmente).
- [ ] Clicar em **Validar geometria...** abre o Validador já com esse lugar marcado em
  "Lugares selecionados no painel Camadas (1)".
- [ ] Clicar em **Exportar mapa...** abre a Exportação de mapas já com "Ajustar ao lugar:
  <nome>" escolhido na extensão, e o nome do lugar preenchido em "Nome da
  propriedade/área".
- [ ] Nenhuma das ações antigas (Buffer, União, Divisão, Recortar, Diferença, Estilo,
  Salvar como, Enviar por e-mail, Editar, Ir para, Mover para pasta) parou de funcionar -
  testar pelo menos 2 ou 3 delas de ponta a ponta.
- [ ] Botão direito numa **pasta** no painel Camadas: "Importar/Exportar KML/KMZ para
  esta pasta" continua aparecendo (fora do submenu "Ferramentas Terra", que é só para
  camadas - comportamento inalterado).

## 3. Painel "Ferramentas Terra - Propriedades"

- [ ] **Vetor > Ferramentas Terra > Ferramentas Terra - Propriedades** mostra/esconde um
  painel lateral ancorável (testar arrastar para outra borda da tela, e também
  "flutuar").
- [ ] Com nenhum lugar selecionado no painel Camadas: o painel mostra a dica "Selecione
  um lugar criado pelo Ferramentas Terra..." e os 4 botões de ação ficam desabilitados.
- [ ] Selecionar um **Polígono** no painel Camadas: o painel preenche Nome, Tipo
  ("Polígono"), Área (em hectares), Perímetro (em metros), SRC e Validação ("OK" ou "N
  problema(s) encontrado(s)") - comparar a área/perímetro mostrados com os da Calculadora
  para o mesmo lugar (devem ser iguais).
- [ ] Selecionar um **Caminho**: o painel mostra Comprimento (Área/Perímetro ficam "-").
- [ ] Selecionar um **Marcador**: Área/Perímetro/Comprimento ficam "-", mas
  Nome/Tipo/SRC/Validação continuam preenchidos.
- [ ] Trocar a seleção para outro lugar atualiza o painel imediatamente, sem precisar
  clicar em nada.
- [ ] Editar a geometria de um lugar mostrado no painel (botão direito > Editar..., mover
  um vértice, salvar) e confirmar que a Área/Perímetro/Comprimento no painel refletem o
  novo valor depois de salvar (não precisa estar com o painel em foco).
- [ ] Alterar o estilo de um lugar mostrado no painel (botão direito > Estilo...) e
  confirmar que isso não quebra o painel (os valores de área/perímetro continuam
  corretos depois).
- [ ] Botão **Calcular medidas** do painel abre a Calculadora já no lugar mostrado.
- [ ] Botão **Alterar estilo...** do painel abre o Gerenciador de Estilos para o lugar
  mostrado.
- [ ] Botão **Validar geometria...** do painel abre o Validador já com o lugar marcado.
- [ ] Botão **Exportar geometria...** do painel abre o mesmo diálogo "Salvar lugar como"
  já existente, pré-preenchido com o nome do lugar.
- [ ] Excluir o lugar atualmente mostrado no painel (pelo painel Camadas): o painel volta
  ao estado "selecione um lugar", sem travar ou mostrar dado antigo.

## 4. Regressão geral

- [ ] Fechar e reabrir o QGIS com o mesmo projeto: os lugares, pastas, estilos e o painel
  lateral continuam funcionando normalmente (persistência via GeoPackage, inalterada).
- [ ] Nenhum erro/traceback aparece no console Python do QGIS durante todo o roteiro
  acima.
- [ ] Nenhuma ação aparece duplicada (nem no menu de contexto, nem no menu Vetor, nem na
  barra).

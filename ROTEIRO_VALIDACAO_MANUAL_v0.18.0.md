# Roteiro de validação manual — v0.18.0 (GeoSketch, ex-Ferramentas Terra)

Cobre a identidade visual GeoSketch e a remoção dos ícones de Calculadora/Estilos da
barra. Os roteiros anteriores (`ROTEIRO_VALIDACAO_MANUAL_v0.17.0.md`/`v0.17.1.md` e mais
antigos) continuam válidos para os itens deles - as funcionalidades em si não mudaram,
só o nome exibido e a remoção dos dois ícones.

Pré-requisito: instalar o ZIP de `releases/v0.18.0/earth_tools_v0.18.0.zip` num QGIS
3.44.15 (recomendado reinstalar do zero se a 0.17.x já estiver instalada, para garantir
que nenhum cache de interface antiga permaneça). Este ZIP já inclui a identificação
oficial (autor, ícone, descrição em português e o ajuste de `qgisMinimumVersion=3.44`).

## 0. Metadados e changelog (checagem nova desta etapa)

- [ ] Aba de detalhes do plugin no Gerenciador de Complementos mostra o **autor "Gabriel
  Alberto"**.
- [ ] A aba "Changelog"/histórico de versões do plugin **carrega e mostra texto** (não
  fica vazia nem gera erro) - esta etapa corrigiu um `%` não escapado em
  `metadata.txt` que podia quebrar a leitura desse campo pelo QGIS; confirmar que o
  changelog completo (da 0.6.0 até a 0.18.0) aparece, inclusive o trecho "corte
  cumulativo 2%-98%" (deve aparecer com um `%` só, não `%%`).
- [ ] Campo de versão mínima do QGIS exigida (se exibido na interface): 3.44.

## 1. Identidade visual

- [ ] **Gerenciador de Complementos** (Complementos > Gerenciar e Instalar Complementos
  > Instalados): o plugin aparece como **"GeoSketch"**, versão 0.18.0.
- [ ] O ícone exibido ao lado do nome "GeoSketch" na lista de Instalados é o **blob
  azul-turquesa** (não o ícone amarelo padrão do QGIS, nem o marcador/placemark usado
  antes). Clicar no plugin na lista e abrir a aba de detalhes: o mesmo ícone aparece
  ampliado, sem fundo quadrado/branco visível (confirma transparência real).
- [ ] Descrição exibida no Gerenciador de Complementos (resumo curto) está em
  **português** e corresponde ao texto: "Desenhe, meça e gerencie geometrias de
  propriedades rurais com praticidade, em um fluxo de trabalho inspirado no Google
  Earth, com salvamento automático em GeoPackage."
- [ ] Aba "Mais informações"/detalhes do plugin: a descrição completa (`about=`) aparece
  em português, nos 4 parágrafos esperados (criação/edição, ferramentas de
  desenho/medição/estilo/geoprocessamento, validação/exportação/KML, GeoPackage com
  pastas).
- [ ] Nenhum erro/traceback no console Python do QGIS ao carregar o complemento.
- [ ] A barra de ferramentas se chama **"GeoSketch"** (confirmar em **Ver > Barras de
  Ferramentas** - deve aparecer "GeoSketch", não mais "Ferramentas Terra").
- [ ] O menu **Vetor** mostra um submenu **"GeoSketch"** (não mais "Ferramentas Terra").
- [ ] Botão direito num lugar no painel Camadas: o submenu do menu de contexto se chama
  **"GeoSketch"**.
- [ ] Abrir qualquer janela do plugin (ex.: Novo Marcador, Régua, Gerar Buffer, Validar
  geometrias, Exportar mapa): o título da janela começa com **"GeoSketch - "**.
- [ ] Disparar qualquer mensagem de aviso/erro/sucesso do plugin (ex.: excluir um lugar,
  salvar com erro): o título da caixa de mensagem ou da barra de mensagens é
  **"GeoSketch"**.
- [ ] Painel lateral (Vetor > GeoSketch > alternar visibilidade): o título do painel é
  **"GeoSketch - Propriedades"**.

## 2. Remoção dos ícones de Calculadora e Gerenciador de Estilos

- [ ] A barra de ferramentas **não tem mais** ícone de Calculadora nem de paleta
  (Estilos) - confirmar visualmente contando os botões restantes.
- [ ] O menu **Vetor > GeoSketch** **não tem mais** a entrada "Calculadora de área e
  distância..." nem qualquer entrada de Estilos solta.
- [ ] Botão direito num lugar > submenu **GeoSketch**: a entrada **"Calcular
  medidas..."** continua presente e, ao clicar, abre a Calculadora normalmente, já com o
  lugar clicado escolhido no combo.
- [ ] Botão direito num lugar > submenu **GeoSketch**: a entrada **"Estilo..."**
  continua presente e, ao clicar, abre o Gerenciador de Estilos normalmente.
- [ ] Painel lateral de propriedades: os botões **"Calcular medidas"** e **"Alterar
  estilo..."** continuam funcionando (abrem as mesmas janelas).

## 3. Regressão - compatibilidade com lugares/presets já existentes

Este é o teste mais importante desta versão: confirma que o `CUSTOM_KEY` e o grupo de
`QSettings` não foram alterados.

- [ ] Abrir um projeto/GeoPackage criado por uma versão **anterior** (0.17.x ou mais
  antiga, com "Ferramentas Terra"): todos os lugares continuam sendo reconhecidos pelo
  plugin (aparecem com o submenu GeoSketch no menu de contexto, normalmente).
- [ ] Se já existiam presets de estilo salvos (Gerenciador de Estilos > Salvar como...)
  numa versão anterior: eles continuam aparecendo na lista de presets depois de
  atualizar para esta versão.
- [ ] Criar um novo lugar nesta versão, salvar o projeto, fechar e reabrir o QGIS: o
  lugar continua reconhecido normalmente.

## 4. Regressão geral

- [ ] Todas as ferramentas de desenho (marcador, polígono, caminho, círculo via Régua),
  edição, geoprocessamento (Buffer, União, Divisão, Recorte, Diferença), validação e
  exportação (mapa, KML/KMZ) continuam funcionando exatamente como antes.
- [ ] Nenhuma ação aparece duplicada em nenhum menu.
- [ ] Nenhum erro/traceback no console Python do QGIS durante todo o roteiro.

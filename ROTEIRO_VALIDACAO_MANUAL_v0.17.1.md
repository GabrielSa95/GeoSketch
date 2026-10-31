# Roteiro de validação manual — v0.17.1 (QGIS 3.44.15)

Cobre exclusivamente o ajuste pontual desta versão (unificação do submenu "Adicionar").
Os roteiros anteriores (`ROTEIRO_VALIDACAO_MANUAL_v0.17.0.md` e versões anteriores)
continuam válidos para os itens deles e não precisam ser repetidos se já foram
confirmados.

Pré-requisito: instalar o ZIP de `releases/v0.17.1/earth_tools_v0.17.1.zip` num QGIS
3.44.15 (ou atualizar uma instalação da 0.17.0 existente).

## 1. Submenu "Adicionar"

- [ ] Botão direito em qualquer camada vetorial (lugar do plugin ou não) no painel
  Camadas: o menu de contexto mostra **um único** item "Adicionar", com seta de
  submenu - não mais várias entradas repetindo "Adicionar".
- [ ] Abrir o submenu "Adicionar": contém, nesta ordem, as 6 opções: Pasta, Modelo de
  propriedade rural, Marcador de local, Caminho, Poligono, Sobreposicao de imagem - com
  os mesmos ícones de antes (pasta, pasta, marcador, caminho, polígono, sem ícone na
  última).
- [ ] Clicar em **Pasta**: cria uma pasta nova, igual a antes.
- [ ] Clicar em **Modelo de propriedade rural**: abre o diálogo de nome do imóvel e cria
  o modelo, igual a antes.
- [ ] Com uma pasta selecionada no painel Camadas, clicar em **Marcador de local**: abre
  a janela Novo Marcador com essa pasta como destino (confirma que
  `self._current_group()` continua funcionando no momento do clique).
- [ ] Clicar em **Caminho** e em **Poligono**: abrem as respectivas janelas de criação,
  também direcionadas à pasta/grupo atual quando houver uma selecionada.
- [ ] Clicar em **Sobreposicao de imagem**: abre o diálogo de escolha de arquivo de
  imagem, igual a antes.

## 2. Restante do menu de contexto (não deve ter mudado)

- [ ] O submenu **"Ferramentas Terra"** (categorizado: Geoprocessamento, Medições,
  Validação, Exportação) continua exatamente como na 0.17.0.
- [ ] **Excluir** continua na raiz do menu, fora de qualquer submenu.
- [ ] Os itens nativos do QGIS (Duplicar Camada, Remover Camada, Abrir Tabela de
  Atributos, Alternar Edição, Filtrar, SRC da Camada, Exportar, Estilos, Propriedades
  etc.) continuam na mesma posição e com a mesma aparência de sempre.

## 3. Regressão geral

- [ ] Nenhum erro/traceback no console Python do QGIS ao abrir o menu de contexto ou
  clicar em qualquer opção do submenu "Adicionar".
- [ ] A barra de ferramentas "Ferramentas Terra" e o menu Vetor > Ferramentas Terra
  continuam idênticos aos da 0.17.0.
- [ ] O painel lateral "Ferramentas Terra - Propriedades" (0.17.0) continua funcionando
  normalmente.

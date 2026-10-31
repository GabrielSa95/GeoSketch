# GeoSketch — organização do projeto

Este é o README de **desenvolvimento** (processo interno, em português). As instruções de
uso do plugin em si (instalação, botões, onde os dados ficam) estão em
`earth_tools/LEIAME.md` — esse arquivo é o que vai dentro do pacote instalável e o usuário
final vê. A apresentação pública em inglês (para o GitHub/repositório oficial de plugins
do QGIS) está em `README.md`, na raiz.

## Estrutura

```text
ferramentas_terra/
├── earth_tools/            # codigo-fonte do plugin
│   ├── __init__.py
│   ├── metadata.txt
│   ├── earth_tools.py
│   ├── LEIAME.md            # guia de uso em portugues, vai dentro do pacote
│   ├── tests/               # testes automatizados, nunca entram no pacote instalavel
│   └── ... demais modulos e icones
├── releases/                # um pacote por versao finalizada, nunca sobrescrito
│   ├── v0.7.0/
│   │   ├── earth_tools_v0.7.0.zip
│   │   └── RELATORIO_v0.7.0.md
│   └── v0.8.0/
│       ├── earth_tools_v0.8.0.zip
│       └── RELATORIO_v0.8.0.md
├── CHANGELOG.md
├── README.md                 # apresentacao publica em ingles (GitHub / repositorio QGIS)
├── LICENSE                   # GPL-2.0-or-later
└── DEVELOPMENT.md             # este arquivo
```

### Histórico Git

O repositório Git público (https://github.com/GabrielSa95/GeoSketch) vive na raiz do
projeto, com um histórico novo iniciado na publicação. O histórico interno de
desenvolvimento que existia antes disso (commits de auditoria/implementação de cada
fase, de 24/10/2026 a 30/10/2026, originalmente dentro de `earth_tools/.git`) foi
preservado como backup local, fora do repositório publicado, por conter o e-mail
pessoal do autor e mensagens de processo interno não destinadas ao público. Os
commits de referência citados nos relatórios de versão (`releases/vX.Y.Z/RELATORIO_vX.Y.Z.md`)
continuam conferíveis nesse backup local.

### Por que `tests/` não está na raiz

Os testes automatizados (`earth_tools/tests/test_geometry_rules.py`) testam módulos do
próprio plugin (`geometry_rules.py`) e já estão versionados junto com o código que
testam, com descoberta automática via `python -m unittest discover -s tests` executado
de dentro de `earth_tools/`. Duplicá-los na raiz criaria duas cópias para manter
sincronizadas sem benefício real.

### Origem dos recursos visuais

Os ícones SVG em `earth_tools/icons/` são de autoria própria do projeto (geometria
simples, sem marcador de licença de terceiros). O ícone oficial do complemento
(`earth_tools/icons/geosketch.png`, o "blob azul-turquesa") foi **gerado pelo ChatGPT, a
pedido do autor (Gabriel Alberto)**, conforme declarado por ele em 2026-10-31. Não é um
recurso de terceiros encontrado pronto na internet nem extraído de um banco de imagens -
é conteúdo gerado por IA, comissionado pelo autor especificamente para este projeto. O
arquivo original (`Blob azul-turquesa translúcido e brilhante.png`, na raiz, fora do
pacote instalável) e sua transparência RGBA real devem ser preservados sem reprocessamento
além do redimensionamento proporcional já documentado em
`releases/v0.18.0/RELATORIO_v0.18.0.md`.

## Como gerar uma nova versão

1. Decida a versão nova (`X.Y.Z`) e atualize `earth_tools/metadata.txt` (campo `version`
   e `changelog`) **só quando o trabalho da versão estiver de fato concluído**. Se
   `README.md`/`LICENSE` da raiz mudaram, copie para `earth_tools/README.md`/`LICENSE`
   também - o repositório oficial do QGIS espera README e LICENSE **dentro** do pacote.
2. Confirme que `git status` dentro de `earth_tools/` está limpo (sem mudança pendente) e
   faça um commit identificável se não estiver.
3. Rode os testes automatizados (`python -m unittest discover -s tests`) e o
   `py_compile` de todos os módulos; registre o resultado real.
4. Gere o ZIP para um arquivo **temporário**, valide (estrutura, integridade,
   `metadata.txt`, ausência de `.git`/`__pycache__`/`tests`/`.gpkg`), e só então mova
   para `releases/vX.Y.Z/earth_tools_vX.Y.Z.zip`. Nunca sobrescreva uma versão que já
   exista em `releases/` — se o diretório já existir, é um conflito a ser resolvido, não
   a ser ignorado.
5. Escreva `releases/vX.Y.Z/RELATORIO_vX.Y.Z.md` com o que foi de fato executado —
   nunca declare um teste manual no QGIS como feito se ele não ocorreu.
6. Atualize `CHANGELOG.md` com um resumo e o commit de referência.

## Requisitos para instalar o plugin

`qgisMinimumVersion=3.44` em `metadata.txt`. **Decisão tomada**: versões anteriores deste
projeto declaravam `3.22` com base numa afirmação ("testado em 3.34 LTR, 3.40 e 3.44")
que não tinha registro equivalente no `CHANGELOG.md` - só a 0.14.1+ registra testes
empíricos *confirmados* contra uma instalação real, especificamente **QGIS 3.44.15**. Por
exigência explícita do processo de publicação do QGIS (não declarar compatibilidade não
comprovada), o valor foi corrigido para `3.44`. Se o plugin for testado com sucesso numa
instalação mais antiga (3.22–3.40), isso é evidência válida para baixar o valor de novo -
documente o teste (versão exata do QGIS, data, resultado) antes de alterar
`qgisMinimumVersion`.

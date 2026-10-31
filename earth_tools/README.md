# GeoSketch

A QGIS plugin that brings a simple, Google Earth-style workflow to drawing, measuring
and managing field geometries: no need to create a layer, pick a CRS, or toggle editing
mode before you start. Formerly known as *Ferramentas Terra*.

> **Status: not yet published.** This repository is being prepared for submission to the
> [official QGIS Python Plugins Repository](https://plugins.qgis.org). See
> "Project status & pending items" below before treating anything here as released.

## Features

- **Drawing tools**: placemark, polygon, path and circle, with live measurements while
  drawing, vertex snapping, and undo/redo.
- **Ruler**: line, path, polygon and circle measurement tabs, with unit switching.
- **Geoprocessing**, backed by native QGIS Processing algorithms (never reimplemented):
  buffer (including negative/shrink buffers), union, split by line, clip, and difference.
- **Area/distance calculator** for any already-saved place.
- **Style manager** with reusable, named presets (shared across projects).
- **Geometry validator**: invalid/empty geometry, duplicate vertices, unclosed rings,
  out-of-bounds, and polygon overlap checks, with safe "fix as a new copy" (never
  overwrites the original).
- **Map export** to PDF/PNG via a real `QgsPrintLayout` (title, legend, scale bar, north
  arrow, CRS, area/perimeter) — preview opens the native QGIS Layout Designer.
- **KML/KMZ import and export**, including folder hierarchies.
- **Folder organization** for places, persisted inside the GeoPackage itself.
- A side panel showing live properties (name, type, area/perimeter/length, CRS,
  validation status) for the selected place.

Everything is saved automatically to a "My Places" GeoPackage next to your project.

## Requirements and compatibility

- `qgisMinimumVersion=3.44` (see `metadata.txt`).
- **Why 3.44 and not lower**: this project's own history records empirical,
  real-QGIS-install testing only against **QGIS 3.44.15** (see `CHANGELOG.md`, versions
  0.14.1+). Some code paths include `try`/`except` fallbacks for APIs available only from
  QGIS 3.32 onward, and the plugin previously declared `qgisMinimumVersion=3.22` based on
  an unverified claim — that claim could not be substantiated against this project's own
  test/changelog record, so the declared minimum was narrowed to the one version with
  actual proof. If you test successfully on an older 3.x release, that's useful evidence
  to lower this value again — see `DEVELOPMENT.md`.
- No third-party Python dependencies beyond what QGIS itself provides (PyQGIS, PyQt) —
  confirmed by inspecting every `import`/`from` statement in the source tree.
- Tested so far only on Windows. Linux/macOS compatibility is expected — the one place
  with OS-specific behavior (`layeractions.py`, "Send by email") explicitly branches on
  `sys.platform` for Windows/macOS/Linux — but has not been independently verified on
  Linux/macOS in this audit.

## Installation

1. In QGIS: **Plugins > Manage and Install Plugins > Install from ZIP**.
2. Select the release ZIP (see `releases/` for packaged versions of this repository, or
   the official repository listing once published).
3. Click **Install Plugin**.
4. The toolbar appears at the top. If it doesn't: **View > Toolbars > GeoSketch**.

For manual/offline installation, copy the `earth_tools` folder into your QGIS profile's
`python/plugins` directory (see `earth_tools/LEIAME.md` for exact paths per OS).

## Usage

See `earth_tools/LEIAME.md` for the full, detailed usage guide **in Portuguese**
(the plugin's interface and this guide are currently Portuguese-first; an English guide
is a pending item — see below).

## Version history

See `CHANGELOG.md` (repository root) for the full version history. Each packaged release
also has its own detailed audit report under `releases/vX.Y.Z/RELATORIO_vX.Y.Z.md`.

## Support and issue reporting

- Issue tracker: https://github.com/GabrielSa95/GeoSketch/issues
- See `DEVELOPMENT.md` for how versions are built, tested and packaged.

## License

GeoSketch is free software, licensed under the **GNU General Public License v2.0 or
later (GPL-2.0-or-later)** — see `LICENSE`. This plugin has no third-party Python
dependencies of its own; it relies on the QGIS/PyQGIS runtime it is installed into. The
project's own icons (`earth_tools/icons/*`) were authored for this project; none were
copied from a third-party icon set.

## Desenvolvimento e autoria

O GeoSketch é desenvolvido e mantido por Gabriel Alberto.

Durante o desenvolvimento do projeto foram utilizadas ferramentas de inteligência
artificial como apoio à programação, revisão de código, identificação de erros,
documentação e aprimoramento das funcionalidades.

A responsabilidade pelo projeto, suas decisões técnicas, manutenção e evolução é de seu
desenvolvedor.

## Project status & pending items

This project has not yet been published. `email=`, `homepage=`, `repository=` and
`tracker=` in `metadata.txt` now point to this repository. The following still need
real values or real-world confirmation before submission to the official QGIS Python
Plugins Repository:

- `experimental=True` in `metadata.txt` should only flip to `False` once the manual
  validation checklist (`ROTEIRO_VALIDACAO_MANUAL_v0.18.0.md`) has actually been run
  against a real QGIS install — it has not been, in this audit (no QGIS install is
  available in this development environment).
- Independent verification on Linux/macOS (see "Requirements and compatibility" above).

See `releases/v0.18.0/RELATORIO_v0.18.0.md` for the full rebranding audit, including what
changed, what was deliberately left unchanged for backward compatibility, and the
complete pending-items list.

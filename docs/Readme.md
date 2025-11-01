![version](https://img.shields.io/badge/version-0.1-blue.svg)
![date](https://img.shields.io/badge/date-01.11.2025-green.svg)
![status](https://img.shields.io/badge/status-development-yellow.svg)
![license](https://img.shields.io/badge/license-MIT-lightgrey.svg)

# Sphinx-Dokumentation

Erklärung der bereitgestellten Sphinx-Dokumentation für das Projekt `read_transactions_fm`.

***
## Contents



## Entwicklung



> **Annahmen**
>
> * Paketpfad: `src/read_transactions`
> * CLI-Modul: `read_transactions/cli.py`
> * Es existiert eine Funktion `build_parser()` in `cli.py`, die einen `argparse.ArgumentParser` zurückgibt.

---

### Verzeichnisstruktur

Konfigurationsdateien
```
read_transactions_fm/
  docs/
    conf.py             # -> allgemeine Konfiguration 
    index.md            # -> Haupteinstieg für die Doku
    cli.md              # -> CLI aus parser
  .github/
    workflows/
      sphinx.yml        # -> Konfiguration zur autom. Erzeugung bei Github
```

Zur Installation der erforderlichen Pakete (optional für Lokale Dooku):
```
requirements-docs.txt
```

---



### Installation

read_transactions lokal installieren, inkl. neues venv

```bash
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\\Scripts\\activate
pip install -e .
```

### Doku lokal bauen


requirements aus txt installoeren
````bash
pip install -r requirements-docs.txt
````

```bash
sphinx-build -b html docs docs/_build/html
```
Vorschau: öffne docs/_build/html/index.html

***

## GitHub einrichten

Aktion unter:  
`/.github/workflows/sphinx.yml`


### GitHub Pages aktivieren

1. Repo → **Settings** → **Pages**
2. **Source**: *Deploy from a branch*
3. **Branch**: `gh-pages` (root) → **Save**


***

## 7) Tipps & Troubleshooting

* **Importfehler bei AutoAPI**: Stelle sicher, dass `sys.path.append(os.path.abspath("../src"))` in `conf.py` gesetzt ist und dein Paket unter `src/read_transactions` liegt.
* **CLI-Seite leer**: Prüfe, ob `build_parser()` existiert und ohne Seiteneffekte importierbar ist. Externe Logik nicht im Import ausführen (nur in `if __name__ == "__main__":`).
* **Mehrsprachigkeit/Theme**: Du kannst jederzeit ein anderes Theme nutzen, z. B. `furo`. Für PDF-Ausgabe LaTeX-Toolchain installieren und `-b latex` bauen.
* **Automatischere API-Navigation**: `autoapi_keep_files = True` hilft beim Debuggen der generierten Seitenstruktur unter `docs/_autoapi/`.

Fertig! Sobald du die Dateien committest und pushst, baut die Action die HTML-Doku und veröffentlicht sie auf `gh-pages`. Öffne danach deine Projekt-URL `https://<dein-username>.github.io/<repo>/`.



***
## Versionshistorie

| Datum / Version   | Autor         | Bemerkung                               |
|-------------------|---------------|-----------------------------------------|
| 01.11.2025 / v0.1 | Tim Häberlein | Grundlegende Erstellung                 |
|                   |               |                                         |
|                   |               |                                         |
```{include} ../README.md
```

```{eval-rst}
.. include:: ../README.md
```

***
***

```{toctree}
:maxdepth: 2
:caption: Inhalt

cli
api/index
```


```{include} ../README.md
:start-after: <!-- docs:getting_started-start -->
:end-before: <!-- docs:getting_started-end -->
```

```{include} ../README.md
:start-after: <!-- docs:cli-start -->
:end-before: <!-- docs:cli-end -->
```

```{include} ../README.md
:start-after: <!-- docs:examples-start -->
:end-before: <!-- docs:example-end -->
```

```{include} ../README.md
:start-after: <!-- docs:installation-start -->
:end-before: <!-- docs:installation-end -->
```

## Automatische Generierung


Diese Website wird bei jedem Push automatisch aus dem Quellcode erzeugt und veröffentlicht:
- **API-Referenz**: via `sphinx-autoapi` aus den Docstrings unter `src/read_transactions`.
- **CLI-Hilfe**: via `sphinx-argparse` aus dem `argparse.ArgumentParser` in `read_transactions.cli`.



```{include} ../README.md
:start-after: <!-- docs:about-start -->
:end-before: <!-- docs:about-end -->
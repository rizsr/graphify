# Architecture

graphify is a Claude Code skill backed by a Python library. The skill orchestrates the library; the library can be used standalone.

## Pipeline

```
detect()  →  extract()  →  build_graph()  →  cluster()  →  analyze()  →  report()  →  export()
```

Each stage is a single function in its own module. They communicate through plain Python dicts and NetworkX graphs - no shared state, no side effects outside `graphify-out/`.

## Module responsibilities

| Module | Function | Input → Output |
|--------|----------|----------------|
| `detect.py` | `collect_files(root)` | directory → `[Path]` filtered list |
| `extract.py` | `extract(path)` | file path → `{nodes, edges}` dict |
| `build.py` | `build_graph(extractions)` | list of extraction dicts → `nx.Graph` |
| `cluster.py` | `cluster(G)` | graph → graph with `community` attr on each node |
| `analyze.py` | `analyze(G)` | graph → analysis dict (god nodes, surprises, questions) |
| `report.py` | `render_report(G, analysis)` | graph + analysis → GRAPH_REPORT.md string |
| `export.py` | `export(G, out_dir, ...)` | graph → Obsidian vault, graph.json, graph.html, graph.svg |
| `ingest.py` | `ingest(url, ...)` | URL → file saved to corpus dir |
| `cache.py` | `check_semantic_cache / save_semantic_cache` | files → (cached, uncached) split |
| `security.py` | validation helpers | URL / path / label → validated or raises |
| `validate.py` | `validate_extraction(data)` | extraction dict → raises on schema errors |
| `serve.py` | `start_server(graph_path)` | graph file path → MCP stdio server |
| `watch.py` | `watch(root, flag_path)` | directory → writes flag file on change |
| `benchmark.py` | `run_benchmark(graph_path)` | graph file → corpus vs subgraph token comparison |

## Extraction output schema

Every extractor returns:

```json
{
  "nodes": [
    {"id": "unique_string", "label": "human name", "source_file": "path", "source_location": "L42"}
  ],
  "edges": [
    {"source": "id_a", "target": "id_b", "relation": "calls|imports|uses|...", "confidence": "EXTRACTED|INFERRED|AMBIGUOUS"}
  ]
}
```

`validate.py` enforces this schema before `build_graph()` consumes it.

## Confidence labels

| Label | Meaning |
|-------|---------|
| `EXTRACTED` | Relationship is explicitly stated in the source (e.g., an import statement, a direct call) |
| `INFERRED` | Relationship is a reasonable deduction (e.g., call-graph second pass, co-occurrence in context) |
| `AMBIGUOUS` | Relationship is uncertain; flagged for human review in GRAPH_REPORT.md |

## Adding a new language extractor

1. Add a `extract_<lang>(path: Path) -> dict` function in `extract.py` following the existing pattern (tree-sitter parse → walk nodes → collect `nodes` and `edges` → call-graph second pass for INFERRED `calls` edges).
2. Register the file suffix in `extract()` dispatch and `collect_files()`.
3. Add the suffix to `CODE_EXTENSIONS` in `detect.py` and `_WATCHED_EXTENSIONS` in `watch.py`.
4. Add the tree-sitter package to `pyproject.toml` dependencies.
5. Add a fixture file to `tests/fixtures/` and tests to `tests/test_languages.py`.

### Adding a new XML-based extractor (e.g. another metadata format)

For languages without a tree-sitter grammar that store code inside XML (like D365 F&O / X++):

1. Add the root element tag(s) to `XPP_ARTIFACT_TAGS` in `detect.py`.
2. Implement a handler function in `extract.py` — use `xml.etree.ElementTree` to parse the XML and regex on any embedded CDATA source blocks.
3. Dispatch to the handler from `extract_xpp()` (or add a new top-level extractor if the format is unrelated to X++).
4. The `.xml` extension is already wired into `collect_files()` and `extract()` dispatch via `is_xpp_file()`. New tags in `XPP_ARTIFACT_TAGS` are automatically detected.
5. Add fixture XML files to `tests/fixtures/xpp/` and tests to `tests/test_xpp.py`.

## X++ / Dynamics 365 F&O Support

graphify supports D365 F&O X++ metadata stored as XML files under `Metadata/` directories. The extractor (`extract_xpp` in `extract.py`) handles **40 artifact types** across 8 tiers:

| Tier | Artifact Types | Key Edges Produced |
|------|---------------|--------------------|
| Code | AxClass, AxTable, AxForm, AxView, AxDataEntityView, AxMap, AxQuery | `extends`, `defines_method`, `calls`, `uses_table`, `uses_field`, `references_enum`, `data_source`, `join` |
| Extensions | AxTableExtension, AxFormExtension, AxDataEntityViewExtension, AxViewExtension, AxQuerySimpleExtension, AxEnumExtension | `extends`, `field_of`, `relation_to` |
| Types | AxEnum, AxEnumExtension, AxEdt | `value_of`, `table_reference` |
| Security | AxSecurityPrivilege, AxSecurityDuty, AxSecurityRole + extensions | `grants_access_to`, `includes_privilege`, `has_duty`, `has_sub_role` |
| UI / Navigation | AxMenuItemDisplay/Action/Output, AxMenuExtension, AxTile | `opens_form`, `runs_class`, `launches`, `includes_tile` |
| Services | AxService, AxServiceGroup | `implemented_by`, `exposes_method`, `includes_service` |
| BI / Analytics | AxAggregateMeasurement, AxAggregateDimension, AxAggregateDataEntity, AxKPI | `measure_group_of`, `uses_table`, `has_dimension`, `measures_from` |
| Config / Meta | AxConfigurationKey, AxReport, AxResource, AxMacroDictionary, AxEdt | node-only |

**Detection**: `detect.py` uses `is_xpp_file(path)` which reads the first 512 bytes and checks for an `<Ax...>` root element tag in `XPP_ARTIFACT_TAGS`. The `FileType.XPP` enum value is used for these files.

**Parsing**: No tree-sitter grammar exists for X++. The extractor uses `xml.etree.ElementTree` for structure and regex patterns on `<Source><![CDATA[...]]>` sections for call analysis (`::` static calls, `->` instance calls, `new ClassName()`, `tableStr()`, `fieldStr()`, `enumNum()`, etc.).

## Security

All external input passes through `graphify/security.py` before use:

- URLs → `validate_url()` (http/https only) + `_NoFileRedirectHandler` (blocks file:// redirects)
- Fetched content → `safe_fetch()` / `safe_fetch_text()` (size cap, timeout)
- Graph file paths → `validate_graph_path()` (must resolve inside `graphify-out/`)
- Node labels → `sanitize_label()` (strips control chars, caps 256 chars, HTML-escapes)

See `SECURITY.md` for the full threat model.

## Testing

One test file per module under `tests/`. Run with:

```bash
pytest tests/ -q
```

All tests are pure unit tests - no network calls, no file system side effects outside `tmp_path`.

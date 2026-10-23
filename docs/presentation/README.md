# Presentation sources

The final editable deck is `deliverables/presentation/project_presentation.pptx`. Its PDF companion is a static copy for viewing and presenting. Speaker notes and source references appear in the PPTX and in `slide_notes.md`. `demo_script.md` includes a short rehearsal script and dashboard steps.

`build_deck.mjs` reads the generated forecasting and allocation CSVs directly. It creates editable PowerPoint charts and tables, records source hashes in its private build directory, renders all 15 slides, and validates the exported package. It uses the Codex bundled `@oai/artifact-tool` JavaScript runtime. That runtime is an optional authoring dependency and is separate from the project's Python training/dashboard environment.

To regenerate from this workstation, run the bundled Node executable with `docs/presentation/build_deck.mjs` as its script argument. On another authoring workstation, set `ARTIFACT_NODE_MODULES`, `PRESENTATION_SKILL_DIR`, and `ARTIFACT_PYTHON` to the supplied authoring-runtime locations. Set `PRESENTATION_REVISION` to a new suffix, for example `_revision2`, to preserve the existing final deck. The finalizer refuses to overwrite an existing final presentation.

The scientific workflow does not require rebuilding the slides. Run the project reproduction commands from the root README to regenerate forecasts, allocation metrics and the local dashboard artifacts. Then use the presentation generator when updated results need a new deck.

Required local inputs include:

- `results/comparison/forecast_metrics_10_30_60min.csv`
- `results/allocation/10min/metrics.csv` and `default_test_metrics.csv`
- `results/lstm/10min/predictions.csv`
- `data/prepared/window_counts.csv`
- `results/dashboard/dashboard-60min.png`

The final deck contains one fixed-seed comparison and discloses the unmet 1% allocation shortfall target. No presenter names or institutional affiliation have been invented.

The final slide is an explicit Conclusion covering the forecasting results, allocation tradeoff and scope. The presentation now has 15 slides.

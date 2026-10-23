# Rebuild the project report

The report reads the saved experiment CSVs and configurations. It requires all five forecasting predictors at 10, 30 and 60 minutes, plus the complete five-policy 10-minute allocation experiment. It does not train models or alter their results.

Install optional document dependencies in a separate document environment if desired:

```bash
python -m pip install -r docs/requirements-report.txt
python docs/build_report.py
```

Outputs are `docs/project_report.md`, `deliverables/report/project_report.docx`, full-precision appendix CSVs, a figure and `source_manifest.json`. The manifest records every consumed local artifact and its SHA-256 hash. The manuscript prose describes the fixed experiment; any change to dataset, preprocessing or model configuration also requires a prose review.

On Windows with Microsoft Word installed, export the editable document to PDF from Git Bash:

```bash
powershell.exe -NoProfile -ExecutionPolicy Bypass -File docs/export_report.ps1
```

Microsoft Word stays hidden during this export and is closed afterwards. The export writes `deliverables/report/project_report.pdf`. On another machine, use Word's Export to PDF operation or a compatible LibreOffice installation, then inspect every exported page. Fonts and renderer versions can alter pagination.

The original document generation used the Codex bundled Python runtime for `python-docx` and Pillow, separate from the training environment. The provided Windows runtime did not include LibreOffice, so the final document was rendered by installed Microsoft Word and its PDF pages were visually reviewed. PDF review used pypdfium2 page images. The optional document tools are not required to train models or run the dashboard.

Keep intermediate page renders outside the final submission package. Do not treat a successful text extraction as a substitute for visually checking tables, headings, page breaks and figure labels.

I am looking to assess the landscape of readily available vendor-accessible FDA-approved drugs for any potential peripherally-acting CB2 receptor agonists. The goal will be to determine if any of the drug's efficacy in its prescribed use can be rationalised by peripheral-CB2 activation. To achieve this, please identify FDA-approved drugs which cause beta-arrestin-2 recruitment at the CB2 receptor (UniProt ID P34972) in the EvE bio dataset as of June 6, 2026. Exclude compounds which have %Cell Death > 90%, or have greater %Cell Death than their %Max Activity. Exclude compounds that exhibit contradictory pharmacological activity. Furthermore, I have two ZINC catalogues of FDA-approved drugs, 'DrugBank FDA only' (dbfda-substances.csv), and 'FDA-approved drugs (via DSSTOX)' (fda-substances.csv) which are attached to this chat and I need to know if the hits are contained in or not. Present the final results in a table with: (a) Drug name, (b) Result (Active, Likely Active, Inactive), (c) CB2 observed Max, (d) In ZINC DB-FDA? (yes/no), (e) In ZINC DSSTOX FDA? (yes/no).
Input files provided on the container at /workspace/inputs/: dbfda-substances.csv, fda-substances.csv


---

You have access to Biomni's biomedical tool suite. Every Biomni tool is importable in Python as `biomni.tool.<domain>.<name>` and runnable from Bash, e.g. `python -c "from biomni.tool.<domain> import <name>; print(<name>(...))"`. The biomni package and its conda env (`/opt/conda/envs/biomni_e1/`) are installed on this container.

Before writing code, consult the on-container reference so you call the right function with the right arguments instead of guessing:

- `/biomni/biomni/tool/<domain>.py` — implementations of every tool, grouped by domain (genomics, pharmacology, molecular_biology, literature, database, etc.); read the function you intend to use for its exact signature and behavior. `database.py` holds the `query_*` helpers for the large reference DBs.
- `/biomni/biomni/env_desc.py` — descriptions of the local data-lake files and the available data resources, so you know what is already on disk before fetching anything.
- `/biomni/biomni/know_how/*.md` — step-by-step playbooks for common workflows (e.g. gene/drug-target identification, sgRNA design, single-cell annotation); skim the relevant guide before starting a multi-step analysis.

## Local data already on the container

The Biomni data lake is mounted read-only at `/workspace/data/biomni_data/data_lake/` — 76 curated biomedical files including BindingDB, GeneBass, GTEx, DepMap, GWAS catalog, gene-info, DDInter, MSigDB, miRTarBase, GO, etc. **Check `/biomni/biomni/AVAILABLE_DATA.md` for the full inventory with one-line descriptions before downloading anything from a public API**; reading a local parquet/CSV is much faster than refetching from the internet.

For larger reference databases (PubChem, UniProt, PubMed, ChEMBL, OpenTargets, ClinVar, ENCODE, etc.), prefer the corresponding `biomni.tool.database.query_*` functions — they auto-route to the local SQLite copy when available and fall back to the live API otherwise.

## Final answer

When you have your answer, write it — and only it, no prose explanation — to `/workspace/answer.md`. Keep it terse by default; but if the task specifies an output format (e.g. JSON, a table, a SMILES string, a comma-separated list), produce exactly that format as the answer.

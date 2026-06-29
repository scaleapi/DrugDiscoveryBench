We are running an early-stage drug-repurposing screen for small-molecule stabilisers of the c-MYC promoter G-quadruplex (NHE III1 element) in c-Myc-driven haematological and ovarian malignancies. The attached file cMYC_G4_ChEMBL35_snapshot.csv is a ChEMBL Release 35 snapshot of bioactivity records under target_chembl_id = CHEMBL3832742 (Homo sapiens), frozen 1 December 2024. From the snapshot, identify the three compounds with the strongest measured Kd against the c-MYC promoter G-quadruplex. For each, report the PubMed ID of the source publication. Please report as a table, three rows, rank 1 to rank 3, with the following columns:

rank | compound_chembl_id | compound_name | standard_type | standard_relation | standard_value | standard_units | assay_chembl_id | document_pmid

Please use the following constraints/definitions, while reporting: standard_type = Kd, standard_relation = "=", standard_units = nM.
Input files provided on the container at /workspace/inputs/: cMYC_G4_ChEMBL35_snapshot.csv


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

We're comparing two lead candidates, compound A and compound B, of a KRAS G12C drug development campaign.

We manage to obtain co-crystal structure data of KRAS G12C with compound A (6USX.pdb) and compound B (6UT0.pdb).

Experimentally, we know that compound B is more potent.

We suspect that a significant conformational change of one specific residue X occurs, when compound B is used instead of compound A. This allows for more hydrophobic contact of residue X with compound B.

Provide the name of residue X, as 3-letter abbreviation with residue number (from the PDB file).

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

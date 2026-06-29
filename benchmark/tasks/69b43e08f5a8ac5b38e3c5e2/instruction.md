The PDB entry 6UL5 describes the X-ray co-crystal structure of HIV-1 RT with inhibitor A. We recently prepared several matched molecular pairs: B, C, D. (All SMILES string are listed below).

By analysis of molecular interactions in the crystal structure, predict the ranking of affinity of the following inhibitors for HIV-1 RT, in descending order. Provide your answer using only "&gt;" and the letters that are used to label the compounds.

A) `N#CC1=CC=C(NC2=NC(OC3=C(C)C=C(/C=C/C#N)C=C3C)=C4C(C=CS4)=N2)C=C1F`

B) `N#CC1=CC=C(NC2=NC(OC3=C(C)C=C(/C=C/C#N)C=C3C)=C4C(C=CO4)=N2)C=C1F`

C) `N#CC1=CC=C(NC2=NC(OC3=C(C)C=C(/C=C/C#N)C=C3C)=C4C(C=CS4)=N2)C=C1C(F)(F)F`

D) `N#CC1=CC=C(CC2=NC(OC3=C(C)C=C(/C=C/C#N)C=C3C)=C4C(C=CS4)=N2)C=C1C(F)(F)F`

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

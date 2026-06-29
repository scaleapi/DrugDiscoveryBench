The PDB entry 8G44 describes the X-ray co-crystal structure of HDAC6 with inhibitor B. We recently prepared several analogs: A, C, D.

(All SMILES string for A to D are listed below).

Predict the ranking of affinity of the following inhibitors for HDAC6, in descending order. Provide your answer using only "&gt;" and the letters that are used to label the compounds.   

(A) `O=C1C2=CC=CC=C2N=C(N1CC(NC)=O)CCC(O)=O`

(B) `O=C1C2=CC=CC=C2N=C(N1CC(NCC3=CC=CC=C3)=O)CCC(O)=O` 

(C) `O=C1C2=CC=CC=C2N=C(N1CC(NCC3=C(OC)C=CC=C3)=O)CCC(O)=O`

(D) `O=C1C2=CC=CC=C2N=C(CCC(O)=O)N1CC(NCC3=C(C(C)(C)C)C=CC=C3)=O`

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

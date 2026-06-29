FlcD (PA3518) from Pseudomonas aeruginosa PAO1 is an HDO enzyme in the fluopsin C biosynthetic cluster. I know canonical HDOs use dinuclear metal centers, but FlcD may differ. I want to examine the metal coordination environment at the highest available resolution. Please retrieve all crystal structures of FlcD from the RCSB PDB that have been resolved to 2.0 angstroms or better. For each qualifying structure, present a single table, sorted by deposition year in ascending order, with these columns: PDB ID | deposition year | resolution (angstroms) | deposited title | active-site metal identity | coordinating amino acid residues within 2.5 angstroms (three-letter codes with residue numbers) | mean distance from the metal center to coordinating protein atoms within 2.5 Å, computed per chain and then averaged across all chains in the ASU (Å) | and structure determination method. As a footnote to the table, please report the number of chains, sequence length, and co-crystallized ligand(s) of the first structure submitted to the RCSB for FlcD.

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

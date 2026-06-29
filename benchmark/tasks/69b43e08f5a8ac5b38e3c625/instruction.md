I'm investigating Osteosarcoma 

Analyzing the clinical data for the disease as of December 2025, I want you to make a list of genes in descending order of total mutations.

There are already many groups working on the TP53 gene, so I want you to drop that and select the next gene that has the most mutations. 

Does this selected gene have an overall association score of 0.5 or more with the disease? If not, again look for the next gene from the list made in the first step and repeat until you find a gene with an overall association score of 0.5 or more.

Now map this gene to its ChEMBL single-protein target via its UniProt accession (the human target whose product is the gene itself, not paralogs or binding partners), and retrieve that target's bioactivities. Select the compound with the lowest IC50 reported with standard relation "=" in nM. If that compound has multiple ChEMBL records (stereoisomers or salts of the same structure), use the canonical named parent record.

Perform a similarity search on that compound (Tanimoto coefficient = 0.4) and identify the most similar compound that is neither the query itself nor an exact-structure duplicate of it, excluding salts, isotopologues, and stereoisomers that share the query's 2D structure.

For both the selected compound and the most-similar compound, return the name, SMILES, and IC50 value (in nM), plus the Tanimoto similarity of the most-similar compound.

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

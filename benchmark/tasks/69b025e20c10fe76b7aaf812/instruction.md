I am collecting data from informed consent forms of patients diagnosed with colon cancer regarding their participation in clinical trials. Although my sample size is small, I aim to compare my findings with historical data, specifically from the study by Charles G. Moertel *et al*., *N Engl J Med* (1990). I know Terry M Therneau published a survival::colon dataset containing the paper's data (observation only points to no chemotherapy). From a total of 10 patients in my dataset, the treatment distribution is as follows. Stage I: 1 patient – no chemotherapy, Stage II: 1 patient – no chemotherapy, 2 patients – Fluorouracil (5-FU), 2 patients – Bevacizumab, 1 patient – Cetuximab, Stage III: 2 patients – CAPOX, Stage IV: 1 patient – FOLFIRI. 
Using the historical data from Moertel et al. (1990) and the dataset derived from these consent forms, determine whether the proportion of patients who received a non-classical chemotherapeutic agent in my dataset is consistent with the historical trend. Don't stratify by cancer stage. Compare the two values using an absolute difference threshold of 10 percentage points. Report YES/ NO by reporting also both percentages. Round to one decimal place.

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

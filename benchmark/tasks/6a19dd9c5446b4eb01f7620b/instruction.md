Attached are two files listing candidate cfDNA methylation regions from two NSCLC cohorts and giving per-region cohort AUC values for the same regions (nsclc_cfDNA_dmrs.bed and nsclc_marker_auc.tsv).

As of 30 May 2026, identify all candidate regions that are hypermethylated in both cohorts (methyl delta > 0, q value < 0.05), have AUC values in both cohorts, overlap a CpG island within 1 kb of a protein-coding HGNC transcription start site on GRCh38, and have prior PubMed evidence as a lung-cancer diagnostic methylation marker. Then, rank eligible regions by the smaller of the two cohort AUC values, then by mean methyl delta, then by region ID. Report the single top-ranked region. Answer with the HGNC symbol, GRCh38 interval, the two cohort AUCs, the specimen type from the supporting literature, and at least one rejected near-miss.
Input files provided on the container at /workspace/inputs/: nsclc_marker_auc.tsv, nsclc_cfDNA_dmrs.bed


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

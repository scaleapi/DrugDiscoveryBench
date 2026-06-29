I am interested in the link between myelin and neurodegenerative diseases such as Alzheimer's disease. Please identify the most abundant saturated fatty acid (defined in mol percentage of total amount of fatty acids) in myelin membranes (isolated in the mouse sciatic nerve) with reference to articles published before (and including) 2011. Starting from this fatty acid, determine the first enzymatic step required for the biosynthesis of the most abundant fatty acid (with the same abundance definition above) in myelin membranes. If there are multiple steps involved, only consider the first step (for example, elongation from C16:0 to C18:0). Identify the specific enzyme responsible for catalyzing this step. Report the title of the literature before proceeding to the next steps.

Then, identify the enzyme isoforms present in humans and determine which isoform shows higher mRNA expression specifically in the cerebellar hemisphere, basal ganglia (including the caudate, nucleus accumbens and putamen), and cerebellum. The 3 areas in the basal ganglia are counted separately. The isoform with the higher median TPM in the majority of those 5 specified tissues is considered to have higher expression, referred to as the 'brain-enriched isoform'.

For the brain-enriched isoform, retrieve its STRING neighborhood. From the full set of pairwise interactions among the displayed nodes, find the unique proteins involved in any edge with a combined score &gt;= 0.99 and the coexpression value is higher than 0. Identify which of those interaction partners are associated with Alzheimer's disease with an association score higher than 0.45. List all partners that meet the criteria, their association score, and the CRISPR Screens score. When querying dynamic databases, limit the search dates to 29 April 2026.

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

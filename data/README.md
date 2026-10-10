# UNSW-NB15 benchmark data

Included official partitions:

| File | Records | Role |
|---|---:|---|
| UNSW_NB15_training-set.csv | 175,341 | Training-only preprocessing/model fitting |
| UNSW_NB15_testing-set.csv | 82,332 | Recorded official comparison and fixed-model degradation experiment |

Source: [UNSW Research dataset page](https://research.unsw.edu.au/projects/unsw-nb15-dataset). These are public benchmark network records, not traffic collected from a university deployment. Original files are preserved; degraded experimental copies are generated in memory.

The selected model uses 42 predictors and excludes `id`, `attack_cat` and `label`. Compatible uploads do not require targets. The official test split participated in candidate selection, so it is not a fresh independent estimate of the selected winner.

The authors grant academic research use and state separate commercial-use and citation terms on the official page. Dataset rights belong to the original authors; inclusion here does not relicense the data or imply permission for unrestricted commercial use. Cite the original dataset work and consult the complete source terms.

Moustafa, N., & Slay, J. (2015). UNSW-NB15: A comprehensive data set for network intrusion detection systems (UNSW-NB15 network data set). *2015 Military Communications and Information Systems Conference (MilCIS).* https://doi.org/10.1109/MILCIS.2015.7348942

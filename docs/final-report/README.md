# Capstone final report

Deliverable: [DataQualiQ_Capstone_Final_Report_Victoria_Mnisi.docx](DataQualiQ_Capstone_Final_Report_Victoria_Mnisi.docx).

Prepared for Victoria Nokubonga Mnisi, student number 202428583, with the user-supplied submission date 12 October 2026. The supplied template identifies Dr. F. Matsebula and Sol Plaatje University; those cover details are retained. The original template is unchanged.

The report follows the template's section order, uses A4, one-inch margins, Arial 11, 1.5 line spacing, numbered bold chapter headings and a bottom-centred page-number field. It includes four measurable objectives, APA author–date references, actual source excerpts rendered as figures, the verified Dashboard/PDF captures, official model comparison, all ten degradation conditions, plots, limitations and recommendations. The editable [Markdown narrative](DataQualiQ_Capstone_Final_Report.md) contains the same report body.

## Provenance

Numerical results come from Phase 3, Phase 5, Phase 15 and Phase 16 records, rather than online performance claims. New report-only feature importance is read from the already-saved forest: no fitting, inference, tuning or artifact replacement occurs. Indicator importances are summed by their raw categorical field. These impurity-based values are descriptive and not causal or independent permutation importance.

`report_evidence.json` records the exact rankings, saved hyperparameters, dataset descriptions and matching before/after SHA-256 checksums for the template, both official CSVs, model, preprocessor and metadata. `report_content.json` stores the structured report body. `assets` contains generated architecture, source excerpts and importance figures; experiment plots and verified interface evidence are reused from their original phase folders.

Academic references were checked online on 9 October 2026 using the original Random Forest paper/publisher record, official UNSW dataset page, original intrusion-detection paper, JMLR scikit-learn paper and official scikit-learn documentation. The date on the cover is the requested submission date, not a fabricated source-access date. The Git origin URL is verified locally; public availability of every local phase file is not assumed.

## Reproduction and checks

`build_report.py` is a documentation-only assembler. It uses python-docx from `TEMP/DataQualiQ-report-tools` and plotting packages from `TEMP/DataQualiQ-experiment-plots`; production dependencies are unchanged. Generation may require permission to read those temporary installed packages.

Structural validation checks ZIP/XML integrity, section order, cover details, all model/experiment values, typography, margins, line spacing, page-number field, embedded images and source/artifact hashes. Generated figures were visually inspected. No Word or LibreOffice renderer is installed in this environment, so exact final pagination was not visually validated in Word. Open the document in Word for a final layout review before submission.

The institution's required similarity check has not been performed. No plagiarism score, similarity percentage or clearance is claimed; complete that check through the approved institutional service. The report was not sent to an external checking service.

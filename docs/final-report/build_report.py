"""Documentation-only report assembly; uses temporary packages, never fits models."""
import hashlib
import json
import os
from pathlib import Path
import sys
import textwrap

ROOT = Path(__file__).resolve().parents[2]
OUT = Path(__file__).resolve().parent
sys.path.insert(0, str(Path(os.environ['TEMP']) / 'DataQualiQ-report-tools'))
sys.path.insert(0, str(Path(os.environ['TEMP']) / 'DataQualiQ-experiment-plots'))
from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Inches, Mm, Pt, RGBColor
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch
from matplotlib.font_manager import FontProperties

TEMPLATE = Path(r'C:\Users\Admin\Desktop\Second Semester\Special Topics in Computer Science\Capstone Final Project Template.docx')
EVIDENCE = json.loads((OUT/'report_evidence.json').read_text())
PHASE5 = json.loads((ROOT/'docs/phase5/evaluation.json').read_text())
PHASE16 = json.loads((ROOT/'docs/phase16/experiment_results.json').read_text())
assert PHASE16['complete']
ASSETS = OUT/'assets'
ASSETS.mkdir(exist_ok=True)
plt.rcParams.update({'font.family':'Arial','font.size':11,'pdf.fonttype':42,'svg.fonttype':'none'})

def savefig(fig, name):
    path = ASSETS/(name+'.png')
    fig.savefig(path, dpi=220, bbox_inches='tight', facecolor='white')
    fig.savefig(ASSETS/(name+'.svg'), bbox_inches='tight')
    plt.close(fig)
    return path

def architecture():
    fig, ax = plt.subplots(figsize=(8.4,6.1))
    ax.set_xlim(0,10); ax.set_ylim(0,10); ax.axis('off')
    nodes = [(1,8.7,'Network CSV\nFastAPI parsing'),(5.4,8.7,'Quality assessment\nNetwork validation'),
             (5.4,6.5,'Saved normalization\nMedian + one-hot encoding'),(5.4,4.3,'Saved Random Forest\nClass + probability'),
             (1,4.3,'Input integrity\nHigh / Review / Low'),(1,2,'Backend recommendations\nHuman review'),
             (5.4,2,'Combined API response\nReact pages + PDF')]
    for x,y,label in nodes:
        ax.add_patch(FancyBboxPatch((x,y-0.8),3.6,1.4,boxstyle='round,pad=0.12',facecolor='#edf3f8',edgecolor='#194e71'))
        ax.text(x+1.8,y-0.1,label,ha='center',va='center',fontsize=11)
    def arrow(a,b,style='-'):
        ax.annotate('',xy=b,xytext=a,arrowprops={'arrowstyle':'->','color':'#194e71','lw':1.6,'linestyle':style})
    arrow((4.7,8.6),(5.25,8.6)); arrow((7.2,7.8),(7.2,7.2)); arrow((7.2,5.6),(7.2,5)); arrow((7.2,3.4),(7.2,2.7))
    arrow((5.3,8.2),(2.8,5)); arrow((5.3,6.2),(3.8,5)); arrow((2.8,3.4),(2.8,2.7)); arrow((4.7,1.9),(5.25,1.9))
    ax.text(5,0.35,'Reliability uses input evidence; probability does not set reliability.\nInvalid required values retain reasons and receive no class/probability.',ha='center',fontsize=10,color='#263a4a')
    return savefig(fig,'architecture')

def code_image(name,path,start,end,title):
    lines=(ROOT/path).read_text(encoding='utf-8').splitlines()[start-1:end]
    displayed=[]
    for index,line in enumerate(lines,start):
        wrapped=textwrap.wrap(line,width=82,replace_whitespace=False,drop_whitespace=False) or ['']
        displayed.append(f'{index:>3}  {wrapped[0]}')
        displayed.extend('     '+part for part in wrapped[1:])
    rendered='\n'.join(displayed)
    fig,ax=plt.subplots(figsize=(8.4,len(displayed)*.29+.8))
    ax.axis('off'); ax.set_title(title,loc='left',fontsize=12,pad=12)
    ax.text(0,1,rendered,va='top',fontfamily='monospace',fontsize=12,transform=ax.transAxes)
    return savefig(fig,name)

ARCH = architecture()
MODEL_CODE = code_image('model-configuration','backend/ml/models.py',7,20,'Actual source: backend/ml/models.py')
pre_lines=(ROOT/'backend/ml/preprocessing.py').read_text().splitlines()
encoder_line=next(i for i,line in enumerate(pre_lines,1) if 'self.encoder_ = OneHotEncoder' in line)
ENCODER_CODE=code_image('saved-encoding','backend/ml/preprocessing.py',encoder_line-4,encoder_line+4,'Actual source: saved categorical encoding')
rank=EVIDENCE['raw_feature_ranking'][:10]
fig,ax=plt.subplots(figsize=(8,4.8),layout='constrained')
ax.barh([x['feature'] for x in rank][::-1],[100*x['importance'] for x in rank][::-1],color='#2274a5')
ax.set_xlabel('Aggregated impurity importance (%)'); ax.set_title('Top ten raw predictor importances',loc='left',fontweight='bold')
ax.spines[['top','right']].set_visible(False)
IMPORTANCE=savefig(fig,'feature-importance')

doc=Document(TEMPLATE)
body=doc.element.body
children=list(body)
for child in children[20:]:
    if child.tag != qn('w:sectPr'): body.remove(child)
for p in doc.paragraphs:
    if 'TITLE OF YOUR PROJECT' in p.text:
        p.text='DataQualiQ: Data Quality-Aware Network Intrusion Detection'
        p.alignment=WD_ALIGN_PARAGRAPH.CENTER
        p.runs[0].bold=True

for style in doc.styles:
    if style.type in (1,2):
        style.font.name='Arial'; style.font.size=Pt(11)
        style.font.color.rgb=RGBColor(0,0,0)
        if style.type==1:
            style.paragraph_format.line_spacing=1.5
            style.paragraph_format.space_after=Pt(6)
for level in [1,2,3]:
    style=doc.styles[f'Heading {level}']
    style.font.bold=True; style.paragraph_format.keep_with_next=True
    style.paragraph_format.space_before=Pt(10)
    style.paragraph_format.space_after=Pt(4)
    style.paragraph_format.page_break_before=False
for section in doc.sections:
    section.page_width=Mm(210); section.page_height=Mm(297)
    section.top_margin=section.bottom_margin=section.left_margin=section.right_margin=Inches(1)
    section.footer_distance=Inches(.4)
    footer=section.footer.paragraphs[0]
    footer.alignment=WD_ALIGN_PARAGRAPH.CENTER
    field=OxmlElement('w:fldSimple');field.set(qn('w:instr'),'PAGE')
    run=OxmlElement('w:r');txt=OxmlElement('w:t');txt.text='1';run.append(txt);field.append(run);footer._p.append(field)

blocks=[]
def heading(text,level=1):
    doc.add_heading(text,level);blocks.append({'type':'heading','text':text,'level':level})
def para(text):
    p=doc.add_paragraph(text);p.paragraph_format.widow_control=True
    blocks.append({'type':'paragraph','text':text})
def table(headers,rows,widths=None):
    t=doc.add_table(rows=1,cols=len(headers));t.autofit=False
    borders=OxmlElement('w:tblBorders')
    for edge in ['top','left','bottom','right','insideH','insideV']:
        item=OxmlElement('w:'+edge);item.set(qn('w:val'),'single');item.set(qn('w:sz'),'4');item.set(qn('w:color'),'AAB7C2');borders.append(item)
    t._tbl.tblPr.append(borders)
    usable=6.267
    sizes=widths or [usable/len(headers)]*len(headers)
    for col,size in zip(t.columns,sizes):col.width=Inches(size)
    for cell,text in zip(t.rows[0].cells,headers):cell.text=str(text)
    repeat=OxmlElement('w:tblHeader');t.rows[0]._tr.get_or_add_trPr().append(repeat)
    for row in rows:
        for cell,text in zip(t.add_row().cells,row):cell.text=str(text)
    for ri,row in enumerate(t.rows):
        no_split=OxmlElement('w:cantSplit');row._tr.get_or_add_trPr().append(no_split)
        for ci,cell in enumerate(row.cells):
            cell.width=Inches(sizes[ci])
            for p in cell.paragraphs:
                p.paragraph_format.space_after=Pt(2);p.paragraph_format.space_before=Pt(0)
                for r in p.runs:r.font.size=Pt(11);r.bold=ri==0
            if ri==0:
                shade=OxmlElement('w:shd');shade.set(qn('w:fill'),'EAF0F5');cell._tc.get_or_add_tcPr().append(shade)
    blocks.append({'type':'table','headers':headers,'rows':[[str(v) for v in row] for row in rows]})
    doc.add_paragraph().paragraph_format.space_after=Pt(0)
def figure(path,caption,width=6.0):
    p=doc.add_paragraph();p.alignment=WD_ALIGN_PARAGRAPH.CENTER
    p.paragraph_format.keep_with_next=True
    p.add_run().add_picture(str(path),width=Inches(width))
    c=doc.add_paragraph(caption);c.runs[0].italic=True
    blocks.append({'type':'figure','path':str(Path(path).relative_to(ROOT)),'caption':caption})

doc.add_page_break()
heading('Contents')
contents=['1. Executive Summary','2. Business Domain','3. Introduction','4. Problem and Objectives',
          '5. Scope','6. Solution','7. Final Model Results','8. Recommendations','9. References','10. Appendix: Links and Evidence']
for text in contents:para(text)
para('The report follows the supplied capstone template. Recorded project evidence is distinguished from literature and from future recommendations. References use APA author–date citations.')

heading('1. Executive Summary')
para('DataQualiQ is a working cybersecurity prototype that analyses uploaded network traffic records. It combines data-quality assessment, safe feature handling and machine-learning classification in a single upload-to-report workflow. The intended users are security analysts, network administrators and students who need to investigate traffic predictions alongside evidence about the inputs used to produce them.')
para('A React frontend communicates with a FastAPI backend. The backend validates the network schema, reuses a training-fitted preprocessor and serves a saved Random Forest. Each accepted record is classified as Normal or Malicious and accompanied by model probabilities and a separate input-integrity status. Invalid required inputs are rejected with reasons instead of receiving guessed predictions. Recommendations guide human review; the application does not automatically block traffic.')
para('On the official 82,332-record UNSW-NB15 testing split, Random Forest achieved 86.4111% accuracy, 80.6874% malicious precision, 99.0206% recall and 88.9188% F1. Its recall-weighted selection reduced missed attacks relative to the Decision Tree baseline, but increased false alarms. A controlled experiment showed that missing predictors reduced accuracy, precision and F1 while slightly increasing recall; supported formatting differences changed no predictions. These results demonstrate a mechanism-dependent relationship between data quality and classifier behavior, within a limited benchmark evaluation.')
para('Recorded whole-system validation passed 28 end-to-end scenarios, 274 backend tests and 49 frontend tests. A full testing-file upload succeeded, but took approximately 239.5 seconds. The deliverable is an explainable decision-support prototype, rather than a production intrusion-prevention system (Mnisi, 2026a, 2026b, 2026c).')

heading('2. Business Domain')
para('The domain is cybersecurity monitoring and network security analysis. The specific user group is analysts and network administrators reviewing compatible, labelled-feature network records exported to CSV. In an educational setting, the same interface can support computer science students examining intrusion detection and model limitations. No commissioned external client or organizational deployment is claimed.')
para('For this user group, the practical need is to prioritize suspicious records without confusing strong model estimates with verified attacks. Missing inputs, unseen categories and rejected values should be visible before an analyst relies on a prediction. Useful outputs include record explanations, concise recommendations, full-file summaries and an exportable report for investigation or academic assessment.')

heading('3. Introduction')
para('Machine-learning-based intrusion detection applies classifiers to network features to distinguish benign from suspicious activity. Its usefulness depends on the input schema, preprocessing consistency and the interpretation of errors. Sommer and Paxson (2010) identify practical difficulties in transferring machine-learning detection to operational networks, including contextual interpretation and false alarms. DataQualiQ addresses a bounded part of this problem by exposing input-integrity evidence beside a classifier output.')
para('The project progressed from a general CSV quality engine to a supervised cybersecurity application. Quality checks remain a supporting layer: the Random Forest provides the intrusion classification, while validation and reliability logic explain whether predictive inputs were handled safely. The research question is: How does data quality affect the reliability of machine-learning-based network intrusion detection?')

heading('4. Problem and Objectives')
heading('4.1 Problem Statement',2)
para('A classifier can return a Malicious label even when required inputs were incomplete or unfamiliar. Without an input-integrity explanation, the user cannot distinguish a prediction based on known, valid features from one requiring review. Conversely, legitimate extreme traffic values may be security evidence and should not be deleted merely because they are statistically unusual. The problem is to integrate validated model inference with understandable input evidence and measured evaluation.')
heading('4.2 Business Objectives',2)
table(['Objective by the submission date','Success measure and recorded evidence'],[
('Deliver a compatible CSV-to-report cybersecurity workflow.','Upload, validation, Dashboard, detailed pages and PDF export demonstrated; 28 of 28 Phase 15 scenarios passed.'),
('Compare two supervised classifiers on the same official split and select using a declared criterion.','Decision Tree and Random Forest evaluated on 82,332 rows; malicious F2 policy and confusion counts recorded in Phase 5.'),
('Expose predictive-input integrity independently of model probability.','High/Review/Low reasons and rejected-row null outputs verified; saved inference tested with fitting forbidden.'),
('Evaluate three controlled quality mechanisms at 5%, 10% and 20%.','Baseline plus nine full-data conditions completed with unchanged labels, source files and saved artifacts in Phase 16.')],[3.0,3.267])
para('These four objectives are specific to the delivered prototype, measurable through stored evaluation evidence and bounded by the 12 October 2026 submission milestone. They do not promise operational accuracy thresholds that have not been agreed or verified.')
heading('4.3 Literature Review',2)
para('Breiman (2001) presents Random Forest as an ensemble of randomized tree predictors. This provides the foundation for the project’s comparison between a single Decision Tree and a forest. The literature motivates the classifier family; it does not establish that DataQualiQ must outperform its baseline on every metric.')
para('Moustafa and Slay (2015) introduce UNSW-NB15 as a benchmark for network intrusion detection. The official dataset page describes a mixture of normal activity and synthetic attack behavior and publishes the 175,341-record training and 82,332-record testing partitions (UNSW, n.d.). DataQualiQ retains those partitions and performs binary prediction, rather than nine-way attack-category classification.')
para('Sommer and Paxson (2010) examine the gap between research evaluations and operational intrusion detection. Their discussion supports evaluating false alarms alongside missed attacks and avoiding claims of production readiness from a benchmark alone. DataQualiQ therefore presents recommendations for investigation and explicitly distinguishes a prediction from a confirmed security incident.')
para('Pedregosa et al. (2011) describe scikit-learn’s reusable machine-learning tools and API-oriented design. The project uses these tools for training-fitted imputation, encoding and saved inference. Official scikit-learn guidance warns against learning preprocessing statistics from evaluation data; fitting on training data and reusing transform on later data is central to the project’s separation strategy (scikit-learn developers, n.d.-a).')
para('Together, these sources motivate the project’s integration of a classifier, a reproducible preprocessing contract and interpretable security review. The controlled data-quality experiment supplies project-specific evidence; no literature result is substituted for the project’s own measured performance.')

heading('5. Scope')
heading('5.1 In-Scope',2)
para('The implemented scope includes compatible network CSV ingestion, existing generic quality checks, network schema validation, supervised binary classification, saved preprocessing and model serving, row-level input reliability, backend recommendations, React decision-support pages and bounded PDF reporting. Evaluation uses the official UNSW-NB15 partitions, a Decision Tree baseline, the selected Random Forest and controlled degradation of declared predictor groups.')
heading('5.2 Out-of-Scope',2)
para('Live packet capture, automatic blocking or isolation, arbitrary feature schemas, multiclass attack attribution, deep-learning model development, calibrated probabilities, online retraining and production multiuser deployment are outside the delivered scope. No model tuning, feature selection or threshold sweep was performed using degraded test outcomes. Reusable analysis IDs, exhaustive result exports and independent external-network validation remain future work.')

heading('6. Solution')
heading('6.1 Overview of Methodology',2)
para('The development approach was incremental implementation with recorded phase-based verification. Existing quality rules were retained while separate modules added training-only preprocessing, candidate training, evaluation, artifact persistence, prediction serving, combined analysis and frontend reporting. This is an implementation and controlled-evaluation methodology; no unrecorded user study, survey or formal randomized trial is claimed.')
para('Source data were preserved. The training split supplied labels and learned preprocessing state; both classifiers were evaluated on the same official testing split. Subsequent serving reused saved artifacts. Phase 15 tested the integrated workflow, and Phase 16 held the model fixed while changing only selected predictive cells. The test split participated in model selection, so its reported performance is not a fresh independent estimate of the chosen winner.')
heading('6.2 Process Flowchart and Implementation',2)
figure(ARCH,'Figure 1. Final upload-to-report architecture. Reliability is derived from input integrity, not probability thresholds.')
table(['Stage','Implementation responsibility'],[
('CSV ingestion','FastAPI checks the file boundary; csv_loading.py parses input while retaining source representations.'),
('Quality and schema checks','pipeline.py supplies existing findings; combined_analysis.py validates saved required-feature rules and maps source positions.'),
('Saved preprocessing','NetworkMLPreprocessor applies normalization, training medians, reserved missing categories and one-hot encoding.'),
('Model inference','NetworkPredictionService loads verified artifacts, processes sparse batches and returns predict/predict_proba results.'),
('Reliability and advice','Combined analysis assigns High/Review/Low reasons; analysis_response.py produces evidence-based recommendations.'),
('Presentation and reports','React consumes the combined API contract and keeps active results in App memory; jsPDF exports a bounded report.')],[1.55,4.717])
heading('6.3 Model and Preprocessing Implementation',2)
figure(MODEL_CODE,'Figure 2. Relevant code excerpt rendered from the actual model factory source. The report generation did not execute training.')
figure(ENCODER_CODE,'Figure 3. Actual saved-encoder implementation excerpt. Missing categories are reserved and unknown categories do not extend the vocabulary.')
para('Numeric missing cells are handled with saved training medians. Categorical missing cells use an explicit reserved indicator. Supported whitespace and case differences are normalized according to the schema. No scaling is required by this tree-based implementation, and legitimate outliers are not removed. Structurally invalid required inputs are rejected rather than being silently converted to ordinary missing values.')
heading('6.4 Record Reliability and Recommendations',2)
table(['Status','Meaning'],[
('High','Prediction succeeded and implemented checks found no qualifying unresolved predictive-input issue; correctness is not guaranteed.'),
('Review','Prediction succeeded but handled missingness, an unseen category or relevant noncritical input finding requires human review.'),
('Low','Invalid required input prevented safe prediction. The rejected record retains its reason and has null class/probability.')],[1.0,5.267])
para('Low and rejected counts overlap: rejected records are the Low subset, not an additional disjoint class. IQR anomalies and preserved duplicates do not automatically lower reliability. Model probability and overall quality score do not select a reliability status. Backend advice prioritizes malicious predictions with input issues, independent investigation of malicious predictions and correction of rejected predictive inputs; no second recommendation algorithm runs in the frontend.')
heading('6.5 API Integration, State and Bounded Results',2)
para('The combined endpoint is POST /analyze-network, while /assess and /predict-network remain separate. Its structured response separates quality, current-upload intrusion summaries, saved official evaluation, reliability, records, pagination and recommendations. The official model_performance metrics are explicitly labelled as official test evaluation and are not calculated from arbitrary uploads.')
para('Inference uses at most 4,096 rows per batch; record responses default to 100 and are capped at 1,000, with bounded evidence. The frontend stores the full active response in memory across navigation, persisting only a small summary and route state. A storage error cannot turn backend success into analysis failure. Refresh loses detailed results and displays a no-active-analysis state. There is no reusable analysis-ID store, so another result window requires reupload/reanalysis.')
heading('6.6 User Interface and Reporting Evidence',2)
figure(ROOT/'docs/phase15/dashboard.png','Figure 4. Actual Phase 15 Dashboard capture after the full testing-file analysis. Full-file summaries and official evaluation are distinct from the returned 100-row record window.')
para('The finished interface includes Upload & Analyse, Dashboard, Data Quality, Intrusion Detection, Results and Reports. Results filters operate only on returned rows. Specific reliability and rejection reasons are available in expanded records. PDF export uses the active analysis and previews at most twenty important returned records. Existing captures verify the Dashboard and exported PDF; no unrecorded screenshot is fabricated.')

heading('7. Final Model Results')
heading('7.1 Final Data and Descriptive Statistics',2)
table(['Partition','Rows','Normal truth','Malicious truth','Malicious share'],[
('Training','175,341','56,000','119,341','68.0622%'),
('Testing','82,332','37,000','45,332',f'{100*45332/82332:.4f}%')],[1.1,1.1,1.15,1.45,1.467])
para('These are ground-truth counts from the retained official partitions, not predicted class totals. The CSVs contain 45 columns. No resampling, class weighting or row removal was introduced in the final model pipeline. Training and testing distributions differ, which limits interpretation of training–test gaps. The official test split was preserved rather than replaced by a new random split. Dataset descriptions and target-validation evidence are recorded in Phase 3 (Mnisi, 2026d).')
para('The original full-file quality score is 100/A under the existing error/quality penalty policy, despite analytical findings. Statistical anomaly occurrences may overlap across columns and are not an attack count. In the Phase 16 baseline, 248,284 analytical occurrences involved 58,543 distinct records, while missing, duplicate, invalid and inconsistency counts were zero. This shows why the heuristic score and analytical security review must remain distinct.')
heading('7.2 Raw and Derived Features',2)
para('The saved model requires 42 predictors: 39 numeric columns and three categorical columns. The fields id, attack_cat and label are excluded from inputs. Labels are needed only for training/evaluation. The exact required names are listed in Appendix 10.2, avoiding an incomplete hand-picked feature list.')
para('Derived features comprise normalized numeric representations and saved one-hot category indicators, producing 197 encoded columns. This is representation expansion rather than new attack labels or a learned feature vocabulary at upload time. Sparse matrices preserve the fixed encoded order. Numeric features remain available without outlier clipping or unnecessary scaling.')
heading('7.3 Feature-Importance Ranking',2)
para('For this report, importance was read from the already-saved forest’s feature_importances_ without fitting or predicting. The values describe mean decrease in impurity. One-hot indicator importances were summed by their raw categorical field so the ranking covers all 42 raw predictors. These are relative model contributions, not causal effects or calibrated measures of security relevance. Impurity importance can favor features with more possible split values; an independent permutation study was not performed (scikit-learn developers, n.d.-b).')
table(['Rank','Raw predictor','Relative importance'],[(str(i),x['feature'],f"{100*x['importance']:.4f}%") for i,x in enumerate(rank,1)],[.65,3.6,2.017])
figure(IMPORTANCE,'Figure 5. Top ten saved-forest raw predictor importances; categorical indicator contributions are aggregated. Complete ranking is retained in report_evidence.json.')
heading('7.4 Algorithm and Hyperparameters',2)
para('The selected classifier is RandomForestClassifier. It uses Gini-based splits, bootstrap samples and randomized feature subsets, following the ensemble approach described by Breiman (2001). Serving reuses the fitted forest, with its default predict decision rule; it does not optimize a probability threshold for each uploaded dataset.')
params=EVIDENCE['parameters']
groups=[['n_estimators','criterion','max_depth'],['min_samples_split','min_samples_leaf','min_weight_fraction_leaf'],['max_features','max_leaf_nodes'],['bootstrap','max_samples','oob_score'],['class_weight','min_impurity_decrease','ccp_alpha'],['random_state','n_jobs'],['verbose','warm_start','monotonic_cst']]
table(['Stored parameter group','Actual saved values'],[(', '.join(group),'; '.join(f'{key}={params[key]}' for key in group)) for group in groups],[2.55,3.717])
para('All stored estimator parameters are reported above. The Decision Tree comparison uses Gini, best splitter, depth 16, minimum split 10, minimum leaf 5 and random_state 42. Both candidates were configured before the official comparison. No parameter sweep is reported because none was performed.')
heading('7.5 Official Test Evaluation and Model Comparison',2)
dt=PHASE5['models']['decision_tree'];rf=PHASE5['models']['random_forest']
rows=[(key.title() if key!='f1' else 'F1',f"{100*dt['metrics'][key]:.4f}%",f"{100*rf['metrics'][key]:.4f}%") for key in ['accuracy','precision','recall','f1','f2']]
rows += [(key.replace('_',' ').title(),f"{dt['counts'][key]:,}",f"{rf['counts'][key]:,}") for key in ['true_negatives','false_positives','false_negatives','true_positives']]
table(['Official test measure','Decision Tree','Random Forest'],rows,[2.567,1.85,1.85])
para('Malicious is the positive class. Confusion matrices use actual rows and predicted columns in [Normal, Malicious] order: Decision Tree [[27962, 9038], [1647, 43685]]; Random Forest [[26256, 10744], [444, 44888]]. False negatives represent missed attacks, while false positives represent normal traffic incorrectly flagged as malicious. These exact counts total 82,332 for each candidate (Mnisi, 2026a).')
para('The declared selection criterion was malicious F2, which weights recall more strongly than precision. Random Forest’s F2 of 94.7164% exceeded Decision Tree’s 93.3237%. It missed 1,203 fewer attacks but generated 1,706 additional false alarms. Decision Tree had better accuracy, precision and F1; selecting the forest is a cybersecurity tradeoff, not evidence that it wins all measures.')
para('The selected forest still missed 444 attacks and produced 10,744 false alarms. Its probability estimates have not been calibrated, and its High input-integrity status does not certify a correct class. Comparing candidates on the official test split makes that split involved in selection, although it was not used for fitting. A fresh external evaluation is needed before operational claims.')
heading('7.6 Controlled Data-Quality Experiment',2)
para('Phase 16 used the same saved forest and preprocessor for the original testing baseline and nine degraded conditions. Numeric missingness affected dur, rate and sbytes (seed 16042); categorical missingness affected proto, service and state (seed 16043); formatting changes added outer whitespace and uppercase proto only (seed 16044). Each 5%, 10% and 20% level is a nested sample of original nonmissing cells within its declared predictor group. Labels and attack categories never determined selection.')
names={'baseline':'Baseline','numeric_missing':'Numeric','categorical_missing':'Categorical','representation':'Formatting'}
def condition(item):return names[item['condition']] + (f" {item['degradation_percent']:g}%" if item['condition']!='baseline' else '')
table(['Condition','Quality','Acc. %','Prec. %','Recall %','F1 %','FN'],[(condition(i),f"{i['quality_score']:g}",*[f"{100*i[k]:.4f}" for k in ['accuracy','precision','recall','f1']],str(i['false_negatives'])) for i in PHASE16['conditions']],[1.5,.52,.81,.81,.81,.81,1.007])
para('Categorical missingness affected accuracy, precision and F1 most at each matched level. At 20%, accuracy decreased by 1.1174 percentage points, precision by 1.4151 and F1 by 0.7799. False positives increased by 1,019. Recall nevertheless increased by 0.2184 points, with 99 fewer missed attacks. Numeric 20% missingness reduced accuracy by 0.9049 points and F1 by 0.6412, while reducing missed attacks by 44. Missingness therefore changed the error tradeoff rather than invariably increasing false negatives (Mnisi, 2026c).')
para('Formatting changes produced exactly the baseline predictions and quality score at all three levels because the saved normalization handled the tested representations. This does not establish robustness to arbitrary corruption. Missingness raised Review counts, while quality scores plateaued at 32.5 for 10% and 20%. The score is a heuristic input-quality measure, not a calibrated predictor of model accuracy or recall.')
figure(ROOT/'docs/phase16/plots/accuracy.png','Figure 6. Verified Phase 16 accuracy versus affected eligible predictor cells. Values and sampling denominators are preserved from the original experiment.')
figure(ROOT/'docs/phase16/plots/recall.png','Figure 7. Verified Phase 16 malicious recall. Recall rose slightly under missingness, despite lower accuracy, precision and F1.')
heading('7.7 System Validation and Large-File Result',2)
table(['Verification','Recorded outcome'],[
('Phase 15 end-to-end scenarios','28 passed; 0 failed'),('Phase 15 backend regression','274 tests passed'),('Phase 15 frontend regression','49 tests passed'),('ESLint and production build','Passed; retained reporting-bundle size advisory'),('Phase 16 backend regression','282 passed, including eight experiment tests')],[2.4,3.867])
para('The recorded checks exercised malformed CSVs, missing required features, missing values, invalid numeric values, unseen categories, outliers, duplicates, the full testing file, Dashboard and detailed routes, filters, refresh, storage quota handling and PDF export. Real React/FastAPI browser sessions handled successful CSV analyses; unavailable-backend and quota boundaries used deliberate mocks. This is automated verification, not a claimed human usability study (Mnisi, 2026b).')
table(['Full official testing-file upload','Recorded value'],[
('Analysed / predicted rows','82,332 / 82,332'),('Predicted Normal / Malicious','26,700 / 55,632'),('Quality','100 / A'),('High / Review reliability','82,327 / 5'),('Low / rejected','0 / 0'),('Average predicted-class probability','90.79%'),('Backend analysis time','239.5 seconds'),('Detailed records returned','100')],[3.55,2.717])
para('Predicted counts above are not ground-truth class counts. The average probability is not accuracy. Concurrent regression work was active during the recorded 239.5-second run, so the timing is a single observed value rather than a service guarantee. The full summary remained separate from the bounded preview; stored browser summary size was 266 bytes.')
heading('7.8 Research Answer and Conclusion',2)
para('Data quality affects machine-learning-based network intrusion detection through the mechanism of the input problem and how the saved pipeline handles it. Missing predictors increased review needs and false alarms while reducing accuracy, precision and F1; recall slightly improved. Supported formatting differences were normalized without changing predictions. Input-integrity reliability, model probability and measured predictive performance are consequently related but distinct.')
para('The project demonstrates a working cybersecurity prototype integrating supervised classification, reusable preprocessing, backend model serving, frontend decision support and controlled evaluation. Its contribution is the connection between computational inference and explainable input evidence, supported by verified upload-to-report behavior. The evidence does not establish universal accuracy, guaranteed attack identification or production readiness.')

heading('8. Recommendations')
heading('8.1 Actionable Insights',2)
para('Prioritize malicious predictions with input-integrity issues and inspect rejected records before reanalysis. Investigate malicious predictions using independent security evidence rather than automatic blocking. Resolve missing source values and validate unfamiliar categories against authoritative network exports. Preserve analytical anomalies and duplicate provenance until their context is understood.')
para('Future evaluation should hold the classifier fixed and use a genuinely independent or temporally separate labelled dataset, multiple degradation seeds and uncertainty intervals. Systematic and combined missingness should be tested without selecting conditions from target labels. Any later tuning must use a separate development protocol and retain an independent final evaluation.')
para('For practical large-file browsing, implement an explicitly bounded, expiring analysis-result store and reusable analysis IDs before adding further result-window requests. Optimize quality-assessment latency and profile peak memory/concurrent workload. These are recommendations, not completed features of the submitted prototype.')
heading('8.2 Potential Risks and Mitigation Strategies',2)
table(['Risk or limitation','Mitigation / next step'],[
('False alarms and missed attacks','Use analyst review and independent evidence; establish operational error costs on new data.'),
('Benchmark/domain shift','Evaluate on genuinely independent networks and time periods before deployment claims.'),
('Schema mismatch and unseen categories','Require saved feature names; expose explicit errors/audits and Review status.'),
('Uncalibrated probabilities','Label them as estimates; assess calibration separately with a proper validation protocol.'),
('Slow full-file assessment','Profile the quality stage, memory and concurrency; retain bounded output and sparse inference.'),
('Refresh and page-local evidence','Keep clear empty states; add reusable analysis IDs before claiming durable result browsing.'),
('Sensitive traffic exports','Use authorized/anonymized data and restrict access; production security controls require separate work.')],[2.2,4.067])
heading('8.3 Challenges and Remaining Limitations',2)
para('Engineering challenges included aligning quality findings to original rows after rejected inputs, maintaining the fitted feature order, preserving source values, separating official evaluation from current-upload summaries and preventing large-response browser storage failures. The final design uses explicit source-position mapping, saved artifacts, bounded responses and memory-based active results to address these issues.')
para('Remaining limits include UNSW-NB15-focused evaluation, a required schema, uploaded-record rather than live analysis, slow large files, uncalibrated probability, page-local filters/PDF previews, evidence truncation and refresh loss. Phase 16 used one seed per mechanism, limited predictor groups and nested levels, without confidence intervals or combined corruption. The official testing split previously participated in model selection. No universal reliability or production security guarantee follows from these results.')

heading('9. References')
references=[
('Breiman, L. (2001). Random forests. Machine Learning, 45(1), 5–32. https://doi.org/10.1023/A:1010933404324',None),
('Mnisi, V. N. (2026). DataQualiQ: Data quality-aware network intrusion detection [Computer software and unpublished project evaluation records]. Sol Plaatje University.','https://github.com/NokubongaVee/DataQualiQ'),
('Moustafa, N., & Slay, J. (2015). UNSW-NB15: A comprehensive data set for network intrusion detection systems (UNSW-NB15 network data set). In 2015 Military Communications and Information Systems Conference (MilCIS) (pp. 1–6). IEEE. https://doi.org/10.1109/MILCIS.2015.7348942',None),
('Pedregosa, F., Varoquaux, G., Gramfort, A., Michel, V., Thirion, B., Grisel, O., Blondel, M., Prettenhofer, P., Weiss, R., Dubourg, V., Vanderplas, J., Passos, A., Cournapeau, D., Brucher, M., Perrot, M., & Duchesnay, É. (2011). Scikit-learn: Machine learning in Python. Journal of Machine Learning Research, 12, 2825–2830. https://jmlr.org/papers/v12/pedregosa11a.html',None),
('scikit-learn developers. (n.d.-a). Common pitfalls and recommended practices. scikit-learn documentation. Retrieved October 9, 2026, from https://scikit-learn.org/stable/common_pitfalls.html',None),
('scikit-learn developers. (n.d.-b). Feature importances with a forest of trees. scikit-learn documentation. Retrieved October 9, 2026, from https://scikit-learn.org/stable/auto_examples/ensemble/plot_forest_importances.html',None),
('Sommer, R., & Paxson, V. (2010). Outside the closed world: On using machine learning for network intrusion detection. In 2010 IEEE Symposium on Security and Privacy (pp. 305–316). IEEE. https://doi.org/10.1109/SP.2010.25',None),
('UNSW. (n.d.). The UNSW-NB15 dataset. UNSW Research. Retrieved October 9, 2026, from https://research.unsw.edu.au/projects/unsw-nb15-dataset',None)]
reference_italics=['Machine Learning, 45','Journal of Machine Learning Research, 12','2015 Military Communications and Information Systems Conference (MilCIS)','2010 IEEE Symposium on Security and Privacy','DataQualiQ: Data quality-aware network intrusion detection','Common pitfalls and recommended practices','Feature importances with a forest of trees','The UNSW-NB15 dataset']
for text,url in references:
    full=text+((' '+url) if url else '')
    p=doc.add_paragraph()
    offset=0
    spans=sorted((full.index(token),token) for token in reference_italics if token in full)
    for start,token in spans:
        p.add_run(full[offset:start]);p.add_run(token).italic=True;offset=start+len(token)
    p.add_run(full[offset:])
    p.paragraph_format.left_indent=Inches(.3);p.paragraph_format.first_line_indent=Inches(-.3)
    blocks.append({'type':'reference','text':p.text})

heading('10. Appendix: Links and Evidence')
heading('10.1 Code Repository and Reproduction Evidence',2)
para('Git repository configured for this project: https://github.com/NokubongaVee/DataQualiQ. This is the verified local origin URL; the report does not assert that every local phase file has already been pushed to the public repository. Implementation code should be submitted through the repository with the matching evaluation evidence.')
para('Primary evidence files: docs/phase5/evaluation.json; backend/models/model_metadata.json; docs/phase15/system_validation.json; docs/phase15/regression_results.json; docs/phase16/experiment_results.json and experiment_results.csv. The final narrative is consolidated in docs/phase17/README.md. Report-specific saved importance extraction and integrity checks are retained in docs/final-report/report_evidence.json.')
heading('10.2 Complete Required Predictor Names',2)
features=json.loads((ROOT/'backend/models/model_metadata.json').read_text())['features']
para('Numeric predictors: '+', '.join(features['numeric_features'])+'.')
para('Categorical predictors: '+', '.join(features['categorical_features'])+'. Excluded fields: id, attack_cat, label. Input column order may differ, but the saved feature order is used for transformation.')
heading('10.3 Additional Verified Figures and Report Evidence',2)
figure(ROOT/'docs/phase16/plots/quality_score.png','Figure 8. Quality-score thresholds plateau while the number of missing cells continues to increase.')
figure(ROOT/'docs/phase16/plots/f1.png','Figure 9. F1 decreases under both missingness mechanisms; formatting changes leave baseline performance unchanged.')
figure(ROOT/'docs/phase16/plots/false_negatives.png','Figure 10. Missed attacks decrease under the tested missingness conditions; the conclusion must include increased false positives.')
figure(ROOT/'docs/phase15/page-1.png','Figure 11. Actual first page of the verified exported network PDF. The eight-page export is preserved in docs/phase15/DataQualiQ-network-report.pdf.',width=4.8)
heading('10.4 Submission and Integrity Notes',2)
para('The original template, training/testing CSVs, selected model, saved preprocessor and metadata were preserved. The report adds no application logic and performs no training or new test-set model selection. References were checked online and numerical results traced to recorded project evidence. Institutional similarity checking has not been run by this report-generation process; no similarity percentage or plagiarism clearance is claimed. The template’s similarity-check requirement must be completed through the institution’s approved service before submission.')

# Consolidate internal evidence under one APA software/project-record citation.
def normalize_citation(text):
    text=text.replace('Mnisi, 2026a, 2026b, 2026c','Mnisi, 2026')
    for suffix in 'abcd':text=text.replace('Mnisi, 2026'+suffix,'Mnisi, 2026')
    return text
for p in doc.paragraphs:
    if normalize_citation(p.text)!=p.text:p.text=normalize_citation(p.text)
for b in blocks:
    if 'text' in b:b['text']=normalize_citation(b['text'])
# Apply the requested typeface/size consistently, including retained cover text.
def format_paragraph(p):
    p.paragraph_format.line_spacing=1.5
    for run in p.runs:
        run.font.name='Arial';run.font.size=Pt(11)
        run._element.get_or_add_rPr().get_or_add_rFonts().set(qn('w:eastAsia'),'Arial')
for p in doc.paragraphs:format_paragraph(p)
for t in doc.tables:
    for row in t.rows:
        for cell in row.cells:
            for p in cell.paragraphs:format_paragraph(p)
for sec in doc.sections:
    for p in sec.footer.paragraphs:format_paragraph(p)
# Cover paragraph marks and nested drawing/textbox runs can carry direct legacy formatting.
for root_element in [doc.element]+[sec.footer._element for sec in doc.sections]:
    for props in root_element.iter(qn('w:rPr')):
        fonts=props.find(qn('w:rFonts'))
        if fonts is None:fonts=OxmlElement('w:rFonts');props.insert(0,fonts)
        for key in ['ascii','hAnsi','eastAsia','cs']:fonts.set(qn('w:'+key),'Arial')
        for key in ['sz','szCs']:
            size=props.find(qn('w:'+key))
            if size is None:size=OxmlElement('w:'+key);props.append(size)
            size.set(qn('w:val'),'22')
doc.core_properties.author='Victoria Nokubonga Mnisi'
doc.core_properties.title='DataQualiQ: Data Quality-Aware Network Intrusion Detection'
doc.core_properties.subject='Capstone Final Report — student 202428583 — submission 12 October 2026'
doc.core_properties.comments='Generated from the supplied capstone template and verified project evidence; original template preserved.'
output=OUT/'DataQualiQ_Capstone_Final_Report_Victoria_Mnisi.docx'
doc.save(output)
(OUT/'report_content.json').write_text(json.dumps(blocks,indent=2,ensure_ascii=False),encoding='utf-8')
md=['# DataQualiQ: Data Quality-Aware Network Intrusion Detection','', 'Victoria Nokubonga Mnisi | 202428583 | 12 October 2026','']
for b in blocks:
    if b['type']=='heading':md += ['#'*b['level']+' '+b['text'],'']
    elif b['type'] in ['paragraph','reference']:md += [b['text'],'']
    elif b['type']=='table':
        md += ['| '+' | '.join(b['headers'])+' |','| '+' | '.join(['---']*len(b['headers']))+' |']
        md += ['| '+' | '.join(row)+' |' for row in b['rows']];md.append('')
    else:md += [f"![{b['caption']}]({os.path.relpath(ROOT/b['path'],OUT).replace(chr(92),'/')})",b['caption'],'']
(OUT/'DataQualiQ_Capstone_Final_Report.md').write_text('\n'.join(md),encoding='utf-8')
after={path:hashlib.sha256(Path(path).read_bytes()).hexdigest() for path in EVIDENCE['files_before']}
assert after==EVIDENCE['files_before'],'Original input or artifact changed'
EVIDENCE.update(files_after=after,files_unchanged=True,report_path=str(output.relative_to(ROOT)),report_sha256=hashlib.sha256(output.read_bytes()).hexdigest())
(OUT/'report_evidence.json').write_text(json.dumps(EVIDENCE,indent=2),encoding='utf-8')
print(f'Created {output.name}: {output.stat().st_size:,} bytes; {len(blocks)} content blocks; original files/artifacts unchanged.')

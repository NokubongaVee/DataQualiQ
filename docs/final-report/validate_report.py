"""Read-only structural and evidence checks for the generated Word report."""
import hashlib
import json
from pathlib import Path
import xml.etree.ElementTree as ET
import zipfile

ROOT=Path(__file__).resolve().parents[2]
OUT=Path(__file__).resolve().parent
DOC=OUT/'DataQualiQ_Capstone_Final_Report_Victoria_Mnisi.docx'
NS={'w':'http://schemas.openxmlformats.org/wordprocessingml/2006/main'}
W='{'+NS['w']+'}'
with zipfile.ZipFile(DOC) as archive:
    assert archive.testzip() is None
    for path in archive.namelist():
        if path.endswith('.xml'):ET.fromstring(archive.read(path))
    document=ET.fromstring(archive.read('word/document.xml'))
    text='\n'.join(node.text or '' for node in document.findall('.//w:t',NS))
    for expected in ['Victoria Nokubonga Mnisi','202428583','12 October 2026','Dr. F. Matsebula','Sol Plaatje University']:
        assert expected in text,expected
    headings=['1. Executive Summary','2. Business Domain','3. Introduction','4. Problem and Objectives','5. Scope','6. Solution','7. Final Model Results','8. Recommendations','9. References','10. Appendix: Links and Evidence']
    positions=[text.rfind(heading) for heading in headings]
    assert positions==sorted(positions) and min(positions)>=0
    for placeholder in ['TITLE OF YOUR PROJECT','Brief non-technical overview','Provide a brief literature review','Performance graphs for parameters sweeps if applicable']:
        assert placeholder not in text
    assert '\ufffd' not in text
    for node in document.findall('.//w:rFonts',NS):
        for key in ['ascii','hAnsi','eastAsia','cs']:assert node.get(W+key)=='Arial'
    for node in document.findall('.//w:sz',NS):assert node.get(W+'val')=='22'
    for node in document.findall('.//w:spacing',NS):
        if node.get(W+'line') is not None:assert node.get(W+'line')=='360'
    section=document.find('w:body/w:sectPr',NS)
    page=section.find('w:pgSz',NS);assert (page.get(W+'w'),page.get(W+'h'))==('11906','16838')
    margins=section.find('w:pgMar',NS)
    for side in ['top','right','bottom','left']:assert margins.get(W+side)=='1440'
    footer=ET.fromstring(archive.read('word/footer1.xml'))
    assert footer.find('.//w:jc',NS).get(W+'val')=='center'
    assert footer.find('.//w:fldSimple',NS).get(W+'instr')=='PAGE'
    image_count=len([name for name in archive.namelist() if name.startswith('word/media/')])
    assert image_count>=12
    for path in ['docs/phase5/evaluation.json','docs/phase16/experiment_results.json']:
        result=json.loads((ROOT/path).read_text())
        items=list(result['models'].values()) if 'models' in result else result['conditions']
        for item in items:
            metrics=item.get('metrics',item)
            for key in ['accuracy','precision','recall','f1']:
                assert f'{100*metrics[key]:.4f}' in text,(path,key)
    for value in ['28 passed; 0 failed','274 tests passed','49 tests passed','239.5 seconds','26,700 / 55,632','90.79%']:
        assert value in text,value
evidence=json.loads((OUT/'report_evidence.json').read_text())
assert evidence['files_before']==evidence['files_after']
for path,expected in evidence['files_before'].items():
    assert hashlib.sha256(Path(path).read_bytes()).hexdigest()==expected,path
assert hashlib.sha256(DOC.read_bytes()).hexdigest()==evidence['report_sha256']
assert len(evidence['raw_feature_ranking'])==42
assert abs(sum(item['importance'] for item in evidence['raw_feature_ranking'])-1)<1e-9
status={'zip_xml_integrity':'passed','cover_details':'passed','section_order':'passed','verified_metric_values':'passed','a4_arial11_spacing_margins_footer':'passed','embedded_images':image_count,'original_files_unchanged':True,'word_render_validation':'unavailable: no Word/LibreOffice installed','institutional_similarity_check':'not performed'}
(OUT/'validation.json').write_text(json.dumps(status,indent=2))
print(json.dumps(status,indent=2))

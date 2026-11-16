"""Build a portable, offline literature-review report from audited records."""
from pathlib import Path
from html import escape
from html.parser import HTMLParser
from collections import Counter
import hashlib
import json
import re

ROOT = Path(__file__).resolve().parent
PARTS = ['agent_literature.json', 'repair_literature.json', 'foundations_literature.json']
REQUIRED = ['id', 'title', 'authors', 'year', 'venue', 'status', 'url',
            'verification_urls', 'access_depth', 'contribution', 'key_findings',
            'importance', 'relevance', 'transferable_idea', 'limitations', 'verified_date']
AREAS = {'A': 'Agents, feedback and evaluation', 'B': 'Repair, testing and security',
         'C': 'Adjacent foundations'}

def e(value):
    if isinstance(value, list):
        value = '; '.join(str(x) for x in value)
    return escape(str(value), quote=True)

records = []
for part in PARTS:
    data = json.loads((ROOT / part).read_text())
    assert len(data) == 50, (part, len(data))
    records.extend(data)
assert len(records) == 150
assert len({p['id'] for p in records}) == 150
norm = lambda s: re.sub(r'[^a-z0-9]', '', s.lower())
assert len({norm(p['title']) for p in records}) == 150, 'Duplicate title'
assert len({p['url'].rstrip('/') for p in records}) == 150, 'Duplicate main URL'
for p in records:
    for k in REQUIRED:
        assert k in p and p[k], (p['id'], k)
    assert 1900 <= int(p['year']) <= 2026, (p['id'], 'year')
    assert p['verified_date'] == '2026-11-16', (p['id'], 'date')
    assert isinstance(p['verification_urls'], list) and p['verification_urls']
    for u in [p['url']] + p['verification_urls']:
        assert u.startswith(('https://', 'http://')), (p['id'], u)

entries = []
labels = [('contribution','Central contribution'), ('key_findings','Key findings'),
          ('importance','Why it matters'), ('relevance','Relation to this research'),
          ('transferable_idea','Idea to use'), ('limitations','Boundary')]
for p in records:
    links = ' · '.join(f'<a href="{e(u)}">Source {i+1}</a>' for i,u in enumerate(dict.fromkeys(p['verification_urls'])))
    body = ''.join(f'<p><b>{label}.</b> {e(p[key])}</p>' for key,label in labels)
    notes = ''.join(f'<p><b>{e(k.replace("_", " ").capitalize())}.</b> {e(p[k])}</p>'
                    for k in ['source_note', 'publication_note', 'verification_note'] if p.get(k))
    entries.append(f'''<article class="paper" id="{e(p['id'])}" data-group="{p['id'][0]}">
<div class="paper-head"><span class="paper-id">{p['id']}</span><span class="badge">{e(p['status'])}</span></div>
<h3><a href="{e(p['url'])}">{e(p['title'])}</a></h3>
<p class="authors">{e(p['authors'])}</p><p class="metadata">{e(p['year'])} · {e(p['venue'])}</p>
{body}<details><summary>Verification and reading depth</summary><p>{e(p['access_depth'])}</p>{notes}<p>{links}</p><p>Verified {e(p['verified_date'])}.</p></details></article>''')

counts = Counter(p['status'] for p in records)
depth = Counter('Targeted full text / full text' if 'full' in p['access_depth'].lower() and 'not full' not in p['access_depth'].lower() else 'Abstract / bibliographic record / other stated depth' for p in records)
count_html = '<ul>' + ''.join(f'<li>{e(k)}: {v}</li>' for k,v in sorted(counts.items())) + '</ul>'
summary = f'<p><strong>150 unique publications; three groups of 50.</strong> Exact status labels, retained without conflating workshop acceptance with a main-conference paper:</p>{count_html}<p>The evidence ledgers and machine-readable bibliography accompany this report. Reading-depth text in each entry is authoritative; full-text access does not mean independent replication.</p>'
body = (ROOT / 'narrative.html').read_text().replace('__LITERATURE__', '\n'.join(entries)).replace('__CORPUS_SUMMARY__', summary)
sections = re.findall(r'<section id="([^"]+)"><h2>(.*?)</h2>', body)
assert len(sections) == 11
nav = ''.join(f'<a href="#{sid}">{title}</a>' for sid,title in sections)
manuscript = ROOT.parent / 'paper' / 'final.md'
manuscript_hash = hashlib.sha256(manuscript.read_bytes()).hexdigest()

css = '''
:root {color-scheme:light;--ink:#192a37;--muted:#586a78;--line:#d5dfe4;--accent:#145c68;--paper:#fff;--wash:#f0f5f5}
*{box-sizing:border-box} html{scroll-behavior:smooth;scroll-padding-top:24px}
body{margin:0;background:#f5f7f7;color:var(--ink);font:17px/1.7 Georgia,'Times New Roman',serif}
a{color:var(--accent);text-decoration-thickness:1px;text-underline-offset:3px;overflow-wrap:anywhere}
header{background:#173e46;color:white;padding:62px max(28px,calc((100vw - 1060px)/2)) 48px}
header a{color:#d5edef} .eyebrow{font:12px/1.5 system-ui,sans-serif;text-transform:uppercase;letter-spacing:.16em}
h1{font-size:clamp(34px,4.5vw,58px);line-height:1.12;max-width:920px;letter-spacing:-.025em;margin:20px 0}
header p{max-width:800px;font-size:19px;color:#e0ebed} .header-meta{font:13px/1.65 system-ui,sans-serif}
.layout{max-width:1450px;margin:0 auto;display:grid;grid-template-columns:255px minmax(0,1fr);gap:46px;padding:44px 28px}
nav{position:sticky;top:24px;align-self:start;max-height:92vh;overflow:auto;font:13px/1.4 system-ui,sans-serif}
nav a{display:block;text-decoration:none;margin-bottom:12px;padding-left:10px;border-left:2px solid #c6d8db}
main{max-width:1050px;min-width:0}section{background:white;padding:36px 42px;margin-bottom:28px;border:1px solid var(--line)}
h2{font-size:29px;line-height:1.25;margin:0 0 26px;letter-spacing:-.018em}h3{font-size:21px;line-height:1.35;margin:30px 0 12px}
p{margin:0 0 17px}.lead{font-size:21px;line-height:1.5}.scope{font:14px/1.65 system-ui,sans-serif;border-left:3px solid var(--accent);padding:14px 18px;background:var(--wash)}
li{margin-bottom:11px}ul,ol{padding-left:25px}table{width:100%;border-collapse:collapse;margin:24px 0 28px;font:14px/1.55 system-ui,sans-serif}
th,td{border-bottom:1px solid var(--line);padding:12px 10px;text-align:left;vertical-align:top}th{background:var(--wash);font-weight:650}
blockquote{margin:22px 0;padding:22px 25px;background:#f5f7f7;border-left:3px solid #527982}blockquote p:last-child{margin-bottom:0}
code{font-size:.86em;font-family:ui-monospace,SFMono-Regular,monospace;background:#eef3f3;padding:2px 4px;overflow-wrap:anywhere}
.library-controls{padding:20px;background:var(--wash);font:14px/1.5 system-ui,sans-serif;margin:24px 0}
label{display:block;font-weight:600;margin:10px 0 6px}input,select{width:100%;font:16px system-ui,sans-serif;padding:10px;border:1px solid #a7bfc2;background:white;color:var(--ink);border-radius:3px}
#visible-count{margin:14px 0 0;color:var(--muted)}.paper{border-top:1px solid var(--line);padding:28px 0 18px}
.paper h3{font-size:21px;margin:12px 0 8px}.paper h3 a{text-decoration:none}.paper p{font-size:15.5px;line-height:1.65;margin-bottom:10px}
.paper-head{display:flex;gap:12px;align-items:center;flex-wrap:wrap;font:12px/1.5 system-ui,sans-serif}.paper-id{font-weight:750;letter-spacing:.05em;color:var(--accent)}
.badge{background:#edf3f3;border:1px solid #d5e3e3;padding:2px 7px;border-radius:3px}.authors,.metadata{font-family:system-ui,sans-serif;font-size:13px!important;color:var(--muted)}
details{font:13px/1.6 system-ui,sans-serif;margin:14px 0}details p{font:13px/1.6 system-ui,sans-serif!important}summary{cursor:pointer;color:var(--accent);padding:4px 0}
footer{padding:36px 28px;max-width:1060px;margin:auto;font:13px/1.65 system-ui,sans-serif;color:var(--muted)}[hidden]{display:none!important}
@media(max-width:1050px){.layout{grid-template-columns:1fr;gap:22px;max-width:900px}nav{position:static;display:grid;grid-template-columns:1fr 1fr;gap:0 15px;max-height:none}section{padding:26px}table{display:block;overflow-x:auto}}
@media(max-width:600px){header{padding:35px 20px}.layout{padding:20px 12px}section{padding:22px 18px}nav{grid-template-columns:1fr}body{font-size:16px}h2{font-size:25px}}
@media print{@page{size:A4;margin:17mm 16mm}body{background:white;font-size:10.5pt;line-height:1.45}header{background:white;color:var(--ink);padding:0 0 22px}header p,header a{color:var(--ink)}h1{font-size:30pt}.layout{display:block;padding:0}nav,.library-controls{display:none}main{max-width:none}section{border:0;padding:0;margin:0;break-before:page}h2{font-size:21pt}h3{font-size:14pt}table{font-size:9pt;display:table}thead{display:table-header-group}tr{break-inside:avoid}.paper{break-inside:avoid}.paper p{font-size:10pt}.paper h3{font-size:12pt}.lead{font-size:13pt}details{display:block}.badge{border:0}footer{padding:24px 0}.paper[hidden]{display:block!important}}
'''
js = '''
const input=document.getElementById('search'), group=document.getElementById('group');
const papers=[...document.querySelectorAll('.paper')];
function filter(){const q=input.value.trim().toLocaleLowerCase(),g=group.value;let n=0;for(const p of papers){const show=(!g||p.dataset.group===g)&&(!q||p.textContent.toLocaleLowerCase().includes(q));p.hidden=!show;if(show)n++;}document.getElementById('visible-count').textContent=n+' of 150 papers';}
input.addEventListener('input',filter);group.addEventListener('change',filter);
window.addEventListener('beforeprint',()=>document.querySelectorAll('details').forEach(d=>d.open=true));
'''
doc = f'''<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Research Review — When Should a Repair Agent Distrust Its Checker?</title><style>{css}</style></head><body>
<header><div class="eyebrow">Critical literature review · Research strategy · 16 November 2026</div><h1>When Should a Repair Agent Distrust Its Checker?</h1><p>A critical review of <em>The Tests Passed. The Benchmark Said No</em>, with 150 annotated publications and a concrete plan for a stronger study.</p><div class="header-meta">Prepared against the current local manuscript and supporting records.<br>Reading-depth and publication-status labels included for every reference.<br><a href="bibliography.json">Structured bibliography</a> · <a href="bibliography.bib">BibTeX</a> · <a href="verification_report.json">Artifact checks</a></div></header>
<div class="layout"><nav aria-label="Report sections">{nav}</nav><main>{body}</main></div>
<footer><p>Manuscript reviewed: <a href="../paper/final.md">paper/final.md</a>. SHA-256: <code>{manuscript_hash}</code>.</p><p>Read-only local verification: historical replay; historical stop-label code-path recount; cross-family error-direction recount; six-slot feedback-replication recount. All passed. No new model calls, experimental data collection, original manuscript edits, or submission actions were performed.</p><p>Research recommendations are this review's synthesis. Source findings are attributed to their authors. Bibliographic identity verification does not establish correctness of every published claim, and the review is not exhaustive beyond its selected 150-paper corpus.</p></footer><script>{js}</script></body></html>'''
(ROOT / 'research_review.html').write_text(doc)
(ROOT / 'bibliography.json').write_text(json.dumps(records, indent=2, ensure_ascii=False)+'\n')

def be(s):
    return str(s).replace('\\','\\textbackslash{}').replace('&',r'\&').replace('%',r'\%').replace('_',r'\_').replace('#',r'\#')
bib=[]
for p in records:
    authors=p['authors'] if isinstance(p['authors'],str) else '; '.join(p['authors'])
    authors=' and '.join(x.strip() for x in authors.split(';'))
    bib.append('@misc{'+p['id']+',\n'+
       '  title = {'+be(p['title'])+'},\n'+
       '  author = {'+be(authors)+'},\n'+
       '  year = {'+str(p['year'])+'},\n'+
       '  howpublished = {'+be(p['venue'])+'},\n'+
       '  note = {'+be(p['status'])+'; metadata verified 2026-11-16},\n'+
       '  url = {'+p['url']+'}\n}')
(ROOT/'bibliography.bib').write_text('\n\n'.join(bib)+'\n')

class AuditParser(HTMLParser):
    def __init__(self):
        super().__init__();self.ids=[];self.anchors=[];self.text=[]
    def handle_starttag(self,tag,attrs):
        d=dict(attrs)
        if 'id' in d:self.ids.append(d['id'])
        if tag=='a' and d.get('href','').startswith('#'):self.anchors.append(d['href'][1:])
    def handle_data(self,data):self.text.append(data)
audit=AuditParser();audit.feed(doc)
assert len(audit.ids)==len(set(audit.ids)), 'Duplicate HTML IDs'
assert set(audit.anchors)<=set(audit.ids), 'Broken section anchor'
assert '__LITERATURE__' not in doc and '__CORPUS_SUMMARY__' not in doc
report={'publication_count':150,'unique_normalized_titles':150,'unique_primary_urls':150,
        'groups':dict(Counter(p['id'][0] for p in records)), 'status_counts':dict(counts),
        'required_fields_complete':True,'sections':len(sections),'internal_anchors_valid':True,
        'verification_date':'2026-11-16','manuscript_sha256':manuscript_hash,
        'html_sha256':hashlib.sha256(doc.encode()).hexdigest(),
        'bibliography_sha256':hashlib.sha256((ROOT/'bibliography.json').read_bytes()).hexdigest(),
        'word_count_approx':len(' '.join(audit.text).split()),
        'scientific_replication_claim':False,
        'reading_depth_note':'See each record; not all entries are full-text reviews.',
        'local_checks':{'historical_replay':'VERIFIED_EXPLORATORY_EVIDENCE','historical_stop_recount':'PASS',
                        'crossfamily_error_direction':'CROSSFAMILY_ERROR_DIRECTION_OK',
                        'feedback_replication':'FEEDBACK_REPLICATION_RECOUNT_OK'}}
(ROOT/'verification_report.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps(report,indent=2))

"""Render the Markdown viva guide to a bookmarked PDF. Requires ReportLab."""
from pathlib import Path
import re
import textwrap
from html import escape
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak, Preformatted
from reportlab.platypus.tableofcontents import TableOfContents
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'output/pdf/viva_and_code_guide.pdf'
OUT.parent.mkdir(parents=True,exist_ok=True)
for name, filename in [('Guide','calibri.ttf'),('GuideBold','calibrib.ttf'),('GuideItalic','calibrii.ttf'),('Code','consola.ttf')]:
    pdfmetrics.registerFont(TTFont(name,str(Path('C:/Windows/Fonts')/filename)))
pdfmetrics.registerFontFamily('Guide',normal='Guide',bold='GuideBold',italic='GuideItalic',boldItalic='GuideBold')
styles=getSampleStyleSheet()
styles.add(ParagraphStyle(name='Text',fontName='Guide',fontSize=10.5,leading=14.4,spaceAfter=7,textColor=colors.HexColor('#27374d'),splitLongWords=True))
styles.add(ParagraphStyle(name='Section',fontName='GuideBold',fontSize=16,leading=20,spaceBefore=17,spaceAfter=9,textColor=colors.HexColor('#163854'),keepWithNext=True))
styles.add(ParagraphStyle(name='Subsection',parent=styles['Section'],fontSize=12,leading=16,spaceBefore=11,spaceAfter=6))
styles.add(ParagraphStyle(name='Cell',parent=styles['Text'],fontSize=8.3,leading=11,spaceAfter=0))
styles.add(ParagraphStyle(name='CodeBlock',fontName='Code',fontSize=8.1,leading=11,backColor=colors.HexColor('#f1f5f9'),borderPadding=9,spaceBefore=5,spaceAfter=12))
styles.add(ParagraphStyle(name='BulletText',parent=styles['Text'],leftIndent=12,firstLineIndent=-9))
styles.add(ParagraphStyle(name='Cover',fontName='GuideBold',fontSize=29,leading=33,spaceAfter=15,textColor=colors.HexColor('#163854')))
styles.add(ParagraphStyle(name='TOCEntry',fontName='Guide',fontSize=10.1,leading=16,spaceBefore=2,leftIndent=0,firstLineIndent=0))

def inline(s):
    s=escape(s).replace('\u2011','-').replace('\u2013','-').replace('\u2014','-')
    s=re.sub(r'`([^`]+)`',r'<font name="Code">\1</font>',s)
    return re.sub(r'\*\*(.+?)\*\*',r'<b>\1</b>',s)

class GuideDoc(SimpleDocTemplate):
    def afterFlowable(self,flowable):
        if isinstance(flowable,Paragraph) and flowable.style.name=='Section':
            title=flowable.getPlainText()
            key='section_'+str(self.seq.nextf('section'))
            self.canv.bookmarkPage(key)
            self.canv.addOutlineEntry(title,key,0,False)
            self.notify('TOCEntry',(0,title,self.page,key))

def footer(canvas,doc):
    canvas.saveState();w,h=A4
    canvas.setStrokeColor(colors.HexColor('#dfe6ef'));canvas.line(45,39,w-45,39)
    canvas.setFont('Guide',8);canvas.setFillColor(colors.HexColor('#73839b'))
    canvas.drawString(45,26,'TRAFFIC FORECASTING | Viva and code guide')
    canvas.drawRightString(w-45,26,str(doc.page))
    if doc.page>1:canvas.drawString(45,h-28,'LSTM / GRU / TRANSFORMER  -  CESNET-TimeSeries24')
    canvas.restoreState()

doc=GuideDoc(str(OUT),pagesize=A4,rightMargin=45,leftMargin=45,topMargin=46,bottomMargin=52,title='Traffic Forecasting - Viva and Code Explanation Guide',author='Project study guide')
flow=[Paragraph('Understand the project.<br/>Explain it with confidence.',styles['Cover']),Paragraph('Viva and code explanation guide',styles['Subsection']),Paragraph('A complete study companion covering the data, code, models, mathematics, results, limitations and demonstration. Read the numerical examples aloud and rehearse the dashboard sequence.',styles['Text']),Spacer(1,12),Paragraph('Contents',styles['Subsection'])]
toc=TableOfContents();toc.levelStyles=[styles['TOCEntry']];flow+=[toc,PageBreak()]
lines=(ROOT/'docs/VIVA_AND_CODE_GUIDE.md').read_text(encoding='utf-8').splitlines()
i=0
while i<len(lines):
    line=lines[i].strip()
    if not line or line.startswith('# '):i+=1;continue
    if line.startswith('```'):
        code=[];i+=1
        while i<len(lines) and not lines[i].startswith('```'):
            raw=lines[i].replace('\t','    ')
            code+=textwrap.wrap(raw,width=98,replace_whitespace=False,drop_whitespace=False,subsequent_indent='    ') or ['']
            i+=1
        flow.append(Preformatted('\n'.join(code),styles['CodeBlock']));i+=1;continue
    if line.startswith('|'):
        rows=[]
        while i<len(lines) and lines[i].strip().startswith('|'):
            cells=[v.strip() for v in lines[i].strip().strip('|').split('|')]
            if not all(re.fullmatch(r':?-+:?',v) for v in cells):rows.append(cells)
            i+=1
        n=len(rows[0]);width=A4[0]-90
        widths=[width/n]*n
        if n==2:widths=[width*.42,width*.58]
        cells=[[Paragraph(inline(v),styles['Cell']) for v in row] for row in rows]
        table=Table(cells,colWidths=widths,repeatRows=1,hAlign='LEFT')
        table.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,0),colors.HexColor('#e0ebf5')),('ROWBACKGROUNDS',(0,1),(-1,-1),[colors.white,colors.HexColor('#f6f8fb')]),('VALIGN',(0,0),(-1,-1),'TOP'),('TOPPADDING',(0,0),(-1,-1),7),('BOTTOMPADDING',(0,0),(-1,-1),7),('LEFTPADDING',(0,0),(-1,-1),8),('RIGHTPADDING',(0,0),(-1,-1),8),('LINEBELOW',(0,0),(-1,0),.5,colors.HexColor('#b8c9dc'))]))
        flow += [table,Spacer(1,10)];continue
    if line.startswith('### '):flow.append(Paragraph(inline(line[4:]),styles['Subsection']));i+=1;continue
    if line.startswith('## '):flow.append(Paragraph(inline(line[3:]),styles['Section']));i+=1;continue
    if line.startswith('- ') or re.match(r'^\d+\. ',line):
        content='- '+line[2:] if line.startswith('- ') else line
        flow.append(Paragraph(inline(content),styles['BulletText']));i+=1;continue
    paragraph=[line];i+=1
    while i<len(lines) and lines[i].strip() and not lines[i].startswith(('#','|','```','- ')) and not re.match(r'^\d+\. ',lines[i]):
        paragraph.append(lines[i].strip());i+=1
    flow.append(Paragraph(inline(' '.join(paragraph)),styles['Text']))
doc.multiBuild(flow,onFirstPage=footer,onLaterPages=footer)
print(OUT)

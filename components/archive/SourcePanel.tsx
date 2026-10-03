import { BookOpen, ExternalLink, FileText, ShieldCheck } from 'lucide-react';
import { LocalizedInterface } from '../i18n/LocalizedInterface';

export type SourceRecord = {
  source:string; sourceUrl?:string; pdfUrl?:string; pdfPage?:number;
  excerptPage?:number|null; pageLabel?:string; sourceHost?:string;
  verifiedAt?:string; sourceNote?:string; sourceKind?:string;
};

export function SourcePanel({record,compact=false,language='en'}:{record:SourceRecord;compact?:boolean;language?:string}) {
  const page=record.excerptPage||record.pdfPage;
  const pdf=record.pdfUrl ? `${record.pdfUrl}${page?`#page=${page}`:''}` : undefined;
  return <LocalizedInterface language={language}><section className={`source-panel ${compact?'compact':''}`} aria-label="Original source">
    <div className="source-panel-heading"><ShieldCheck size={19}/><strong>Original source</strong></div>
    <p translate="no">{record.source}</p>
    {record.sourceHost&&<small translate="no">{record.sourceHost}{record.pageLabel?` · ${record.pageLabel}`:''}</small>}
    <div className="source-links">
      {pdf&&<a href={pdf} target="_blank" rel="noopener noreferrer"><FileText size={17}/>Open original PDF<ExternalLink size={14}/></a>}
      {record.sourceUrl&&<a href={record.sourceUrl} target="_blank" rel="noopener noreferrer"><BookOpen size={17}/>Source website<ExternalLink size={14}/></a>}
    </div>
    {!pdf&&<small>No original PDF has been attached to this institutional record.</small>}
    {!compact&&<small>SMRITI’s summary is separate from the original document. PDFs open on the institution’s website.</small>}
  </section></LocalizedInterface>;
}

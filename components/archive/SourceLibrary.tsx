import { useState } from 'react';
import { BookOpen, ExternalLink, FileText } from 'lucide-react';
import { LocalizedInterface } from '../i18n/LocalizedInterface';

type Volume={id:string;title:string;pdfUrl:string;sourceUrl:string;language:string;verifiedAt?:string};
export function SourceLibrary({volumes,language}:{volumes:Volume[];language:string}) {
  const [filter,setFilter]=useState('English');
  const items=volumes.filter(volume=>volume.language===filter);
  return <LocalizedInterface language={language}><section className="source-library">
    <div className="library-heading"><BookOpen/><div><p className="eyebrow">READ THE ORIGINALS</p><h2>Writings & Speeches</h2><p>Official editions. Original PDFs. Direct institutional links.</p></div></div>
    <div className="library-tools"><div role="group" aria-label="Edition language">
      {['English','Hindi'].map(name=><button key={name} aria-pressed={filter===name} className={filter===name?'active':''} onClick={()=>setFilter(name)}>{name}</button>)}
    </div><a href="https://www.mea.gov.in/books-writings-of-ambedkar.htm" target="_blank" rel="noopener noreferrer">Official collection<ExternalLink size={15}/></a></div>
    <div className="volume-grid">{items.map(volume=><a key={volume.id} href={volume.pdfUrl} target="_blank" rel="noopener noreferrer">
      <FileText/><span><b translate="no">{volume.title}</b><small>Original PDF</small></span><ExternalLink size={16}/>
    </a>)}</div>
    <p className="source-note">Hosted by the Ministry of External Affairs. PDF links were checked on 3 October 2026. External availability can change.</p>
  </section></LocalizedInterface>;
}

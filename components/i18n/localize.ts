import { Children, cloneElement, Fragment, isValidElement, type ReactNode } from 'react';

export type Messages = Record<string, string>;
export const messageKey = (text:string) => text.replace(/\s+/g, ' ').trim();
const preserved = new Set(['SMRITI AI','SMRITI-1949','OCR','PNG','JPEG','TIFF','IIIF','SHA-256','PostgreSQL','Microsoft','Wikimedia Commons']);
export function translatable(text:string) {
  const key=messageKey(text);
  return /[A-Za-z]/.test(key) && !preserved.has(key) && !/^(https?:\/\/|[a-f0-9]{32,}$)/i.test(key);
}

/** Translate the React tree before reconciliation, never React-owned DOM nodes.
 * Event handlers, IDs, URL targets and controlled field values remain unchanged.
 */
export function localizeTree(node:ReactNode, messages:Messages, missing:Set<string>):ReactNode {
  function text(value:string) {
    const key=messageKey(value);
    if(!translatable(value)) return value;
    const translated=messages[key];
    if(!translated){
      const labeled=key.match(/^(.+) — ([A-Za-z]+)$/);
      if(labeled && messages[labeled[1]] && messages[labeled[2]])return `${messages[labeled[1]]} — ${messages[labeled[2]]}`;
      const count=key.match(/^(\d+) (pages|records|min)$/);
      if(count && messages[count[2]])return `${count[1]} ${messages[count[2]]}`;
      const entry=key.match(/^ENTRY (\d+)$/);
      if(entry && messages.Entry)return `${messages.Entry} ${entry[1]}`;
      for(const prefix of ['Listen in','Speak in','Remove','Museum guide']){
        if(key.startsWith(prefix+' ') && messages[prefix]){
          const rest=key.slice(prefix.length).trim();
          return `${messages[prefix]} ${messages[rest]||rest}`;
        }
      }
      missing.add(key);return value;
    }
    return (value.match(/^\s*/)?.[0]||'')+translated+(value.match(/\s*$/)?.[0]||'');
  }
  function walk(child:ReactNode):ReactNode {
    if(typeof child==='string')return text(child);
    if(Array.isArray(child))return Children.map(child,walk);
    if(!isValidElement<Record<string, unknown>>(child))return child;
    if(child.type!==Fragment && typeof child.type!=='string')return child; // Icons have no UI messages.
    const props=child.props;
    if(props.translate==='no' || props['data-localize']==='no' || String(props.className||'').split(' ').includes('notranslate') || ['code','pre','script','style','svg'].includes(String(child.type)))return child;
    const next:Record<string,unknown>={};
    for(const attribute of ['placeholder','title','aria-label','alt'])if(typeof props[attribute]==='string')next[attribute]=text(props[attribute] as string);
    // An option without an explicit value otherwise submits its translated label.
    if(child.type==='option' && props.value===undefined && typeof props.children==='string')next.value=props.children;
    if(props.children!==undefined && child.type!=='textarea')next.children=walk(props.children as ReactNode);
    return cloneElement(child,next);
  }
  return walk(node);
}

/** Keep canonical English search working alongside the displayed native text. */
export function localizedSearchText(values:string[],messages:Messages) {
  return values.map(value=>`${value} ${messages[messageKey(value)]||''}`).join(' ').normalize('NFKC').toLocaleLowerCase();
}

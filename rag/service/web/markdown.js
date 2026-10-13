/* Markdown rendered as DOM nodes; HTML is text and links permit HTTP(S) only. */
(function(){
 'use strict';
 function el(tag,text){const n=document.createElement(tag);if(text!==undefined)n.textContent=text;return n;}
 function inline(text,target){
  const pattern=/(`[^`\n]+`|\*\*[^*\n]+\*\*|__[^_\n]+__|~~[^~\n]+~~|\*[^*\n]+\*|\[[^\]\n]+\]\([^\s)]+\))/g;
  let from=0;for(const match of text.matchAll(pattern)){
   target.append(document.createTextNode(text.slice(from,match.index)));const token=match[0];let n;
   if(token.startsWith('`'))n=el('code',token.slice(1,-1));
   else if(token.startsWith('**')||token.startsWith('__')){n=el('strong');inline(token.slice(2,-2),n);}
   else if(token.startsWith('~~'))n=el('del',token.slice(2,-2));
   else if(token.startsWith('*'))n=el('em',token.slice(1,-1));
   else{const m=token.match(/^\[([^\]]+)\]\(([^)]+)\)$/);try{const u=new URL(m[2]);if(!['https:','http:'].includes(u.protocol))throw Error();n=el('a',m[1]);n.href=u.href;n.target='_blank';n.rel='noopener noreferrer';}catch{n=el('span',token);}}
   target.append(n);from=match.index+token.length;
  }target.append(document.createTextNode(text.slice(from)));
 }
 function cells(line){return line.trim().replace(/^\|/,'').replace(/\|$/,'').split('|').map(x=>x.trim());}
 function markdown(text){const root=el('div');root.className='markdown';const lines=String(text||'').replace(/\r\n/g,'\n').split('\n');let i=0;
  while(i<lines.length){const l=lines[i];if(!l.trim()){i++;continue;}
   if(/^\s*```/.test(l)){const language=l.trim().slice(3);const content=[];i++;while(i<lines.length&&!/^\s*```/.test(lines[i]))content.push(lines[i++]);i++;const pre=el('pre');pre.append(el('code',content.join('\n')));if(language)pre.setAttribute('data-language',language);root.append(pre);continue;}
   const heading=l.match(/^(#{1,6})\s+(.+)/);if(heading){const h=el('h'+heading[1].length);inline(heading[2],h);root.append(h);i++;continue;}
   if(/^\s*(?:---+|\*\*\*+)\s*$/.test(l)){root.append(el('hr'));i++;continue;}
   if(i+1<lines.length&&l.includes('|')&&/^\s*\|?\s*:?-{3,}:?\s*(?:\|\s*:?-{3,}:?\s*)+\|?\s*$/.test(lines[i+1])){
    const wrap=el('div');wrap.className='table-wrap';const table=el('table');const head=el('thead'),tr=el('tr');cells(l).forEach(t=>{const th=el('th');inline(t,th);tr.append(th)});head.append(tr);table.append(head);i+=2;const body=el('tbody');while(i<lines.length&&lines[i].includes('|')&&lines[i].trim()){const row=el('tr');cells(lines[i++]).forEach(t=>{const td=el('td');inline(t,td);row.append(td)});body.append(row);}table.append(body);wrap.append(table);root.append(wrap);continue;
   }
   if(/^\s*>/.test(l)){const quote=el('blockquote'),parts=[];while(i<lines.length&&/^\s*>/.test(lines[i]))parts.push(lines[i++].replace(/^\s*>\s?/,''));quote.append(markdown(parts.join('\n')));root.append(quote);continue;}
   if(/^\s*(?:[-+*]|\d+[.)])\s+/.test(l)){
    const ordered=/^\s*\d+[.)]/.test(l),list=el(ordered?'ol':'ul');while(i<lines.length&&/^\s*(?:[-+*]|\d+[.)])\s+/.test(lines[i])&&ordered===/^\s*\d+[.)]/.test(lines[i])){const li=el('li');let t=lines[i++].replace(/^\s*(?:[-+*]|\d+[.)])\s+/,'');const task=t.match(/^\[([ xX])\]\s+/);if(task){const box=el('input');box.type='checkbox';box.checked=task[1]!==' ';box.disabled=true;li.append(box);t=t.slice(task[0].length);}inline(t,li);list.append(li);}root.append(list);continue;
   }
   const p=el('p');inline(l,p);root.append(p);i++;
  }return root;
 }
 window.renderMarkdown=markdown;
})();

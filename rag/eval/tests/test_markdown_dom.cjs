'use strict';
const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
class Node {constructor(tag,text=''){this.tag=tag;this.textContent=text;this.children=[];this.attributes={};}append(...children){this.children.push(...children)}setAttribute(k,v){this.attributes[k]=v}}
const context={window:{},URL,document:{createElement:tag=>new Node(tag),createTextNode:t=>new Node('#text',t)}};
vm.createContext(context);vm.runInContext(fs.readFileSync('rag/service/web/markdown.js','utf8'),context);
const walk=n=>[n,...n.children.flatMap(walk)];
let nodes=walk(context.window.renderMarkdown('# 标题\n\n**加粗** 和 `代码`\n- 列表\n\n| 景点 | 时间 |\n| --- | --- |\n| 龙门 | 10:00 |\n\n```python\nprint(1)\n```\n> 引用'));
for(const t of ['h1','strong','code','ul','table','pre','blockquote'])assert(nodes.some(n=>n.tag===t),t);
nodes=walk(context.window.renderMarkdown('<script>alert(1)</script>\n[危险](javascript:alert(1))\n[来源](https://example.com)'));
assert(!nodes.some(n=>n.tag==='script'||n.tag==='img'));
assert.equal(nodes.filter(n=>n.tag==='a').length,1);assert.equal(nodes.find(n=>n.tag==='a').href,'https://example.com/');
assert(nodes.some(n=>n.textContent.includes('<script>')));
console.log('Markdown DOM tests passed: common blocks, literal HTML, safe links');

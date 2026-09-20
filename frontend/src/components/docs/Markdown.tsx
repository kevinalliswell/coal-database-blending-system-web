import { createElement, Fragment, type ReactNode } from 'react';

const normalizedLines = (text: string) => text.replace(/\r\n?/g, '\n').split('\n');
const headingPattern = /^(#{1,6})[ \t]+(.+?)(?:[ \t]+#+)?[ \t]*$/;
const listPattern = /^([-+*]|\d+\.)[ \t]+(.+)$/;
const tableCells = (line: string) => line.trim().replace(/^\|/, '').replace(/\|$/, '').split(/(?<!\\)\|/).map(cell => cell.trim().replace(/\\\|/g, '|'));
const tableDivider = (line = '') => /^\s*\|/.test(line) && tableCells(line).every(cell => /^:?-{3,}:?$/.test(cell));
const fencePattern = /^\s*(`{3,}|~{3,})(.*)$/;

export interface DocumentHeading { id: string; text: string; level: number; line: number }

/** The table of contents and rendered headings share IDs, including duplicates. */
export function getDocumentHeadings(text: string): DocumentHeading[] {
  const seen = new Map<string, number>(); const headings: DocumentHeading[] = [];
  let fence = '';
  normalizedLines(text).forEach((line, index) => {
    const marker = line.match(fencePattern)?.[1];
    if (marker) {
      if (!fence) fence = marker;
      else if (marker[0] === fence[0] && marker.length >= fence.length) fence = '';
      return;
    }
    if (fence) return;
    const heading = line.match(headingPattern);
    if (!heading) return;
    const label = heading[2].replace(/[`*]/g, '');
    const base = label.toLowerCase().replace(/[^\p{L}\p{N}\s-]/gu, '').trim().replace(/\s+/g, '-') || 'section';
    const count = (seen.get(base) || 0) + 1; seen.set(base, count);
    headings.push({ id: count === 1 ? base : `${base}-${count}`, text: label, level: heading[1].length, line: index });
  });
  return headings;
}

function inline(text: string): ReactNode[] {
  return text.split(/(`[^`]+`|\*\*[^*]+\*\*|\[[^\]]+\]\([^)]+\))/g).filter(Boolean).map((part, i) => {
    if (part.startsWith('`')) return <code key={i}>{part.slice(1, -1)}</code>;
    if (part.startsWith('**')) return <strong key={i}>{part.slice(2, -2)}</strong>;
    const link = part.match(/^\[([^\]]+)\]\(([^)]+)\)$/);
    if (link) {
      const target = link[2].replace(/^docs\//, '');
      if (/^https:\/\//.test(target)) return <a key={i} href={target} target="_blank" rel="noopener noreferrer">{link[1]}</a>;
      if (/^#[^\s]+$/.test(target)) return <a key={i} href={target}>{link[1]}</a>;
      const document = target.match(/^([A-Z0-9_.-]+\.md)(#[^\s]+)?$/);
      if (document) return <a key={i} href={`/help?document=${encodeURIComponent(document[1])}${document[2] || ''}`}>{link[1]}</a>;
      return <Fragment key={i}>{link[1]}</Fragment>;
    }
    return <Fragment key={i}>{part}</Fragment>;
  });
}

/** Render our document subset with semantic elements; embedded HTML stays text. */
export function Markdown({ text }: { text: string }) {
  const lines = normalizedLines(text); const nodes: ReactNode[] = [];
  const headings = new Map(getDocumentHeadings(text).map(heading => [heading.line, heading]));
  const startsBlock = (index: number) => !lines[index]?.trim() || headings.has(index)
    || fencePattern.test(lines[index]) || listPattern.test(lines[index])
    || lines[index].startsWith('> ') || (lines[index].trim().startsWith('|') && tableDivider(lines[index + 1]));
  for (let i = 0; i < lines.length; i++) {
    const line = lines[i]; if (!line.trim()) continue;
    const fence = line.match(fencePattern);
    if (fence) {
      const code: string[] = [];
      while (++i < lines.length) {
        const closing = lines[i].match(fencePattern)?.[1];
        if (closing && closing[0] === fence[1][0] && closing.length >= fence[1].length) break;
        code.push(lines[i]);
      }
      nodes.push(<pre key={i}><code>{code.join('\n')}</code></pre>); continue;
    }
    const heading = headings.get(i);
    if (heading) {
      nodes.push(createElement(`h${Math.min(6, heading.level + 1)}`, { key: i, id: heading.id }, inline(line.match(headingPattern)![2]))); continue;
    }
    if (line.trim().startsWith('|') && tableDivider(lines[i + 1])) {
      const headers = tableCells(line); const rows: string[][] = []; i++;
      while (lines[i + 1]?.trim().startsWith('|')) rows.push(tableCells(lines[++i]));
      nodes.push(<div className="doc-table-scroll" key={i} tabIndex={0} role="region" aria-label="文档表格"><table><thead><tr>{headers.map((header, j) => <th scope="col" key={j}>{inline(header)}</th>)}</tr></thead><tbody>{rows.map((row, j) => <tr key={j}>{headers.map((_, k) => <td key={k}>{inline(row[k] || '')}</td>)}</tr>)}</tbody></table></div>); continue;
    }
    const list = line.match(listPattern);
    if (list) {
      const ordered = /^\d/.test(list[1]); const items = [list[2]];
      while (listPattern.test(lines[i + 1] || '')) {
        const next = lines[i + 1].match(listPattern)!;
        if (/^\d/.test(next[1]) !== ordered) break;
        items.push(next[2]); i++;
      }
      nodes.push(createElement(ordered ? 'ol' : 'ul', { key: i, ...(ordered && parseInt(list[1]) !== 1 ? { start: parseInt(list[1]) } : {}) }, items.map((item, j) => <li key={j}>{inline(item)}</li>))); continue;
    }
    if (line.startsWith('> ')) {
      const quote = [line.slice(2)];
      while (lines[i + 1]?.startsWith('> ')) quote.push(lines[++i].slice(2));
      nodes.push(<blockquote key={i}><p>{inline(quote.join(' '))}</p></blockquote>); continue;
    }
    const paragraph = [line.trim()];
    while (i + 1 < lines.length && !startsBlock(i + 1)) paragraph.push(lines[++i].trim());
    nodes.push(<p key={i}>{inline(paragraph.join(' '))}</p>);
  }
  return <>{nodes}</>;
}

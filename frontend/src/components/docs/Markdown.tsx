import { createElement, Fragment, type ReactNode } from 'react';

function inline(text: string): ReactNode[] {
  return text.split(/(`[^`]+`|\*\*[^*]+\*\*|\[[^\]]+\]\([^)]+\))/g).filter(Boolean).map((part, i) => {
    if (part.startsWith('`')) return <code key={i}>{part.slice(1, -1)}</code>;
    if (part.startsWith('**')) return <strong key={i}>{part.slice(2, -2)}</strong>;
    const link = part.match(/^\[([^\]]+)\]\(([^)]+)\)$/);
    if (link) {
      const target = link[2].replace(/^docs\//, '');
      if (/^https:\/\//.test(target)) return <a key={i} href={target} target="_blank" rel="noopener noreferrer">{link[1]}</a>;
      if (/^[A-Z0-9_.-]+\.md$/.test(target)) return <a key={i} href={`/help?document=${encodeURIComponent(target)}`}>{link[1]}</a>;
      return <Fragment key={i}>{link[1]}</Fragment>;
    }
    return <Fragment key={i}>{part}</Fragment>;
  });
}

/** Render the repository's small Markdown subset without accepting embedded HTML. */
export function Markdown({ text }: {text: string}) {
  const lines = text.split('\n'); const nodes: ReactNode[] = [];
  for (let i = 0; i < lines.length; i++) {
    const line = lines[i]; if (!line.trim()) continue;
    if (line.startsWith('```')) {
      const code: string[] = [];
      while (++i < lines.length && !lines[i].startsWith('```')) code.push(lines[i]);
      nodes.push(<pre key={i}><code>{code.join('\n')}</code></pre>); continue;
    }
    const heading = line.match(/^(#{1,6}) (.+)$/);
    if (heading) { nodes.push(createElement(`h${Math.min(6, heading[1].length + 1)}`, {key: i}, inline(heading[2]))); continue; }
    if (line.startsWith('|') && /^\|[\s:|-]+\|$/.test(lines[i + 1] || '')) {
      const cells = (row: string) => row.slice(1, -1).split('|').map(v => v.trim());
      const headers = cells(line); const rows: string[][] = []; i++;
      while (lines[i + 1]?.startsWith('|')) rows.push(cells(lines[++i]));
      nodes.push(<div className="tbl-wrap" key={i}><table><thead><tr>{headers.map((h,j) => <th key={j}>{inline(h)}</th>)}</tr></thead><tbody>{rows.map((row,j) => <tr key={j}>{row.map((cell,k) => <td key={k}>{inline(cell)}</td>)}</tr>)}</tbody></table></div>); continue;
    }
    if (/^(- |\d+\. )/.test(line)) {
      const ordered = /^\d/.test(line); const items = [line.replace(/^(- |\d+\. )/, '')];
      while (/^(- |\d+\. )/.test(lines[i+1] || '')) items.push(lines[++i].replace(/^(- |\d+\. )/, ''));
      nodes.push(createElement(ordered ? 'ol' : 'ul', {key:i}, items.map((item,j) => <li key={j}>{inline(item)}</li>))); continue;
    }
    nodes.push(<p key={i}>{inline(line)}</p>);
  }
  return <>{nodes}</>;
}

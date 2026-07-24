"use client";

import React from "react";

/** 行内解析：将 **加粗** 渲染为 <strong>。返回 React 节点数组（XSS 安全，不注入 HTML）。 */
function renderInline(text: string, keyBase: string): React.ReactNode[] {
  const parts = text.split(/(\*\*[^*]+\*\*)/g);
  return parts.map((p, i) => {
    if (p.startsWith("**") && p.endsWith("**") && p.length > 4) {
      return (
        <strong key={`${keyBase}-b${i}`} className="font-semibold">
          {p.slice(2, -2)}
        </strong>
      );
    }
    return <React.Fragment key={`${keyBase}-t${i}`}>{p}</React.Fragment>;
  });
}

/**
 * 轻量 Markdown 渲染器（自包含、XSS 安全）。
 * 支持本项目中「合同审查报告」用到的语法：
 * 标题(#/##/###)、加粗(**)、无序列表(- )、引用(> )、代码围栏(```)、分隔线(---)、
 * 以及 <details>/<summary> 折叠块（完整报告附录）。
 * 全部以 React 节点输出，避免 dangerouslySetInnerHTML。
 */
export function Markdown({ content, className }: { content: string; className?: string }) {
  const lines = content.split("\n");
  const blocks: React.ReactNode[] = [];
  let i = 0;
  let key = 0;

  while (i < lines.length) {
    const line = lines[i];

    // 代码围栏
    if (line.trim().startsWith("```")) {
      const buf: string[] = [];
      i++;
      while (i < lines.length && !lines[i].trim().startsWith("```")) {
        buf.push(lines[i]);
        i++;
      }
      i++; // 跳过结束 ```
      blocks.push(
        <pre
          key={key++}
          className="my-3 overflow-x-auto rounded-md bg-gray-100 dark:bg-white/10 p-3 text-xs leading-relaxed"
        >
          <code>{buf.join("\n")}</code>
        </pre>
      );
      continue;
    }

    // <details> 折叠块（完整报告附录）
    if (line.trim() === "<details>") {
      let summary = "点击展开";
      const inner: string[] = [];
      i++;
      while (i < lines.length && lines[i].trim() !== "</details>") {
        const l = lines[i].trim();
        const sm = l.match(/^<summary>(.*)<\/summary>$/);
        if (sm) {
          summary = sm[1];
        } else {
          inner.push(lines[i]);
        }
        i++;
      }
      i++; // 跳过 </details>
      blocks.push(
        <details
          key={key++}
          className="my-3 rounded-md border border-gray-200 dark:border-white/10 p-3"
        >
          <summary className="cursor-pointer font-medium text-gray-700 dark:text-gray-200">
            {summary}
          </summary>
          <pre className="mt-2 overflow-x-auto text-xs leading-relaxed text-gray-600 dark:text-gray-300">
            <code>{inner.join("\n").trim()}</code>
          </pre>
        </details>
      );
      continue;
    }

    // 分隔线
    if (/^---+$/.test(line.trim())) {
      blocks.push(<hr key={key++} className="my-4 border-gray-200 dark:border-white/10" />);
      i++;
      continue;
    }

    // 标题
    const h = line.match(/^(#{1,3})\s+(.*)$/);
    if (h) {
      const level = h[1].length;
      const text = h[2];
      const cls =
        level === 1
          ? "text-2xl font-bold mt-2 mb-3"
          : level === 2
          ? "text-xl font-semibold mt-5 mb-2"
          : "text-base font-semibold mt-4 mb-2";
      const Tag = (`h${level}` as unknown) as keyof JSX.IntrinsicElements;
      blocks.push(
        <Tag key={key++} className={`${cls} text-gray-900 dark:text-gray-100`}>
          {renderInline(text, `h${key}`)}
        </Tag>
      );
      i++;
      continue;
    }

    // 引用
    if (line.trim().startsWith(">")) {
      const buf: string[] = [];
      while (i < lines.length && lines[i].trim().startsWith(">")) {
        buf.push(lines[i].trim().replace(/^>\s?/, ""));
        i++;
      }
      blocks.push(
        <blockquote
          key={key++}
          className="my-2 border-l-4 border-gray-300 dark:border-white/20 pl-3 text-gray-600 dark:text-gray-300 italic"
        >
          {buf.map((b, bi) => (
            <p key={bi} className="my-1">
              {renderInline(b, `q${key}-${bi}`)}
            </p>
          ))}
        </blockquote>
      );
      continue;
    }

    // 无序列表
    if (/^\s*-\s+/.test(line)) {
      const items: string[] = [];
      while (i < lines.length && /^\s*-\s+/.test(lines[i])) {
        items.push(lines[i].replace(/^\s*-\s+/, ""));
        i++;
      }
      blocks.push(
        <ul key={key++} className="my-2 list-disc space-y-1 pl-6 text-gray-700 dark:text-gray-200">
          {items.map((it, ii) => (
            <li key={ii}>{renderInline(it, `li${key}-${ii}`)}</li>
          ))}
        </ul>
      );
      continue;
    }

    // 空行
    if (line.trim() === "") {
      i++;
      continue;
    }

    // 段落（合并连续非空、非特殊行）
    const para: string[] = [];
    while (
      i < lines.length &&
      lines[i].trim() !== "" &&
      !lines[i].trim().startsWith("```") &&
      !lines[i].trim().startsWith("#") &&
      !lines[i].trim().startsWith(">") &&
      !/^\s*-\s+/.test(lines[i]) &&
      !/^---+$/.test(lines[i].trim()) &&
      lines[i].trim() !== "<details>"
    ) {
      para.push(lines[i]);
      i++;
    }
    blocks.push(
      <p key={key++} className="my-2 leading-relaxed text-gray-700 dark:text-gray-200">
        {para.map((p, pi) => (
          <React.Fragment key={pi}>
            {pi > 0 && <br />}
            {renderInline(p, `p${key}-${pi}`)}
          </React.Fragment>
        ))}
      </p>
    );
  }

  return <div className={className}>{blocks}</div>;
}

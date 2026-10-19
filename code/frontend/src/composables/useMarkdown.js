// 把 AI 输出的 Markdown（含 LaTeX 数学）渲染成安全 HTML。
// 流程：抽取数学公式占位 → marked 解析 Markdown → DOMPurify 消毒 → 还原 KaTeX。
import { marked } from 'marked';
import DOMPurify from 'dompurify';
import katex from 'katex';

marked.setOptions({ gfm: true, breaks: true });

function renderMath(expr, display) {
  try {
    return katex.renderToString(expr, { displayMode: display, throwOnError: false });
  } catch {
    return expr;
  }
}

/**
 * 渲染富文本（Markdown + 数学）为消毒后的 HTML 字符串。
 * 支持：**粗体**、列表、代码块、`行内代码`、标题、引用，
 * 以及 $$…$$ / \[…\]（块级公式）和 $…$ / \(…\)（行内公式）。
 */
export function renderRich(src) {
  if (src == null || src === '') return '';
  const math = [];
  const stash = (expr, display) => {
    const token = `@@IFMATH${math.length}@@`;
    math.push(renderMath(expr.trim(), display));
    return token;
  };

  let text = String(src);
  // 先把数学公式抽出占位，避免被 Markdown 误处理
  text = text.replace(/\$\$([\s\S]+?)\$\$/g, (_, e) => stash(e, true));     // $$ … $$
  text = text.replace(/\\\[([\s\S]+?)\\\]/g, (_, e) => stash(e, true));      // \[ … \]
  text = text.replace(/\\\(([\s\S]+?)\\\)/g, (_, e) => stash(e, false));     // \( … \)
  text = text.replace(/\$([^\n$]+?)\$/g, (_, e) => stash(e, false));         // $ … $

  let html = marked.parse(text);
  html = DOMPurify.sanitize(html);
  // KaTeX 输出可信，放在消毒之后还原，避免被剥离
  html = html.replace(/@@IFMATH(\d+)@@/g, (_, i) => math[Number(i)] ?? '');
  return html;
}

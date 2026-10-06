import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import remarkMath from "remark-math";
import rehypeKatex from "rehype-katex";
import { WidgetHost } from "mathbank-widgets";
import { normalizeMathDelimiters } from "../../lib/markdown.js";
import { parseWidgetBlock, widgetSourceFromPre } from "../../lib/widgetBlocks.mjs";
import { mentionedProblemCodes } from "../../lib/problemDiagrams.mjs";
import ProblemDiagrams, { SourceImage } from "./ProblemDiagrams.jsx";
import ProblemSource from "./ProblemSource.jsx";

const renderInline = (t) => <MathText>{t}</MathText>;

// ```widget fenced JSON from the tutor becomes a whitelisted, declarative widget card (never executed).
const components = {
  img({ node, ...props }) {
    const src = props.src?.startsWith("/api/rest/solve/images/") && !props.src.includes("?")
      ? `${props.src}?v=question-figures` : props.src;
    return <SourceImage key={src} {...props} src={src} className="mb-source-image" />;
  },
  pre({ node, children, ...props }) {
    const source = widgetSourceFromPre(node);
    if (source == null) return <pre {...props}>{children}</pre>;
    const parsed = parseWidgetBlock(source);
    if (parsed?.spec) return <WidgetHost spec={parsed.spec} renderMath={renderInline} className="my-2" />;
    if (parsed?.pending) return <div className="small text-secondary my-2" data-testid="widget-pending">Preparing a visual…</div>;
    return <pre {...props}>{children}</pre>;
  },
};

export default function MathText({ children }) {
  return (
    <div className="markdown-body">
      {mentionedProblemCodes(children || "", { includeEmbedded: true }).map((code) => <ProblemSource key={code} code={code} />)}
      <ReactMarkdown remarkPlugins={[remarkGfm, remarkMath]} rehypePlugins={[rehypeKatex]} components={components}>
        {normalizeMathDelimiters(children || "")}
      </ReactMarkdown>
      {mentionedProblemCodes(children || "").map((code) => <ProblemDiagrams key={code} code={code} showSource={false} />)}
    </div>
  );
}

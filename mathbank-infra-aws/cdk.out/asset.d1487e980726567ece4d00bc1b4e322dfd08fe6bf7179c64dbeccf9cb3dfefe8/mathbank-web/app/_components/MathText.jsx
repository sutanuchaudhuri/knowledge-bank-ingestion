import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import remarkMath from "remark-math";
import rehypeKatex from "rehype-katex";
import { WidgetHost } from "mathbank-widgets";
import { prepareMathMarkdown } from "../../lib/markdownText.mjs";
import { parseWidgetBlock, widgetSourceFromPre } from "../../lib/widgetBlocks.mjs";
import { mentionedProblemCodes } from "../../lib/problemDiagrams.mjs";
import ProblemDiagrams, { SourceImage } from "./ProblemDiagrams.jsx";
import ProblemSource from "./ProblemSource.jsx";
import { geometryArtifactSource } from "../../lib/tutorProblem.mjs";
import GeometryArtifact from "./GeometryArtifact.jsx";
import AsymptoteDiagram from "./AsymptoteDiagram.jsx";
import { geometrySceneSource } from "../../lib/geometryScenes.mjs";
import GeometryScene from "./GeometryScene.jsx";

const renderInline = (t) => <MathText>{t}</MathText>;
const learningPlanSections = new Map([
  ["why this route", "route"],
  ["your first checkpoint", "checkpoint"],
  ["evidence", "evidence"],
]);

// ```widget fenced JSON from the tutor becomes a whitelisted, declarative widget card (never executed).
const components = {
  p({ node, children, ...props }) {
    const standaloneLabel = node?.children?.length === 1 && node.children[0].tagName === "strong";
    const first = node?.children?.[0];
    const label = first?.tagName === "strong"
      ? first.children?.map((child) => child.value || "").join("").trim().replace(/:$/, "").toLowerCase()
      : "";
    const planSection = learningPlanSections.get(label);
    const classes = [
      standaloneLabel && "mb-markdown-section-label",
      planSection && `mb-learning-plan-panel mb-learning-plan-${planSection}`,
    ].filter(Boolean).join(" ");
    return <p {...props} className={classes || undefined}>{children}</p>;
  },
  a({ node, href, children, ...props }) {
    const tone = /^#mb-tone-(given|goal|insight|warning)$/.exec(href || "")?.[1];
    if (tone) return <span className={`mb-format-${tone}`} title={{ given: "Given", goal: "Goal", insight: "Key insight", warning: "Caution" }[tone]}>{children}</span>;
    return <a href={href} {...props}>{children}</a>;
  },
  img({ node, ...props }) {
    const src = props.src?.startsWith("/api/rest/solve/images/") && !props.src.includes("?")
      ? `${props.src}?v=question-figures` : props.src;
    return <SourceImage key={src} {...props} src={src} className="mb-source-image" />;
  },
  pre({ node, children, ...props }) {
    const scene = geometrySceneSource(node);
    if (scene?.scene) return <GeometryScene key={`${scene.scene.scene_id}:${scene.scene.version}`} scene={scene.scene} />;
    if (scene?.error) return <div role="alert" className="text-danger">{scene.error}</div>;
    if (scene?.pending) return <div role="status" className="text-secondary small">Receiving geometry scene…</div>;
    const code = node?.children?.find((child) => child.tagName === "code");
    const classes = code?.properties?.className || [];
    const languages = Array.isArray(classes) ? classes : [classes];
    if (languages.includes("language-asymptote-pending")) return <div role="status" className="text-secondary small">Receiving diagram source...</div>;
    if (languages.includes("language-asymptote") || languages.includes("language-asy")) {
      return <AsymptoteDiagram source={(code.children || []).map((child) => child.value || "").join("").trim()} />;
    }
    const geometry = geometryArtifactSource(node);
    if (geometry?.plan) return <GeometryArtifact plan={geometry.plan} renderMath={renderInline} />;
    if (geometry?.error) return <div role="alert" className="text-danger">{geometry.error}</div>;
    if (geometry?.pending) return <div role="status" className="text-secondary small">Preparing a geometry diagram…</div>;
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
        {prepareMathMarkdown(children || "")}
      </ReactMarkdown>
      {mentionedProblemCodes(children || "").map((code) => <ProblemDiagrams key={code} code={code} showSource={false} />)}
    </div>
  );
}

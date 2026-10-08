import { PageHeader } from "../../../_components/ui.jsx";
import GeometrySceneRun from "./GeometrySceneRun.jsx";

export default async function GeometryScenesPage({ searchParams }) {
  const params = await searchParams;
  const run = params?.run;
  return <>
    <PageHeader icon="activity" title="Geometry scene diagnostics" subtitle="Inspect an orchestration run without generating a new scene." />
    <GeometrySceneRun run={run} owner={params?.owner} />
  </>;
}

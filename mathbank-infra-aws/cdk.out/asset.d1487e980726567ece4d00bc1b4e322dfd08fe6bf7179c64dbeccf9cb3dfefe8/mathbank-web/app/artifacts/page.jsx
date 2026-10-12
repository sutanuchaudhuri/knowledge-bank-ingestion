import ArtifactLibrary from "./ArtifactLibrary.jsx";
import { hasValidAdminSession } from "../../lib/session.js";

export default async function ArtifactsPage() { return <ArtifactLibrary canGenerate={await hasValidAdminSession()} />; }

import Classroom from "../../_components/Classroom.jsx";

export const dynamic = "force-dynamic";

export default async function StudentPage({ params }) {
  const { sid } = await params;
  return <Classroom sid={sid} />;
}

export const CODE = "PRASOLOV_PGV1_CH06_P031";
export function intent(step = "DEFINE_A1") {
  const requirements = {
    DEFINE_A1: ["quadrilateral_ABCD", "triangle_BCD", "A1"],
    SHARED_CD: ["triangle_BCD", "triangle_CDA", "A1", "B1", "segment_CD"],
    EQUAL_RADII: ["triangle_BCD", "A1", "radius_A1C", "radius_A1D"],
    ITERATE_CIRCUMCENTERS: ["quadrilateral_A1B1C1D1", "A1", "B1", "C1", "D1"],
  };
  return {
    artifact_goal: "TEACH_CURRENT_OBJECT", problem_code: CODE, current_step: step,
    must_show: requirements[step], max_level: step === "ITERATE_CIRCUMCENTERS" ? 2 : 1,
    setup: {
      problem_code: CODE, version: "circumcenter-iteration-v1", base: { vertices: [..."ABCD"] },
      coordinate_policy: "illustrative-nondegenerate-not-source",
      definitions: [1, 2].flatMap((level) => [..."ABCD"].map((letter, index) => ({
        id: `${letter}${level}`, type: "circumcenter", level, provenance: "canonical-statement-definition",
        triangle: [1, 2, 3].map((offset) => {
          const v = "ABCD"[(index + offset) % 4];
          return level === 1 ? v : `${v}1`;
        }),
      }))),
    },
  };
}

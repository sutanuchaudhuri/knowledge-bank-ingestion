"""Original synthetic examples, independent of the corpus and paid providers."""

from geometry_scene.schemas import (
    Entity,
    MathObject,
    Relation,
    RelationStatus,
    RelationType,
    SceneInput,
    VisualDelta,
)

from .models import (
    AddProvisionalCurve,
    ConstructionProgram,
    CreateScene,
    LayoutAngle,
    MathematicalVariable,
    Present,
    PromoteCurve,
    TrustedFacts,
)


def examples() -> dict[str, tuple[ConstructionProgram, TrustedFacts]]:
    layout_scene = SceneInput(
        scene_id="free_intersection",
        problem_text="Two lines intersect at P. Their angle is not specified.",
        objects={name: MathObject() for name in ("A", "P", "B")},
        entities=(
            Entity(id="line_AP", type="LINE", refs=("A", "P")),
            Entity(id="line_PB", type="LINE", refs=("P", "B")),
        ),
    )
    layout = ConstructionProgram(
        id="free_intersection",
        steps=(
            CreateScene(
                scene=layout_scene,
                mathematical_variables=(
                    MathematicalVariable(
                        name="theta", meaning="Unspecified angle APB", unit="DEGREES"
                    ),
                ),
                layout_variables=(
                    LayoutAngle(
                        name="theta_layout",
                        points=("A", "P", "B"),
                        minimum=35,
                        maximum=145,
                        preference=73,
                    ),
                ),
            ),
            Present(
                visual=VisualDelta(
                    highlight=("point_P",), caption="A readable representative; no angle is given."
                )
            ),
        ),
    )
    target = Relation(
        id="cyclic",
        type=RelationType.CONCYCLIC,
        args=("A", "B", "C", "D"),
        status=RelationStatus.TARGET_TO_PROVE,
    )
    initial = CreateScene(
        scene=SceneInput(
            scene_id="provisional_cycle",
            problem_text="Four points are shown. Their concyclicity is a target, not a given.",
            objects={name: MathObject() for name in ("A", "B", "C", "D")},
            positions={"A": (130, 110), "B": (430, 140), "C": (485, 335), "D": (160, 365)},
            relations=(target,),
        )
    )
    guide = AddProvisionalCurve(id="gamma", through=("A", "B", "C", "D"))
    proof = target.model_copy(
        update={
            "status": RelationStatus.PROVEN,
            "provenance": "Synthetic host-approved proof fixture, not derived from layout or model prose.",
        }
    )
    provisional = ConstructionProgram(id="provisional_only", steps=(initial, guide))
    promotion = ConstructionProgram(
        id="trusted_promotion",
        steps=(
            initial,
            guide,
            PromoteCurve(curve_id="gamma", trusted_relation_id="cyclic", relayout=True),
            Present(
                visual=VisualDelta(
                    highlight=("circle_cyclic",),
                    caption="Concyclicity was verified by external evidence.",
                )
            ),
        ),
    )
    return {
        "01_free_intersection": (layout, TrustedFacts()),
        "02_provisional_curve": (provisional, TrustedFacts()),
        "03_trusted_circle_promotion": (promotion, TrustedFacts(relations=(proof,))),
    }

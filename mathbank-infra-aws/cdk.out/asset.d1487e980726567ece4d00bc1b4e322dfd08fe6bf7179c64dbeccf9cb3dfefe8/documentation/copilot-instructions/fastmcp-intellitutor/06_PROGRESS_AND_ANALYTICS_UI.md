# 06 — Student Progress and Analytics UI

## 1. Rich UI + model-readable summary

Progress is a strong use case for `ToolResult`:

- user sees charts/tables/cards;
- model sees a concise summary it can reason about.

Do not make the model parse the rendered UI.

## 2. Learner progress wireframe

```text
┌──────────────────────────────────────────────────────────────────┐
│ Your Progress                                                    │
│ Courses 3     Completed 1     Problems 84     This week 6.2 h   │
├──────────────────────────────────────────────────────────────────┤
│ Course progress                                                  │
│ Markov Chains      ███████░░  72%                                │
│ Inequalities       █████████  94%                                │
│ Polynomials        █████░░░░  53%                                │
├──────────────────────────────────────────────────────────────────┤
│ Recent focus areas                                               │
│ • Transition matrix row normalization                            │
│ • Vieta transformed roots                                       │
│ • Jensen convexity direction                                     │
├──────────────────────────────────────────────────────────────────┤
│ Practice history [searchable table]                              │
└──────────────────────────────────────────────────────────────────┘
```

## 3. Prefab implementation pattern

Verified Prefab components suitable here:
- `Metric`;
- `BarChart` / chart family;
- `DataTable`;
- `Badge`;
- `Card`;
- `Column`, `Row`, `Grid`.

## 4. Example

```python
from fastmcp.tools import ToolResult
from prefab_ui.app import PrefabApp
from prefab_ui.components import Column, Grid, Metric, DataTable, DataTableColumn
from prefab_ui.components.charts import BarChart, ChartSeries

@progress_app.ui()
def open_progress() -> ToolResult:
    actor = require_student()
    dto = progress_service.student_dashboard(actor.student_id)

    with Column(gap=4, css_class="p-6") as view:
        with Grid(columns=[1, 1, 1], gap=3):
            Metric(label="Problems", value=str(dto.problems_completed))
            Metric(label="Courses", value=str(dto.courses_active))
            Metric(label="Hours this week", value=f"{dto.hours_week:.1f}")

        BarChart(
            data=dto.course_progress_rows,
            series=[ChartSeries(data_key="percent", label="Complete")],
            x_axis="course",
        )

        DataTable(
            columns=[
                DataTableColumn(key="date", header="Date", sortable=True),
                DataTableColumn(key="activity", header="Activity"),
                DataTableColumn(key="result", header="Result"),
            ],
            rows=dto.recent_activity,
            search=True,
        )

    summary = (
        f"{dto.courses_active} active courses; "
        f"{dto.problems_completed} problems completed; "
        f"current focus: {', '.join(dto.focus_labels[:3])}."
    )

    return ToolResult(content=summary, structured_content=view)
```

Adapt exact return typing to installed FastMCP/FastMCP Apps version.

## 5. Privacy

Student UI may show the learner's own:
- attempts;
- course progress;
- hints;
- mastered/working-on labels defined by product policy.

Instructor/admin aggregate dashboard may show:
- cohort completion;
- quiz accuracy;
- route usage;
- aggregated misconception counts.

Do not put learner-specific misconception edges in shared Neo4j.

## 6. Agentic progress follow-up

Because the model receives the summary, the user can ask:

```text
"What should I work on today?"
```

The assistant may call safe recommendation tools that use:
- approved course prerequisites;
- learner-owned progress;
- published problem corpus.

Recommendations should cite/identify why:
- incomplete prerequisite;
- repeated error signature;
- upcoming course checkpoint;
- transfer practice need.

The recommendation system must not create new canonical content.

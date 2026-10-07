# Visual Policy Engine

## Defaults

Vertices:
- small dots,
- readable labels,
- collision avoidance.

Primary segments:
- solid,
- stronger than background curves.

Auxiliary constructions:
- lighter or dashed.

Extensions:
- dashed/dotted.

Circles:
- thin/light unless central.

Contact points:
- explicitly marked if relevant.

Angle marks:
- only current/relevant,
- avoid overlap,
- never imply an unproved relation.

## Status rules

GIVEN:
- may render faithfully.

PROVEN:
- may promote visually.

TARGET_TO_PROVE:
- must not be visually asserted.

UNKNOWN:
- must not be rendered as true.

ASSUMED_FOR_CONSTRUCTION:
- may use construction styling.

## Large circle policy

```text
FULL_CIRCLE
VISIBLE_ARC
CLIPPED_CIRCLE
```

## Broken-line policy

If straightness is target-to-prove, use noncommittal/broken representation until proof.

## Highlight policy

At each step emphasize only the current pedagogical focus.

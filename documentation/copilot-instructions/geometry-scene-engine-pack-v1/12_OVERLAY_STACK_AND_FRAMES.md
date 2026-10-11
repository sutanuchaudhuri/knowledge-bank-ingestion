# Overlay Stack and Frames

```text
Frame 0 = Base
Frame 1 = Frame 0 + Overlay 1
Frame 2 = Frame 1 + Overlay 2
Frame 3 = Frame 2 + Overlay 3
```

Frame metadata:

```text
frame_id
step_number
math_state_version
scene_state_version
visual_state_version
overlay_operations[]
caption
linked_solution_step_id
```

UI should support:

```text
Previous
Next
Play
Pause
Scrub
```

Existing points should not move between frames unless an explicit re-layout is requested.

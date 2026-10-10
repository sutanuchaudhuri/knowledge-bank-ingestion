# Markov Chains — Original Manim Storyboard

All narration below is course-authored. Planned timestamps must be reconciled after render.

## Scene 1 — What is a state? (0:00–1:45)
0:00–0:25 Show a long path history.
0:25–0:55 Collapse relevant history into current state.
0:55–1:20 Markov property: next-step law depends on current state.
1:20–1:45 Warning: memoryless process != careless state design.
Tags: PROB_MARKOV, TECH_STATE_GRAPH.
Misconceptions: MC-M01.

## Scene 2 — AMC 2019 state compression (0:00–2:20)
0:00–0:35 Show many labeled money configurations.
0:35–1:00 Merge into A=(1,1,1) and B=type (2,1,0).
1:00–1:35 Derive A->A=1/4, A->B=3/4, B->A=1/4, B->B=3/4.
1:35–2:05 Show after one step distribution is (1/4,3/4).
2:05–2:20 Apply transition again and show it remains unchanged.
Problem bridge: AMC10_2019B_Q22 / AMC12_2019B_Q19.

## Scene 3 — First-step hitting probability (0:00–2:40)
0:00–0:35 Define h_i as probability of eventual success.
0:35–1:10 Condition on first transition.
1:10–1:35 Derive h_i = ΣP_ij h_j.
1:35–2:05 Set success=1, failure=0.
2:05–2:40 Build the frog 0..4 + disappeared model.
Problem bridge: AMC12_2025B_Q20.
Misconceptions: MC-M06, MC-M07.

## Scene 4 — Triangle bug recurrence (0:00–2:10)
0:00–0:35 Three physical vertices.
0:35–1:00 Compress Y/Z into "not home".
1:00–1:25 p_(n+1)=1/2(1-p_n).
1:25–1:50 subtract fixed point 1/3.
1:50–2:10 geometric convergence with alternating sign.
Problem bridge: AIME_2003_II_Q13.

## Scene 5 — Transition matrices (0:00–2:20)
0:00–0:30 Convert arrows to P_ij.
0:30–0:55 Verify each row sums to 1.
0:55–1:25 μ_(n+1)=μ_nP.
1:25–1:55 P^n as n-step transitions.
1:55–2:20 warning about row vs column convention.
Tags: PROB_MARKOV_MATRIX, ALG_MATRIX.
Misconceptions: MC-M02, MC-M09.

## Scene 6 — Stationarity and periodicity (0:00–2:40)
0:00–0:40 πP=π.
0:40–1:10 solve a 2-state stationary distribution.
1:10–1:40 interpret long-run proportions.
1:40–2:10 deterministic A<->B alternation.
2:10–2:40 explain: stationary exists, but point-mass start oscillates.
Misconception: MC-M04.

# Learning graph

PROB_BASIC
   |
   +--> PROB_COND ----------------------+
   |                                    |
   +--> PROB_EXP                        |
   |                                    v
   +--> COUNT_REC ----------------> PROB_MARKOV
                                        |
                                        +--> TECH_STATE_GRAPH
                                        |       |
                                        |       +--> state compression
                                        |       +--> first-step equations
                                        |
                                        +--> hitting / absorption
                                        |       |
                                        |       +--> probability of eventual success
                                        |       +--> expected hitting time
                                        |
                                        +--> PROB_MARKOV_MATRIX
                                                |
                                                +--> P^n
                                                +--> linear systems
                                                +--> stationary distribution
                                                +--> long-run behavior

ALG_MATRIX is helpful for the matrix track but not required for the first-step recurrence track.

## Competition-first technique map

Use direct conditioning when:
- only one or two steps matter;
- symmetry collapses the state space immediately.

Use state compression when:
- many physical configurations behave identically;
- only a small statistic of the current configuration affects the future.

Use first-step recursion when:
- the question asks "eventually";
- the process can revisit states;
- enumerating all paths is impossible or wasteful.

Use transition matrices when:
- n-step probabilities matter;
- there are a small number of stable states;
- repeated application is central.

Use absorbing-chain equations when:
- there are success/failure terminal states;
- the target is a hitting probability or expected stopping time.

Use stationary distributions when:
- the distribution becomes invariant under one step;
- the question asks long-run proportions or repeated-state probabilities.

# Graph 05 — Learning Paths and Reasoning

## Goal

Use the graph to build explainable learning sequences rather than merely nearest-neighbor recommendations.

## Inputs

- target problem/concept
- known/mastered concepts
- recent failure concepts/techniques
- target contest and horizon
- desired difficulty progression

## Path computation

For a target concept:

1. traverse prerequisite edges backward
2. subtract mastered concepts
3. topologically order remaining prerequisites
4. rank by dependency depth and frequency in target corpus
5. select representative problems for each step

The output should explain *why* each node is included.

## Edge weighting

Potential weights:

- curated prerequisite strength
- empirical co-occurrence
- learner transition success
- target-corpus frequency

Keep curated prerequisite truth separate from empirical recommendation weights.

## Graph algorithms

Useful algorithms after the corpus is stable:

- shortest path for explanation
- personalized PageRank for neighborhood relevance
- community detection for latent topic clusters
- node similarity for structural similarity

Graph algorithms produce candidate insight, not automatic canonical taxonomy edits.

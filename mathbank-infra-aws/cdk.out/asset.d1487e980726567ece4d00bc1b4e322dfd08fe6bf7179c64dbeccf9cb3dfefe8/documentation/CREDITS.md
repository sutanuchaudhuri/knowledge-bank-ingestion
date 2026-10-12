# Data sources and credits

MathBank's entire competition-math corpus comes from problems, solutions and official
archives published by the organizations below. **None of this content originates with
MathBank** — we are deeply grateful to every organizer and archive that makes decades of
competition mathematics freely browsable, and we encourage anyone who wants the
authoritative, original record to visit the source directly.

Counts below are **live-queried from `core.problem.source_url`**, not estimated. As of
this writing, 4,859 of 12,542 problems carry a recorded source URL; the rest are being
backfilled as ingestion continues (see
[documentation/requirements/reference/POSTGRES_DML.md](requirements/reference/POSTGRES_DML.md)
for the full ingestion/provenance pipeline).

## Competition archives and organizers

| Organization | Competitions archived here | Official site | Problems sourced |
|---|---|---|---|
| **Art of Problem Solving (AoPS)** | AMC 10, AMC 12, AIME (community-maintained wiki archive) | [artofproblemsolving.com](https://artofproblemsolving.com) | 3,665 |
| **Mathematical Association of America (MAA)** | Organizes and administers the AMC/AIME series that AoPS archives above | [maa.org](https://maa.org) | — (credited as the competitions' owner/administrator) |
| **Purple Comet Math Meet** | Purple Comet, High School and Middle School divisions | [purplecomet.org](https://purplecomet.org) | 1,050 |
| **Stanford University Mathematical Organization (SUMO)** | Stanford Math Tournament (SMT) | [sumo.stanford.edu/smt](https://sumo.stanford.edu/smt/), [stanfordmathtournament.com](https://www.stanfordmathtournament.com) | 62 |
| **Advantage Testing Foundation**, in partnership with Jane Street | Math Prize for Girls (MPG) — Main Test and Olympiad, hosted annually at MIT | [mathprize.atfoundation.org](https://mathprize.atfoundation.org) | 42 |
| **Caltech Math Meet (CMM) / Caltech-Harvey Mudd Math Competition (CHMMC)** | CMM (2024-2026), CHMMC (2010-2022) | [caltechmathmeet.org](https://www.caltechmathmeet.org) | 19 |
| **Harvard-MIT Mathematics Tournament (HMMT)** | HMMT November, February and Invitational | [hmmt.org](https://www.hmmt.org), archive mirror on [hmmt-archive.s3.amazonaws.com](https://hmmt-archive.s3.amazonaws.com) | 12 |
| **Princeton University Mathematics Competition (PUMaC)** | PUMaC, Division A/B, Team, Power, Finals | [pumac.princeton.edu](https://pumac.princeton.edu), community-maintained mirror archive | 9 |

Our internal ingestion catalog (`competition_catalog.csv` /
`source_ingestion_queue.csv` in
[mathbank-data-ingestion](../mathbank-data-ingestion/src/mathbank/data/maths_corpus/))
also tracks each source's canonical archive URL and explicit coverage gaps, so every
record can be traced back to exactly where it came from.

## How we use this content

- We store **canonical source URLs plus derived metadata** (concepts, skills,
  difficulty, taxonomy tags) — not bulk copies of full copyrighted problem or solution
  text. See `core.problem.source_url` and `core.paper`.
- Every problem record keeps a link back to its official archive, so attribution
  travels with the data wherever it is used — in search results, the tutor's answers, a
  micro-course, or a generated quiz.
- Worked solutions are either the source's own published solution (credited the same
  way) or produced/reviewed internally by MathBank and explicitly marked as such — never
  presented as an official solution when they are not.
- If you are a rights holder and have a concern about how your organization's content is
  represented here, please open an issue in this repository.

## See also

- [README.md](../README.md) — the engineering map.
- [documentation/BLOG_USE_CASES.md](BLOG_USE_CASES.md) — what the platform built from
  this corpus actually does, for a business audience.
- [documentation/requirements/17_DOMAIN_AND_TECHNICAL_GLOSSARY.md](requirements/17_DOMAIN_AND_TECHNICAL_GLOSSARY.md)
  — definitions for every competition/acronym referenced above.

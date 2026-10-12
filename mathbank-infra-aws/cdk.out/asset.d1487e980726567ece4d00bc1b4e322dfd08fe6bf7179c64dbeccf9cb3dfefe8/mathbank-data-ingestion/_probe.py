import sqlite3
conn = sqlite3.connect("data/mathbank.db")
conn.row_factory = sqlite3.Row

print("=== Unmapped questions with URLs ===")
cur = conn.execute(
    "SELECT exam_level, COUNT(*) as total,"
    " SUM(CASE WHEN problem_url != '' AND problem_url IS NOT NULL THEN 1 ELSE 0 END) as has_url"
    " FROM unmapped_questions GROUP BY exam_level ORDER BY total DESC"
)
for r in cur:
    print(f"  {r['exam_level']:15s}  total={r['total']}  has_url={r['has_url']}")

print("\n=== Fine concept gap by level ===")
cur = conn.execute(
    "SELECT exam_level, COUNT(*) as total,"
    " SUM(CASE WHEN direct_problem_url != '' AND direct_problem_url IS NOT NULL THEN 1 ELSE 0 END) as has_url"
    " FROM fine_concept_gaps GROUP BY exam_level ORDER BY total DESC LIMIT 10"
)
for r in cur:
    print(f"  {r['exam_level']:15s}  total={r['total']}  has_url={r['has_url']}")

print("\n=== Sample URLs from unmapped_questions ===")
cur = conn.execute(
    "SELECT question_id, exam_level, problem_url, suggested_domain"
    " FROM unmapped_questions WHERE problem_url != '' AND problem_url IS NOT NULL LIMIT 8"
)
for r in cur:
    print(f"  {r['question_id']:30s}  {r['exam_level']:8s}  {str(r['problem_url'])[:80]}")

print("\n=== Sample AoPS URLs from questions (unclassified) ===")
cur = conn.execute(
    "SELECT question_id, exam_level, aops_question_url, classification_status"
    " FROM questions"
    " WHERE classification_status NOT IN ('FINE_COMPLETE','SKIP_COMPLETE')"
    " AND aops_question_url != '' AND aops_question_url IS NOT NULL LIMIT 8"
)
for r in cur:
    print(f"  {r['question_id']:30s}  {r['classification_status']:15s}  {str(r['aops_question_url'])[:70]}")

print("\n=== Documents already stored ===")
cur = conn.execute("SELECT COUNT(*) as n FROM documents WHERE entity_type='question'")
print(f"  {cur.fetchone()['n']} question documents")

conn.close()

"""Vendored copies of small, pure-stdlib `mathbank-scripts/*.py` modules, for deployment
contexts where that sibling monorepo directory isn't present (Lambda, any installed —
non-editable — package; see requirements/63). Each caller tries the real monorepo-
relative sibling import first (unchanged local dev/test behavior), falling back to the
matching module here only on ImportError. Keep these in sync with their
`mathbank-scripts/` source manually — they are small and change rarely.
"""

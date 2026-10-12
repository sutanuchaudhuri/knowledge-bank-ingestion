# PostgreSQL `public` schema

**Role:** Default/extension namespace. No application relations observed; installed extension routines reside here.

**Access family:** Extension functions/operators are used indirectly by UUID, trigram and vector operations.

**Evidence:** live catalog metadata at 2026-10-08T01:57:54.421824+00:00; source `2bb4c2f682bf205556b8d6e895c868b10cdcc7a7`.
Metadata is observational, not proof of data correctness, endpoint authorization, or publication readiness.
Exact columns/constraints/indexes below are the observed selected-target catalog. No private row values are included.

[Schema index](README.md) | [DML/access boundaries](../POSTGRES_DML.md) | [REST contracts](../REST_API.md)

## Relations

No tables, views, sequences or foreign relations were observed in this namespace.

## Functions and routines

Extension routines are owned by their installed extension, not project migration code.
Volatility: i=immutable, s=stable, v=volatile. No routine was invoked by this inspection.

| Signature | Returns | Language / volatility | Security definer | Owner / source |
|---|---|---|---|---|
| `array_to_halfvec(double precision[], integer, boolean)` | `halfvec` | c / i | False | extension `vector` |
| `array_to_halfvec(integer[], integer, boolean)` | `halfvec` | c / i | False | extension `vector` |
| `array_to_halfvec(numeric[], integer, boolean)` | `halfvec` | c / i | False | extension `vector` |
| `array_to_halfvec(real[], integer, boolean)` | `halfvec` | c / i | False | extension `vector` |
| `array_to_sparsevec(double precision[], integer, boolean)` | `sparsevec` | c / i | False | extension `vector` |
| `array_to_sparsevec(integer[], integer, boolean)` | `sparsevec` | c / i | False | extension `vector` |
| `array_to_sparsevec(numeric[], integer, boolean)` | `sparsevec` | c / i | False | extension `vector` |
| `array_to_sparsevec(real[], integer, boolean)` | `sparsevec` | c / i | False | extension `vector` |
| `array_to_vector(double precision[], integer, boolean)` | `vector` | c / i | False | extension `vector` |
| `array_to_vector(integer[], integer, boolean)` | `vector` | c / i | False | extension `vector` |
| `array_to_vector(numeric[], integer, boolean)` | `vector` | c / i | False | extension `vector` |
| `array_to_vector(real[], integer, boolean)` | `vector` | c / i | False | extension `vector` |
| `avg(halfvec)` | `halfvec` | internal / i | False | extension `vector` |
| `avg(vector)` | `vector` | internal / i | False | extension `vector` |
| `binary_quantize(halfvec)` | `bit` | c / i | False | extension `vector` |
| `binary_quantize(vector)` | `bit` | c / i | False | extension `vector` |
| `cosine_distance(halfvec, halfvec)` | `double precision` | c / i | False | extension `vector` |
| `cosine_distance(sparsevec, sparsevec)` | `double precision` | c / i | False | extension `vector` |
| `cosine_distance(vector, vector)` | `double precision` | c / i | False | extension `vector` |
| `gin_extract_query_trgm(text, internal, smallint, internal, internal, internal, internal)` | `internal` | c / i | False | extension `pg_trgm` |
| `gin_extract_value_trgm(text, internal)` | `internal` | c / i | False | extension `pg_trgm` |
| `gin_trgm_consistent(internal, smallint, text, integer, internal, internal, internal, internal)` | `boolean` | c / i | False | extension `pg_trgm` |
| `gin_trgm_triconsistent(internal, smallint, text, integer, internal, internal, internal)` | `"char"` | c / i | False | extension `pg_trgm` |
| `gtrgm_compress(internal)` | `internal` | c / i | False | extension `pg_trgm` |
| `gtrgm_consistent(internal, text, smallint, oid, internal)` | `boolean` | c / i | False | extension `pg_trgm` |
| `gtrgm_decompress(internal)` | `internal` | c / i | False | extension `pg_trgm` |
| `gtrgm_distance(internal, text, smallint, oid, internal)` | `double precision` | c / i | False | extension `pg_trgm` |
| `gtrgm_in(cstring)` | `gtrgm` | c / i | False | extension `pg_trgm` |
| `gtrgm_options(internal)` | `void` | c / i | False | extension `pg_trgm` |
| `gtrgm_out(gtrgm)` | `cstring` | c / i | False | extension `pg_trgm` |
| `gtrgm_penalty(internal, internal, internal)` | `internal` | c / i | False | extension `pg_trgm` |
| `gtrgm_picksplit(internal, internal)` | `internal` | c / i | False | extension `pg_trgm` |
| `gtrgm_same(gtrgm, gtrgm, internal)` | `internal` | c / i | False | extension `pg_trgm` |
| `gtrgm_union(internal, internal)` | `gtrgm` | c / i | False | extension `pg_trgm` |
| `halfvec(halfvec, integer, boolean)` | `halfvec` | c / i | False | extension `vector` |
| `halfvec_accum(double precision[], halfvec)` | `double precision[]` | c / i | False | extension `vector` |
| `halfvec_add(halfvec, halfvec)` | `halfvec` | c / i | False | extension `vector` |
| `halfvec_avg(double precision[])` | `halfvec` | c / i | False | extension `vector` |
| `halfvec_cmp(halfvec, halfvec)` | `integer` | c / i | False | extension `vector` |
| `halfvec_combine(double precision[], double precision[])` | `double precision[]` | c / i | False | extension `vector` |
| `halfvec_concat(halfvec, halfvec)` | `halfvec` | c / i | False | extension `vector` |
| `halfvec_eq(halfvec, halfvec)` | `boolean` | c / i | False | extension `vector` |
| `halfvec_ge(halfvec, halfvec)` | `boolean` | c / i | False | extension `vector` |
| `halfvec_gt(halfvec, halfvec)` | `boolean` | c / i | False | extension `vector` |
| `halfvec_in(cstring, oid, integer)` | `halfvec` | c / i | False | extension `vector` |
| `halfvec_l2_squared_distance(halfvec, halfvec)` | `double precision` | c / i | False | extension `vector` |
| `halfvec_le(halfvec, halfvec)` | `boolean` | c / i | False | extension `vector` |
| `halfvec_lt(halfvec, halfvec)` | `boolean` | c / i | False | extension `vector` |
| `halfvec_mul(halfvec, halfvec)` | `halfvec` | c / i | False | extension `vector` |
| `halfvec_ne(halfvec, halfvec)` | `boolean` | c / i | False | extension `vector` |
| `halfvec_negative_inner_product(halfvec, halfvec)` | `double precision` | c / i | False | extension `vector` |
| `halfvec_out(halfvec)` | `cstring` | c / i | False | extension `vector` |
| `halfvec_recv(internal, oid, integer)` | `halfvec` | c / i | False | extension `vector` |
| `halfvec_send(halfvec)` | `bytea` | c / i | False | extension `vector` |
| `halfvec_spherical_distance(halfvec, halfvec)` | `double precision` | c / i | False | extension `vector` |
| `halfvec_sub(halfvec, halfvec)` | `halfvec` | c / i | False | extension `vector` |
| `halfvec_to_float4(halfvec, integer, boolean)` | `real[]` | c / i | False | extension `vector` |
| `halfvec_to_sparsevec(halfvec, integer, boolean)` | `sparsevec` | c / i | False | extension `vector` |
| `halfvec_to_vector(halfvec, integer, boolean)` | `vector` | c / i | False | extension `vector` |
| `halfvec_typmod_in(cstring[])` | `integer` | c / i | False | extension `vector` |
| `hamming_distance(bit, bit)` | `double precision` | c / i | False | extension `vector` |
| `hnsw_bit_support(internal)` | `internal` | c / v | False | extension `vector` |
| `hnsw_halfvec_support(internal)` | `internal` | c / v | False | extension `vector` |
| `hnsw_sparsevec_support(internal)` | `internal` | c / v | False | extension `vector` |
| `hnswhandler(internal)` | `index_am_handler` | c / v | False | extension `vector` |
| `inner_product(halfvec, halfvec)` | `double precision` | c / i | False | extension `vector` |
| `inner_product(sparsevec, sparsevec)` | `double precision` | c / i | False | extension `vector` |
| `inner_product(vector, vector)` | `double precision` | c / i | False | extension `vector` |
| `ivfflat_bit_support(internal)` | `internal` | c / v | False | extension `vector` |
| `ivfflat_halfvec_support(internal)` | `internal` | c / v | False | extension `vector` |
| `ivfflathandler(internal)` | `index_am_handler` | c / v | False | extension `vector` |
| `jaccard_distance(bit, bit)` | `double precision` | c / i | False | extension `vector` |
| `l1_distance(halfvec, halfvec)` | `double precision` | c / i | False | extension `vector` |
| `l1_distance(sparsevec, sparsevec)` | `double precision` | c / i | False | extension `vector` |
| `l1_distance(vector, vector)` | `double precision` | c / i | False | extension `vector` |
| `l2_distance(halfvec, halfvec)` | `double precision` | c / i | False | extension `vector` |
| `l2_distance(sparsevec, sparsevec)` | `double precision` | c / i | False | extension `vector` |
| `l2_distance(vector, vector)` | `double precision` | c / i | False | extension `vector` |
| `l2_norm(halfvec)` | `double precision` | c / i | False | extension `vector` |
| `l2_norm(sparsevec)` | `double precision` | c / i | False | extension `vector` |
| `l2_normalize(halfvec)` | `halfvec` | c / i | False | extension `vector` |
| `l2_normalize(sparsevec)` | `sparsevec` | c / i | False | extension `vector` |
| `l2_normalize(vector)` | `vector` | c / i | False | extension `vector` |
| `set_limit(real)` | `real` | c / v | False | extension `pg_trgm` |
| `show_limit(-)` | `real` | c / s | False | extension `pg_trgm` |
| `show_trgm(text)` | `text[]` | c / i | False | extension `pg_trgm` |
| `similarity(text, text)` | `real` | c / i | False | extension `pg_trgm` |
| `similarity_dist(text, text)` | `real` | c / i | False | extension `pg_trgm` |
| `similarity_op(text, text)` | `boolean` | c / s | False | extension `pg_trgm` |
| `sparsevec(sparsevec, integer, boolean)` | `sparsevec` | c / i | False | extension `vector` |
| `sparsevec_cmp(sparsevec, sparsevec)` | `integer` | c / i | False | extension `vector` |
| `sparsevec_eq(sparsevec, sparsevec)` | `boolean` | c / i | False | extension `vector` |
| `sparsevec_ge(sparsevec, sparsevec)` | `boolean` | c / i | False | extension `vector` |
| `sparsevec_gt(sparsevec, sparsevec)` | `boolean` | c / i | False | extension `vector` |
| `sparsevec_in(cstring, oid, integer)` | `sparsevec` | c / i | False | extension `vector` |
| `sparsevec_l2_squared_distance(sparsevec, sparsevec)` | `double precision` | c / i | False | extension `vector` |
| `sparsevec_le(sparsevec, sparsevec)` | `boolean` | c / i | False | extension `vector` |
| `sparsevec_lt(sparsevec, sparsevec)` | `boolean` | c / i | False | extension `vector` |
| `sparsevec_ne(sparsevec, sparsevec)` | `boolean` | c / i | False | extension `vector` |
| `sparsevec_negative_inner_product(sparsevec, sparsevec)` | `double precision` | c / i | False | extension `vector` |
| `sparsevec_out(sparsevec)` | `cstring` | c / i | False | extension `vector` |
| `sparsevec_recv(internal, oid, integer)` | `sparsevec` | c / i | False | extension `vector` |
| `sparsevec_send(sparsevec)` | `bytea` | c / i | False | extension `vector` |
| `sparsevec_to_halfvec(sparsevec, integer, boolean)` | `halfvec` | c / i | False | extension `vector` |
| `sparsevec_to_vector(sparsevec, integer, boolean)` | `vector` | c / i | False | extension `vector` |
| `sparsevec_typmod_in(cstring[])` | `integer` | c / i | False | extension `vector` |
| `strict_word_similarity(text, text)` | `real` | c / i | False | extension `pg_trgm` |
| `strict_word_similarity_commutator_op(text, text)` | `boolean` | c / s | False | extension `pg_trgm` |
| `strict_word_similarity_dist_commutator_op(text, text)` | `real` | c / i | False | extension `pg_trgm` |
| `strict_word_similarity_dist_op(text, text)` | `real` | c / i | False | extension `pg_trgm` |
| `strict_word_similarity_op(text, text)` | `boolean` | c / s | False | extension `pg_trgm` |
| `subvector(halfvec, integer, integer)` | `halfvec` | c / i | False | extension `vector` |
| `subvector(vector, integer, integer)` | `vector` | c / i | False | extension `vector` |
| `sum(halfvec)` | `halfvec` | internal / i | False | extension `vector` |
| `sum(vector)` | `vector` | internal / i | False | extension `vector` |
| `vector(vector, integer, boolean)` | `vector` | c / i | False | extension `vector` |
| `vector_accum(double precision[], vector)` | `double precision[]` | c / i | False | extension `vector` |
| `vector_add(vector, vector)` | `vector` | c / i | False | extension `vector` |
| `vector_avg(double precision[])` | `vector` | c / i | False | extension `vector` |
| `vector_cmp(vector, vector)` | `integer` | c / i | False | extension `vector` |
| `vector_combine(double precision[], double precision[])` | `double precision[]` | c / i | False | extension `vector` |
| `vector_concat(vector, vector)` | `vector` | c / i | False | extension `vector` |
| `vector_dims(halfvec)` | `integer` | c / i | False | extension `vector` |
| `vector_dims(vector)` | `integer` | c / i | False | extension `vector` |
| `vector_eq(vector, vector)` | `boolean` | c / i | False | extension `vector` |
| `vector_ge(vector, vector)` | `boolean` | c / i | False | extension `vector` |
| `vector_gt(vector, vector)` | `boolean` | c / i | False | extension `vector` |
| `vector_in(cstring, oid, integer)` | `vector` | c / i | False | extension `vector` |
| `vector_l2_squared_distance(vector, vector)` | `double precision` | c / i | False | extension `vector` |
| `vector_le(vector, vector)` | `boolean` | c / i | False | extension `vector` |
| `vector_lt(vector, vector)` | `boolean` | c / i | False | extension `vector` |
| `vector_mul(vector, vector)` | `vector` | c / i | False | extension `vector` |
| `vector_ne(vector, vector)` | `boolean` | c / i | False | extension `vector` |
| `vector_negative_inner_product(vector, vector)` | `double precision` | c / i | False | extension `vector` |
| `vector_norm(vector)` | `double precision` | c / i | False | extension `vector` |
| `vector_out(vector)` | `cstring` | c / i | False | extension `vector` |
| `vector_recv(internal, oid, integer)` | `vector` | c / i | False | extension `vector` |
| `vector_send(vector)` | `bytea` | c / i | False | extension `vector` |
| `vector_spherical_distance(vector, vector)` | `double precision` | c / i | False | extension `vector` |
| `vector_sub(vector, vector)` | `vector` | c / i | False | extension `vector` |
| `vector_to_float4(vector, integer, boolean)` | `real[]` | c / i | False | extension `vector` |
| `vector_to_halfvec(vector, integer, boolean)` | `halfvec` | c / i | False | extension `vector` |
| `vector_to_sparsevec(vector, integer, boolean)` | `sparsevec` | c / i | False | extension `vector` |
| `vector_typmod_in(cstring[])` | `integer` | c / i | False | extension `vector` |
| `word_similarity(text, text)` | `real` | c / i | False | extension `pg_trgm` |
| `word_similarity_commutator_op(text, text)` | `boolean` | c / s | False | extension `pg_trgm` |
| `word_similarity_dist_commutator_op(text, text)` | `real` | c / i | False | extension `pg_trgm` |
| `word_similarity_dist_op(text, text)` | `real` | c / i | False | extension `pg_trgm` |
| `word_similarity_op(text, text)` | `boolean` | c / s | False | extension `pg_trgm` |

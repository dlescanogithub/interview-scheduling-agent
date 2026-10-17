# ADR 0004: Local BM25

## Status

Accepted

## Context

The FAQ is 25 short synthetic documents. An embeddings API would add a network call, a price, and a dependency the lab does not need.

## Decision

Retrieval is Okapi BM25 in pure Python. Answers cite document ids. Below the score threshold the policy says it does not know and offers a person. One document is untrusted and tells the agent to ignore the rules; that text is data, and the injection ceiling stops an external effect the user did not ask for.

Hit@k is reported on 30 queries labelled while the corpus was written. The report says so. The bootstrap interval resamples those queries. It is not a comparison of models.

## Consequences

The hit rate on this set can be perfect and still say nothing about a new question. Embeddings and a vector index stay design-only. Replacing BM25 later does not remove the citation rule or the poison-document invariant.

#!/usr/bin/env python3
"""
Phase 13 BM25Okapi Implementation

Deterministic, standalone, zero-external-dependency BM25 Okapi implementation.
"""

import numpy as np


def tokenize_bm25(text: str) -> list:
    """Deterministic tokenization for BM25 matching."""
    cleaned = "".join(c.lower() if c.isalnum() else " " for c in text)
    return [t for t in cleaned.split() if len(t) > 1]


class BM25Okapi:
    """Self-contained Okapi BM25 implementation."""
    def __init__(self, corpus=None, k1=1.5, b=0.75):
        self.k1 = k1
        self.b = b
        self.corpus_size = len(corpus) if corpus else 0
        self.avgdl = sum(len(doc) for doc in corpus) / self.corpus_size if corpus and self.corpus_size else 0
        self.doc_freqs = []
        self.idf = {}
        self.doc_len = []

        if corpus:
            nd = {}
            for doc in corpus:
                self.doc_len.append(len(doc))
                frequencies = {}
                for word in doc:
                    frequencies[word] = frequencies.get(word, 0) + 1
                self.doc_freqs.append(frequencies)

                for word in frequencies:
                    nd[word] = nd.get(word, 0) + 1

            for word, freq in nd.items():
                idf = np.log((self.corpus_size - freq + 0.5) / (freq + 0.5) + 1)
                self.idf[word] = max(idf, 0.0)

    def get_scores(self, query):
        scores = np.zeros(self.corpus_size, dtype=np.float32)
        doc_len = np.array(self.doc_len, dtype=np.float32)
        for q in query:
            if q not in self.idf:
                continue
            q_idf = self.idf[q]
            for i, doc_dict in enumerate(self.doc_freqs):
                if q in doc_dict:
                    freq = doc_dict[q]
                    denom = freq + self.k1 * (1 - self.b + self.b * doc_len[i] / self.avgdl)
                    scores[i] += q_idf * (freq * (self.k1 + 1)) / denom
        return scores

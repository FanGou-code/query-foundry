#!/usr/bin/env python3
"""Phase 0: mine the test query text layer into a style spec draft.

Reads ONLY the `query` text field of the official queries.json (no GT fields,
no image access). Output: spec/style_spec.json + spec/vocab_freq.json.

Everything mechanical and reproducible: same input -> same output.
"""

import json
import hashlib
import re
from collections import Counter
from pathlib import Path
from statistics import mean, median

MAIN = Path("/home/fang0/dev/projects/aicomp-multimodal-grounding")
QUERIES = MAIN / "data/Test/queries/queries.json"
OUT_SPEC = Path(__file__).resolve().parent.parent / "spec/style_spec.json"
OUT_VOCAB = Path(__file__).resolve().parent.parent / "spec/vocab_freq.json"

# token classes for skeleton collapse
ORD = {"first", "second", "third", "fourth", "fifth", "sixth", "seventh",
       "eighth", "ninth", "tenth", "last"}
SUP = {"leftmost", "rightmost", "topmost", "bottommost", "nearest", "closest",
       "farthest", "uppermost", "lowermost", "frontmost"}
DET = {"the", "a", "an", "his", "her", "its", "their"}
PREP = {"of", "in", "on", "at", "to", "from", "by", "with", "near", "beside",
        "behind", "next", "along", "across", "between", "under", "above",
        "over", "against", "around", "inside", "outside", "onto", "into"}
DIR = {"left", "right", "front", "back", "rear", "top", "bottom", "middle",
       "center", "centre", "side", "end", "edge", "corner", "foreground",
       "background"}
FAR = {"far"}
ROW = {"row", "rows", "line", "lines", "column", "columns", "queue"}

RE_ORD = re.compile(r"\b(first|second|third|fourth|fifth|sixth|seventh|eighth|last)\b", re.I)
RE_SUP = re.compile(r"\b(leftmost|rightmost|topmost|bottommost|nearest|closest|farthest|uppermost|lowermost|frontmost)\b", re.I)
RE_DIST = re.compile(r"\b(near|nearer|nearby|far|farther|farthest|close|closer|distance|away)\b", re.I)
RE_SPAT = re.compile(r"\b(left|right|front|back|rear|top|bottom|middle|center|centre|side|row|rows|behind|beside|between|above|below|under|foreground|background|edge|corner)\b", re.I)


def tokenize(text):
    return re.findall(r"[a-z0-9']+", text.lower())


def token_class(tok):
    if tok in ORD:
        return "<ORD>"
    if tok in SUP:
        return "<SUP>"
    if tok in DET:
        return tok
    if tok in PREP:
        return tok
    if tok in DIR:
        return tok
    if tok in FAR:
        return "<FAR>"
    if tok in ROW:
        return tok
    if tok.isdigit():
        return "<NUM>"
    return "<X>"


def main():
    raw = QUERIES.read_bytes()
    sha = hashlib.sha256(raw).hexdigest()
    data = json.loads(raw)
    texts = [v["query"] for v in data.values()]
    n = len(texts)

    # ---- corpus stats ----
    counts = Counter(texts)
    repeated = {q: c for q, c in counts.items() if c > 1}
    lower_counts = Counter(t.lower() for t in texts)
    wc = [len(t.split()) for t in texts]
    wc_sorted = sorted(wc)

    # ---- vocab ----
    vocab = Counter(tok for t in texts for tok in tokenize(t))
    vocab_ge5 = {w: c for w, c in vocab.items() if c >= 5}

    # ---- skeleton table ----
    skeletons = Counter()
    sk_examples = {}
    for t in texts:
        toks = tokenize(t)
        sk = " ".join(token_class(x) for x in toks)
        skeletons[sk] += 1
        sk_examples.setdefault(sk, t)
    top_skeletons = skeletons.most_common(60)

    # ---- frames: frequent raw n-grams (glue patterns) ----
    def ngrams(k):
        c = Counter()
        for t in texts:
            toks = tokenize(t)
            for i in range(len(toks) - k + 1):
                c[" ".join(toks[i:i + k])] += 1
        return c

    bi, tri, quad = ngrams(2), ngrams(3), ngrams(4)

    # ---- domain phrase census ----
    phrases = [
        "from left to right", "from right to left",
        "from the left", "from the right",
        "on the left", "on the right",
        "to the left", "to the right",
        "at the left", "at the right",
        "in the left", "in the right",
        "in the front row", "in the back row", "front row", "back row",
        "closest to the camera", "farthest from the camera",
        "nearest to the camera", "in the foreground", "in the background",
        "the far left", "the far right", "on the far left", "on the far right",
        "far left", "far right",
        "in the middle of", "in front of the", "of the image",
        "to the camera", "from the camera", "the camera",
        "wearing a", "holding a", "in front of", "next to",
    ]
    joined = {" ".join(tokenize(t)) for t in texts}
    phrase_counts = {}
    for p in phrases:
        # count over tokens per query (a phrase may appear twice in one query: rare)
        pc = sum(len(re.findall(r"\b" + re.escape(p) + r"\b", " ".join(tokenize(t)))) for t in texts)
        phrase_counts[p] = pc

    # ---- MT quirk detectors ----
    quirks = []

    def add_quirk(name, hits):
        if hits:
            quirks.append({"pattern": name, "count": len(hits),
                           "examples": [h[1] for h in hits[:5]]})

    dup_adj = [(i, t) for i, t in enumerate(texts)
               if any(a == b for a, b in zip(tokenize(t), tokenize(t)[1:]))]
    add_quirk("adjacent duplicate token (the the / of of ...)", dup_adj)

    a_vowel = [(i, t) for i, t in enumerate(texts)
               if re.search(r"\ba\s+[aeiou]", t.lower())]
    an_cons = [(i, t) for i, t in enumerate(texts)
               if re.search(r"\ban\s+[bcdfgjklmnpqrstvwxyz]", t.lower())]
    add_quirk("'a' + vowel-initial word", a_vowel)
    add_quirk("'an' + consonant-initial word", an_cons)

    dbl_space = [(i, t) for i, t in enumerate(texts) if "  " in t]
    add_quirk("double space", dbl_space)

    non_ascii = [(i, t) for i, t in enumerate(texts) if not t.isascii()]
    add_quirk("non-ascii characters", non_ascii)

    suspicious_plurals = ["persons", "peoples", "mans", "womans", "childrens",
                          "furnitures", "equipments", "clothings", "staffs",
                          "closes", "最"]
    for w in suspicious_plurals:
        hits = [(i, t) for i, t in enumerate(texts)
                if re.search(r"\b" + re.escape(w) + r"\b", t.lower())]
        add_quirk(f"suspicious token '{w}'", hits)

    # ---- draft style buckets (text-layer heuristic, priority: ordinal > distance > spatial > attr/action) ----
    buckets = Counter()
    for t in texts:
        if RE_ORD.search(t) or RE_SUP.search(t):
            buckets["ordinal"] += 1
        elif RE_DIST.search(t):
            buckets["distance"] += 1
        elif RE_SPAT.search(t):
            buckets["spatial"] += 1
        else:
            buckets["attribute_action"] += 1

    # lexical probes for dialect grammar (legit features vs errors, both counted)
    probes = {
        "closest_to": r"\bclosest to\b",
        "nearest_to": r"\bnearest to\b",
        "closest_attributive": r"\bclosest (?!to\b)[a-z]",
        "nearest_attributive": r"\bnearest (?!to\b)[a-z]",
        "immediate_nearest": r"\bimmediate(ly)? nearest\b",
        "next_to_the": r"\bnext to the\b",
        "in_front_of_the": r"\bin front of the\b",
        "of_the_image": r"\bof the (image|photo|picture)\b",
    }
    probe_counts = {k: sum(1 for t in texts if re.search(p, t.lower()))
                    for k, p in probes.items()}

    spec = {
        "status": "draft-awaiting-admin-review",
        "version": "phase0-draft",
        "source": {
            "file": "aicomp-multimodal-grounding/data/Test/queries/queries.json",
            "sha256": sha,
            "fields_read": ["query"],
        },
        "corpus_stats": {
            "total": n,
            "unique_verbatim": len(counts),
            "verbatim_repeat_rate": round(1 - len(counts) / n, 4),
            "unique_lower": len(lower_counts),
            "lower_repeat_rate": round(1 - len(lower_counts) / n, 4),
            "repeat_groups_ge2": len(repeated),
            "word_count": {
                "mean": round(mean(wc), 2),
                "median": median(wc),
                "p25": wc_sorted[n // 4],
                "p75": wc_sorted[3 * n // 4],
                "min": min(wc),
                "max": max(wc),
            },
            "vocab_size": len(vocab),
            "vocab_size_freq_ge5": len(vocab_ge5),
        },
        "style_buckets_draft": {
            "rule": "priority ordinal > distance > spatial > attribute_action; regex-defined in script",
            "shares": {k: f"{v} ({v / n * 1000:.0f} per-mille)" for k, v in buckets.most_common()},
        },
        "skeletons_top60": [
            {"skeleton": s, "count": c,
             "share_per_mille": round(c / n * 1000),
             "example": sk_examples[s]}
            for s, c in top_skeletons
        ],
        "skeleton_diversity": {
            "unique_skeletons": len(skeletons),
            "top60_coverage": round(sum(c for _, c in top_skeletons) / n, 3),
        },
        "frames_top": {
            "bigrams": [[g, c] for g, c in bi.most_common(25)],
            "trigrams": [[g, c] for g, c in tri.most_common(25)],
            "quadgrams": [[g, c] for g, c in quad.most_common(15)],
        },
        "domain_phrases": phrase_counts,
        "lexical_probes": probe_counts,
        "quirks_threshold20": quirks,
        "quirk_threshold_note": "MT 怪癖只学高频：候选列表按机械检测全量给出，≥20 次才进语法；本表含全部命中，管理员审阅定取舍",
    }

    OUT_SPEC.parent.mkdir(parents=True, exist_ok=True)
    OUT_SPEC.write_text(json.dumps(spec, ensure_ascii=False, indent=2) + "\n")
    OUT_VOCAB.write_text(json.dumps(vocab, ensure_ascii=False, indent=2, sort_keys=True) + "\n")

    # ---- stdout summary ----
    print(f"source sha256={sha[:16]}…  total={n}")
    cs = spec["corpus_stats"]
    print(f"verbatim repeat rate={cs['verbatim_repeat_rate']}  "
          f"lower repeat rate={cs['lower_repeat_rate']}  repeat_groups={cs['repeat_groups_ge2']}")
    print(f"word count mean={cs['word_count']['mean']} median={cs['word_count']['median']} "
          f"range=[{cs['word_count']['min']},{cs['word_count']['max']}]")
    print(f"vocab={cs['vocab_size']}  vocab(freq>=5)={cs['vocab_size_freq_ge5']}")
    print("\nbuckets (draft):")
    for k, v in buckets.most_common():
        print(f"  {k:<18} {v:>5}  {v / n * 1000:>4} per-mille")
    print(f"\nunique skeletons={len(skeletons)}  top60 coverage={spec['skeleton_diversity']['top60_coverage']}")
    print("\ntop 15 skeletons:")
    for s, c in skeletons.most_common(15):
        print(f"  {c:>5}  {s}")
    print("\ndomain phrases:")
    for p, c in sorted(phrase_counts.items(), key=lambda kv: -kv[1]):
        if c:
            print(f"  {c:>5}  {p}")
    print("\nquirks:")
    for q in quirks:
        print(f"  {q['count']:>4}  {q['pattern']}  e.g. {q['examples'][0][:70] if q['examples'] else ''}")
    print(f"\nwrote {OUT_SPEC}")
    print(f"wrote {OUT_VOCAB}")


if __name__ == "__main__":
    main()

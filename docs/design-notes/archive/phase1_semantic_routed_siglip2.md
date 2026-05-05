# Phase1 Semantic Routing (SigLIP2)

## Why

Phase1 originally used a global real-anchor semantic score:

`s_semantic_anchor(x) = median_{r in X_real} Sim(E(x), E(r))`

This is useful for distribution guardrails, but it does not distinguish:

- real-guided synthetic samples (anchor image + prompt/control)
- prompt-only synthetic samples

For current generation workflows, these two sample types should be validated differently.

## What

Introduce a routed phase1 score `s_phase1_semantic`:

- For real-guided synthetic rows:
  - use paired image-image score `s_semantic_pair`
  - `s_semantic_pair(x) = Sim(E(x), E(anchor(x)))`
  - anchor is resolved from row metadata, default `guide_image_id`
- For prompt-only synthetic rows:
  - use prompt-image score `s_prompt`
  - computed by SigLIP2 `logits_per_image -> sigmoid` (`clip.prompt_score_mode: siglip_sigmoid`)
- Fallback:
  - if routed source is unavailable, use `s_semantic_anchor`

All scores are normalized to `[0, 1]` for policy gating/fusion.

## Routing Rules

Routing is enabled by `filter.phase1_semantic.enabled: true`.

- Guided sample detection (`guided_marker_fields`):
  - `guide_image_id`
  - `anchor_real_image_path`
  - `effective_anchor_input`
  - `effective_anchor_inputs`
- Prompt override field:
  - `prompt_field` (default `effective_prompt_text`)

## Config Example

```yaml
filter:
  clip:
    model_id: google/siglip2-base-patch16-224
    prompt_score_mode: siglip_sigmoid

  phase1_semantic:
    enabled: true
    guided_source: semantic_pair
    prompt_only_source: prompt_score
    fallback_source: semantic_anchor
    prompt_field: effective_prompt_text
    guided_marker_fields:
      - guide_image_id
      - anchor_real_image_path
      - effective_anchor_input
      - effective_anchor_inputs
    anchor_sid_fields:
      - guide_image_id

  policy:
    gates:
      - metric: s_phase1_semantic
        op: ">="
        threshold_from: q05_real
```

## Output Fields

`filter/filter_scores.jsonl` now includes:

- `s_semantic_pair`
- `s_phase1_semantic`
- `s_phase1_semantic_source` (`semantic_pair|prompt_score|semantic_anchor`)

`filter/report.json` now includes:

- `phase1_semantic` routing state
- paired-score hit/miss stats

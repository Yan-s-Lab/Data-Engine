# 1) Summary
- Change phase1 prompt scoring to support weighted multi-group text comparison from `filter.clip.compare-texts`.
- Needed because prompt-only filtering should use configured multi-aspect texts (`human` / `body_structure` / `negative`) instead of a single prompt string.

# 2) Scope
## In scope
- Phase1 component logic in `filter/pipeline_engine/phase1_dual_signal.py`.
- Prompt score core logic in `filter/filter_stages/clip_prompt_score.py`.
- Config contract extension for compare-text weighting and reduction.
- Unit tests for routing-to-compare-text path and weighted aggregation formula.
- Kernel/design docs update for new config and formula.

## Out of scope
- Changes to phase2/phase3.
- Reworking decision thresholds in `phase1_dual_signal`.
- Changing generation-side prompt templating.

# 3) Layer Placement (Orchestration / Components / Core)
- Changed layers:
  - Components: `phase1_dual_signal` chooses prompt-scoring source based on config.
  - Core-like stage utilities: `clip_prompt_score` adds weighted compare-text scoring primitive.
- Why:
  - Selection logic belongs to phase component.
  - Numeric scoring formula belongs to reusable stage utility.

# 4) Interfaces (Signatures)
## New/changed public interfaces
- `filter.filter_stages.clip_prompt_score.compute_compare_texts_prompt_scores(...)`
  - Inputs:
    - rows, runtime
    - `compare_texts: Dict[str, List[str]]`
    - `group_weights: Dict[str, float]`
    - `group_reduce: str`
    - `negative_scale: float`
  - Outputs:
    - `Dict[sample_id, score]` in `[0,1]`
    - runtime stats dict for report
  - Error handling:
    - Missing image / empty group texts -> per-sample score fallback `0.0`.
- `filter.filter_stages.clip_prompt_score.aggregate_compare_texts_group_scores(...)`
  - Pure function for weighted aggregation from group scores.

## Backward compatibility
- Existing single-prompt path remains default when `compare-texts` is absent/empty.
- Existing `clip.prompt_text` and `phase1_semantic.prompt_field` behavior remains unchanged for fallback path.

# 5) Data Contracts (Explicit Schemas)
## Step Inputs
- Existing dict rows unchanged (`sample_id`, `image_path`, `source`, optional prompt fields).
- New config-driven contract:
  - `filter.clip.compare-texts`: map of `group_name -> [text, ...]`
  - `filter.clip.compare-texts-weights`: optional map of `group_name -> weight`
  - `filter.clip.compare-texts-group-reduce`: `max|mean|p75` (default `max`)
  - `filter.clip.compare-texts-negative-scale`: float (default `1.0`)

## Step Outputs
- Existing phase1 score row fields unchanged (`s_prompt`, `s_anchor`, `s_final`, etc.).
- Report adds compare-text runtime state (enabled, groups, weights, reduce mode).

# 6) Config Contract
- Config keys added/used:
  - `filter.clip.compare-texts` (existing in task config, now consumed)
  - `filter.clip.compare-texts-weights` (new optional)
  - `filter.clip.compare-texts-group-reduce` (new optional)
  - `filter.clip.compare-texts-negative-scale` (new optional)
- Defaults:
  - Missing weights -> `1.0` per group.
  - Missing reduce -> `max`.
  - Missing negative-scale -> `1.0`.
  - Group names starting with `neg` are treated as negative groups.
  - Accept legacy typo group `body_strucure` as alias of `body_structure`.
- Validation rules:
  - Non-positive weights are ignored and replaced by default `1.0`.
  - Empty text lists are ignored.
- Example:
```yaml
filter:
  clip:
    compare-texts:
      human: ["human", "person", "human body"]
      body_structure: ["visible deltoid muscle", "visible elbow", "normal neck anatomy"]
      negative: ["not human", "non-human anatomy", "failure artifact"]
    compare-texts-weights:
      human: 0.4
      body_structure: 0.6
      negative: 1.0
    compare-texts-group-reduce: max
    compare-texts-negative-scale: 1.0
```

# 7) Registry / Dispatch Plan (If applicable)
- No new phase registry entries.
- `phase1_dual_signal` keeps same dispatch id and selects compare-text scorer internally when configured.

# 8) Dependency Direction Check
Confirm imports follow Orchestration → Components → Core
- Orchestration imports:
  - unchanged (`run_filter.py` -> pipeline_engine)
- Components imports:
  - `phase1_dual_signal.py` imports stage utilities from `filter.filter_stages`
- Core imports:
  - `clip_prompt_score.py` imports only stage runtime helpers (`clip_embed_cache`)

# 9) Test Plan (Minimum)
- Unit tests to add/modify:
  - compare-text weighted aggregation function behavior.
  - phase1 uses compare-text scorer when `compare-texts` exists.
- Integration tests:
  - reuse existing phase1 semantic tests; no new heavy integration required.
- Run:
```bash
python -m unittest discover -s test -p 'test_filter_phase1_semantic.py' -v
```

# 10) Risks & Mitigations
- Risk: weights misconfigured causing unexpected suppression.
  - Mitigation: sane defaults + report fields for active groups/weights.
- Risk: typo in config group names.
  - Mitigation: alias support for `body_strucure`.
- Risk: behavior drift from old single-prompt score.
  - Mitigation: strict fallback to legacy path when compare-texts not configured.

# 11) Implementation Checklist
- [x] Design note approved/ready
- [x] Code changes implemented
- [x] Tests added/updated
- [x] Docs updated
- [ ] Git commit message:
- [ ] Pushed to remote

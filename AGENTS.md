# Real-Anchored Synthetic Data Engine — CLI-First Research System

---

## 0. Agent Role

You are an engineering and research agent working on a **Real-Anchored Synthetic Data Engine**.

This system is a **closed-loop research platform** for iterative data construction, filtering, model training, evaluation, and feedback-driven refinement.

The system may be rewritten at any time.
It prioritizes:

* Research clarity
* Experimental agility
* Iteration transparency
* Distribution control

It does **not** prioritize production scalability.

---

# 1. Project Identity (Non-Negotiable)

## 1.1 What This Project Is

This project is a **closed-loop Data Iteration Engine**.

It is not:

* A dataset
* A model
* A synthetic generator
* A training script collection

It is a **data evolution system**.

Core loop components:

1. Real data ingestion
2. Guided synthetic data generation
3. Multi-stage filtering & labeling
4. Supervised / semi-supervised training
5. Evaluation & slice-based failure analysis
6. Feedback-driven generation/filter policy update
7. Human-in-the-Loop correction

The identity of the project is the **iteration mechanism**.

---

# 2. Real-Anchored Synthetic Paradigm

## 2.1 Core Principle

Real data defines the **distribution anchor**.

Synthetic data is a **controlled expansion operator**.

Synthetic data must always:

* Be conditioned on real data statistics
* Be guided by model failure slices
* Be validated against real validation sets
* Be filtered before mixing

Training rule:

```
Train(real + filtered_synthetic)
```

Synthetic data never replaces real data.

It expands and probes distribution coverage.

---

## 2.2 Synthetic Is Policy-Driven

Synthetic generation must be governed by:

* Failure slice targeting
* Coverage balancing objectives
* Controlled perturbation experiments
* Distribution gap hypotheses

Synthetic generation without a policy is invalid.

---

# 3. System Architecture Philosophy

## 3.1 CLI-First, Pipeline-First

The atomic unit of execution is a CLI module:

```bash
python module.py --config config.yaml
```

Pipelines are composed by chaining CLIs.

No subsystem should require:

* Long-running services
* Tight framework coupling
* Hidden background orchestration

UI and services may wrap CLI logic, but CLI remains canonical.

---

## 3.2 Canonical Logical Subsystems

Logical modules:

* `ingest/` — normalize and register real/synthetic data
* `generate/` — synthetic generation (policy-driven)
* `embed/` — embedding computation
* `filter/` — ASF / PCS / CLIP / statistical filters
* `label/` — pseudo-labeling + HITL integration
* `train/` — supervised / semi-supervised training
* `eval/` — metrics + slice-based analysis
* `analysis/` — failure pattern extraction

These are conceptual boundaries.
Implementation may evolve.

---

# 4. Filtering as First-Class Component

Filters are decision modules.

They:

* Accept model feedback
* Adjust thresholds
* Control data admission
* Regulate pseudo-label acceptance
* Enforce distribution constraints

Filters are:

* Iterative
* Configurable
* Potentially stateful

Filtering logic must be explicit and reproducible.

Filtering is not preprocessing.
It is a control layer.

---

# 5. Closed-Loop Feedback (Hard Constraint)

The system must implement:

```
Real Data
   ↓
Guided Synthetic Generation
   ↓
Filtering & Labeling
   ↓
Train (real + synthetic)
   ↓
Evaluate
   ↓
Failure & Slice Analysis
   ↓
Update Generation + Filter Policies
```

Feedback sources:

* mAP / IoU / calibration metrics
* Slice failures (pose / BMI / lighting / viewpoint)
* Pseudo-label uncertainty
* HITL corrections
* Distribution misalignment statistics

Every stage must allow iteration.

No stage is terminal.

---

# 6. Human-in-the-Loop (Mandatory)

The system must support:

* Pushing uncertain samples for annotation
* Pulling corrected annotations
* Tracking annotation provenance
* Reintegration into training
* Tracking correction impact

External annotation tools (e.g., Label Studio) may be used via CLI connectors.

Full automation is not required.

Human correction is part of the loop.

---

# 7. Experimental Discipline (New Section)

This is a research system.

Therefore:

* Every experiment must be reproducible
* Every dataset version must be traceable
* Every synthetic policy must be logged
* Every filter configuration must be versioned
* Every training run must record its data mixture

No silent data mutation is allowed.

---

# 8. Git and Change Management (Critical Addition)

## 8.1 Mandatory Git Discipline

When introducing:

* Major architectural changes
* Functional additions
* Filtering logic modifications
* Data schema changes
* CLI interface changes

You must:

1. Stage only relevant files
2. Write meaningful commit messages
3. Reference design intent

Example:

```bash
git add ingest/ filter/ docs/design/filter_update.md
git commit -m "Refactor filter module: introduce ASF threshold policy abstraction"
```

---

## 8.2 Commit Message Structure

Use structured messages:

```
[Module] Short summary

Why:
What problem this change solves

What:
Key changes introduced

Impact:
Expected effect on iteration loop
```

---

## 8.3 Large Changes Require Documentation

If modification affects:

* Closed-loop logic
* Data mixing policy
* Synthetic policy
* Filter mechanism
* Training pipeline structure

You must:

* Update `docs/design/*.md`
* Update `docs/state/*.md` if implementation changes
* Then commit

Design must not drift silently.

---

# 9. Source of Truth Hierarchy

When reasoning:

1. AGENTS.md — conceptual constraints
2. docs/state/*.md — implemented reality
3. docs/design/*.md — architectural intent
4. Code — implementation snapshot

Never assume features exist unless verified.

---

# 10. Final Principle

> This system optimizes for understanding and controlling data evolution.

We refine thinking before optimizing infrastructure.

# 11. Execution Environment (Hard Constraint)

The conda environment is part of the experimental state.

All CLI modules, scripts, and agent-invoked commands in this repository
must be executed inside the following conda environment:

   "open_data_engine"

Running any command outside this environment is considered an invalid
experiment and may lead to irreproducible or undefined behavior.

Agents must not:
- execute CLI modules from the `base` environment
- execute CLI modules from unrelated conda environments
- assume environment correctness without verification

If environment verification logic exists in code (e.g. CLI preflight checks),
agents must not bypass or remove it.

Environment correctness must be treated as a first-class precondition,
not a convenience.
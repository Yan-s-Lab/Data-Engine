**Real-Anchored Synthetic Data Engine — CLI-First Research System**

---

## 0. Agent Role

You are an engineering and research agent working on a **Real-Anchored Synthetic Data Engine**.

This system is designed for iterative data construction, filtering, training, and feedback-driven refinement.

The system may be rewritten from scratch.
It is optimized for research clarity and experimental agility, not industrial deployment.

---

## 1. Project Identity (Non-Negotiable)

### 1.1 What This Project Is

This project is a **closed-loop Data Engine** that includes:

1. Real data ingestion
2. Guided synthetic data generation
3. Multi-stage filtering and labeling
4. Supervised and semi-supervised training
5. Evaluation and slice-based failure analysis
6. Feedback-driven policy refinement
7. Human-in-the-Loop (HITL) correction

The entity of the project is the **data iteration system**, not a single dataset or model.

---

## 2. Real-Anchored Synthetic Paradigm

### 2.1 Core Principle

Real data serves as the **distribution anchor**.
Synthetic data serves as a **guided expansion mechanism**.

Synthetic data must always be:

* conditioned on real data statistics
* guided by model failure patterns
* evaluated against real validation sets

Training always mixes:

```
Train(real + synthetic)
```

Synthetic never replaces real data.

---

### 2.2 Role of Synthetic Data

Synthetic data is used for:

* Cold-start expansion when real data is scarce
* Coverage balancing (pose, BMI, lighting, viewpoint, etc.)
* Failure probing and stress testing
* Controlled experiments on distribution shifts

Synthetic generation is **policy-driven**, not arbitrary.

---

## 3. System Architecture Philosophy

### 3.1 CLI-First, Pipeline-First

The minimal unit of the system is a CLI module.

Every subsystem must be runnable via:

```bash
python module.py --config config.yaml
```

Pipelines are composed by chaining CLIs, not by tightly coupled services.

Services or UI tools may exist, but they must wrap CLI logic.

---

### 3.2 Canonical Subsystems

The system conceptually contains:

* `ingest/` – normalize and register real/synthetic data
* `embed/` – compute embeddings for filtering
* `filter/` – apply ASF, PCS, and other filters
* `label/` – pseudo-labeling and HITL integration
* `train/` – supervised/semi-supervised model training
* `eval/` – metrics and slice-based failure analysis

These are logical modules.
Actual implementation may evolve.

---

## 4. Filtering as First-Class Component

Filters are not preprocessing utilities.

Filters are decision modules that:

* Accept model/eval feedback
* Update thresholds and policies
* Control data selection and mixing
* Regulate pseudo-label acceptance

Examples include:

* ASF (Annotation Similarity Filter)
* PCS (Perturbation CLIP Similarity)
* CLIP-based semantic consistency checks
* Statistical distribution alignment

Filters are iterative and stateful.

---

## 5. Closed-Loop Feedback (Hard Constraint)

The system must implement the loop:

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

Feedback sources include:

* evaluation metrics (mAP, IoU, calibration)
* slice failures (pose, BMI, lighting, etc.)
* pseudo-label uncertainty
* HITL corrections

No stage is terminal.
Every stage must allow iteration.

---

## 6. Human-in-the-Loop (HITL)

HITL is a mandatory component.

The system must support:

* pushing uncertain samples for annotation
* pulling corrected labels
* recording provenance
* integrating corrections into future training

External tools (e.g., Label Studio) may be used via minimal CLI integration.

Full automation is not required.

---

## 7. Implementation Constraints

When writing or rewriting code:

1. Prefer explicit, modular CLI scripts.
2. Avoid over-engineered service frameworks.
3. Keep artifacts transparent and reproducible.
4. Separate:

   * ingestion
   * filtering
   * labeling
   * training
   * evaluation
5. Do not assume any previous repository structure is authoritative.

---

## 8. Source of Truth Hierarchy

When reasoning:

1. `Agent.md` defines conceptual constraints.
2. `docs/state/*.md` defines current implementation reality.
3. `docs/design/*.md` defines aspirational architecture.
4. Code may lag behind design.

Never assume unimplemented features exist.

---

## 9. Final Principle

> This project optimizes for understanding and controlling data iteration,
> not for shipping infrastructure.

Agents should help the system converge intellectually before optimizing technically.

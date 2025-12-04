# Architecture Overview

OpenDataEngine is designed as a **Modular, Plugin-based, Event-driven Data Engine**.

- **Modular:** each responsibility (collection, mining, filtering, labeling, training, evaluation) is an independent service.
- **Plugin-based:** each service can host multiple algorithms (e.g. different filters or trainers) behind a common interface.
- **Event-driven:** heavy tasks are triggered via a queue (e.g. Redis + RQ/Celery), keeping services loosely coupled.

---

## 1. Layered Architecture

From top to bottom, OpenDataEngine consists of **six layers**:

### 1.1 Data Collection Layer

- **Services**
  - `collection-gateway`
  - `collectors/` (manual-uploader, spider-collector, robot-collector, video-mining-collector, …)
- **Responsibility**
  - Bring data from multiple sources into the system:
    - Manual upload
    - Web spiders
    - Robotics data (e.g. ROS topics)
    - Video mining
    - Future AR / logs / other sensors
  - Normalize everything into a unified `raw_samples` schema

Data comes from a ==family of collection== methods: manual upload, spiders, robotics log, video mining, **synthetic generators (e.g. T2I models)**, **internal mining services** (e.g. cold-start sampling). All of them eventually push data into collection-gateway as raw_samples.
> Informal analogy:  
> `collection-gateway` is the **warehouse front desk** (收件处),  
> `collectors` are the **delivery agents** (快递小哥) that push data into it.

---

### 1.2 Mine & Preprocess Layer

- **Service**
  - `mine-service`
- **Responsibility**
  - Process `raw_samples` into `candidate_samples`:
    - Deduplication
    - Basic quality filtering (broken file, too small, etc.)
    - Temporal / topological segmentation (e.g. split robot trajectories, video episodes)
    - Coarse sampling (e.g. from 1M raw → 10k candidates)

==While mine-service is logically part of the “collection family”, it runs inside the warehouse: it operates on existing raw_samples (e.g. cold-start selection of 500 seeds, dedup, coarse sampling) and writes back curated candidate_samples.==

This is the **first “data cleaning + selection” pass** before applying more advanced filters.

---

### 1.3 Filter & Labeling Layer

- **Services**
  - `filter-service`
  - `label-sync-service` (integration with external labeling platforms)
- **Responsibility**
  - Apply advanced, pluggable filters:
    - CLIP similarity filters
    - ASF / PCS / perturbation-based filters
  - Manage labeling workflow:
    - Create / sync projects with Label Studio / CVAT
    - Pull human annotations and pseudo-labels
  - Produce **versioned datasets**:
    - `dataset_versions` that are ready for training

---

### 1.4 Training Layer

- **Service**
  - `training-service`
- **Responsibility**
  - Train models from a given dataset version:
    - Start from segmentation CV tasks (e.g. YOLO / SAM / other frameworks)
    - Extendable to other modalities and tasks
  - Register trained models:
    - Store artefacts in object storage
    - Record config and metrics summary in `models` table

---

### 1.5 Evaluation & HITL Layer

- **Service**
  - `evaluation-service`
- **Responsibility**
  - Run evaluation on chosen datasets:
    - Task-specific metrics (mIoU, mAP, etc.)
    - Per-sample error analysis
  - Mark `need_review` samples for **Human-in-the-Loop (HITL)** review:
    - These samples will be sent back to the labeling pipeline
    - Humans can confirm/correct model predictions → new labels → next training round

---

### 1.6 Orchestration & Infra Layer

- **Service**
  - `gateway-api`
- **Infrastructure**
  - `postgres` (metadata)
  - `redis` (task queue)
  - `minio` or local volumes (object storage)
- **Responsibility**
  - Expose a **unified API** to UI / CLI / other systems:
    - Create datasets
    - Trigger mining / filtering / training / evaluation
    - Query task / run / model status
  - Internally:
    - Write / update metadata in Postgres
    - Enqueue heavy tasks for other services

---
## 2. Core Domain Entities & Meta Conventions

OpenDataEngine does **not** hard-code task-specific logic (e.g. ComfyUI workflows,
robot scripts, or specific evaluation metrics). Instead, everything is described by a
small set of **domain entities** with structured `meta` fields stored as JSON.

All services share these entities:

- `CollectionRun` – one ingestion / generation / import run
- `RawSample` – one raw item (image / frame / text / …)
- `DatasetView` – a logical dataset constructed from collections + filters + splits
- `TrainingRun` – one training experiment on a dataset
- `EvalRun` – one evaluation experiment (metrics + artifacts) on a model and dataset

Each entity has a `meta` JSON field with a **common structure**:

### 2.1 `CollectionRun.meta`

Describes *how* this collection was produced.

- `method`
  - `family`: high-level type – `"collector" | "filter" | "synthetic" | "importer" | …"`
  - `name`: concrete method – `"manual_uploader" | "spider" | "comfy_t2i" | "mine_cold_start" | …"`
  - `origin`: data origin – `"real_world" | "web" | "synthetic" | "public_dataset" | "simulation" | …"`
  - `interaction_mode`: `"manual" | "automatic" | "semi_auto"`
  - `tool`: optional external tool name – `"comfyui" | "browser_spider" | "none" | …"`
  - `operator`: who triggered it (user / system)
- `data`
  - `modalities`: e.g. `["image"]`, `["image","mask"]`
  - `domain`: e.g. `"shoulder_injection"`, `"generic_natural_image"`
  - `approx_samples`: rough expected sample count
  - `license`, `sensitive_level`: usage & compliance info
- `pipeline`
  - `tags`: free-form tags – `"cold_start"`, `"seed"`, `"flux"`, …
  - `version`: pipeline or config version
  - `upstream_run_ids`: if derived from other runs
- `external`
  - opaque payload for external systems (e.g. full ComfyUI workflow JSON,
    spider URL list, robot scenario config).  
    Data Engine stores it but does not interpret the structure.

This allows us to treat **manual upload, spider, cold-start mining, and T2I generators
all as `CollectionRun` with different `method.*` values**.

### 2.2 `RawSample.meta`

Describes each raw file.

- `collection_run_id`: which `CollectionRun` it belongs to
- `data`
  - `modality`: `"image" | "video" | "text" | …"`
  - `width`, `height`, `channels`, `format`, `duration_sec` (if applicable)
  - `hash`: content hash for deduplication
- `semantic`
  - `split_hint`: `"train" | "val" | "test" | "unspecified"`
  - `category_hint`: coarse category if known
  - `prompt`: optional text prompt / caption
  - `language`: if text is involved
- `pipeline`
  - `is_filtered_in`: `true | false | null` (null = not filtered yet)
  - `filter_scores`: open dict for CLIP / aesthetic / uncertainty scores
  - `label_status`: `"unlabeled" | "human_labeled" | "pseudo_labeled" | "verified"`
- `external`
  - `generator`: info about T2I / simulator (name, seed, workflow id, …)
  - `capture`: camera / robot capture info, etc.

### 2.3 `DatasetView.meta`

A logical dataset constructed from collections + filters.

- `source`
  - `type`: `"collection_query" | "static_list" | "external_import"`
  - `collection_ids`: which collections it draws from
  - `filters`: query conditions over `RawSample.meta`
- `split`
  - `strategy`: `"by_ratio" | "by_rule" | …"`
  - `params`: e.g. `{train: 0.7, val: 0.2, test: 0.1}`
  - `seed`: for reproducible splits
- `task`
  - `type`: `"segmentation" | "detection" | "qa" | …"`
  - `label_schema`: versioned label definition id
  - `input_modalities`, `target_modalities`
- `pipeline`
  - `tags`: e.g. `"filter1_passed"`, `"yolo11_trainset"`
  - `created_by`: which service created this view
  - `upstream_run_ids`: provenance

### 2.4 `TrainingRun.meta`

Abstract description of a training experiment.

- `task`: task type, model family/name, framework, pretrained weights
- `data`: dataset id, used splits, sample counts
- `hyperparams`: epochs, batch size, lr, optimizer, scheduler, …
- `hardware`: device, num_gpus, node id
- `pipeline`: tags, notes, upstream dataset / collection ids
- `artifacts`: relative paths to checkpoints, logs, etc.

### 2.5 `EvalRun.meta`

Abstract description of an evaluation experiment.

- `subject`: what is being evaluated (training_run_id, checkpoint path, …)
- `data`: dataset id + split
- `protocol`
  - `preset`: evaluation preset name, e.g. `"segmentation_core"`
  - `metrics`: metric names (`"mAP@0.5"`, `"mIoU"`, …)
  - `external_evaluators`: names of evaluator backends used
- `pipeline`: tags, notes, upstream ids
- `results`
  - `summary`: key metrics
  - `artifacts`: links to detailed JSON / reports / plots

> **Important:**  
> Data Engine focuses on these **abstract entities and meta schemas**.  
> Concrete business logic (e.g. a specific ComfyUI workflow, a specific LLM
> evaluator, a specific robot sequence) lives in external tools or plugins and is
> only referenced via `method.*`, `external.*`, and `artifacts` paths.

---
## 3. Key Roles: gateway-api vs collection-gateway vs collectors vs mine-service

To avoid confusion, here is a concise comparison:

- **`gateway-api`**
  - System **control center / front desk for users**
  - Orchestrates: `mine`, `filter`, `train`, `eval`, HITL flows
  - Used by: front-end UI, external tools, scripts

- **`collection-gateway`**
  - **Single entry point for raw data**
  - Receives files + metadata, stores them as `raw_samples`
  - Used by: collectors (spiders, robots, manual uploaders, etc.)

- **`collectors/`**
  - Various **data ingestion tools/agents**
  - Implementation examples:
    - `manual-uploader`: upload from local directory
    - `spider-collector`: web crawling
    - `robot-collector`: ROS node publishing frames/states
    - `video-mining-collector`: cut frames from long videos
  - They **always send data into `collection-gateway`**, not directly to DB.

- **`mine-service`**
  - **First-stage data processing** inside the warehouse:
    - deduplication, coarse sampling, segmenting sequences
    - transform `raw_samples` → `candidate_samples`

---

## 4. Data Flow (high-level)

A typical closed loop looks like:

1. **Collect**
   - One or multiple `collectors` push data to `collection-gateway`
   - `raw_samples` are stored + registered

2. **Mine**
   - `gateway-api` triggers `mine-service` for a given collection
   - `mine-service` outputs `candidate_samples`

3. **Filter & Label**
   - `gateway-api` triggers `filter-service` on a candidate set
   - Filtered samples are sent to a labeling project (via `label-sync-service`)
   - Human annotators and pseudo-labels update `dataset_versions`

4. **Train**
   - `gateway-api` triggers `training-service` on a specific `dataset_version`
   - New model artefacts are stored and registered

5. **Evaluate & HITL**
   - `gateway-api` triggers `evaluation-service`
   - Hard / wrong samples are marked as `need_review`
   - These samples go back to labeling → new dataset version → new training round

This forms a **closed-loop Data Engine** with humans and models both improving the dataset over time.

--- 
## 5. Human-in-the-Loop (HITL) Closed Loop

OpenDataEngine is designed to support **Human-in-the-Loop (HITL)** workflows, especially for
semi-supervised learning settings where **models and human experts correct each other**.

At a high level, humans mainly participate in two key stages:

- **Evaluation** – inspect how the model behaves on real data
- **Correction** – fix wrong or low-confidence predictions and feed them back as new labels

Concretely, HITL appears in two layers:

### 5.1 Where HITL happens in the architecture
1. **Filter & Labeling Layer**
   - Services: `filter-service`, `label-sync-service`
   - Role:
     - Use models (e.g. CLIP, task models) to pre-select or pre-label samples
     - Send selected items to a labeling platform
     - Let humans confirm / correct / refine labels

2. **Evaluation & HITL Layer**
   - Service: `evaluation-service`
   - Role:
     - Run the trained model on evaluation datasets
     - Log per-sample predictions and metrics
     - Detect "hard" or "suspicious" samples and mark them as `need_review`
     - Push these samples back into the labeling workflow


### 5.2 Typical HITL loop in semi-supervised learning

In a semi-supervised setting, a typical HITL loop looks like:

1. **Start with a labeled set L and an unlabeled pool U**
   - L: high-quality human-labeled data
   - U: large raw pool collected via the Data Collection + Mine layers

2. **Train an initial model M₀ on L**
   - Triggered via `gateway-api` → `training-service`
   - The resulting model is stored and registered in `models`

3. **Predict on the unlabeled pool U (pseudo-labeling)**
   - `filter-service` (or a dedicated pseudo-label worker) runs M₀ on samples from U
   - For each sample, it records:
     - model prediction (pseudo label)
     - confidence / uncertainty score
     - optional consistency / perturbation-based stability scores

4. **AI pre-filtering: select what is worth human attention**
   - High-confidence, stable pseudo-labels can be auto-accepted as training candidates
   - Low-confidence or unstable samples are marked as `need_review`
   - A subset of "borderline" samples is sent to human experts

5. **Human review and correction (HITL)**
   - `label-sync-service` creates / updates projects on Label Studio / CVAT
   - Humans:
     - confirm correct pseudo-labels,
     - fix incorrect ones,
     - or annotate from scratch if the model is very uncertain
   - These human corrections are written back as new label versions in `dataset_versions`

6. **Update the training set and retrain**
   - A new `dataset_version` is created that merges:
     - original labeled set L
     - accepted pseudo-labeled samples from U
     - human-reviewed corrections
   - `gateway-api` triggers a new training run:
     - M₁ is trained on the updated dataset version

7. **Evaluation + error mining**
   - `evaluation-service` evaluates M₁ on one or more datasets
   - For each sample, it can:
     - log the error type,
     - mark `need_review` when prediction is suspicious or inconsistent
   - These `need_review` samples are again pushed to the labeling platform,
     closing the HITL loop.

This creates a **closed data loop**:
raw data → pseudo-labeling → AI pre-filtering → human review → new dataset version → new model → evaluation → new hard cases → back to human review.

### 5.3 Roles of AI vs Human in this loop
### AI vs Human responsibilities

- **AI (models + filters)**
  - Quickly scan large unlabeled pools
  - Provide pseudo labels and confidence/uncertainty scores
  - Suggest which samples are likely correct (auto-accept) and which are suspicious (need human)

- **Human experts**
  - Focus on the "interesting" subset:
    - low-confidence samples,
    - high-loss samples,
    - disagreement cases between multiple models/filters
  - Correct labels, add fine-grained annotations, and define new edge cases

- **OpenDataEngine**
  - Provides the infrastructure so that:
    - models and humans see the same samples and metadata,
    - every correction becomes part of a **versioned dataset**,
    - each new model training run has a reproducible data provenance.


# Overall:
HITL in OpenDataEngine:

- Models propose (pseudo-labels, filters, suspicious samples)
- Humans dispose (confirm, correct, annotate edge cases)
- The engine turns these interactions into new dataset versions → new models → new evaluations.

# OpenDataEngine

OpenDataEngine is an open-source data engine with **Human-in-the-Loop (HITL)**, designed using a **microservices architecture** for scalability and extensibility.

By integrating open-source AI models, OpenDataEngine helps to **reduce data collection cost** and **accelerate data labeling** across common AI tasks (starting from CV, and extensible to robotics / logs / multi-modal data).

> **Design philosophy:**  
> - Top-level: a **unified orchestration layer** (one “control center”)  
> - Bottom-level: **pluggable modules** (filters, trainers, collectors…) that can be swapped or extended without changing the whole system.

---

## Features (WIP)

- 🧱 **Modular, plugin-based architecture**  
  - Separate services for collection, mining, filtering, labeling, training, evaluation  
  - Each service can host multiple plugins (e.g., different filters or trainers)

- 🧑‍💻 **HITL (Human-in-the-Loop) by design**  
  - Integrates with external labeling platforms (Label Studio, CVAT, etc.)  
  - Supports error mining & review loops for model evaluation

- 🤖 **Multi-source data collection**  
  - Manual upload, spiders, robotics data, video mining…  
  - Unified `collection-gateway` as the single entry for **raw samples**

- 📦 **Microservices + Docker-first**  
  - Each backend component is a FastAPI-based service  
  - `docker-compose` for local orchestration  
  - Future-ready for Kubernetes deployment

---

## TODO / Roadmap

- [x] Overall architecture image
- [ ] Synthetic module + Label module
  - [ ] Pick a robust open-source labeling platform (e.g. Label Studio / CVAT)
  - [ ] Design controllable generation methods + guidance strategies
- [ ] Evaluation + HITL loop
- [ ] Filter module
  - [ ] CLIP-based filter
  - [ ] Perturbation-based filter (stability / robustness filter)
- [ ] More plugins & tasks
  - [ ] New trainers (other CV tasks, then non-CV tasks)
  - [ ] More data collectors (robotics, AR, logs, etc.)
- [ ] Login authorization layer
  - [ ]
---

## High-level Architecture (6 Layers)

Details are in [`docs/architecture.md`](docs/architecture.md).  
Here is the short version:

1. **Data Collection Layer**  
   - Services: `collection-gateway` + various `collectors/`  
   - Responsibility: bring data from outside world → unified `raw_samples` format

2. **Mine & Preprocess Layer**  
   - Service: `mine-service`  
   - Responsibility: deduplication, coarse sampling, basic preprocessing → `candidate_samples`

3. **Filter & Labeling Layer**  
   - Services: `filter-service`, `label-sync-service`  
   - Responsibility: intelligent filtering, integration with labeling platforms, produce `dataset_versions`

4. **Training Layer**  
   - Service: `training-service`  
   - Responsibility: train models from a given dataset version → register `models`

5. **Evaluation & HITL Layer**  
   - Service: `evaluation-service`  
   - Responsibility: run evaluation, log per-sample errors, mark `need_review` samples for human review

6. **Orchestration & Infra Layer**  
   - Service: `gateway-api`  
   - Infra: `postgres`, `redis`, `minio` / local storage  
   - Responsibility: expose unified API to UI/tools, manage tasks & status, trigger jobs

---

## Project Structure

```bash
data-engine/
├── services/                     # 每个后端服务一个子目录（FastAPI）
│   ├── gateway-api/              # Orchestrator, 总控中心/前台，统一对外 API
│   │   ├── app/
│   │   │   ├── main.py
│   │   │   ├── api/              # 路由：datasets, runs, models, tasks...
│   │   │   ├── schemas/          # Pydantic 模型（请求/响应）
│   │   │   ├── services/         # 调度其他服务 / 发送队列任务
│   │   │   └── deps.py
│   │   ├── tests/
│   │   └── Dockerfile
│   │
│   ├── collection-gateway/       # Data Collection 层统一入口（数据收件处）
│   │   ├── app/
│   │   │   ├── main.py
│   │   │   ├── api/
│   │   │   │   ├── collections.py   # 创建 collection_run
│   │   │   │   └── samples.py       # 上传/登记 raw_sample，单个样本
│   │   │   ├── schemas/             # RawSample, CollectionRun
│   │   │   └── storage/             # 本地/MinIO 抽象
│   │   ├── tests/
│   │   └── Dockerfile
│   │
│   ├── mine-service/
│   │   ├── app/
│   │   │   ├── main.py              # 可选 REST 接口 / 健康检查
│   │   │   ├── workers/             # 队列 Worker：mine_raw_samples()
│   │   │   └── logic/               # 去重 / 采样 / 分段算法
│   │   └── Dockerfile
│   │
│   ├── filter-service/
│   │   ├── app/
│   │   │   ├── main.py              # 健康检查 + 配置接口
│   │   │   ├── workers/
│   │   │   │   ├── clip_filter.py
│   │   │   │   ├── asf_filter.py
│   │   │   │   └── pcs_filter.py
│   │   │   └── plugin_registry.py   # 插件注册表（新增 Filter 在这里挂接）
│   │   └── Dockerfile
│   │
│   ├── label-sync-service/
│   │   ├── app/
│   │   │   ├── main.py
│   │   │   ├── workers/
│   │   │   │   └── sync_from_label_studio.py
│   │   │   └── clients/
│   │   │       └── label_studio_client.py
│   │   └── Dockerfile
│   │
│   ├── training-service/
│   │   ├── app/
│   │   │   ├── main.py              # 监控 / 状态查询
│   │   │   ├── workers/
│   │   │   │   ├── train_segmentation_yolo.py
│   │   │   │   └── train_xxx_other_task.py
│   │   │   └── runners/
│   │   │       └── yolo_runner.py   # 包装已有训练脚本
│   │   └── Dockerfile
│   │
│   ├── evaluation-service/
│   │   ├── app/
│   │   │   ├── main.py
│   │   │   ├── workers/
│   │   │   │   ├── eval_segmentation.py
│   │   │   │   └── error_analysis.py
│   │   │   └── metrics/
│   │   └── Dockerfile
│   │
│   └── synthetic-service/         # 可选：合成数据生成服务（Phase 2）
│       ├── app/
│       │   ├── main.py
│       │   ├── workers/
│       │   │   └── generate_synthetic_batch.py
│       │   └── clients/           # ComfyUI / Flux / SD 接口
│       └── Dockerfile
│
├── collectors/                    # 工具脚本：调用 collection-gateway API
│   ├── manual-uploader/           # 本地目录 → collection-gateway
│   │   └── upload_from_dir.py
│   ├── spider-collector/
│   │   └── run_spider_and_push.py
│   ├── robot-collector/
│   │   └── ros_node_publisher.py  # ROS topic → HTTP → collection-gateway
│   └── video-mining-collector/
│       └── extract_frames_and_push.py
│
├── libs/                          # 共享代码（避免各服务 copy-paste）
│   ├── core_db/
│   │   └── __init__.py
│   │   └── db.py                # Engine / SessionLocal / Base
│   │   └── deps.py              # FastAPI 里用的 get_db 依赖
│   │   └── models/
│   │   │   └── __init__.py        # 汇总导出所有 ORM 模型
│   │   │   └── collection.py      # Collection 相关表
│   │   │   └── sample.py          # Sample 相关表
│   │   │   └── # …未来可以继续拆 user.py, job.py 等
│   ├── core-schemas/              # Pydantic 模型（RawSample, Dataset, Model, Task...）
│   ├── core-queue/                # 队列封装（Redis/RQ 或 Celery）
│   └── core-storage/              # 本地 / MinIO / S3 客户端
│
├── infra/                         # infrastructure 基础设施：所有服务共同依赖的基础设施 + 部署文件 （多服务架构的表现）
│   ├── docker-compose.yml         # 一键启动所有服务和基础设施
│   ├── env/                       # .env 模板
│   │   ├── .env.gateway
│   │   ├── .env.collection
│   │   └── ...
│   └── k8s/                       # 将来要上 Kubernetes 再填
│
├── docs/
│   ├── architecture.md            # 高层架构描述
│   ├── data_flow.md               # 数据流 / 状态机（WIP）
│   └── api-specs/                 # OpenAPI / 接口规范
│
├── scripts/
│   ├── dev_bootstrap.sh           # 本地快速启动环境
│   └── init_db.py                 # 初始化数据库 / 基础表
│
└── README.md


# Usage 

```bash

conda create -n open_data_engine python=3.10 
conda activate open_data_engine

# 第一次创建环境后使用一次 pip，安装 uv！！后续统一用 uv 管理安装
pip install uv

# 安装依赖
uv pip install -r requirements.txt


# -----------------------------
# 把 Data-Engine 这个项目装进环境里。-e = editable，可编辑安装（开发模式）
uv pip install -e .


# 安装 model 权重的 cli： https://huggingface.co/docs/huggingface_hub/en/guides/cli

uv tool install "huggingface_hub"

hf auth whoami

# 如果 zsh: command not found: hf，请执行下列命令，否则忽略
  echo 'export PATH="$HOME/.local/bin:$PATH"' >> ~/.zshrc
  source ~/.zshrc


# 环境变量，如果 docker 没有专门修改端口，端口开启正常的话，默认按照下列配置
export COLLECTION_GATEWAY_URL=http://localhost:8001/

# ----------------------------
# uv 管理规范：下载示例，保持 toml 更新和 requirement.txt更新
# ----------------------------
# eg: uv 下载 pillow 并 更新 toml 依赖文件
uv add Pillow
# eg: 更新 requirements.txt (不固定版本： 普遍">=xxx.xx"形式)
uv pip install -r requirements.txt 
# eg: 更新requirements.txt，固定版本的, (普遍"=xxx.xx"形式)
uv export --no-hashes --format requirements-txt > requirements.txt



# ----------------------------
# 镜像里面的依赖，如果在本地更新了，需要重新 docker build
# ----------------------------
# 例如本地开发途中，我们有依赖更新了，那么此时由于我们当前的./infra/docker-compose.yml中配置的挂载只有开发的文件夹，但是没有包含依赖，所以下一次启动需要按照如下操作
docker compose up --build

# 如果只是普通更新，代码更新，按照我们的配置，只需要
docker compose up

```
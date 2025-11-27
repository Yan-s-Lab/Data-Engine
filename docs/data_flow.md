

# 🔥 整条 MVP Pipeline（你可以作为 docs/data_flow.md）

## Scenario: “Injection Data Engine MVP 1.0”：

### Step 1. 上传初始数据（冷启动）

```
manual-uploader → collection-gateway → raw_samples
```

### Step 2. Mine

```
mine-service:
    - 去重
    - 基础质量过滤
    - 抽样候选集 candidate_samples
```

### Step 3. Filter-1（AI + 人工结合）

```
filter-service:
    - CLIP embeddings
    - 聚类 → scatter plot (UMAP)

人工：
    在前端选择：accept / reject
输出 → filtered_samples
```

### Step 4. 标注（人工的第一层）

```
label-sync-service → Label Studio
人工在 Label Studio 画 mask
label-sync 拉回 → dataset_version_1
```

### Step 5. Synthetic Augment

```
synthetic-service:
    - ComfyUI workflow (camera/pose guidance)
    - filter2: CLIP / pose alignment

输出 → synthetic_samples

dataset_version_2 = real + synthetic
```

### Step 6. 训练 YOLO

```
training-service → best.pt
```

### Step 7. 评估（AI 的第二次筛选）

```
evaluation-service:
    - IoU
    - 边界误差
    - need_review = True
```

### Step 8. HITL 闭环（人工的第二层）

```
Hard cases → Label Studio → 修正 → 新标签
dataset_version_3 → 再训练 → 再评估
```

> **synthetic + real ♻️ training ♻️ HITL 无限循环**

---

```
The MVP of OpenDataEngine for Injection Segmentation supports:
real data → mine → CLIP filtering → human labeling → synthetic augmentation →
YOLO training → evaluation → HITL corrections → next dataset version.
```


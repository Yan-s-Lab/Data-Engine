from PIL import Image
from pathlib import Path
import torch
from transformers import AutoProcessor, AutoModel

ckpt = "google/siglip2-so400m-patch16-naflex"
device = "cuda" if torch.cuda.is_available() else "cpu"

model = AutoModel.from_pretrained(ckpt, dtype=torch.float32).to(device).eval()
# processor = AutoProcessor.from_pretrained(ckpt)  # 先别加 use_fast，避免你版本不兼容/行为变化
processor = AutoProcessor.from_pretrained(ckpt, use_fast=True)

image_path = Path(__file__).resolve().parent / "yk003__body_pose_coco__prompt_canny__yk003__body_pose_coco__0275_00002_.png"
print("image path:", image_path)
image = Image.open(image_path).convert("RGB")
print("PIL:", image.mode, image.size)

positive_texts = [
    "a photo of one or more people",
    "a real-world photo containing people",
    "a natural human pose in a real-life scene",
    "one or more people with visible body poses",
    "people with distinguishable body positions",
    "a full-body or mostly visible human figure",
    "one or more people with visible arms and legs",
    "a photo suitable for human pose estimation",
    "people in natural standing, walking, or moving poses",
    "a realistic scene with one or more humans visible",
    "a realistic photo of people in natural poses",
    "a natural scene containing people"
]
negative_texts = [
    "a photo with no person",
    "a landscape or object without people",
    "a close-up photo of a face",
    "a portrait photo focusing only on the face",
    "a close-up of a hand or fingers",
    "a close-up of legs or feet only",
    "a cropped image showing only part of a person",
    "a body part close-up without the full pose",
    "a person heavily cut off by the image border",
    "a severely occluded person",
    "multiple people heavily overlapping and hard to distinguish",
    "a distorted human body",
    "a person with missing limbs",
    "a person with extra limbs",
    "an anatomically incorrect human body",
    "a person with too many legs",
    "A person has many legs",
    "a cartoon style image",
    "3d rendered character",
]
texts = positive_texts + negative_texts

inputs = processor(text=texts, images=image, padding="max_length", return_tensors="pt")
pv = inputs["pixel_values"]
print("pixel_values dtype/min/max:", pv.dtype, pv.min().item(), pv.max().item())

inputs = {k: v.to(device) for k, v in inputs.items()}

with torch.no_grad():
    logits = model(**inputs).logits_per_image.float().cpu()[0]

print("logits:", logits.numpy())
probs = torch.sigmoid(logits)

for index, label in enumerate(texts):
    print(f"{probs[index].item():.1%} that image is '{label}'")
    print(f"[{index}] {label}: logit={logits[index].item():.6f}, sigmoid={probs[index].item():.6f}")

pos_logits = logits[: len(positive_texts)]
neg_logits = logits[len(positive_texts) :]

# Pairwise fairness score: compare every positive prompt with every negative prompt.
pairwise = pos_logits[:, None] - neg_logits[None, :]
pairwise_flat = pairwise.flatten()

median_margin = pairwise_flat.median().item()
mean_margin = pairwise_flat.mean().item()

sorted_pairwise = torch.sort(pairwise_flat).values
n = sorted_pairwise.numel()
trim = int(n * 0.2)
if trim > 0 and n > 2 * trim:
    trimmed_mean_margin = sorted_pairwise[trim:-trim].mean().item()
else:
    trimmed_mean_margin = mean_margin

q1 = torch.quantile(pairwise_flat, 0.25).item()
q3 = torch.quantile(pairwise_flat, 0.75).item()
iqr = q3 - q1
std = pairwise_flat.std(unbiased=False).item()

threshold = 0.0
pred = median_margin > threshold

print("\n=== Pairwise margins (pos_i - neg_j) ===")
print(pairwise.numpy())
print("pairwise_count:", n)
print("median_margin:", f"{median_margin:.6f}")
print("trimmed_mean_margin(20%):", f"{trimmed_mean_margin:.6f}")
print("mean_margin:", f"{mean_margin:.6f}")
print("IQR:", f"{iqr:.6f}")
print("std:", f"{std:.6f}")
print("threshold:", f"{threshold:.6f}")
print("final:", pred)

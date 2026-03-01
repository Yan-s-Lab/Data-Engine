import torch
import requests
from PIL import Image
from transformers import AutoProcessor, AutoModel, BitsAndBytesConfig

ckpt = "google/siglip2-so400m-patch16-naflex"


def load_model():
    try:
        bnb_config = BitsAndBytesConfig(load_in_4bit=True)
        return AutoModel.from_pretrained(
            ckpt,
            quantization_config=bnb_config,
            device_map="auto",
            attn_implementation="sdpa",
        )
    except Exception as exc:
        print(f"[warn] 4-bit load failed, fallback to non-quantized model: {exc}")
        return AutoModel.from_pretrained(
            ckpt,
            device_map="auto",
            dtype=torch.float16 if torch.cuda.is_available() else torch.float32,
            attn_implementation="sdpa",
        )


model = load_model()
processor = AutoProcessor.from_pretrained(ckpt)

url = "https://huggingface.co/datasets/huggingface/documentation-images/resolve/main/pipeline-cat-chonk.jpeg"
image = Image.open(requests.get(url, stream=True).raw) # type: ignore
# candidate_labels = ["a Pallas cat", "a lion", "a Siberian tiger"]
candidate_labels = ["a cat", "a plane", "a remote"]

# follows the pipeline prompt template to get same results
texts = [f'This is a photo of {label}.' for label in candidate_labels]

# IMPORTANT: we pass `padding=max_length` and `max_length=64` since the model was trained with this
inputs = processor(text=candidate_labels, images=image, padding="max_length", max_length=64, return_tensors="pt").to(model.device)

with torch.no_grad():
    try:
        outputs = model(**inputs)
    except RuntimeError as exc:
        if "same dtype" not in str(exc):
            raise
        print(f"[warn] quantized forward failed, retrying in non-quantized mode: {exc}")
        model = AutoModel.from_pretrained(
            ckpt,
            device_map="auto",
            dtype=torch.float16 if torch.cuda.is_available() else torch.float32,
            attn_implementation="sdpa",
        )
        inputs = inputs.to(model.device)
        outputs = model(**inputs)

logits_per_image = outputs.logits_per_image
probs = torch.sigmoid(logits_per_image) # SigLIP2是采用 sigmoid 训练的

image0_probs = probs[0]
for label, score in zip(candidate_labels, image0_probs):
    print(f"{label:25s} -> {score.item():.4f}")
print(f"{image0_probs[0]:.1%} that image 0 is '{candidate_labels[0]}'")

# from transformers import pipeline
# from transformers.image_utils import load_image


# # load pipeline
# ckpt = "google/siglip2-so400m-patch16-naflex"
# image_classifier = pipeline(model=ckpt, task="zero-shot-image-classification")

# # load image and candidate labels
# image = load_image("http://images.cocodataset.org/val2017/000000039769.jpg")
# candidate_labels = ["2 cats", "a plane", "a remote"]

# # run inference
# outputs = image_classifier(image, candidate_labels)
# print(outputs)

import argparse
import json
from pathlib import Path

import cv2
import numpy as np


BODY25_LIMBS = [
    (1, 8), (1, 2), (1, 5),
    (2, 3), (3, 4),
    (5, 6), (6, 7),
    (8, 9), (9, 10), (10, 11),
    (8, 12), (12, 13), (13, 14),
    (1, 0), (0, 15), (15, 17),
    (0, 16), (16, 18),
    (14, 19), (19, 20), (14, 21),
    (11, 22), (22, 23), (11, 24),
]

COCO18_LIMBS = [
    (1, 2), (2, 3), (3, 4),
    (1, 5), (5, 6), (6, 7),
    (1, 8), (8, 9), (9, 10),
    (1, 11), (11, 12), (12, 13),
    (1, 0), (0, 14), (14, 16),
    (0, 15), (15, 17),
]


def to_kpts(arr):
    if not arr:
        return np.zeros((0, 3), dtype=np.float32)
    return np.asarray(arr, dtype=np.float32).reshape(-1, 3)


def draw_kpts(img, kpts, radius, color, thr):
    if kpts.size == 0 or radius <= 0:
        return
    for x, y, c in kpts:
        if c < thr:
            continue
        cv2.circle(img, (int(x), int(y)), radius, color, -1, cv2.LINE_AA)


def draw_limbs(img, kpts, limbs, thickness, color, thr):
    if kpts.size == 0 or thickness <= 0:
        return
    n = kpts.shape[0]
    for a, b in limbs:
        if a >= n or b >= n:
            continue
        xa, ya, ca = kpts[a]
        xb, yb, cb = kpts[b]
        if ca < thr or cb < thr:
            continue
        cv2.line(
            img,
            (int(xa), int(ya)),
            (int(xb), int(yb)),
            color,
            thickness,
            cv2.LINE_AA,
        )


def infer_body_limbs(body_kpts):
    n = body_kpts.shape[0]
    if n >= 25:
        return BODY25_LIMBS
    if n >= 18:
        return COCO18_LIMBS
    return []


def parse_args():
    p = argparse.ArgumentParser(
        description="Render OpenPose JSON to black background with configurable thickness/radius."
    )
    p.add_argument("--json", required=True, help="OpenPose keypoints JSON path")
    p.add_argument("--ref-image", required=True, help="Reference image path for output size")
    p.add_argument("--out", required=True, help="Output rendered PNG path")

    p.add_argument("--conf-thr", type=float, default=0.05, help="Confidence threshold")

    p.add_argument("--body-line", type=int, default=2, help="Body limb thickness")
    p.add_argument("--body-point", type=int, default=2, help="Body point radius")

    p.add_argument("--face-point", type=int, default=1, help="Face point radius")
    p.add_argument("--hand-point", type=int, default=1, help="Hand point radius")

    p.add_argument("--body-color", default="0,255,255", help="BGR color: b,g,r")
    p.add_argument("--face-color", default="0,255,0", help="BGR color: b,g,r")
    p.add_argument("--hand-color", default="255,255,0", help="BGR color: b,g,r")
    return p.parse_args()


def parse_color(s):
    b, g, r = [int(x) for x in s.split(",")]
    return (b, g, r)


def main():
    args = parse_args()

    ref = cv2.imread(str(args.ref_image), cv2.IMREAD_COLOR)
    if ref is None:
        raise FileNotFoundError(f"Cannot read ref image: {args.ref_image}")
    h, w = ref.shape[:2]

    data = json.loads(Path(args.json).read_text())
    people = data.get("people", [])

    canvas = np.zeros((h, w, 3), dtype=np.uint8)

    body_color = parse_color(args.body_color)
    face_color = parse_color(args.face_color)
    hand_color = parse_color(args.hand_color)

    for p in people:
        body = to_kpts(p.get("pose_keypoints_2d", []))
        face = to_kpts(p.get("face_keypoints_2d", []))
        lhand = to_kpts(p.get("hand_left_keypoints_2d", []))
        rhand = to_kpts(p.get("hand_right_keypoints_2d", []))

        draw_limbs(
            canvas,
            body,
            infer_body_limbs(body),
            args.body_line,
            body_color,
            args.conf_thr,
        )
        draw_kpts(canvas, body, args.body_point, body_color, args.conf_thr)
        draw_kpts(canvas, face, args.face_point, face_color, args.conf_thr)
        draw_kpts(canvas, lhand, args.hand_point, hand_color, args.conf_thr)
        draw_kpts(canvas, rhand, args.hand_point, hand_color, args.conf_thr)

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    cv2.imwrite(str(out), canvas)
    print(f"Saved: {out}")


if __name__ == "__main__":
    main()

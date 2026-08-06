"""Build compressed CC OCR orientation fixtures (dev helper, not shipped)."""

from __future__ import annotations

import io
import json
import urllib.parse
import urllib.request
from pathlib import Path

from PIL import Image


ROOT = Path(__file__).resolve().parents[1] / "tests" / "fixtures" / "file_search" / "ocr" / "orientation"
MAX_DIM = 1400
ANGLES = (0, 90, 180, 270)
_UA = {"User-Agent": "srxy-fixture-builder/1.0"}

SOURCES = [
	{
		"id": "ocr_document",
		"url": "https://upload.wikimedia.org/wikipedia/commons/7/75/Test_OCR_document.jpg",
		"title": "Test OCR document.jpg",
		"author": "Kaldari",
		"license": "CC0 1.0",
		"license_url": "https://creativecommons.org/publicdomain/zero/1.0/",
		"page": "https://commons.wikimedia.org/wiki/File:Test_OCR_document.jpg",
		"token": "sister",
	},
	{
		"id": "no_smoking",
		"url": "",
		"title": "Malaysia Prohibition-signs-No-smoking-sign-01.jpg",
		"author": "see Commons page",
		"license": "CC BY-SA 4.0",
		"license_url": "https://creativecommons.org/licenses/by-sa/4.0/",
		"page": "https://commons.wikimedia.org/wiki/File:Malaysia_Prohibition-signs-No-smoking-sign-01.jpg",
		"token": "smoking",
		"commons_title": "File:Malaysia Prohibition-signs-No-smoking-sign-01.jpg",
	},
]


def commons_original_url(title: str) -> str:
	api = "https://commons.wikimedia.org/w/api.php?" + urllib.parse.urlencode(
		{
			"action": "query",
			"titles": title,
			"prop": "imageinfo",
			"iiprop": "url",
			"format": "json",
		}
	)
	with urllib.request.urlopen(urllib.request.Request(api, headers=_UA), timeout=60) as response:
		payload = json.load(response)
	pages = payload["query"]["pages"]
	for page in pages.values():
		info = (page.get("imageinfo") or [{}])[0]
		url = info.get("url")
		if isinstance(url, str) and url:
			return url.split("?", 1)[0]
	raise RuntimeError(f"could not resolve Commons URL for {title}")


def compress(im: Image.Image) -> Image.Image:
	im = im.convert("RGB")
	width, height = im.size
	max_dim = max(width, height)
	if max_dim > MAX_DIM:
		scale = MAX_DIM / max_dim
		im = im.resize((int(width * scale), int(height * scale)), Image.Resampling.LANCZOS)
	return im


def save_jpeg(im: Image.Image, path: Path):
	im.save(path, format="JPEG", quality=75, optimize=True)


def rotate_on_canvas(im: Image.Image, angle: int) -> Image.Image:
	if angle % 360 == 0:
		return im
	return im.rotate(angle, expand=True, fillcolor="white")


def main():
	ROOT.mkdir(parents=True, exist_ok=True)
	# Drop superseded fixture names from earlier builds.
	for stale in ROOT.glob("welcome_sign_*.jpg"):
		stale.unlink()
	for stale in ROOT.glob("*_45.jpg"):
		stale.unlink()

	attrib = ["# OCR orientation fixtures — attribution", ""]
	for src in SOURCES:
		print("fetch", src["id"])
		url = src["url"] or commons_original_url(str(src["commons_title"]))
		req = urllib.request.Request(url, headers=_UA)
		with urllib.request.urlopen(req, timeout=120) as response:
			data = response.read()
		base = compress(Image.open(io.BytesIO(data)))
		for angle in ANGLES:
			out = ROOT / f"{src['id']}_{angle}.jpg"
			save_jpeg(rotate_on_canvas(base, angle), out)
			print(" ", out.name, out.stat().st_size)
		attrib.append(f"## {src['id']}_*.jpg")
		attrib.append(f"- Source: [{src['title']}]({src['page']})")
		attrib.append(f"- Author: {src['author']}")
		attrib.append(f"- License: [{src['license']}]({src['license_url']})")
		attrib.append(f"- Modifications: resized (max {MAX_DIM}px), JPEG q75, rotated to 0/90/180/270")
		attrib.append(f"- Expected OCR token: `{src['token']}`")
		attrib.append("")
	(ROOT / "ATTRIBUTION.md").write_text("\n".join(attrib) + "\n", encoding="utf-8")
	print("wrote", ROOT)


if __name__ == "__main__":
	main()

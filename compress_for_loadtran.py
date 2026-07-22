#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Nen anh cuc manh de dung voi loadtran.py.

Mac dinh script se:
  - quet anh trong thu muc hien tai
  - crop/resize ve dung size poster 1080x1701
  - xuat JPG nen manh nhung van giu anh de nhin vao thu muc compressed/

Ly do resize san ve 1080x1701:
  loadtran.py neu gap anh dung kich thuoc nay se giu bytes goc,
  khong convert sang PNG lon hon.

Vi du:
  python compress_for_loadtran.py
  python compress_for_loadtran.py --input . --output compressed
  python compress_for_loadtran.py --replace-original
  python compress_for_loadtran.py --max-kb 100   # RCM 100KB
  python compress_for_loadtran.py --max-kb 0     # MAX-READABLE
  python loadtran.py --dir compressed --har synthetic_player_poster.har
"""

import argparse
import io
import os
import sys
from pathlib import Path

try:
    from PIL import Image, ImageOps
except ImportError:
    print("Thieu Pillow. Cai dat: pip install Pillow")
    sys.exit(1)

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass


IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".webp", ".bmp", ".tif", ".tiff"}
DEFAULT_W = 1080
DEFAULT_H = 1701


def human_size(n):
    if n < 1024:
        return "{} B".format(n)
    if n < 1024 * 1024:
        return "{:.1f} KB".format(n / 1024)
    return "{:.2f} MB".format(n / 1024 / 1024)


def flatten_to_rgb(img, bg=(0, 0, 0)):
    """Chuyen RGBA/P/LA ve RGB, nen alpha len nen den."""
    img = ImageOps.exif_transpose(img)
    if img.mode in ("RGBA", "LA"):
        base = Image.new("RGB", img.size, bg)
        alpha = img.getchannel("A")
        base.paste(img.convert("RGB"), mask=alpha)
        return base
    if img.mode == "P" and "transparency" in img.info:
        img = img.convert("RGBA")
        base = Image.new("RGB", img.size, bg)
        base.paste(img.convert("RGB"), mask=img.getchannel("A"))
        return base
    return img.convert("RGB")


def cover_crop_resize(img, width, height):
    """Resize cover-crop ve dung width x height."""
    img = flatten_to_rgb(img)
    ow, oh = img.size
    if ow == width and oh == height:
        return img

    scale = max(width / ow, height / oh)
    nw = max(1, int(round(ow * scale)))
    nh = max(1, int(round(oh * scale)))

    resample = getattr(Image, "Resampling", Image).LANCZOS
    img = img.resize((nw, nh), resample)

    left = max(0, (nw - width) // 2)
    top = max(0, (nh - height) // 2)
    return img.crop((left, top, left + width, top + height))


def jpeg_bytes(img, quality):
    buf = io.BytesIO()
    img.save(
        buf,
        format="JPEG",
        quality=int(quality),
        optimize=True,
        progressive=True,
        subsampling=2,
    )
    return buf.getvalue()


def png8_bytes(img, colors):
    """PNG palette nen manh, dung khi muon file PNG that."""
    buf = io.BytesIO()
    pal = img.convert("P", palette=Image.Palette.ADAPTIVE, colors=int(colors))
    pal.save(buf, format="PNG", optimize=True, compress_level=9)
    return buf.getvalue()


def downsample_then_upscale(img, factor, width, height):
    """Lam mat chi tiet de file nen nho hon nhung van giu kich thuoc cuoi."""
    if factor >= 0.999:
        return img
    resample = getattr(Image, "Resampling", Image).LANCZOS
    small_w = max(16, int(round(width * factor)))
    small_h = max(16, int(round(height * factor)))
    small = img.resize((small_w, small_h), resample)
    return small.resize((width, height), resample)


def compress_jpeg(img, width, height, max_bytes, min_quality, absolute_min=False):
    """
    Neu co max_bytes: lay ban dau tien <= max_bytes voi chat luong cao nhat co the.
    Neu absolute_min=True: lay file nho nhat tim duoc.
    """
    qualities = list(range(85, min_quality - 1, -5))
    if min_quality not in qualities:
        qualities.append(min_quality)
    qualities = sorted(set(qualities), reverse=True)

    # factor cang nho anh cang nho, nhung cang mo/nat.
    # Khong co target KB: dung muc san 0.48 + q>=25 de van nhin ro.
    # Co target KB: cho phep giam them de co the dat muc KB nguoi dung nhap.
    if max_bytes:
        factors = [
            1.0, 0.92, 0.85, 0.78, 0.70, 0.62, 0.55, 0.48,
            0.40, 0.33, 0.25, 0.20, 0.16,
        ]
    else:
        factors = [1.0, 0.92, 0.85, 0.78, 0.70, 0.62, 0.55, 0.48]

    smallest = None
    chosen = None
    for factor in factors:
        work = downsample_then_upscale(img, factor, width, height)
        for q in qualities:
            data = jpeg_bytes(work, q)
            meta = {"quality": q, "factor": factor, "format": "jpg"}
            if smallest is None or len(data) < len(smallest[0]):
                smallest = (data, meta)

            if max_bytes and len(data) <= max_bytes and not absolute_min:
                chosen = (data, meta)
                return chosen, smallest

    return smallest, smallest


def compress_png8(img, max_bytes, absolute_min=False):
    colors_list = [256, 192, 128, 96, 64, 48, 32, 24, 16, 12, 8, 4]
    smallest = None
    for colors in colors_list:
        data = png8_bytes(img, colors)
        meta = {"colors": colors, "format": "png8"}
        if smallest is None or len(data) < len(smallest[0]):
            smallest = (data, meta)
        if max_bytes and len(data) <= max_bytes and not absolute_min:
            return (data, meta), smallest
    return smallest, smallest


def unique_out_path(out_dir, stem, suffix):
    p = out_dir / (stem + suffix)
    if not p.exists():
        return p
    i = 2
    while True:
        p = out_dir / "{}_{}{}".format(stem, i, suffix)
        if not p.exists():
            return p
        i += 1


def write_replace_original(original_path, data, suffix):
    """
    Ghi anh nen vao ngay vi tri anh goc.
    - JPG/JPEG dau vao: thay noi dung file cu.
    - Dinh dang khac: tao cung ten .jpg/.png moi va xoa file cu.
    """
    original_path = Path(original_path)
    src_suffix = original_path.suffix.lower()

    if suffix.lower() in (".jpg", ".jpeg") and src_suffix in (".jpg", ".jpeg"):
        final_path = original_path
    elif suffix.lower() == ".png" and src_suffix == ".png":
        final_path = original_path
    else:
        final_path = original_path.with_suffix(suffix)
        if final_path.exists() and final_path.resolve() != original_path.resolve():
            final_path = unique_out_path(original_path.parent, original_path.stem + "_lt", suffix)

    tmp_path = original_path.with_name(
        ".{}.__lt_tmp{}".format(original_path.stem, suffix)
    )
    tmp_path.write_bytes(data)

    if final_path.resolve() == original_path.resolve():
        os.replace(str(tmp_path), str(original_path))
    else:
        os.replace(str(tmp_path), str(final_path))
        try:
            original_path.unlink()
        except FileNotFoundError:
            pass

    return final_path


def compress_one(path, out_dir, args):
    original_size = path.stat().st_size
    with Image.open(path) as im:
        original_wh = im.size
        poster = cover_crop_resize(im, args.width, args.height)

    # max_kb <= 0 nghia la MAX-READABLE: nen manh nhung van giu anh de nhin.
    max_bytes = int(args.max_kb * 1024) if args.max_kb > 0 else 0
    absolute_min = args.absolute_min or args.max_kb <= 0
    min_quality = max(25, args.min_quality) if args.max_kb <= 0 else args.min_quality

    if args.format == "png8":
        (data, meta), _ = compress_png8(poster, max_bytes, absolute_min)
        suffix = ".png"
    else:
        (data, meta), _ = compress_jpeg(
            poster,
            args.width,
            args.height,
            max_bytes,
            min_quality,
            absolute_min,
        )
        suffix = ".jpg"

    if getattr(args, "replace_original", False):
        out_path = write_replace_original(path, data, suffix)
        action = "REPLACE"
    else:
        out_path = unique_out_path(out_dir, path.stem + "_lt", suffix)
        out_path.write_bytes(data)
        action = "WRITE"

    ratio = 100.0 * len(data) / max(1, original_size)
    extra = []
    if meta.get("format") == "jpg":
        extra.append("q={}".format(meta["quality"]))
        extra.append("factor={:.2f}".format(meta["factor"]))
    else:
        extra.append("colors={}".format(meta["colors"]))
    if max_bytes:
        extra.append("target={}KB".format(args.max_kb))
        extra.append("OK" if len(data) <= max_bytes else "OVER")
    else:
        extra.append("MAX-READABLE")

    print(
        "{} -> {} | {} | {} {} -> {} | {} ({:.1f}%) | {}".format(
            path.name,
            out_path.name,
            action,
            original_wh,
            human_size(original_size),
            human_size(len(data)),
            "{}x{}".format(args.width, args.height),
            ratio,
            ", ".join(extra),
        )
    )
    return out_path


def collect_files(input_path, output_dir):
    p = Path(input_path)
    if p.is_file():
        return [p]

    out_resolved = output_dir.resolve()
    files = []
    for x in sorted(p.iterdir()):
        if not x.is_file():
            continue
        if x.parent.resolve() == out_resolved:
            continue
        if x.suffix.lower() in IMAGE_EXTS:
            files.append(x)
    return files


def main():
    ap = argparse.ArgumentParser(description="Nen anh cuc manh cho loadtran.py")
    ap.add_argument("--input", "-i", default=".", help="File/thu muc anh dau vao, mac dinh .")
    ap.add_argument("--output", "-o", default="compressed", help="Thu muc xuat, mac dinh compressed")
    ap.add_argument("--width", type=int, default=DEFAULT_W, help="Rong output, mac dinh 1080")
    ap.add_argument("--height", type=int, default=DEFAULT_H, help="Cao output, mac dinh 1701")
    ap.add_argument("--max-kb", type=int, default=100, help="Muc tieu KB, RCM 100KB; 0 = MAX-READABLE")
    ap.add_argument("--min-quality", type=int, default=10, help="Quality JPG thap nhat khi co target KB, mac dinh 10")
    ap.add_argument("--absolute-min", action="store_true", help="Lay file nho nhat tim duoc, chap nhan anh mo/nat hon")
    ap.add_argument("--format", choices=["jpg", "png8"], default="jpg", help="jpg = nho nhat; png8 = PNG that nhung thuong lon hon")
    ap.add_argument("--replace-original", action="store_true", help="Ghi de/thay anh goc bang anh da nen, xoa file goc neu doi duoi")
    args = ap.parse_args()

    out_dir = Path(args.output)
    if not args.replace_original:
        out_dir.mkdir(parents=True, exist_ok=True)

    files = collect_files(args.input, out_dir)
    if not files:
        print("Khong tim thay anh trong:", args.input)
        return 1

    print("Input:", Path(args.input).resolve())
    print("Output:", "replace original" if args.replace_original else out_dir.resolve())
    effective_min_quality = max(25, args.min_quality) if args.max_kb <= 0 else args.min_quality
    print("Mode: {} | size={}x{} | max_kb={} | min_quality={}".format(
        args.format, args.width, args.height, args.max_kb, effective_min_quality
    ))
    print("")

    made = []
    for f in files:
        try:
            made.append(compress_one(f, out_dir, args))
        except Exception as e:
            print("{} -> LOI: {}".format(f.name, e))

    print("")
    print("Xong: {} file".format(len(made)))
    print("Chay loadtran bang thu muc da nen:")
    if args.replace_original:
        run_dir = Path(args.input).parent if Path(args.input).is_file() else Path(args.input)
        print("  python loadtran.py --dir {} --har synthetic_player_poster.har".format(run_dir))
    else:
        print("  python loadtran.py --dir {} --har synthetic_player_poster.har".format(out_dir))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

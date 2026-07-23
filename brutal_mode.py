#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
BRUTAL MODE an toàn dung lượng:
  - Flow batch theo source "auto 2 ảnh đổ lên": tối đa 5 ảnh/batch.
  - Giữ nguyên nhịp nghỉ mặc định 6 giây giữa các lượt gọi loadtran.
  - Nếu có nhiều hơn 1 HAR: cho chọn 1 HAR hoặc toàn bộ HAR.
  - Nếu có nhiều hơn 1 ảnh: cho chọn 1 ảnh hoặc toàn bộ ảnh.
  - Đầu tiên test ảnh gốc.
  - Ảnh gốc fail thì mới tạo các bản nén trong _brutal_work/ và test tiếp.
  - Ảnh nào chạy được -> copy bản chạy được vào anh_OK/.
  - Ảnh đã pass ở mốc nào thì dừng ngay, không nén tiếp mốc thấp hơn.
  - Luôn xóa ảnh/candidate fail, TRỪ ảnh nằm trong thư mục anh_goc/.
  - Ảnh trong anh_goc/ không bị xóa/move; ảnh fail ở ngoài anh_goc/ sẽ bị xóa.

Chạy riêng:
  python brutal_mode.py --har synthetic_player_poster.har
"""

import argparse
import builtins
import contextlib
import hashlib
import io
import json
import os
import re
import shutil
import sys
import time
from pathlib import Path
from types import SimpleNamespace

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass


def enable_windows_ansi():
    if os.name != "nt":
        return
    try:
        import ctypes
        kernel32 = ctypes.windll.kernel32
        for handle_id in (-11, -12):
            handle = kernel32.GetStdHandle(handle_id)
            mode = ctypes.c_uint32()
            if kernel32.GetConsoleMode(handle, ctypes.byref(mode)):
                kernel32.SetConsoleMode(handle, mode.value | 0x0004)
    except Exception:
        pass


enable_windows_ansi()


SOURCE_DIR = "anh_goc"
OK_DIR = "anh_OK"
FAIL_DIR = "anh_FAIL"      # chỉ giữ folder cho tương thích; không đưa ảnh fail vào đây
WORK_DIR = "_brutal_work"
MANIFEST = ".brutal_manifest.json"
MAX_PER_BATCH = 5
SLEEP_BETWEEN_BATCH = 6
MEDIA_EXTS = {".jpg", ".jpeg", ".png", ".webp", ".gif", ".mp4"}
IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".webp", ".bmp", ".tif", ".tiff"}
DEFAULT_TARGETS = [70, 60, 50, 40, 45, 40, 36, 35, 32, 30]


class C:
    RESET = "\033[0m"
    BOLD = "\033[1m"
    RED = "\033[91m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    CYAN = "\033[96m"
    GRAY = "\033[90m"


def color(s, c):
    return c + str(s) + C.RESET


def info(s):
    print(color("> " + str(s), C.CYAN), flush=True)


def ok(s):
    print(color("[OK] " + str(s), C.GREEN), flush=True)


def warn(s):
    print(color("[!] " + str(s), C.YELLOW), flush=True)


def fail(s):
    print(color("[X] " + str(s), C.RED), flush=True)


def header(title):
    print(color("=" * 70, C.CYAN))
    print(color("  " + str(title), C.BOLD + C.CYAN))
    print(color("=" * 70, C.CYAN))


class Tee(io.StringIO):
    def __init__(self, real):
        super().__init__()
        self.real = real

    def write(self, s):
        self.real.write(s)
        self.real.flush()
        return super().write(s)

    def flush(self):
        self.real.flush()
        return super().flush()


def parse_targets(raw):
    if not raw:
        return DEFAULT_TARGETS[:]
    out = []
    for part in str(raw).replace(" ", "").split(","):
        if not part:
            continue
        try:
            n = int(part)
        except ValueError:
            raise SystemExit("Preset KB không hợp lệ: {}".format(part))
        if n < 0:
            raise SystemExit("Preset KB phải >= 0")
        out.append(n)
    return out or DEFAULT_TARGETS[:]


def load_manifest(path=MANIFEST):
    p = Path(path)
    if not p.exists():
        return {}
    try:
        return json.loads(p.read_text(encoding="utf-8", errors="ignore"))
    except Exception:
        return {}


def save_manifest(data, path=MANIFEST):
    Path(path).write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def file_sig(p):
    p = Path(p)
    try:
        st = p.stat()
        return "{}:{}:{}".format(str(p.resolve()).lower(), st.st_size, int(st.st_mtime))
    except Exception:
        return str(p)


def is_done(src, manifest, ok_dir):
    sig = file_sig(src)
    rec = manifest.get(sig)
    if rec and rec.get("status") == "OK" and Path(rec.get("ok_file", "")).exists():
        return True
    # fallback: neu trong OK da co ten file tu source thi skip de tranh chay lai lien tuc
    ok_name = Path(ok_dir) / Path(src).with_suffix(".jpg").name
    return ok_name.exists()


def discover_originals(source_dir=SOURCE_DIR, include_root=True, ok_dir=OK_DIR):
    """Lay danh sach anh goc, KHONG move/xoa anh goc."""
    Path(source_dir).mkdir(exist_ok=True)
    Path(ok_dir).mkdir(exist_ok=True)
    originals = []
    seen = set()

    roots = [Path(source_dir)]
    if include_root:
        roots.append(Path("."))

    ignored_dirs = {
        Path(source_dir).resolve(),
        Path(ok_dir).resolve(),
        Path(FAIL_DIR).resolve(),
        Path(WORK_DIR).resolve(),
        Path("compressed").resolve(),
    }

    for root in roots:
        if not root.exists() or not root.is_dir():
            continue
        for f in sorted(root.iterdir()):
            if not f.is_file() or f.suffix.lower() not in MEDIA_EXTS:
                continue
            if f.parent.resolve() in ignored_dirs and root == Path("."):
                continue
            try:
                key = str(f.resolve()).lower()
            except Exception:
                key = str(f).lower()
            if key in seen:
                continue
            seen.add(key)
            originals.append(f)
    return originals


def safe_unlink(p):
    try:
        Path(p).unlink()
        return True
    except FileNotFoundError:
        return True
    except Exception as e:
        warn("Không xóa được {}: {}".format(Path(p).name, e))
        return False


def safe_rmtree(p):
    p = Path(p)
    if not p.exists():
        return True
    try:
        shutil.rmtree(p)
        return True
    except Exception as e:
        warn("Không xóa được folder {}: {}".format(p, e))
        return False


def path_in_dir(path, folder):
    """True nếu path nằm trong folder (dùng để bảo vệ anh_goc/)."""
    try:
        p = Path(path).resolve()
        root = Path(folder).resolve()
        return p == root or root in p.parents
    except Exception:
        return False


def is_protected_source_file(path, source_dir=SOURCE_DIR):
    """Ảnh trong thư mục anh_goc là bản gốc được giữ lại kể cả khi fail."""
    p = Path(path)
    return p.exists() and p.is_file() and path_in_dir(p, source_dir)


def delete_failed_media(path, source_dir=SOURCE_DIR, reason="FAIL"):
    """Xóa file fail, ngoại trừ file nằm trong thư mục anh_goc/."""
    p = Path(path)
    if is_protected_source_file(p, source_dir):
        warn("{} fail nhưng nằm trong {} -> giữ nguyên".format(p.name, source_dir))
        return False
    if p.exists() and p.is_file():
        deleted = safe_unlink(p)
        if deleted:
            warn("{} {} -> đã xóa file fail".format(p.name, reason))
        return deleted
    return True


def ensure_dirs(*dirs):
    for d in dirs:
        Path(d).mkdir(parents=True, exist_ok=True)


def unique_path(folder, name):
    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=True)
    p = folder / name
    if not p.exists():
        return p
    stem, suffix = p.stem, p.suffix
    i = 2
    while True:
        q = folder / "{}_{}{}".format(stem, i, suffix)
        if not q.exists():
            return q
        i += 1


def safe_stem(name):
    text = re.sub(r'[<>:"/\\|?*\x00-\x1f]+', "_", str(name))
    text = re.sub(r"\s+", "_", text).strip("._ ")
    return text[:80] or "img"


def source_hash(src):
    return hashlib.sha1(file_sig(src).encode("utf-8", errors="ignore")).hexdigest()[:12]


def candidate_dir_for(src, work_dir=WORK_DIR):
    src = Path(src)
    return Path(work_dir) / "{}__{}".format(safe_stem(src.stem), source_hash(src))


def compress_variant(src, target_kb, work_dir=WORK_DIR):
    """Tạo 1 bản nén từ ảnh gốc vào folder tạm. Ảnh gốc không bị sửa/xóa."""
    import compress_for_loadtran as cf

    src = Path(src)
    folder = candidate_dir_for(src, work_dir)
    folder.mkdir(parents=True, exist_ok=True)

    if src.suffix.lower() not in IMAGE_EXTS:
        # GIF/MP4: copy lam candidate raw, khong sua original
        dest = unique_path(folder, src.name)
        shutil.copy2(src, dest)
        return dest

    label = "max" if int(target_kb) <= 0 else "kb{}".format(int(target_kb))
    args = SimpleNamespace(
        width=1080,
        height=1701,
        max_kb=int(target_kb),
        min_quality=10,
        absolute_min=False,
        format="jpg",
        replace_original=False,
    )
    tmp = cf.compress_one(src, folder, args)
    dest = folder / "{}__{}.jpg".format(safe_stem(src.stem), label)
    if tmp.resolve() != dest.resolve():
        safe_unlink(dest)
        os.replace(str(tmp), str(dest))
    return dest


def parse_sanitize_boxes(raw):
    """
    Parse vùng che dạng:
      "x1,y1,x2,y2;x1,y1,x2,y2"
    Nếu giá trị <= 1 thì hiểu là tỉ lệ theo ảnh, nếu > 1 thì hiểu là pixel.
    """
    if not raw:
        return None
    boxes = []
    for chunk in str(raw).replace("|", ";").split(";"):
        chunk = chunk.strip()
        if not chunk:
            continue
        parts = [p.strip() for p in chunk.split(",")]
        if len(parts) != 4:
            raise SystemExit("Vùng sanitize không hợp lệ: {}".format(chunk))
        try:
            boxes.append(tuple(float(x) for x in parts))
        except ValueError:
            raise SystemExit("Vùng sanitize không hợp lệ: {}".format(chunk))
    return boxes or None


def _box_to_pixels(box, width, height):
    vals = list(box)
    if all(0 <= v <= 1 for v in vals):
        x1, y1, x2, y2 = (
            int(round(vals[0] * width)),
            int(round(vals[1] * height)),
            int(round(vals[2] * width)),
            int(round(vals[3] * height)),
        )
    else:
        x1, y1, x2, y2 = (int(round(v)) for v in vals)
    x1 = max(0, min(width - 1, x1))
    y1 = max(0, min(height - 1, y1))
    x2 = max(x1 + 1, min(width, x2))
    y2 = max(y1 + 1, min(height, y2))
    return x1, y1, x2, y2


def normalize_sanitize_style(raw=None):
    """Chỉ giữ 2 kiểu sanitize đang dùng: stripes và stripes_light."""
    text = (str(raw or "stripes_light").strip().lower()
            .replace(" ", "-").replace("_", "-"))
    if text in ("1", "stripes", "stripe", "line", "lines", "gach", "gạch", "gach-trang", "gạch-trắng", "trang", "trắng"):
        return "stripes"
    if text in ("2", "stripes-light", "stripe-light", "light", "lighter", "mo", "mờ", "gach-mo", "gạch-mờ", "trang-mo", "trắng-mờ"):
        return "stripes_light"
    warn("Kiểu sanitize không rõ '{}', dùng gạch trắng mờ.".format(raw))
    return "stripes_light"


def sanitize_variant(src, work_dir=WORK_DIR, boxes=None, crop_margin=0.035, sanitize_style="stripes_light"):
    """
    Tạo bản đã sanitize vào thư mục tạm, không sửa ảnh gốc.

    Việc xử lý gồm:
      - đọc lại ảnh, xuất PNG sạch metadata;
      - cover-resize về đúng 1080x1701;
      - phủ gạch trắng toàn ảnh.
    Chỉ còn 2 kiểu:
      - stripes: gạch trắng rõ;
      - stripes_light: gạch trắng mờ hơn để nhìn rõ ảnh hơn.
    """
    try:
        from PIL import Image, ImageDraw, ImageOps
    except ImportError:
        raise SystemExit("Thiếu Pillow. Cài đặt: pip install Pillow")

    src = Path(src)
    folder = candidate_dir_for(src, work_dir)
    folder.mkdir(parents=True, exist_ok=True)

    if src.suffix.lower() not in IMAGE_EXTS:
        dest = unique_path(folder, "{}__sanitize_raw{}".format(safe_stem(src.stem), src.suffix.lower()))
        shutil.copy2(src, dest)
        return dest

    sanitize_style = normalize_sanitize_style(sanitize_style)

    with Image.open(src) as im:
        im = ImageOps.exif_transpose(im)
        if im.mode in ("RGBA", "LA"):
            base = Image.new("RGB", im.size, (10, 10, 10))
            base.paste(im.convert("RGB"), mask=im.getchannel("A"))
            im = base
        elif im.mode == "P" and "transparency" in im.info:
            im = im.convert("RGBA")
            base = Image.new("RGB", im.size, (10, 10, 10))
            base.paste(im.convert("RGB"), mask=im.getchannel("A"))
            im = base
        else:
            im = im.convert("RGB")

        # Không crop ở style gạch: giữ bố cục ảnh gốc.
        ow, oh = im.size
        target_w, target_h = 1080, 1701
        ow, oh = im.size
        scale = max(target_w / ow, target_h / oh)
        nw = max(1, int(round(ow * scale)))
        nh = max(1, int(round(oh * scale)))
        resample = getattr(getattr(Image, "Resampling", Image), "LANCZOS", 1)
        im = im.resize((nw, nh), resample)
        left = max(0, (nw - target_w) // 2)
        top = max(0, (nh - target_h) // 2)
        im = im.crop((left, top, left + target_w, top + target_h))

    if sanitize_style in ("stripes", "stripes_light"):
        # Chỉ phủ gạch trắng toàn ảnh, không kính mờ, không blur, không ô che.
        # stripes_light dùng alpha thấp hơn để nhìn rõ ảnh hơn.
        im_rgba = im.convert("RGBA")
        overlay = Image.new("RGBA", im_rgba.size, (0, 0, 0, 0))
        draw = ImageDraw.Draw(overlay, "RGBA")
        step = 38   # tỉ lệ giống pattern trong ảnh mẫu
        width = 2
        alpha = 205 if sanitize_style == "stripes" else 95
        for x in range(-target_h, target_w + target_h + step, step):
            draw.line((x, target_h, x + target_h, 0), fill=(255, 255, 255, alpha), width=width)
        im_rgba = Image.alpha_composite(im_rgba, overlay)
        dest = unique_path(folder, "{}__{}.png".format(safe_stem(src.stem), sanitize_style))
        im_rgba.convert("RGB").save(dest, format="PNG", optimize=True, compress_level=9)
        return dest


def cleanup_source_candidates(src, work_dir=WORK_DIR):
    safe_rmtree(candidate_dir_for(src, work_dir))


def patch_loadtran_auto_inputs(loadtran):
    old_input = getattr(loadtran, "input", builtins.input)
    old_cinput = getattr(loadtran, "cinput", None)
    old_ask_choice = getattr(loadtran, "ask_choice", None)

    def auto_input(prompt=""):
        p = str(prompt).lower()
        if "ok" in p:
            ans = "ok"
        elif "vòng" in p or "vong" in p:
            ans = ""
        else:
            ans = ""
        print("-> Auto: {}".format(ans))
        return ans

    def auto_ask_choice(prompt, options):
        p = str(prompt).lower()
        if "chức năng" in p or "chuc nang" in p:
            ans = "1"
        elif "phân công" in p or "phan cong" in p:
            ans = "2"
        elif "lưu" in p or "luu" in p:
            ans = "1"
        else:
            ans = sorted(options.keys())[0]
        print("-> Auto: {}".format(ans))
        return ans

    loadtran.input = auto_input
    if hasattr(loadtran, "cinput"):
        loadtran.cinput = auto_input
    if hasattr(loadtran, "ask_choice"):
        loadtran.ask_choice = auto_ask_choice

    def restore():
        loadtran.input = old_input
        if old_cinput is not None:
            loadtran.cinput = old_cinput
        if old_ask_choice is not None:
            loadtran.ask_choice = old_ask_choice

    return restore


class BatchRunner:
    """Gọi loadtran theo batch và giữ nguyên nhịp nghỉ giữa các batch."""

    def __init__(self, har, sleep_between_batch=SLEEP_BETWEEN_BATCH, har_label=None):
        self.har = har
        self.har_label = har_label or ("Tất cả HAR" if har is None else Path(har).name)
        self.sleep_between_batch = sleep_between_batch
        self.ran = 0

    def run(self, media_files):
        if self.ran and self.sleep_between_batch:
            info("Nghỉ {}s trước batch tiếp theo...".format(self.sleep_between_batch))
            time.sleep(self.sleep_between_batch)
        self.ran += 1
        info("Gọi LoadTran với {}.".format(self.har_label))
        return run_loadtran_batch(self.har, media_files)


def success_from_return(result, count):
    success = set()
    if not isinstance(result, dict):
        return success
    for acc_data in result.values():
        if not isinstance(acc_data, dict):
            continue
        for _rnd, res_list in acc_data.get("rounds") or []:
            for idx, res in enumerate(res_list[:count], 1):
                if res and res[0]:
                    success.add(idx)
    return success


def success_from_log(text):
    clean = re.sub(r"\x1b\[[0-9;]*m", "", text or "")
    success = set()
    for m in re.findall(r"V\d+#(\d+)\s+.*?OK", clean, re.IGNORECASE):
        try:
            success.add(int(m))
        except Exception:
            pass
    return success


def run_loadtran_batch(har, media_files):
    import loadtran

    media_files = [Path(p) for p in media_files]
    if not media_files:
        return set()

    restore = patch_loadtran_auto_inputs(loadtran)
    output = Tee(sys.stdout)
    result = None
    try:
        with contextlib.redirect_stdout(output):
            har_arg = None if har is None else str(Path(har).resolve())
            result = loadtran.run(har_arg, ".", 1, False, [str(p) for p in media_files])
    except SystemExit as e:
        print(color("loadtran dừng sớm/SystemExit: {}".format(e), C.YELLOW))
    except Exception as e:
        print(color("Lỗi nghiêm trọng loadtran: {}".format(e), C.RED))
    finally:
        restore()
        try:
            loadtran.stop_sign_bridge()
        except Exception:
            pass

    success = success_from_return(result, len(media_files))
    if not success:
        success = success_from_log(output.getvalue())
    return success


def copy_success_file(src_file, original_src, ok_dir, label):
    src_file = Path(src_file)
    original_src = Path(original_src)
    if src_file.suffix.lower() in (".jpg", ".jpeg"):
        dest_name = original_src.with_suffix(".jpg").name
    else:
        # PNG/WEBP/GIF/MP4/sanitize thành công: giữ đúng đuôi theo nội dung file.
        dest_name = original_src.with_suffix(src_file.suffix.lower()).name
    dest = unique_path(ok_dir, dest_name)
    shutil.copy2(src_file, dest)
    ok("{} đạt {} -> {}".format(original_src.name, label, dest))
    return dest


def human_size(n):
    try:
        n = int(n)
    except Exception:
        return "?"
    if n < 1024:
        return "{} B".format(n)
    if n < 1024 * 1024:
        return "{:.1f} KB".format(n / 1024)
    return "{:.2f} MB".format(n / 1024 / 1024)


def discover_har_files(directory="."):
    return sorted(
        p for p in Path(directory).glob("*.har")
        if p.is_file() and ".bak" not in p.name.lower()
    )


def ask_raw(prompt, default=""):
    try:
        ans = builtins.input(color(prompt, C.YELLOW)).strip()
        return ans if ans else default
    except EOFError:
        return default


def ask_index(files, prompt="Chọn số thứ tự", default=1):
    while True:
        raw = ask_raw("{} [ENTER={}]: ".format(prompt, default), str(default))
        if raw.isdigit() and 1 <= int(raw) <= len(files):
            return int(raw) - 1
        warn("Nhập số từ 1 đến {}.".format(len(files)))


def resolve_har_choice(har=None, all_har=False, interactive=True):
    """Trả về (har_arg, label). har_arg=None nghĩa là dùng toàn bộ HAR trong thư mục."""
    if har:
        raw = str(har).strip()
        if raw.lower() in ("all", "*", "tatca", "tấtcả", "all-har"):
            files = discover_har_files(".")
            if not files:
                return None, None
            return None, "Tất cả HAR ({} file)".format(len(files))
        p = Path(raw)
        if not p.exists():
            return None, None
        return p.resolve(), p.name

    files = discover_har_files(".")
    if not files:
        return None, None
    if len(files) == 1:
        ok("Tìm thấy 1 HAR: {}".format(files[0].name))
        return files[0].resolve(), files[0].name
    if all_har or not interactive:
        ok("Dùng toàn bộ {} file HAR.".format(len(files)))
        return None, "Tất cả HAR ({} file)".format(len(files))

    print("")
    info("Có {} file HAR:".format(len(files)))
    for i, f in enumerate(files, 1):
        print("  [{}] {}  {}".format(i, color(f.name, C.CYAN), color(human_size(f.stat().st_size), C.GRAY)))
    mode = ask_raw("Chọn HAR: [1] chỉ 1 file, [2] toàn bộ file HAR (ENTER=2): ", "2")
    if mode == "1":
        idx = ask_index(files, "Chọn file HAR", 1)
        return files[idx].resolve(), files[idx].name
    return None, "Tất cả HAR ({} file)".format(len(files))


def choose_pending_images(pending, selected_image=None, all_images=False, interactive=True):
    """Nếu nhiều ảnh thì cho chọn 1 ảnh hoặc toàn bộ ảnh."""
    pending = list(pending)
    if selected_image:
        raw = str(selected_image).strip()
        rp = None
        try:
            rp = Path(raw).resolve()
        except Exception:
            pass
        matches = []
        for p in pending:
            try:
                if rp and p.resolve() == rp:
                    matches.append(p)
                    continue
            except Exception:
                pass
            if p.name.lower() == raw.lower():
                matches.append(p)
        if matches:
            ok("Đã chọn ảnh: {}".format(matches[0].name))
            return [matches[0]]
        warn("Không tìm thấy ảnh đã chỉ định: {}".format(raw))
        return []

    if len(pending) <= 1 or all_images or not interactive:
        if len(pending) > 1:
            ok("Dùng toàn bộ {} ảnh.".format(len(pending)))
        return pending

    print("")
    info("Có {} ảnh đang chờ xử lý:".format(len(pending)))
    for i, f in enumerate(pending, 1):
        size = human_size(f.stat().st_size) if f.exists() else "?"
        print("  [{}] {}  {}".format(i, color(str(f), C.CYAN), color(size, C.GRAY)))
    mode = ask_raw("Chọn ảnh: [1] chỉ 1 ảnh, [2] toàn bộ ảnh (ENTER=2): ", "2")
    if mode == "1":
        idx = ask_index(pending, "Chọn ảnh", 1)
        return [pending[idx]]
    return pending


def find_first_har():
    files = discover_har_files(".")
    return str(files[0]) if files else None


def run_brutal(
    har=None,
    source_dir=SOURCE_DIR,
    ok_dir=OK_DIR,
    fail_dir=FAIL_DIR,
    work_dir=WORK_DIR,
    batch_size=MAX_PER_BATCH,
    sleep_between_batch=SLEEP_BETWEEN_BATCH,
    targets=None,
    include_root=True,
    rerun_all=False,
    all_har=False,
    selected_image=None,
    all_images=False,
    interactive_select=True,
):
    targets = targets or DEFAULT_TARGETS[:]
    batch_size = max(1, min(5, int(batch_size or MAX_PER_BATCH)))
    ensure_dirs(source_dir, ok_dir, fail_dir, work_dir)

    har_arg, har_label = resolve_har_choice(
        har=har,
        all_har=all_har,
        interactive=interactive_select,
    )
    if not har_label:
        fail("Không tìm thấy file .har!")
        return {"ok": 0, "fail": 0, "skipped": 0}

    manifest = load_manifest()

    header("BRUTAL MODE - TEST GỐC RỒI NÉN")
    print("HAR       :", color(har_label, C.GREEN))
    print("Ảnh gốc   :", color("{} + thư mục chạy".format(source_dir) if include_root else source_dir, C.CYAN))
    print("Ảnh OK    :", color(ok_dir, C.CYAN))
    print("Tạm       :", color(work_dir, C.CYAN))
    print("Batch     :", color(batch_size, C.CYAN))
    print("Preset KB :", color(",".join(map(str, targets)), C.CYAN))
    print("Delay     :", color("{}s giữa các batch".format(sleep_between_batch), C.CYAN))
    print("Fail      :", color("xóa file fail, trừ file nằm trong {}".format(source_dir), C.YELLOW))
    print("")

    originals = discover_originals(source_dir, include_root=include_root, ok_dir=ok_dir)
    if not originals:
        warn("Không thấy ảnh. Hãy bỏ ảnh ngang hàng run_combo.bat hoặc vào {}".format(source_dir))
        return {"ok": 0, "fail": 0, "skipped": 0}

    pending = []
    skipped = 0
    for src in originals:
        if not rerun_all and is_done(src, manifest, ok_dir):
            skipped += 1
            continue
        pending.append(src)

    if not pending:
        ok("Tất cả ảnh đã có trong anh_OK hoặc manifest. Không cần chạy lại.")
        return {"ok": 0, "fail": 0, "skipped": skipped}

    pending = choose_pending_images(
        pending,
        selected_image=selected_image,
        all_images=all_images,
        interactive=interactive_select,
    )
    if not pending:
        warn("Không còn ảnh nào sau bước chọn ảnh.")
        return {"ok": 0, "fail": 0, "skipped": skipped}

    total_ok = 0
    total_fail = 0
    total_fail_kept = 0
    total_fail_deleted = 0
    source_deleted_after_ok = 0
    candidate_deleted = 0
    runner = BatchRunner(har_arg, sleep_between_batch, har_label)

    # 1) Test ảnh gốc trước, không sửa/xóa/move ảnh gốc.
    header("PASS ẢNH GỐC - {} ảnh".format(len(pending)))
    failed_originals = []
    for start in range(0, len(pending), batch_size):
        batch = pending[start:start + batch_size]
        info("Batch ảnh gốc {} ảnh".format(len(batch)))
        for i, f in enumerate(batch, 1):
            print("  [{}] {}".format(i, f))
        success_idx = runner.run(batch)
        for i, src in enumerate(batch, 1):
            if i in success_idx:
                dest = copy_success_file(src, src, ok_dir, "ẢNH GỐC")
                manifest[file_sig(src)] = {"status": "OK", "ok_file": str(dest), "source": str(src), "mode": "original"}
                total_ok += 1
                ok("{} đã pass ảnh gốc -> không nén ảnh này".format(src.name))
            else:
                failed_originals.append(src)
                warn("{} fail ảnh gốc -> sẽ tạo bản nén để test".format(src.name))
        save_manifest(manifest)

    # 2) Chỉ ảnh gốc fail mới được nén và test variant.
    still_pending = failed_originals[:]
    for target in targets:
        if not still_pending:
            break
        mode = "MAX-READABLE" if int(target) <= 0 else "{}KB".format(target)
        header("PASS BẢN NÉN {} - {} ảnh".format(mode, len(still_pending)))
        next_pending = []

        # Tạo variant sau khi ảnh gốc fail, rồi test theo batch.
        candidates = []
        cand_to_src = []
        for src in still_pending:
            try:
                cand = compress_variant(src, target, work_dir)
                candidates.append(cand)
                cand_to_src.append(src)
                print("  {} -> {}".format(src.name, cand.name))
            except Exception as e:
                fail("Nén lỗi {}: {}".format(src.name, e))
                next_pending.append(src)

        for start in range(0, len(candidates), batch_size):
            batch_cands = candidates[start:start + batch_size]
            batch_srcs = cand_to_src[start:start + batch_size]
            success_idx = runner.run(batch_cands)

            for i, cand in enumerate(batch_cands, 1):
                src = batch_srcs[i - 1]
                if i in success_idx:
                    dest = copy_success_file(cand, src, ok_dir, mode)
                    manifest[file_sig(src)] = {"status": "OK", "ok_file": str(dest), "source": str(src), "mode": mode}
                    total_ok += 1
                    ok("{} đã pass ở mốc {} -> dừng nén các mốc thấp hơn cho ảnh này".format(src.name, mode))
                    cleanup_source_candidates(src, work_dir)
                    if not is_protected_source_file(src, source_dir):
                        if delete_failed_media(src, source_dir, "ảnh gốc fail, đã có bản OK"):
                            source_deleted_after_ok += 1
                else:
                    if delete_failed_media(cand, source_dir, "{} fail".format(mode)):
                        candidate_deleted += 1
                    next_pending.append(src)
                    warn("{} fail {} -> thử preset tiếp".format(src.name, mode))
            save_manifest(manifest)

        # Xóa trùng nhưng giữ thứ tự
        dedup = []
        seen = set()
        for src in next_pending:
            k = file_sig(src)
            if k not in seen and not is_done(src, manifest, ok_dir):
                seen.add(k)
                dedup.append(src)
        still_pending = dedup

    if still_pending:
        header("FAIL CUỐI - XÓA NGOÀI ANH_GOC")
        for src in still_pending:
            total_fail += 1
            src_sig = file_sig(src)
            cleanup_source_candidates(src, work_dir)
            protected = is_protected_source_file(src, source_dir)
            if protected:
                total_fail_kept += 1
                manifest[src_sig] = {"status": "FAIL", "source": str(src), "kept": True}
                fail("{} FAIL hết preset -> nằm trong {} nên giữ nguyên".format(src.name, source_dir))
            else:
                deleted = delete_failed_media(src, source_dir, "FAIL hết preset")
                if deleted:
                    total_fail_deleted += 1
                manifest[src_sig] = {"status": "FAIL", "source": str(src), "deleted": bool(deleted)}
                fail("{} FAIL hết preset -> đã xóa nếu file còn tồn tại".format(src.name))
        save_manifest(manifest)

    header("BRUTAL HOÀN TẤT")
    print("{:<26}: {}".format("OK", color(total_ok, C.GREEN)))
    print("{:<26}: {}".format("FAIL cuối", color(total_fail, C.RED)))
    print("{:<26}: {}".format("  giữ trong " + source_dir, color(total_fail_kept, C.YELLOW)))
    print("{:<26}: {}".format("  đã xóa ngoài " + source_dir, color(total_fail_deleted, C.RED)))
    print("{:<26}: {}".format("SKIP", color(skipped, C.GRAY)))
    print("{:<26}: {}".format("Source fail đã xóa sau OK", color(source_deleted_after_ok, C.YELLOW)))
    print("{:<26}: {}".format("Candidate fail đã xóa", color(candidate_deleted, C.YELLOW)))
    print("{:<26}: {}".format("Ảnh OK", color(ok_dir, C.CYAN)))
    print("{:<26}: {}".format("Thư mục tạm", color(work_dir + " đã dọn theo từng ảnh", C.CYAN)))
    return {
        "ok": total_ok,
        "fail": total_fail,
        "fail_kept": total_fail_kept,
        "fail_deleted": total_fail_deleted,
        "source_deleted_after_ok": source_deleted_after_ok,
        "candidate_deleted": candidate_deleted,
        "skipped": skipped,
    }


def run_filter_images(
    har=None,
    source_dir=SOURCE_DIR,
    ok_dir=OK_DIR,
    fail_dir=FAIL_DIR,
    work_dir=WORK_DIR,
    batch_size=MAX_PER_BATCH,
    sleep_between_batch=SLEEP_BETWEEN_BATCH,
    include_root=True,
    rerun_all=False,
    all_har=False,
    selected_image=None,
    all_images=False,
    interactive_select=True,
):
    """Lọc ảnh: chạy ảnh gốc thẳng qua LoadTran, không nén."""
    batch_size = max(1, min(5, int(batch_size or MAX_PER_BATCH)))
    ensure_dirs(source_dir, ok_dir, fail_dir, work_dir)

    har_arg, har_label = resolve_har_choice(
        har=har,
        all_har=all_har,
        interactive=interactive_select,
    )
    if not har_label:
        fail("Không tìm thấy file .har!")
        return {"ok": 0, "fail": 0, "skipped": 0}

    manifest = load_manifest()

    header("LỌC ẢNH - CHẠY GỐC KHÔNG NÉN")
    print("HAR       :", color(har_label, C.GREEN))
    print("Ảnh gốc   :", color("{} + thư mục chạy".format(source_dir) if include_root else source_dir, C.CYAN))
    print("Ảnh OK    :", color(ok_dir, C.CYAN))
    print("Batch     :", color(batch_size, C.CYAN))
    print("Delay     :", color("{}s giữa các batch".format(sleep_between_batch), C.CYAN))
    print("Fail      :", color("xóa file fail, trừ file nằm trong {}".format(source_dir), C.YELLOW))
    print("Nén       :", color("KHÔNG nén, chạy thẳng ảnh gốc", C.YELLOW))
    print("")

    originals = discover_originals(source_dir, include_root=include_root, ok_dir=ok_dir)
    if not originals:
        warn("Không thấy ảnh. Hãy bỏ ảnh ngang hàng run_combo.bat hoặc vào {}".format(source_dir))
        return {"ok": 0, "fail": 0, "skipped": 0}

    pending = []
    skipped = 0
    for src in originals:
        if not rerun_all and is_done(src, manifest, ok_dir):
            skipped += 1
            continue
        pending.append(src)

    if not pending:
        ok("Tất cả ảnh đã có trong anh_OK hoặc manifest. Không cần chạy lại.")
        return {"ok": 0, "fail": 0, "skipped": skipped}

    pending = choose_pending_images(
        pending,
        selected_image=selected_image,
        all_images=all_images,
        interactive=interactive_select,
    )
    if not pending:
        warn("Không còn ảnh nào sau bước chọn ảnh.")
        return {"ok": 0, "fail": 0, "skipped": skipped}

    runner = BatchRunner(har_arg, sleep_between_batch, har_label)
    total_ok = 0
    total_fail = 0
    total_fail_kept = 0
    total_fail_deleted = 0

    for start in range(0, len(pending), batch_size):
        batch = pending[start:start + batch_size]
        info("Batch lọc ảnh {} ảnh".format(len(batch)))
        for i, f in enumerate(batch, 1):
            print("  [{}] {}".format(i, f))
        success_idx = runner.run(batch)
        for i, src in enumerate(batch, 1):
            src_sig = file_sig(src)
            if i in success_idx:
                dest = copy_success_file(src, src, ok_dir, "LỌC ẢNH")
                manifest[src_sig] = {"status": "OK", "ok_file": str(dest), "source": str(src), "mode": "filter-original"}
                total_ok += 1
                ok("{} pass lọc ảnh -> không nén".format(src.name))
            else:
                total_fail += 1
                protected = is_protected_source_file(src, source_dir)
                if protected:
                    total_fail_kept += 1
                    manifest[src_sig] = {"status": "FAIL", "source": str(src), "mode": "filter-original", "kept": True}
                    fail("{} fail lọc ảnh -> nằm trong {} nên giữ nguyên".format(src.name, source_dir))
                else:
                    deleted = delete_failed_media(src, source_dir, "fail lọc ảnh")
                    if deleted:
                        total_fail_deleted += 1
                    manifest[src_sig] = {"status": "FAIL", "source": str(src), "mode": "filter-original", "deleted": bool(deleted)}
                    fail("{} fail lọc ảnh -> đã xóa nếu file còn tồn tại".format(src.name))
        save_manifest(manifest)

    header("LỌC ẢNH HOÀN TẤT")
    print("{:<26}: {}".format("OK", color(total_ok, C.GREEN)))
    print("{:<26}: {}".format("FAIL", color(total_fail, C.RED)))
    print("{:<26}: {}".format("  giữ trong " + source_dir, color(total_fail_kept, C.YELLOW)))
    print("{:<26}: {}".format("  đã xóa ngoài " + source_dir, color(total_fail_deleted, C.RED)))
    print("{:<26}: {}".format("SKIP", color(skipped, C.GRAY)))
    print("{:<26}: {}".format("Ảnh OK", color(ok_dir, C.CYAN)))
    return {
        "ok": total_ok,
        "fail": total_fail,
        "fail_kept": total_fail_kept,
        "fail_deleted": total_fail_deleted,
        "skipped": skipped,
    }



def compress_sanitize_variant(src, target_kb, work_dir=WORK_DIR, sanitize_style="stripes_light"):
    """Tạo bản sanitize rồi nén PNG8 theo KB vào thư mục tạm."""
    import compress_for_loadtran as cf

    src = Path(src)
    style = normalize_sanitize_style(sanitize_style)
    folder = candidate_dir_for(src, work_dir)
    folder.mkdir(parents=True, exist_ok=True)

    sanitized = sanitize_variant(src, work_dir=work_dir, sanitize_style=style)
    if src.suffix.lower() not in IMAGE_EXTS:
        return sanitized

    label = "max" if int(target_kb) <= 0 else "kb{}".format(int(target_kb))
    args = SimpleNamespace(
        width=1080,
        height=1701,
        max_kb=int(target_kb),
        min_quality=10,
        absolute_min=False,
        format="png8",
        replace_original=False,
    )
    tmp = cf.compress_one(Path(sanitized), folder, args)
    dest = folder / "{}__{}__{}.png".format(safe_stem(src.stem), style, label)
    if Path(tmp).resolve() != dest.resolve():
        safe_unlink(dest)
        os.replace(str(tmp), str(dest))
    try:
        if Path(sanitized).resolve() != dest.resolve():
            safe_unlink(sanitized)
    except Exception:
        pass
    return dest


def _run_generated_load_mode(
    mode_title,
    manifest_mode,
    candidate_label,
    candidate_builder,
    har=None,
    source_dir=SOURCE_DIR,
    ok_dir=OK_DIR,
    fail_dir=FAIL_DIR,
    work_dir=WORK_DIR,
    batch_size=MAX_PER_BATCH,
    sleep_between_batch=SLEEP_BETWEEN_BATCH,
    include_root=True,
    rerun_all=False,
    all_har=False,
    selected_image=None,
    all_images=False,
    interactive_select=True,
    sanitize_style="stripes_light",
    target_kb=None,
):
    """Chạy các mode tạo candidate trước rồi load theo batch."""
    batch_size = max(1, min(5, int(batch_size or MAX_PER_BATCH)))
    ensure_dirs(source_dir, ok_dir, fail_dir, work_dir)
    style = normalize_sanitize_style(sanitize_style)

    har_arg, har_label = resolve_har_choice(
        har=har,
        all_har=all_har,
        interactive=interactive_select,
    )
    if not har_label:
        fail("Không tìm thấy file .har!")
        return {"ok": 0, "fail": 0, "skipped": 0}

    manifest = load_manifest()

    header(mode_title)
    print("HAR       :", color(har_label, C.GREEN))
    print("Ảnh gốc   :", color("{} + thư mục chạy".format(source_dir) if include_root else source_dir, C.CYAN))
    print("Ảnh OK    :", color(ok_dir, C.CYAN))
    print("Tạm       :", color(work_dir, C.CYAN))
    print("Batch     :", color(batch_size, C.CYAN))
    print("Delay     :", color("{}s giữa các batch".format(sleep_between_batch), C.CYAN))
    print("Style     :", color(style, C.CYAN))
    if target_kb is not None:
        mode_txt = "MAX-READABLE" if int(target_kb) <= 0 else "{}KB".format(int(target_kb))
        print("Nén       :", color(mode_txt + " sau sanitize", C.CYAN))
    print("Fail      :", color("xóa candidate/source fail, trừ file nằm trong {}".format(source_dir), C.YELLOW))
    print("")

    originals = discover_originals(source_dir, include_root=include_root, ok_dir=ok_dir)
    if not originals:
        warn("Không thấy ảnh. Hãy bỏ ảnh ngang hàng run_combo.bat hoặc vào {}".format(source_dir))
        return {"ok": 0, "fail": 0, "skipped": 0}

    pending = []
    skipped = 0
    for src in originals:
        if not rerun_all and is_done(src, manifest, ok_dir):
            skipped += 1
            continue
        pending.append(src)

    if not pending:
        ok("Tất cả ảnh đã có trong anh_OK hoặc manifest. Không cần chạy lại.")
        return {"ok": 0, "fail": 0, "skipped": skipped}

    pending = choose_pending_images(
        pending,
        selected_image=selected_image,
        all_images=all_images,
        interactive=interactive_select,
    )
    if not pending:
        warn("Không còn ảnh nào sau bước chọn ảnh.")
        return {"ok": 0, "fail": 0, "skipped": skipped}

    runner = BatchRunner(har_arg, sleep_between_batch, har_label)
    total_ok = 0
    total_fail = 0
    total_fail_kept = 0
    total_fail_deleted = 0
    candidate_deleted = 0
    build_error = 0

    for start_i in range(0, len(pending), batch_size):
        src_batch = pending[start_i:start_i + batch_size]
        header("TẠO CANDIDATE - {} ảnh".format(len(src_batch)))
        candidates = []
        cand_to_src = []
        build_failed_srcs = []
        for src in src_batch:
            try:
                cand = candidate_builder(src, style)
                candidates.append(cand)
                cand_to_src.append(src)
                size_txt = human_size(cand.stat().st_size) if Path(cand).exists() else "?"
                print("  {} -> {} ({})".format(src.name, Path(cand).name, size_txt))
            except Exception as e:
                build_error += 1
                build_failed_srcs.append(src)
                fail("Tạo candidate lỗi {}: {}".format(src.name, e))

        if candidates:
            info("Batch load {} candidate".format(len(candidates)))
            success_idx = runner.run(candidates)
        else:
            success_idx = set()

        for i, cand in enumerate(candidates, 1):
            src = cand_to_src[i - 1]
            src_sig = file_sig(src)
            if i in success_idx:
                dest = copy_success_file(cand, src, ok_dir, candidate_label)
                manifest[src_sig] = {
                    "status": "OK",
                    "ok_file": str(dest),
                    "source": str(src),
                    "mode": manifest_mode,
                    "style": style,
                    "target_kb": target_kb,
                }
                total_ok += 1
                ok("{} pass {} -> {}".format(src.name, candidate_label, dest.name))
            else:
                total_fail += 1
                if delete_failed_media(cand, source_dir, "candidate fail"):
                    candidate_deleted += 1
                protected = is_protected_source_file(src, source_dir)
                if protected:
                    total_fail_kept += 1
                    manifest[src_sig] = {"status": "FAIL", "source": str(src), "mode": manifest_mode, "style": style, "kept": True}
                    fail("{} FAIL -> nằm trong {} nên giữ nguyên".format(src.name, source_dir))
                else:
                    deleted = delete_failed_media(src, source_dir, "source fail")
                    if deleted:
                        total_fail_deleted += 1
                    manifest[src_sig] = {"status": "FAIL", "source": str(src), "mode": manifest_mode, "style": style, "deleted": bool(deleted)}
                    fail("{} FAIL -> đã xóa nếu file còn tồn tại".format(src.name))
            cleanup_source_candidates(src, work_dir)

        for src in build_failed_srcs:
            total_fail += 1
            src_sig = file_sig(src)
            protected = is_protected_source_file(src, source_dir)
            if protected:
                total_fail_kept += 1
                manifest[src_sig] = {"status": "FAIL", "source": str(src), "mode": manifest_mode, "style": style, "build_error": True, "kept": True}
            else:
                deleted = delete_failed_media(src, source_dir, "build candidate fail")
                if deleted:
                    total_fail_deleted += 1
                manifest[src_sig] = {"status": "FAIL", "source": str(src), "mode": manifest_mode, "style": style, "build_error": True, "deleted": bool(deleted)}
            cleanup_source_candidates(src, work_dir)
        save_manifest(manifest)

    header(mode_title + " HOÀN TẤT")
    print("{:<26}: {}".format("OK", color(total_ok, C.GREEN)))
    print("{:<26}: {}".format("FAIL", color(total_fail, C.RED)))
    print("{:<26}: {}".format("  giữ trong " + source_dir, color(total_fail_kept, C.YELLOW)))
    print("{:<26}: {}".format("  đã xóa ngoài " + source_dir, color(total_fail_deleted, C.RED)))
    print("{:<26}: {}".format("SKIP", color(skipped, C.GRAY)))
    print("{:<26}: {}".format("Build lỗi", color(build_error, C.YELLOW)))
    print("{:<26}: {}".format("Candidate fail đã xóa", color(candidate_deleted, C.YELLOW)))
    print("{:<26}: {}".format("Ảnh OK", color(ok_dir, C.CYAN)))
    return {
        "ok": total_ok,
        "fail": total_fail,
        "fail_kept": total_fail_kept,
        "fail_deleted": total_fail_deleted,
        "candidate_deleted": candidate_deleted,
        "build_error": build_error,
        "skipped": skipped,
    }


def run_sanitize_load(
    har=None,
    source_dir=SOURCE_DIR,
    ok_dir=OK_DIR,
    fail_dir=FAIL_DIR,
    work_dir=WORK_DIR,
    batch_size=MAX_PER_BATCH,
    sleep_between_batch=SLEEP_BETWEEN_BATCH,
    include_root=True,
    rerun_all=False,
    all_har=False,
    selected_image=None,
    all_images=False,
    interactive_select=True,
    sanitize_style="stripes_light",
):
    """Sanitize + load ảnh: tạo bản gạch trắng rồi load, không test ảnh gốc trước."""
    style = normalize_sanitize_style(sanitize_style)
    return _run_generated_load_mode(
        "SANITIZE + LOAD ẢNH",
        "sanitize-load",
        "SANITIZE LOAD",
        lambda src, st: sanitize_variant(src, work_dir=work_dir, sanitize_style=st),
        har=har,
        source_dir=source_dir,
        ok_dir=ok_dir,
        fail_dir=fail_dir,
        work_dir=work_dir,
        batch_size=batch_size,
        sleep_between_batch=sleep_between_batch,
        include_root=include_root,
        rerun_all=rerun_all,
        all_har=all_har,
        selected_image=selected_image,
        all_images=all_images,
        interactive_select=interactive_select,
        sanitize_style=style,
    )


def run_sanitize_compress_load(
    har=None,
    source_dir=SOURCE_DIR,
    ok_dir=OK_DIR,
    fail_dir=FAIL_DIR,
    work_dir=WORK_DIR,
    batch_size=MAX_PER_BATCH,
    sleep_between_batch=SLEEP_BETWEEN_BATCH,
    include_root=True,
    rerun_all=False,
    all_har=False,
    selected_image=None,
    all_images=False,
    interactive_select=True,
    sanitize_style="stripes_light",
    target_kb=40,
):
    """Sanitize + nén ảnh + load: tạo bản gạch trắng, nén PNG8 theo KB rồi load."""
    style = normalize_sanitize_style(sanitize_style)
    target_kb = int(target_kb)
    return _run_generated_load_mode(
        "SANITIZE + NÉN ẢNH + LOAD",
        "sanitize-compress-load",
        "SANITIZE + NÉN LOAD",
        lambda src, st: compress_sanitize_variant(src, target_kb, work_dir=work_dir, sanitize_style=st),
        har=har,
        source_dir=source_dir,
        ok_dir=ok_dir,
        fail_dir=fail_dir,
        work_dir=work_dir,
        batch_size=batch_size,
        sleep_between_batch=sleep_between_batch,
        include_root=include_root,
        rerun_all=rerun_all,
        all_har=all_har,
        selected_image=selected_image,
        all_images=all_images,
        interactive_select=interactive_select,
        sanitize_style=style,
        target_kb=target_kb,
    )


def run_sanitize_filter(*args, **kwargs):
    """Alias cũ, giữ tương thích: hiện chạy theo Sanitize + load ảnh."""
    return run_sanitize_load(*args, **kwargs)

def main():
    ap = argparse.ArgumentParser(description="Brutal mode: test ảnh gốc, fail thì tự nén và test variant; xóa fail ngoài anh_goc.")
    ap.add_argument("--har", default=None, help="Chỉ định 1 file HAR; dùng --har all hoặc --all-har để chạy toàn bộ HAR")
    ap.add_argument("--all-har", action="store_true", help="Dùng toàn bộ file .har trong thư mục, không hỏi chọn HAR")
    ap.add_argument("--image", default=None, help="Chỉ định 1 ảnh cần chạy theo tên file hoặc đường dẫn")
    ap.add_argument("--all-images", action="store_true", help="Dùng toàn bộ ảnh, không hỏi chọn ảnh")
    ap.add_argument("--filter-images", action="store_true", help="Lọc ảnh: chạy ảnh gốc thẳng, không nén")
    ap.add_argument("--sanitize-load", action="store_true", help="Sanitize + load ảnh: tạo bản gạch trắng rồi load")
    ap.add_argument("--sanitize-compress-load", action="store_true", help="Sanitize + nén ảnh + load")
    ap.add_argument("--sanitize-filter", action="store_true", help=argparse.SUPPRESS)
    ap.add_argument("--sanitize-style", default="stripes-light", choices=["stripes", "stripes-light", "stripes_light"],
                    help="Kiểu sanitize: stripes=gạch trắng rõ, stripes-light=gạch trắng mờ hơn (mặc định)")
    ap.add_argument("--sanitize-kb", type=int, default=40, help="KB cho mode --sanitize-compress-load; 0 = MAX-READABLE")
    ap.add_argument("--non-interactive", action="store_true", help="Không hiện menu chọn; mặc định dùng toàn bộ HAR/ảnh khi có nhiều")
    ap.add_argument("--source", default=SOURCE_DIR)
    ap.add_argument("--ok-dir", default=OK_DIR)
    ap.add_argument("--fail-dir", default=FAIL_DIR)
    ap.add_argument("--work-dir", default=WORK_DIR)
    ap.add_argument("--batch-size", type=int, default=MAX_PER_BATCH)
    ap.add_argument("--sleep", type=float, default=SLEEP_BETWEEN_BATCH)
    ap.add_argument("--targets", default=",".join(map(str, DEFAULT_TARGETS)))
    ap.add_argument("--no-root", action="store_true", help="Chỉ lấy ảnh trong anh_goc, không lấy ảnh ngang hàng tool")
    ap.add_argument("--rerun-all", action="store_true")
    args = ap.parse_args()

    common = dict(
        har=args.har,
        source_dir=args.source,
        ok_dir=args.ok_dir,
        fail_dir=args.fail_dir,
        work_dir=args.work_dir,
        batch_size=args.batch_size,
        sleep_between_batch=args.sleep,
        include_root=not args.no_root,
        rerun_all=args.rerun_all,
        all_har=args.all_har,
        selected_image=args.image,
        all_images=args.all_images,
        interactive_select=not args.non_interactive,
    )
    if args.sanitize_compress_load:
        run_sanitize_compress_load(**common, sanitize_style=args.sanitize_style, target_kb=args.sanitize_kb)
    elif args.sanitize_load or args.sanitize_filter:
        run_sanitize_load(**common, sanitize_style=args.sanitize_style)
    elif args.filter_images:
        run_filter_images(**common)
    else:
        run_brutal(**common, targets=parse_targets(args.targets))


if __name__ == "__main__":
    main()

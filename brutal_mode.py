#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
BRUTAL MODE an toan dung luong:
  - Flow batch theo source "auto 2 anh do len": toi da 5 anh/batch.
  - Giữ nguyên nhịp nghỉ mặc định 6 giây giữa các lượt gọi loadtran.
  - Dau tien test anh goc.
  - Anh goc fail thi moi tao cac ban nen trong _brutal_work/ va test tiep.
  - Anh nao chay duoc -> copy ban chay duoc vao anh_OK/.
  - Luon xoa anh/candidate fail, TRU anh nam trong thu muc anh_goc/.
  - Anh trong anh_goc/ khong bi xoa/move; anh fail o ngoai anh_goc/ se bi xoa.

Chay rieng:
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
FAIL_DIR = "anh_FAIL"      # chi giu folder cho tuong thich; khong dua anh fail vao day
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
            raise SystemExit("Preset KB khong hop le: {}".format(part))
        if n < 0:
            raise SystemExit("Preset KB phai >= 0")
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
        warn("Khong xoa duoc {}: {}".format(Path(p).name, e))
        return False


def safe_rmtree(p):
    p = Path(p)
    if not p.exists():
        return True
    try:
        shutil.rmtree(p)
        return True
    except Exception as e:
        warn("Khong xoa duoc folder {}: {}".format(p, e))
        return False


def path_in_dir(path, folder):
    """True neu path nam trong folder (dung de bao ve anh_goc/)."""
    try:
        p = Path(path).resolve()
        root = Path(folder).resolve()
        return p == root or root in p.parents
    except Exception:
        return False


def is_protected_source_file(path, source_dir=SOURCE_DIR):
    """Anh trong thu muc anh_goc la ban goc duoc giu lai ke ca khi fail."""
    p = Path(path)
    return p.exists() and p.is_file() and path_in_dir(p, source_dir)


def delete_failed_media(path, source_dir=SOURCE_DIR, reason="FAIL"):
    """Xoa file fail, ngoai tru file nam trong thu muc anh_goc/."""
    p = Path(path)
    if is_protected_source_file(p, source_dir):
        warn("{} fail nhung nam trong {} -> giu nguyen".format(p.name, source_dir))
        return False
    if p.exists() and p.is_file():
        deleted = safe_unlink(p)
        if deleted:
            warn("{} {} -> da xoa file fail".format(p.name, reason))
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
    """Tao 1 ban nen tu anh goc vao folder tam. Anh goc khong bi sua/xoa."""
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
        elif "vong" in p:
            ans = ""
        else:
            ans = ""
        print("-> Auto: {}".format(ans))
        return ans

    def auto_ask_choice(prompt, options):
        p = str(prompt).lower()
        if "chuc nang" in p:
            ans = "1"
        elif "phan cong" in p:
            ans = "2"
        elif "luu" in p:
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
    """Goi loadtran theo batch va giu nguyen nhịp nghỉ giữa các batch."""

    def __init__(self, har, sleep_between_batch=SLEEP_BETWEEN_BATCH):
        self.har = har
        self.sleep_between_batch = sleep_between_batch
        self.ran = 0

    def run(self, media_files):
        if self.ran and self.sleep_between_batch:
            info("Nghi {}s truoc batch tiep theo...".format(self.sleep_between_batch))
            time.sleep(self.sleep_between_batch)
        self.ran += 1
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
            result = loadtran.run(str(har), ".", 1, False, [str(p) for p in media_files])
    except SystemExit as e:
        print(color("loadtran dung som/SystemExit: {}".format(e), C.YELLOW))
    except Exception as e:
        print(color("Loi nghiem trong loadtran: {}".format(e), C.RED))
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
        # PNG/WEBP/GIF/MP4 raw thanh cong: giu dung duoi file de tranh doi noi dung.
        dest_name = original_src.name
    dest = unique_path(ok_dir, dest_name)
    shutil.copy2(src_file, dest)
    ok("{} dat {} -> {}".format(original_src.name, label, dest))
    return dest


def find_first_har():
    for f in Path(".").glob("*.har"):
        return str(f)
    return None


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
):
    targets = targets or DEFAULT_TARGETS[:]
    batch_size = max(1, min(5, int(batch_size or MAX_PER_BATCH)))
    ensure_dirs(source_dir, ok_dir, fail_dir, work_dir)

    if not har:
        har = find_first_har()
    if not har:
        fail("Khong tim thay file .har!")
        return {"ok": 0, "fail": 0, "skipped": 0}

    manifest = load_manifest()

    header("BRUTAL MODE - ORIGINAL THEN COMPRESSED")
    print("HAR       :", color(Path(har).name, C.GREEN))
    print("Anh goc   :", color("{} + root".format(source_dir) if include_root else source_dir, C.CYAN))
    print("Anh OK    :", color(ok_dir, C.CYAN))
    print("Work tmp  :", color(work_dir, C.CYAN))
    print("Batch     :", color(batch_size, C.CYAN))
    print("Preset KB :", color(",".join(map(str, targets)) + " (0=MAX-READABLE)", C.CYAN))
    print("Delay     :", color("{}s giua cac batch".format(sleep_between_batch), C.CYAN))
    print("Fail      :", color("xoa file fail, tru file nam trong {}".format(source_dir), C.YELLOW))
    print("")

    originals = discover_originals(source_dir, include_root=include_root, ok_dir=ok_dir)
    if not originals:
        warn("Khong thay anh. Hay bo anh ngang hang run_combo.bat hoac vao {}".format(source_dir))
        return {"ok": 0, "fail": 0, "skipped": 0}

    pending = []
    skipped = 0
    for src in originals:
        if not rerun_all and is_done(src, manifest, ok_dir):
            skipped += 1
            continue
        pending.append(src)

    if not pending:
        ok("Tat ca anh da co trong anh_OK hoac manifest. Khong can chay lai.")
        return {"ok": 0, "fail": 0, "skipped": skipped}

    total_ok = 0
    total_fail = 0
    total_fail_kept = 0
    total_fail_deleted = 0
    source_deleted_after_ok = 0
    candidate_deleted = 0
    runner = BatchRunner(har, sleep_between_batch)

    # 1) Test anh goc truoc, khong sua/xoa/move anh goc.
    header("PASS ORIGINAL - {} anh".format(len(pending)))
    failed_originals = []
    for start in range(0, len(pending), batch_size):
        batch = pending[start:start + batch_size]
        info("Batch original {} anh".format(len(batch)))
        for i, f in enumerate(batch, 1):
            print("  [{}] {}".format(i, f))
        success_idx = runner.run(batch)
        for i, src in enumerate(batch, 1):
            if i in success_idx:
                dest = copy_success_file(src, src, ok_dir, "ORIGINAL")
                manifest[file_sig(src)] = {"status": "OK", "ok_file": str(dest), "source": str(src), "mode": "original"}
                total_ok += 1
            else:
                failed_originals.append(src)
                warn("{} fail ORIGINAL -> se tao ban nen de test".format(src.name))
        save_manifest(manifest)

    # 2) Chi anh goc fail moi duoc nen va test variant.
    still_pending = failed_originals[:]
    for target in targets:
        if not still_pending:
            break
        mode = "MAX-READABLE" if int(target) <= 0 else "{}KB".format(target)
        header("PASS COMPRESSED {} - {} anh".format(mode, len(still_pending)))
        next_pending = []

        # Tao variant sau khi original fail, roi test theo batch.
        candidates = []
        cand_to_src = []
        for src in still_pending:
            try:
                cand = compress_variant(src, target, work_dir)
                candidates.append(cand)
                cand_to_src.append(src)
                print("  {} -> {}".format(src.name, cand.name))
            except Exception as e:
                fail("Nen loi {}: {}".format(src.name, e))
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
                    cleanup_source_candidates(src, work_dir)
                    if not is_protected_source_file(src, source_dir):
                        if delete_failed_media(src, source_dir, "ORIGINAL fail, da co ban OK"):
                            source_deleted_after_ok += 1
                else:
                    if delete_failed_media(cand, source_dir, "{} fail".format(mode)):
                        candidate_deleted += 1
                    next_pending.append(src)
                    warn("{} fail {} -> thu preset tiep".format(src.name, mode))
            save_manifest(manifest)

        # remove duplicates while preserving order
        dedup = []
        seen = set()
        for src in next_pending:
            k = file_sig(src)
            if k not in seen and not is_done(src, manifest, ok_dir):
                seen.add(k)
                dedup.append(src)
        still_pending = dedup

    if still_pending:
        header("FAIL CUOI - XOA NGOAI ANH_GOC")
        for src in still_pending:
            total_fail += 1
            src_sig = file_sig(src)
            cleanup_source_candidates(src, work_dir)
            protected = is_protected_source_file(src, source_dir)
            if protected:
                total_fail_kept += 1
                manifest[src_sig] = {"status": "FAIL", "source": str(src), "kept": True}
                fail("{} FAIL het preset -> nam trong {} nen giu nguyen".format(src.name, source_dir))
            else:
                deleted = delete_failed_media(src, source_dir, "FAIL het preset")
                if deleted:
                    total_fail_deleted += 1
                manifest[src_sig] = {"status": "FAIL", "source": str(src), "deleted": bool(deleted)}
                fail("{} FAIL het preset -> da xoa neu file con ton tai".format(src.name))
        save_manifest(manifest)

    header("BRUTAL DONE")
    print("{:<26}: {}".format("OK", color(total_ok, C.GREEN)))
    print("{:<26}: {}".format("FAIL cuoi", color(total_fail, C.RED)))
    print("{:<26}: {}".format("  giu trong " + source_dir, color(total_fail_kept, C.YELLOW)))
    print("{:<26}: {}".format("  da xoa ngoai " + source_dir, color(total_fail_deleted, C.RED)))
    print("{:<26}: {}".format("SKIP", color(skipped, C.GRAY)))
    print("{:<26}: {}".format("Source fail da xoa sau OK", color(source_deleted_after_ok, C.YELLOW)))
    print("{:<26}: {}".format("Candidate fail da xoa", color(candidate_deleted, C.YELLOW)))
    print("{:<26}: {}".format("Anh OK", color(ok_dir, C.CYAN)))
    print("{:<26}: {}".format("Thu muc tam", color(work_dir + " da don theo tung anh", C.CYAN)))
    return {
        "ok": total_ok,
        "fail": total_fail,
        "fail_kept": total_fail_kept,
        "fail_deleted": total_fail_deleted,
        "source_deleted_after_ok": source_deleted_after_ok,
        "candidate_deleted": candidate_deleted,
        "skipped": skipped,
    }


def main():
    ap = argparse.ArgumentParser(description="Brutal mode: test original, fail thi tu nen va test variant; xoa fail ngoai anh_goc.")
    ap.add_argument("--har", default=None)
    ap.add_argument("--source", default=SOURCE_DIR)
    ap.add_argument("--ok-dir", default=OK_DIR)
    ap.add_argument("--fail-dir", default=FAIL_DIR)
    ap.add_argument("--work-dir", default=WORK_DIR)
    ap.add_argument("--batch-size", type=int, default=MAX_PER_BATCH)
    ap.add_argument("--sleep", type=float, default=SLEEP_BETWEEN_BATCH)
    ap.add_argument("--targets", default=",".join(map(str, DEFAULT_TARGETS)))
    ap.add_argument("--no-root", action="store_true", help="Chi lay anh trong anh_goc, khong lay anh ngang hang tool")
    ap.add_argument("--rerun-all", action="store_true")
    args = ap.parse_args()

    run_brutal(
        har=args.har,
        source_dir=args.source,
        ok_dir=args.ok_dir,
        fail_dir=args.fail_dir,
        work_dir=args.work_dir,
        batch_size=args.batch_size,
        sleep_between_batch=args.sleep,
        targets=parse_targets(args.targets),
        include_root=not args.no_root,
        rerun_all=args.rerun_all,
    )


if __name__ == "__main__":
    main()

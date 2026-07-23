#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Menu gop 3 tool:
  1) update_synthetic_har.py  -> cap nhat synthetic_player_poster.har tu link moi
  2) compress_for_loadtran.py -> nen anh va thay anh goc
  3) loadtran.py             -> chay mod anh

Neu co nhieu .har/media trong thu muc, script se hien menu chon.

Chay:
  python loadtran_combo.py

Tuy chon:
  python loadtran_combo.py --har synthetic_player_poster.har --dir .
  Nen anh se hoi target KB, RCM 100KB. Nhap 0 = MAX-READABLE.
"""

import argparse
import json
import os
import sys
from pathlib import Path
from types import SimpleNamespace
from urllib.parse import parse_qsl, urlparse

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass


def enable_windows_ansi():
    """Bat ANSI color tren cmd.exe/Windows Terminal neu co the."""
    if os.name != "nt":
        return
    try:
        import ctypes

        kernel32 = ctypes.windll.kernel32
        for handle_id in (-11, -12):  # STD_OUTPUT_HANDLE, STD_ERROR_HANDLE
            handle = kernel32.GetStdHandle(handle_id)
            mode = ctypes.c_uint32()
            if kernel32.GetConsoleMode(handle, ctypes.byref(mode)):
                kernel32.SetConsoleMode(handle, mode.value | 0x0004)
    except Exception:
        pass


enable_windows_ansi()

MEDIA_EXTS = {".jpg", ".jpeg", ".png", ".webp", ".gif", ".mp4"}


class C:
    RESET = "\033[0m"
    BOLD = "\033[1m"
    DIM = "\033[2m"
    RED = "\033[91m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    BLUE = "\033[94m"
    CYAN = "\033[96m"
    GRAY = "\033[90m"


def color(txt, c):
    return c + str(txt) + C.RESET


def ok(txt):
    return color("[OK] " + str(txt), C.GREEN)


def warn(txt):
    return color("[!] " + str(txt), C.YELLOW)


def err(txt):
    return color("[X] " + str(txt), C.RED)


def info(txt):
    return color("> " + str(txt), C.CYAN)


def header(title):
    line = "=" * 62
    print(color(line, C.CYAN))
    print(color("  " + title, C.BOLD + C.CYAN))
    print(color(line, C.CYAN))


def ask_yes_no(question, default=False):
    suffix = "[Y/n]" if default else "[y/N]"
    while True:
        ans = input(color("{} {} ".format(question, suffix), C.YELLOW)).strip().lower()
        if not ans:
            return default
        if ans in ("y", "yes", "c", "co", "có", "1"):
            return True
        if ans in ("n", "no", "k", "khong", "không", "0"):
            return False
        print(warn("Nhap y hoac n."))


def ask_int(question, default):
    raw = input(color("{} [{}]: ".format(question, default), C.YELLOW)).strip()
    if not raw:
        return default
    try:
        return int(raw)
    except ValueError:
        print(warn("Nhap sai, dung mac dinh {}.".format(default)))
        return default


def ask_text(question, default):
    raw = input(color("{} [{}]: ".format(question, default), C.YELLOW)).strip()
    return raw if raw else default


def ask_choice(prompt, options, default=None):
    print("\n" + color(prompt, C.CYAN))
    for k, v in options.items():
        mark = color("  <-- mặc định", C.GRAY) if default is not None and k == str(default) else ""
        print("    {}[{}]{} {}{}".format(C.YELLOW + C.BOLD, k, C.RESET, v, mark))
    while True:
        raw = input(color("    Chọn{}: ".format(" [ENTER={}]".format(default) if default is not None else ""), C.YELLOW)).strip()
        if not raw and default is not None:
            return str(default)
        if raw in options:
            return raw
        print(warn("Nhập một trong các lựa chọn: {}".format(" / ".join(options.keys()))))


def parse_index_selection(raw, count, allow_all=True):
    raw = (raw or "").strip().lower().replace(",", " ")
    if allow_all and (not raw or raw in ("all", "a", "*")):
        return list(range(count))

    picked = []
    for part in raw.split():
        if "-" in part:
            left, right = part.split("-", 1)
            if not left.isdigit() or not right.isdigit():
                raise ValueError(part)
            a, b = int(left), int(right)
            if a > b:
                a, b = b, a
            for x in range(a, b + 1):
                if x < 1 or x > count:
                    raise ValueError(part)
                picked.append(x - 1)
        else:
            if not part.isdigit():
                raise ValueError(part)
            x = int(part)
            if x < 1 or x > count:
                raise ValueError(part)
            picked.append(x - 1)

    out = []
    seen = set()
    for i in picked:
        if i not in seen:
            seen.add(i)
            out.append(i)
    if not out:
        raise ValueError("empty")
    return out


def choose_har(cli_har=None):
    if cli_har:
        p = Path(cli_har)
        print(info("Dung HAR tu command: {}".format(p.name)))
        return p

    har_files = sorted(
        p for p in Path(".").glob("*.har")
        if p.is_file() and ".bak" not in p.name.lower()
    )

    if not har_files:
        p = Path("synthetic_player_poster.har")
        print(warn("Khong thay .har nao, se tao/dung: {}".format(p.name)))
        return p

    if len(har_files) == 1:
        print(ok("Tim thay 1 HAR: {}".format(har_files[0].name)))
        return har_files[0]

    default_idx = 0
    for i, p in enumerate(har_files):
        if p.name.lower() == "synthetic_player_poster.har":
            default_idx = i
            break

    print(info("Co {} file .har, chon file can dung:".format(len(har_files))))
    for i, p in enumerate(har_files, 1):
        mark = color("  <-- default", C.GRAY) if i - 1 == default_idx else ""
        print("  {}. {}  {}{}".format(
            color(i, C.YELLOW),
            color(p.name, C.CYAN),
            color("{:.1f} MB".format(p.stat().st_size / 1024 / 1024), C.GRAY),
            mark,
        ))

    while True:
        raw = input(color("Chon HAR [ENTER={}]: ".format(default_idx + 1), C.YELLOW)).strip()
        if not raw:
            return har_files[default_idx]
        if raw.isdigit() and 1 <= int(raw) <= len(har_files):
            return har_files[int(raw) - 1]
        print(warn("Nhap STT tu 1 den {}.".format(len(har_files))))


def discover_media(image_dir):
    d = Path(image_dir)
    if d.is_file():
        return [d] if d.suffix.lower() in MEDIA_EXTS else []
    if not d.exists():
        return []
    return sorted(
        p for p in d.iterdir()
        if p.is_file() and p.suffix.lower() in MEDIA_EXTS
    )


def choose_media(image_dir, cli_media=None):
    if cli_media:
        files = [Path(p) for p in cli_media]
        print(info("Dung media tu command: {} file".format(len(files))))
        return files

    files = discover_media(image_dir)
    if not files:
        print(warn("Khong tim thay media trong {}".format(image_dir)))
        return []

    if len(files) == 1:
        print(ok("Tim thay 1 media: {}".format(files[0].name)))
        return files

    print(info("Co {} file media, chon file can dung:".format(len(files))))
    for i, p in enumerate(files, 1):
        print("  {}. {}  {}".format(
            color(i, C.YELLOW),
            color(p.name, C.CYAN),
            color("{:.1f} KB".format(p.stat().st_size / 1024), C.GRAY),
        ))
    print(color("  ENTER/all = tat ca | vi du: 1 3 5-7", C.GRAY))

    while True:
        raw = input(color("Chon media: ", C.YELLOW))
        try:
            idxs = parse_index_selection(raw, len(files), allow_all=True)
            return [files[i] for i in idxs]
        except ValueError:
            print(warn("Nhap STT hop le, vi du: 1 2 hoac 1-3 hoac all."))


def read_player_poster_text():
    print(info("Dan link player-poster hoac nguyen noi dung loi net::ERR_NAME_NOT_RESOLVED:"))
    lines = []
    while True:
        line = input(color("> " if not lines else "", C.GRAY))
        if not line.strip() and lines:
            break
        if not line.strip():
            continue
        lines.append(line)
        if "https://kgvn-camp.mobagarena.com/" in line:
            break
    return "\n".join(lines)


def update_har_interactive(har_path, source_har):
    import update_synthetic_har as uh

    text = read_player_poster_text()
    page_url = uh.extract_url(text)
    parsed = urlparse(page_url)
    query_items = parse_qsl(parsed.query, keep_blank_values=True)
    params = dict(query_items)

    ua, sec_ch_ua = uh.load_ua_from_source(source_har)
    hp = Path(har_path)
    if hp.exists():
        har = json.loads(hp.read_text(encoding="utf-8", errors="ignore"))
    else:
        har = uh.ensure_minimal_har(hp, page_url, query_items, ua, sec_ch_ua)

    result = uh.update_har(har, page_url, query_items, params, ua, sec_ch_ua)
    hp.write_text(json.dumps(har, ensure_ascii=False, indent=2), encoding="utf-8")

    print(ok("Da cap nhat HAR: {}".format(hp.name)))
    print("  token:", uh.compact_secret(result["itop"]))
    print("  ts   :", result["ts"])
    print("  nick :", result["nickname"])


def compress_images_inplace(files, target_kb):
    import compress_for_loadtran as cf

    files = [Path(f) for f in files]
    if not files:
        print(warn("Khong co anh nao de nen."))
        return []

    out_dummy = files[0].parent / ".lt_compressed_tmp"

    mode_txt = "MAX-READABLE" if target_kb <= 0 else "{}KB (RCM 100KB)".format(target_kb)
    args = SimpleNamespace(
        width=1080,
        height=1701,
        max_kb=target_kb,
        min_quality=10,
        absolute_min=False,
        format="jpg",
        replace_original=True,
    )

    print(info("Nen {} anh ve {} va thay file goc...".format(len(files), mode_txt)))
    made = []
    for f in files:
        if f.suffix.lower() not in cf.IMAGE_EXTS:
            print(warn("{}: bo qua nen, dinh dang nay de loadtran xu ly truc tiep".format(f.name)))
            made.append(f)
            continue
        try:
            made.append(cf.compress_one(f, out_dummy, args))
        except Exception as e:
            print(err("{}: {}".format(f.name, e)))
            made.append(f)
    print(ok("Nen anh xong. Anh goc da duoc thay bang ban JPG nen."))
    return made


def default_compress_dir(image_dir):
    d = Path(image_dir)
    if str(d) == "." and Path("anh_goc").exists() and discover_media("anh_goc"):
        return "anh_goc"
    return image_dir


def compress_images_to_folder(files, target_kb, output_dir="compressed"):
    """Nén nhiều ảnh ra thư mục output, không thay file gốc."""
    import compress_for_loadtran as cf

    files = [Path(f) for f in files]
    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    if not files:
        print(warn("Không có ảnh nào để nén."))
        return []

    mode_txt = "MAX-READABLE" if target_kb <= 0 else "{}KB".format(target_kb)
    args = SimpleNamespace(
        width=1080,
        height=1701,
        max_kb=target_kb,
        min_quality=10,
        absolute_min=False,
        format="jpg",
        replace_original=False,
    )

    print(info("Nén {} ảnh về {} -> lưu vào {} (không thay ảnh gốc)...".format(
        len(files), mode_txt, out_dir)))
    made = []
    for f in files:
        if f.suffix.lower() not in cf.IMAGE_EXTS:
            print(warn("{}: bỏ qua, định dạng này không nén bằng JPEG batch.".format(f.name)))
            continue
        try:
            made.append(cf.compress_one(f, out_dir, args))
        except Exception as e:
            print(err("{}: {}".format(f.name, e)))
    print(ok("Nén đa ảnh xong: {} file -> {}".format(len(made), out_dir)))
    return made


def ask_brutal_targets():
    import brutal_mode

    default_text = ",".join(map(str, brutal_mode.DEFAULT_TARGETS))
    print("")
    print(info("Preset Brutal mặc định: {}".format(default_text)))
    print(color("Gợi ý: 30-40KB thường sẽ pass các ảnh khó.", C.YELLOW))
    choice = input(color("Chọn preset: [1] mặc định, [2] tự nhập KB (ENTER=1): ", C.YELLOW)).strip()
    if choice != "2":
        return brutal_mode.DEFAULT_TARGETS[:]
    while True:
        raw = input(color("Nhập các KB muốn thử, ví dụ 20,30,40: ", C.YELLOW)).strip()
        if not raw:
            raw = "30,40"
        try:
            targets = brutal_mode.parse_targets(raw)
            print(ok("Dùng preset tự chọn: {}".format(",".join(map(str, targets)))))
            return targets
        except SystemExit as e:
            print(warn(str(e)))


def ask_sanitize_style():
    style_choice = ask_choice(
        "Chọn kiểu sanitize:",
        {
            "1": "Gạch trắng mờ hơn (mặc định, nhìn rõ ảnh hơn)",
            "2": "Gạch trắng rõ toàn ảnh",
        },
        default="1",
    )
    return "stripes_light" if style_choice == "1" else "stripes"


def run_loadtran(har_path, image_dir, rounds, dry_run, media_files=None):
    import loadtran

    print("")
    header("RUN LOADTRAN")
    loadtran.run(str(har_path), str(image_dir), rounds, dry_run=dry_run, media_files=media_files)


def main():
    ap = argparse.ArgumentParser(description="Combo runner: update HAR -> compress -> loadtran")
    ap.add_argument("--har", default=None, help="HAR se dung cho loadtran; bo trong thi hien menu chon neu co nhieu HAR")
    ap.add_argument("--source-har", default="ProxyPin7-21_10_00_12.har", help="HAR goc de lay UA/sec-ch-ua")
    ap.add_argument("--dir", default=".", help="Thu muc anh, mac dinh .")
    ap.add_argument("--media", nargs="*", default=None, help="Chon san media bang command, bo qua menu chon anh")
    ap.add_argument("--compress-kb", "--max-kb", dest="compress_kb", type=int, default=100,
                    help="Muc tieu nen anh, RCM 100KB; 0 = MAX-READABLE")
    ap.add_argument("--rounds", type=int, default=None, help="So vong cho loadtran")
    ap.add_argument("--dry-run", action="store_true", help="Truyen dry-run vao loadtran")
    ap.add_argument("--yes-update", action="store_true", help="Bo qua cau hoi update HAR va bat update")
    ap.add_argument("--no-update", action="store_true", help="Bo qua cau hoi update HAR va khong update")
    ap.add_argument("--yes-compress", action="store_true", help="Bo qua cau hoi nen anh va bat nen")
    ap.add_argument("--no-compress", action="store_true", help="Bo qua cau hoi nen anh va khong nen")
    ap.add_argument("--absolute-min", action="store_true", help=argparse.SUPPRESS)
    args = ap.parse_args()

    header("LOADTRAN COMBO")
    print(" Dir :", color(args.dir, C.CYAN))
    print("")

    main_action = ask_choice(
        "Bạn muốn làm gì?",
        {
            "1": "{}Thay ảnh load{} (chạy LoadTran/HAR)".format(C.GREEN + C.BOLD, C.RESET),
            "2": "{}Nén đa ảnh{} (chưa thay ảnh, chỉ xuất file nén)".format(C.CYAN + C.BOLD, C.RESET),
        },
    )

    if main_action == "2":
        image_dir = default_compress_dir(args.dir)
        print(info("Thư mục ảnh dùng để nén: {}".format(image_dir)))
        media_files = choose_media(image_dir, args.media)
        if not media_files:
            print(err("Không có ảnh để nén."))
            return
        target_kb = ask_int("Nén xuống bao nhiêu KB? Gợi ý 30-40 cho ảnh khó, nhập 0 = MAX-READABLE", args.compress_kb)
        out_dir = ask_text("Thư mục lưu ảnh đã nén", "compressed")
        made = compress_images_to_folder(media_files, target_kb, out_dir)
        print(ok("Hoàn tất nén đa ảnh: {} file.".format(len(made))))
        print(info("Ảnh gốc vẫn giữ nguyên. Khi muốn chạy LoadTran, chọn thư mục: {}".format(out_dir)))
        return

    if args.yes_update:
        do_update = True
    elif args.no_update:
        do_update = False
    else:
        do_update = ask_yes_no("Có cần update .har từ link mới không?", default=False)

    if do_update:
        har_path = choose_har(args.har)
        update_har_interactive(har_path, args.source_har)
    else:
        har_path = None
        print(color("Skip update HAR.", C.GRAY))

    print("")
    auto_mode = ask_choice(
        "Chọn chế độ auto ảnh:",
        {
            "0": "Chạy thường / bỏ qua auto",
            "1": "{}Brutal Mode{} (test gốc, fail thì tự nén theo preset)".format(C.YELLOW + C.BOLD, C.RESET),
            "2": "{}Lọc ảnh{} (chạy thẳng ảnh gốc, không nén)".format(C.CYAN + C.BOLD, C.RESET),
            "3": "{}Sanitize + load ảnh{} (gạch trắng rồi load, không nén)".format(C.GREEN + C.BOLD, C.RESET),
            "4": "{}Sanitize + nén ảnh + load{} (gạch trắng, nén KB rồi load)".format(C.YELLOW + C.BOLD, C.RESET),
        },
    )
    if auto_mode == "1":
        import brutal_mode

        targets = ask_brutal_targets()
        brutal_mode.run_brutal(
            har=args.har or None,
            source_dir="anh_goc",
            ok_dir="anh_OK",
            fail_dir="anh_FAIL",
            batch_size=5,
            sleep_between_batch=6,
            targets=targets,
        )
        return
    if auto_mode == "2":
        import brutal_mode

        brutal_mode.run_filter_images(
            har=args.har or None,
            source_dir="anh_goc",
            ok_dir="anh_OK",
            fail_dir="anh_FAIL",
            batch_size=5,
            sleep_between_batch=6,
        )
        return
    if auto_mode == "3":
        import brutal_mode

        style = ask_sanitize_style()
        brutal_mode.run_sanitize_load(
            har=args.har or None,
            source_dir="anh_goc",
            ok_dir="anh_OK",
            fail_dir="anh_FAIL",
            batch_size=5,
            sleep_between_batch=6,
            sanitize_style=style,
        )
        return
    if auto_mode == "4":
        import brutal_mode

        style = ask_sanitize_style()
        default_kb = args.compress_kb if args.compress_kb != 100 else 40
        target_kb = ask_int("Nén xuống bao nhiêu KB sau sanitize? Gợi ý 30-40, nhập 0 = MAX-READABLE", default_kb)
        brutal_mode.run_sanitize_compress_load(
            har=args.har or None,
            source_dir="anh_goc",
            ok_dir="anh_OK",
            fail_dir="anh_FAIL",
            batch_size=5,
            sleep_between_batch=6,
            sanitize_style=style,
            target_kb=target_kb,
        )
        return

    print("")
    if args.yes_compress:
        do_compress = True
    elif args.no_compress:
        do_compress = False
    else:
        do_compress = ask_yes_no("Có cần nén ảnh và thay ảnh gốc không?", default=False)

    media_files = choose_media(args.dir, args.media)
    if do_compress:
        target_kb = ask_int("Nén xuống bao nhiêu KB? RCM 100KB, nhập 0 = MAX-READABLE", args.compress_kb)
        media_files = compress_images_inplace(media_files, target_kb)
    else:
        print(color("Skip nen anh.", C.GRAY))

    if har_path is None:
        har_path = choose_har(args.har)

    print("")
    print(" HAR :", color(har_path, C.CYAN))
    print(" Media:", color("{} file".format(len(media_files)) if media_files else "auto", C.CYAN))
    run_loadtran(har_path, args.dir, args.rounds, args.dry_run, media_files=media_files)


if __name__ == "__main__":
    raise SystemExit(main())

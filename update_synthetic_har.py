#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Cap nhat synthetic_player_poster.har tu link/error text player-poster.

Chay nhanh:
  python update_synthetic_har.py
  # dan nguyen dong "Trang web hien khong kha dung ... https://... net::ERR_NAME_NOT_RESOLVED"

Hoac:
  python update_synthetic_har.py --text "https://kgvn-camp.mobagarena.com/app/player-poster?..."
  python update_synthetic_har.py --file link.txt
"""

import argparse
import json
import re
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import parse_qsl, urlparse

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass


DEFAULT_HAR = "synthetic_player_poster.har"
DEFAULT_SOURCE_HAR = "ProxyPin7-21_10_00_12.har"
API_HOST = "kgvn-api.mobagarena.com"
PAGE_HOST = "kgvn-camp.mobagarena.com"
COS_HOST = "aovcamp-h5-ugc-1254801811.cos.ap-singapore.myqcloud.com"

DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (Linux; Android 16; CPH2747 Build/BP2A.250605.015; wv) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Version/4.0 Chrome/149.0.7827.91 "
    "Mobile Safari/537.36 MSDK/5.36.000 mQQAppId/1105779914 "
    "mWXAppId/wx7a814e3ceeda8320 mGameId/1137 MSDKdeviceId/disable"
)
DEFAULT_SEC_CH_UA = '"Android WebView";v="149", "Chromium";v="149", "Not)A;Brand";v="24"'


def now_iso():
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def compact_secret(value, keep=8):
    if not value:
        return "-"
    if len(value) <= keep * 2:
        return value
    return "{}...{} (len={})".format(value[:keep], value[-keep:], len(value))


def extract_url(text):
    m = re.search(r"https://kgvn-camp\.mobagarena\.com/[^\s\"'<>]+", text)
    if not m:
        raise SystemExit("Khong tim thay URL kgvn-camp.mobagarena.com trong noi dung da nhap.")
    return m.group(0).rstrip(".,;)'\"")


def read_input_text(args):
    if args.text:
        return args.text
    if args.file:
        return Path(args.file).read_text(encoding="utf-8", errors="ignore")

    if not sys.stdin.isatty():
        data = sys.stdin.read()
        if data.strip():
            return data

    print("Dan link hoac nguyen noi dung loi. Script se tu dung khi thay URL:")
    lines = []
    while True:
        try:
            line = input("> " if not lines else "")
        except EOFError:
            break
        if not line.strip() and lines:
            break
        if not line.strip():
            continue
        lines.append(line)
        if re.search(r"https://kgvn-camp\.mobagarena\.com/[^\s\"'<>]+", line):
            break
    return "\n".join(lines).strip()


def headers_to_dict(headers):
    return {h.get("name", "").lower(): h.get("value", "") for h in headers or []}


def set_header(headers, name, value):
    lname = name.lower()
    for h in headers:
        if h.get("name", "").lower() == lname:
            h["value"] = value
            return
    headers.append({"name": name, "value": value})


def del_header(headers, name):
    lname = name.lower()
    headers[:] = [h for h in headers if h.get("name", "").lower() != lname]


def qlist(query_items):
    return [{"name": k, "value": v} for k, v in query_items]


def load_ua_from_source(source_har):
    ua = DEFAULT_USER_AGENT
    sec = DEFAULT_SEC_CH_UA
    p = Path(source_har)
    if not p.exists():
        return ua, sec
    try:
        har = json.loads(p.read_text(encoding="utf-8", errors="ignore"))
        for entry in har.get("log", {}).get("entries", []):
            hdrs = headers_to_dict(entry.get("request", {}).get("headers", []))
            if hdrs.get("user-agent"):
                ua = hdrs["user-agent"]
            if hdrs.get("sec-ch-ua"):
                sec = hdrs["sec-ch-ua"]
    except Exception:
        pass
    return ua, sec


def ensure_minimal_har(path, page_url, query_items, ua, sec_ch_ua):
    """Tao HAR toi thieu neu file chua ton tai."""
    ts = now_iso()

    def hlist(d):
        return [{"name": k, "value": v} for k, v in d.items()]

    def make_post(endpoint, payload):
        body = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
        return {
            "startedDateTime": ts,
            "time": 0,
            "request": {
                "method": "POST",
                "url": "https://{}/{}".format(API_HOST, endpoint.lstrip("/")),
                "httpVersion": "HTTP/2",
                "headers": hlist({
                    "content-type": "application/json",
                    "msdk-itopencodeparam": "",
                    "user-agent": ua,
                    "sec-ch-ua": sec_ch_ua,
                }),
                "queryString": [],
                "cookies": [],
                "headersSize": -1,
                "bodySize": len(body.encode("utf-8")),
                "postData": {"mimeType": "application/json", "text": body},
            },
            "response": {
                "status": 200,
                "statusText": "OK",
                "httpVersion": "HTTP/2",
                "headers": [{"name": "content-type", "value": "application/json"}],
                "cookies": [],
                "content": {"size": 0, "mimeType": "application/json", "text": ""},
                "redirectURL": "",
                "headersSize": -1,
                "bodySize": -1,
            },
            "cache": {},
            "timings": {"send": 0, "wait": 0, "receive": 0},
        }

    def make_put(suffix):
        return {
            "startedDateTime": ts,
            "time": 0,
            "request": {
                "method": "PUT",
                "url": "https://{}/1/704/SYNTHETIC_USER_PATH/0/1/SYNTHETIC_POSTER_ID{}".format(
                    COS_HOST, suffix
                ),
                "httpVersion": "HTTP/2",
                "headers": hlist({
                    "content-type": "image/png",
                    "host": COS_HOST,
                    "origin": "https://kgvn-camp.mobagarena.com",
                    "referer": "https://kgvn-camp.mobagarena.com/",
                    "user-agent": ua,
                }),
                "queryString": [],
                "cookies": [],
                "headersSize": -1,
                "bodySize": 0,
            },
            "response": {
                "status": 200,
                "statusText": "OK",
                "httpVersion": "HTTP/2",
                "headers": [],
                "cookies": [],
                "content": {"size": 0, "mimeType": "text/plain", "text": ""},
                "redirectURL": "",
                "headersSize": -1,
                "bodySize": -1,
            },
            "cache": {},
            "timings": {"send": 0, "wait": 0, "receive": 0},
        }

    har = {
        "log": {
            "version": "1.2",
            "creator": {"name": "synthetic-har-updater", "version": "1.0"},
            "pages": [{
                "startedDateTime": ts,
                "id": "page_1",
                "title": page_url,
                "pageTimings": {},
            }],
            "entries": [
                {
                    "startedDateTime": ts,
                    "time": 0,
                    "request": {
                        "method": "GET",
                        "url": page_url,
                        "httpVersion": "HTTP/2",
                        "headers": hlist({
                            "upgrade-insecure-requests": "1",
                            "user-agent": ua,
                            "accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                            "accept-language": "vi-VN,vi;q=0.9,en-US;q=0.8,en;q=0.7",
                        }),
                        "queryString": qlist(query_items),
                        "cookies": [],
                        "headersSize": -1,
                        "bodySize": 0,
                    },
                    "response": {
                        "status": 0,
                        "statusText": "net::ERR_NAME_NOT_RESOLVED",
                        "httpVersion": "",
                        "headers": [],
                        "cookies": [],
                        "content": {"size": 0, "mimeType": "text/plain", "text": ""},
                        "redirectURL": "",
                        "headersSize": -1,
                        "bodySize": -1,
                        "_error": "net::ERR_NAME_NOT_RESOLVED",
                    },
                    "cache": {},
                    "timings": {"send": -1, "wait": -1, "receive": -1},
                },
                make_post("/api/user/game/getselfuserinfo", {}),
                make_post("/api/game/poster/playerimage/createposter", {}),
                make_post("/api/game/poster/playerimage/getpostereditinfo", {}),
                make_post("/api/game/poster/getcoscredential", {
                    "scene": "PlayerimagePoster",
                    "fileName": "0/1/SYNTHETIC_POSTER_ID_large.png",
                }),
                make_post("/api/game/poster/getcoscredential", {
                    "scene": "PlayerimagePoster",
                    "fileName": "0/1/SYNTHETIC_POSTER_ID.png",
                }),
                make_put("_large.png"),
                make_put(".png"),
            ],
        }
    }
    Path(path).write_text(json.dumps(har, ensure_ascii=False, indent=2), encoding="utf-8")
    return har


def update_har(har, page_url, query_items, params, ua, sec_ch_ua):
    itop = params.get("itopencodeparam", "")
    if not itop:
        raise SystemExit("URL thieu tham so itopencodeparam.")

    token_for_header = itop
    optional_encodeparam = params.get("encodeparam", "")

    fixed_updates = {
        "camp-source": "AOV-CAMP",
        "msdk-gameid": params.get("gameid", "1137"),
        "camp-authtype": "msdk",
        "areaid": params.get("aov_areaid", "1"),
        "msdk-os": params.get("os", "1"),
        "logicworldid": params.get("partition", "1011"),
        "aov-language": params.get("lang", "VN"),
        "msdk-channelid": params.get("channelid", "10"),
        "aov-region": params.get("aov_region", "1137"),
        "origin": "https://kgvn-camp.mobagarena.com",
        "x-requested-with": "com.garena.game.kgvn",
        "referer": "https://kgvn-camp.mobagarena.com/",
        "sec-ch-ua-mobile": "?1",
        "sec-ch-ua-platform": '"Android"',
        "sec-fetch-site": "same-site",
        "sec-fetch-mode": "cors",
        "sec-fetch-dest": "empty",
        "accept": "*/*",
        "accept-language": "vi-VN,vi;q=0.9,en-US;q=0.8,en;q=0.7",
        "accept-encoding": "gzip, deflate, br, zstd",
        "user-agent": ua,
        "sec-ch-ua": sec_ch_ua,
    }

    log = har.setdefault("log", {})
    log.setdefault("creator", {})["name"] = "synthetic-har-updater"
    log["creator"]["version"] = "1.0"

    for page in log.get("pages", []):
        page["title"] = page_url

    post_count = 0
    get_count = 0
    for entry in log.get("entries", []):
        req = entry.get("request", {})
        method = req.get("method", "")
        url = req.get("url", "")

        if method == "GET" and PAGE_HOST in url and "/app/player-poster" in url:
            req["url"] = page_url
            req["queryString"] = qlist(query_items)
            hdrs = req.setdefault("headers", [])
            set_header(hdrs, "user-agent", ua)
            get_count += 1

        if method == "POST" and API_HOST in url:
            hdrs = req.setdefault("headers", [])
            for k, v in fixed_updates.items():
                set_header(hdrs, k, v)
            set_header(hdrs, "content-type", "application/json")
            set_header(hdrs, "msdk-itopencodeparam", token_for_header)

            # Link player-poster thuong chi co itopencodeparam.
            # Neu de lai encodeparam cu trong HAR thi loadtran.py co the lay nham sign da cu.
            if optional_encodeparam:
                set_header(hdrs, "encodeparam", optional_encodeparam)
            else:
                del_header(hdrs, "encodeparam")

            post_count += 1

    if get_count == 0:
        raise SystemExit("HAR khong co GET player-poster de cap nhat.")
    if post_count == 0:
        raise SystemExit("HAR khong co POST kgvn-api de cap nhat token.")

    return {
        "itop": itop,
        "access_token": params.get("access_token", ""),
        "ts": params.get("ts", ""),
        "seq": params.get("seq", ""),
        "sig": params.get("sig", ""),
        "nickname": params.get("nickname", ""),
        "post_count": post_count,
        "get_count": get_count,
    }


def main():
    ap = argparse.ArgumentParser(
        description="Cap nhat synthetic_player_poster.har tu URL player-poster moi."
    )
    ap.add_argument("--har", default=DEFAULT_HAR, help="HAR can sua, mac dinh synthetic_player_poster.har")
    ap.add_argument("--output", default=None, help="File output, mac dinh ghi de --har")
    ap.add_argument("--source-har", default=DEFAULT_SOURCE_HAR, help="HAR goc de lay user-agent/sec-ch-ua neu can")
    ap.add_argument("--text", default="", help="Dan truc tiep URL hoac nguyen noi dung loi")
    ap.add_argument("--file", default="", help="Doc URL/noi dung loi tu file txt")
    ap.add_argument("--backup", action="store_true", help="Tao file .bak truoc khi ghi de HAR")
    ap.add_argument("--no-backup", action="store_true", help=argparse.SUPPRESS)
    args = ap.parse_args()

    input_text = read_input_text(args)
    page_url = extract_url(input_text)
    parsed = urlparse(page_url)
    query_items = parse_qsl(parsed.query, keep_blank_values=True)
    params = dict(query_items)

    ua, sec_ch_ua = load_ua_from_source(args.source_har)
    har_path = Path(args.har)
    if har_path.exists():
        har = json.loads(har_path.read_text(encoding="utf-8", errors="ignore"))
    else:
        har = ensure_minimal_har(har_path, page_url, query_items, ua, sec_ch_ua)

    info = update_har(har, page_url, query_items, params, ua, sec_ch_ua)

    out_path = Path(args.output) if args.output else har_path
    if out_path.resolve() == har_path.resolve() and har_path.exists() and args.backup:
        bak = har_path.with_suffix(har_path.suffix + "." + datetime.now().strftime("%Y%m%d_%H%M%S") + ".bak")
        shutil.copy2(har_path, bak)
        print("Backup:", bak.name)

    out_path.write_text(json.dumps(har, ensure_ascii=False, indent=2), encoding="utf-8")

    print("Da cap nhat:", out_path.name)
    print("GET player-poster:", info["get_count"])
    print("POST kgvn-api:", info["post_count"])
    print("itopencodeparam:", compact_secret(info["itop"]))
    print("access_token:", compact_secret(info["access_token"]))
    print("ts:", info["ts"])
    print("seq:", info["seq"])
    print("sig:", info["sig"])
    print("nickname:", info["nickname"])
    print("")
    print("Chay tiep:")
    print("  python loadtran.py --har {}".format(out_path.name))


if __name__ == "__main__":
    main()

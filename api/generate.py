"""POST /config 的核心逻辑：校验请求 JSON，并调用 main.py 生成配置。

与 Flask 解耦，方便单测与复用。
"""
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MAIN_PY = os.path.join(PROJECT_ROOT, "main.py")
CONFIG_TEMPLATE_DIR = os.path.join(PROJECT_ROOT, "config_template")

MAX_SUBS = int(os.environ.get("MAX_SUBS", "10"))
GENERATE_TIMEOUT = int(os.environ.get("GENERATE_TIMEOUT", "300"))
# 允许被 API 读取的本地文件根目录（订阅文件、不能引用的模板等）。
# 默认项目根目录；自托管时可用环境变量指向专门的目录，如 /data。
LOCAL_DATA_DIR = os.path.realpath(os.environ.get("LOCAL_DATA_DIR", PROJECT_ROOT))

_URL_RE = re.compile(r"^https?://", re.IGNORECASE)

# 单个订阅的字段与默认值（与 providers.json 的 subscribes[] 对齐）
SUBSCRIBE_DEFAULTS = {
    "tag": "",
    "enabled": True,
    "emoji": 1,
    "subgroup": "",
    "prefix": "",
    "ex-node-name": "",
    "User-Agent": "clash.meta",
}

# 顶层字段与默认值
PROVIDER_DEFAULTS = {
    "auto_set_outbounds_dns": {"proxy": "", "direct": ""},
    "save_config_path": "./config.json",
    "auto_backup": False,
    "exclude_protocol": "ssr",
    "config_template": "",
    "Only-nodes": False,
    "gh": 0,  # 非 providers.json 字段：github 加速序号(1 开始)，0 表示不用
}


class BadRequest(ValueError):
    """请求参数错误 → HTTP 400。"""


class GenerateError(RuntimeError):
    """生成失败 → HTTP 502。"""


def _local_file_path(value):
    """把 `file://` 或本地路径归一化为绝对路径，并限制在 LOCAL_DATA_DIR 内。"""
    raw = value
    lower = value.lower()
    if lower.startswith("file://"):
        raw = value[len("file://"):]
    elif lower.startswith("file:"):
        raw = value[len("file:"):]
    if not raw:
        raise BadRequest("本地文件路径为空")
    path = raw if os.path.isabs(raw) else os.path.join(LOCAL_DATA_DIR, raw)
    path = os.path.realpath(path)
    if os.path.commonpath([LOCAL_DATA_DIR, path]) != LOCAL_DATA_DIR:
        raise BadRequest(f"本地文件不在允许目录内：{value}")
    if not os.path.isfile(path):
        raise BadRequest(f"本地文件不存在：{value}")
    return path


def _normalize_subscribe(raw, index):
    if not isinstance(raw, dict):
        raise BadRequest(f"subscribes[{index}] 必须是对象")
    url = str(raw.get("url", "")).strip()
    if not url:
        raise BadRequest(f"subscribes[{index}] 缺少 url")
    # 本地订阅文件：file:// 或服务端已存在的绝对路径（限制在 LOCAL_DATA_DIR 内）
    if url.lower().startswith("file:"):
        url = _local_file_path(url)
    elif url.startswith("/") and os.path.isfile(url):
        url = _local_file_path(url)

    item = dict(SUBSCRIBE_DEFAULTS)
    merged = dict(raw)
    if "ua" in merged and "User-Agent" not in merged:  # ua 是 User-Agent 的别名
        merged["User-Agent"] = merged["ua"]
    item.update({k: v for k, v in merged.items() if k in SUBSCRIBE_DEFAULTS})
    item["url"] = url
    item["tag"] = str(item["tag"]).strip() or f"tag_{index + 1}"
    item["enabled"] = bool(item["enabled"])
    try:
        item["emoji"] = 1 if int(item["emoji"]) else 0
    except (TypeError, ValueError):
        item["emoji"] = 1
    return item


def normalize(payload):
    """把请求 JSON 规范化成 main.py 需要的 providers 结构。"""
    if not isinstance(payload, dict):
        raise BadRequest("请求体必须是 JSON 对象")

    subscribes = payload.get("subscribes")
    if not isinstance(subscribes, list) or not subscribes:
        raise BadRequest("subscribes 必须是非空数组")
    if len(subscribes) > MAX_SUBS:
        raise BadRequest(f"订阅数量不能超过 {MAX_SUBS}")

    providers = dict(PROVIDER_DEFAULTS)
    providers.update({k: v for k, v in payload.items() if k in PROVIDER_DEFAULTS})

    seen = set()
    normalized_subs = []
    for i, raw in enumerate(subscribes):
        item = _normalize_subscribe(raw, i)
        if item["tag"] in seen:
            raise BadRequest(f"订阅 tag 重复：{item['tag']}")
        seen.add(item["tag"])
        normalized_subs.append(item)
    providers["subscribes"] = normalized_subs
    _resolve_template(providers)
    return providers


def _resolve_template(providers):
    """归一化 config_template：

    - 对象        → 内联模板（原样保留，run() 会写入临时文件）
    - http(s) URL → 远程模板
    - 其余字符串  → config_template/ 目录下的文件名（可省 .json 后缀）
    - 为空        → 交给 main.py 使用默认模板

    本地文件名限定在 config_template/ 目录内，禁止绝对路径与 `..` 目录穿越。
    """
    template = providers.get("config_template")
    if not isinstance(template, str):
        return
    template = template.strip()
    if not template or _URL_RE.match(template):
        return
    name = template if template.endswith(".json") else template + ".json"
    base = os.path.realpath(CONFIG_TEMPLATE_DIR)
    path = os.path.realpath(os.path.join(base, name))
    # realpath 后必须仍在 config_template/ 内（防 `../` 穿越）
    if os.path.commonpath([base, path]) != base or not os.path.isfile(path):
        raise BadRequest(f"本地模板不存在或不允许访问：config_template/{template}")
    providers["config_template"] = path


def run(providers):
    """调用 main.py 生成配置，返回配置文本。每次使用独立临时目录，进程安全。"""
    providers = json.loads(json.dumps(providers))  # 深拷贝，避免污染调用方

    workdir = tempfile.mkdtemp(prefix="sbs-")
    try:
        # 内联模板：写入临时文件，再交给 main.py 当作本地模板读取
        template = providers.get("config_template")
        if isinstance(template, dict):
            if not template.get("outbounds"):
                raise BadRequest("内联 config_template 缺少 outbounds 字段")
            template_path = os.path.join(workdir, "template.json")
            with open(template_path, "w", encoding="utf-8") as f:
                json.dump(template, f, ensure_ascii=False)
            providers["config_template"] = template_path

        input_path = os.path.join(workdir, "providers.json")
        output_path = os.path.join(workdir, "config.json")
        providers["save_config_path"] = output_path
        with open(input_path, "w", encoding="utf-8") as f:
            json.dump(providers, f, ensure_ascii=False)

        cmd = [
            sys.executable, MAIN_PY,
            "--temp_json_file", input_path,
        ]
        gh = providers.get("gh")
        if gh:
            cmd += ["--gh_proxy_index", str(int(gh) - 1)]

        try:
            proc = subprocess.run(
                cmd,
                cwd=PROJECT_ROOT,
                capture_output=True,
                text=True,
                timeout=GENERATE_TIMEOUT,
            )
        except subprocess.TimeoutExpired:
            raise GenerateError(f"生成超时（>{GENERATE_TIMEOUT}s）")

        if proc.returncode != 0:
            detail = (proc.stderr or proc.stdout or "").strip()
            raise GenerateError(detail[-2000:] or "main.py 执行失败")

        with open(output_path, encoding="utf-8") as f:
            return f.read()
    finally:
        shutil.rmtree(workdir, ignore_errors=True)

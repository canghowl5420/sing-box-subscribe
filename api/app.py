"""sing-box-subscribe 的 HTTP API。

业务接口只有一个：

    POST /config   请求体为 JSON（见 docs/api.md），响应体是生成好的 sing-box 配置。

运行方式：
    python api/app.py                 # 本地/容器，默认监听 :5000
    vercel                            # vercel.json 会把请求 rewrite 到本模块
"""
import os
import sys

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from flask import Flask, Response, jsonify, render_template, request

try:
    from api import generate
except ImportError:  # 直接以 `python api/app.py` 运行时
    import generate  # type: ignore

app = Flask(__name__, template_folder=os.path.join(PROJECT_ROOT, "templates"))
app.secret_key = "sing-box"


def _template_names():
    """config_template/ 目录下的模板文件名（不含扩展名，已排序）。"""
    template_dir = os.path.join(PROJECT_ROOT, "config_template")
    files = sorted(f for f in os.listdir(template_dir) if f.endswith(".json"))
    return [os.path.splitext(f)[0] for f in files]


@app.get("/")
def index():
    """调试页面：填写表单，生成请求 JSON 或完整的 config.json。"""
    return render_template("index.html", templates=_template_names())


@app.post("/config")
def config():
    payload = request.get_json(silent=True)
    if payload is None:
        return jsonify(status="error",
                       message="请求体必须是合法 JSON，且 Content-Type: application/json"), 400
    try:
        providers = generate.normalize(payload)
        content = generate.run(providers)
    except generate.BadRequest as exc:
        return jsonify(status="error", message=str(exc)), 400
    except generate.GenerateError as exc:
        return jsonify(status="error", message=str(exc)), 502
    except Exception as exc:  # noqa: BLE001
        return jsonify(status="error", message=f"生成失败：{exc}"), 500
    return Response(content, mimetype="application/json")


if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=int(os.environ.get("PORT", "5000")))

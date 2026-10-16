# HTTP API 文档（POST /config）

本分支已把接口改为 **POST + JSON body**：请求体里直接写订阅和每个订阅的参数，
服务端生成后把 sing-box 配置作为响应体返回。**不再需要拼接 URL**，也不再有
`&` / `|` / `%2C` 的字符串手术。

- 请求：`POST /config`，`Content-Type: application/json`
- 响应：`200`，body 即生成好的 sing-box `config.json` 文本（`application/json`）
- 出错：非 200，body 为 `{"status":"error","message":"..."}`

---

## 1. 请求 JSON 格式

请求体就是一个 providers 对象（与 `providers.json` 同构，字段都可省略）：

```json
{
  "subscribes": [
    {
      "url": "https://机场A订阅",
      "tag": "airportA",
      "enabled": true,
      "emoji": 1,
      "subgroup": "",
      "prefix": "A-",
      "User-Agent": "clash.meta",
      "ex-node-name": "网站,剩余流量,过期"
    },
    {
      "url": "https://机场B订阅",
      "tag": "airportB",
      "enabled": true,
      "emoji": 0,
      "prefix": "B-",
      "User-Agent": "v2rayng"
    }
  ],
  "config_template": "default",
  "exclude_protocol": "ssr",
  "auto_set_outbounds_dns": { "proxy": "", "direct": "" },
  "Only-nodes": false,
  "gh": 0
}
```

### subscribes[]（必填，至少 1 条）

| 字段 | 类型 | 默认 | 说明 |
|---|---|---|---|
| `url` | string | 必填 | 订阅链接；支持 http(s)/base64/`vmess://` 等分享链接、clash YAML、sing-box JSON；也可是服务端本地文件（`file://` 或绝对路径，见下） |
| `tag` | string | `tag_1`、`tag_2`… | 订阅标识。模板里可用 `{tag}` 引用该订阅的节点；**必须唯一** |
| `enabled` | bool | `true` | 为 `false` 时跳过该订阅 |
| `emoji` | 0/1 | `1` | 是否按国别给节点名加国旗 emoji |
| `subgroup` | string | `""` | 子分组名；非空时该订阅会单独生成一个 selector 分组 |
| `prefix` | string | `""` | 节点名前缀 |
| `User-Agent` | string | `clash.meta` | 拉取订阅时使用的 UA（部分机场需要特定 UA，如 `clashmeta`） |
| `ex-node-name` | string | `""` | 需要过滤掉的节点关键词，多个用逗号或 `|` 分隔 |

### 顶层字段（可选）

| 字段 | 类型 | 默认 | 说明 |
|---|---|---|---|
| `config_template` | string | 空 | 见下方三种写法 |
| `exclude_protocol` | string | `ssr` | 排除的协议，逗号分隔（如 `ssr,hy2`） |
| `auto_set_outbounds_dns` | object | `{"proxy":"","direct":""}` | 自动补 DNS，填 DNS server 的 tag 才生效 |
| `Only-nodes` | bool | `false` | 为 `true` 时只输出节点数组，不套模板 |
| `auto_backup` | bool | `false` | 落盘时是否备份旧配置 |
| `gh` | int | `0` | GitHub 加速序号（从 1 开始），用于替换模板里 rule_set 的 GitHub 链接 |
| `subscribes`（缺省 `enabled`） | — | — | 未写 `enabled` 视为 true |

> 约束：`subscribes` 数量上限默认 10（环境变量 `MAX_SUBS` 可调）；
> `tag` 不能重复。
>
> **本地订阅文件**：`url` 可写 `file:///data/subs.txt` 或服务端已存在的绝对路径，
> 但必须位于 `LOCAL_DATA_DIR`（默认项目根目录，可用环境变量改）之内，越界返回 `400`。

### `config_template` 的写法

| 写法 | 示例 | 说明 |
|---|---|---|
| 留空 / 不写 | `"config_template": ""` | 使用默认模板 `config_template/default.json`（固定，不存在则报错） |
| 文件名 | `"config_template": "my_tpl"` | 读取 `config_template/my_tpl.json`；后缀 `.json` 可省略，也支持子目录如 `"custom/foo"` |
| 远程 URL | `"config_template": "https://example.com/tpl.json"` | 服务端 `GET` 这个地址并解析 |
| 内联对象 | `"config_template": { "outbounds": [...] }` | 整份模板 JSON 直接写在请求体里上传，服务端不读任何文件 |

> 文件名限定在 `config_template/` 目录内，禁止绝对路径与 `..` 目录穿越，越界返回 `400`。
> 内联模板至少需要包含 `outbounds` 字段。

### `tag` 用法

`tag` 是**订阅的标识 / 分组键**，不是节点名——它不影响节点最终显示，只用于归组、模板引用与去重校验。

- **归组**：每条订阅解析出的节点按它的 `tag` 收进 `nodes[tag]`。
- **模板引用**：模板里用 `{tag}` 占位符引用该订阅的节点。例：

  ```json
  { "tag": "MyGroup", "type": "selector", "outbounds": ["{airportA}", "direct"] }
  ```

  会把 `airportA` 这条订阅的节点填进 `MyGroup`。内置的 `default.json` 主要用 `{all}`
  （= 所有订阅的所有节点），所以**用默认模板时 `tag` 填什么都不影响分组**；
  只有自定义模板写了 `{tag}` 时才关键。
- **默认值**：留空时按顺序自动补 `tag_1`、`tag_2`…。
- **唯一性**：`tag` 必须唯一，重复返回 `400`。
- **subgroup**：若该订阅带 `subgroup`，`tag` 会被改写成 `<tag>-<子组名>-subgroup`，并额外生成一个 selector 分组。
- **与节点名无关**：节点名 = `prefix` + 原节点名 + `emoji`（国旗）。想改显示效果请用 `prefix` / `emoji`，不是 `tag`。
- **去重**：跨订阅按**节点名**全局去重，与 `tag` 无关。

示例——两条订阅各自成组，再用 `{tag}` 引用：

```json
{
  "subscribes": [
    {"url": "https://a.com/sub?token=AAA", "tag": "airportA", "prefix": "A-"},
    {"url": "https://b.com/sub?token=BBB", "tag": "airportB", "prefix": "B-"}
  ],
  "config_template": {
    "dns": {"servers": [], "rules": []},
    "route": {"rules": []},
    "outbounds": [
      {"tag": "A", "type": "selector", "outbounds": ["{airportA}"]},
      {"tag": "B", "type": "selector", "outbounds": ["{airportB}"]},
      {"tag": "Proxy", "type": "selector", "outbounds": ["A", "B", "direct"]},
      {"tag": "direct", "type": "direct"}
    ]
  }
}
```

> 模板占位符的完整展开规则（`{all}` / `{tag}` / `filter` / 子组）见
> [template-placeholders.md](template-placeholders.md)。

---

## 2. curl 用法

### 2.1 最简：单订阅

```bash
curl -s http://127.0.0.1:5000/config \
  -H 'Content-Type: application/json' \
  -d '{
        "subscribes": [
          {"url": "https://example.com/api/v1/client/subscribe?token=XXX"}
        ],
        "config_template": "default"
      }' \
  -o config.json
```

### 2.2 多订阅，每个订阅各自的 tag / ua / prefix

```bash
curl -s http://127.0.0.1:5000/config \
  -H 'Content-Type: application/json' \
  -d '{
        "subscribes": [
          {"url": "https://a.com/sub?token=AAA", "tag": "airportA",
           "ua": "clashmeta", "User-Agent": "clashmeta", "prefix": "A-", "emoji": 1},
          {"url": "https://b.com/sub?token=BBB", "tag": "airportB",
           "User-Agent": "v2rayng", "prefix": "B-", "emoji": 0,
           "ex-node-name": "官网,剩余流量"}
        ],
        "config_template": "default",
        "exclude_protocol": "ssr"
      }' \
  -o config.json
```

> `ua` 与 `User-Agent` 等价，写哪个都行（`ua` 是给习惯 URL 写法的用户留的别名）。

### 2.3 用文件承载请求体（推荐，避免 shell 转义/超长）

```bash
cat > payload.json <<'JSON'
{
  "subscribes": [
    {"url": "https://a.com/sub?token=AAA", "tag": "airportA", "prefix": "A-"},
    {"url": "https://b.com/sub?token=BBB", "tag": "airportB", "prefix": "B-"}
  ],
  "config_template": "default"
}
JSON

curl -s http://127.0.0.1:5000/config \
  -H 'Content-Type: application/json' \
  --data-binary @payload.json \
  -o config.json
```

#### `payload.json` 不在当前目录时如何指定

`--data-binary @路径` 里的路径由 **curl** 解析：相对路径相对于「运行 curl 时的当前目录」，
或以绝对路径指定。几种写法：

```bash
# 1) 绝对路径（最省心）
curl -s http://127.0.0.1:5000/config \
  -H 'Content-Type: application/json' \
  --data-binary @/home/me/configs/payload.json \
  -o /home/me/config.json

# 2) 相对于你运行 curl 的目录
cd /home/me && curl -s http://127.0.0.1:5000/config \
  -H 'Content-Type: application/json' \
  --data-binary @configs/payload.json -o config.json

# 3) 用变量拼路径
PAYLOAD=/some/where/payload.json
curl -s http://127.0.0.1:5000/config \
  -H 'Content-Type: application/json' \
  --data-binary @"$PAYLOAD" -o config.json

# 4) 管道 + 标准输入（@- 表示从 stdin 读）
cat /some/where/payload.json | curl -s http://127.0.0.1:5000/config \
  -H 'Content-Type: application/json' \
  --data-binary @- -o config.json
```

注意：

- **`@` 后面的 `~` 不会被 shell 展开**（Bash 只在单词开头或 `=`/`:` 之后展开 `~`），
  `@~/x.json` 会原样传给 curl 导致找不到文件。请改用 `@$HOME/x.json` 或绝对路径。
- 路径含空格或特殊字符时用引号：`--data-binary @"$HOME/my payload.json"`。
- `-o config.json` 同样是相对当前目录写出的；要落到别处就写绝对路径，如 `-o /path/config.json`。
- `@` 是 curl 自己的语法（从文件读 body），`@` 后必须紧跟文件名，可与 `-d`/`--data-binary` 搭配；
  用 `--data-binary` 可原样保留文件内容与新行。

### 2.4 只输出节点（不套模板）

```bash
curl -s http://127.0.0.1:5000/config \
  -H 'Content-Type: application/json' \
  -d '{"Only-nodes": true, "subscribes": [{"url": "https://a.com/sub?token=AAA"}]}'
```

### 2.5 使用本地模板文件

把自定义模板放到仓库的 `config_template/` 目录下（此目录也是内置模板所在处），然后：

```bash
# 文件：config_template/my_tpl.json
curl -s http://127.0.0.1:5000/config \
  -H 'Content-Type: application/json' \
  -d '{
        "subscribes": [{"url": "https://a.com/sub?token=AAA"}],
        "config_template": "my_tpl"
      }' \
  -o config.json
```

- `"my_tpl"` 与 `"my_tpl.json"` 等价；也可指向子目录，如 `"custom/my_tpl"`。
- 绝对路径（`/etc/...`）和 `../` 会被拒绝（返回 `400`），避免读取任意文件。

> 通过 CLI（`main.py`）直连时不受此限制：`--temp_json_file payload.json` 里
> `"config_template": "/abs/path/tpl.json"` 或 `"file:///abs/path/tpl.json"` 均可。

### 2.6 远程模板 + GitHub 加速

```bash
curl -s http://127.0.0.1:5000/config \
  -H 'Content-Type: application/json' \
  -d '{
        "subscribes": [{"url": "https://a.com/sub?token=AAA"}],
        "config_template": "https://raw.githubusercontent.com/you/repo/main/tpl.json",
        "gh": 1
      }' \
  -o config.json
```

### 2.7 内联模板 + 本地订阅文件

不需要在服务端准备任何文件：模板直接写在请求体里（`config_template` 是个对象）：

```json
{
  "subscribes": [
    {"url": "https://a.com/sub?token=AAA", "tag": "A"},
    {"url": "file:///data/subs-b.txt", "tag": "B"}
  ],
  "config_template": {
    "dns": { "servers": [], "rules": [] },
    "route": { "rules": [] },
    "outbounds": [
      { "tag": "Proxy", "type": "selector", "outbounds": ["{all}"] },
      { "tag": "auto", "type": "urltest", "outbounds": ["{all}"] },
      { "tag": "direct", "type": "direct" }
    ]
  }
}
```

- `config_template` 为对象时，服务端直接使用，**不会去读任何模板文件**。
- 内联模板至少要有 `outbounds`。其余字段（`dns`/`route`/`inbounds`）按 sing-box 模板常规写。
- 上例第二个订阅用 `file:///data/subs-b.txt` 指向服务端本地文件；
  它必须位于 `LOCAL_DATA_DIR` 内（见 §4），否则返回 `400`。

### 2.8 直接喂给 sing-box

```bash
curl -s http://127.0.0.1:5000/config \
  -H 'Content-Type: application/json' \
  --data-binary @payload.json \
  -o /etc/sing-box/config.json

sing-box check -c /etc/sing-box/config.json && sing-box run -c /etc/sing-box/config.json
```

---

## 3. 响应

- 成功：`200`，响应体为完整 sing-box 配置（可直接保存为 `config.json`）。
- 失败：返回 JSON 错误对象，HTTP 状态码见下：

| 状态码 | 场景 | body 示例 |
|---|---|---|
| `400` | 请求体不是 JSON / 字段不合法 / tag 重复 / 超过订阅上限 | `{"status":"error","message":"subscribes[0] 缺少 url"}` |
| `502` | 拉取订阅或生成失败 / 超时 | `{"status":"error","message":"生成超时（>300s）"}` |
| `500` | 其它异常 | `{"status":"error","message":"生成失败：..."}` |

> 解析失败时，服务端会把 `main.py` 的 stderr 末尾回填到 `message`，便于排查。

---

## 4. 环境变量

| 变量 | 默认 | 说明 |
|---|---|---|
| `MAX_SUBS` | `10` | 单次请求允许的最大订阅数 |
| `GENERATE_TIMEOUT` | `300` | 子进程生成超时（秒） |
| `LOCAL_DATA_DIR` | 项目根目录 | API 允许读取的本地文件根目录（订阅文件用）；越界返回 `400` |
| `PORT` | `5000` | `python api/app.py` 监听端口 |

---

## 5. 与旧版 URL 写法的对照（迁移）

旧版 GET `/config/<path:url>` 已移除。迁移对照：

| 旧写法 | 新写法 |
|---|---|
| `/config/https://a.com/sub?token=AAA&emoji=1&prefix=A-` | `{"subscribes":[{"url":"https://a.com/sub?token=AAA","emoji":1,"prefix":"A-"}]}` |
| `/config/a|b|c&tag=A,B,C&ua=x,y,z` | `{"subscribes":[{"url":"a","tag":"A","User-Agent":"x"},{"url":"b","tag":"B","User-Agent":"y"},{"url":"c","tag":"C","User-Agent":"z"}]}` |
| `&file=2` | 旧序号已去除，改用文件名：`"config_template": "default"` |
| `&eps=ssr,hy2` | `"exclude_protocol": "ssr,hy2"` |
| `&gh=1` | `"gh": 1` |

这样每个订阅的 `tag / ua / prefix / emoji / enn / subgroup / enabled` 都能独立设置，
且订阅 URL 里的 `&`、`?`、`=&` 不会再被误解析。

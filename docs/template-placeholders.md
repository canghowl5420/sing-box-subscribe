# 模板占位符与合成配置说明

本文说明 **订阅节点是如何被"填"进 `config_template/*.json` 模板**的，即 `main.py` 中
`combin_to_config()` 及其辅助函数的行为。适用对象：想自己改模板、写 `filter`、或排查
"为什么某个分组是空的 / 多了个分组 / 少了节点"的人。

> 代码位置：`main.py`
> - `combin_to_config(config, data)` —— 合成主函数
> - `pro_node_template(nodes, outbound, group)` —— 单个分组的节点展开
> - `nodes_filter(nodes, filter, group)` / `action_keywords(nodes, action, keywords)` —— 过滤
> - `set_proxy_rule_dns(config)` / `pro_dns_from_route_rules(rule)` —— 自动 DNS
> - `process_subscribes()` —— 上游产出的 `data`

---

## 1. 两个核心数据结构

### 1.1 模板 `config`

就是 `config_template/*.json` 反序列化后的 dict，包含 `dns` / `route` / `inbounds` /
`outbounds` 等。其中 `outbounds` 里会有一批 **selector / urltest 分组**，它们的
`outbounds` 字段里写着**占位符**，例如：

```json
{ "tag": "Proxy",     "type": "selector", "outbounds": ["auto", "direct", "{all}"] },
{ "tag": "HongKong",  "type": "selector", "outbounds": ["{all}"],
  "filter": [{ "action": "include", "keywords": ["🇭🇰|HK|hk|香港|港|HongKong"] }] },
{ "tag": "auto",      "type": "urltest",  "outbounds": ["{all}"],
  "filter": [{ "action": "exclude", "keywords": ["网站|地址|剩余|过期|时间|有效"] }] },
{ "tag": "direct",    "type": "direct" }
```

### 1.2 节点表 `data`

`process_subscribes()` 的产出，结构是 `{订阅tag: [sing-box outbound 对象, ...]}`：

```json
{
  "airportA": [
    { "tag": "🇭🇰 香港01", "type": "vmess", "server": "...", ... },
    { "tag": "🇺🇸 美国01", "type": "vmess", ... }
  ],
  "airportB": [ { "tag": "🇭🇰 香港02", "type": "trojan", ... } ]
}
```

> `data` 的 key 默认是订阅的 `tag`（`tag_1` / `tag_2` / 自定义）；若该订阅配置了
> `subgroup`，key 会变成 `tag-子组名-subgroup`（见 §4.1）。
> 每个节点对象最终会被**原样追加**到 `config["outbounds"]` 末尾，所以它必须是合法的
> sing-box outbound。

---

## 2. 占位符语法

占位符只出现在某个出站的 `outbounds` 数组里，用花括号包裹。规则如下：

| 写法 | 含义 | 展开为 |
|---|---|---|
| `"{all}"` | 所有订阅的所有节点 | 遍历 `data` 每个分组，把这些节点的 **tag** 依次填入（并逐个套用该出站的 `filter`） |
| `"{airportA}"` | 指定订阅 tag 的节点 | `data["airportA"]` 里节点的 tag 列表（同样套用 `filter`） |
| `"auto"` / `"direct"` / `"其他字面量"` | 普通出站引用 | 原样保留（指向同文件里已存在的出站 tag） |
| `"{不存在的key}"` | 未匹配到任何分组 | **直接消失**（不会报错，也不占位） |

要点：

- **花括号是唯一的占位符标记**。只要字符串以 `{` 开头、以 `}` 结尾，就按占位符处理；
  否则一律当字面 tag 原样保留。
- 展开后会做**同层去重**：同一个 `outbounds` 数组里重复出现的项只保留第一次（见 §5）。
- **`{all}` 会"吃掉"同数组里的其它 `{...}` 占位符**：见 §4.2 的预清理步骤。

---

## 3. 总体流程

```
combin_to_config(config, data)
 ├─ 0. 子组(subgroup)预处理            → 为每个 subgroup 造一个 selector
 ├─ 1. {all} 预清理                    → 含 {all} 的出站，丢掉其它 {xxx} 占位符
 ├─ 2. 逐出站展开占位符                → pro_node_template() 套 filter 后取 tag
 │       └─ 空结果回退为 direct
 ├─ 3. 删除已用过的 filter 字段
 ├─ 4. config.outbounds = 模板出站 + 所有节点对象
 ├─ 5. 自动补齐 DNS（可选，需配置 auto_set_outbounds_dns）
 └─ 6. wireguard 出站搬到 endpoints（sing-box 1.11+ 兼容）
```

> 旁路：若 `providers["Only-nodes"]` 为真，**不会调用 `combin_to_config`**，
> 而是把所有节点对象拍平成一个数组直接输出（只出节点、不要模板）。

---

## 4. 逐步拆解

### 4.0 前置：`process_subscribes` 做了什么

在合成之前，每个节点已经过：`prefix` 前缀 → `emoji` 国旗重命名 → `ex-node-name` 过滤
（`nodefilter`）→ 按 tag 归组。最后 `proDuplicateNodeName(nodes)` 做**全局重名去重**
（重名的节点名会追加 ` 2`、` 3` …）。所以到 `combin_to_config` 这一步，`data` 里每个节点的
`tag` 都是唯一的。

### 4.1 子组预处理（subgroup）

当订阅配置了 `subgroup` 时，`process_subscribes` 会把它的 tag 改写成
`<原tag>-<子组名>-subgroup`。合成阶段遇到带 `subgroup` 的 data key 时：

```python
sub_name = (group.rsplit("-", 1)[0]).rsplit("-", 1)[-1]   # 取出"子组名"
# 1) 在 Proxy 组里，把 "{all}" 替换成 sub_name；若无 {all} 则插入
# 2) 新建一个 selector：{"tag": sub_name, "type": "selector",
#                        "outbounds": ["{<原group key>}"]}
#    插入到 outbounds 列表倒数第 2 个位置（即 auto、direct 之前）
```

例：`data` 里键为 `airportA-香港专线-subgroup`，模板 `Proxy = ["auto","direct","{all}"]` →
`Proxy = ["auto","direct","香港专线"]`，并新增出站
`{"tag":"香港专线","type":"selector","outbounds":["🇭🇰 HK-A"]}`。

> ⚠️ **注意**：替换是"把 `{all}` 元素改成子组名"，不是追加。因此**一旦用 subgroup，
> `Proxy` 里的 `{all}` 槽位就被子组占用**，非 subgroup 订阅的普通节点不会再出现在
> `Proxy` 里（它们仍会出现在 `auto` 以及各自的 `{all}` 分组里）。请按需调整模板。

### 4.2 `{all}` 预清理

对每个出站，如果它的 `outbounds` 里包含 `"{all}"`，会先做一次过滤，**只保留 `{all}` 和
非花括号的字面量，丢弃其它 `{xxx}` 占位符**。

```python
if '{all}' in po["outbounds"]:
    o1 = []
    for item in po["outbounds"]:
        if item.startswith('{') and item.endswith('}'):
            if item[1:-1] == 'all':
                o1.append(item)          # 只留 {all}
        else:
            o1.append(item)              # 字面量保留
    po["outbounds"] = o1
```

原因：`{all}` 已包含全部节点，其它 `{tag}` 属冗余。
副作用：`["{airportA}", "{all}"]` 会变成只展开 `{all}`，`{airportA}` 被丢弃。

### 4.3 逐项展开

```python
for oo in po["outbounds"]:
    if oo in check_dup: continue         # 同层去重
    check_dup.append(oo)
    if oo.startswith('{') and oo.endswith('}'):
        key = oo[1:-1]
        if data.get(key):
            t_o.extend(pro_node_template(data[key], po, key))
        elif key == 'all':
            for group in data:           # 按 data 的插入顺序 = 订阅顺序
                t_o.extend(pro_node_template(data[group], po, group))
        # else: 未知占位符 → 什么都不加
    else:
        t_o.append(oo)                   # 字面 tag 原样保留
```

`pro_node_template` 做的事很简单：**先套该出站的 `filter`，再把剩下节点的 `tag` 取出来**：

```python
def pro_node_template(data_nodes, config_outbound, group):
    if config_outbound.get('filter'):
        data_nodes = nodes_filter(data_nodes, config_outbound['filter'], group)
    return [node.get('tag') for node in data_nodes]
```

注意 `group` 传入的是**当前正在展开的 data key**（对 `{all}` 就是每个订阅 tag）。
它只用于 `filter` 的 `for` 判定，见 §6。

### 4.4 空分组回退

展开后若某出站的 `outbounds` 为空，会自动补上模板里 `type == "direct"` 的 tag，
并打印告警，避免因空 selector 导致 sing-box 启动失败：

```python
if len(t_o) == 0:
    t_o.append(direct_item['tag'])
```

### 4.5 删除 `filter`

`filter` 是**模板专用的编译期指令**，不是 sing-box 的合法字段。用完即删：

```python
if po.get('filter'):
    del po['filter']
```

### 4.6 拼接节点

```python
config["outbounds"] = config_outbounds + temp_outbounds
```

前半是"模板出站"（selector/urltest/direct…），后半是所有真实节点对象。
**节点对象本身也要是合法 outbound**，sing-box 会直接使用它们。

### 4.7 自动 DNS（可选）

仅当 `providers["auto_set_outbounds_dns"]` 里 `proxy`、`direct` 两个 tag 都非空，
且它们确实存在于 `config.dns.servers` 时，才执行 `set_proxy_rule_dns`：

- 为 `route.rules` 里出现过的非 `direct`/`block`/`dns-out` 出站，各生成一个 DNS server
  （tag = `<出站>_dns`，`detour = <出站>`），并追加到 `dns.servers`；
- 为每条 route 规则生成对应的 DNS 规则（`pro_dns_from_route_rules` 只搬运两边同名的字段，
  如 `domain`/`domain_suffix`/`geosite`/`port`/`process_name`…）；
- `logical` 类型规则会递归展开其子规则；
- 最后对 `dns.rules` 去重、并把生成的 server 追加进 `dns.servers`。

目的是**让 DNS 查询与流量走同一个出站**，避免 DNS 泄漏。

### 4.8 WireGuard → endpoints

sing-box 1.11+ 把 WireGuard 从 `outbounds` 移到了顶层 `endpoints`。这里自动兼容：
把所有 `type == "wireguard"` 的出站收集起来，在 `config` 的 `outbounds` 键之后插入一个
`endpoints` 键，并把它们从 `outbounds` 中移除。

---

## 5. 同层去重（check_dup）

展开前的原始项（占位符字符串或字面 tag）会先比对去重。也就是说：

```
outbounds: ["{all}", "{all}"]   → 只展开一次
outbounds: ["auto", "auto"]     → 只保留一个 "auto"
```

去重发生在**展开之前**、比较的是**原始字符串**，所以不同占位符展开出的同名节点不会在
这一步被去掉（节点级重名已在 `proDuplicateNodeName` 处理过）。

---

## 6. `filter` 语义

`filter` 是一个数组，**按顺序**对节点执行；每项可带 `for` 限定生效的分组。

```json
"filter": [
  { "action": "include", "keywords": ["🇭🇰|香港"] },
  { "action": "exclude", "keywords": ["过期"], "for": ["tag_1"] }
]
```

- `action`：`include`（保留匹配项）或 `exclude`（剔除匹配项）。
- `keywords`：字符串数组，会被 `'|'.join(...)` 成一个**正则**，对节点 `tag` 做
  `re.search`（非全匹配）。空/纯空白字符串表示**不过滤**。
- `for`：可选。若存在，则当传入的 `group`（即当前展开的 data key）**不在** `for` 列表里时，
  该条过滤被跳过。用于"只对某个订阅生效"。

匹配 + 动作的判定逻辑（XOR 技巧）：

```python
flag = (action == 'exclude')                 # exclude 时 flag=True
match = bool(re.search(pattern, node['tag']))
if match ^ flag: temp_nodes.append(node)     # include: 匹配保留；exclude: 不匹配保留
```

> `keywords` 里的正则会组合成 `a|b|c`。若关键词本身含特殊字符，需自行转义。
> 因为用的是 `re.search`，关键词 `US` 也会命中 `RUSSIA` 之类，写规则时用边界或更具体词。

---

## 7. 坑位清单（务必留意）

1. **`{all}` 会丢弃同数组的其它占位符**（§4.2）。不要写 `["{a}", "{all}"]` 期望两者都展开。
2. **未知 `{key}` 静默消失**，不报错。占位符拼错会得到空分组 → 被回退成 `direct`。
3. **subgroup 会占用 `Proxy` 的 `{all}` 槽位**（§4.1），普通订阅节点不再进 `Proxy`。
4. **空分组回退为 `direct`**：分组没人匹配到节点时不是报错，而是变直连，注意别误以为生效。
5. **`filter` 用完即删**，最终配置里不应出现 `filter`；若出现说明该出站没有 `outbounds`
   字段（删除逻辑在 `if po.get("outbounds")` 内）。
6. **正则而非精确匹配**：`keywords` 会 `join("|")` 成正则，注意特殊字符与子串误伤。
7. **顺序即订阅顺序**：`{all}` 按 `data` 的插入顺序（= `providers.subscribes` 顺序）展开，
   节点在配置里的先后顺序由此决定。

---

## 8. 实操示例

### 输入

模板（节选）：

```json
"outbounds": [
  { "tag": "Proxy", "type": "selector", "outbounds": ["auto", "direct", "{all}"] },
  { "tag": "HongKong", "type": "selector", "outbounds": ["{all}"],
    "filter": [{ "action": "include", "keywords": ["🇭🇰|HK|香港"] }] },
  { "tag": "US", "type": "selector", "outbounds": ["{all}"],
    "filter": [{ "action": "include", "keywords": ["🇺🇸|US|美国"] }] },
  { "tag": "auto", "type": "urltest", "outbounds": ["{all}"],
    "filter": [{ "action": "exclude", "keywords": ["过期"] }] },
  { "tag": "direct", "type": "direct" }
]
```

`data`：

```json
{
  "airportA": [
    { "tag": "🇭🇰 香港01", "type": "vmess" },
    { "tag": "🇺🇸 美国01", "type": "vmess" }
  ],
  "airportB": [
    { "tag": "🇭🇰 香港02", "type": "trojan" },
    { "tag": "过期节点", "type": "trojan" }
  ]
}
```

### 输出（节选）

```json
[
  { "tag": "Proxy",    "type": "selector",
    "outbounds": ["auto", "direct", "🇭🇰 香港01", "🇺🇸 美国01", "🇭🇰 香港02", "过期节点"] },
  { "tag": "HongKong", "type": "selector", "outbounds": ["🇭🇰 香港01", "🇭🇰 香港02"] },
  { "tag": "US",       "type": "selector", "outbounds": ["🇺🇸 美国01"] },
  { "tag": "auto",     "type": "urltest",  "outbounds": ["🇭🇰 香港01", "🇺🇸 美国01", "🇭🇰 香港02"] },
  { "tag": "direct",   "type": "direct" },
  { "tag": "🇭🇰 香港01", "type": "vmess" },
  { "tag": "🇺🇸 美国01", "type": "vmess" },
  { "tag": "🇭🇰 香港02", "type": "trojan" },
  { "tag": "过期节点", "type": "trojan" }
]
```

可见：`HongKong`/`US` 只收匹配节点；`auto` 排除了"过期"；`filter` 字段已消失；
节点对象被追加在末尾。

若开启自动 DNS（`auto_set_outbounds_dns.proxy = "proxy_dns"`，且 route 里有 `Proxy` 出站），
还会额外生成：

```json
"dns": {
  "servers": [ ..., { "tag": "Proxy_dns", "address": "tls://1.1.1.1", "detour": "Proxy" } ],
  "rules": [ { "domain_suffix": [".example.com"], "server": "Proxy_dns" } ]
}
```

---

## 9. 自测方法

想在不联网的情况下验证模板行为，可写个小脚本直接调 `combin_to_config`：

```python
import copy, json, sys
sys.path.insert(0, '.')
import main
main.providers = {"auto_set_outbounds_dns": {"proxy": "", "direct": ""}}  # 关掉自动 DNS

template = json.load(open('config_template/default.json'))
data = {
    "airportA": [{"tag": "🇭🇰 香港01", "type": "vmess"},
                 {"tag": "🇺🇸 美国01", "type": "vmess"}],
    "airportB": [{"tag": "🇭🇰 香港02", "type": "trojan"}],
}
out = main.combin_to_config(copy.deepcopy(template), data)
for o in out["outbounds"]:
    if o.get("type") in ("selector", "urltest"):
        print(o["tag"], "->", o["outbounds"])
```

依赖：`pip install -r requirements.txt`（`flask` 是 `main.py` 顶部 `from api.app import TEMP_DIR`
的间接依赖）。

# sing-box-subscribe

根据配置模板生成 sing-box 使用的 `config.json`。主要用于给使用 `clash_mode` 配置的用户，把订阅节点加入配置文件。

它并不适合完全不了解 sing-box 配置文件的人。至少你要了解 outbound、DNS server、DNS rules、路由规则；最好理解 clash 的分组方式。

请参考：[http://sing-box.sagernet.org/configuration](http://sing-box.sagernet.org/configuration/)。

**默认不解析 SSR 协议脚本。如果订阅链接里包含 SSR 协议，会直接报错！！！**

**Vercel 服务器的处理时间上限是 10 秒。如果 clash 文件太大，会因超时而失败！！！**

> **本分支已把接口改为 `POST /config`（请求体为 JSON）**，每个订阅的 `tag`、`User-Agent`、`prefix`、`emoji`、`ex-node-name`、`subgroup` 等都可以独立设置，不再需要把订阅和参数拼进 URL。
> 用法、JSON 格式与 curl 示例见 [docs/api.md](../docs/api.md)。
> 下面关于 `/config/URL_LINK?...` 的说明是**旧写法，已移除**。

## Feature

**sing-box 网页解析器**

用你自己搭建的网站实现配置的实时更新，可作为 sing-box 的远程链接。

例如我搭建的网站 [https://sing-box-subscribe.vercel.app](https://sing-box-subscribe.vercel.app)，在网站后面加 `/config/URL_LINK`，这里的 `URL_LINK` 指订阅链接：

```
https://xxxxxxx.vercel.app/config/https://xxxxxxsubscribe?token=123456&file=https://github.com/Toperlock/sing-box-subscribe/raw/main/config_template/config_template_groups_rule_set_tun.json
```

### 2024.2.16 更新：支持在链接后追加 `emoji`、`tag`、`prefix`、`ua`、`file`、`eps`、`enn` 参数。多个参数用 `&` 连接。用法与 `providers.json` 里的参数相同

`/config/URL_LINK&emoji=1&prefix=♥&ua=v2rayng&eps=vmess,hy2&enn=网站,剩余流量&file=https://xxxxxxxxx.json`

上例表示：启用 emoji、在节点名前加 ♥、使用 v2rayng 的 User-Agent，并用 `https://xxxxxxxxx.json` 作为生成的 sing-box 配置模板。

示例：https://sing-box-subscribe.vercel.app/config/https://gist.githubusercontent.com/Toperlock/b1ca381c32820e8c79669cbbd85b68ac/raw/dafae92fbe48ff36dae6e5172caa1cfd7914cda4/gistfile1.txt&file=https://github.com/Toperlock/sing-box-subscribe/raw/main/config_template/config_template_groups_rule_set_tun.json

### 2023.11.04 更新：可以处理两条订阅链接，格式为 `/config/URL` 编码后，`emoji`、`tag`、`prefix`、`UA` 参数不能写（2024.1.1 起支持 3 条订阅链接）

用 `|` 连接两条订阅链接，然后 [URL 编码](https://www.urlencoder.org/) 后放到 `config/` 之后，如下图所示：

<div align="left">
  <img src="https://github.com/Toperlock/sing-box-subscribe/assets/86833913/5ed8e9de-3296-4dfc-ad65-2e181017829e" alt="how-to-use" width="50%" />
</div>

示例：https://sing-box-subscribe.vercel.app/config/https%3A%2F%2Fgist.githubusercontent.com%2FToperlock%2Fb1ca381c32820e8c79669cbbd85b68ac%2Fraw%2Fdafae92fbe48ff36dae6e5172caa1cfd7914cda4%2Fgistfile1.txt%7Chttps%3A%2F%2Fgist.githubusercontent.com%2FToperlock%2Ffa2fdc5f827ff7d288c23d568db75412%2Fraw%2F6c3b725da347f57b0021b806dfca5f51e1660746%2F1.yaml

### 2026.10 更新（本分支 fork）：多订阅下，所有"原先仅单订阅可用"的参数现在都支持按订阅分别设置

当用 `|` 连接多条订阅链接时，原先只对单订阅生效的参数（`tag`、`ua`/`UA`、`prefix`、`emoji`、`enn`）现在既可以是：

- **单个值** → 对**所有**订阅生效；也可以是
- **逗号分隔的列表** → 按订阅顺序**一一对应**。

`/config/URL_LINK_1|URL_LINK_2|URL_LINK_3&tag=airportA,airportB,airportC&ua=clashmeta,v2rayng,sing-box&prefix=A-,B-,C-&emoji=1,0,1&enn=网站,过期,剩余&file=https://xxxxxxxxx.json`

| 参数 | 含义 | 默认值 |
|---|---|---|
| `tag` | 订阅标识（模板里用 `{airportA}` 引用） | `tag_1` / `tag_2` / `tag_3` |
| `ua` / `UA` | 拉取该订阅时使用的 `User-Agent` | `clash.meta` |
| `prefix` | 该订阅的节点名前缀 | 无 |
| `emoji` | `1`/`0`，是否在节点名前加国旗 emoji | `1` |
| `enn` | `ex-node-name`：需要过滤掉的节点关键词 | 无 |

- 列表可以用**原始逗号**，也可以用 URL 编码的 `%2C`，两种都支持。
- 列表里**留空**（例如 `tag=A,,C`）表示该位保持默认；列表比订阅数短时，剩余订阅保持默认。
- **传单个值**表示对**所有**订阅生效（例如 `&emoji=0` 让所有订阅都不加国旗，`&ua=single-ua` 所有订阅都用它）。

示例：

`/config/https://a.com/sub?token=1|https://b.com/sub?token=2&tag=机场A,机场B&ua=clashmeta,v2rayng&prefix=[A] ,[B]&emoji=1,0&enn=过期&file=https://xxxxxxxxx.json`

> 说明：本段为 fork 新增功能的说明，中文文档同样包含；英文版见 [README.md](./README.md)。

### 2023.11.10 更新：`file` 参数可简写为数字 `1`、`2`，表示使用 GitHub 仓库中提供的模板序号

示例：https://sing-box-subscribe.vercel.app/config/https://gist.githubusercontent.com/Toperlock/b1ca381c32820e8c79669cbbd85b68ac/raw/dafae92fbe48ff36dae6e5172caa1cfd7914cda4/gistfile1.txt&file=2

### 演示视频

|网页解析订阅链接（v2/clash/sing-box）|
|-----------------------------|
|<video controls width="250" src="https://github.com/Toperlock/sing-box-subscribe/assets/86833913/a583c443-0c7b-454e-aaf2-f0a7159b276a"></video>|

## 目录

[操作视频](https://github.com/Toperlock/sing-box-subscribe/blob/main/instructions/README.md#-demonstration-video)

[参数含义](https://github.com/Toperlock/sing-box-subscribe/tree/main/instructions#providersjson-file)

[模板详解](https://github.com/Toperlock/sing-box-subscribe/tree/main/instructions#config-template-files)

[在 Windows 上运行 sing-box](https://github.com/Toperlock/sing-box-subscribe/tree/main/instructions#windows-sing-box-usage)

## 支持的协议

|  协议  | V2 订阅 | Clash 订阅 | 标准 URI 格式 | SingBox 格式 |
|  :----  | :----: | :----: | :----: | :----: |
| http  | ✅ | ✅ | ✅ | ✅ |
| socks5  | ✅ | ✅ | ✅ | ✅ |
| shadowsocks  | ✅ | ✅ | ✅ | ✅ |
| shadowsocksR  | ✅ | ✅ | ✅ | sing-box 默认不支持 |
| vmess  | ✅ | ✅ | ✅ | ✅ |
| trojan  | ✅ | ✅ | ✅ | ✅ |
| vless  | ✅ | ✅ | ✅ | ✅ |
| tuic  | ✅ | ✅ | ✅ | ✅ |
| hysteria  | ✅ | ✅ | ✅ | ✅ |
| hysteria2  | ✅ | ✅ | ✅ | ✅ |
| wireguard  | ✅ | ✅ | ✅ | ✅ |

~不支持解析 clash 订阅~ 目前只实现了上表中打勾协议的分享链接（**v2 或 clash 订阅格式**）解析。你可以自己写协议解析器，例如 `vless.py`（文件名必须与协议名一致），放到 `parsers` 目录下。`vless.py` 里必须包含一个 `parse` 函数。

**本脚本仅供个人使用。我用 [yacd](https://yacd.metacubex.one)（iOS 请使用 http://yacd.metacubex.one）来管理节点切换（outbound 类型为 `urltest` 和 `selector`），并像 clash 一样分流，非常方便。如果你有类似需求，可以试试。如果你有新的功能需求或使用中遇到错误，请提交 issue，不要去骚扰 sing-box。**

**脚本可以部署到 Vercel 上以网页方式运行，也可以下载源码在本地运行。请使用你自己部署的网站来生成 sing-box 配置。**

# 一、服务端部署

## 快速开始

1. 点击本项目右上角的 fork 按钮，把项目 fork 到你自己的仓库；
2. 点击右侧按钮开始部署：
   [![Deploy with Vercel](https://vercel.com/button)](https://vercel.com/new)，直接用 GitHub 账号登录；[详见教程](../docs/vercel-cn.md#how-to-create-a-new-project)。
3. 部署完成后即可使用；
4. （可选）[绑定自定义域名](https://vercel.com/docs/concepts/projects/domains/add-a-domain)：Vercel 分配的域名 DNS 在某些地区被污染，绑定自定义域名可直连。

### 开启自动更新

> 如果遇到 Upstream Sync 执行报错，请手动点击一次 Sync Fork！

fork 项目后，由于 GitHub 的限制，你需要手动进入你 fork 项目的 Actions 页面，启用 Workflows，并启用 Upstream Sync Action，这样就能开启每小时自动更新：

![AutoUpdate](https://github.com/Toperlock/ChatGPT-Next-Web/raw/main/docs/images/enable-actions.jpg)

![Enable Automatic Updates](https://github.com/Toperlock/ChatGPT-Next-Web/raw/main/docs/images/enable-actions-sync.jpg)

### 手动更新代码

如果你想立刻手动更新，请参考 [GitHub 文档](https://docs.github.com/en/pull-requests/collaborating-with-pull-requests/working-with-forks/syncing-a-fork) 了解如何将 fork 项目与上游代码同步。

你可以 star/watch 本项目或关注作者，以便及时收到新功能通知。

## 网页操作步骤

[示例网站](https://sing-box-subscribe.vercel.app/)。打开你部署的网站，编辑右侧 `编辑服务器 TEMP_JSON_DATA` 框的内容，点击 `保存`，在左上角选择配置模板，然后点击 `生成配置文件`。👉🏻[参数填写说明](https://github.com/Toperlock/sing-box-subscribe/tree/main/instructions#providersjson-file)

iOS 可用快捷指令复制网页内容；内容太多时可选择下载文件，自行解决文件后缀问题。👉🏻[快捷指令安装](https://www.icloud.com/shortcuts/75fd371e0aa8438a89f715238a21ee68)

Android 用 Chrome 浏览器打开网页生成配置文件（请先在浏览器 设置-无障碍 中缩小网页），长按内容 → 全选 → 分享到代码编辑器，检查编辑器显示的内容是否完整。👉🏻[编辑器安装](https://mt2.cn/download/)

**注意：点击保存后要尽快去"生成配置文件"，否则你填的内容会留在网页上，别人打开网站时能看到。目前暂没想到好的解决办法。**

<div align="left">
  <img src="https://github.com/Toperlock/sing-box-subscribe/assets/86833913/f794806c-edfc-4951-a216-6e38646f3791" alt="how-to-use" width="50%" />
</div>

## 🎬 演示视频

|网页解析订阅链接|网页解析 URI 链接|
|-----------------------------|-----------------------------|
|<video controls width="250" src="https://github.com/Toperlock/sing-box-subscribe/assets/86833913/9f8f1a70-58b1-4117-a650-f956d9249e43"></video>|<video controls width="250" src="https://github.com/Toperlock/sing-box-subscribe/assets/86833913/63e180ad-eead-433f-8ee8-73055dafbd56"></video>|

|Android Chrome 缩小页面|网页直接解析 base64|
|-----------------------------|-----------------------------|
|<video controls width="250" src="https://github.com/Toperlock/sing-box-subscribe/assets/86833913/cb149206-307f-4de8-9968-9832dcf8268a"></video>|<video controls width="250" src="https://github.com/Toperlock/sing-box-subscribe/assets/86833913/0081f055-2cd4-46bb-a4a9-7aac7d5f93a5"></video>|

|本地解析订阅链接|本地解析 URI 链接|
|-----------------------------|-----------------------------|
|<video controls width="250" src="https://github.com/Toperlock/sing-box-subscribe/assets/86833913/12da95a3-aae9-4ae4-ab88-774ed54f3217"></video>|<video controls width="250" src="https://github.com/Toperlock/sing-box-subscribe/assets/86833913/7e93568d-ece6-4cba-8dd0-bc5b5e64ade7"></video>|

# 二、本地安装
### 在你的电脑上安装 [Python](https://www.python.org/) 3.10 或更高版本。确保把 Python 加入系统环境变量（按 Google 的安装步骤操作）。

<div align="left">
  <img src="https://github.com/Toperlock/sing-box-subscribe/assets/86833913/f387322b-a602-40df-b3b6-95561329f2f8" alt="install" width="60%" />
</div>

### 在终端输入以下命令安装依赖（Mac 上把 `pip` 换成 `pip3`）：

```
pip install -r requirements.txt
```

<div align="left">
  <img src="https://github.com/Toperlock/sing-box-subscribe/assets/86833913/0fc03b49-4c57-4ef3-a4fc-044c1a108d75" alt="install" width="60%" />
</div>

### 下载 `sing-box-subscribe` 项目，打开终端进入项目目录（可以直接在文件路径栏输入 `cmd`）。

<div align="left">
  <img src="https://github.com/Toperlock/sing-box-subscribe/assets/86833913/73f05ba8-105c-4f10-8e6c-16e27f26c084" alt="run" width="60%" />
</div>

### 把你的订阅链接填入 `providers.json`，编辑 `config_template_groups_tun.json` 模板文件，编辑好后用以下命令运行脚本：

```
python main.py
```

或者你可以用 `template_index` 直接指定模板，`0` 表示第一个模板（no flask 不支持此参数）：

```
python main.py --template_index=0
```

Windows 系统建议把命令写进一个批处理程序里执行。

使用前，请先编辑 `providers.json` 文件和 `config_template` 目录下的 `.json` 模板文件。

内置模板：`default.json`（默认，适配较新版 sing-box）与 `sb-config-1.12.json`（适配 sing-box 1.12）。`default.json` 会按地区过滤节点：
* 实现 `Openai` 路由规则
* 实现 `Youtube` 路由规则
* 实现 `Google` 路由规则
* 实现 `Github` 路由规则
* 实现 `Telegram` 路由规则
* 实现 `Twitter` 路由规则
* 实现 `Facebook` 路由规则
* 实现 `Instagram` 路由规则
* 实现 `Bilibili` 路由规则
* 实现 `Bahamut` 路由规则
* 实现 `Spotify` 路由规则
* 实现 `TikTok` 路由规则
* 实现 `Netflix` 路由规则
* 实现 `Disney+` 路由规则
* 实现 `Apple` 路由规则
* 实现 `Amazon` 路由规则
* 实现 `Microsoft` 路由规则
* 实现 `Game` 路由规则
* 实现 `Hbo` 路由规则
* 实现 `Prime Video` 路由规则


# providers.json 文件
在这个文件里，你可以添加订阅链接和基础设置。
```json
{
    "subscribes":[
        {
            "url": "https://4gviet.com/api/v1/client/subscribe?token=xx",
            "tag": "airport1_tag", //可以保持默认不改
            "enabled": true, //是否转换该链接
            "emoji": 1, //是否添加国旗 emoji
            "subgroup": "",
            "prefix": "", //不添加节点名前缀
            "ex-node-name": "网站|流量|过期", //过滤包含关键词的节点
            "User-Agent":"clashmeta" //设置浏览器 UA
        },
        {
            "url": "https://5gtocdocao.com/api/v1/client/subscribe?token=xx",
            "tag": "airport2_tag", //可以保持默认不改
            "enabled": false, //不转换该链接
            "emoji": 0, //不添加国旗 emoji
            "subgroup": "named", //给订阅链接命名
            "prefix": "❤️node_name prefix - ", //添加节点名前缀
            "User-Agent":"clashmeta" //设置浏览器 UA
        }
    ],
    "auto_set_outbounds_dns":{
        "proxy": "",
        "direct": ""
    },
    "save_config_path": "./config.json",
    "auto_backup": false,
    "exclude_protocol": "ssr", //不解析 ssr 节点！！！
    "config_template": "", //自定义正确的网页 json 配置模板链接
    "Only-nodes": false //是否只输出节点信息
}
```
- `url`：必填。

> 支持普通 V2 订阅链接（**内容为 base64 编码**）

> 支持 clash 订阅链接

> 支持 sing-box 订阅链接

> 支持本地文件路径（**内容为标准 URI 链接或 Clash 字段**）

    `.txt` 后缀的本地文件，需要每行一个单节点分享链接，例如以 `ss://` 开头（非订阅链接）。

    `.yaml` 后缀的本地文件，需填写正确的 clash proxies 字段。

    本地文件需保存在同一磁盘。本地路径格式：`/Desktop/sing-box-subscribe/xx.txt`，或与 `main.py` 同目录的相对路径格式：`./xx.txt`。

- `tag`：必填。保持默认即可。

> 在配置模板里填入这个 tag 即可加入该订阅。这里的 "airport1_tag" 对应配置模板里的 `{机场1}`。具体用法见下方"config 模板文件"一节。

<details>
      <summary>tag 截图参考</summary>

<div align="left">
  <img src="https://github.com/Toperlock/sing-box-subscribe/assets/86833913/781c5bb7-c5c5-467e-a6ae-05ff44a19973" alt="download" width="65%" />
</div>

</details>

- `enabled`：可选。**设为 false 则忽略该订阅**。

- `emoji`：可选。**设为 false 或 0，节点名将不带国旗 emoji**。

- `subgroup`：可选。给订阅链接命名并生成一个 outbound。

- `prefix`：可选。设置一个自定义前缀，会加到节点名的开头。不设置则不加前缀。

- `ex-node-name`：可选。过滤包含关键词的节点，多个关键词用 "|" 分隔。

- `User-Agent`：可选。可自定义 UA，例如设为 "clash.meta" 或 "sing-box"。

<details>
      <summary>prefix 效果参考</summary>

![Snipaste_2023-05-02_12-53-27](https://user-images.githubusercontent.com/21310130/235582317-6bb3d0a6-916f-445f-999b-f17b3db41eea.png)

</details>

- `auto_set_outbounds_dns`：可选。
> 包含 `proxy` 和 `direct` 两项设置。

> `proxy` 和 `direct` 应设置为配置模板文件中 `dns server` 的 `tag`。

> 设置该项后，脚本会自动让路由规则适配 DNS 规则。

> 路由规则中设为 `direct` 的 outbound，其 DNS 服务器会被设为指定的 `direct` outbound。

> 路由规则中需要代理的 outbound，会被设为对应的 `proxy` outbound，脚本会自动为该代理 outbound 创建对应的 `dns server`，并采用 `proxy` 设置的 `dns server`。

- `save_config_path`：必填。设置生成配置文件的路径。

- `auto_backup`：可选。
> 设为 true 时，脚本会把当前使用的 sing-box 配置文件重命名为 `原文件名.当前时间.bak` 进行备份，以防生成了错误配置需要还原。

- `exclude_protocol`：可选。
> 设置要排除的协议，用逗号分隔，例如 ssr, vmess。

> 使用该设置中协议的分享链接会被忽略。

> sing-box 官方发行程序不支持 ssr（需要额外编译参数），所以该设置可能有用。

- `config_template`：可选。填写一个正确的网页 json 配置模板链接，将按此模板生成 sing-box 配置。

- `Only-nodes`：可选。
> 设为 true 或 1 时，只输出该订阅链接的 sing-box 格式节点信息。

# config 模板文件
脚本会在 `config_template` 目录里查找 JSON 模板文件，运行时可以选择使用哪个模板文件。

例如目录下有 `tun.json` 和 `socks.json` 两个模板文件。

![Snipaste_2023-03-24_22-16-49](https://user-images.githubusercontent.com/21310130/227548643-ffbf3825-9304-4df7-9b65-82a935227aef.png)

脚本不会校验模板文件的正确性。如果模板文件有误，会报错且脚本无法运行。

模板文件与 sing-box 配置类似，但新增了一些参数，如 `{all}`、`{机场tag}`（即 `{airport_tag}`）、`filter`，它们只在 `urltest` 和 `selector` outbound 中配合 `clash_mode` 生效。
```json
{
  "tag":"proxy",
  "type":"selector",
  "outbounds":[
    "auto",
    "{all}"//所有订阅的所有节点都会加到该 tag 的位置
  ],
  "filter":[
    //该过滤器会移除 airport1_tag 中名字含 ˣ² 的节点
    {"action":"exclude","keywords":["ˣ²"],"for":["机场1"]}
  ]
},
{
  "tag":"netflix",
  "type":"selector",
  "outbounds":[
    "{机场1}",//tag 为 airport1_tag 的订阅节点会加到该 tag 的位置
    "{机场2}"//tag 为 airport2_tag 的订阅节点会加到该 tag 的位置
  ],
  "filter":[
    //如果 airport1_tag 和 airport2_tag 中有名字含 'sg','新加坡','tw','台湾' 的节点，它们共同组成 netflix 分组
    {"action":"include","keywords":["sg|新加坡|tw|台湾"]},
    //"for" 设为 airport1_tag，表示该规则只对 airport1_tag 生效
    {"action":"exclude","keywords":["ˣ²"],"for":["机场1"]}
    //该过滤器会移除 airport1_tag 中名字含 ˣ² 的节点
  ]
}
```
- `{all}`：代表所有订阅中的所有节点。脚本会把所有节点加到带此标识的 `outbounds` 中。

- `{机场tag}`（即 `{airport_tag}`）：在 `providers.json` 里设置的机场 `tag` 可以在这里使用，代表该订阅中的所有节点。

- `filter`：可选。节点过滤，是一个数组对象，可以添加任意多条规则，格式为：
```json
"filter": [
    {"action": "include", "keywords": ["keyword1|keyword2"]},
    {"action": "exclude", "keywords": ["keyword1|keyword2"], "for": ["airport1_tag", "airport2_tag"]}
  ]
```
- **关键词区分大小写**

- `include`：添加要保留的关键词，多个关键词用 '|' 连接。名字包含这些关键词的节点会被保留，其他节点会被删除。

- `exclude`：添加要排除的关键词，多个关键词用 '|' 连接。名字包含这些关键词的节点会被删除，其他节点会被保留。

- `for`：可选。设置为机场 `tag`，可以多个。该规则只对指定机场生效，其他机场忽略此规则。

多条规则会按顺序依次执行。

# Windows 上的 sing-box 使用

1. 下载 Windows 客户端程序 [sing-box-windows-amd64.zip](https://github.com/SagerNet/sing-box/releases)。
2. 新建一个 `.bat` 批处理文件，内容为 `start /min sing-box.exe run`。
3. 参考 [客户端配置](https://github.com/chika0801/sing-box-examples/blob/main/Tun/config_client_windows.json) 示例按需修改，并把文件名改为 **config.json**，然后把批处理文件放到与 **sing-box.exe** 相同的文件夹。
4. 右键 **sing-box.exe**，选择"属性"，进入"兼容性"，勾选"以管理员身份运行此程序"。
5. 运行批处理文件，在弹出的"用户账户控制"对话框中点击"是"。

## 隐藏 Windows 运行 sing-box 时弹出的 cmd 窗口

> 使用 WinSW 把 sing-box.exe 设置为 Windows 服务，[WinSW 教程](https://github.com/winsw/winsw)

> XML 配置文件修改
```xml
<service>
  <id>sing-box</id>
  <name>sing-box</name>
  <description>sing-box Service</description>
  <executable>./sing-box.exe</executable>
  <log mode="reset"></log>
  <arguments>run</arguments>
</service>
```
<details>
      <summary>Windows sing-box 文件夹内容</summary>

<div align="left">
  <img src="https://github.com/Toperlock/sing-box-subscribe/assets/86833913/c6a815bf-b542-43c6-aeb6-84020586a1f1" alt="download" width="50%" />
</div>

</details>

## 在非图形客户端中，不使用 tun 的用法

例如你在 Windows 上用内核直接运行 sing-box，删除 inbounds 里的 tun 字段：

```json
"inbounds": [
    {
      "type": "mixed",
      "listen": "127.0.0.1",
      "listen_port": 2080, //该端口必须与 Windows 代理端口一致
      "sniff": true,
      "set_system_proxy": true,
      "sniff_override_destination": false,
      "domain_strategy": "ipv4_only"
    }
  ]
```

<div align="left">
  <img src="https://github.com/Toperlock/sing-box-subscribe/assets/86833913/387f2077-b8b6-42ed-9658-361b28179db2" alt="download" width="50%" />
</div>

<details>
      <summary><b>效果参考</b></summary>

具体效果取决于各自的 outbound 与规则设置。

<div align="left">
  <img src="https://user-images.githubusercontent.com/21310130/227577941-01c80cfc-1cd9-4f95-a709-f5442a2a2058.png" alt="download" width="50%" />
  <img src="https://user-images.githubusercontent.com/21310130/227577968-6747c7aa-db61-4f6c-b7cc-e3802e34cc3d.png" alt="download" width="50%" />
  <img src="https://github.com/Toperlock/sing-box-subscribe/assets/86833913/955968d7-98e7-4bd2-a582-02576877dba1" alt="download" width="50%" />
  <img src="https://github.com/Toperlock/sing-box-subscribe/assets/86833913/9e7c35ff-c6c4-46c4-a74b-624ff72c17ea" alt="download" width="50%" />
</div>

</details>

# 致谢
- [xream](https://github.com/xream)
- [sing-box](https://github.com/SagerNet/sing-box)
- [yacd](https://github.com/haishanh/yacd)
- [clash](https://github.com/Dreamacro/clash)
- [sing-box-examples@chika0801](https://github.com/chika0801/sing-box-examples)

部分协议解析参考自 [convert2clash](https://github.com/waited33/convert2clash)。

部分 clash2v2ray 解析参考自 [clash2base64](https://github.com/yuanyiwei/toys/blob/master/DEPRECATED/clash/clash2base64.py)。

部分同步代码参考自 [ChatGPT-Next-Web](https://github.com/Yidadaa/ChatGPT-Next-Web)。

感谢 @SayRad 提供的越南语翻译。

---

> 本中文文档由本分支（fork）基于 main 分支的英文文档 [instructions/README.md](./README.md) 翻译整理，并补充了 fork 新增的多订阅参数功能说明。

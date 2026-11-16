# evidgate

[![PyPI](https://img.shields.io/pypi/v/evidgate.svg)](https://pypi.org/project/evidgate/)
[![Python](https://img.shields.io/pypi/pyversions/evidgate.svg)](https://pypi.org/project/evidgate/)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
[![CI](https://github.com/BringCo/evidgate/actions/workflows/ci.yml/badge.svg)](https://github.com/BringCo/evidgate/actions/workflows/ci.yml)

[English](README.md) · **简体中文**

**把交付物里的每一句话变成一条检查，并且拒绝加载一条永远不可能变红的检查。**

它不判断内容对不对。它判断的是：你为这句话声称的依据是不是真的、还在不在、能不能复现；
然后把这个判断写成一份能交给别人的台账。

一行台账 = 一条检查 = 跑过的那条命令 = 它返回的退出码 = 你续跑的位置 = 放行还是拦下的决定。

## 它要拦的到底是什么

**一个因为错误原因报绿的检查，比没有检查更糟**——你会停止查看。下面三种都是做这个工具时
真碰到的，不是设想：

**1. 命令根本没跑。** Windows 上没有 `grep`。执行一个不存在的命令，退出码是 `1`，而
`exit:1` 恰好就是"grep 什么都没找到"的合法断言。于是这条检查在**从未真正执行过**的情况下
一直报通过。现在 evidgate 把"命令没跑起来"和"命令跑了并返回这个码"分开，只有后者能通过。

**2. 检查没有对象。** 一份 172 个文件、每一条都是源文件（没有派生件）的清单，让 `figures`
包报了 **3 个 PASS、覆盖率 100%**：没有派生件就没有比较对象，每条规则都在空转。现在有一条
`GF0` 检查，唯一职责就是在这种清单上变红。

**3. 从来没人要求这条检查失败过。** 这一类天生是沉默的：规则写进 CI 之后从没拿一份坏掉的
副本试过，它就一直没被验证过。所以 `counter`（这条检查怎么就变红了）是必填字段，缺了在
**加载时**就被拒绝，不是等到运行时才发现。

## 它和别的工具差在哪

| | 普通 linter | 人的 checklist | evidgate |
|---|---|---|---|
| 谁决定通过 | 规则 | 人打勾 | 命令 + 它的退出码 |
| 凭什么证明 | 没有 | 没有 | 命令、退出码、输出片段、产物哈希、时间戳 |
| 规则悄悄失效时 | 无声 | 无声 | `evidgate mutate` 报 "detection 1/1" 或 "NOT caught" |
| "还剩什么没做"记在哪 | 无处 | 另一张表 | 同一行台账 |
| 能不能存在一条没法失败的规则 | 能 | 能 | **加载期直接拒绝** |

`counter` 是必填字段，所以**一条不可能失败的闸门不是闸门，是许愿。**

## 30 秒

```bash
pip install evidgate
cd <你的项目>
evidgate init --dir .        # 生成 evidgate.yaml，挑一个真实存在的文件作起点
evidgate doctor --dir .      # yaml 能解析吗？命令都能找到吗？先排环境再怪项目
evidgate run --dir .         # 出台账和判定；exit 1 表示被拦下

# 或者直接从 clone 跑的零安装入口（只用标准库）：
./bin/evidgate --version
```

`doctor` 报 `BAD` 就先修那个——最常见的是 `method` 里的命令不在 `PATH`，或者用到了
shell 语法却没声明 `shell:`。

跑一遍自带的三领域示例：

```console
$ evidgate run --dir examples/mixed
evidgate 0.9.2.post1 · mixed-delivery (fictional) · 7 checks
   D1 FAIL(红)  草稿里的绝对化词带范围或检索日期  ─  -exit 2 (want 0) | got: L3 [首次实现] 本方案首次实现全自动估价流程。 | [absolutes] 1 finding(s)  (exit 2)
   D2 DIFF(黄)  草稿里的统计数字带口径  ─  -exit 3 (want 0) | got: L3 抽样调参后误差降低 18.4%。 | [numeral_scope] 1 finding(s)  (exit 3)
   A1 PASS     产物存在且非空  ─  +exit 0 (want 0) ; +regex OK ─ \d -> 3
   A2 FAIL(红)  正本与其派生副本逐字节一致  ─  -exit 1 (want 0)
   C1 PASS     代码单测全绿  ─  +exit 0 (want 0)
   C2 PASS     源码里没有明文密钥  ─  +exit 0 (want 0) ; +not_contains OK:api_key ; +not_contains OK:secret_key
   C3 PASS     源码里没有残留 TODO  ─  +exit 1 (want 1)

PASS 4 · DIFF(黄) 1 · FAIL(红) 2 · 待补 0 · 未覆盖 0 | coverage 7/7 (100.0%)
RELEASE BLOCKED  blocked by D1, A2
note: PASS 表示「证据存在且可复现」，不表示数值本身正确。
```

示例故意把中文检查名和英文输出混在一起：自带的 `prose` 规则针对中文稿，而同一张台账
可以装任何一种语言。

红项拦下放行，黄项进确认清单，**待补永远不算完成**。退出码 1 表示被拦下——非零的运行
不能报成通过。

## 在真东西上查到了什么

| 对象 | 规模 | 结果 |
|---|---|---|
| 成熟开源项目 | 8 个 | **0 检出** |
| 个人交付物仓库 | 4 个 | **3 个真缺陷** |
| 一份真实论文稿 | 581 句 | 校准前 222 条 → **32 条** |

那个 0 是边界，不是弱点：成熟项目本来就不提交密钥、也不留 `.bak` 文件。个人仓库里那三个
缺陷是：坏符号链接让整个扫描崩溃、上面那个空转却全绿的清单、以及 `suggest` 认不出
`.fig`/`.dia`/`.dat` 这类真实的图源。这个工具是**交付前最后看一眼**用的。

## 适合谁

- 你马上要把一份稿子、一份报告、一套申报材料或者一个构建目录交给别人，而对方会问
  "这个数字哪来的"。
- 交付物是 agent 产出的，"做完了"只是一句话、背后没有命令。自己开多个窗口时同理：
  别的上下文给的结论是用来核的，不是用来信的。
- 你已经在跑测试和 linter，并且发现它们都不留痕：**查了什么、用什么命令、什么时候**。

## 不适合谁

- **内容正确性**——数字对不对、论证成不成立。
- **排版、术语统一、AI 腔**——[Vale](https://vale.sh/) 和 `deliverable-qa` 规则多得多。
- **审成熟仓库**——预期就是 0 检出。
- **审批流**——没有角色、没有多人签署，这是单人用的命令行工具。

## 装成 agent skill

`skill/evidgate/SKILL.md` 是给 agent 看的说明书：什么时候该用它、头一分钟跑哪几条、
一条检查长什么样、假绿的三种形状。把整个目录拷或链到你的 agent 的 skills 目录：

```bash
cp -r skill/evidgate ~/.hermes/skills/                   # Hermes
ln -s "$PWD/skill/evidgate" ~/.hermes/skills/evidgate    # 或改用软链
```

之后一句「说完之前先跑 evidgate」就有了明确指向。`evidgate run` 被拦时退出码是 1——
拿着非零结果报成功的 agent，正是这个工具要拦的那种。

## 命令

```bash
evidgate init --dir <项目>                       # 起步的 evidgate.yaml
evidgate suggest --dir <项目> [--write]          # 读磁盘，告诉你该用哪个包
evidgate doctor --dir <项目>                     # yaml + 命令可解析性，先排环境
evidgate run --dir <项目> [--only C1,P2]         # 跑 + 重建台账；exit 1 = 被拦下
evidgate resume --dir <项目>                     # 只重跑未解决的
evidgate report --dir <项目>                     # 生成 gate_report.md：表、黄项、未核、结论
evidgate mutate --dir <项目> --baseline A --mutant B [--only C1]   # 这条检查真会变红吗
evidgate prose-init --dir <项目> --file <稿子>   # 追加中文 prose 规则（P1..P5）
evidgate artifact-init --dir <项目> --out artifacts.json   # 扫成一份产物清单
evidgate artifact-update --dir <项目>            # 重算产物自身的 md5（绝不碰 source_md5）
evidgate artifact-stamp --dir <项目> --path <路径>   # 重新生成之后：记录源哈希
evidgate pack [list|show <名字>]                 # 看一个包展开成什么
```

## 文档（参考手册为英文）

| 文档 | 讲什么 |
|---|---|
| [怎么写一条检查](docs/writing-a-check.md) | `method` 两种写法、`optional`、全部 `expect` 子句、证据自检、加自己的领域 |
| [artifact 插件](docs/artifact-plugin.md) | 五条清单规则、为什么 `stale` 比哈希不比时间、`orphan` 的范围与开销、`source_md5` 的唯一写入者 |
| [prose 插件](docs/prose-plugin.md) | 五条中文规则、校准过程、句子边界、`EVIDGATE_EVIDENCE` |
| [shell 与 Windows](docs/shell-and-windows.md) | 为什么默认不经 shell、Git Bash 的查找方式、Windows 上那次假绿 |
| [suggest 与检查包](docs/suggest-and-packs.md) | 第一个命令、三个包与它们的参数 |

## 示例

所有示例都是**虚构的**，每个缺陷都是故意种进去的。

- `examples/mixed/`——prose + artifact + code 在同一张台账里（就是上面那段输出）
- `examples/`——一份中文草稿，六条检查，2 PASS / 2 DIFF / 2 FAIL
- `examples/figures/`——一个 SVG 源、三个派生，三种 `stale` 判定并排展示
- `examples/artifact/`——一个 markdown 源带两个派生，四条产物检查

变异演示：

```bash
./bin/evidgate mutate --dir examples --baseline examples/base --mutant examples/mut --only C1
# detection power: 1/1
```

## 范围

**不做**：验证一个参考文献真的存在、或真的说了你说的那句话——那是
[refchecker](https://github.com/markrussinovich/refchecker) 这类工具的事。
**不做**：判断文本是不是 AI 写的、判断排版好坏、判断一个数字对不对。
**做**：检查你为自己的说法、数字和产物声称的依据，是不是真的、能复现、有记录——只要你的
命令能观察到它。

`prose` 是写作提示器，不是审校工具。诚实的实测：人工读稿找出 22 处问题、规则报出 26 处，
两者重合的部分很少。

## 来源与许可

证据三元组和三态判定沿用了 obra/superpowers 的 `verification-before-completion`；
"证据闸"这个框架取自 TestifySec Pushgate。本项目新增的部分写在
[ATTRIBUTION.md](ATTRIBUTION.md)。

许可：MIT
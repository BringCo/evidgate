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
被检查的东西可以是一段话、一个产物文件，或者生成这个产物的代码。

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

这三种都不稀奇，它们就是"没人要求检查证明自己能失败"时检查会变成的样子。

## 它和别的工具差在哪

| | 普通 linter | 人的 checklist | evidgate |
|---|---|---|---|
| 谁决定通过 | 规则 | 人打勾 | 命令 + 它的退出码 |
| 凭什么证明 | 没有 | 没有 | 命令、退出码、输出片段、产物哈希、时间戳 |
| 规则悄悄失效时 | 无声 | 无声 | `evidgate mutate` 报 "detection 1/1" 或 "NOT caught" |
| "还剩什么没做"记在哪 | 无处 | 另一张表 | 同一行台账 |
| 能不能存在一条没法失败的规则 | 能 | 能 | **加载期直接拒绝** |

最后一行就是整个设计：`counter` 是必填字段，所以
**一条不可能失败的闸门不是闸门，是许愿。**

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
shell 语法却没声明 `shell:`。工具自带写出来的检查都用 `builtin:`，在进程内执行，这两类
问题都碰不到。

跑一遍自带的三领域示例：

```console
$ evidgate run --dir examples/mixed
evidgate 0.9.2 · mixed-delivery (fictional) · 7 checks
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
`.fig`/`.dia`/`.dat` 这类真实的图源。这个工具是**交付前最后看一眼**用的，不是拿去审别人
成熟仓库的。

## 适合谁

- 你马上要把一份稿子、一份报告、一套申报材料或者一个构建目录交给别人，而对方会问
  "这个数字哪来的"。
- 你在多个窗口或多个 agent 之间来回，别的上下文说"做完了"，你想核一下而不是直接信。
- 你已经在跑测试和 linter，并且发现它们都不留痕：**查了什么、用什么命令、什么时候**。

## 不适合谁

- **内容正确性**——数字对不对、论证成不成立。它不做，也不会做。
- **排版、术语统一、AI 腔**——[Vale](https://vale.sh/) 和 `deliverable-qa` 规则多得多。
- **审成熟仓库**——预期就是 0 检出。
- **审批流**——没有角色、没有多人签署，这是单人用的命令行工具。

## 一张台账，三种领域

引擎不知道"文档"是什么。它只认 `command`、`expect`、`counter`、`severity` 和退出码。
上面那七条检查来自三个不同的世界，共用一张表和同一个放行决定：

| 领域 | 检查示例 | 断言 |
|---|---|---|
| prose（一份草稿） | 绝对化词是否带检索日期或范围 | 对 prose 规则的 `exit:0` |
| artifact（一个产物文件） | 产物非空 / 正本与派生副本逐字节一致 | `regex:\d`、`cmp -s` |
| code（生成产物的代码） | 单测全绿 / 没有明文密钥 / 没有残留 TODO | `exit:0`、`not_contains:`、`exit:1` |

最后一行值得注意：`grep -rn TODO src/` 断言的是 **`exit:1`**——"没匹配到"是一个合法预期。
只要一条命令的退出码是确定的，它就能被检查。

加自己的领域不用改 `core/`：写个脚本，按约定返回 0 / 2 / 3，然后声明成检查项。整个插件
契约就这一句。

## 怎么写一条检查

```yaml
checks:
  - cid: A2
    name: 正本与其派生副本逐字节一致
    method: cmp -s src/app.py src/app.py.bak
    expect: exit:0
    counter: 改常量但忘了同步 .bak，本项必须变红
    severity: red        # red = 阻断，yellow = 不阻断（进黄项清单）
```

`method` 有两种写法：

| 写法 | 什么时候用 |
|---|---|
| `cmp -s a b` / 任意 shell 命令 | 你自己的脚本或工具。必须能找到，找不到 `doctor` 会告诉你 |
| `builtin:prose:absolutes draft.md` | evidgate 自带的检查，**进程内**派发，不经过 `PATH` |

只对某些环境成立的检查，加 `optional: true`（输入不存在、服务没起）。失败的 optional 检查
会变成 `SKIP(未覆盖)`——出现在报告里、算处理过、**永远不阻断**。没有这个机制，"我的项目
里没有那个文件"就会显示成一条红色失败，而闸门就是这么失去读者的。

`expect` 子句（用 `;` 连接，必须全部成立）：

| 子句 | 含义 |
|---|---|
| `exit:N` | 退出码等于 N（任何值都行——`exit:1` 是合法预期） |
| `contains:TEXT` / `not_contains:TEXT` | 标准输出包含 / 不包含 |
| `regex:PATTERN` | 标准输出匹配（多行） |
| `lines>=N` / `lines<=N` | 非空输出行数 |
| `file:PATH` | 路径存在（记录字节数和 md5） |
| `md5:PATH=HEX` | 文件哈希匹配 |
| `manual` | 没有命令断言，一直是待补并阻断 |

需要读标准输出的断言（`contains` / `regex` / `lines`），如果命令一个字都没打印，会被证据
自检判失败——否则 `not_contains` 在空输出上恒真。

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
evidgate prose scan --file <稿子> --rule absolutes   # 单条规则单独跑
evidgate pack [list|show <名字>]                 # 看一个包展开成什么
```

## 插件：artifact（清单驱动）

五条检查，来自管内容产物的三条规矩：一个产物只有一个源；派生件靠重新生成，不靠手改；在
创建时就登记最便宜。一切都能从清单判定，所以不靠猜。

```bash
evidgate artifact-init --dir .        # 扫成 artifacts.json（全部 role=source）
# 然后标注哪些是派生件、从哪来
```

```yaml
- cid: A1
  name: 登记产物齐全且未被手改
  method: builtin:artifact:manifest artifacts.json
  expect: exit:0
```

| 规则 | 问什么 | 红/黄 |
|---|---|---|
| `derivatives` | 清单里到底有没有派生项？（一个都没有时，其余每条规则都在空转） | 红 |
| `manifest` | 登记过的文件都还在吗？**派生件**记录的 md5 还对得上吗？ | 红 |
| `stale` | 自这条派生件生成以来，源变过吗？（比哈希，不比文件时间） | 黄 |
| `sync` | `same_as_source` 的派生件还等于它的源吗？ | 红 |
| `orphan` | 被扫目录里有没有清单从未登记的文件？ | 黄 |

闸门自己的文件（`evidgate.yaml`、`evidgate_ledger.md`、`gate_report.md`）永远不算 orphan
——它们是配置和输出，不是交付物。

`stale` 比的是记录下来的 `source_md5` 和源文件现在的哈希，**从不看文件时间**。早期版本用
mtime，是错的：`git clone`、解压、`rsync` 都会把时间刷成"现在"，所以同一个示例在工作区报
`1 PASS / 2 DIFF`，clone 之后报 `2 PASS / 1 DIFF`。比哈希，两边结论一样。

**`orphan` 要指向产物目录，不要指向仓库根。** 在一个真实的 17k 文件项目上实测过：扫仓库
根报出 6002 个"未登记"文件（源码、文档、`.bak` 副本），结论是真的，但没有用。只扫 `build/`
才是设计意图。开销同样值得注意：同样 201 个文件，ext4 上 0.001 秒，跨 WSL 的 `/mnt/c`
挂载 0.818 秒（单文件约 800 倍），所以在挂载盘上，扫描宽度比文件数量更要紧。

永远不想登记的文件（构建日志、临时文件）放进清单的 `ignore` 列表，用 shell 通配匹配：

```json
{"root": ".", "ignore": ["*.log", "tmp/", "*.tmp"], "items": [...]}
```

`source_md5` 只有一个写入者：**`artifact-stamp`**，在你重新生成之后立刻调用。
`artifact-update` 故意不碰它。早期版本碰了，后果是一条命令就能让所有过期派生件看起来是新的，
什么都没重新生成——那不叫闸门，那叫洗地。

```bash
evidgate artifact-stamp --dir . --path build/report.html   # 只在重新生成之后
```

`stale` 能说什么、不能说什么：它回答"自这次盖章以来源变过没有"。它无法判断一个派生件
是否曾经同步过。没有 `source_md5` 的派生件报**无法判断**，绝不报成干净。在一个真实的图
目录上实测（10 个 SVG 源、30 个派生件）：盖章之前，30 个全是"无法判断"；mtime 那版启发式
曾把其中 10 个判成过期，但那个判定本身就不可靠。

## 插件：prose（中文）

`evidgate prose scan --rule <名字>`——退出码 `0` 干净、`2` 阻断、`3` 提示：

| 规则 | 命中的是什么（校准之后） |
|---|---|
| `denominator` | 正文句子数——只作信息，让覆盖率可算 |
| `absolutes` | **`本文/我们` + 首次/首创/率先**，或 **首次/首创 + 提出/实现/证明/引入/建立**，且没有检索日期。描述性用法（"某指标首次跌破目标"、"唯一缺口为负者"）不触发 |
| `uncited` | 结论动词（表明/说明/证明/意味着/取决于）**没有**引用、图表、§ 编号、统计量或实测标记 |
| `numeral_scope` | 裸数字（ρ / R² / 倍 / % / 降低 N）附近没有 `n=`、`m/m`、`p=`、±、口径/协议/脚本/路径 |
| `citation_chain` | 正文里的 `[n]` 在文献表里缺号，以及列了却从未被引的条目 |

### 校准（这部分才要紧）

这些规则的第一版是照着编造的示例写出来的，**是错的**。在一份真实的 581 句稿子上，它触发了
**222 次**，误报约 95%——把一句描述性的"某指标首次跌破目标"当成首创声明，把一句"首次下降"
当成创新点，把所有含 `20/20` 或 `p=1.7e-12` 的句子都当成"缺样本量"。
校准之后同一份稿子触发 **32 次**，`tests/` 里九条回归测试钉住了那些必须保持沉默的描述性写法。

两条要知道的约定：

- **句子边界**：prose 规则按 `。；！？` 切句。按*行*计数的台账（含表格行）会得到不同的分母
  ——同一个文件，581 句 vs 251 行台账。不同工具的覆盖率数字不可比。
- **你所在领域的标记**：用 `EVIDGATE_EVIDENCE` 追加，`|` 分隔的正则，例如
  `EVIDGATE_EVIDENCE='20/20|Holm|pp|§[0-9]'`。内置列表只认得常见的那些。

这些是启发式，不是判据——黄项就是该由人去看的地方，这也正是黄项存在的原因。

## 默认不经 shell

除非你声明，**检查不经 shell 执行**。这是故意的：只有这样，同一条检查在每个平台上才是
同一个意思。

```yaml
- cid: C3
  method: grep -rn TODO src/       # 切成 argv 直接执行
  expect: exit:1
```

命令需要管道、重定向、`$()` 或 `&&` 时，就明说：

```yaml
- cid: A1
  shell: bash                      # bash | sh | cmd | powershell | pwsh
  method: test -s build/out.txt && wc -c < build/out.txt
```

边界说清楚：

- 不写 `shell:` 而命令又需要 shell 语法时，会直接失败并提示你加 `shell: bash`——它不会替你
  悄悄挑一个 shell。`doctor` 在你跑之前就把这个缺失报成 `BAD`。
- Windows 上 `shell: bash` 只在标准安装位置找 **Git Bash**，**故意不用 `PATH` 里的 `bash`**
  ——那里这个名字解析到 `C:\Windows\System32\bash.exe`，是 WSL 入口，用的是 `/mnt/e/...`
  而不是 `/e/...`，会找错地方。
- 没有 Git Bash，就没有 `shell: bash` 检查。它们会报"命令未找到"并阻断放行。`builtin:`
  检查什么都不需要，到处都能跑。

### Windows

所有以 `builtin:` 形式提供的检查（`packs/figures` 全部）两个平台都能跑。写成 shell 命令的
（`grep`、`test -d`、`$(...)`）需要 POSIX shell。

命令完全找不到时，evidgate 现在会明说并判失败，而不是接受那个退出码——因为在 Windows 上
少一个 `grep` 的退出码就是 `1`，而 `1` 正是 `expect: exit:1`（"grep 没找到"）要的东西。
那是一次真实的静默假绿。

Windows 上优先用 `builtin:` 检查，或者在 Git Bash / WSL 下跑。

## 从这里开始：`evidgate suggest`

空配置是最糟的第一分钟。不如先问一句：

```console
$ evidgate suggest
扫到的东西：
  · figs 一带：3 个 svg、4 个 png、3 个 pdf
      → 一个源 + 多个派生 —— 正是 figures 包要盯的结构

建议在 evidgate.yaml 里写一行：
    packs: figures

生成它：evidgate init --packs figures
```

它读磁盘——图目录、构建产物、文献表、测试——告诉你哪些包适用、哪些检查还得自己写。
`--write` 直接生成配置。`README.md` 和 evidgate 自己的台账/报告不会被误当成待审文档。

## 检查包

用一行代替十五条：

```yaml
project: my-deliverable
ledger: evidgate_ledger.md
packs: figures
```

这就是一份完整配置。`evidgate run` 把它展开成这个包的检查（derivatives / manifest /
stale / orphan），红项照样阻断。

| 包 | 加了什么 |
|---|---|
| `figures` | 一个源、多个派生：`png`/`pdf`/`eps` 由 `artifacts.json` 覆盖 |
| `build` | 构建产物非空、不含明文密钥、没有残留 `.tmp`/`.bak` |
| `repo` | 单测全绿、没有遗留 `TODO`/`FIXME`/`breakpoint()` |

参数写在冒号后面：`packs: figures:manifest=my.json,outdir=figs`。
用 `evidgate pack show figures` 看一个包展开成什么。

**范围说明。** 它故意不做排版和 AI 腔检查——Vale 和 `deliverable-qa` 做这些，规则多得多。
evidgate 问的是另一个问题：*这句话背后的依据在不在、没被改过、还能复现吗？* 所以每条检查
都要跑一条命令、记录退出码、哈希和时间戳；所以这里的包查产物，不查文风。

## 示例

所有示例都是**虚构的**，每个缺陷都是故意种进去的。

- `examples/mixed/`——prose + artifact + code 在同一张台账里（就是上面那段输出）。
  跑：`./bin/evidgate run --dir examples/mixed`
- `examples/`——一份中文草稿，六条检查，2 PASS / 2 DIFF / 2 FAIL。
  跑：`cd examples && ../bin/evidgate run --dir .`
- `examples/figures/`——图目录的真实形态：**一个 SVG 源、三个派生**（png/pdf/eps）。三种
  `stale` 判定并排展示：盖过章且干净、从没盖章（"无法判断"）、盖过章但源又变了。
  图是生成的，不是真素材。
  跑：`./bin/evidgate run --dir examples/figures`
- `examples/artifact/`——一个 markdown 源带两个派生，四条产物检查
  （已登记 / 过期 / 被手改 / 未登记）在一张台账里。1 PASS / 2 DIFF / 1 FAIL。
  跑：`./bin/evidgate run --dir examples/artifact`

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
两者重合的部分很少。它只能告诉你"这句话看起来没给口径"，不能告诉你"这个数字错了"。

## 来源与许可

证据三元组和三态判定沿用了 obra/superpowers 的 `verification-before-completion`；
"证据闸"这个框架取自 TestifySec Pushgate。本项目新增的部分写在
[ATTRIBUTION.md](ATTRIBUTION.md)。

许可：MIT
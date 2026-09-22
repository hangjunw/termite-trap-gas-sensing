# 发布到 GitHub 的详细流程

本文档面向本仓库的作者，覆盖从「本地准备」到「拿到 Zenodo DOI 并回填稿件」的完整链条。
两条路线任选一条：**路线 A** 免安装、5 分钟；**路线 B** 是长期维护该走的路。

---

## 0. 发布前检查清单

发布是**不可撤**的动作（commit 历史会永久留在公开仓库），先逐项过一遍：

| # | 检查项 | 命令 / 位置 | 当前状态 |
|---|---|---|---|
| 1 | `CITATION.cff` 里的 `repository-code` 换成真实仓库地址 | `CITATION.cff` 第 15 行 | ⚠️ 待填（现为 `<user>` 占位） |
| 2 | `CITATION.cff` 的 `doi`、作者 `orcid` | `CITATION.cff` | ⚠️ 发表后回填 |
| 3 | `README.md` 里的 `git clone <this-repo>` | `README.md` 快速开始 | ⚠️ 换成真实地址 |
| 4 | 作者占位符 `[Author C]` | 稿件 ¶2；`CITATION.cff` 只列了 3 位 | ⚠️ 待确认 |
| 5 | 无敏感信息 | `git grep -iE "password\|api[_-]key\|secret\|token"` | ✅ 已核查为空 |
| 6 | 无临时/缓存文件 | `find . -name "__pycache__" -o -name "*.pyc" -o -name '~$*'` | ✅ 已核查为空（`.gitignore` 已覆盖） |
| 7 | 大文件 | 最大 `data/termite_gas_measurements.csv` 0.72 MB | ✅ 远低于 25 MB 网页上限 / 100 MB 硬上限，**不需要 Git LFS** |
| 8 | 仓库名与可见性 | 建议 `termite-trap-gas-sensing`，Public | 待定 |

> **可见性**：投 MDPI/Elsevier 等期刊时，Data Availability Statement 指向的仓库
> 必须是**公开可访问**的；审稿阶段可先设 Private，投稿时改 Public，或把
> 审稿人加为 Collaborator。私有仓库在评审期是常见做法，但录用前必须公开。

---

## 1. 路线 A：网页上传（最快，无需安装任何东西）

适合：只想发一版、之后不打算频繁改动。

1. 打开 <https://github.com/new>
2. 填写：
   - **Repository name**：`termite-trap-gas-sensing`
   - **Description**：`Code and data for a networked multi-gas sensing system for in-trap monitoring of termite-associated CO2 and CH4`
   - **Public**（见上方可见性说明）
   - ⚠️ **不要勾选** `Add a README file`、`Add .gitignore`、`Choose a license`
     —— 本仓库已有这三个文件，勾了会产生冲突，首次 push 会报
     `rejected ... fetch first`
3. 点 **Create repository**，进入空仓库页面
4. 点 **uploading an existing file**
5. 打开本地 `github_release/termite-trap-gas-sensing/`，**全选里面的内容**
   （`.gitattributes`、`.gitignore`、`CITATION.cff`、`LICENSE`、`README.md`、
   `calibration/`、`data/`、`docs/`、`figures/`、`requirements.txt`、
   `results/`、`src/`）
   —— 注意是**内容**，不是外层文件夹 —— 拖进浏览器上传区
   - 现代 GitHub 支持直接拖文件夹，目录结构会保留
   - 限制：单次最多 100 个文件（本仓库 36 个）、单文件 ≤ 25 MB（本仓库最大 0.72 MB）
   - `.gitignore` 是点开头的隐藏文件，Windows 资源管理器默认不显示；先在
     「查看 → 显示 → 隐藏的项目」打开，否则会漏传
6. 下方 **Commit changes** 填 `Initial release v1.0.0`，点提交

> 网页上传的缺点：无法用命令批量更新；以后每改一次都要重新拖。所以只建议用于
> 一次性发布。

---

## 2. 路线 B：Git 命令行（推荐）

### 2.1 一次性配置（每台机器只做一次）

```bash
git config --global user.name  "Hangjun Wang"
git config --global user.email "whj@zafu.edu.cn"
```

> 改这两项会写进每一次 commit 的作者信息，公开可见。用你希望对外显示的身份。
> 若只想对本仓库生效，去掉 `--global` 并在仓库目录内执行。
>
> 已经提交后发现写错了？`git commit --amend --reset-author --no-edit`
> （若已 push，需要 `git push --force-with-lease` 重写远端历史，公开仓库慎用）。

### 2.2 先在本地建好仓库并提交

本仓库已经完成这一步，可以直接跳到 2.3。若在别的机器上从零开始：

```bash
cd github_release/termite-trap-gas-sensing

git init -b main          # 初始化，主分支名 main
git add .                 # 暂存全部
git status                # ★ 必看：确认没有 __pycache__ / ~$xxx.docx 混进来
git commit -m "Initial release v1.0.0: data, calibration notice, reproduction code"
```

`git status` 的输出应该是 36 个 `new file:`。如果看到 `__pycache__/` 或
`~$` 开头的临时文件，先删掉再 `git add .`。

顺手看一眼提交内容对不对：

```bash
git show --stat HEAD | head -20
git ls-files | wc -l          # 应为 36
```

### 2.3 在 GitHub 上建空仓库

同路线 A 第 1–3 步：建 `termite-trap-gas-sensing`，**三个初始化选项全部不勾**。

### 2.4 关联远端并推送

把 `<用户名>` 换成你的 GitHub 账号名：

```bash
git remote add origin https://github.com/<用户名>/termite-trap-gas-sensing.git
git remote -v                      # 核对一遍地址
git push -u origin main
```

`-u` 只在第一次需要，作用是把本地 `main` 和远端 `origin/main` 绑定，
之后直接 `git push` 即可。

### 2.5 认证（第一次 push 会弹窗）

GitHub 早已停用账号密码推送，三种方式选一种：

| 方式 | 做法 | 适用 |
|---|---|---|
| **Git Credential Manager**（最省事） | Windows 版 Git 自带。第一次 `git push` 会弹出浏览器登录 GitHub，授权后凭据存进 Windows 凭据管理器 | 推荐，日常单人开发 |
| **Personal Access Token (PAT)** | GitHub → Settings → Developer settings → Personal access tokens → **Fine-grained tokens** → 生成，权限勾 `Contents: Read and write` → 推送时**用户名填 GitHub 用户名、密码位置粘贴 token** | 脚本化、CI |
| **SSH** | `ssh-keygen -t ed25519 -C "whj@zafu.edu.cn"` → 把 `~/.ssh/id_ed25519.pub` 内容贴到 GitHub → Settings → SSH and GPG keys → 远端改用 `git@github.com:<用户名>/termite-trap-gas-sensing.git` | 长期多机开发 |

⚠️ PAT 只显示一次，务必当场存好；**不要**把 token 写进任何进仓库的文件。

推送成功后刷新仓库页面，应看到 README 渲染、36 个文件、右侧
`MIT license` 徽标和语言统计（Python 为主）。

---

## 3. 发布后：打版本标签 + 关联 Zenodo 拿 DOI

期刊现在普遍要求数据/代码有**独立 DOI**，而不仅是一个仓库链接。

1. **先打 tag**（Zenodo 只对 Release 生成 DOI，不对裸 commit）：

   ```bash
   git tag -a v1.0.0 -m "Release v1.0.0: manuscript submission version"
   git push origin v1.0.0
   ```

   或在网页：仓库右侧 **Releases → Create a new release**，**Choose a tag** 填
   `v1.0.0` → 生成 tag → 标题 `v1.0.0` → 描述里写清这一版对应哪次投稿。

2. **关联 Zenodo**：登录 <https://zenodo.org> → 用 GitHub 账号登录 →
   Settings → GitHub → 找到本仓库 → 把开关拨到 **ON**。
3. 回到 GitHub，**再发一次 Release**（或编辑已发的 Release 重新保存）。Zenodo
   只会为「开启开关之后」创建的 Release 生成 DOI。
4. Zenodo 会给出两个 DOI：
   - **Concept DOI**（`10.5281/zenodo.xxxxxxx`）——指向"这个项目"，永远指向最新版，**引用用这个**；
   - **Version DOI**——指向具体某一版。
5. 把 DOI 徽标加进 README（可选，但评审喜欢看）：

   ```markdown
   [![DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.xxxxxxx.svg)](https://doi.org/10.5281/zenodo.xxxxxxx)
   ```

---

## 4. 把结果回填进稿件

拿到 DOI 后，稿件与仓库要对齐，否则评审会发现口径不一致：

1. `CITATION.cff`：填入 `doi`、`repository-code`、作者 `orcid`；
2. `README.md`：把 `git clone <this-repo>` 换成真实地址；
3. 稿件 **Data Availability Statement**：把 "available from the corresponding
   author upon reasonable request" 改为指向仓库 + DOI，例如

   > The measurement data and the analysis code that reproduces every table and
   > figure are openly available at https://github.com/&lt;user&gt;/termite-trap-gas-sensing
   > (archived at https://doi.org/10.5281/zenodo.xxxxxxx). The sensor calibration
   > files and raw calibration sweep are available from the corresponding author
   > on reasonable request.

4. 注意：标定部分**保持"索要"口径**，与 `calibration/README.md` 一致
   （见 `REPRODUCIBILITY.md` 第 5 节）。

---

## 5. 后续更新流程

改了分析代码或补充了数据之后：

```bash
git status                          # 看改了什么
git diff                            # 看具体改动
git add -A
git commit -m "Fix: recompute Table 8 LOD from unrounded sigma"
git push
```

若这一版需要新 DOI（例如投稿后大改）：`git tag -a v1.1.0 -m "..."` +
`git push origin v1.1.0`，再去 GitHub 发对应 Release，Zenodo 会自动出新 DOI。

**发布前务必重跑一遍复现**，确保仓库里的 `results/`、`figures/` 与新代码一致：

```bash
python -m src.run_all
```

---

## 6. 常见坑

| 现象 | 原因 | 解决 |
|---|---|---|
| `! [rejected] main -> main (fetch first)` | 建仓库时勾了 README/LICENSE/gitignore，远端已有 commit | `git pull --rebase origin main` 后再 push；或删掉远端仓库重建（更干净） |
| `fatal: remote origin already exists` | 之前加过远端 | `git remote set-url origin <新地址>` |
| push 卡在 `Username for ...` 输密码报 403 | GitHub 不支持密码认证 | 用 PAT 或 Git Credential Manager |
| 中文文件名在 `git status` 显示成 `"\347\251\272..."` | Git 默认转义非 ASCII 路径 | 只看不改：`git config --global core.quotepath false` |
| 每次 `git status` 显示全部文件被改 | Windows CRLF 与仓库 LF 冲突 | 本仓库已含 `.gitattributes`（`* text=auto eol=lf`），若仍出现：`git add --renormalize .` |
| 误提交了 `__pycache__` | 在 `.gitignore` 生效前就 add 了 | `git rm -r --cached __pycache__` 后重新 commit |
| 上传后某文件夹不见了 | 拖拽时漏了隐藏的 `.gitignore` / `.gitattributes` | 网页：Add file → Upload files，单独补传 |
| Excel 打开 CSV 后 `Timestamp` 列多出年份（`2026/8/24 12:46`） | 文件里只有 `08-24 12:46`（无年份）；Excel 的 CSV 导入把它当日期解析并按本机格式显示 | **不是文件问题**。纯 CSV 无法阻止表格软件导入时的日期识别；说明 `h` 才是用来计时长的量。已在 `data/README.md` 第 2 节第 4 条写明 |
| Excel 打开 csv 中文乱码 | 文件是 UTF-8 **带 BOM**（`utf-8-sig`） | 正常现象，Excel 双击能正确识别；用 pandas 读时加 `encoding="utf-8-sig"` |

---

## 7. 本仓库的三条发布红线

发布前请再确认一次，这三条同时写在稿件里，不能自相矛盾：

1. 展示与统计**只用 0–24 h 窗口**，仓库里的 `results/` 不得含超窗数字；
2. 三个空白对照**按批次分别报告、永不合并**；
3. 只用相对时长，**不出现绝对日期**（原始时间戳无年份，`t` 里的 2025 是解析产物）。

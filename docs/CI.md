# CI 与自托管运行器

PR 检查显式 checkout 当前 PR 的完整 head SHA；各平台使用同一份提交。普通 CI 不发布资产、合并 PR 或建立版本标签。正式发布仍由 [Release 工作流](RELEASE.md) 对已合入主线的固定 SHA 重新验收。

## 检查范围

| 检查 | 运行环境 | 验收内容 |
| --- | --- | --- |
| CI / macOS ARM64 regression | `kevin-mac-coal`，macOS ARM64 自托管 | 完整 Python 回归、前端回归、桌面 shell 回归、显式 TypeScript 检查、Web 与桌面模式前端构建、版本清单核对 |
| CI / test | GitHub 托管 Ubuntu，Python 3.11 / Node 22 | 原有全部回归与前端构建，以及真实 Dockerfile 的 Linux amd64 镜像构建、新库与旧库 HTTP 验收 |
| Windows build / Windows Server 2019 noninteractive build | `ustb-win-coal`，低权限自托管服务 | 完整回归、类型检查、Web/离线前端、冻结后端 HTTP 及临时数据库重启、NSIS/ZIP 编译与散列；不运行安装包或 GUI |
| Windows desktop / windows-x64 | GitHub 托管 Windows 2022，Python 3.11 / Node 22 | 原有全部回归、冻结后端、安装包与 ZIP 构建、NSIS 安装、已安装程序 Electron 操作、重启、卸载与用户数据保留 |

四项检查独立执行。Mac 成功或 Windows 构建成功不能替代 Linux 镜像或 Windows 安装验证；托管预算不足、下载失败或排队都不算通过。发布工作流和原平台验收要求保持不变。

## Mac 配置与隔离

运行器标签为 `[self-hosted, macOS, ARM64, local-mac, coal-web]`。机器需预装 `/opt/homebrew/bin/python3.12`（原生 ARM64）；作业先检查 Python 版本、架构与提交，再创建独立虚拟环境。Node 22 ARM64 由 `actions/setup-node` 提供。Mac 的 Python 3.12 回归补充 Linux/Windows 的 Python 3.11 覆盖。

仅在当前私有仓库、同仓库真人账号提交的 PR 或主线 push 上运行 Mac 作业。Fork、机器人 PR 和仓库变为公开后的事件不进入个人主机；Linux/Windows 托管检查仍执行。不使用 `pull_request_target`，权限仅为 `contents: read`，checkout 不持久化凭据，不传入部署密钥。

自托管运行器与本机用户共用权限，并非安全沙箱。维护者仍须确保同仓库分支和工作流修改可信。作业不执行 `sudo`、全局 Python 安装、Docker 清理或主机服务重启。

每次运行使用 `ci/<run-id>-<attempt>` checkout，Python 虚拟环境、npm 依赖及生成文件均位于该目录。结果记录后通过 `always()` 清理该次目录；同 PR 的旧 Mac 作业可被新提交取消。工具缓存由 Actions 管理。若进程强制退出或主机断电导致清理未执行，维护者应在确认没有活动作业后，仅清除该次遗留目录。

主机由两个仓库的 Runner 共用；作业要求启动时至少有 3 GiB 可用空间，还需保持代理和用户服务在线。服务安装、代理与启动方式由本机运维文档 `/Users/kevin/CodeWorkSpace/Ops/github-actions-runner.md` 管理，不向仓库复制私有环境文件或凭据。

## Windows Server 2019 非交互构建

使用 `[self-hosted, Windows, X64, local-windows, windows-build, coal-web]`。任务核对 Server 2019 build 17763、64 位进程、NetworkService SID `S-1-5-20`、非管理员与 Session 0；信任条件和 Mac 相同。两个仓库共用服务账号，不能视为安全沙箱。

系统已有 Git 2.9 / Python 3.10，任务不覆盖它们：checkout 前下载 [官方 MinGit 2.55.0.5](https://github.com/git-for-windows/git/releases/tag/v2.55.0.windows.5)，以发布元数据中的 SHA-256 验证；随后使用 [CPython 官方 NuGet 3.11.9](https://www.nuget.org/packages/python/3.11.9)（3.11 系列的 Windows 二进制版本）创建临时 venv。NuGet 固定 SHA-256 已与实际下载及官方 catalog SHA-512 交叉核对。它不是后续 3.11 安全更新的替代品；项目升级 Python 时应一起更新依赖与多平台验收。[Node 22.23.2 x64 官方 ZIP](https://nodejs.org/dist/v22.23.2/) 同样核对官方散列并解压。包来源、版本和散列固定在工作流/脚本中，失败即停止。

三个官方归档缓存在本 Runner 的 `_work/_cbos-package-cache`，每次使用前重新核验 SHA-256。缺失时下载到本次临时目录，校验成功才移入缓存，单次下载超时为 180 秒。服务器无法访问官方源时，可在可信机器从相同官方地址下载、校验后传入该目录；不能更换来源或跳过校验。缓存只保留归档，不安装软件或共享运行环境。

MinGit、CPython、venv、pip/npm/Electron/PyInstaller 缓存、临时数据库和产物位于本次任务的独立目录；仅通过 Actions 的任务 PATH/环境文件提供工具，不写系统 PATH、注册表、全局 Python 或业务目录。仅删除本次任务的 checkout 与临时目录；不清理其他 Runner、业务服务或共享数据。原生命令退出码会使步骤失败。

冻结后端通过随机 loopback 端口及临时数据目录测试六煤计算、导入导出、登录和重启；额外核对程序内置版本/SHA 与 checkout 一致。打包只执行 `dist:win --publish never`，不启动生成的安装器。Actions 日志和 Summary 中的 `CI_WINDOWS_BUILD_JSON` 记录服务身份、完整 SHA、步骤状态、pytest 统计、后端报告及 EXE/ZIP SHA-256。构建产物随后清理，不作为发行下载；正式流程仍重新构建并上传验收后的资产。

安装、覆盖升级、卸载和 Electron GUI 必须使用独立非业务测试账号及可丢弃的环境。当前完整 Windows 工作流明确要求 `RUNNER_ENVIRONMENT=github-hosted`；不得伪造环境变量或直接改为业务服务器 Runner。新增构建任务不生成 `windows-validation.json`，并始终标记 `full_windows_acceptance: false`。升级和 GUI 验收未执行时必须单独报告，不能以 Runner 在线、基础 smoke 或构建通过替代。

## 结果核对与重试

1. 在 PR Checks 打开具体 Actions 作业，核对 checkout SHA 与最新 PR head 相同。
2. Mac 的 Job Summary 与日志中的 `CI_VALIDATION_JSON` 包含实际 Runner 名称、系统/架构、版本、Python/Node 版本、run ID，以及从 pytest XML / 前端和 shell TAP 提取的测试统计和各步骤实际 outcome。报告未生成时显示 `null`，不会记为通过；须同时核对各步骤及最终结论。完整测试输出仍在 Actions 日志，可下载保存。Mac 这份额外报告不依赖 Artifact 存储配额；Linux/Windows 原有构建资产及验收产物仍须上传成功。
3. `Build web and offline frontend` 两次构建均须成功。它们验证共享界面编译；Windows 的冻结、安装和界面操作仍由 Windows 作业负责。
4. 若 GitHub 注明 `The job was not started because an Actions budget is preventing further use.`，说明托管作业未启动；恢复 Actions 预算后重跑失败作业，无需改变代码或跳过门禁。
5. 源码变化后推送新提交，重新执行新 SHA 的全部检查。保留失败日志定位根因，不能用旧 SHA 的成功记录替代。

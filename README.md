# Student Code Diagnosis

一个面向信息学教师的本地单题 C++ 代码 AI 诊断工具。

当前默认工作流不进行本地编译判题。教师可以输入 Vesibay 题目网址并粘贴一份
C++ 代码，也可以使用已授权的网站管理员账号读取提交详情和 OJ 判题证据，再使用
自己配置的模型 API 获得结构化教学诊断。

## 当前功能

- 通过 `https://www.vesibay.cn/problem/<题号>` 导入公开题；
- 支持训练页面中仍属于公开题库的 `/training/<训练ID>/problem/<题号>` 地址；
- 自动获取题号、标题、描述、输入、输出、提示、限制和公开样例；
- 导入后可在页面中校对和编辑题面；
- 通过文本框粘贴单份 C++ 代码；
- 支持通过题目网站内任意提交报告网址（直接、分组、训练或比赛路径）导入源码和判题证据；
- 管理员模式读取最终状态、测试点状态、输入和标准输出；
- 上传型测试数据通过只读下载接口获取，并仅在内存中安全解压 `.in/.out` 内容；
- 管理员响应会在本地剔除用户名、UID、IP 等身份信息；
- 支持 DeepSeek 和自定义 OpenAI 兼容服务；
- 可设置 API 基础地址、模型名称、思考/非思考模式、超时和输出长度；
- 使用 JSON Output 并在本地严格校验诊断结果；
- 展示结论、可信度、问题类别、代码证据、样例推演、建议和教学反馈。
- API Key 和 Vesibay 账号使用 Windows DPAPI 加密保存在本机。

当前不支持班级名单和批量导入。

## 安装与启动

普通教师推荐下载 GitHub Releases 中的 `StudentCodeDiagnosis-Setup-<版本>.exe`，
运行安装程序后从桌面或开始菜单启动。安装版自带 Python 运行环境，不要求另行安装
Python、Streamlit 或 g++，程序仅监听本机 `127.0.0.1` 并自动打开浏览器。

源码开发方式要求 Python 3.11 或更高版本：

要求 Python 3.11 或更高版本。

```powershell
cd D:\work\student_code_diagnosis
python -m pip install -r requirements.txt
python -m streamlit run app.py
```

Windows 源码版也可以直接双击：

```text
start_streamlit.bat
```

## 使用流程

1. 在侧边栏选择模型服务并填写 API Key，然后点击“保存设置”。
2. DeepSeek 默认配置为：
   - API 基础地址：`https://api.deepseek.com`
   - 模型：`deepseek-v4-flash`
   - 模式：非思考模式
3. 可先点击“测试连接”。
4. 选择“题目网址＋粘贴代码”或“Vesibay提交详情网址”。
5. 手动模式下导入题面、校对内容并粘贴代码。
6. 提交模式下先在侧边栏验证并保存网站账号，再粘贴普通或组内提交详情网址。
7. 点击“开始AI诊断”。

## 模型设置与 API Key

非敏感设置保存在：

```text
%LOCALAPPDATA%\StudentCodeDiagnosis\config\settings.json
```

API Key 不会写入普通配置、数据库或历史记录。点击“保存设置”后，它会通过
Windows DPAPI 加密写入
`%LOCALAPPDATA%\StudentCodeDiagnosis\config\secrets.json`，只能由保存它的
Windows 用户解密；
也可通过 `DEEPSEEK_API_KEY` 环境变量覆盖。页面提供“清除Key”按钮。

本地数据库、任务数据和临时目录分别位于：

```text
%LOCALAPPDATA%\StudentCodeDiagnosis\data
%LOCALAPPDATA%\StudentCodeDiagnosis\temp
```

升级或卸载程序不会把个人设置打包进安装目录。首次运行新版本时，程序会把旧源码
目录中的设置和数据迁移到上述用户数据目录；目标位置已有文件时不会覆盖。

Vesibay 用户名和密码使用相同的本机加密存储。程序启动后用它们换取网站
`Authorization` 令牌，令牌只驻留当前进程内存。网站目前返回的是管理员令牌，
并非服务端限制权限的只读令牌；“只读”由本工具的固定接口白名单保证。

DeepSeek 请求在非思考模式下显式发送：

```json
{"thinking": {"type": "disabled"}}
```

选择思考模式时发送 `enabled`。自定义 OpenAI 兼容服务不会收到 DeepSeek 专用的
`thinking` 字段，也不会被强制发送 `temperature`，从而使用各模型自己的合法默认值。
DeepSeek非思考模式仍使用 `temperature=0.2`；DeepSeek思考模式按官方要求省略该参数。
“测试连接”会同时检查配置的模型是否存在于当前API Key返回的模型列表中，避免出现
连接测试成功、正式诊断时才提示模型不存在或无权限的情况。

复杂代码推演可能产生较多思考Token，默认请求超时为300秒、最大输出为12000 Token；
教师仍可在设置页按所用模型的限制自行调整。

## 诊断边界

本工具把以下内容发送给教师配置的第三方模型服务：

- 题目标题和描述；
- 输入、输出和提示；
- 公开样例输入与输出；
- 粘贴的 C++ 源代码。

手动粘贴模式不会编译或运行代码，也没有隐藏测试数据。提交详情模式会使用 OJ
已经产生的判题状态统计。测试点详情和学生源码默认折叠并只在本机显示；只有教师
选中测试点并主动开启“发送选中的测试点详情给模型”后，才会把相应输入、标准输出、
时间、内存及运行错误信息作为诊断证据。开启该选项后，程序还会在独立临时目录中
编译一次学生源码，只运行教师选中的测试点，并把本地捕获的实际输出一并发送给模型。
Windows本地验证程序使用128MB栈保留空间，以减少OJ与Windows默认栈大小差异造成的
假性运行错误；服务还会预先计算首个输出差异行，模型只负责结合源码解释原因。
发送给模型的标准输出会明确标记为网站的
权威标准答案，并明确声明证据不含学生实际输出；模型不得臆测学生输出。网站的历史
提交接口不提供可靠的学生程序
输出，因此 WA 详情不会伪造或展示“学生输出”。本工具仍不会重新运行代码。结果使用
`likely_correct`、`likely_incorrect` 和 `uncertain`，不会冒充新的确定性判题结果。

## 安全边界

- 题目导入仅允许 HTTPS 的 `www.vesibay.cn` 公开题路径；
- 实际 API 地址由程序从题号构造，不直接请求任意用户网址；
- 禁止自动跳转，限制响应大小并设置超时；
- 题面和代码按不可信数据放入提示词；
- 模型输出必须通过本地字段、类型、枚举和置信度校验；
- 常见字段别名、中文类别、百分比置信度和字符串行号会先归一化；
- 首次返回仍不合规时，会要求模型仅修复JSON格式并自动重试一次；
- API Key 不进入提示词或日志。
- 网站账号、密码和令牌不进入提示词、SQLite 或日志；
- 管理员客户端只允许登录、身份、提交详情、测试点和题目读取请求；
- 测试数据包限制压缩大小、文件数、单文件大小和解压后总大小，不写入磁盘；
- 测试点右上角复选框独立控制是否选中，点击 WA/RE 方块只负责打开详情；
- RE详情保留网站原始错误信息、测试点输入和标准输出，并提供基于固定规则的中文可能原因；
- 提交证据发送给模型前会删除用户名、UID、IP 和其他身份字段；
- 隐藏测试数据默认不发送；教师主动选中并开启发送选项后才会发送给第三方模型；
- 本地只运行教师勾选的测试点，复用受控Runner的时间限制和进程树清理，任务结束后
  删除源码、可执行文件和运行目录；该机制不是OS安全沙箱，不能抵御蓄意恶意代码；
- 本机 `secrets.json` 只保存 DPAPI 密文，用户设置、数据库和任务数据均被
  `.gitignore` 排除，也不会进入安装包。

## 版本与更新

当前版本号由 `core/version.py` 统一维护。侧边栏中的“检查更新”只读取 GitHub
最新正式 Release 的版本与安装包地址，不会自动下载或静默安装。教师确认后可从
GitHub 下载新版安装程序覆盖安装。

## 测试

```powershell
python -m pytest -ra
```

网络服务测试使用注入的假传输层，不依赖真实 API Key 或网络。真实 Vesibay 导入
可在人工测试时单独验证。

## Windows 打包与发布

维护者需要 Python 3.11/3.12、PyInstaller 6 和 Inno Setup 6：

```powershell
python -m pip install -r requirements-build.txt
powershell -ExecutionPolicy Bypass -File scripts\build_windows.ps1
```

输出位于 `dist\installer`，并同时生成 SHA-256 校验文件。推送形如 `v1.0.0` 的
标签后，GitHub Actions 会在 Windows 环境运行全部测试、构建安装程序并发布 Release。

## 代码分层

- `models/imported_problem.py`：导入后的题面与公开样例；
- `models/ai_code_diagnosis.py`：结构化 AI 诊断结果；
- `models/vesibay_submission.py`：脱敏后的 OJ 提交与测试点证据；
- `services/problem_importer.py`：Vesibay 公开题导入；
- `services/json_http_client.py`：有大小、超时和重定向限制的 JSON HTTP；
- `services/ai_code_diagnosis_service.py`：提示词、API 请求和结果校验；
- `services/vesibay_readonly_client.py`：管理员登录和固定白名单只读导入；
- `services/secret_store.py`：Windows DPAPI 本地凭据保护；
- `services/credential_service.py`：模型和网站凭据管理；
- `services/settings_service.py`：非敏感模型设置；
- `ui/components/`：Streamlit 输入与结果展示；
- `ui/app.py`：页面组合，不包含网络协议和诊断解析逻辑。

仓库中早期编译、判题、历史和班级模块暂时保留用于兼容既有测试与数据，但新的
默认产品流程和页面不会调用这些模块。

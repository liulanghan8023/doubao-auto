# doubao-automation

基于 Python、Playwright 和 Vue 的网页自动化脚手架，包含：

- `.env` 配置管理
- 首次手动登录并持久化会话
- 网页控制台
- 单次执行入口
- `start` / `stop` 脚本

## 目录结构

```text
.
├── pyproject.toml
├── scripts/
│   ├── bootstrap.sh
│   ├── install_browser.sh
│   ├── login.sh
│   ├── run_once.sh
│   ├── start.sh
│   └── stop.sh
└── src/doubao_automation/
    ├── browser.py
    ├── cli.py
    ├── config.py
    ├── logging.py
    ├── runner.py
    ├── tasks.py
    ├── service.py
    └── web.py
├── web/
│   ├── src/
│   │   ├── App.vue
│   │   ├── main.js
│   │   └── styles.css
│   ├── index.html
│   ├── package.json
│   └── vite.config.js
```

## 快速开始

1. 初始化虚拟环境并安装依赖：

```bash
./scripts/bootstrap.sh
```

2. 安装 Playwright 浏览器：

```bash
./scripts/install_browser.sh
```

3. 准备环境变量：

```bash
cp .env.example .env
```

4. 启动网页控制台：

```bash
./scripts/start.sh
```

脚本会以前台方式运行，并在当前终端直接输出日志。

然后打开 `http://127.0.0.1:8000`

停止服务时，直接在当前终端按 `Ctrl+C`

5. 在网页里点击 `打开登录窗口`，首次完成豆包登录。

6. 登录完成后，你可以在网页里直接：

- 管理提示词模板
- 新建任务并选择模板
- 选择一张本地参考图
- 编辑图片和视频提示词
- 发起图片生成或视频提交
- 查看日志和状态

## 命令行备用入口

如果你仍然希望从命令行触发，也保留了这些脚本：

```bash
./scripts/login.sh
./scripts/run_once.sh
```

## 环境变量

- `AUTOMATION_TARGET_URL`: 目标网页地址
- `AUTOMATION_HEADLESS`: 是否无头运行，默认 `true`
- `AUTOMATION_TIMEOUT_MS`: 页面超时，默认 `30000`
- `AUTOMATION_SCREENSHOT_PATH`: 截图输出路径
- `AUTOMATION_LOG_LEVEL`: 日志级别，默认 `INFO`
- `AUTOMATION_BROWSER_PROFILE_DIR`: Playwright 持久化登录目录
- `AUTOMATION_LOGIN_WAIT_SECONDS`: 首次登录等待时长，默认 `180`

## 登录机制

- 首次可执行 `./scripts/login.sh`，或者在网页中点击 `打开登录窗口`
- 你在浏览器里手动完成登录，脚本会等待登录态稳定后关闭浏览器
- 登录状态会保存在本地 `runtime/browser-profile`
- 后续执行会复用这个浏览器 Profile，不再要求重新登录

如果登录过期，删掉 `runtime/browser-profile` 后重新执行 `./scripts/login.sh`

## 图像生成下载

- 单次执行会先跳转到新的生成会话，再只抓取当前会话中新出现的结果图 URL
- 图片内容会通过页面会话直接下载，并保存到 `runtime/generated-images`

## 网页控制台说明

- 后端使用 FastAPI 暴露任务、模板、登录、单次执行等接口
- 前端是 Vite + Vue + Vue Flow 控制台页面，代码已拆成组件、composable 和工具文件
- 任务数据持久化在 `runtime/app.db`，服务启动时如果数据库文件不存在会自动创建并建表
- 提示词模板保存在 `prompt_templates` 表，字段包括 `id`、`name`、`image_prompt`、`video_prompt`、`created_at`
- 任务支持绑定模板；选中模板后，任务的图片和视频提示词会自动使用该模板内容
- “新建任务” 会把当前表单恢复到配置默认值
- 节点 2 会展示当前任务最近一次图片生成产物，节点 3 会展示视频提交状态

## 后续扩展建议

- 在 `runner.py` 中补充登录后的业务动作，例如发送消息、读取回复、导出结果
- 为核心流程增加 `pytest` 测试
- 如果需要正式前端工程化，可以再把 `web/` 迁移到 Vite + Vue 单文件组件结构

# OCR-Kit

基于 **PP-OCRv6、ONNX Runtime、FastAPI 与 Vue 3** 构建的现代 OCR 工作台。支持图片和 PDF 文档识别、逐页结果展示、检测框与文本联动、实时进度日志以及结果导出。

## 界面预览

![OCR-Kit PDF 逐页识别与文字联动界面](docs/images/ocr-kit-workbench.png)

## 功能特性

- 图片 OCR：支持 JPG、PNG、WebP、BMP、TIFF 等常见格式
- PDF OCR：按页渲染并逐页识别，可配置 DPI 和最大处理页数
- 坐标框联动：悬停或点击识别框，同步定位右侧文字
- PDF 分页联动：PDF 页面、检测框和识别结果同步切换
- 流式进度：通过 Server-Sent Events 实时显示日志和分页结果
- 结果检索：支持当前页文字搜索和低置信度筛选
- 结果导出：复制单行、当前页、全部内容或导出 TXT
- 识别历史：在浏览器本地保存近期识别结果
- 明暗主题：工业扫描工作台风格，支持深色和浅色模式
- 跨平台：支持 Windows PowerShell、Linux 和 WSL

## 技术栈

### 后端

- Python 3.11 / 3.12
- FastAPI
- PaddleOCR 3
- PP-OCRv6
- ONNX Runtime
- PyMuPDF
- Pillow
- NumPy

### 前端

- Vue 3
- Vite
- PDF.js
- 原生 SSE
- Canvas 与 SVG OCR 覆盖层

## 系统架构

```text
┌──────────────────── Vue 3 Frontend ────────────────────┐
│ 文件上传 │ PDF.js 页面渲染 │ OCR 框联动 │ 日志与结果流 │
└───────────────────────┬────────────────────────────────┘
                        │ HTTP / SSE
┌───────────────────────▼────────────────────────────────┐
│                    FastAPI Server                       │
│ 图片预处理 │ PDF 页面渲染 │ 任务调度 │ 流式事件广播    │
└───────────────────────┬────────────────────────────────┘
                        │
┌───────────────────────▼────────────────────────────────┐
│             PP-OCRv6 + ONNX Runtime                     │
│               文字检测与文字识别                        │
└────────────────────────────────────────────────────────┘
```

## 项目结构

```text
OCR-Kit/
├── server.py                 # FastAPI OCR 服务
├── requirements.txt          # Python 依赖
├── download_models.py        # 可选模型下载脚本
├── test_ocr.py               # 命令行 OCR 测试
└── frontend/
    ├── src/
    │   ├── api/              # HTTP 与 SSE 客户端
    │   ├── components/       # 上传、结果、日志和历史组件
    │   ├── composables/      # OCR 与历史状态管理
    │   └── assets/           # 全局视觉样式
    ├── public/               # 图标等静态资源
    ├── package.json
    └── vite.config.js
```

## 快速开始

### 1. 克隆项目

```bash
git clone https://github.com/chun-hua/OCR-Kit.git
cd OCR-Kit
```

### 2. 创建 Python 环境

推荐使用 Python 3.11 或 Python 3.12，并使用独立环境安装依赖。

#### Windows PowerShell

```powershell
py -3.11 -m venv venv-win
.\venv-win\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

如果 PowerShell 禁止执行激活脚本：

```powershell
Set-ExecutionPolicy -Scope Process Bypass
.\venv-win\Scripts\Activate.ps1
```

#### Linux / WSL

```bash
python3 -m venv venv
source venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

> Windows 与 Linux/WSL 的虚拟环境不可混用。

### 3. 启动后端

```bash
python server.py
```

默认地址为 `http://localhost:8765`。

自定义监听地址和端口：

```bash
python server.py --host 0.0.0.0 --port 8080
```

### 4. 启动前端

打开另一个终端：

```bash
cd frontend
npm install
npm run dev
```

访问 `http://localhost:5173`。

## API

| 方法   | 路径           | 说明             |
| ------ | -------------- | ---------------- |
| `GET`  | `/health`      | 服务健康检查     |
| `POST` | `/ocr/image`   | 识别单张图片     |
| `POST` | `/ocr/pdf`     | 逐页识别 PDF     |
| `POST` | `/ocr/text`    | 返回图片纯文本   |
| `GET`  | `/ocr/logs`    | OCR 实时日志 SSE |
| `GET`  | `/ocr/results` | PDF 分页结果 SSE |

### 图片识别

```bash
curl -X POST -F "file=@example.png" http://localhost:8765/ocr/image
```

### PDF 识别

```bash
curl -X POST \
  -F "file=@example.pdf" \
  "http://localhost:8765/ocr/pdf?dpi=200&max_pages=0"
```

参数：

- `dpi`：PDF 页面渲染清晰度，范围 `72-600`
- `max_pages`：最大处理页数，`0` 表示全部页面

## 命令行测试

```bash
python test_ocr.py example.png
python test_ocr.py example.pdf
```

## 模型说明

首次执行 OCR 时，PaddleOCR 会自动下载所需模型。项目默认设置 Hugging Face 镜像：

```text
https://hf-mirror.com
```

也可以提前下载模型：

```bash
python download_models.py
```

下载后的模型位于本地 `models/` 目录，该目录不会提交到 Git。

## 生产构建

```bash
cd frontend
npm install
npm run build
```

生成文件位于 `frontend/dist/`。

## 常见问题

### `numpy.dtype size changed`

这通常表示 NumPy 与 `scikit-image` 等二进制包版本不兼容。不要在 Anaconda `base` 环境中混合安装大量 pip 包，建议创建独立环境：

```powershell
conda create -n pp-ocr python=3.11 -y
conda activate pp-ocr
python -m pip install -r requirements.txt
```

### PowerShell 找不到 `Activate.ps1`

Windows 虚拟环境的激活脚本位于：

```powershell
.\venv-win\Scripts\Activate.ps1
```

WSL/Linux 中创建的环境使用 `venv/bin/activate`，不能直接在 Windows PowerShell 中使用。

### PDF 页面较慢或内存占用较高

- 将 DPI 从 `200` 调低至 `150`
- 使用 `max_pages` 限制处理页数
- 避免同时提交多个超大 PDF

## 隐私与安全

- 上传文件仅发送到当前配置的 OCR 后端
- 浏览器历史记录保存在本地存储中
- 仓库不包含用户文档、模型文件、虚拟环境或本地配置
- 请勿将 `.env`、密钥、访问令牌或私有文档提交到仓库

## 开发检查

```bash
python -m py_compile server.py test_ocr.py download_models.py

cd frontend
npm run build
npm audit --omit=dev
```

## 后续计划

- 批量文件识别
- 导出 JSON、Markdown 和可搜索 PDF
- 任务取消与队列管理
- 自定义模型目录和离线模式
- 表格与版面结构识别
- Docker 部署

欢迎通过 Issue 提交问题和功能建议。

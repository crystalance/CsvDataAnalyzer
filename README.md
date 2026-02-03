# CSV 数据分析系统 (Code Interpreter)

基于大模型的 CSV 数据分析系统，仿照 OpenAI Code Interpreter 设计思想构建。

## 功能特点

- **自然语言交互**: 用自然语言描述数据分析需求，AI 自动生成 Python 代码
- **代码自动执行**: 生成的代码在沙箱环境中自动执行
- **智能纠错**: 代码执行失败时自动修正重试（最多3次）
- **图表生成**: 支持 matplotlib 图表，自动保存并显示
- **对话记忆**: 支持多轮对话，可利用上下文进行关联分析
- **多模型支持**: 支持通义千问(Qwen)、OpenAI、DeepSeek

## 项目结构

```
CsvDataAnalyzer/
├── app.py                  # Gradio Web 应用入口
├── analyzer.py             # 核心分析器类
├── llm/
│   ├── __init__.py
│   ├── base.py             # LLM 抽象基类
│   ├── qwen.py             # 通义千问实现
│   ├── openai_llm.py       # OpenAI 实现
│   └── deepseek.py         # DeepSeek 实现
├── core/
│   ├── __init__.py
│   ├── executor.py         # 代码执行器
│   └── prompts.py          # Prompt 模板
├── config.py               # 配置管理
├── requirements.txt        # 依赖列表
└── README.md
```

## 快速开始

### macOS

```bash
# 1. 创建虚拟环境
python3 -m venv venv
source venv/bin/activate

# 2. 安装依赖
pip install -r requirements.txt

# 3. 配置 API Key
cp .env.example .env
# 编辑 .env 文件，填入 API Key

# 4. 运行
python app.py

# 5. 浏览器访问 http://localhost:7860
```

### Windows

```powershell
# 1. 创建虚拟环境
python -m venv venv
.\venv\Scripts\activate

# 2. 安装依赖
pip install -r requirements.txt

# 3. 配置 API Key
copy .env.example .env
# 编辑 .env 文件，填入 API Key

# 4. 运行
python app.py

# 5. 浏览器访问 http://localhost:7860
```

## 配置说明

在 `.env` 文件中配置 API Key：

```
# 通义千问 API Key (必填)
DASHSCOPE_API_KEY=your_key_here

# OpenAI API Key (可选)
OPENAI_API_KEY=your_key_here

# DeepSeek API Key (可选)
DEEPSEEK_API_KEY=your_key_here
```

## 使用说明

1. **上传 CSV 文件**: 点击上传区域选择 CSV 文件
2. **选择模型**: 从下拉菜单选择要使用的大模型
3. **输入问题**: 在输入框中用自然语言描述数据分析需求
4. **查看结果**: 系统会显示生成的代码、执行结果、图表和分析解释
5. **继续对话**: 可以基于之前的分析继续提问
6. **清空对话**: 点击"清空对话"开始新的分析会话

## 示例问题

假设上传的 CSV 文件包含销售数据：

1. "分析 Clothing 随时间变化的总销售额趋势"
2. "对 Bikes 进行同样的分析"
3. "哪些年份 Components 比 Accessories 的总销售额高?"

## 依赖说明

- `gradio>=4.0.0` - Web UI 框架
- `dashscope>=1.14.0` - 通义千问 SDK
- `openai>=1.0.0` - OpenAI SDK (也用于 DeepSeek)
- `pandas>=2.0.0` - 数据处理
- `matplotlib>=3.7.0` - 图表生成
- `python-dotenv>=1.0.0` - 环境变量管理

## 注意事项

- 图表标签使用英文以避免中文显示问题
- 代码在受限环境中执行，可能不支持所有 Python 功能
- 大文件分析可能需要较长时间
- 请确保 API Key 配置正确

## License

MIT

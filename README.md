# CSV Data Analyzer

A Code Interpreter-style data analysis system powered by Large Language Models.

English | [中文](README_CN.md)

## What & Why

### What is this?

This project implements a **Code Interpreter** pattern - a system that:
1. Takes natural language questions about data
2. Generates Python code to answer those questions
3. Executes the code in a sandboxed environment
4. Returns results (text, tables, charts) to the user

### Why build this?

Inspired by OpenAI's Code Interpreter (now called Advanced Data Analysis), this project demonstrates how to build a similar system using open-source components:

- **Democratize data analysis**: Users don't need to know Python to analyze data
- **Transparent reasoning**: Unlike black-box AI, users can see and verify the generated code
- **Iterative refinement**: The system learns from execution errors and self-corrects

---

## System Design

### Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              Gradio Web UI                                  │
│                           (app.py - Frontend)                               │
└─────────────────────────────────────────────────────────────────────────────┘
                                     │
                                     ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                             CSVAnalyzer                                     │
│                     (analyzer.py - Orchestrator)                            │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │  • Manages conversation history                                     │    │
│  │  • Coordinates LLM and Executor                                     │    │
│  │  • Implements retry logic with error feedback                       │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────────────────────┘
                          │                    │
                          ▼                    ▼
┌─────────────────────────────────┐  ┌─────────────────────────────────────────┐
│         LLM Layer               │  │              Core Layer                 │
│         (llm/)                  │  │              (core/)                    │
│  ┌───────────────────────────┐  │  │  ┌─────────────────────────────────┐    │
│  │  BaseLLM (Abstract)       │  │  │  │  CodeExecutor                   │    │
│  │    ├── QwenLLM            │  │  │  │  • Sandboxed code execution     │    │
│  │    ├── OpenAILLM          │  │  │  │  • Output/figure capture        │    │
│  │    └── DeepSeekLLM        │  │  │  └─────────────────────────────────┘    │
│  └───────────────────────────┘  │  │  ┌─────────────────────────────────┐    │
│                                 │  │  │  ErrorHandler                   │    │
│                                 │  │  │  • Error classification         │    │
│                                 │  │  │  • Targeted fix suggestions     │    │
│                                 │  │  └─────────────────────────────────┘    │
│                                 │  │  ┌─────────────────────────────────┐    │
│                                 │  │  │  PromptBuilder                  │    │
│                                 │  │  │  • System prompts               │    │
│                                 │  │  │  • Error correction prompts     │    │
│                                 │  │  └─────────────────────────────────┘    │
└─────────────────────────────────┘  └─────────────────────────────────────────┘
```

### Request Flow

```
User Question: "What is the average sales by region?"
                              │
                              ▼
┌──────────────────────────────────────────────────────────────────────────────┐
│ Step 1: Build Context                                                        │
│ ┌──────────────────────────────────────────────────────────────────────────┐ │
│ │ System Prompt + CSV Schema + Conversation History + User Question        │ │
│ └──────────────────────────────────────────────────────────────────────────┘ │
└──────────────────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌──────────────────────────────────────────────────────────────────────────────┐
│ Step 2: LLM Generates Code                                                   │
│ ┌──────────────────────────────────────────────────────────────────────────┐ │
│ │ ```python                                                                │ │
│ │ df = pd.read_csv(csv_path)                                               │ │
│ │ result = df.groupby('Region')['Sales'].mean()                            │ │
│ │ print(result)                                                            │ │
│ │ ```                                                                      │ │
│ └──────────────────────────────────────────────────────────────────────────┘ │
└──────────────────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌──────────────────────────────────────────────────────────────────────────────┐
│ Step 3: Execute Code                                                         │
│ ┌────────────────────────────────┐    ┌────────────────────────────────────┐ │
│ │ Success?                       │    │ Output:                            │ │
│ │   YES ──────────────────────────────▶ Region                             │ │
│ │                                │    │ East     1523.45                   │ │
│ │                                │    │ West     1821.30                   │ │
│ │                                │    │ ...                                │ │
│ └────────────────────────────────┘    └────────────────────────────────────┘ │
│                 │ NO                                                         │
│                 ▼                                                            │
│ ┌──────────────────────────────────────────────────────────────────────────┐ │
│ │ Error Feedback Loop (up to 3 retries)                                    │ │
│ │   1. Classify error (KeyError, TypeError, etc.)                          │ │
│ │   2. Generate targeted fix suggestions                                   │ │
│ │   3. Send error context back to LLM                                      │ │
│ │   4. LLM generates corrected code                                        │ │
│ │   5. Re-execute                                                          │ │
│ └──────────────────────────────────────────────────────────────────────────┘ │
└──────────────────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌──────────────────────────────────────────────────────────────────────────────┐
│ Step 4: Generate Explanation                                                 │
│ ┌──────────────────────────────────────────────────────────────────────────┐ │
│ │ LLM summarizes the results in natural language                           │ │
│ └──────────────────────────────────────────────────────────────────────────┘ │
└──────────────────────────────────────────────────────────────────────────────┘
                              │
                              ▼
                    Display to User
```

---

## Key Design Choices

### 1. Error Feedback Loop

**Why?** LLMs occasionally generate code with errors (wrong column names, type mismatches, syntax errors). Instead of failing immediately, we:

```python
for attempt in range(max_retries):  # Default: 3 attempts
    code = llm.generate(messages)
    result = executor.execute(code)

    if result.success:
        return result

    # Classify error and build targeted feedback
    error_info = ErrorClassifier.classify(result.error)
    hint = ErrorClassifier.get_hint(error_info)  # e.g., "Column 'Sales' not found. Available: ['Revenue', 'Quantity']"

    # Add error context for next attempt
    messages.append({"role": "user", "content": error_context})
```

**Benefits:**
- **Higher success rate**: Many errors are fixable with proper feedback
- **Better UX**: Users don't need to manually debug LLM-generated code
- **Learning opportunity**: Error context helps LLM understand the data better

### 2. Error Classification

We classify errors into 8 types with targeted suggestions:

| Error Type | Example | Suggestion |
|------------|---------|------------|
| `KEY_ERROR` | `KeyError: 'Sales'` | Check column names, show available columns |
| `TYPE_ERROR` | `TypeError: cannot convert...` | Suggest `astype()`, `pd.to_numeric()` |
| `VALUE_ERROR` | `ValueError: could not convert '$1,234'` | Suggest data cleaning (remove `$`, `,`) |
| `SYNTAX_ERROR` | `SyntaxError: invalid syntax` | Check brackets, indentation |
| ... | ... | ... |

### 3. Modular LLM Layer

**Why abstract the LLM?** Different LLMs have different APIs, rate limits, and capabilities. Our design:

```python
class BaseLLM(ABC):
    @abstractmethod
    def chat(self, messages: list[dict]) -> str:
        pass

class QwenLLM(BaseLLM):      # DashScope API
class OpenAILLM(BaseLLM):    # OpenAI API
class DeepSeekLLM(BaseLLM):  # OpenAI-compatible API
```

**Benefits:**
- **Easy to switch**: Change model with one line
- **Easy to extend**: Add new models by implementing `BaseLLM`
- **Testable**: Mock LLM for unit tests

### 4. Sandboxed Execution

Code runs in a controlled environment with:
- Pre-imported libraries (`pandas`, `matplotlib`)
- Captured stdout/stderr
- Automatic figure saving
- No file system access outside designated directories

---

## Project Structure

```
CsvDataAnalyzer/
├── app.py                      # Gradio Web UI
├── analyzer.py                 # Core orchestrator (CSVAnalyzer)
├── config.py                   # Configuration management
│
├── llm/                        # LLM abstraction layer
│   ├── base.py                 # Abstract base class
│   ├── qwen.py                 # Qwen (通义千问) implementation
│   ├── openai_llm.py           # OpenAI implementation
│   └── deepseek.py             # DeepSeek implementation
│
├── core/                       # Core execution components
│   ├── executor.py             # Sandboxed code executor
│   ├── error_handler.py        # Error classification & suggestions
│   └── prompts.py              # Prompt templates
│
├── tests/                      # Test suite
│   ├── test_error_handler.py   # Unit tests for error handling
│   └── test_error_correction_flow.py  # Integration tests
│
├── history/                    # Saved conversations (auto-generated)
├── outputs/                    # Generated figures (auto-generated)
└── data/                       # Sample CSV files
```

---

## How to Run

### Prerequisites

- Python 3.10+
- API key for at least one LLM provider

### Installation

```bash
# Clone the repository
git clone <repo-url>
cd CsvDataAnalyzer

# Create virtual environment
python3 -m venv venv
source venv/bin/activate  # On Windows: .\venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Configure API keys
cp .env.example .env
# Edit .env and add your API keys
```

### Configuration

Edit `.env` file:

```bash
# Required: At least one of these
DASHSCOPE_API_KEY=your_qwen_key      # For Qwen (通义千问)
OPENAI_API_KEY=your_openai_key       # For OpenAI
DEEPSEEK_API_KEY=your_deepseek_key   # For DeepSeek
```

### Run the Application

```bash
source venv/bin/activate
python app.py
# Open http://localhost:7860 in browser
# special remind: for windows user, you can't access 0.0.0.0:7860, but 127.0.0.1
```

### Run Tests

```bash
source venv/bin/activate

# Unit tests
python -m unittest tests/test_error_handler.py -v

# Integration test (error correction flow)
python tests/test_error_correction_flow.py --fail-count 2
```

### Test Error Correction in UI

1. Upload a CSV file
2. Expand "测试模式" (Test Mode) panel
3. Check "启用错误注入" (Enable Error Injection)
4. Set failure count (1-2)
5. Ask any question and watch the error correction process

---

## Example Usage

Upload a sales CSV and try these questions:

```
1. "Show the first 5 rows of data"
2. "What is the total sales by region?"
3. "Plot monthly sales trend"
4. "Which product category has the highest average sales?"
5. "Compare sales between 2022 and 2023"
```


## Tech Stack

| Component | Technology |
|-----------|------------|
| Frontend | Gradio 4.x |
| LLM | Qwen / OpenAI / DeepSeek |
| Data Processing | Pandas |
| Visualization | Matplotlib |
| Configuration | python-dotenv |

---

## License

MIT

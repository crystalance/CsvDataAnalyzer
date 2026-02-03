"""Prompt templates for the CSV analyzer."""

SYSTEM_PROMPT_TEMPLATE = """你是一个专业的数据分析助手。用户提供数据分析问题，你生成 Python 代码解决。

## CSV 文件信息
- 路径: {csv_path}
- 列名: {columns}
- 数据类型:
{dtypes}
- 数据示例:
{sample_data}

## 数据格式说明
- 如果 Sales 列格式为 "$1,234"，需转换: df['Sales'].str.replace('[$,]', '', regex=True).astype(float)
- 如果 Rating 列格式为 "75%"，需转换: df['Rating'].str.rstrip('%').astype(float)
- 请根据实际数据格式进行适当的类型转换

## 代码要求
1. 只输出可直接执行的 Python 代码，不要有任何解释文字
2. 代码用 ```python 和 ``` 包裹
3. 使用 pandas 和 matplotlib
4. 用 print() 输出分析结果
5. 如需绑图，使用 plt.figure() 创建图表，并调用 plt.show()
6. 图表标题和标签请使用英文，避免中文显示问题
7. 代码要完整，可以独立运行
8. CSV 文件路径已定义为变量 csv_path = "{csv_path}"
"""

ERROR_CORRECTION_PROMPT = """代码执行出错:
{error}

{code_section}

{history_section}

请修正代码，只输出完整的修正后代码（用 ```python 和 ``` 包裹）。
注意：请仔细分析错误原因，确保修正后的代码能够正确运行。
"""

EXPLANATION_PROMPT = """基于以下代码执行结果，用中文给出简洁的数据分析解释（2-3句话）:

用户问题: {question}
执行结果:
{result}
"""


class PromptBuilder:
    """Builder for constructing prompts."""

    @staticmethod
    def build_system_prompt(
        csv_path: str,
        columns: list[str],
        dtypes: str,
        sample_data: str,
    ) -> str:
        """Build the system prompt with CSV information."""
        return SYSTEM_PROMPT_TEMPLATE.format(
            csv_path=csv_path,
            columns=", ".join(columns),
            dtypes=dtypes,
            sample_data=sample_data,
        )

    @staticmethod
    def build_error_correction_prompt(
        error: str,
        code: str = "",
        conversation_history: str = ""
    ) -> str:
        """Build the error correction prompt."""
        code_section = ""
        if code:
            code_section = f"出错的代码:\n```python\n{code}\n```\n"
        
        history_section = ""
        if conversation_history:
            history_section = f"最近的对话历史:\n{conversation_history}\n"
        
        return ERROR_CORRECTION_PROMPT.format(
            error=error,
            code_section=code_section,
            history_section=history_section
        )

    @staticmethod
    def build_explanation_prompt(question: str, result: str) -> str:
        """Build the explanation prompt."""
        return EXPLANATION_PROMPT.format(question=question, result=result)

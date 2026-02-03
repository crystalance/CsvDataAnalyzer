"""Error classification and handling for code execution failures."""

import re
from enum import Enum
from dataclasses import dataclass


class ErrorType(Enum):
    """Types of code execution errors."""
    SYNTAX_ERROR = "syntax"
    NAME_ERROR = "name"
    TYPE_ERROR = "type"
    KEY_ERROR = "key"
    INDEX_ERROR = "index"
    IMPORT_ERROR = "import"
    VALUE_ERROR = "value"
    ATTRIBUTE_ERROR = "attribute"
    RUNTIME_ERROR = "runtime"


@dataclass
class ErrorInfo:
    """Structured error information."""
    error_type: ErrorType
    message: str
    details: dict


# Hints for each error type
ERROR_HINTS = {
    ErrorType.KEY_ERROR: """
可能原因:
1. 列名拼写错误或大小写不匹配
2. 列名包含额外空格
修复建议: 请检查列名是否与可用列名完全一致""",

    ErrorType.NAME_ERROR: """
可能原因:
1. 变量未定义就使用
2. 函数名拼写错误
修复建议: 检查变量是否已正确定义，函数名是否正确""",

    ErrorType.TYPE_ERROR: """
可能原因:
1. 数据类型不匹配（如字符串与数字运算）
2. 函数参数类型错误
修复建议: 使用适当的类型转换，如 astype(), pd.to_numeric()""",

    ErrorType.VALUE_ERROR: """
可能原因:
1. 数据包含无法转换的值（如 '$1,234' 转数字）
2. 数据包含空值或特殊字符
修复建议: 先清洗数据（去除特殊字符、处理空值）再进行转换""",

    ErrorType.SYNTAX_ERROR: """
可能原因:
1. 括号不匹配
2. 缩进错误
3. 缺少冒号或逗号
修复建议: 检查代码语法格式""",

    ErrorType.INDEX_ERROR: """
可能原因:
1. 索引超出范围
2. 数据为空
修复建议: 先检查数据长度，使用安全的索引访问方式""",

    ErrorType.IMPORT_ERROR: """
可能原因:
1. 模块未安装
2. 模块名拼写错误
修复建议: 使用已导入的 pandas 和 matplotlib，避免导入其他模块""",

    ErrorType.ATTRIBUTE_ERROR: """
可能原因:
1. 对象没有该属性或方法
2. 数据类型不正确导致方法不可用
修复建议: 检查对象类型，使用正确的方法""",

    ErrorType.RUNTIME_ERROR: """
可能原因: 代码逻辑错误或数据问题
修复建议: 仔细检查代码逻辑和数据处理流程""",
}


class ErrorClassifier:
    """Classify and analyze code execution errors."""

    # Patterns for error classification
    _PATTERNS = [
        (r"SyntaxError", ErrorType.SYNTAX_ERROR),
        (r"NameError", ErrorType.NAME_ERROR),
        (r"TypeError", ErrorType.TYPE_ERROR),
        (r"KeyError", ErrorType.KEY_ERROR),
        (r"IndexError", ErrorType.INDEX_ERROR),
        (r"ImportError|ModuleNotFoundError", ErrorType.IMPORT_ERROR),
        (r"ValueError", ErrorType.VALUE_ERROR),
        (r"AttributeError", ErrorType.ATTRIBUTE_ERROR),
    ]

    @classmethod
    def classify(cls, error_msg: str) -> ErrorInfo:
        """
        Classify an error message and extract key information.

        Args:
            error_msg: The error message string.

        Returns:
            ErrorInfo with error type, message, and extracted details.
        """
        error_type = ErrorType.RUNTIME_ERROR
        details = {}

        # Determine error type
        for pattern, etype in cls._PATTERNS:
            if re.search(pattern, error_msg):
                error_type = etype
                break

        # Extract additional details based on error type
        if error_type == ErrorType.KEY_ERROR:
            # Extract the missing key/column name
            match = re.search(r"KeyError:\s*['\"]?([^'\"]+)['\"]?", error_msg)
            if match:
                details["missing_key"] = match.group(1)

        elif error_type == ErrorType.NAME_ERROR:
            # Extract the undefined name
            match = re.search(r"name\s+['\"](\w+)['\"]", error_msg)
            if match:
                details["undefined_name"] = match.group(1)

        elif error_type == ErrorType.ATTRIBUTE_ERROR:
            # Extract the missing attribute
            match = re.search(r"has no attribute\s+['\"](\w+)['\"]", error_msg)
            if match:
                details["missing_attribute"] = match.group(1)

        elif error_type == ErrorType.TYPE_ERROR:
            # Extract type information
            match = re.search(r"cannot\s+(\w+)\s+['\"]?(\w+)['\"]?", error_msg)
            if match:
                details["operation"] = match.group(1)
                details["type"] = match.group(2)

        return ErrorInfo(
            error_type=error_type,
            message=error_msg,
            details=details
        )

    @classmethod
    def get_hint(cls, error_info: ErrorInfo) -> str:
        """
        Get a helpful hint for the given error.

        Args:
            error_info: The classified error information.

        Returns:
            A helpful hint string.
        """
        base_hint = ERROR_HINTS.get(error_info.error_type, ERROR_HINTS[ErrorType.RUNTIME_ERROR])

        # Add specific details if available
        if error_info.error_type == ErrorType.KEY_ERROR and "missing_key" in error_info.details:
            base_hint += f"\n注意: 找不到的列名是 '{error_info.details['missing_key']}'"

        elif error_info.error_type == ErrorType.NAME_ERROR and "undefined_name" in error_info.details:
            base_hint += f"\n注意: 未定义的变量是 '{error_info.details['undefined_name']}'"

        return base_hint.strip()


def format_error_context(
    error_msg: str,
    code: str,
    columns: list[str],
    dtypes: str,
    conversation_history: str = ""
) -> str:
    """
    Format a comprehensive error context for LLM correction.

    Args:
        error_msg: The error message.
        code: The code that caused the error.
        columns: Available CSV column names.
        dtypes: DataFrame dtypes as string.
        conversation_history: Recent conversation history.

    Returns:
        Formatted error context string.
    """
    # Classify the error
    error_info = ErrorClassifier.classify(error_msg)
    hint = ErrorClassifier.get_hint(error_info)

    context_parts = [
        "## 代码执行出错\n",
        "### 错误信息",
        f"```\n{error_msg}\n```\n",
        "### 错误分析",
        f"- 错误类型: {error_info.error_type.value.upper()}",
        hint,
        "",
        "### 出错的代码",
        f"```python\n{code}\n```\n",
        "### CSV 数据信息",
        f"- 可用列名: {', '.join(columns)}",
        f"- 数据类型:\n{dtypes}\n",
    ]

    if conversation_history:
        context_parts.extend([
            "### 最近对话历史",
            conversation_history,
            ""
        ])

    context_parts.extend([
        "### 修复要求",
        "1. 仔细分析上述错误原因",
        "2. 参考可用列名，确保列名正确",
        "3. 输出完整的修正后代码（用 ```python 和 ``` 包裹）",
    ])

    return "\n".join(context_parts)

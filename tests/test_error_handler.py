"""Tests for error classification and handling."""

import unittest
from core.error_handler import ErrorClassifier, ErrorType, format_error_context


class TestErrorClassifier(unittest.TestCase):
    """Test cases for ErrorClassifier."""

    def test_classify_key_error(self):
        """Test KeyError classification."""
        error_msg = "KeyError: 'Sales'"
        error_info = ErrorClassifier.classify(error_msg)

        self.assertEqual(error_info.error_type, ErrorType.KEY_ERROR)
        self.assertEqual(error_info.details.get("missing_key"), "Sales")

    def test_classify_name_error(self):
        """Test NameError classification."""
        error_msg = "NameError: name 'undefined_var' is not defined"
        error_info = ErrorClassifier.classify(error_msg)

        self.assertEqual(error_info.error_type, ErrorType.NAME_ERROR)
        self.assertEqual(error_info.details.get("undefined_name"), "undefined_var")

    def test_classify_type_error(self):
        """Test TypeError classification."""
        error_msg = "TypeError: cannot concatenate 'str' and 'int' objects"
        error_info = ErrorClassifier.classify(error_msg)

        self.assertEqual(error_info.error_type, ErrorType.TYPE_ERROR)

    def test_classify_value_error(self):
        """Test ValueError classification."""
        error_msg = "ValueError: could not convert string to float: '$1,234'"
        error_info = ErrorClassifier.classify(error_msg)

        self.assertEqual(error_info.error_type, ErrorType.VALUE_ERROR)

    def test_classify_syntax_error(self):
        """Test SyntaxError classification."""
        error_msg = "SyntaxError: invalid syntax"
        error_info = ErrorClassifier.classify(error_msg)

        self.assertEqual(error_info.error_type, ErrorType.SYNTAX_ERROR)

    def test_classify_import_error(self):
        """Test ImportError classification."""
        error_msg = "ModuleNotFoundError: No module named 'nonexistent'"
        error_info = ErrorClassifier.classify(error_msg)

        self.assertEqual(error_info.error_type, ErrorType.IMPORT_ERROR)

    def test_classify_attribute_error(self):
        """Test AttributeError classification."""
        error_msg = "AttributeError: 'DataFrame' object has no attribute 'nonexistent_method'"
        error_info = ErrorClassifier.classify(error_msg)

        self.assertEqual(error_info.error_type, ErrorType.ATTRIBUTE_ERROR)
        self.assertEqual(error_info.details.get("missing_attribute"), "nonexistent_method")

    def test_classify_unknown_error(self):
        """Test unknown error classification falls back to RUNTIME_ERROR."""
        error_msg = "Some unknown error occurred"
        error_info = ErrorClassifier.classify(error_msg)

        self.assertEqual(error_info.error_type, ErrorType.RUNTIME_ERROR)

    def test_get_hint_key_error(self):
        """Test hint generation for KeyError."""
        error_msg = "KeyError: 'InvalidColumn'"
        error_info = ErrorClassifier.classify(error_msg)
        hint = ErrorClassifier.get_hint(error_info)

        self.assertIn("列名", hint)
        self.assertIn("InvalidColumn", hint)

    def test_get_hint_name_error(self):
        """Test hint generation for NameError."""
        error_msg = "NameError: name 'myvar' is not defined"
        error_info = ErrorClassifier.classify(error_msg)
        hint = ErrorClassifier.get_hint(error_info)

        self.assertIn("变量", hint)
        self.assertIn("myvar", hint)


class TestFormatErrorContext(unittest.TestCase):
    """Test cases for format_error_context function."""

    def test_format_error_context_basic(self):
        """Test basic error context formatting."""
        context = format_error_context(
            error_msg="KeyError: 'Sales'",
            code="df['Sales'].sum()",
            columns=["Product", "Revenue", "Quantity"],
            dtypes="Product    object\nRevenue    float64\nQuantity   int64",
            conversation_history=""
        )

        # Check all sections are present
        self.assertIn("代码执行出错", context)
        self.assertIn("KeyError", context)
        self.assertIn("错误类型: KEY", context)
        self.assertIn("df['Sales'].sum()", context)
        self.assertIn("Product, Revenue, Quantity", context)
        self.assertIn("修复要求", context)

    def test_format_error_context_with_history(self):
        """Test error context with conversation history."""
        context = format_error_context(
            error_msg="TypeError: invalid operation",
            code="df['col'].mean()",
            columns=["col"],
            dtypes="col    object",
            conversation_history="问题: 计算平均值\n代码: df['col'].mean()"
        )

        self.assertIn("最近对话历史", context)
        self.assertIn("计算平均值", context)


if __name__ == "__main__":
    unittest.main()

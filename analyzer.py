"""Core CSV analyzer that orchestrates LLM and code execution."""

import re
from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from config import Config
from core.executor import CodeExecutor, ExecutionResult
from core.prompts import PromptBuilder
from llm import QwenLLM, OpenAILLM, DeepSeekLLM, BaseLLM


@dataclass
class AnalysisResult:
    """Result of a complete analysis."""
    code: str
    output: str
    figure_path: str | None
    explanation: str
    error: str | None = None


class CSVAnalyzer:
    """Main analyzer class that coordinates LLM and code execution."""

    def __init__(self, csv_path: str, model: str = "qwen"):
        self.csv_path = csv_path
        self.model_name = model
        self.llm = self._create_llm(model)
        self.executor = CodeExecutor(csv_path)
        self.history: list[dict] = []
        self._df: pd.DataFrame | None = None

    def _create_llm(self, model: str) -> BaseLLM:
        """Create LLM instance based on model name."""
        llm_classes = {
            "qwen": QwenLLM,
            "openai": OpenAILLM,
            "deepseek": DeepSeekLLM,
        }
        llm_class = llm_classes.get(model)
        if llm_class is None:
            raise ValueError(f"Unknown model: {model}. Choose from: {list(llm_classes.keys())}")
        return llm_class()

    def switch_model(self, model: str):
        """Switch to a different LLM model."""
        self.model_name = model
        self.llm = self._create_llm(model)

    def _load_df(self) -> pd.DataFrame:
        """Load and cache the DataFrame."""
        if self._df is None:
            self._df = pd.read_csv(self.csv_path, encoding='utf-8')
        return self._df

    def get_preview(self, rows: int = 5) -> pd.DataFrame:
        """Get a preview of the CSV data."""
        return self._load_df().head(rows)

    def _get_csv_info(self) -> tuple[list[str], str, str]:
        """Get CSV column info, dtypes, and sample data."""
        df = self._load_df()
        columns = df.columns.tolist()
        dtypes = df.dtypes.to_string()
        sample_data = df.head(3).to_string()
        return columns, dtypes, sample_data

    def _build_messages(self, question: str) -> list[dict]:
        """Build messages list for LLM including history."""
        columns, dtypes, sample_data = self._get_csv_info()

        system_prompt = PromptBuilder.build_system_prompt(
            csv_path=self.csv_path,
            columns=columns,
            dtypes=dtypes,
            sample_data=sample_data,
        )

        messages = [{"role": "system", "content": system_prompt}]

        # Add conversation history
        for item in self.history:
            messages.append({"role": "user", "content": item["question"]})
            messages.append({
                "role": "assistant",
                "content": f"```python\n{item['code']}\n```"
            })
            if item.get("result"):
                messages.append({
                    "role": "user",
                    "content": f"执行结果:\n{item['result']}"
                })

        # Add current question
        messages.append({"role": "user", "content": question})

        return messages

    def _extract_code(self, response: str) -> str:
        """Extract code from LLM response."""
        # Try to find code in ```python ... ``` blocks
        pattern = r"```python\s*(.*?)\s*```"
        matches = re.findall(pattern, response, re.DOTALL)
        if matches:
            return matches[0].strip()

        # Try to find code in ``` ... ``` blocks
        pattern = r"```\s*(.*?)\s*```"
        matches = re.findall(pattern, response, re.DOTALL)
        if matches:
            return matches[0].strip()

        return response.strip()

    def _generate_and_execute(
        self,
        messages: list[dict],
        max_retries: int = 3
    ) -> tuple[str, ExecutionResult]:
        """Generate code and execute with retry on failure."""
        current_messages = messages.copy()

        for attempt in range(max_retries):
            # Generate code
            response = self.llm.chat(current_messages)
            code = self._extract_code(response)

            # Execute code
            result = self.executor.execute(code)

            if result.success:
                return code, result

            # Prepare error correction message
            error_prompt = PromptBuilder.build_error_correction_prompt(result.error)
            current_messages.append({"role": "assistant", "content": response})
            current_messages.append({"role": "user", "content": error_prompt})

        # Return last result even if failed
        return code, result

    def _generate_explanation(self, question: str, result: ExecutionResult) -> str:
        """Generate explanation for the execution result."""
        if not result.success:
            return f"代码执行失败: {result.error}"

        if not result.output.strip():
            return "代码执行成功，但没有输出结果。"

        prompt = PromptBuilder.build_explanation_prompt(
            question=question,
            result=result.output[:2000],  # Limit result length
        )

        messages = [{"role": "user", "content": prompt}]
        return self.llm.chat(messages)

    def analyze(self, question: str) -> AnalysisResult:
        """
        Perform complete analysis for a question.

        1. Build prompt with system info, history, and question
        2. Generate code using LLM
        3. Execute code (retry on failure)
        4. Generate explanation
        5. Save to history

        Args:
            question: User's data analysis question.

        Returns:
            AnalysisResult with code, output, figure, and explanation.
        """
        # Build messages
        messages = self._build_messages(question)

        # Generate and execute code
        code, exec_result = self._generate_and_execute(
            messages,
            max_retries=Config.MAX_RETRIES
        )

        # Generate explanation
        explanation = self._generate_explanation(question, exec_result)

        # Save to history
        self.history.append({
            "question": question,
            "code": code,
            "result": exec_result.output if exec_result.success else exec_result.error,
            "explanation": explanation,
        })

        return AnalysisResult(
            code=code,
            output=exec_result.output,
            figure_path=exec_result.figure_path,
            explanation=explanation,
            error=exec_result.error if not exec_result.success else None,
        )

    def new_conversation(self):
        """Start a new conversation (clear history)."""
        self.history = []
        self.executor.reset()

    def get_history(self) -> list[dict]:
        """Get conversation history."""
        return self.history.copy()

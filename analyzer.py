"""Core CSV analyzer that orchestrates LLM and code execution."""

import re
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Generator

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
        max_retries: int = 3,
        yield_callback=None
    ) -> tuple[str, ExecutionResult]:
        """Generate code and execute with retry on failure."""
        current_messages = messages.copy()
        last_error = None

        for attempt in range(max_retries):
            try:
                if yield_callback:
                    yield_callback(f"🔄 正在生成代码 (尝试 {attempt + 1}/{max_retries})...")
                
                # Generate code with retry on connection errors
                response = None
                llm_retry_count = 3
                for llm_attempt in range(llm_retry_count):
                    try:
                        response = self.llm.chat(current_messages)
                        break
                    except Exception as e:
                        if yield_callback:
                            yield_callback(f"⚠️ LLM调用失败 (尝试 {llm_attempt + 1}/{llm_retry_count}): {str(e)}")
                        if llm_attempt < llm_retry_count - 1:
                            time.sleep(2 ** llm_attempt)  # Exponential backoff
                        else:
                            raise
                
                if response is None:
                    raise Exception("LLM调用失败，无法获取响应")
                
                code = self._extract_code(response)
                
                if yield_callback:
                    yield_callback(f"✅ 代码生成成功\n```python\n{code}\n```")
                    yield_callback("🔧 正在执行代码...")

                # Execute code
                result = self.executor.execute(code)

                if result.success:
                    if yield_callback:
                        yield_callback(f"✅ 代码执行成功\n执行结果:\n{result.output}")
                    return code, result

                # Code execution failed
                last_error = result.error
                if yield_callback:
                    yield_callback(f"❌ 代码执行失败 (尝试 {attempt + 1}/{max_retries})\n错误信息:\n{result.error}")
                    yield_callback("🔧 正在请求大模型修正代码...")

                # Prepare error correction message with full context
                error_prompt = PromptBuilder.build_error_correction_prompt(
                    result.error,
                    code=code,
                    conversation_history=self._get_recent_history()
                )
                current_messages.append({"role": "assistant", "content": response})
                current_messages.append({"role": "user", "content": error_prompt})

            except Exception as e:
                # LLM call failed
                last_error = f"LLM调用错误: {str(e)}"
                if yield_callback:
                    yield_callback(f"❌ {last_error}")
                    if attempt < max_retries - 1:
                        yield_callback(f"🔄 正在重试 (尝试 {attempt + 2}/{max_retries})...")
                
                # If it's a connection error and we have retries left, wait and retry
                if attempt < max_retries - 1:
                    time.sleep(2 ** attempt)  # Exponential backoff
                    continue
                else:
                    # Last attempt failed, return error result
                    return "", ExecutionResult(
                        success=False,
                        output="",
                        error=last_error,
                        figure_path=None
                    )

        # All retries exhausted
        if yield_callback:
            yield_callback(f"❌ 所有重试均失败，最终错误: {last_error}")
        return code if 'code' in locals() else "", result if 'result' in locals() else ExecutionResult(
            success=False,
            output="",
            error=last_error or "未知错误",
            figure_path=None
        )

    def _generate_explanation(self, question: str, result: ExecutionResult, yield_callback=None) -> str:
        """Generate explanation for the execution result."""
        if not result.success:
            return f"代码执行失败: {result.error}"

        if not result.output.strip():
            return "代码执行成功，但没有输出结果。"

        if yield_callback:
            yield_callback("📝 正在生成分析解释...")

        prompt = PromptBuilder.build_explanation_prompt(
            question=question,
            result=result.output[:2000],  # Limit result length
        )

        messages = [{"role": "user", "content": prompt}]
        
        try:
            explanation = self.llm.chat(messages)
            if yield_callback:
                yield_callback(f"✅ 分析完成\n**分析:**\n{explanation}")
            return explanation
        except Exception as e:
            error_msg = f"生成解释时出错: {str(e)}"
            if yield_callback:
                yield_callback(f"⚠️ {error_msg}")
            return error_msg
    
    def _get_recent_history(self, max_items: int = 3) -> str:
        """Get recent conversation history as string for error correction."""
        if not self.history:
            return "无历史对话"
        
        recent = self.history[-max_items:]
        history_text = []
        for item in recent:
            history_text.append(f"问题: {item['question']}")
            history_text.append(f"代码: {item['code']}")
            if item.get('result'):
                history_text.append(f"结果: {item['result']}")
        return "\n".join(history_text)

    def analyze(self, question: str, yield_callback=None) -> AnalysisResult:
        """
        Perform complete analysis for a question.

        1. Build prompt with system info, history, and question
        2. Generate code using LLM
        3. Execute code (retry on failure)
        4. Generate explanation
        5. Save to history

        Args:
            question: User's data analysis question.
            yield_callback: Optional callback function to yield progress updates.

        Returns:
            AnalysisResult with code, output, figure, and explanation.
        """
        if yield_callback:
            yield_callback(f"📋 收到问题: {question}")
            yield_callback("🔍 正在构建提示词...")
        
        # Build messages
        messages = self._build_messages(question)

        # Generate and execute code
        code, exec_result = self._generate_and_execute(
            messages,
            max_retries=Config.MAX_RETRIES,
            yield_callback=yield_callback
        )

        # Generate explanation
        explanation = self._generate_explanation(question, exec_result, yield_callback)

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
    
    def analyze_stream(self, question: str) -> Generator[str, None, None]:
        """
        Perform analysis with streaming updates.
        
        Yields progress messages. Use analyze() to get the final result.
        """
        yield f"📋 收到问题: {question}\n"
        yield "🔍 正在构建提示词...\n"
        
        messages = self._build_messages(question)
        
        # Generate and execute with streaming
        code = ""
        exec_result = None
        last_error = None
        
        for attempt in range(Config.MAX_RETRIES):
            try:
                yield f"🔄 正在生成代码 (尝试 {attempt + 1}/{Config.MAX_RETRIES})...\n"
                
                # Generate code with retry on connection errors
                response = None
                llm_retry_count = 3
                for llm_attempt in range(llm_retry_count):
                    try:
                        response = self.llm.chat(messages)
                        break
                    except Exception as e:
                        yield f"⚠️ LLM调用失败 (尝试 {llm_attempt + 1}/{llm_retry_count}): {str(e)}\n"
                        if llm_attempt < llm_retry_count - 1:
                            time.sleep(2 ** llm_attempt)
                        else:
                            raise
                
                if response is None:
                    raise Exception("LLM调用失败，无法获取响应")
                
                code = self._extract_code(response)
                yield f"✅ 代码生成成功\n```python\n{code}\n```\n"
                yield "🔧 正在执行代码...\n"
                
                exec_result = self.executor.execute(code)
                
                if exec_result.success:
                    yield f"✅ 代码执行成功\n执行结果:\n{exec_result.output}\n"
                    break
                
                last_error = exec_result.error
                yield f"❌ 代码执行失败 (尝试 {attempt + 1}/{Config.MAX_RETRIES})\n错误信息:\n{exec_result.error}\n"
                yield "🔧 正在请求大模型修正代码...\n"
                
                error_prompt = PromptBuilder.build_error_correction_prompt(
                    exec_result.error,
                    code=code,
                    conversation_history=self._get_recent_history()
                )
                messages.append({"role": "assistant", "content": response})
                messages.append({"role": "user", "content": error_prompt})
                
            except Exception as e:
                last_error = f"LLM调用错误: {str(e)}"
                yield f"❌ {last_error}\n"
                if attempt < Config.MAX_RETRIES - 1:
                    yield f"🔄 正在重试 (尝试 {attempt + 2}/{Config.MAX_RETRIES})...\n"
                    time.sleep(2 ** attempt)
                else:
                    exec_result = ExecutionResult(
                        success=False,
                        output="",
                        error=last_error,
                        figure_path=None
                    )
        
        # Ensure exec_result is set even if all attempts failed
        if exec_result is None:
            exec_result = ExecutionResult(
                success=False,
                output="",
                error=last_error or "未知错误：所有尝试均失败",
                figure_path=None
            )
            yield f"❌ 所有重试均失败，最终错误: {exec_result.error}\n"
        elif not exec_result.success:
            yield f"❌ 所有重试均失败，最终错误: {last_error or exec_result.error}\n"
        
        if exec_result:
            yield "📝 正在生成分析解释...\n"
            try:
                explanation = self._generate_explanation(question, exec_result)
                yield f"✅ 分析完成\n**分析:**\n{explanation}\n"
                
                # Save to history with figure_path
                self.history.append({
                    "question": question,
                    "code": code,
                    "result": exec_result.output if exec_result.success else exec_result.error,
                    "explanation": explanation,
                    "figure_path": exec_result.figure_path,
                })
            except Exception as e:
                yield f"⚠️ 生成解释时出错: {str(e)}\n"
                # Still save to history even if explanation failed
                self.history.append({
                    "question": question,
                    "code": code,
                    "result": exec_result.output if exec_result.success else exec_result.error,
                    "explanation": f"生成解释时出错: {str(e)}",
                    "figure_path": exec_result.figure_path,
                })

    def new_conversation(self):
        """Start a new conversation (clear history)."""
        self.history = []
        self.executor.reset()

    def get_history(self) -> list[dict]:
        """Get conversation history."""
        return self.history.copy()

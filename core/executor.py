"""Code executor for running generated Python code."""

import io
import re
import sys
import uuid
from contextlib import redirect_stdout, redirect_stderr
from dataclasses import dataclass
from pathlib import Path

import matplotlib
matplotlib.use('Agg')  # Use non-interactive backend
import matplotlib.pyplot as plt
import pandas as pd

from config import Config


@dataclass
class ExecutionResult:
    """Result of code execution."""
    success: bool
    output: str
    error: str
    figure_path: str | None


class CodeExecutor:
    """Executes Python code in a controlled environment."""

    # Simulated errors for testing
    _TEST_ERRORS = [
        "KeyError: 'NonexistentColumn'",
        "TypeError: cannot convert the series to <class 'float'>",
        "ValueError: could not convert string to float: '$1,234'",
    ]

    def __init__(self, csv_path: str):
        self.csv_path = csv_path
        self.globals: dict = {}
        self._init_globals()
        # Test mode settings
        self._test_mode = False
        self._fail_count = 0
        self._max_fails = 0

    def set_test_mode(self, enabled: bool, fail_count: int = 1):
        """
        Enable or disable test mode with error injection.

        Args:
            enabled: Whether to enable test mode.
            fail_count: Number of times to inject errors before allowing success.
        """
        self._test_mode = enabled
        self._max_fails = fail_count if enabled else 0
        self._fail_count = 0

    def _init_globals(self):
        """Initialize the global namespace with common imports."""
        self.globals = {
            "pd": pd,
            "plt": plt,
            "csv_path": self.csv_path,
            "__builtins__": __builtins__,
        }

    def _extract_code(self, text: str) -> str:
        """Extract Python code from markdown code blocks."""
        # Try to find code in ```python ... ``` blocks
        pattern = r"```python\s*(.*?)\s*```"
        matches = re.findall(pattern, text, re.DOTALL)
        if matches:
            return matches[0].strip()

        # Try to find code in ``` ... ``` blocks
        pattern = r"```\s*(.*?)\s*```"
        matches = re.findall(pattern, text, re.DOTALL)
        if matches:
            return matches[0].strip()

        # Return original text if no code blocks found
        return text.strip()

    def _inject_figure_save(self, code: str, figure_path: Path) -> str:
        """Inject figure saving code and remove plt.show() calls."""
        save_code = f"plt.savefig(r'{figure_path}', dpi=100, bbox_inches='tight')"

        if "plt.show()" in code:
            # Replace plt.show() with save only (remove show to avoid warning)
            code = code.replace("plt.show()", save_code)
        elif "plt.figure(" in code or "plt.plot(" in code or "plt.bar(" in code:
            # If there's plotting but no show(), add save at the end
            code = f"{code}\n{save_code}"

        return code

    def execute(self, code: str) -> ExecutionResult:
        """
        Execute code and capture output and figures.

        Args:
            code: Python code to execute (may be wrapped in markdown code blocks).

        Returns:
            ExecutionResult with success status, output, error, and figure path.
        """
        # Test mode: inject errors
        if self._test_mode and self._fail_count < self._max_fails:
            self._fail_count += 1
            error_msg = self._TEST_ERRORS[(self._fail_count - 1) % len(self._TEST_ERRORS)]
            return ExecutionResult(
                success=False,
                output="",
                error=f"[测试模式] {error_msg}",
                figure_path=None
            )

        # Extract code from markdown if needed
        code = self._extract_code(code)

        # Prepare figure path
        Config.ensure_output_dir()
        figure_path = Config.OUTPUT_DIR / f"figure_{uuid.uuid4().hex[:8]}.png"

        # Inject figure saving
        code = self._inject_figure_save(code, figure_path)

        # Capture stdout and stderr
        stdout_capture = io.StringIO()
        stderr_capture = io.StringIO()

        # Close any existing figures
        plt.close('all')

        try:
            with redirect_stdout(stdout_capture), redirect_stderr(stderr_capture):
                exec(code, self.globals)

            output = stdout_capture.getvalue()
            stderr_output = stderr_capture.getvalue()

            # Check if figure was generated
            actual_figure_path = str(figure_path) if figure_path.exists() else None

            return ExecutionResult(
                success=True,
                output=output + stderr_output,
                error="",
                figure_path=actual_figure_path,
            )

        except Exception as e:
            return ExecutionResult(
                success=False,
                output=stdout_capture.getvalue(),
                error=f"{type(e).__name__}: {str(e)}",
                figure_path=None,
            )
        finally:
            plt.close('all')

    def reset(self):
        """Reset the execution environment."""
        self._init_globals()

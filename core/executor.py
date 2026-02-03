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

    def __init__(self, csv_path: str):
        self.csv_path = csv_path
        self.globals: dict = {}
        self._init_globals()

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
        """Inject figure saving code before plt.show() calls."""
        # Replace plt.show() with save and show
        save_code = f"plt.savefig(r'{figure_path}', dpi=100, bbox_inches='tight')"

        if "plt.show()" in code:
            code = code.replace("plt.show()", f"{save_code}\nplt.show()")
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

"""
Test script for error correction flow.

This script allows testing the error correction mechanism by:
1. Injecting errors into code execution
2. Observing how the system handles and corrects errors

Usage:
    python tests/test_error_correction_flow.py [--fail-count N]

Options:
    --fail-count N    Number of times to force execution failure (default: 1)
"""

import argparse
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.executor import CodeExecutor, ExecutionResult
from analyzer import CSVAnalyzer


class ErrorInjectingExecutor(CodeExecutor):
    """Executor that injects errors for testing."""

    def __init__(self, csv_path: str, fail_count: int = 1):
        super().__init__(csv_path)
        self._fail_count = fail_count
        self._current_fails = 0

    def execute(self, code: str) -> ExecutionResult:
        """Execute code with optional error injection."""
        if self._current_fails < self._fail_count:
            self._current_fails += 1
            # Simulate different error types
            error_types = [
                "KeyError: 'NonexistentColumn'",
                "TypeError: cannot convert the series to <class 'float'>",
                "ValueError: could not convert string to float: '$1,234'",
            ]
            error_msg = error_types[(self._current_fails - 1) % len(error_types)]

            print(f"\n[TEST] Injecting error #{self._current_fails}: {error_msg}")
            return ExecutionResult(
                success=False,
                output="",
                error=error_msg,
                figure_path=None
            )

        # Normal execution
        print(f"\n[TEST] Normal execution (after {self._current_fails} injected failures)")
        return super().execute(code)


def test_error_correction(csv_path: str, fail_count: int = 1):
    """Test the error correction flow with injected errors."""
    print("=" * 60)
    print("Error Correction Flow Test")
    print("=" * 60)
    print(f"CSV file: {csv_path}")
    print(f"Injected failures: {fail_count}")
    print("=" * 60)

    # Create analyzer
    analyzer = CSVAnalyzer(csv_path, model="qwen")

    # Replace executor with error-injecting version
    analyzer.executor = ErrorInjectingExecutor(csv_path, fail_count=fail_count)

    # Test question
    question = "Show the first 5 rows of data"

    print(f"\nQuestion: {question}")
    print("-" * 40)

    # Run analysis with streaming to see the correction process
    for update in analyzer.analyze_stream(question):
        print(update, end="")

    print("\n" + "=" * 60)
    print("Test completed!")
    print("=" * 60)


def main():
    parser = argparse.ArgumentParser(description="Test error correction flow")
    parser.add_argument(
        "--fail-count",
        type=int,
        default=1,
        help="Number of times to force execution failure (default: 1)"
    )
    parser.add_argument(
        "--csv",
        type=str,
        default="data/sample.csv",
        help="Path to CSV file for testing"
    )
    args = parser.parse_args()

    # Check if CSV exists, create sample if not
    csv_path = Path(args.csv)
    if not csv_path.exists():
        print(f"CSV file not found: {csv_path}")
        print("Creating sample CSV for testing...")

        csv_path.parent.mkdir(parents=True, exist_ok=True)
        sample_data = """Product,Sales,Quantity,Region
Apple,1000,50,North
Banana,800,40,South
Orange,1200,60,East
Grape,600,30,West
Mango,900,45,North"""
        csv_path.write_text(sample_data)
        print(f"Created: {csv_path}")

    test_error_correction(str(csv_path), args.fail_count)


if __name__ == "__main__":
    main()

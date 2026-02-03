"""Gradio Web application for CSV Data Analyzer."""

import gradio as gr
import pandas as pd
from pathlib import Path

from analyzer import CSVAnalyzer, AnalysisResult


# Global analyzer instance
analyzer: CSVAnalyzer | None = None


def load_csv(file) -> tuple[pd.DataFrame | None, str]:
    """Load CSV file and return preview."""
    global analyzer

    if file is None:
        return None, "请上传 CSV 文件"

    try:
        # Get file path
        file_path = file.name if hasattr(file, 'name') else str(file)

        # Create analyzer with default model
        analyzer = CSVAnalyzer(file_path, model="qwen")

        # Get preview
        preview = analyzer.get_preview(rows=5)

        return preview, f"已加载文件: {Path(file_path).name}"

    except Exception as e:
        return None, f"加载文件失败: {str(e)}"


def switch_model(model: str) -> str:
    """Switch the LLM model."""
    global analyzer

    if analyzer is None:
        return "请先上传 CSV 文件"

    try:
        analyzer.switch_model(model)
        return f"已切换到模型: {model}"
    except Exception as e:
        return f"切换模型失败: {str(e)}"


def format_response(result: AnalysisResult) -> str:
    """Format analysis result for display."""
    parts = []

    # Code section
    parts.append("**生成的代码:**")
    parts.append(f"```python\n{result.code}\n```")

    # Execution result
    if result.error:
        parts.append(f"\n**执行错误:**\n```\n{result.error}\n```")
    elif result.output:
        parts.append(f"\n**执行结果:**\n```\n{result.output}\n```")

    # Explanation
    if result.explanation:
        parts.append(f"\n**分析:**\n{result.explanation}")

    return "\n".join(parts)


def analyze(
    question: str,
    history: list,
    model: str
) -> tuple[list, str | None, str]:
    """Process user question and return response."""
    global analyzer

    if not question.strip():
        return history, None, ""

    if analyzer is None:
        history = history + [
            {"role": "user", "content": question},
            {"role": "assistant", "content": "请先上传 CSV 文件"}
        ]
        return history, None, ""

    # Switch model if needed
    if model != analyzer.model_name:
        try:
            analyzer.switch_model(model)
        except Exception as e:
            history = history + [
                {"role": "user", "content": question},
                {"role": "assistant", "content": f"切换模型失败: {str(e)}"}
            ]
            return history, None, ""

    try:
        # Perform analysis
        result = analyzer.analyze(question)

        # Format response
        response = format_response(result)

        # Update history with new message format
        history = history + [
            {"role": "user", "content": question},
            {"role": "assistant", "content": response}
        ]

        # Return with figure if available
        return history, result.figure_path, ""

    except Exception as e:
        error_msg = f"分析失败: {str(e)}"
        history = history + [
            {"role": "user", "content": question},
            {"role": "assistant", "content": error_msg}
        ]
        return history, None, ""


def clear_history() -> tuple[list, None]:
    """Clear conversation history."""
    global analyzer

    if analyzer:
        analyzer.new_conversation()

    return [], None


def create_app():
    """Create and configure the Gradio app."""

    with gr.Blocks(title="CSV 数据分析系统") as app:

        gr.Markdown(
            """
            # CSV 数据分析系统 (Code Interpreter)
            上传 CSV 文件，用自然语言提问，AI 自动生成代码分析数据
            """
        )

        with gr.Row():
            with gr.Column(scale=2):
                file_input = gr.File(
                    label="上传 CSV 文件",
                    file_types=[".csv"],
                    file_count="single"
                )
            with gr.Column(scale=1):
                model_dropdown = gr.Dropdown(
                    choices=["qwen", "openai", "deepseek"],
                    value="qwen",
                    label="选择模型"
                )
            with gr.Column(scale=1):
                status_text = gr.Textbox(
                    label="状态",
                    interactive=False,
                    value="请上传 CSV 文件"
                )

        csv_preview = gr.Dataframe(
            label="CSV 预览 (前5行)",
            interactive=False,
            wrap=True
        )

        gr.Markdown("---")

        with gr.Row():
            gr.Markdown("### 对话区域")
            clear_btn = gr.Button("清空对话", variant="secondary", size="sm")

        chatbot = gr.Chatbot(
            label="对话",
            height=400,
            elem_classes=["chatbot"]
        )

        image_output = gr.Image(
            label="生成的图表",
            type="filepath",
            visible=True
        )

        with gr.Row():
            question_input = gr.Textbox(
                placeholder="请输入数据分析问题，例如：分析 Clothing 随时间变化的总销售额趋势",
                label="问题",
                scale=4,
                lines=1
            )
            submit_btn = gr.Button("发送", variant="primary", scale=1)

        gr.Markdown(
            """
            ---
            **示例问题:**
            - 分析 Clothing 随时间变化的总销售额趋势
            - 对 Bikes 进行同样的分析
            - 哪些年份 Components 比 Accessories 的总销售额高?
            """
        )

        # Event handlers
        file_input.change(
            fn=load_csv,
            inputs=[file_input],
            outputs=[csv_preview, status_text]
        )

        model_dropdown.change(
            fn=switch_model,
            inputs=[model_dropdown],
            outputs=[status_text]
        )

        submit_btn.click(
            fn=analyze,
            inputs=[question_input, chatbot, model_dropdown],
            outputs=[chatbot, image_output, question_input]
        )

        question_input.submit(
            fn=analyze,
            inputs=[question_input, chatbot, model_dropdown],
            outputs=[chatbot, image_output, question_input]
        )

        clear_btn.click(
            fn=clear_history,
            inputs=[],
            outputs=[chatbot, image_output]
        )

    return app


if __name__ == "__main__":
    app = create_app()
    app.launch(
        server_name="0.0.0.0",
        server_port=7860,
        share=False
    )

"""Gradio Web application for CSV Data Analyzer."""

import json
from datetime import datetime
from pathlib import Path

import gradio as gr
import pandas as pd

from analyzer import CSVAnalyzer, AnalysisResult

# Global analyzer instance
analyzer: CSVAnalyzer | None = None

# History save directory
HISTORY_DIR = Path("history")
HISTORY_DIR.mkdir(exist_ok=True)


def load_csv(file) -> tuple[pd.DataFrame | None, str]:
    """Load CSV file and return preview."""
    global analyzer

    if file is None:
        return None, "请上传 CSV 文件"

    try:
        file_path = file.name if hasattr(file, 'name') else str(file)
        analyzer = CSVAnalyzer(file_path, model="qwen")
        preview = analyzer.get_preview(rows=3)
        return preview, f"已加载: {Path(file_path).name}"

    except Exception as e:
        return None, f"加载失败: {str(e)}"


def switch_model(model: str) -> str:
    """Switch the LLM model."""
    global analyzer

    if analyzer is None:
        return "请先上传 CSV 文件"

    try:
        analyzer.switch_model(model)
        return f"模型: {model}"
    except Exception as e:
        return f"切换失败: {str(e)}"


def format_response(result: AnalysisResult) -> str:
    """Format analysis result for display."""
    parts = []

    parts.append("**生成的代码:**")
    parts.append(f"```python\n{result.code}\n```")

    if result.error:
        parts.append(f"\n**执行错误:**\n```\n{result.error}\n```")
    elif result.output:
        parts.append(f"\n**执行结果:**\n```\n{result.output}\n```")

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
        result = analyzer.analyze(question)
        response = format_response(result)

        history = history + [
            {"role": "user", "content": question},
            {"role": "assistant", "content": response}
        ]

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


def save_history(history: list, save_name: str) -> str:
    """Save conversation history to a JSON file."""
    if not history:
        return "没有对话可保存"

    if not save_name.strip():
        save_name = datetime.now().strftime("%Y%m%d_%H%M%S")

    save_name = save_name.strip().replace(" ", "_")
    if not save_name.endswith(".json"):
        save_name += ".json"

    file_path = HISTORY_DIR / save_name

    try:
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump({
                "timestamp": datetime.now().isoformat(),
                "history": history
            }, f, ensure_ascii=False, indent=2)
        return f"已保存: {save_name}"
    except Exception as e:
        return f"保存失败: {str(e)}"


def get_history_files() -> list:
    """Get list of saved history files."""
    files = list(HISTORY_DIR.glob("*.json"))
    files.sort(key=lambda x: x.stat().st_mtime, reverse=True)
    return [f.name for f in files]


def load_history(filename: str) -> tuple[list, str]:
    """Load conversation history from a JSON file."""
    global analyzer

    if not filename:
        return [], "请选择历史记录"

    file_path = HISTORY_DIR / filename

    try:
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        history = data.get("history", [])

        if analyzer:
            analyzer.new_conversation()

        return history, f"已加载: {filename}"
    except Exception as e:
        return [], f"加载失败: {str(e)}"


def refresh_history_list() -> gr.update:
    """Refresh the history file dropdown."""
    return gr.update(choices=get_history_files())


def create_app():
    """Create and configure the Gradio app."""

    with gr.Blocks(title="CSV 数据分析系统") as app:

        gr.Markdown("# CSV 数据分析系统 (Code Interpreter)")

        # Top row: File upload and settings (compact)
        with gr.Row():
            file_input = gr.File(
                label="上传 CSV",
                file_types=[".csv"],
                file_count="single",
                scale=2
            )
            model_dropdown = gr.Dropdown(
                choices=["qwen", "openai", "deepseek"],
                value="qwen",
                label="模型",
                scale=1
            )
            status_text = gr.Textbox(
                label="状态",
                interactive=False,
                value="请上传 CSV",
                scale=1
            )

        # CSV preview (collapsible and compact)
        with gr.Accordion("CSV 预览", open=False):
            csv_preview = gr.Dataframe(
                label="",
                interactive=False,
                wrap=True,
                max_height=150
            )

        # Main chat area (takes most space)
        gr.Markdown("### 对话")

        chatbot = gr.Chatbot(
            label="",
            height=500,
            elem_classes=["chatbot"]
        )

        # Image output (collapsible)
        with gr.Accordion("生成的图表", open=False):
            image_output = gr.Image(
                label="",
                type="filepath",
                height=300
            )

        # Input row
        with gr.Row():
            question_input = gr.Textbox(
                placeholder="输入数据分析问题...",
                label="",
                scale=5,
                lines=1
            )
            submit_btn = gr.Button("发送", variant="primary", scale=1)

        # History management (collapsible)
        with gr.Accordion("对话管理", open=False):
            with gr.Row():
                clear_btn = gr.Button("清空当前对话", variant="secondary")

            gr.Markdown("**保存对话**")
            with gr.Row():
                save_name_input = gr.Textbox(
                    placeholder="输入保存名称（可选）",
                    label="",
                    scale=3
                )
                save_btn = gr.Button("保存", scale=1)
            save_status = gr.Textbox(label="", interactive=False, max_lines=1)

            gr.Markdown("**加载历史对话**")
            with gr.Row():
                history_dropdown = gr.Dropdown(
                    choices=get_history_files(),
                    label="",
                    scale=3
                )
                refresh_btn = gr.Button("刷新", scale=1)
                load_btn = gr.Button("加载", scale=1)
            load_status = gr.Textbox(label="", interactive=False, max_lines=1)

        # Example questions
        gr.Markdown(
            """
            ---
            **示例:** 分析 Clothing 随时间变化的总销售额趋势 | 对 Bikes 进行同样的分析 | 哪些年份 Components 比 Accessories 的总销售额高?
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

        save_btn.click(
            fn=save_history,
            inputs=[chatbot, save_name_input],
            outputs=[save_status]
        )

        refresh_btn.click(
            fn=refresh_history_list,
            inputs=[],
            outputs=[history_dropdown]
        )

        load_btn.click(
            fn=load_history,
            inputs=[history_dropdown],
            outputs=[chatbot, load_status]
        )

    return app


if __name__ == "__main__":
    app = create_app()
    app.launch(
        server_name="0.0.0.0",
        server_port=7860,
        share=False
    )

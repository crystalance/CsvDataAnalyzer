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
        return None, "请上传 CSV"

    try:
        file_path = file.name if hasattr(file, 'name') else str(file)
        analyzer = CSVAnalyzer(file_path, model="qwen")
        preview = analyzer.get_preview(rows=3)
        return preview, f"已加载: {Path(file_path).name}"

    except Exception as e:
        return None, f"失败: {str(e)}"


def switch_model(model: str) -> str:
    """Switch the LLM model."""
    global analyzer

    if analyzer is None:
        return "请先上传 CSV"

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
):
    """Process user question and return response with streaming updates."""
    global analyzer

    if not question.strip():
        yield history, None, ""
        return

    if analyzer is None:
        history = history + [
            {"role": "user", "content": question},
            {"role": "assistant", "content": "请先上传 CSV 文件"}
        ]
        yield history, None, ""
        return

    if model != analyzer.model_name:
        try:
            analyzer.switch_model(model)
        except Exception as e:
            history = history + [
                {"role": "user", "content": question},
                {"role": "assistant", "content": f"切换模型失败: {str(e)}"}
            ]
            yield history, None, ""
            return

    # Add user question to history immediately
    current_history = history + [{"role": "user", "content": question}]
    assistant_response = ""
    
    try:
        # Use streaming analysis
        for update in analyzer.analyze_stream(question):
            assistant_response += update
            # Update history with streaming response
            current_history_with_response = current_history + [
                {"role": "assistant", "content": assistant_response}
            ]
            yield current_history_with_response, None, ""
        
        # After streaming is complete, get the final formatted result
        # The analyze_stream already saved to history, so we can get the result
        # by calling analyze() which will use cached results, or we format from history
        # Actually, let's just call analyze() to get the properly formatted result
        # But this might duplicate LLM calls. Let's check if we can avoid that.
        
        # Get the last history item to format final response
        if analyzer.history and analyzer.history[-1]["question"] == question:
            last_item = analyzer.history[-1]
            
            # Get figure_path from history if available, otherwise try to find latest
            figure_path = last_item.get("figure_path")
            if not figure_path:
                import glob
                figures = sorted(glob.glob("outputs/figure_*.png"), key=lambda x: Path(x).stat().st_mtime, reverse=True)
                figure_path = figures[0] if figures else None
            
            # Determine if there was an error
            result_text = last_item.get("result", "")
            has_error = result_text and ("错误" in result_text or "失败" in result_text or "Error" in result_text)
            
            final_result = AnalysisResult(
                code=last_item.get("code", ""),
                output=result_text if not has_error else "",
                figure_path=figure_path,
                explanation=last_item.get("explanation", ""),
                error=result_text if has_error else None
            )
            
            final_response = format_response(final_result)
            
            # Final update with formatted response
            final_history = current_history + [
                {"role": "assistant", "content": final_response}
            ]
            yield final_history, figure_path, ""
        else:
            # No history saved, just use the streaming response
            yield current_history, None, ""

    except Exception as e:
        error_msg = f"分析失败: {str(e)}"
        final_history = current_history + [
            {"role": "assistant", "content": error_msg}
        ]
        yield final_history, None, ""


def save_history(history: list) -> gr.update:
    """Auto-save conversation history with timestamp."""
    if not history:
        return gr.update(choices=get_history_files())

    save_name = datetime.now().strftime("%Y%m%d_%H%M%S") + ".json"
    file_path = HISTORY_DIR / save_name

    try:
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump({
                "timestamp": datetime.now().isoformat(),
                "history": history
            }, f, ensure_ascii=False, indent=2)
        return gr.update(choices=get_history_files(), value=save_name.replace(".json", ""))
    except Exception as e:
        return gr.update(choices=get_history_files())


def get_history_files() -> list:
    """Get list of saved history files."""
    files = list(HISTORY_DIR.glob("*.json"))
    files.sort(key=lambda x: x.stat().st_mtime, reverse=True)
    return [f.stem for f in files]


def load_history(filename: str) -> list:
    """Load conversation history from a JSON file."""
    global analyzer

    if not filename:
        return []

    file_path = HISTORY_DIR / f"{filename}.json"

    try:
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        history = data.get("history", [])

        if analyzer:
            analyzer.new_conversation()

        return history
    except Exception:
        return []


def delete_history(filename: str) -> gr.update:
    """Delete a history file."""
    if not filename:
        return gr.update()

    file_path = HISTORY_DIR / f"{filename}.json"

    try:
        file_path.unlink()
        return gr.update(choices=get_history_files(), value=None)
    except Exception:
        return gr.update()


def new_conversation() -> tuple[list, None, str, gr.update]:
    """Start a new conversation."""
    global analyzer

    if analyzer:
        analyzer.new_conversation()

    return [], None, "", gr.update(value=None)


def create_app():
    """Create and configure the Gradio app."""

    with gr.Blocks(title="CSV 数据分析系统", css="""
        .main-container { margin-top: 10px; align-items: stretch !important; }
        .left-sidebar {
            padding-right: 15px;
            display: flex !important;
            flex-direction: column !important;
        }
        .chatbot-container { border-radius: 8px; }
        .history-section {
            margin-top: auto !important;
            padding-top: 12px !important;
        }
        .history-section .markdown { margin-bottom: 2px !important; }
        .history-section .markdown p { margin: 0 !important; font-weight: bold; }
        .history-list {
            max-height: 150px !important;
            overflow-y: auto !important;
            border: 1px solid #374151 !important;
            border-radius: 8px !important;
            padding: 8px !important;
            background: #1f2937 !important;
        }
        .history-list label { margin-bottom: 4px !important; }
    """) as app:

        # ========== Page Header (Full Width) ==========
        gr.Markdown("# CSV 数据分析系统")
        gr.Markdown("上传 CSV 文件，用自然语言提问，AI 自动生成代码分析数据")

        # ========== Main Content ==========
        with gr.Row(elem_classes="main-container"):
            # ========== Left Sidebar ==========
            with gr.Column(scale=1, min_width=280, elem_classes="left-sidebar"):
                # New chat button
                new_chat_btn = gr.Button("+ 新建对话", variant="primary", size="lg")

                # File upload
                file_input = gr.File(
                    label="上传 CSV",
                    file_types=[".csv"],
                    file_count="single"
                )

                # Model and status in a group
                with gr.Group():
                    model_dropdown = gr.Dropdown(
                        choices=["qwen", "openai", "deepseek"],
                        value="qwen",
                        label="模型"
                    )
                    status_text = gr.Textbox(
                        label="状态",
                        interactive=False,
                        value="就绪",
                        max_lines=1
                    )

                # CSV preview
                with gr.Accordion("CSV 预览", open=False):
                    csv_preview = gr.Dataframe(
                        label="",
                        interactive=False,
                        wrap=True,
                        max_height=150
                    )

                # History section - compact layout
                with gr.Group(elem_classes="history-section"):
                    gr.Markdown("**历史对话**")
                    history_list = gr.Radio(
                        choices=get_history_files(),
                        label="",
                        interactive=True,
                        container=False,
                        elem_classes="history-list"
                    )
                    with gr.Row():
                        load_btn = gr.Button("加载", size="sm", scale=1)
                        delete_btn = gr.Button("删除", size="sm", variant="stop", scale=1)

            # ========== Right Main Area ==========
            with gr.Column(scale=4):
                # Chat area - full height
                chatbot = gr.Chatbot(
                    label="",
                    height=550,
                    elem_classes="chatbot-container"
                )

                # Image output
                with gr.Accordion("生成的图表", open=False):
                    image_output = gr.Image(
                        label="",
                        type="filepath",
                        height=250
                    )

                # Input area - aligned with left sidebar bottom
                with gr.Row():
                    question_input = gr.Textbox(
                        placeholder="输入数据分析问题，如：分析各品类的销售趋势",
                        label="",
                        scale=6,
                        lines=1,
                        container=False
                    )
                    submit_btn = gr.Button("发送", variant="primary", scale=1, min_width=80)
                    save_btn = gr.Button("保存对话", variant="primary", scale=1, min_width=80)

        # ========== Event Handlers ==========
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

        new_chat_btn.click(
            fn=new_conversation,
            inputs=[],
            outputs=[chatbot, image_output, question_input, history_list]
        )

        save_btn.click(
            fn=save_history,
            inputs=[chatbot],
            outputs=[history_list]
        )

        load_btn.click(
            fn=load_history,
            inputs=[history_list],
            outputs=[chatbot]
        )

        delete_btn.click(
            fn=delete_history,
            inputs=[history_list],
            outputs=[history_list]
        )

    return app


if __name__ == "__main__":
    app = create_app()
    app.launch(
        server_name="0.0.0.0",
        server_port=7860,
        share=False
    )

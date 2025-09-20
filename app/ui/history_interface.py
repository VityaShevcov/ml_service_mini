"""
Gradio interface for chat history and analytics
"""
import gradio as gr
import requests
import pandas as pd
from typing import List, Dict, Any, Tuple, Optional
from datetime import datetime, timedelta

from config import settings


class HistoryInterface:
    """Interface for viewing chat history and user analytics"""
    
    def __init__(self, api_base_url: str = None):
        self.api_base_url = api_base_url or f"http://{settings.host}:{settings.port}"
        self.current_token = None
        self.current_page = 1
        self.page_size = 20
    
    def set_auth(self, token: str):
        """Set authentication token"""
        self.current_token = token
    
    def get_chat_history(self, page: int = 1, page_size: int = 20, model_filter: str = "all", 
                        date_from: str = "", date_to: str = "") -> Tuple[List[List], str, int]:
        """Get chat history from API with filtering"""
        try:
            if not self.current_token:
                return [], "❌ Not authenticated", 0
            
            params = {
                "page": page,
                "page_size": page_size
            }
            
            # Add filters if provided
            if model_filter and model_filter != "all":
                params["model_name"] = model_filter
            if date_from:
                params["date_from"] = date_from
            if date_to:
                params["date_to"] = date_to
            
            response = requests.get(
                f"{self.api_base_url}/chat/history",
                params=params,
                headers={"Authorization": f"Bearer {self.current_token}"},
                timeout=10
            )
            
            if response.status_code == 200:
                data = response.json()
                history_items = data.get("history", [])
                total_count = data.get("total", 0)
                
                # Convert to display format
                display_history = []
                for item in history_items:
                    timestamp = item.get("created_at", "")
                    model = item.get("model_name", "Unknown")
                    credits = item.get("credits_charged", 0)
                    processing_time = item.get("processing_time_ms", 0)
                    
                    # Format timestamp
                    try:
                        dt = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
                        formatted_time = dt.strftime("%Y-%m-%d %H:%M:%S")
                    except:
                        formatted_time = timestamp
                    
                    # Truncate long text
                    prompt = item.get("prompt", "")
                    response_text = item.get("response", "")
                    
                    prompt_display = prompt[:100] + "..." if len(prompt) > 100 else prompt
                    response_display = response_text[:100] + "..." if len(response_text) > 100 else response_text
                    
                    display_history.append([
                        formatted_time,
                        model,
                        prompt_display,
                        response_display,
                        f"{credits} credits",
                        f"{processing_time}ms" if processing_time else "N/A"
                    ])
                
                status_msg = f"✅ Loaded {len(display_history)} of {total_count} interactions"
                return display_history, status_msg, total_count
            else:
                error_msg = f"❌ Failed to load history: HTTP {response.status_code}"
                if response.status_code == 401:
                    error_msg = "❌ Authentication failed. Please login again."
                return [], error_msg, 0
                
        except Exception as e:
            return [], f"❌ Error loading history: {str(e)}", 0
    
    def get_available_models(self) -> List[str]:
        """Get list of available models for filtering"""
        try:
            if not self.current_token:
                return ["all"]
            
            # Prefer chat models endpoint which includes cost/availability
            response = requests.get(
                f"{self.api_base_url}/chat/models",
                headers={"Authorization": f"Bearer {self.current_token}"},
                timeout=10
            )
            
            if response.status_code == 200:
                data = response.json()
                models = data.get("available_models", []) if isinstance(data, dict) else []
                if not models and isinstance(data, list):
                    models = data
                names: List[str] = []
                for m in models:
                    if isinstance(m, dict):
                        name = m.get("name")
                        if name:
                            names.append(name)
                    else:
                        names.append(str(m))
                return ["all"] + names
            else:
                return ["all", "gemma3-1b", "gemma3-12b"]  # Fallback
                
        except Exception:
            return ["all", "gemma3-1b", "gemma3-12b"]  # Fallback
    
    def get_usage_statistics(self, days: int = 7) -> Tuple[Dict[str, Any], str]:
        """Get usage statistics for the specified period"""
        try:
            if not self.current_token:
                return {}, "❌ Not authenticated"
            
            response = requests.get(
                f"{self.api_base_url}/monitoring/analytics",
                params={"days": days},
                headers={"Authorization": f"Bearer {self.current_token}"},
                timeout=10
            )
            
            if response.status_code == 200:
                data = response.json()
                analytics = data.get("analytics", {})
                return analytics, f"✅ Statistics loaded for last {days} days"
            else:
                return {}, f"❌ Failed to load statistics: HTTP {response.status_code}"
                
        except Exception as e:
            return {}, f"❌ Error loading statistics: {str(e)}"
    
    def export_history_csv(self, model_filter: str = "all", date_from: str = "", 
                          date_to: str = "") -> Tuple[str, str]:
        """Export chat history to CSV file"""
        try:
            if not self.current_token:
                return "", "❌ Not authenticated"
            
            # Get all history data (large page size)
            history_data, status_msg, total_count = self.get_chat_history(
                page=1, page_size=1000, model_filter=model_filter, 
                date_from=date_from, date_to=date_to
            )
            
            if not history_data:
                return "", "❌ No data to export"
            
            # Convert to DataFrame
            df = pd.DataFrame(history_data, columns=[
                "Timestamp", "Model", "Prompt", "Response", "Credits", "Processing Time"
            ])
            
            # Generate filename
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"chat_history_{timestamp}.csv"
            
            # Save to CSV
            df.to_csv(filename, index=False)
            
            return filename, f"✅ Exported {len(history_data)} interactions to {filename}"
            
        except Exception as e:
            return "", f"❌ Export failed: {str(e)}"
    
    def create_interface(self) -> gr.Blocks:
        """Create the Gradio interface for history viewing"""
        
        with gr.Blocks(title="Chat History & Analytics") as interface:
            gr.Markdown("# 📊 Chat History & Analytics")
            
            with gr.Tab("Chat History"):
                with gr.Row():
                    with gr.Column(scale=2):
                        model_dropdown = gr.Dropdown(
                            choices=self.get_available_models(),
                            value="all",
                            label="Filter by Model",
                            interactive=True
                        )
                    with gr.Column(scale=2):
                        date_from = gr.Textbox(
                            label="From Date (YYYY-MM-DD)",
                            placeholder="2024-01-01",
                            interactive=True
                        )
                    with gr.Column(scale=2):
                        date_to = gr.Textbox(
                            label="To Date (YYYY-MM-DD)",
                            placeholder="2024-12-31",
                            interactive=True
                        )
                    with gr.Column(scale=1):
                        refresh_btn = gr.Button("🔄 Refresh", variant="primary")
                
                with gr.Row():
                    with gr.Column(scale=1):
                        prev_btn = gr.Button("⬅️ Previous", interactive=False)
                    with gr.Column(scale=2):
                        page_info = gr.Textbox(
                            value="Page 1",
                            label="Current Page",
                            interactive=False
                        )
                    with gr.Column(scale=1):
                        next_btn = gr.Button("➡️ Next", interactive=False)
                
                history_table = gr.Dataframe(
                    headers=["Timestamp", "Model", "Prompt", "Response", "Credits", "Processing Time"],
                    datatype=["str", "str", "str", "str", "str", "str"],
                    interactive=False,
                    wrap=True
                )
                
                status_text = gr.Textbox(
                    label="Status",
                    interactive=False,
                    value="Click Refresh to load history"
                )
                
                with gr.Row():
                    export_btn = gr.Button("📥 Export to CSV", variant="secondary")
                    export_status = gr.Textbox(
                        label="Export Status",
                        interactive=False,
                        visible=False
                    )
            
            with gr.Tab("Usage Statistics"):
                with gr.Row():
                    stats_days = gr.Slider(
                        minimum=1,
                        maximum=30,
                        value=7,
                        step=1,
                        label="Analysis Period (days)"
                    )
                    load_stats_btn = gr.Button("📈 Load Statistics", variant="primary")
                
                with gr.Row():
                    with gr.Column():
                        total_interactions = gr.Number(
                            label="Total Interactions",
                            interactive=False
                        )
                        total_credits = gr.Number(
                            label="Total Credits Used",
                            interactive=False
                        )
                    with gr.Column():
                        avg_processing_time = gr.Number(
                            label="Avg Processing Time (ms)",
                            interactive=False
                        )
                        active_users = gr.Number(
                            label="Active Users",
                            interactive=False
                        )
                
                model_usage_table = gr.Dataframe(
                    headers=["Model", "Interactions", "Credits Used", "Avg Time (ms)"],
                    datatype=["str", "number", "number", "number"],
                    interactive=False,
                    label="Usage by Model"
                )
                
                stats_status = gr.Textbox(
                    label="Statistics Status",
                    interactive=False,
                    value="Click Load Statistics to view analytics"
                )
            
            # State variables
            current_page_state = gr.State(1)
            total_pages_state = gr.State(1)
            
            # Event handlers
            def load_history_page(page, model_filter, date_from, date_to):
                """Load specific page of history"""
                history_data, status, total_count = self.get_chat_history(
                    page=page, page_size=self.page_size,
                    model_filter=model_filter, date_from=date_from, date_to=date_to
                )
                
                total_pages = max(1, (total_count + self.page_size - 1) // self.page_size)
                page_text = f"Page {page} of {total_pages}"
                
                # Update button states
                prev_interactive = page > 1
                next_interactive = page < total_pages
                
                return (
                    history_data, status, page_text, page, total_pages,
                    gr.update(interactive=prev_interactive),
                    gr.update(interactive=next_interactive)
                )
            
            def go_to_page(direction, current_page, total_pages, model_filter, date_from, date_to):
                """Navigate to previous/next page"""
                if direction == "prev" and current_page > 1:
                    new_page = current_page - 1
                elif direction == "next" and current_page < total_pages:
                    new_page = current_page + 1
                else:
                    new_page = current_page
                
                return load_history_page(new_page, model_filter, date_from, date_to)
            
            def load_statistics(days):
                """Load usage statistics"""
                stats, status = self.get_usage_statistics(days)
                
                if not stats:
                    return 0, 0, 0, 0, [], status
                
                models_data = stats.get("models", {})
                users_data = stats.get("users", {})
                
                total_int = models_data.get("total_interactions", 0)
                total_cred = models_data.get("total_credits_used", 0)
                avg_time = models_data.get("avg_processing_time_ms", 0)
                active_usr = users_data.get("active_users", 0)
                
                # Model usage breakdown
                by_model = models_data.get("by_model", {})
                model_table = []
                for model_name, model_stats in by_model.items():
                    model_table.append([
                        model_name,
                        model_stats.get("count", 0),
                        model_stats.get("credits_used", 0),
                        model_stats.get("avg_processing_time_ms", 0)
                    ])
                
                return total_int, total_cred, avg_time, active_usr, model_table, status
            
            def export_history(model_filter, date_from, date_to):
                """Export history to CSV"""
                filename, status = self.export_history_csv(model_filter, date_from, date_to)
                return status, gr.update(visible=True)
            
            # Connect events
            refresh_btn.click(
                fn=lambda mf, df, dt, cp: load_history_page(1, mf, df, dt),
                inputs=[model_dropdown, date_from, date_to, current_page_state],
                outputs=[
                    history_table, status_text, page_info, 
                    current_page_state, total_pages_state,
                    prev_btn, next_btn
                ]
            )
            
            prev_btn.click(
                fn=lambda cp, tp, mf, df, dt: go_to_page("prev", cp, tp, mf, df, dt),
                inputs=[current_page_state, total_pages_state, model_dropdown, date_from, date_to],
                outputs=[
                    history_table, status_text, page_info,
                    current_page_state, total_pages_state,
                    prev_btn, next_btn
                ]
            )
            
            next_btn.click(
                fn=lambda cp, tp, mf, df, dt: go_to_page("next", cp, tp, mf, df, dt),
                inputs=[current_page_state, total_pages_state, model_dropdown, date_from, date_to],
                outputs=[
                    history_table, status_text, page_info,
                    current_page_state, total_pages_state,
                    prev_btn, next_btn
                ]
            )
            
            load_stats_btn.click(
                fn=load_statistics,
                inputs=[stats_days],
                outputs=[
                    total_interactions, total_credits, avg_processing_time,
                    active_users, model_usage_table, stats_status
                ]
            )
            
            export_btn.click(
                fn=export_history,
                inputs=[model_dropdown, date_from, date_to],
                outputs=[export_status, export_status]
            )
        
        return interface


def create_history_interface(api_base_url: str = None) -> HistoryInterface:
    """Factory function to create HistoryInterface"""
    return HistoryInterface(api_base_url)
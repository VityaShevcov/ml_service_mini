"""
Gradio interface for administrative functions
"""
import gradio as gr
import requests
import pandas as pd
from typing import List, Dict, Any, Tuple, Optional
from datetime import datetime, timedelta

from config import settings


class AdminInterface:
    """Interface for administrative functions and analytics"""
    
    def __init__(self, api_base_url: str = None):
        self.api_base_url = api_base_url or f"http://{settings.host}:{settings.port}"
        self.current_token = None
        self.is_admin = False
    
    def set_auth(self, token: str):
        """Set authentication token and verify admin status"""
        self.current_token = token
        self.is_admin = self._verify_admin_access()
    
    def _verify_admin_access(self) -> bool:
        """Verify if current user has admin access"""
        try:
            if not self.current_token:
                return False
            
            response = requests.get(
                f"{self.api_base_url}/admin/dashboard",
                headers={"Authorization": f"Bearer {self.current_token}"},
                timeout=10
            )
            
            return response.status_code == 200
            
        except Exception:
            return False
    
    def get_dashboard_data(self, days: int = 7) -> Tuple[Dict[str, Any], str]:
        """Get admin dashboard data"""
        try:
            if not self.current_token:
                return {}, "❌ Not authenticated"
            
            response = requests.get(
                f"{self.api_base_url}/admin/dashboard",
                params={"days": days},
                headers={"Authorization": f"Bearer {self.current_token}"},
                timeout=10
            )
            
            if response.status_code == 200:
                data = response.json()
                dashboard = data.get("dashboard", {})
                return dashboard, f"✅ Dashboard loaded for last {days} days"
            elif response.status_code == 403:
                return {}, "❌ Admin access required"
            else:
                return {}, f"❌ Failed to load dashboard: HTTP {response.status_code}"
                
        except Exception as e:
            return {}, f"❌ Error loading dashboard: {str(e)}"
    
    def get_users_list(self, page: int = 1, search: str = "") -> Tuple[List[List], str, int]:
        """Get users list with search"""
        try:
            if not self.current_token:
                return [], "❌ Not authenticated", 0
            
            params = {"page": page, "page_size": 20}
            if search:
                params["search"] = search
            
            response = requests.get(
                f"{self.api_base_url}/admin/users",
                params=params,
                headers={"Authorization": f"Bearer {self.current_token}"},
                timeout=10
            )
            
            if response.status_code == 200:
                data = response.json()
                users = data.get("users", [])
                total = data.get("pagination", {}).get("total", 0)
                
                # Format for display
                users_display = []
                for user in users:
                    stats = user.get("statistics", {})
                    users_display.append([
                        user.get("id", ""),
                        user.get("username", ""),
                        user.get("email", ""),
                        user.get("credits", 0),
                        stats.get("total_interactions", 0),
                        stats.get("total_credits_spent", 0),
                        user.get("created_at", "")[:10],  # Date only
                        "✅" if user.get("is_active", False) else "❌"
                    ])
                
                return users_display, f"✅ Loaded {len(users)} users", total
            else:
                return [], f"❌ Failed to load users: HTTP {response.status_code}", 0
                
        except Exception as e:
            return [], f"❌ Error loading users: {str(e)}", 0
    
    def get_user_details(self, user_id: int) -> Tuple[Dict[str, Any], str]:
        """Get detailed user information"""
        try:
            if not self.current_token:
                return {}, "❌ Not authenticated"
            
            response = requests.get(
                f"{self.api_base_url}/admin/users/{user_id}",
                headers={"Authorization": f"Bearer {self.current_token}"},
                timeout=10
            )
            
            if response.status_code == 200:
                data = response.json()
                return data, "✅ User details loaded"
            elif response.status_code == 404:
                return {}, "❌ User not found"
            else:
                return {}, f"❌ Failed to load user details: HTTP {response.status_code}"
                
        except Exception as e:
            return {}, f"❌ Error loading user details: {str(e)}"
    
    def adjust_user_credits(self, user_id: int, amount: int, description: str) -> Tuple[bool, str]:
        """Adjust user credits"""
        try:
            if not self.current_token:
                return False, "❌ Not authenticated"
            
            response = requests.post(
                f"{self.api_base_url}/admin/users/{user_id}/credits",
                params={"amount": amount, "description": description},
                headers={"Authorization": f"Bearer {self.current_token}"},
                timeout=10
            )
            
            if response.status_code == 200:
                data = response.json()
                new_balance = data.get("new_balance", 0)
                return True, f"✅ Credits adjusted. New balance: {new_balance}"
            else:
                error_detail = response.json().get("detail", "Unknown error")
                return False, f"❌ Failed to adjust credits: {error_detail}"
                
        except Exception as e:
            return False, f"❌ Error adjusting credits: {str(e)}"
    
    def generate_usage_report(self, days: int = 30, format: str = "json") -> Tuple[str, str]:
        """Generate usage report"""
        try:
            if not self.current_token:
                return "", "❌ Not authenticated"
            
            response = requests.get(
                f"{self.api_base_url}/admin/reports/usage",
                params={"days": days, "format": format},
                headers={"Authorization": f"Bearer {self.current_token}"},
                timeout=30
            )
            
            if response.status_code == 200:
                data = response.json()
                
                if format == "csv":
                    content = data.get("content", "")
                    filename = data.get("filename", f"usage_report_{datetime.now().strftime('%Y%m%d')}.csv")
                    
                    # Save to file
                    with open(filename, 'w') as f:
                        f.write(content)
                    
                    return filename, f"✅ CSV report generated: {filename}"
                else:
                    # JSON format - return formatted string
                    import json
                    report_json = json.dumps(data.get("report", {}), indent=2)
                    return report_json, f"✅ JSON report generated for last {days} days"
            else:
                return "", f"❌ Failed to generate report: HTTP {response.status_code}"
                
        except Exception as e:
            return "", f"❌ Error generating report: {str(e)}"
    
    def get_financial_report(self, days: int = 30) -> Tuple[Dict[str, Any], str]:
        """Get financial report"""
        try:
            if not self.current_token:
                return {}, "❌ Not authenticated"
            
            response = requests.get(
                f"{self.api_base_url}/admin/reports/financial",
                params={"days": days},
                headers={"Authorization": f"Bearer {self.current_token}"},
                timeout=10
            )
            
            if response.status_code == 200:
                data = response.json()
                return data.get("report", {}), f"✅ Financial report loaded for last {days} days"
            else:
                return {}, f"❌ Failed to load financial report: HTTP {response.status_code}"
                
        except Exception as e:
            return {}, f"❌ Error loading financial report: {str(e)}"
    
    def get_system_status(self) -> Tuple[Dict[str, Any], str]:
        """Get system status"""
        try:
            if not self.current_token:
                return {}, "❌ Not authenticated"
            
            response = requests.get(
                f"{self.api_base_url}/admin/system/status",
                headers={"Authorization": f"Bearer {self.current_token}"},
                timeout=10
            )
            
            if response.status_code == 200:
                data = response.json()
                return data.get("system_status", {}), "✅ System status loaded"
            else:
                return {}, f"❌ Failed to load system status: HTTP {response.status_code}"
                
        except Exception as e:
            return {}, f"❌ Error loading system status: {str(e)}"
    
    def create_interface(self) -> gr.Blocks:
        """Create the Gradio interface for admin functions"""
        
        with gr.Blocks(title="Admin Panel") as interface:
            
            # Check admin access
            if not self.is_admin:
                gr.Markdown("# ❌ Access Denied")
                gr.Markdown("You need administrator privileges to access this panel.")
                return interface
            
            gr.Markdown("# 🔧 Admin Panel")
            
            with gr.Tabs():
                
                # Dashboard Tab
                with gr.Tab("📊 Dashboard"):
                    with gr.Row():
                        dashboard_days = gr.Slider(
                            minimum=1, maximum=90, value=7, step=1,
                            label="Analysis Period (days)"
                        )
                        refresh_dashboard_btn = gr.Button("🔄 Refresh Dashboard", variant="primary")
                    
                    with gr.Row():
                        with gr.Column():
                            total_users_display = gr.Number(label="Total Users", interactive=False)
                            active_users_display = gr.Number(label="Active Users", interactive=False)
                            activity_rate_display = gr.Number(label="Activity Rate (%)", interactive=False)
                        
                        with gr.Column():
                            total_interactions_display = gr.Number(label="Total Interactions", interactive=False)
                            total_credits_display = gr.Number(label="Credits Used", interactive=False)
                            avg_processing_time_display = gr.Number(label="Avg Processing Time (ms)", interactive=False)
                    
                    system_health_display = gr.Textbox(
                        label="System Health",
                        interactive=False,
                        lines=3
                    )
                    
                    dashboard_status = gr.Textbox(
                        label="Status",
                        interactive=False,
                        value="Click Refresh Dashboard to load data"
                    )
                
                # Users Management Tab
                with gr.Tab("👥 Users"):
                    with gr.Row():
                        user_search = gr.Textbox(
                            label="Search Users",
                            placeholder="Username or email"
                        )
                        search_users_btn = gr.Button("🔍 Search", variant="primary")
                    
                    users_table = gr.Dataframe(
                        headers=["ID", "Username", "Email", "Credits", "Interactions", "Credits Spent", "Created", "Active"],
                        datatype=["number", "str", "str", "number", "number", "number", "str", "str"],
                        interactive=False
                    )
                    
                    with gr.Row():
                        selected_user_id = gr.Number(label="User ID", precision=0)
                        credit_adjustment = gr.Number(label="Credit Adjustment (+/-)")
                        adjustment_description = gr.Textbox(label="Description", value="Admin adjustment")
                        adjust_credits_btn = gr.Button("💰 Adjust Credits", variant="secondary")
                    
                    users_status = gr.Textbox(
                        label="Status",
                        interactive=False,
                        value="Search for users to manage"
                    )
                
                # Reports Tab
                with gr.Tab("📈 Reports"):
                    with gr.Row():
                        report_days = gr.Slider(
                            minimum=1, maximum=365, value=30, step=1,
                            label="Report Period (days)"
                        )
                        report_format = gr.Dropdown(
                            choices=["json", "csv"],
                            value="json",
                            label="Format"
                        )
                    
                    with gr.Row():
                        generate_usage_btn = gr.Button("📊 Generate Usage Report", variant="primary")
                        generate_financial_btn = gr.Button("💰 Generate Financial Report", variant="primary")
                    
                    report_output = gr.Textbox(
                        label="Report Output",
                        lines=20,
                        interactive=False
                    )
                    
                    financial_summary = gr.Textbox(
                        label="Financial Summary",
                        lines=10,
                        interactive=False
                    )
                    
                    reports_status = gr.Textbox(
                        label="Status",
                        interactive=False,
                        value="Select report type and click generate"
                    )
                
                # System Status Tab
                with gr.Tab("🖥️ System"):
                    refresh_system_btn = gr.Button("🔄 Refresh System Status", variant="primary")
                    
                    with gr.Row():
                        with gr.Column():
                            cpu_usage = gr.Number(label="CPU Usage (%)", interactive=False)
                            memory_usage = gr.Number(label="Memory Usage (%)", interactive=False)
                            disk_usage = gr.Number(label="Disk Usage (%)", interactive=False)
                        
                        with gr.Column():
                            gpu_available = gr.Textbox(label="GPU Status", interactive=False)
                            uptime = gr.Number(label="Uptime (hours)", interactive=False)
                            health_status = gr.Textbox(label="Health Status", interactive=False)
                    
                    system_details = gr.Textbox(
                        label="System Details",
                        lines=15,
                        interactive=False
                    )
                    
                    system_status = gr.Textbox(
                        label="Status",
                        interactive=False,
                        value="Click Refresh to load system status"
                    )
            
            # Event handlers
            def load_dashboard(days):
                """Load dashboard data"""
                dashboard, status = self.get_dashboard_data(days)
                
                if not dashboard:
                    return (0, 0, 0, 0, 0, 0, "No data", status)
                
                users_data = dashboard.get("users", {})
                usage_data = dashboard.get("usage", {})
                models_data = usage_data.get("models", {})
                health_data = dashboard.get("system", {}).get("health", {})
                
                health_text = f"Status: {health_data.get('status', 'Unknown')}\n"
                health_text += f"Issues: {', '.join(health_data.get('issues', []))}"
                
                return (
                    users_data.get("total_users", 0),
                    users_data.get("active_users", 0),
                    users_data.get("activity_rate", 0),
                    models_data.get("total_interactions", 0),
                    models_data.get("total_credits_used", 0),
                    models_data.get("avg_processing_time_ms", 0),
                    health_text,
                    status
                )
            
            def search_users(search_term):
                """Search users"""
                users, status, total = self.get_users_list(page=1, search=search_term)
                return users, status
            
            def adjust_credits(user_id, amount, description):
                """Adjust user credits"""
                if not user_id or amount == 0:
                    return "❌ Please provide valid user ID and non-zero amount"
                
                success, message = self.adjust_user_credits(int(user_id), int(amount), description)
                return message
            
            def generate_usage_report(days, format):
                """Generate usage report"""
                report, status = self.generate_usage_report(days, format)
                return report, status
            
            def generate_financial_report(days):
                """Generate financial report"""
                report, status = self.get_financial_report(days)
                
                if not report:
                    return "", status
                
                summary = report.get("summary", {})
                summary_text = f"Period: {days} days\n"
                summary_text += f"Credits Added: {summary.get('total_credits_added', 0)}\n"
                summary_text += f"Credits Spent: {summary.get('total_credits_spent', 0)}\n"
                summary_text += f"Net Flow: {summary.get('net_flow', 0)}\n"
                summary_text += f"Total Transactions: {summary.get('total_transactions', 0)}"
                
                return summary_text, status
            
            def load_system_status():
                """Load system status"""
                status_data, status = self.get_system_status()
                
                if not status_data:
                    return (0, 0, 0, "Unknown", 0, "Unknown", "No data", status)
                
                metrics = status_data.get("metrics", {})
                health = status_data.get("health", {})
                
                cpu_pct = metrics.get("cpu", {}).get("percent", 0)
                memory_pct = metrics.get("memory", {}).get("percent", 0)
                disk_pct = metrics.get("disk", {}).get("percent", 0)
                gpu_status = "Available" if metrics.get("gpu", {}).get("available", False) else "Not Available"
                uptime_hours = metrics.get("uptime_seconds", 0) / 3600
                health_stat = health.get("status", "Unknown")
                
                import json
                details = json.dumps(status_data, indent=2)
                
                return (cpu_pct, memory_pct, disk_pct, gpu_status, uptime_hours, health_stat, details, status)
            
            # Connect events
            refresh_dashboard_btn.click(
                fn=load_dashboard,
                inputs=[dashboard_days],
                outputs=[
                    total_users_display, active_users_display, activity_rate_display,
                    total_interactions_display, total_credits_display, avg_processing_time_display,
                    system_health_display, dashboard_status
                ]
            )
            
            search_users_btn.click(
                fn=search_users,
                inputs=[user_search],
                outputs=[users_table, users_status]
            )
            
            adjust_credits_btn.click(
                fn=adjust_credits,
                inputs=[selected_user_id, credit_adjustment, adjustment_description],
                outputs=[users_status]
            )
            
            generate_usage_btn.click(
                fn=generate_usage_report,
                inputs=[report_days, report_format],
                outputs=[report_output, reports_status]
            )
            
            generate_financial_btn.click(
                fn=generate_financial_report,
                inputs=[report_days],
                outputs=[financial_summary, reports_status]
            )
            
            refresh_system_btn.click(
                fn=load_system_status,
                inputs=[],
                outputs=[
                    cpu_usage, memory_usage, disk_usage, gpu_available,
                    uptime, health_status, system_details, system_status
                ]
            )
        
        return interface


def create_admin_interface(api_base_url: str = None) -> AdminInterface:
    """Factory function to create AdminInterface"""
    return AdminInterface(api_base_url)
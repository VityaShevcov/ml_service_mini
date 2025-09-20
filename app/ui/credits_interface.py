"""
Gradio interface for credit management and top-up
"""
import gradio as gr
import requests
from typing import List, Dict, Any, Tuple, Optional
from datetime import datetime

from config import settings


class CreditsInterface:
    """Interface for credit management and top-up operations"""
    
    def __init__(self, api_base_url: str = None):
        self.api_base_url = api_base_url or f"http://{settings.host}:{settings.port}"
        self.current_token = None
        self.current_user = None
    
    def set_auth(self, token: str, user_info: Dict[str, Any] = None):
        """Set authentication token and user info"""
        self.current_token = token
        self.current_user = user_info
    
    def get_current_balance(self) -> Tuple[int, str]:
        """Get current user credit balance"""
        try:
            if not self.current_token:
                return 0, "❌ Not authenticated"
            
            response = requests.get(
                f"{self.api_base_url}/billing/balance",
                headers={"Authorization": f"Bearer {self.current_token}"},
                timeout=10
            )
            
            if response.status_code == 200:
                data = response.json()
                balance = data.get("credits", 0)  # API returns "credits", not "balance"
                return balance, f"✅ Current balance: {balance} credits"
            else:
                return 0, f"❌ Failed to get balance: HTTP {response.status_code}"
                
        except Exception as e:
            return 0, f"❌ Error getting balance: {str(e)}"
    
    def add_credits(self, amount: int, description: str = "Credit top-up") -> Tuple[bool, str, int]:
        """Add credits to user account"""
        try:
            if not self.current_token:
                return False, "❌ Not authenticated", 0
            
            if amount <= 0:
                return False, "❌ Amount must be positive", 0
            
            response = requests.post(
                f"{self.api_base_url}/billing/add",
                json={
                    "amount": amount,
                    "description": description
                },
                headers={"Authorization": f"Bearer {self.current_token}"},
                timeout=10
            )
            
            if response.status_code == 200:
                data = response.json()
                new_balance = data.get("credits", 0)  # API returns "credits", not "new_balance"
                return True, f"✅ Added {amount} credits. New balance: {new_balance}", new_balance
            else:
                error_detail = response.json().get("detail", "Unknown error")
                return False, f"❌ Failed to add credits: {error_detail}", 0
                
        except Exception as e:
            return False, f"❌ Error adding credits: {str(e)}", 0
    
    def get_transaction_history(self, limit: int = 20) -> Tuple[List[List], str]:
        """Get credit transaction history"""
        try:
            if not self.current_token:
                return [], "❌ Not authenticated"
            
            response = requests.get(
                f"{self.api_base_url}/billing/transactions",
                params={"limit": limit},
                headers={"Authorization": f"Bearer {self.current_token}"},
                timeout=10
            )
            
            if response.status_code == 200:
                data = response.json()
                transactions = data.get("transactions", [])
                
                # Format for display
                history_display = []
                for transaction in transactions:
                    timestamp = transaction.get("created_at", "")
                    try:
                        dt = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
                        formatted_time = dt.strftime("%Y-%m-%d %H:%M:%S")
                    except:
                        formatted_time = timestamp
                    
                    transaction_type = transaction.get("transaction_type", "")
                    amount = transaction.get("amount", 0)
                    description = transaction.get("description", "")
                    
                    # Format amount with sign
                    if transaction_type == "add":
                        amount_display = f"+{amount}"
                        type_display = "➕ Credit Added"
                    else:
                        amount_display = f"-{abs(amount)}"
                        type_display = "➖ Credit Used"
                    
                    history_display.append([
                        formatted_time,
                        type_display,
                        amount_display,
                        description
                    ])
                
                return history_display, f"✅ Loaded {len(history_display)} transactions"
            else:
                return [], f"❌ Failed to load history: HTTP {response.status_code}"
                
        except Exception as e:
            return [], f"❌ Error loading history: {str(e)}"
    
    def get_credit_packages(self) -> List[Dict[str, Any]]:
        """Get available credit packages"""
        # Predefined credit packages
        return [
            {"amount": 100, "price": "$5.00", "bonus": 0, "description": "Starter Pack"},
            {"amount": 250, "price": "$10.00", "bonus": 25, "description": "Popular Choice"},
            {"amount": 500, "price": "$20.00", "bonus": 75, "description": "Best Value"},
            {"amount": 1000, "price": "$35.00", "bonus": 200, "description": "Power User"},
            {"amount": 2500, "price": "$75.00", "bonus": 625, "description": "Enterprise"}
        ]
    
    def simulate_payment(self, package_amount: int, payment_method: str) -> Tuple[bool, str]:
        """Simulate payment processing (for demo purposes)"""
        try:
            # In a real implementation, this would integrate with payment processors
            # like Stripe, PayPal, etc.
            
            # Simulate processing time
            import time
            time.sleep(1)
            
            # Find the package
            packages = self.get_credit_packages()
            selected_package = None
            for package in packages:
                if package["amount"] == package_amount:
                    selected_package = package
                    break
            
            if not selected_package:
                return False, "❌ Invalid package selected"
            
            # Calculate total credits (base + bonus)
            total_credits = selected_package["amount"] + selected_package["bonus"]
            
            # Add credits to account
            success, message, new_balance = self.add_credits(
                total_credits, 
                f"Credit purchase: {selected_package['description']} ({payment_method})"
            )
            
            if success:
                return True, f"✅ Payment successful! Added {total_credits} credits ({selected_package['amount']} + {selected_package['bonus']} bonus)"
            else:
                return False, f"❌ Payment processed but credit addition failed: {message}"
                
        except Exception as e:
            return False, f"❌ Payment processing error: {str(e)}"
    
    def create_interface(self) -> gr.Blocks:
        """Create the Gradio interface for credit management"""
        
        with gr.Blocks(title="Credit Management") as interface:
            gr.Markdown("# 💰 Credit Management")
            
            with gr.Tabs():
                
                # Balance & Top-up Tab
                with gr.Tab("💳 Top-up Credits"):
                    with gr.Row():
                        current_balance_display = gr.Number(
                            label="Current Balance",
                            interactive=False,
                            value=0
                        )
                        refresh_balance_btn = gr.Button("🔄 Refresh", variant="secondary")
                    
                    gr.Markdown("## 📦 Credit Packages")
                    
                    # Create package selection
                    packages = self.get_credit_packages()
                    package_choices = []
                    package_info = {}
                    
                    for package in packages:
                        total_credits = package["amount"] + package["bonus"]
                        choice_text = f"{package['description']} - {package['amount']} credits"
                        if package["bonus"] > 0:
                            choice_text += f" + {package['bonus']} bonus = {total_credits} total"
                        choice_text += f" ({package['price']})"
                        
                        package_choices.append(choice_text)
                        package_info[choice_text] = package
                    
                    selected_package = gr.Dropdown(
                        choices=package_choices,
                        label="Select Package",
                        value=package_choices[1] if len(package_choices) > 1 else None
                    )
                    
                    with gr.Row():
                        payment_method = gr.Dropdown(
                            choices=["Credit Card", "PayPal", "Bank Transfer", "Cryptocurrency"],
                            value="Credit Card",
                            label="Payment Method"
                        )
                        purchase_btn = gr.Button("💳 Purchase Credits", variant="primary")
                    
                    gr.Markdown("## ➕ Custom Amount")
                    
                    with gr.Row():
                        custom_amount = gr.Number(
                            label="Custom Amount",
                            minimum=1,
                            maximum=10000,
                            step=1,
                            value=100
                        )
                        custom_description = gr.Textbox(
                            label="Description",
                            value="Custom credit addition",
                            placeholder="Optional description"
                        )
                        add_custom_btn = gr.Button("➕ Add Credits", variant="secondary")
                    
                    topup_status = gr.Textbox(
                        label="Status",
                        interactive=False,
                        value="Select a package or enter custom amount to add credits"
                    )
                
                # Transaction History Tab
                with gr.Tab("📊 Transaction History"):
                    with gr.Row():
                        history_limit = gr.Slider(
                            minimum=10,
                            maximum=100,
                            value=20,
                            step=10,
                            label="Number of transactions to show"
                        )
                        load_history_btn = gr.Button("📋 Load History", variant="primary")
                    
                    history_table = gr.Dataframe(
                        headers=["Date & Time", "Type", "Amount", "Description"],
                        datatype=["str", "str", "str", "str"],
                        interactive=False
                    )
                    
                    history_status = gr.Textbox(
                        label="Status",
                        interactive=False,
                        value="Click Load History to view your transactions"
                    )
                
                # Usage Analytics Tab
                with gr.Tab("📈 Usage Analytics"):
                    gr.Markdown("## 💡 Credit Usage Insights")
                    
                    with gr.Row():
                        analytics_days = gr.Slider(
                            minimum=7,
                            maximum=90,
                            value=30,
                            step=1,
                            label="Analysis Period (days)"
                        )
                        load_analytics_btn = gr.Button("📊 Load Analytics", variant="primary")
                    
                    with gr.Row():
                        with gr.Column():
                            total_spent = gr.Number(label="Total Credits Spent", interactive=False)
                            avg_daily_usage = gr.Number(label="Avg Daily Usage", interactive=False)
                        with gr.Column():
                            most_used_model = gr.Textbox(label="Most Used Model", interactive=False)
                            total_interactions = gr.Number(label="Total Interactions", interactive=False)
                    
                    usage_breakdown = gr.Textbox(
                        label="Usage Breakdown by Model",
                        lines=8,
                        interactive=False
                    )
                    
                    analytics_status = gr.Textbox(
                        label="Status",
                        interactive=False,
                        value="Click Load Analytics to view your usage patterns"
                    )
            
            # Event handlers
            def refresh_balance():
                """Refresh current balance"""
                balance, status = self.get_current_balance()
                return balance, status
            
            def purchase_package(package_text, payment_method):
                """Purchase selected package"""
                if not package_text:
                    return "❌ Please select a package", 0
                
                # Extract package amount from text
                for choice, package in package_info.items():
                    if choice == package_text:
                        success, message = self.simulate_payment(package["amount"], payment_method)
                        if success:
                            # Refresh balance
                            new_balance, _ = self.get_current_balance()
                            return message, new_balance
                        else:
                            return message, 0
                
                return "❌ Invalid package selected", 0
            
            def add_custom_credits(amount, description):
                """Add custom amount of credits"""
                if not amount or amount <= 0:
                    return "❌ Please enter a valid amount", 0
                
                success, message, new_balance = self.add_credits(int(amount), description)
                return message, new_balance if success else 0
            
            def load_transaction_history(limit):
                """Load transaction history"""
                history, status = self.get_transaction_history(int(limit))
                return history, status
            
            def load_usage_analytics(days):
                """Load usage analytics"""
                try:
                    if not self.current_token:
                        return 0, 0, "Not available", 0, "Not authenticated", "❌ Not authenticated"
                    
                    # Get chat statistics
                    response = requests.get(
                        f"{self.api_base_url}/chat/stats",
                        headers={"Authorization": f"Bearer {self.current_token}"},
                        timeout=10
                    )
                    
                    if response.status_code == 200:
                        data = response.json()
                        stats = data.get("stats", {})
                        
                        total_credits_spent = stats.get("total_credits_spent", 0)
                        total_msgs = stats.get("total_messages", 0)
                        favorite_model = stats.get("favorite_model", "None")
                        models_used = stats.get("models_used", {})
                        
                        avg_daily = round(total_credits_spent / days, 2) if days > 0 else 0
                        
                        # Format model breakdown
                        breakdown_text = "Model Usage Breakdown:\n"
                        for model, count in models_used.items():
                            breakdown_text += f"• {model}: {count} interactions\n"
                        
                        return (
                            total_credits_spent, avg_daily, favorite_model, total_msgs,
                            breakdown_text, f"✅ Analytics loaded for last {days} days"
                        )
                    else:
                        return 0, 0, "Error", 0, "Failed to load analytics", f"❌ HTTP {response.status_code}"
                        
                except Exception as e:
                    return 0, 0, "Error", 0, "Failed to load analytics", f"❌ Error: {str(e)}"
            
            # Connect events
            refresh_balance_btn.click(
                fn=refresh_balance,
                outputs=[current_balance_display, topup_status]
            )
            
            purchase_btn.click(
                fn=purchase_package,
                inputs=[selected_package, payment_method],
                outputs=[topup_status, current_balance_display]
            )
            
            add_custom_btn.click(
                fn=add_custom_credits,
                inputs=[custom_amount, custom_description],
                outputs=[topup_status, current_balance_display]
            )
            
            load_history_btn.click(
                fn=load_transaction_history,
                inputs=[history_limit],
                outputs=[history_table, history_status]
            )
            
            load_analytics_btn.click(
                fn=load_usage_analytics,
                inputs=[analytics_days],
                outputs=[
                    total_spent, avg_daily_usage, most_used_model,
                    total_interactions, usage_breakdown, analytics_status
                ]
            )
            
            # Auto-load balance on interface load
            interface.load(
                fn=refresh_balance,
                outputs=[current_balance_display, topup_status]
            )
        
        return interface


def create_credits_interface(api_base_url: str = None) -> CreditsInterface:
    """Factory function to create CreditsInterface"""
    return CreditsInterface(api_base_url)
"""
Gradio chat interface with ML models and billing
"""
import gradio as gr
import requests
from typing import List, Tuple, Optional
import json

from config import settings


class ChatInterface:
    """Main chat interface for ML interactions"""
    
    def __init__(self, api_base_url: str = None):
        self.api_base_url = api_base_url or f"http://{settings.host}:{settings.port}"
        self.current_token = None
        self.current_user = None
    
    def set_auth(self, token: str, user_info: dict = None):
        """Set authentication token and user info"""
        self.current_token = token
        self.current_user = user_info
    
    def get_available_models(self) -> List[str]:
        """Get available chat models"""
        try:
            response = requests.get(
                f"{self.api_base_url}/chat/models",
                timeout=10
            )
            
            if response.status_code == 200:
                data = response.json()
                models = data.get("available_models", [])
                names: List[str] = []
                if isinstance(models, list):
                    for m in models:
                        if isinstance(m, dict):
                            name = str(m.get("name", "")).strip()
                        else:
                            name = str(m).strip()
                        if name:
                            names.append(name)
                # Ensure both target models are selectable to allow reload-on-demand
                for required in ["Gemma3 1B", "Gemma3 4B"]:
                    if required not in names:
                        names.append(required)
                # Keep stable order: 1B first
                ordered = [n for n in ["Gemma3 1B", "Gemma3 4B"] if n in names]
                return ordered or ["Gemma3 1B", "Gemma3 4B"]
            else:
                return ["Gemma3 1B", "Gemma3 4B"]  # Fallback
                
        except Exception:
            return ["Gemma3 1B", "Gemma3 4B"]  # Fallback
    
    def get_user_credits(self) -> int:
        """Get current user credits"""
        try:
            if not self.current_token:
                return 0
            
            response = requests.get(
                f"{self.api_base_url}/billing/balance",
                headers={"Authorization": f"Bearer {self.current_token}"},
                timeout=10
            )
            
            if response.status_code == 200:
                data = response.json()
                return data.get("credits", 0)
            else:
                return 0
                
        except Exception:
            return 0
    
    def send_message(
        self,
        message: str,
        model: str,
        history: List[List[str]]
    ) -> Tuple[List[List[str]], str, str, Optional[int]]:
        """Send message to chat API and return response details.

        Returns (updated_history, credits_info, status_message, remaining_credits)
        where ``remaining_credits`` will be ``None`` if the value cannot be
        determined from the API response.
        """
        try:
            if not self.current_token:
                return history, "❌ Not authenticated", "Please login first"
            
            if not message.strip():
                return history, "", "Please enter a message"
            
            # Send message to API
            response = requests.post(
                f"{self.api_base_url}/chat/message",
                json={
                    "message": message.strip(),
                    "model": model,
                    "use_ollama": True  # Force Ollama for speed
                },
                headers={"Authorization": f"Bearer {self.current_token}"},
                timeout=30  # Longer timeout for ML generation
            )

            if response.status_code == 200:
                data = response.json()

                if data.get("success"):
                    # Add to history
                    ai_response = data.get("message", "No response")
                    credits_charged = data.get("credits_charged", 0)
                    remaining_credits = data.get("remaining_credits")
                    if remaining_credits is None and self.current_user is not None:
                        remaining_credits = self.current_user.get("credits")
                    processing_time = data.get("processing_time_ms", 0)
                    model_used = data.get("model_used", model)

                    # Update history - Gradio 5.x format
                    new_history = history + [
                        {"role": "user", "content": message},
                        {"role": "assistant", "content": ai_response}
                    ]

                    # Create credits info
                    credits_display_value = (
                        f"{remaining_credits}" if remaining_credits is not None else "unknown"
                    )
                    credits_info = (
                        f"💳 Credits: {credits_display_value} (-{credits_charged})"
                    )

                    # Create status message
                    status_msg = f"✅ Response generated using {model_used} in {processing_time}ms"

                    if remaining_credits is not None:
                        # Keep local cache in sync for UI updates without extra requests
                        if self.current_user is not None:
                            self.current_user["credits"] = remaining_credits

                    return new_history, credits_info, status_msg, remaining_credits
                else:
                    error_msg = data.get("message", "Unknown error")
                    return history, "❌ Generation failed", f"Error: {error_msg}", None

            elif response.status_code == 402:
                # Insufficient credits
                try:
                    error_data = response.json()
                    error_msg = error_data.get("detail", "Insufficient credits")
                    remaining_credits = error_data.get("remaining_credits")
                except:
                    error_msg = "Insufficient credits"
                    remaining_credits = None

                return history, "💳 Insufficient credits", f"❌ {error_msg}", remaining_credits

            elif response.status_code == 503:
                # Service unavailable
                return (
                    history,
                    "🔄 Service loading",
                    "ML service is initializing, please try again in a moment",
                    None,
                )

            else:
                try:
                    error_data = response.json()
                    error_msg = error_data.get("detail", f"HTTP {response.status_code}")
                except:
                    error_msg = f"HTTP {response.status_code}"

                return history, "❌ Error", f"Error: {error_msg}", None

        except requests.exceptions.Timeout:
            return (
                history,
                "⏱️ Timeout",
                "Request timed out. The model might be loading or busy.",
                None,
            )

        except requests.exceptions.RequestException as e:
            return (
                history,
                "🔌 Connection error",
                f"Connection error: {str(e)}",
                None,
            )

        except Exception as e:
            return (
                history,
                "❌ Unexpected error",
                f"Unexpected error: {str(e)}",
                None,
            )
    
    def add_credits(self, amount: int) -> Tuple[str, str]:
        """
        Add credits to user account
        Returns (credits_info, status_message)
        """
        try:
            if not self.current_token:
                return "❌ Not authenticated", "Please login first"
            
            if amount <= 0:
                return "", "Please enter a positive amount"
            
            response = requests.post(
                f"{self.api_base_url}/billing/add",
                json={"amount": amount},
                headers={"Authorization": f"Bearer {self.current_token}"},
                timeout=10
            )
            
            if response.status_code == 200:
                data = response.json()
                new_credits = data.get("credits", 0)
                message = data.get("message", "Credits added")
                
                return f"💳 Credits: {new_credits}", f"✅ {message}"
            else:
                try:
                    error_data = response.json()
                    error_msg = error_data.get("detail", "Failed to add credits")
                except:
                    error_msg = "Failed to add credits"
                
                return "❌ Error", f"Error: {error_msg}"
                
        except Exception as e:
            return "❌ Error", f"Error: {str(e)}"
    
    def get_chat_history(self) -> List[List[str]]:
        """Get user's chat history"""
        try:
            if not self.current_token:
                return []
            
            response = requests.get(
                f"{self.api_base_url}/chat/history?page=1&page_size=50",
                headers={"Authorization": f"Bearer {self.current_token}"},
                timeout=10
            )
            
            if response.status_code == 200:
                data = response.json()
                history_items = data.get("history", [])
                
                # Convert to chat format - Gradio 5.x format
                chat_history = []
                for item in history_items:
                    prompt = item.get("prompt", "")
                    response_text = item.get("response", "")
                    chat_history.extend([
                        {"role": "user", "content": prompt},
                        {"role": "assistant", "content": response_text}
                    ])
                
                return chat_history
            else:
                return []
                
        except Exception:
            return []
    
    def create_chat_interface(self) -> gr.Blocks:
        """Create main chat interface"""
        
        with gr.Blocks(title="ML Chat Service") as chat_interface:
            # Header
            with gr.Row():
                gr.Markdown("# 🤖 ML Chat Service")
                credits_display = gr.Markdown("💳 Credits: Loading...")
            
            # Main chat area
            with gr.Row():
                with gr.Column(scale=4):
                    chatbot = gr.Chatbot(
                        label="Chat with AI",
                        height=500,
                        show_label=True,
                        container=True,
                        type="messages"
                    )
                    
                    with gr.Row():
                        msg_input = gr.Textbox(
                            label="Message",
                            placeholder="Type your message here...",
                            lines=2,
                            max_lines=5,
                            scale=4
                        )
                        send_btn = gr.Button("Send", variant="primary", scale=1)
                    
                    with gr.Row():
                        _choices = self.get_available_models()
                        _default = "Gemma3 1B" if "Gemma3 1B" in _choices else (_choices[0] if _choices else "Gemma3 1B")
                        model_selector = gr.Radio(
                            choices=_choices,
                            value=_default,
                            label="Select Model",
                            info="Gemma3 1B: 1 credit, Gemma3 4B: 3 credits"
                        )
                        use_ollama = gr.Checkbox(label="Use Ollama backend", value=True)
                        clear_btn = gr.Button("Clear Chat", variant="secondary")
                    
                    model_recommendations = gr.Markdown(
                        "💡 **Smart Model Selection**: System will automatically use cheaper models if you don't have enough credits",
                        visible=True
                    )
                
                with gr.Column(scale=1):
                    gr.Markdown("### 💳 Credits")
                    
                    current_credits = gr.Number(
                        label="Current Credits",
                        value=0,
                        interactive=False
                    )
                    
                    add_amount = gr.Number(
                        label="Add Credits",
                        value=50,
                        minimum=1,
                        maximum=1000,
                        step=1
                    )
                    
                    add_credits_btn = gr.Button("Add Credits", variant="secondary")
                    
                    gr.Markdown("### 📊 Model Costs")
                    gr.Markdown("""
                    - **Gemma3 1B**: 1 credit per message
                    - **Gemma3 12B**: 3 credits per message
                    
                    💡 **Tip**: Use Gemma3 1B for quick responses, Gemma3 12B for detailed answers.
                    """)
                    
                    load_history_btn = gr.Button("Load History", variant="secondary")
            
            # Status area
            status_message = gr.Markdown("")
            
            # Hidden state for authentication
            auth_token = gr.Textbox(visible=False)
            
            # Event handlers
            def handle_prepare_model_switch(new_model: str):
                # Immediate feedback while backend reload runs
                return {status_message: f"⏳ Loading {new_model} ..."}

            def handle_reload_model(new_model: str, token: str):
                try:
                    if token:
                        self.current_token = token
                    headers = {"Authorization": f"Bearer {self.current_token}"} if self.current_token else {}
                    resp = requests.post(
                        f"{self.api_base_url}/ml/reload-model/{new_model}",
                        headers=headers,
                        timeout=180
                    )
                    if resp.status_code == 200:
                        data = resp.json() if resp.headers.get("content-type", "").startswith("application/json") else {}
                        if data.get("success", True):
                            return {status_message: f"✅ Model '{new_model}' loaded"}
                        return {status_message: f"❌ Failed to load '{new_model}'"}
                    # Error branch: try detail
                    try:
                        err = resp.json().get("detail", f"HTTP {resp.status_code}")
                    except Exception:
                        err = f"HTTP {resp.status_code}"
                    return {status_message: f"❌ Failed to load '{new_model}': {err}"}
                except requests.exceptions.Timeout:
                    return {status_message: f"⏱️ Timeout while loading '{new_model}'"}
                except Exception as e:
                    return {status_message: f"❌ Error while loading '{new_model}': {str(e)}"}
            def handle_send_message(message, model, history, token, use_ol):
                if token:
                    self.current_token = token

                # Pass model as is; backend switches by config
                new_history, credits_info, status, remaining = self.send_message(
                    message,
                    model,
                    history
                )

                updates = {
                    chatbot: new_history,
                    msg_input: "",
                    credits_display: credits_info,
                    status_message: status
                }

                if remaining is not None:
                    updates[current_credits] = remaining
                else:
                    # Leave current balance untouched when we cannot infer the value
                    updates[current_credits] = gr.update()

                return updates
            
            def handle_add_credits(amount, token):
                if token:
                    self.current_token = token
                
                credits_info, status = self.add_credits(amount)
                credits = self.get_user_credits()
                
                return {
                    credits_display: credits_info,
                    current_credits: credits,
                    status_message: status
                }
            
            def handle_load_history(token):
                if token:
                    self.current_token = token
                
                history = self.get_chat_history()
                return {
                    chatbot: history,
                    status_message: f"✅ Loaded {len(history)} messages from history"
                }
            
            def handle_clear_chat():
                return {
                    chatbot: [],
                    status_message: "✅ Chat cleared"
                }
            
            def update_credits_display(token):
                if token:
                    self.current_token = token
                    credits = self.get_user_credits()
                    return {
                        credits_display: f"💳 Credits: {credits}",
                        current_credits: credits
                    }
                return {
                    credits_display: "💳 Credits: Not logged in",
                    current_credits: 0
                }
            
            # Bind events
            # Model switch: show loading, then attempt reload and report result
            model_selector.change(
                fn=handle_prepare_model_switch,
                inputs=[model_selector],
                outputs=[status_message]
            ).then(
                fn=handle_reload_model,
                inputs=[model_selector, auth_token],
                outputs=[status_message]
            )
            send_btn.click(
                fn=handle_send_message,
                inputs=[msg_input, model_selector, chatbot, auth_token, use_ollama],
                outputs=[chatbot, msg_input, credits_display, current_credits, status_message]
            )
            
            msg_input.submit(
                fn=handle_send_message,
                inputs=[msg_input, model_selector, chatbot, auth_token, use_ollama],
                outputs=[chatbot, msg_input, credits_display, current_credits, status_message]
            )
            
            add_credits_btn.click(
                fn=handle_add_credits,
                inputs=[add_amount, auth_token],
                outputs=[credits_display, current_credits, status_message]
            )
            
            load_history_btn.click(
                fn=handle_load_history,
                inputs=[auth_token],
                outputs=[chatbot, status_message]
            )
            
            clear_btn.click(
                fn=handle_clear_chat,
                outputs=[chatbot, status_message]
            )
            
            # Update credits on token change
            auth_token.change(
                fn=update_credits_display,
                inputs=[auth_token],
                outputs=[credits_display, current_credits]
            )
            
            # Store components for external access
            chat_interface.auth_token = auth_token
            chat_interface.chatbot = chatbot
            chat_interface.credits_display = credits_display
            chat_interface.status_message = status_message

        return chat_interface

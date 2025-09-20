"""
Gradio authentication interface
"""
import gradio as gr
import requests
from typing import Tuple, Optional

from config import settings


class AuthInterface:
    """Authentication interface for Gradio"""
    
    def __init__(self, api_base_url: str = None):
        self.api_base_url = api_base_url or f"http://{settings.host}:{settings.port}"
        self.current_token = None
        self.current_user = None
    
    def login(self, username: str, password: str) -> Tuple[bool, str, str]:
        """
        Login user and return status
        Returns (success, message, token)
        """
        try:
            if not username or not password:
                return False, "Please enter both username and password", ""
            
            response = requests.post(
                f"{self.api_base_url}/auth/login",
                json={"username": username, "password": password},
                timeout=10
            )
            
            if response.status_code == 200:
                data = response.json()
                if data.get("success") and data.get("data", {}).get("access_token"):
                    token = data["data"]["access_token"]
                    user_info = data["data"]["user"]
                    
                    self.current_token = token
                    self.current_user = user_info
                    
                    return True, f"Welcome, {user_info['username']}! You have {user_info['credits']} credits.", token
                else:
                    return False, data.get("message", "Login failed"), ""
            else:
                try:
                    error_data = response.json()
                    return False, error_data.get("detail", "Login failed"), ""
                except:
                    return False, f"Login failed (HTTP {response.status_code})", ""
                    
        except requests.exceptions.RequestException as e:
            return False, f"Connection error: {str(e)}", ""
        except Exception as e:
            return False, f"Unexpected error: {str(e)}", ""
    
    def register(self, username: str, email: str, password: str, confirm_password: str) -> Tuple[bool, str]:
        """
        Register new user
        Returns (success, message)
        """
        try:
            # Validate inputs
            if not all([username, email, password, confirm_password]):
                return False, "Please fill in all fields"
            
            if password != confirm_password:
                return False, "Passwords do not match"
            
            if len(password) < 8:
                return False, "Password must be at least 8 characters long"
            
            if "@" not in email:
                return False, "Please enter a valid email address"
            
            response = requests.post(
                f"{self.api_base_url}/auth/register",
                json={
                    "username": username,
                    "email": email,
                    "password": password
                },
                timeout=10
            )
            
            if response.status_code == 200:
                data = response.json()
                if data.get("success"):
                    return True, f"Registration successful! You can now login with username '{username}'"
                else:
                    return False, data.get("message", "Registration failed")
            else:
                try:
                    error_data = response.json()
                    return False, error_data.get("detail", "Registration failed")
                except:
                    return False, f"Registration failed (HTTP {response.status_code})"
                    
        except requests.exceptions.RequestException as e:
            return False, f"Connection error: {str(e)}"
        except Exception as e:
            return False, f"Unexpected error: {str(e)}"
    
    def get_user_info(self, token: str) -> Optional[dict]:
        """Get current user information"""
        try:
            if not token:
                return None
            
            response = requests.get(
                f"{self.api_base_url}/auth/me",
                headers={"Authorization": f"Bearer {token}"},
                timeout=10
            )
            
            if response.status_code == 200:
                return response.json()
            else:
                return None
                
        except Exception:
            return None
    
    def create_auth_interface(self) -> gr.Blocks:
        """Create Gradio authentication interface"""
        
        with gr.Blocks(title="ML Chat Service - Login") as auth_interface:
            gr.Markdown("# 🤖 ML Chat Service")
            gr.Markdown("Welcome to the ML Chat Service! Please login or register to continue.")
            
            with gr.Tabs():
                with gr.Tab("Login"):
                    with gr.Column():
                        login_username = gr.Textbox(
                            label="Username",
                            placeholder="Enter your username",
                            max_lines=1
                        )
                        login_password = gr.Textbox(
                            label="Password",
                            placeholder="Enter your password",
                            type="password",
                            max_lines=1
                        )
                        login_btn = gr.Button("Login", variant="primary")
                        login_message = gr.Markdown("")
                        
                        # Hidden components to store auth state
                        auth_token = gr.Textbox(visible=False)
                        auth_success = gr.Textbox(visible=False)
                
                with gr.Tab("Register"):
                    with gr.Column():
                        reg_username = gr.Textbox(
                            label="Username",
                            placeholder="Choose a username (min 3 characters)",
                            max_lines=1
                        )
                        reg_email = gr.Textbox(
                            label="Email",
                            placeholder="Enter your email address",
                            max_lines=1
                        )
                        reg_password = gr.Textbox(
                            label="Password",
                            placeholder="Choose a password (min 8 characters)",
                            type="password",
                            max_lines=1
                        )
                        reg_confirm_password = gr.Textbox(
                            label="Confirm Password",
                            placeholder="Confirm your password",
                            type="password",
                            max_lines=1
                        )
                        register_btn = gr.Button("Register", variant="secondary")
                        register_message = gr.Markdown("")
            
            # Login event handler
            def handle_login(username, password):
                success, message, token = self.login(username, password)
                
                if success:
                    return {
                        login_message: f"✅ {message}",
                        auth_token: token,
                        auth_success: "true"
                    }
                else:
                    return {
                        login_message: f"❌ {message}",
                        auth_token: "",
                        auth_success: "false"
                    }
            
            # Register event handler
            def handle_register(username, email, password, confirm_password):
                success, message = self.register(username, email, password, confirm_password)
                
                if success:
                    return f"✅ {message}"
                else:
                    return f"❌ {message}"
            
            # Bind events
            login_btn.click(
                fn=handle_login,
                inputs=[login_username, login_password],
                outputs=[login_message, auth_token, auth_success]
            )
            
            register_btn.click(
                fn=handle_register,
                inputs=[reg_username, reg_email, reg_password, reg_confirm_password],
                outputs=[register_message]
            )
            
            # Store components for external access
            auth_interface.auth_token = auth_token
            auth_interface.auth_success = auth_success
            auth_interface.login_message = login_message
        
        return auth_interface
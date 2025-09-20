"""
Main Gradio interface combining authentication and chat
"""
import gradio as gr
from typing import Tuple

from app.ui.auth_interface import AuthInterface
from app.ui.chat_interface import ChatInterface
from app.ui.history_interface import HistoryInterface
from app.ui.credits_interface import CreditsInterface
from app.ui.admin_interface import AdminInterface
from config import settings


class MainInterface:
    """Main application interface"""
    
    def __init__(self, api_base_url: str = None):
        self.api_base_url = api_base_url or f"http://{settings.host}:{settings.port}"
        self.auth_interface = AuthInterface(self.api_base_url)
        self.chat_interface = ChatInterface(self.api_base_url)
        self.history_interface = HistoryInterface(self.api_base_url)
        self.credits_interface = CreditsInterface(self.api_base_url)
        self.admin_interface = AdminInterface(self.api_base_url)
    
    def create_main_interface(self) -> gr.Blocks:
        """Create the main application interface"""
        
        with gr.Blocks(
            title="ML Chat Service",
            theme=gr.themes.Soft(),
            css="""
            .gradio-container {
                max-width: 1200px !important;
            }
            .auth-container {
                max-width: 500px;
                margin: 0 auto;
            }
            """
        ) as main_app:
            
            # Application state
            app_state = gr.State({"authenticated": False, "token": None, "user": None})
            
            # Create interfaces (wrap auth in a toggleable container)
            with gr.Group(visible=True) as auth_container:
                auth_ui = self.auth_interface.create_auth_interface()
            
            # Main application tabs (initially hidden)
            with gr.Tabs(visible=False) as main_tabs:
                with gr.Tab("💬 Chat"):
                    chat_ui = self.chat_interface.create_chat_interface()
                
                with gr.Tab("💰 Credits"):
                    credits_ui = self.credits_interface.create_interface()
                
                with gr.Tab("📊 History & Analytics"):
                    history_ui = self.history_interface.create_interface()
                
                with gr.Tab("🔧 Admin Panel"):
                    admin_ui = self.admin_interface.create_interface()
            
            # Initially show auth interface (auth_container visible by default)
            
            def handle_authentication_success(auth_success, token, current_state):
                """Handle successful authentication"""
                if auth_success == "true" and token:
                    # Get user info
                    user_info = self.auth_interface.get_user_info(token)
                    
                    # Update state
                    new_state = {
                        "authenticated": True,
                        "token": token,
                        "user": user_info
                    }
                    
                    # Set auth for interfaces
                    self.chat_interface.set_auth(token, user_info)
                    self.history_interface.set_auth(token)
                    self.credits_interface.set_auth(token, user_info)
                    self.admin_interface.set_auth(token)
                    
                    return {
                        auth_container: gr.update(visible=False),
                        main_tabs: gr.update(visible=True),
                        app_state: new_state
                    }
                
                return {
                    auth_container: gr.update(visible=True),
                    main_tabs: gr.update(visible=False),
                    app_state: current_state
                }
            
            def handle_logout(current_state):
                """Handle user logout"""
                new_state = {"authenticated": False, "token": None, "user": None}
                
                return {
                    auth_container: gr.update(visible=True),
                    main_tabs: gr.update(visible=False),
                    app_state: new_state
                }
            
            # Add logout button to main tabs
            with main_tabs:
                with gr.Row():
                    logout_btn = gr.Button("🚪 Logout", variant="secondary", size="sm")
            
            # Bind authentication events
            auth_ui.auth_success.change(
                fn=handle_authentication_success,
                inputs=[auth_ui.auth_success, auth_ui.auth_token, app_state],
                outputs=[auth_container, main_tabs, app_state]
            )

            # Also trigger on token change to ensure tabs reveal reliably after login
            auth_ui.auth_token.change(
                fn=handle_authentication_success,
                inputs=[auth_ui.auth_success, auth_ui.auth_token, app_state],
                outputs=[auth_container, main_tabs, app_state]
            )
            
            logout_btn.click(
                fn=handle_logout,
                inputs=[app_state],
                outputs=[auth_container, main_tabs, app_state]
            )
        
        return main_app
    
    def launch(self, **kwargs):
        """Launch the Gradio interface"""
        app = self.create_main_interface()
        
        # Default launch parameters
        launch_params = {
            "server_name": settings.host,
            "server_port": settings.port + 1,  # Use different port from FastAPI
            "share": False,
            "debug": settings.debug,
            "show_error": True,
            "quiet": False
        }
        
        # Override with provided parameters
        launch_params.update(kwargs)
        
        print(
            f"Launching Gradio interface on http://{launch_params['server_name']}:{launch_params['server_port']}"
        )
        print(
            f"API server should be running on http://{settings.host}:{settings.port}"
        )
        
        return app.launch(**launch_params)
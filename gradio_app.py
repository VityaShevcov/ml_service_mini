"""
Gradio application launcher
"""
import sys
import os

# Add the project root to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.ui.main_interface import MainInterface
from config import settings


def main():
    """Launch the Gradio interface"""
    print("🤖 ML Chat Service - Gradio Interface")
    print("=" * 50)
    
    # Create and launch interface
    interface = MainInterface()
    
    try:
        # Allow overriding port via env var GRADIO_SERVER_PORT, fallback to 7861
        port_str = os.getenv("GRADIO_SERVER_PORT")
        try:
            port = int(port_str) if port_str else 7861
        except ValueError:
            port = 7861
        interface.launch(
            share=False,
            debug=settings.debug,
            show_error=True,
            server_name="127.0.0.1",
            server_port=port,
            quiet=False
        )
    except KeyboardInterrupt:
        print("\n👋 Gradio interface stopped")
    except Exception as e:
        print(f"❌ Error launching Gradio interface: {e}")


if __name__ == "__main__":
    main()
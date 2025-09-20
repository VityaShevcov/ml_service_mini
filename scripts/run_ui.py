from app.ui.main_interface import MainInterface
from config import settings


def main() -> None:
    interface = MainInterface()
    # Avoid non-ASCII prints to prevent encoding issues on Windows consoles
    print(f"Launching Gradio interface on http://{settings.host}:{settings.port + 1}")
    print(f"API server should be running on http://{settings.host}:{settings.port}")
    interface.launch(server_name=settings.host, server_port=settings.port + 1, share=False, debug=settings.debug)


if __name__ == "__main__":
    main()



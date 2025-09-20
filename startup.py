#!/usr/bin/env python3
"""
Startup script for ML Chat Billing Service
Handles database initialization, model loading, and service startup
"""
import os
import sys
import asyncio
import logging
from pathlib import Path

# Add project root to Python path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from config import settings
from app.database import engine, get_db
from app.database import Base
from app.models import User
from app.models.crud import UserCRUD
from app.services.user_service import UserService
from app.utils.logging import get_logger


logger = get_logger(__name__)


class StartupManager:
    """Manages application startup and initialization"""
    
    def __init__(self):
        self.db_initialized = False
        self.models_loaded = False
        self.admin_created = False
    
    def initialize_database(self):
        """Initialize database and create tables"""
        try:
            logger.info("initializing_database")
            
            # Create all tables
            Base.metadata.create_all(bind=engine)
            
            self.db_initialized = True
            logger.info("database_initialized_successfully")
            
        except Exception as e:
            logger.error("database_initialization_failed", error=str(e))
            raise
    
    def create_admin_user(self):
        """Create default admin user if not exists"""
        try:
            logger.info("checking_admin_user")
            
            # Get database session
            db = next(get_db())
            
            # Check if admin user exists
            admin_user = UserCRUD.get_by_username(db, "admin")
            
            if not admin_user:
                logger.info("creating_admin_user")
                
                # Create admin user
                user_service = UserService(db)
                success, message, user = user_service.register_user(
                    username="admin",
                    email="admin@example.com",
                    password="Admin123!"  # Strong password with uppercase, number, special char
                )
                
                # Add extra credits for admin
                if success and user:
                    from app.services.billing_service import BillingService
                    billing_service = BillingService(db)
                    billing_service.add_credits(user.id, 9900, "Admin initial bonus credits")
                
                if success:
                    logger.info("admin_user_created", user_id=user.id)
                    self.admin_created = True
                else:
                    logger.error("admin_user_creation_failed", message=message)
            else:
                logger.info("admin_user_already_exists", user_id=admin_user.id)
                self.admin_created = True
            
            db.close()
            
        except Exception as e:
            logger.error("admin_user_setup_failed", error=str(e))
            raise
    
    def initialize_ml_models(self):
        """Initialize ML models (lazy loading)"""
        try:
            logger.info("initializing_ml_models")
            
            # Import ML service
            from app.ml.ml_service import MLService
            
            # Create ML service instance
            ml_service = MLService()
            
            # Initialize with lazy loading (don't actually load models yet)
            results = ml_service.initialize_models()
            
            if results:
                logger.info("ml_models_initialized", results=results)
                self.models_loaded = True
            else:
                logger.warning("ml_models_initialization_incomplete")
                self.models_loaded = False
            
        except Exception as e:
            logger.error("ml_models_initialization_failed", error=str(e))
            # Don't raise - ML models can be loaded on-demand
            self.models_loaded = False
    
    def check_environment(self):
        """Check environment variables and configuration"""
        try:
            logger.info("checking_environment")
            
            # Check required environment variables
            required_vars = [
                "DATABASE_URL",
                "SECRET_KEY",
                "JWT_SECRET_KEY"
            ]
            
            missing_vars = []
            for var in required_vars:
                if not os.getenv(var):
                    missing_vars.append(var)
            
            if missing_vars:
                logger.warning("missing_environment_variables", 
                             missing=missing_vars)
                print(f"⚠️  Missing environment variables: {', '.join(missing_vars)}")
                print("   Using default values from config.py")
            
            # Check database URL
            if settings.database_url == "sqlite:///./ml_chat_service.db":
                logger.info("using_sqlite_database")
                print("📁 Using SQLite database: ./ml_chat_service.db")
            else:
                logger.info("using_external_database", url=settings.database_url.split('@')[0])
            
            # Check debug mode
            if settings.debug:
                logger.warning("debug_mode_enabled")
                print("🐛 Debug mode is enabled")
            
            logger.info("environment_check_completed")
            
        except Exception as e:
            logger.error("environment_check_failed", error=str(e))
            raise
    
    def run_startup_sequence(self):
        """Run complete startup sequence"""
        try:
            print("🚀 Starting ML Chat Billing Service...")
            print("=" * 50)
            
            # Check environment
            print("1️⃣  Checking environment...")
            self.check_environment()
            
            # Initialize database
            print("2️⃣  Initializing database...")
            self.initialize_database()
            
            # Create admin user
            print("3️⃣  Setting up admin user...")
            self.create_admin_user()
            
            # Initialize ML models
            print("4️⃣  Initializing ML models...")
            self.initialize_ml_models()
            
            # Print startup summary
            self.print_startup_summary()
            
            return True
            
        except Exception as e:
            logger.error("startup_sequence_failed", error=str(e))
            print(f"❌ Startup failed: {str(e)}")
            return False
    
    def print_startup_summary(self):
        """Print startup summary"""
        print("\n" + "=" * 50)
        print("📊 Startup Summary:")
        print(f"   Database: {'✅' if self.db_initialized else '❌'}")
        print(f"   Admin User: {'✅' if self.admin_created else '❌'}")
        print(f"   ML Models: {'✅' if self.models_loaded else '⚠️  (Lazy Loading)'}")
        
        print(f"\n🌐 Service URLs:")
        print(f"   API Server: http://{settings.host}:{settings.port}")
        print(f"   Gradio UI: http://{settings.host}:{settings.port + 1}")
        print(f"   API Docs: http://{settings.host}:{settings.port}/docs")
        
        if self.admin_created:
            print(f"\n👤 Admin Credentials:")
            print(f"   Username: admin")
            print(f"   Email: admin@example.com")
            print(f"   Password: admin123")
            print(f"   ⚠️  Change password in production!")
        
        print("\n" + "=" * 50)


def start_api_server():
    """Start the FastAPI server"""
    try:
        import uvicorn
        from main import app
        
        logger.info("starting_api_server", 
                   host=settings.host, 
                   port=settings.port)
        
        uvicorn.run(
            app,
            host=settings.host,
            port=settings.port,
            log_level="info" if settings.debug else "warning",
            reload=settings.debug
        )
        
    except Exception as e:
        logger.error("api_server_startup_failed", error=str(e))
        raise


def start_gradio_interface():
    """Start the Gradio interface"""
    try:
        from app.ui.main_interface import MainInterface
        
        logger.info("starting_gradio_interface")
        
        # Create and launch interface
        main_interface = MainInterface()
        main_interface.launch(
            server_name=settings.host,
            server_port=settings.port + 1,
            share=False,
            debug=settings.debug
        )
        
    except Exception as e:
        logger.error("gradio_interface_startup_failed", error=str(e))
        raise


def main():
    """Main startup function"""
    import argparse
    
    parser = argparse.ArgumentParser(description="ML Chat Billing Service Startup")
    parser.add_argument("--mode", choices=["api", "ui", "both"], default="both",
                       help="Service mode to start")
    parser.add_argument("--skip-init", action="store_true",
                       help="Skip initialization steps")
    
    args = parser.parse_args()
    
    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    
    # Run startup sequence unless skipped
    if not args.skip_init:
        startup_manager = StartupManager()
        if not startup_manager.run_startup_sequence():
            sys.exit(1)
    
    # Start services based on mode
    if args.mode == "api":
        print("🚀 Starting API server only...")
        start_api_server()
    
    elif args.mode == "ui":
        print("🚀 Starting Gradio UI only...")
        start_gradio_interface()
    
    elif args.mode == "both":
        print("🚀 Starting both API server and Gradio UI...")
        
        # Start API server in background
        import threading
        api_thread = threading.Thread(target=start_api_server, daemon=True)
        api_thread.start()
        
        # Give API server time to start
        import time
        time.sleep(2)
        
        # Start Gradio interface (blocking)
        start_gradio_interface()


if __name__ == "__main__":
    main()
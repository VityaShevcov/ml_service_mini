#!/usr/bin/env python3
"""
Script to reorganize project structure
"""
import os
import shutil

def reorganize_project():
    """Reorganize test files and clean up structure"""

    # Создать папки
    os.makedirs('tests/integration', exist_ok=True)
    os.makedirs('tests/scripts', exist_ok=True)

    print("📁 Creating directories...")

    # Список файлов для перемещения в integration
    integration_files = [
        'test_api_basic.py',
        'test_chat_basic.py',
        'test_endpoints.py',
        'test_gradio.py',
        'test_ml_basic.py',
        'test_ml_service.py'
    ]

    # Список файлов для перемещения в scripts
    scripts_files = [
        'scripts/test_model_loader.py'
    ]

    print("🔄 Moving integration test files...")
    # Переместить файлы в integration
    for file in integration_files:
        if os.path.exists(file):
            shutil.move(file, f'tests/integration/{file}')
            print(f"  ✅ Moved {file} to tests/integration/")

    print("🔄 Moving script files...")
    # Переместить файлы в scripts
    for file in scripts_files:
        if os.path.exists(file):
            shutil.move(file, f'tests/scripts/{os.path.basename(file)}')
            print(f"  ✅ Moved {file} to tests/scripts/")

    print("🗑️ Cleaning up...")
    # Удалить пустую папку scripts если она есть
    if os.path.exists('scripts') and not os.listdir('scripts'):
        os.rmdir('scripts')
        print("  ✅ Removed empty scripts directory")

    print("✅ Project reorganization completed!")

    # Показать новую структуру
    print("\n📂 New project structure:")
    for root, dirs, files in os.walk('.'):
        level = root.replace('.', '').count(os.sep)
        indent = ' ' * 2 * level
        print(f'{indent}{os.path.basename(root)}/')
        subindent = ' ' * 2 * (level + 1)
        for file in files[:5]:  # Первые 5 файлов
            print(f'{subindent}{file}')
        if len(files) > 5:
            print(f'{subindent}... ({len(files)} files total)')

if __name__ == "__main__":
    reorganize_project()

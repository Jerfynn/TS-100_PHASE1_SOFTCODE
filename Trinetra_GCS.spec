# -*- mode: python ; coding: utf-8 -*-
import sys
import os

block_cipher = None

src_dir = os.path.join(os.path.abspath('.'), 'src')

added_files = [
    (os.path.join(src_dir, '*.html'), 'src'),
    (os.path.join(src_dir, '*.png'), 'src'),
    (os.path.join(src_dir, '*.json'), 'src'),
    (os.path.join(src_dir, 'assets', '*.png'), 'src/assets'),
    (os.path.join(src_dir, 'pages', '*.py'), 'src/pages'),
    ('app_icon.ico', '.'),
]

hidden_imports = [
    'PySide6.QtCore',
    'PySide6.QtGui',
    'PySide6.QtWidgets',
    'PySide6.QtWebEngineWidgets',
    'PySide6.QtWebEngineCore',
    'PySide6.QtNetwork',
    'PySide6.QtSvg',
    'PySide6.QtSvgWidgets',
    'PySide6.QtOpenGL',
    'PySide6.QtOpenGLWidgets',
    'pygame',
    'serial',
    'serial.tools',
    'serial.tools.list_ports',
    'socket',
    'json',
    'math',
    'threading',
    'time',
    'hashlib',
    'hmac',
    'ast',
    'winsound',
    'src',
    'src.app',
    'src.widgets',
    'src.connection',
    'src.styles',
    'src.crypto_link',
    'src.pages',
    'src.pages.earth_page',
    'src.pages.plan_page',
    'src.pages.settings_page',
    'src.pages.setup_page',
]

a = Analysis(
    ['main.py'],
    pathex=['.'],
    binaries=[],
    datas=added_files,
    hiddenimports=hidden_imports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'tkinter', 'matplotlib', 'scipy', 'torch', 'torchvision', 
        'pandas', 'openpyxl', 'jupyter', 'IPython', 'notebook', 
        'mediapipe', 'sympy', 'fastapi', 'uvicorn'
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='Trinetra_GCS',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='app_icon.ico',
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name='Trinetra_GCS',
)

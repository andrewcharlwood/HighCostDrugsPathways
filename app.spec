# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for NHS Pathway Analysis desktop app."""

import os

block_cipher = None

# Project root (where this spec file lives)
ROOT = os.path.abspath(os.path.dirname(SPECPATH)) if 'SPECPATH' in dir() else os.path.abspath('.')

a = Analysis(
    ['app_desktop.py'],
    pathex=[os.path.join(ROOT, 'src')],
    binaries=[],
    datas=[
        ('data/pathways.db', 'data'),
        ('data/DimSearchTerm.csv', 'data'),
        ('data/defaultTrusts.csv', 'data'),
        ('dash_app/assets/nhs.css', 'dash_app/assets'),
    ],
    hiddenimports=[
        # Dash internals
        'dash',
        'dash.dash',
        'dash.dcc',
        'dash.html',
        'dash.exceptions',
        'dash._utils',
        'dash.dependencies',
        'dash_mantine_components',
        # Plotly
        'plotly',
        'plotly.graph_objects',
        'plotly.io',
        'plotly.express',
        'plotly.subplots',
        # Data
        'pandas',
        'pandas._libs.tslibs',
        'numpy',
        'sqlite3',
        # App packages (src/ on pathex)
        'core',
        'core.config',
        'core.models',
        'core.logging_config',
        'core.resource_path',
        'data_processing',
        'data_processing.database',
        'data_processing.schema',
        'data_processing.pathway_queries',
        'data_processing.parsing',
        'data_processing.diagnosis_lookup',
        'analysis',
        'analysis.pathway_analyzer',
        'analysis.statistics',
        'visualization',
        'visualization.plotly_generator',
        # Dash app
        'dash_app',
        'dash_app.app',
        'dash_app.data',
        'dash_app.data.queries',
        'dash_app.data.card_browser',
        'dash_app.callbacks',
        'dash_app.callbacks.filters',
        'dash_app.callbacks.chart',
        'dash_app.callbacks.modals',
        'dash_app.callbacks.navigation',
        'dash_app.callbacks.trust_comparison',
        'dash_app.callbacks.kpi',
        'dash_app.callbacks.trends',
        'dash_app.components',
        'dash_app.components.header',
        'dash_app.components.sub_header',
        'dash_app.components.sidebar',
        'dash_app.components.filter_bar',
        'dash_app.components.chart_card',
        'dash_app.components.footer',
        'dash_app.components.modals',
        'dash_app.components.trust_comparison',
        'dash_app.components.trends',
        # pywebview backend
        'webview',
        'clr',
        'pythonnet',
        # Flask (Dash's server)
        'flask',
        'flask.json',
        'flask.json.provider',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'snowflake',
        'snowflake.connector',
        'cli',
        'pytest',
        'tests',
        'tkinter',
        'matplotlib',
        'IPython',
        'jupyter',
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
    name='NHS_Pathway_Analysis',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,  # --windowed (no console)
    icon=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='NHS_Pathway_Analysis',
)

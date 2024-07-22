from cx_Freeze import setup, Executable

base = None

target = Executable(
    script="app.py",
    icon="icon.ico",
    base=base
)

setup(
    name="CYCU-iLearning-Score-Analyzer",
    version="1.0",
    description="cycu-ilearning-score-analyzer",
    author="MO7YW4NG",
    options={'build_exe': {
        'packages': ['aiohttp','getpass','os','hashlib','base64','asyncio','Crypto','bs4','rich'],
        'include_files': ['icon.ico']
    },'bdist_msi': {'initial_target_dir': r'[DesktopFolder]\\CYCU-iLearning-Score-Analyzer'},
      'bdist_mac': {
            'bundle_name': 'CYCU-iLearning-Score-Analyzer',
            'iconfile': 'icon.ico',
        },},
    executables=[target],
)

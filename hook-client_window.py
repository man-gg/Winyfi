# PyInstaller hook for client_window package
# This helps PyInstaller find all the submodules

from PyInstaller.utils.hooks import collect_submodules, collect_data_files

# Collect all submodules from client_window
hiddenimports = collect_submodules('client_window')
hiddenimports += collect_submodules('client_window.tabs')

# Collect any data files if needed
datas = collect_data_files('client_window', include_py_files=True)

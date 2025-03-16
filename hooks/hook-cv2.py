from PyInstaller.utils.hooks import collect_dynamic_libs

# 自动包含所有OpenCV的DLL
binaries = collect_dynamic_libs('cv2')
hiddenimports = ['numpy.core.multiarray']

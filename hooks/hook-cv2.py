# hooks/hook-cv2.py
from PyInstaller.utils.hooks import collect_dynamic_libs, collect_data_files

# 包含所有OpenCV的DLL
binaries = collect_dynamic_libs('cv2')

# 包含所有NumPy的隐藏依赖
hiddenimports = [
    'numpy.core._multiarray_umath',
    'numpy.core._dtype_ctypes',
    'numpy.core._methods'
]

# 包含NumPy的二进制文件
datas = collect_data_files('numpy')

import common as c
from config import bitness, msvc_version, build_dir, dependencies_dir, build_type
import os
import platform

c.print('>> Installing tesseract')

install_dir = dependencies_dir
url = 'https://github.com/tesseract-ocr/tesseract/archive/5.1.0.tar.gz'
required_version = '5.1.0'

build_type_flag = 'Debug' if build_type == 'debug' else 'Release'

# compatibility flags
compat_flags = ''
compat_flags += ' -D DISABLE_LEGACY_ENGINE=ON '
compat_flags += ' -D DISABLE_ARCHIVE=ON '
compat_flags += ' -D DISABLE_CURL=ON '

version_tag = os.environ.get('TAG', '')
if version_tag == 'compatible':
    compat_flags += ' -D HAVE_AVX2=0 '
    compat_flags += ' -D HAVE_FMA=0 '

lib_suffix = version_tag
if len(lib_suffix) > 0:
    lib_suffix = '-' + lib_suffix

cache_file = install_dir + '/tesseract{}.cache'.format(lib_suffix)
cache_file_data = required_version + build_type_flag

def check_existing():
    if not os.path.exists(cache_file):
        return False
    with open(cache_file, 'r') as f:
        cached = f.read()
        if cached != cache_file_data:
            return False

    includes_path = install_dir + '/include/tesseract'
    if len(c.get_folder_files(includes_path)) == 0:
        return False

    if platform.system() == "Windows":
        lib = install_dir + '/bin/tesseract{}.dll'.format(lib_suffix)
        orig_lib = install_dir + '/bin/tesseract51.dll'
    elif platform.system() == "Darwin":
        lib = install_dir + '/lib/libtesseract{}.dylib'.format(lib_suffix)
        orig_lib = install_dir + '/lib/libtesseract.{}.dylib'.format(required_version)
    else:
        lib = install_dir + '/lib/libtesseract{}.so'.format(lib_suffix)
        orig_lib = install_dir + '/lib/libtesseract.so.{}'.format(required_version)

    if os.path.exists(lib):
        return True
    if os.path.exists(orig_lib):
        os.rename(orig_lib, lib)
        return True

    return False


if check_existing() and not 'FORCE' in os.environ:
    c.print('>> Using cached')
    exit(0)

archive = 'tesseract-' + os.path.basename(url)
c.download(url, archive)

src_dir = os.path.abspath('tesseract_src')
c.extract(archive, '.')
c.symlink(c.get_archive_top_dir(archive), src_dir)

if platform.system() == "Windows":
    # workaround for not found 'max'
    modify_data = ''
    modify_file = '{}/src/ccmain/thresholder.cpp'.format(src_dir)
    with open(modify_file, 'r') as f:
        modify_data = f.read()

    if modify_data.find('<algorithm>') == -1:
        modify_data = modify_data.replace(
        '''<tuple>''',
        '''<tuple>\n#include <algorithm>''')

    with open(modify_file, 'w') as f:
        f.write(modify_data)

    # ignore libtiff
    modify_data = ''
    modify_file = '{}/CMakeLists.txt'.format(src_dir)
    with open(modify_file, 'r') as f:
        modify_data = f.read()

    if modify_data.find('#pkg_check_modules(TIFF libtiff-4)') == -1:
        modify_data = modify_data.replace(
        '''pkg_check_modules(TIFF libtiff-4)''',
        '''#pkg_check_modules(TIFF libtiff-4)''')

    with open(modify_file, 'w') as f:
        f.write(modify_data)

if platform.system() == "Linux":
    # FIXME fix crash on ubuntu
    modify_data = ''
    modify_file = '{}/src/ccmain/tessedit.cpp'.format(src_dir)
    with open(modify_file, 'r') as f:
        modify_data = f.read()

    lines = modify_data.split('\n')
    for line in [250,253,255,256]:
        if not lines[line].startswith('//'):
            lines[line] = '// ' + lines[line]
    modify_data = '\n'.join(lines)

    with open(modify_file, 'w') as f:
        f.write(modify_data)



c.ensure_got_path(install_dir)

c.recreate_dir(build_dir)
os.chdir(build_dir)

cmake_args = '"{0}" -DCMAKE_INSTALL_PREFIX="{1}" -DLeptonica_DIR="{1}/cmake" \
-DBUILD_TRAINING_TOOLS=OFF -DBUILD_TESTS=OFF -DBUILD_SHARED_LIBS=ON -DSW_BUILD=OFF \
'.format(src_dir, install_dir)

if platform.system() == "Windows":
    env_cmd = c.get_msvc_env_cmd(bitness=bitness, msvc_version=msvc_version)
    c.apply_cmd_env(env_cmd)
    cmake_args += ' ' + c.get_cmake_arch_args(bitness=bitness)

c.set_make_threaded()
c.run('cmake {}'.format(cmake_args))

if len(compat_flags) > 0:
    c.run('cmake {} .'.format(compat_flags))
    c.run('cmake {} .'.format(compat_flags))  # for sure :)

c.run('cmake --build . --config {}'.format(build_type_flag))
c.run('cmake --build . --target install --config {}'.format(build_type_flag))

with open(cache_file, 'w') as f:
    f.write(cache_file_data)

if not check_existing():  # add suffix
    c.print('>> Build failed')
    exit(1)

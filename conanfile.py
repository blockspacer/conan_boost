import glob
import os
import sys
import shutil

from conans import ConanFile
from conans import tools
from conans.client.build.cppstd_flags import cppstd_flag
from conans.tools import Version
from conans.errors import ConanException
from conans.model.version import Version
from conans.errors import ConanInvalidConfiguration

from conans import ConanFile, CMake, tools, AutoToolsBuildEnvironment, RunEnvironment, python_requires
from conans.errors import ConanInvalidConfiguration, ConanException
from conans.tools import os_info
import os, re, stat, fnmatch, platform, glob, traceback, shutil
from functools import total_ordering

# if you using python less than 3 use from distutils import strtobool
from distutils.util import strtobool

conan_build_helper = python_requires("conan_build_helper/[~=0.0]@conan/stable")

try:
    from cStringIO import StringIO
except ImportError:
    from io import StringIO

# From from *1 (see below, b2 --show-libraries), also ordered following linkage order
# see https://github.com/Kitware/CMake/blob/master/Modules/FindBoost.cmake to know the order

lib_list = ['math', 'wave', 'container', 'contract', 'exception', 'graph', 'iostreams', 'locale', 'log',
            'program_options', 'random', 'regex', 'mpi', 'serialization',
            'coroutine', 'fiber', 'context', 'timer', 'thread', 'chrono', 'date_time',
            'atomic', 'filesystem', 'system', 'graph_parallel', 'python',
            'stacktrace', 'test', 'type_erasure']

# Users locally they get the 1.0.0 version,
# without defining any env-var at all,
# and CI servers will append the build number.
# USAGE
# version = get_version("1.0.0")
# BUILD_NUMBER=-pre1+build2 conan export-pkg . my_channel/release
def get_version(version):
    bn = os.getenv("BUILD_NUMBER")
    return (version + bn) if bn else version

class BoostConan(conan_build_helper.CMakePackage):
    name = "boost"
    settings = "os", "arch", "compiler", "build_type"
    description = "Boost provides free peer-reviewed portable C++ source libraries"
    url = "https://github.com/conan-io/conan-center-index"
    homepage = "https://www.boost.org"
    license = "BSL-1.0"
    topics = ("conan", "boost", "libraries", "cpp")
    version = get_version("1.71.0")
    # The current python option requires the package to be built locally, to find default Python
    # implementation
    options = {
        "enable_ubsan": [True, False],
        "enable_asan": [True, False],
        "enable_msan": [True, False],
        "enable_tsan": [True, False],
        "shared": [True, False],
        "header_only": [True, False],
        "error_code_header_only": [True, False],
        "system_no_deprecated": [True, False],
        "asio_no_deprecated": [True, False],
        "filesystem_no_deprecated": [True, False],
        "no_rtti": [True, False],
        "no_exceptions": [True, False],
        "fPIC": [True, False],
        "layout": ["system", "versioned", "tagged"],
        "magic_autolink": [True, False],  # enables BOOST_ALL_NO_LIB
        "python_executable": "ANY",  # system default python installation is used, if None
        "python_version": "ANY",  # major.minor; computed automatically, if None
        "namespace": "ANY",  # custom boost namespace for bcp, e.g. myboost
        "namespace_alias": [True, False],  # enable namespace alias for bcp, boost=myboost
        "zlib": [True, False],
        "bzip2": [True, False],
        "lzma": [True, False],
        "zstd": [True, False],
        "segmented_stacks": [True, False],
        "debug_level": [i for i in range(1, 14)],
        "pch": [True, False],
        "without_ctest": [True, False],
        "extra_b2_flags": "ANY"  # custom b2 flags
    }
    options.update({"without_%s" % libname: [True, False] for libname in lib_list})

    default_options = {
        "enable_ubsan": False,
        "enable_asan": False,
        "enable_msan": False,
        "enable_tsan": False,
        'shared': False,
        'header_only': False,
        'error_code_header_only': False,
        'system_no_deprecated': False,
        'asio_no_deprecated': False,
        'filesystem_no_deprecated': False,
        "no_rtti": False,
        "no_exceptions": True,
        'fPIC': True,
        'layout': 'system',
        'magic_autolink': False,
        'python_executable': 'None',
        'python_version': 'None',
        'namespace': 'boost',
        'namespace_alias': False,
        'zlib': False,
        'bzip2': False,
        'lzma': False,
        'zstd': False,
        'segmented_stacks': False,
        "debug_level": 2,
        'pch': True,
        "without_ctest": True,
        'extra_b2_flags': 'None',
    }

    for libname in lib_list:
        if libname != "python" \
           and libname != "coroutine" \
           and libname != "math" \
           and libname != "wave" \
           and libname != "contract" \
           and libname != "locale" \
           and libname != "random" \
           and libname != "regex" \
           and libname != "mpi" \
           and libname != "timer" \
           and libname != "thread" \
           and libname != "chrono" \
           and libname != "atomic" \
           and libname != "system" \
           and libname != "stacktrace" \
           and libname != "program_options" \
           and libname != "serialization" \
           and libname != "log" \
           and libname != "type_erasure" \
           and libname != "test" \
           and libname != "graph" \
           and libname != "graph_parallel" \
           and libname != "iostreams" \
           and libname != "context" \
           and libname != "fiber" \
           and libname != "filesystem" \
           and libname != "date_time" \
           and libname != "exception" \
           and libname != "container":
            default_options.update({"without_%s" % libname: False})
            print('without_{} is False'.format(libname))

    default_options.update({"without_python": True})
    default_options.update({"without_coroutine": True})
    default_options.update({"without_stacktrace": True})
    default_options.update({"without_math": True})
    default_options.update({"without_wave": True})
    default_options.update({"without_contract": True})
    default_options.update({"without_locale": True})
    default_options.update({"without_random": True})
    default_options.update({"without_regex": True})
    default_options.update({"without_mpi": True})
    default_options.update({"without_timer": True})
    default_options.update({"without_thread": True})
    default_options.update({"without_chrono": True})
    default_options.update({"without_atomic": True})
    default_options.update({"without_system": True})

    # requires exceptions
    default_options.update({"without_program_options": True})
    # requires exceptions
    default_options.update({"without_serialization": True})
    # requires exceptions
    default_options.update({"without_log": True})
    # requires exceptions
    default_options.update({"without_type_erasure": True})
    # requires exceptions
    default_options.update({"without_test": True})
    # requires rtti
    default_options.update({"without_graph": True})
    default_options.update({"without_graph_parallel": True})
    # requires exceptions
    default_options.update({"without_iostreams": True})
    # requires exceptions
    default_options.update({"without_context": True})
    # requires exceptions
    default_options.update({"without_fiber": True})
    # requires exceptions
    default_options.update({"without_filesystem": True})
    # requires exceptions
    default_options.update({"without_date_time": True})
    # requires exceptions
    default_options.update({"without_exception": True})
    # requires rtti
    default_options.update({"without_container": True})

    # TODO
    # requires rtti
    #default_options.update({"without_xpressive": True})
    # requires rtti
    #default_options.update({"without_property_map": True})
    # requires rtti
    #default_options.update({"without_property_tree": True})

    short_paths = True
    no_copy_source = True
    exports_sources = ['patches/*']

    # sets cmake variables required to use clang 10 from conan
    def _is_compile_with_llvm_tools_enabled(self):
      return self._environ_option("COMPILE_WITH_LLVM_TOOLS", default = 'false')

    # installs clang 10 from conan
    def _is_llvm_tools_enabled(self):
      return self._environ_option("ENABLE_LLVM_TOOLS", default = 'false')

    @property
    def _bcp_dir(self):
        return "custom-boost"

    @property
    def _folder_name(self):
        return "boost_%s" % self.version.replace(".", "_")

    @property
    def _is_msvc(self):
        return self.settings.compiler == "Visual Studio"

    @property
    def _zip_bzip2_requires_needed(self):
        return not self.options.without_iostreams and not self.options.header_only

    @property
    def _python_executable(self):
        """
        obtain full path to the python interpreter executable
        :return: path to the python interpreter executable, either set by option, or system default
        """
        exe = self.options.python_executable if self.options.python_executable else sys.executable
        return str(exe).replace('\\', '/')

    def configure(self):
        lower_build_type = str(self.settings.build_type).lower()

        if lower_build_type != "release" and not self._is_llvm_tools_enabled():
            self.output.warn('enable llvm_tools for Debug builds')

        if self._is_compile_with_llvm_tools_enabled() and not self._is_llvm_tools_enabled():
            raise ConanInvalidConfiguration("llvm_tools must be enabled")

        if self.options.enable_ubsan \
           or self.options.enable_asan \
           or self.options.enable_msan \
           or self.options.enable_tsan:
            if not self._is_llvm_tools_enabled():
                raise ConanInvalidConfiguration("sanitizers require llvm_tools")

    def config_options(self):
        if self.settings.os == "Windows":
            del self.options.fPIC

    def build_requirements(self):
        self.build_requires("b2/4.2.0")

        # provides clang-tidy, clang-format, IWYU, scan-build, etc.
        if self._is_llvm_tools_enabled():
          self.build_requires("llvm_tools/master@conan/stable")

    def requirements(self):
        if self._zip_bzip2_requires_needed:
            if self.options.zlib:
                # requires openssl
                # TODO: use self.requires("chromium_zlib/master@conan/stable")
                self.requires("zlib/v1.2.11@conan/stable")
            if self.options.bzip2:
                # patched version
                self.requires("bzip2/1.0.8@dev/stable")
            if self.options.lzma:
                self.requires("xz_utils/5.2.4")
            if self.options.zstd:
                self.requires("zstd/1.4.3")

    def package_id(self):
        if self.options.header_only:
            self.info.header_only()
            self.info.options.header_only = True
        else:
            del self.info.options.debug_level
            del self.info.options.pch
            del self.info.options.python_executable  # PATH to the interpreter is not important, only version matters
            if self.options.without_python:
                del self.info.options.python_version
            else:
                self.info.options.python_version = self._python_version

    def source(self):
        tools.get(**self.conan_data["sources"][self.version])
        if self.version in self.conan_data["patches"]:
            for patch in self.conan_data["patches"][self.version]:
                tools.patch(**patch)

    ##################### BUILDING METHODS ###########################

    def _run_python_script(self, script):
        """
        execute python one-liner script and return its output
        :param script: string containing python script to be executed
        :return: output of the python script execution, or None, if script has failed
        """
        output = StringIO()
        command = '"%s" -c "%s"' % (self._python_executable, script)
        self.output.info('running %s' % command)
        try:
            self.run(command=command, output=output)
        except ConanException:
            self.output.info("(failed)")
            return None
        output = output.getvalue().strip()
        self.output.info(output)
        return output if output != "None" else None

    def _get_python_path(self, name):
        """
        obtain path entry for the python installation
        :param name: name of the python config entry for path to be queried (such as "include", "platinclude", etc.)
        :return: path entry from the sysconfig
        """
        # https://docs.python.org/3/library/sysconfig.html
        # https://docs.python.org/2.7/library/sysconfig.html
        return self._run_python_script("from __future__ import print_function; "
                                       "import sysconfig; "
                                       "print(sysconfig.get_path('%s'))" % name)

    def _get_python_sc_var(self, name):
        """
        obtain value of python sysconfig variable
        :param name: name of variable to be queried (such as LIBRARY or LDLIBRARY)
        :return: value of python sysconfig variable
        """
        return self._run_python_script("from __future__ import print_function; "
                                       "import sysconfig; "
                                       "print(sysconfig.get_config_var('%s'))" % name)

    def _get_python_du_var(self, name):
        """
        obtain value of python distutils sysconfig variable
        (sometimes sysconfig returns empty values, while python.sysconfig provides correct values)
        :param name: name of variable to be queried (such as LIBRARY or LDLIBRARY)
        :return: value of python sysconfig variable
        """
        return self._run_python_script("from __future__ import print_function; "
                                       "import distutils.sysconfig as du_sysconfig; "
                                       "print(du_sysconfig.get_config_var('%s'))" % name)

    def _get_python_var(self, name):
        """
        obtain value of python variable, either by sysconfig, or by distutils.sysconfig
        :param name: name of variable to be queried (such as LIBRARY or LDLIBRARY)
        :return: value of python sysconfig variable
        """
        return self._get_python_sc_var(name) or self._get_python_du_var(name)

    @property
    def _python_version(self):
        """
        obtain version of python interpreter
        :return: python interpreter version, in format major.minor
        """
        version = self._run_python_script("from __future__ import print_function; "
                                          "import sys; "
                                          "print('%s.%s' % (sys.version_info[0], sys.version_info[1]))")
        if self.options.python_version and version != self.options.python_version:
            raise ConanInvalidConfiguration("detected python version %s doesn't match conan option %s" % (version,
                                                                                          self.options.python_version))
        return version

    @property
    def _python_inc(self):
        """
        obtain the result of the "sysconfig.get_python_inc()" call
        :return: result of the "sysconfig.get_python_inc()" execution
        """
        return self._run_python_script("from __future__ import print_function; "
                                       "import sysconfig; "
                                       "print(sysconfig.get_python_inc())")

    @property
    def _python_abiflags(self):
        """
        obtain python ABI flags, see https://www.python.org/dev/peps/pep-3149/ for the details
        :return: the value of python ABI flags
        """
        return self._run_python_script("from __future__ import print_function; "
                                       "import sys; "
                                       "print(getattr(sys, 'abiflags', ''))")

    @property
    def _python_includes(self):
        """
        attempt to find directory containing Python.h header file
        :return: the directory with python includes
        """
        include = self._get_python_path('include')
        plat_include = self._get_python_path('platinclude')
        include_py = self._get_python_var('INCLUDEPY')
        include_dir = self._get_python_var('INCLUDEDIR')
        python_inc = self._python_inc

        candidates = [include,
                      plat_include,
                      include_py,
                      include_dir,
                      python_inc]
        for candidate in candidates:
            if candidate:
                python_h = os.path.join(candidate, 'Python.h')
                self.output.info('checking %s' % python_h)
                if os.path.isfile(python_h):
                    self.output.info('found Python.h: %s' % python_h)
                    return candidate.replace('\\', '/')
        raise Exception("couldn't locate Python.h - make sure you have installed python development files")

    @property
    def _python_libraries(self):
        """
        attempt to find python development library
        :return: the full path to the python library to be linked with
        """
        library = self._get_python_var("LIBRARY")
        ldlibrary = self._get_python_var("LDLIBRARY")
        libdir = self._get_python_var("LIBDIR")
        multiarch = self._get_python_var("MULTIARCH")
        masd = self._get_python_var("multiarchsubdir")
        with_dyld = self._get_python_var("WITH_DYLD")
        if libdir and multiarch and masd:
            if masd.startswith(os.sep):
                masd = masd[len(os.sep):]
            libdir = os.path.join(libdir, masd)

        if not libdir:
            libdest = self._get_python_var("LIBDEST")
            libdir = os.path.join(os.path.dirname(libdest), "libs")

        candidates = [ldlibrary, library]
        library_prefixes = [""] if self._is_msvc else ["", "lib"]
        library_suffixes = [".lib"] if self._is_msvc else [".so", ".dll.a", ".a"]
        if with_dyld:
            library_suffixes.insert(0, ".dylib")

        python_version = self._python_version
        python_version_no_dot = python_version.replace(".", "")
        versions = ["", python_version, python_version_no_dot]
        abiflags = self._python_abiflags

        for prefix in library_prefixes:
            for suffix in library_suffixes:
                for version in versions:
                    candidates.append("%spython%s%s%s" % (prefix, version, abiflags, suffix))

        for candidate in candidates:
            if candidate:
                python_lib = os.path.join(libdir, candidate)
                self.output.info('checking %s' % python_lib)
                if os.path.isfile(python_lib):
                    self.output.info('found python library: %s' % python_lib)
                    return python_lib.replace('\\', '/')
        raise ConanInvalidConfiguration("couldn't locate python libraries - make sure you have installed python development files")

    def _clean(self):
        src = os.path.join(self.source_folder, self._folder_name)
        clean_dirs = [os.path.join(self.build_folder, "bin.v2"),
                      os.path.join(self.build_folder, "architecture"),
                      os.path.join(self.source_folder, self._bcp_dir),
                      os.path.join(src, "dist", "bin"),
                      os.path.join(src, "stage"),
                      os.path.join(src, "tools", "build", "src", "engine", "bootstrap"),
                      os.path.join(src, "tools", "build", "src", "engine", "bin.ntx86"),
                      os.path.join(src, "tools", "build", "src", "engine", "bin.ntx86_64")]
        for d in clean_dirs:
            if os.path.isdir(d):
                self.output.warn('removing "%s"' % d)
                shutil.rmtree(d)

    @property
    def _b2_exe(self):
        b2_exe = "b2.exe" if tools.os_info.is_windows else "b2"
        return os.path.join(self.deps_cpp_info["b2"].rootpath, "bin", b2_exe)

    @property
    def _bcp_exe(self):
        folder = os.path.join(self.source_folder, self._folder_name, "dist", "bin")
        return os.path.join(folder, "bcp.exe" if tools.os_info.is_windows else "bcp")

    @property
    def _use_bcp(self):
        return self.options.namespace != "boost"

    @property
    def _boost_dir(self):
        return self._bcp_dir if self._use_bcp else self._folder_name

    @property
    def _boost_build_dir(self):
        return os.path.join(self.source_folder, self._folder_name, "tools", "build")

    def _build_bcp(self):
        folder = os.path.join(self.source_folder, self._folder_name, 'tools', 'bcp')
        with tools.vcvars(self.settings) if self._is_msvc else tools.no_op():
            with tools.chdir(folder):
                command = "%s -j%s --abbreviate-paths -d2 toolset=%s" % (self._b2_exe, tools.cpu_count(), self._toolset)
                self.output.warn(command)
                self.run(command)

    def _run_bcp(self):
        with tools.vcvars(self.settings) if self._is_msvc else tools.no_op():
            with tools.chdir(self.source_folder):
                os.mkdir(self._bcp_dir)
                namespace = "--namespace=%s" % self.options.namespace
                alias = "--namespace-alias" if self.options.namespace_alias else ""
                boostdir = "--boost=%s" % self._folder_name
                libraries = {"build", "boost-build.jam", "boostcpp.jam", "boost_install", "headers"}
                for d in os.listdir(os.path.join(self._folder_name, "boost")):
                    if os.path.isdir(os.path.join(self._folder_name, "boost", d)):
                        libraries.add(d)
                for d in os.listdir(os.path.join(self._folder_name, "libs")):
                    if os.path.isdir(os.path.join(self._folder_name, "libs", d)):
                        libraries.add(d)
                libraries = ' '.join(libraries)
                command = "{bcp} {namespace} {alias} " \
                          "{boostdir} {libraries} {outdir}".format(bcp=self._bcp_exe,
                                                                   namespace=namespace,
                                                                   alias=alias,
                                                                   libraries=libraries,
                                                                   boostdir=boostdir,
                                                                   outdir=self._bcp_dir)
                self.output.warn(command)
                self.run(command)

    def build(self):
        if self.options.header_only:
            self.output.warn("Header only package, skipping build")
            return

        self._clean()

        if self._use_bcp:
            self._build_bcp()
            self._run_bcp()

        # Help locating bzip2 and zlib
        self._create_user_config_jam(self._boost_build_dir)

        # JOIN ALL FLAGS
        b2_flags = " ".join(self._build_flags)
        full_command = "%s %s" % (self._b2_exe, b2_flags)
        # -d2 is to print more debug info and avoid travis timing out without output
        sources = os.path.join(self.source_folder, self._boost_dir)
        full_command += ' --debug-configuration --build-dir="%s"' % self.build_folder
        self.output.warn(full_command)

        with tools.vcvars(self.settings) if self._is_msvc else tools.no_op():
            with tools.chdir(sources):
                # To show the libraries *1
                # self.run("%s --show-libraries" % b2_exe)
                self.run(full_command)

        arch = self.settings.get_safe('arch')
        if arch.startswith("asm.js"):
            self._create_emscripten_libs()

    def _create_emscripten_libs(self):
        # Boost Build doesn't create the libraries, but it gets close,
        # leaving .bc files where the libraries would be.
        staged_libs = os.path.join(
            self.source_folder, self._boost_dir, "stage", "lib"
        )
        for bc_file in os.listdir(staged_libs):
            if bc_file.startswith("lib") and bc_file.endswith(".bc"):
                a_file = bc_file[:-3] + ".a"
                cmd = "emar q {dst} {src}".format(
                    dst=os.path.join(staged_libs, a_file),
                    src=os.path.join(staged_libs, bc_file),
                )
                self.output.info(cmd)
                self.run(cmd)

    @property
    def _b2_os(self):
        return {"Windows": "windows",
                "WindowsStore": "windows",
                "Linux": "linux",
                "Android": "android",
                "Macos": "darwin",
                "iOS": "iphone",
                "watchOS": "iphone",
                "tvOS": "appletv",
                "FreeBSD": "freebsd",
                "SunOS": "solaris"}.get(str(self.settings.os))

    @property
    def _b2_address_model(self):
        if str(self.settings.arch) in ["x86_64", "ppc64", "ppc64le", "mips64", "armv8", "sparcv9"]:
            return "64"
        else:
            return "32"

    @property
    def _b2_binary_format(self):
        return {"Windows": "pe",
                "WindowsStore": "pe",
                "Linux": "elf",
                "Android": "elf",
                "Macos": "mach-o",
                "iOS": "mach-o",
                "watchOS": "mach-o",
                "tvOS": "mach-o",
                "FreeBSD": "elf",
                "SunOS": "elf"}.get(str(self.settings.os))

    @property
    def _b2_architecture(self):
        if str(self.settings.arch).startswith('x86'):
            return 'x86'
        elif str(self.settings.arch).startswith('ppc'):
            return 'power'
        elif str(self.settings.arch).startswith('arm'):
            return 'arm'
        elif str(self.settings.arch).startswith('sparc'):
            return 'sparc'
        elif str(self.settings.arch).startswith('mips64'):
            return 'mips64'
        elif str(self.settings.arch).startswith('mips'):
            return 'mips1'
        else:
            return None

    @property
    def _b2_abi(self):
        if str(self.settings.arch).startswith('x86'):
            return "ms" if str(self.settings.os) in ["Windows", "WindowsStore"] else "sysv"
        elif str(self.settings.arch).startswith('ppc'):
            return "sysv"
        elif str(self.settings.arch).startswith('arm'):
            return "aapcs"
        elif str(self.settings.arch).startswith('mips'):
            return "o32"
        else:
            return None

    def collect_cxx_flags(self):
        collect_cxx_flags = ' '

        if self.options.enable_ubsan:
            collect_cxx_flags += '-fPIC'
            collect_cxx_flags += ' '
            collect_cxx_flags += '-fno-optimize-sibling-calls'
            collect_cxx_flags += ' '
            collect_cxx_flags += '-fno-omit-frame-pointer'
            collect_cxx_flags += ' '
            collect_cxx_flags += '-fno-stack-protector'
            collect_cxx_flags += ' '
            collect_cxx_flags += '-fno-wrapv'
            collect_cxx_flags += ' '
            collect_cxx_flags += '-fsanitize=undefined'
            collect_cxx_flags += ' '
            collect_cxx_flags += '-fsanitize=float-divide-by-zero'
            collect_cxx_flags += ' '
            collect_cxx_flags += '-fsanitize=unsigned-integer-overflow'
            collect_cxx_flags += ' '
            collect_cxx_flags += '-fsanitize=implicit-conversion'
            collect_cxx_flags += ' '
            collect_cxx_flags += '-fsanitize=nullability-arg'
            collect_cxx_flags += ' '
            collect_cxx_flags += '-fsanitize=nullability-assign'
            collect_cxx_flags += ' '
            collect_cxx_flags += '-fsanitize=nullability-return'
            collect_cxx_flags += ' '
            collect_cxx_flags += '-fno-sanitize=vptr'
            collect_cxx_flags += ' '

        if self.options.enable_asan:
            collect_cxx_flags += '-fPIC'
            collect_cxx_flags += ' '
            collect_cxx_flags += '-fno-optimize-sibling-calls'
            collect_cxx_flags += ' '
            collect_cxx_flags += '-fno-omit-frame-pointer'
            collect_cxx_flags += ' '
            collect_cxx_flags += '-fno-stack-protector'
            collect_cxx_flags += ' '
            collect_cxx_flags += '-fsanitize-address-use-after-scope'
            collect_cxx_flags += ' '
            collect_cxx_flags += '-fsanitize=address'
            collect_cxx_flags += ' '

        if self.options.enable_tsan:
            collect_cxx_flags += '-fPIC'
            collect_cxx_flags += ' '
            collect_cxx_flags += '-fno-optimize-sibling-calls'
            collect_cxx_flags += ' '
            collect_cxx_flags += '-fno-omit-frame-pointer'
            collect_cxx_flags += ' '
            collect_cxx_flags += '-fno-stack-protector'
            collect_cxx_flags += ' '
            collect_cxx_flags += '-fsanitize=thread'
            collect_cxx_flags += ' '

        if self.options.enable_msan:
            collect_cxx_flags += '-fPIC'
            collect_cxx_flags += ' '
            collect_cxx_flags += '-fPIE'
            collect_cxx_flags += ' '
            collect_cxx_flags += '-fno-elide-constructors'
            collect_cxx_flags += ' '
            collect_cxx_flags += '-fno-optimize-sibling-calls'
            collect_cxx_flags += ' '
            collect_cxx_flags += '-fno-omit-frame-pointer'
            collect_cxx_flags += ' '
            collect_cxx_flags += '-fno-stack-protector'
            collect_cxx_flags += ' '
            collect_cxx_flags += '-fsanitize-memory-track-origins=2'
            collect_cxx_flags += ' '
            collect_cxx_flags += '-fsanitize-memory-use-after-dtor'
            collect_cxx_flags += ' '
            collect_cxx_flags += '-fsanitize=memory'
            collect_cxx_flags += ' '

        if self.options.enable_msan \
           or self.options.enable_asan \
           or self.options.enable_tsan \
           or self.options.enable_ubsan \
           or self._is_compile_with_llvm_tools_enabled():
            llvm_tools_ROOT = self.deps_cpp_info["llvm_tools"].rootpath.replace('\\', '/')
            self.output.info('llvm_tools_ROOT = %s' % (llvm_tools_ROOT))
            collect_cxx_flags += '-Wno-error=unused-command-line-argument'
            collect_cxx_flags += ' '
            collect_cxx_flags += '-Wno-unused-command-line-argument'
            collect_cxx_flags += ' '
            collect_cxx_flags += '-fuse-ld=lld'
            collect_cxx_flags += ' '
            collect_cxx_flags += '-D__CLANG__'
            collect_cxx_flags += ' '
            collect_cxx_flags += '-nostdinc++'
            collect_cxx_flags += ' '
            collect_cxx_flags += '-stdlib=libc++'
            collect_cxx_flags += ' '
            collect_cxx_flags += "-isystem {}/include/c++/v1".format(llvm_tools_ROOT)
            collect_cxx_flags += ' '
            collect_cxx_flags += "-isystem {}/include".format(llvm_tools_ROOT)
            collect_cxx_flags += ' '
            collect_cxx_flags += "-isystem {}/lib/clang/10.0.1/include".format(llvm_tools_ROOT)
            collect_cxx_flags += ' '
            collect_cxx_flags += "-lc++"
            collect_cxx_flags += ' '
            collect_cxx_flags += "-lc++abi"
            collect_cxx_flags += ' '
            collect_cxx_flags += "-lunwind"
            collect_cxx_flags += ' '
            collect_cxx_flags += "-Wl,-rpath,{}/lib".format(llvm_tools_ROOT)
            collect_cxx_flags += ' '
            collect_cxx_flags += "-L{}/lib".format(llvm_tools_ROOT)
            collect_cxx_flags += ' '

        return collect_cxx_flags

    def collect_linkflags(self):
        collect_linkflags = ' '

        # TODO: unknown argument '-static-libtsan'
        #if self.options.enable_ubsan:
        #    collect_linkflags += '-static-libubsan'
        #    collect_linkflags += ' '
        #
        #if self.options.enable_asan:
        #    collect_linkflags += '-static-libasan'
        #    collect_linkflags += ' '
        #
        #if self.options.enable_tsan:
        #    collect_linkflags += '-static-libtsan'
        #    collect_linkflags += ' '
        #
        #if self.options.enable_msan:
        #    collect_linkflags += '-static-libmsan'
        #    collect_linkflags += ' '

        if self.options.enable_msan \
           or self.options.enable_asan \
           or self.options.enable_tsan \
           or self.options.enable_ubsan \
           or self._is_compile_with_llvm_tools_enabled():
            llvm_tools_ROOT = self.deps_cpp_info["llvm_tools"].rootpath.replace('\\', '/')
            self.output.info('llvm_tools_ROOT = %s' % (llvm_tools_ROOT))
            collect_linkflags += '-stdlib=libc++'
            collect_linkflags += ' '
            collect_linkflags += '-lc++'
            collect_linkflags += ' '
            collect_linkflags += '-lc++abi'
            collect_linkflags += ' '
            collect_linkflags += '-lunwind'
            collect_linkflags += ' '
            collect_linkflags += "-Wl,-rpath,{}/lib".format(llvm_tools_ROOT)
            collect_linkflags += ' '
            collect_linkflags += "-L{}/lib".format(llvm_tools_ROOT)
            collect_linkflags += ' '

        return collect_linkflags

    @property
    def _gnu_cxx11_abi(self):
        """Checks libcxx setting and returns value for the GNU C++11 ABI flag
        _GLIBCXX_USE_CXX11_ABI= .  Returns None if C++ library cannot be
        determined.
        """

        if self._is_compile_with_llvm_tools_enabled():
          return "0"

        try:
            if str(self.settings.compiler.libcxx) == "libstdc++":
                return "0"
            elif str(self.settings.compiler.libcxx) == "libstdc++11":
                return "1"
        except:
            pass
        return None

    @property
    def _build_flags(self):
        flags = self._build_cross_flags

        # https://www.boost.org/doc/libs/1_70_0/libs/context/doc/html/context/architectures.html
        if self._b2_os:
            flags.append("target-os=%s" % self._b2_os)
        if self._b2_architecture:
            flags.append("architecture=%s" % self._b2_architecture)
        if self._b2_address_model:
            flags.append("address-model=%s" % self._b2_address_model)
        if self._b2_binary_format:
            flags.append("binary-format=%s" % self._b2_binary_format)
        if self._b2_abi:
            flags.append("abi=%s" % self._b2_abi)

        flags.append("--layout=%s" % self.options.layout)
        flags.append("--user-config=%s" % os.path.join(self._boost_build_dir, 'user-config.jam'))
        flags.append("-sNO_ZLIB=%s" % ("0" if self.options.zlib else "1"))
        flags.append("-sNO_BZIP2=%s" % ("0" if self.options.bzip2 else "1"))
        flags.append("-sNO_LZMA=%s" % ("0" if self.options.lzma else "1"))
        flags.append("-sNO_ZSTD=%s" % ("0" if self.options.zstd else "1"))

        def add_defines(option, library):
            if option:
                for define in self.deps_cpp_info[library].defines:
                    flags.append("define=%s" % define)

        if self._zip_bzip2_requires_needed:
            add_defines(self.options.zlib, "zlib")
            add_defines(self.options.bzip2, "bzip2")
            add_defines(self.options.lzma, "lzma")
            add_defines(self.options.zstd, "zstd")

        if self._is_msvc and self.settings.compiler.runtime:
            flags.append("runtime-link=%s" % ("static" if "MT" in str(self.settings.compiler.runtime) else "shared"))

        flags.append("threading=multi")

        flags.append("link=%s" % ("static" if not self.options.shared else "shared"))
        if self.settings.build_type == "Debug":
            flags.append("variant=debug")
        else:
            flags.append("variant=release")

        for libname in lib_list:
            if getattr(self.options, "without_%s" % libname):
                flags.append("--without-%s" % libname)

        flags.append("toolset=%s" % self._toolset)

        if self.settings.get_safe("compiler.cppstd"):
            flags.append("cxxflags=%s" % cppstd_flag(
                    self.settings.get_safe("compiler"),
                    self.settings.get_safe("compiler.version"),
                    self.settings.get_safe("compiler.cppstd")
                )
            )

        # CXX FLAGS
        cxx_flags = []
        # fPIC DEFINITION
        if self.settings.os != "Windows":
            if self.options.fPIC:
                cxx_flags.append("-fPIC")

        collected_linkflags = self.collect_linkflags()
        self.output.info('collected_linkflags = %s' % (collected_linkflags))

        collected_cxx_flags = self.collect_cxx_flags()
        self.output.info('collected_cxx_flags = %s' % (collected_cxx_flags))

        # Standalone toolchain fails when declare the std lib
        if collected_cxx_flags == "" and self.settings.os != "Android":
            try:
                if self._gnu_cxx11_abi:
                    flags.append("define=_GLIBCXX_USE_CXX11_ABI=%s" % self._gnu_cxx11_abi)

                if "clang" in str(self.settings.compiler):
                    if str(self.settings.compiler.libcxx) == "libc++":
                        cxx_flags.append("-stdlib=libc++")
                        flags.append('linkflags="-stdlib=libc++"')
                    else:
                        cxx_flags.append("-stdlib=libstdc++")
            except:
                pass

        flags.append('linkflags="{}"'.format(collected_linkflags))

        cxx_flags.append(collected_cxx_flags)

        if self.options.error_code_header_only:
            flags.append("define=BOOST_ERROR_CODE_HEADER_ONLY=1")
        if self.options.system_no_deprecated:
            flags.append("define=BOOST_SYSTEM_NO_DEPRECATED=1")
        if self.options.asio_no_deprecated:
            flags.append("define=BOOST_ASIO_NO_DEPRECATED=1")
        if self.options.filesystem_no_deprecated:
            flags.append("define=BOOST_FILESYSTEM_NO_DEPRECATED=1")

        if self.options.no_rtti:
            flags.append("define=BOOST_NO_RTTI=1")
            flags.append("define=BOOST_NO_TYPEID=1")

        if self.options.no_exceptions:
            flags.append("define=BOOST_EXCEPTION_DISABLE=1")
            flags.append("define=BOOST_NO_EXCEPTIONS=1")

        if self.options.segmented_stacks:
            flags.extend(["segmented-stacks=on",
                          "define=BOOST_USE_SEGMENTED_STACKS=1",
                          "define=BOOST_USE_UCONTEXT=1"])
        flags.append("pch=on" if self.options.pch else "pch=off")

        if tools.is_apple_os(self.settings.os):
            if self.settings.get_safe("os.version"):
                cxx_flags.append(tools.apple_deployment_target_flag(self.settings.os,
                                                                    self.settings.os.version))

        if self.settings.os == "iOS":
            cxx_flags.append("-DBOOST_AC_USE_PTHREADS")
            cxx_flags.append("-DBOOST_SP_USE_PTHREADS")
            cxx_flags.append("-fvisibility=hidden")
            cxx_flags.append("-fvisibility-inlines-hidden")
            cxx_flags.append("-fembed-bitcode")

        cxx_flags = 'cxxflags="%s"' % " ".join(cxx_flags) if cxx_flags else ""
        flags.append(cxx_flags)

        if self.options.extra_b2_flags:
            flags.append(str(self.options.extra_b2_flags))

        flags.extend(["install",
                      "--prefix=%s" % self.package_folder,
                      "-j%s" % tools.cpu_count(),
                      "--abbreviate-paths",
                      "-d%s" % str(self.options.debug_level)])
        return flags

    @property
    def _build_cross_flags(self):
        flags = []
        if not tools.cross_building(self.settings):
            return flags
        arch = self.settings.get_safe('arch')
        self.output.info("Cross building, detecting compiler...")

        if arch.startswith('arm'):
            if 'hf' in arch:
                flags.append('-mfloat-abi=hard')
        elif arch in ["x86", "x86_64"]:
            pass
        elif arch.startswith("ppc"):
            pass
        elif arch.startswith("mips"):
            pass
        elif arch.startswith("asm.js"):
            pass
        else:
            self.output.warn("Unable to detect the appropriate ABI for %s architecture." % arch)
        self.output.info("Cross building flags: %s" % flags)

        return flags

    @property
    def _ar(self):
        if "AR" in os.environ:
            return os.environ["AR"]
        if tools.is_apple_os(self.settings.os) and self.settings.compiler == "apple-clang":
            return tools.XCRun(self.settings).ar
        return None

    @property
    def _ranlib(self):
        if "RANLIB" in os.environ:
            return os.environ["RANLIB"]
        if tools.is_apple_os(self.settings.os) and self.settings.compiler == "apple-clang":
            return tools.XCRun(self.settings).ranlib
        return None

    @property
    def _cxx(self):
        if "CXX" in os.environ:
            return os.environ["CXX"]
        if tools.is_apple_os(self.settings.os) and self.settings.compiler == "apple-clang":
            return tools.XCRun(self.settings).cxx
        compiler_version = str(self.settings.compiler.version)
        major = compiler_version.split(".")[0]
        if self.settings.compiler == "gcc":
            return tools.which("g++-%s" % compiler_version) or tools.which("g++-%s" % major) or tools.which("g++") or ""
        if self.settings.compiler == "clang":
            return tools.which("clang++-%s" % compiler_version) or tools.which("clang++-%s" % major) or tools.which("clang++") or ""
        return ""

    def _create_user_config_jam(self, folder):
        """To help locating the zlib and bzip2 deps"""
        self.output.warn("Patching user-config.jam")

        contents = ""
        if self._zip_bzip2_requires_needed:
            def create_library_config(name):
                includedir = self.deps_cpp_info[name].include_paths[0].replace('\\', '/')
                libdir = self.deps_cpp_info[name].lib_paths[0].replace('\\', '/')
                lib = self.deps_cpp_info[name].libs[0]
                version = self.deps_cpp_info[name].version
                return "\nusing {name} : {version} : " \
                       "<include>{includedir} " \
                       "<search>{libdir} " \
                       "<name>{lib} ;".format(name=name,
                                              version=version,
                                              includedir=includedir,
                                              libdir=libdir,
                                              lib=lib)

            contents = ""
            if self.options.zlib:
                contents += create_library_config("zlib")
            if self.options.bzip2:
                contents += create_library_config("bzip2")
            if self.options.lzma:
                contents += create_library_config("lzma")
            if self.options.zstd:
                contents += create_library_config("zstd")

        if not self.options.without_python:
            # https://www.boost.org/doc/libs/1_70_0/libs/python/doc/html/building/configuring_boost_build.html
            contents += '\nusing python : {version} : "{executable}" : "{includes}" : "{libraries}" ;'\
                .format(version=self._python_version,
                        executable=self._python_executable,
                        includes=self._python_includes,
                        libraries=self._python_libraries)

        # Specify here the toolset with the binary if present if don't empty parameter :
        contents += '\nusing "%s" : %s : ' % (self._toolset, self._toolset_version)
        contents += ' %s' % self._cxx.replace("\\", "/")

        if tools.is_apple_os(self.settings.os):
            if self.settings.compiler == "apple-clang":
                contents += " -isysroot %s" % tools.XCRun(self.settings).sdk_path
            if self.settings.get_safe("arch"):
                contents += " -arch %s" % tools.to_apple_arch(self.settings.arch)

        collected_linkflags = self.collect_linkflags()
        self.output.info('(2) collected_linkflags = %s' % (collected_linkflags))

        collected_cxx_flags = self.collect_cxx_flags()
        self.output.info('(2) collected_cxx_flags = %s' % (collected_cxx_flags))

        contents += " : \n"

        if self._ar:
            contents += '<archiver>"%s" ' % tools.which(self._ar).replace("\\", "/")

        if self._ranlib:
            contents += '<ranlib>"%s" ' % tools.which(self._ranlib).replace("\\", "/")

        contents += '<cxxflags>"%s%s" ' % (os.environ["CXXFLAGS"] if "CXXFLAGS" in os.environ else "", collected_cxx_flags)

        contents += '<cflags>"%s%s" ' % (os.environ["CFLAGS"] if "CFLAGS" in os.environ else "", collected_cxx_flags)

        contents += '<linkflags>"%s%s" ' % (os.environ["LDFLAGS"] if "LDFLAGS" in os.environ else "", collected_linkflags)

        if "ASFLAGS" in os.environ:
            contents += '<asmflags>"%s" ' % os.environ["ASFLAGS"]

        contents += " ;"

        self.output.warn(contents)
        filename = "%s/user-config.jam" % folder
        tools.save(filename,  contents)

    @property
    def _toolset_version(self):
        if self._is_msvc:
            compiler_version = str(self.settings.compiler.version)
            if Version(compiler_version) >= "16":
                return "14.2"
            elif Version(compiler_version) >= "15":
                return "14.1"
            else:
                return "%s.0" % compiler_version
        return ""

    @property
    def _toolset(self):
        compiler = str(self.settings.compiler)
        if self._is_msvc:
            return "msvc"
        elif self.settings.os == "Windows" and compiler == "clang":
            return "clang-win"
        elif self.settings.os == "Emscripten" and compiler == "clang":
            return "emscripten"
        elif compiler == "gcc" and tools.is_apple_os(self.settings.os):
            return "darwin"
        elif compiler == "apple-clang":
            return "clang-darwin"
        elif self.settings.os == "Android" and compiler == "clang":
            return "clang-linux"
        elif str(self.settings.compiler) in ["clang", "gcc"]:
            return compiler
        elif compiler == "sun-cc":
            return "sunpro"
        elif compiler == "intel":
            toolset = {"Macos": "intel-darwin",
                       "Windows": "intel-win",
                       "Linux": "intel-linux"}.get(str(self.settings.os))
            return toolset
        else:
            return compiler

    ####################################################################

    def package(self):
        # This stage/lib is in source_folder... Face palm, looks like it builds in build but then
        # copy to source with the good lib name
        self.copy("LICENSE_1_0.txt", dst="licenses", src=os.path.join(self.source_folder,
                                                                      self._folder_name))
        tools.rmdir(os.path.join(self.package_folder, "lib", "cmake"))
        if self.options.header_only:
            self.copy(pattern="*", dst="include/boost", src="%s/boost" % self._boost_dir)

    def package_info(self):
        gen_libs = [] if self.options.header_only else tools.collect_libs(self)

        # List of lists, so if more than one matches the lib like serialization and wserialization
        # both will be added to the list
        ordered_libs = [[] for _ in range(len(lib_list))]

        # The order is important, reorder following the lib_list order
        missing_order_info = []
        for real_lib_name in gen_libs:
            for pos, alib in enumerate(lib_list):
                if os.path.splitext(real_lib_name)[0].split("-")[0].endswith(alib):
                    ordered_libs[pos].append(real_lib_name)
                    break
            else:
                # self.output.info("Missing in order: %s" % real_lib_name)
                if "_exec_monitor" not in real_lib_name:  # https://github.com/bincrafters/community/issues/94
                    missing_order_info.append(real_lib_name)  # Assume they do not depend on other

        # Flat the list and append the missing order
        self.cpp_info.libs = [item for sublist in ordered_libs
                                      for item in sublist if sublist] + missing_order_info

        if self.options.without_test:  # remove boost_unit_test_framework
            self.cpp_info.libs = [lib for lib in self.cpp_info.libs if "unit_test" not in lib]

        self.output.info("LIBRARIES: %s" % self.cpp_info.libs)
        self.output.info("Package folder: %s" % self.package_folder)

        if not self.options.header_only and self.options.shared:
            self.cpp_info.defines.append("BOOST_ALL_DYN_LINK")

        if self.options.system_no_deprecated:
            self.cpp_info.defines.append("BOOST_SYSTEM_NO_DEPRECATED")

        if self.options.asio_no_deprecated:
            self.cpp_info.defines.append("BOOST_ASIO_NO_DEPRECATED")

        if self.options.no_rtti:
            self.cpp_info.defines.append("BOOST_NO_RTTI")
            self.cpp_info.defines.append("BOOST_NO_TYPEID")

        if self.options.no_exceptions:
            self.cpp_info.defines.append("BOOST_EXCEPTION_DISABLE")
            self.cpp_info.defines.append("BOOST_NO_EXCEPTIONS")

        if self.options.filesystem_no_deprecated:
            self.cpp_info.defines.append("BOOST_FILESYSTEM_NO_DEPRECATED")

        if self.options.segmented_stacks:
            self.cpp_info.defines.extend(["BOOST_USE_SEGMENTED_STACKS", "BOOST_USE_UCONTEXT"])

        if self.settings.os != "Android":
            if self._gnu_cxx11_abi:
                self.cpp_info.defines.append("_GLIBCXX_USE_CXX11_ABI=%s" % self._gnu_cxx11_abi)

        if not self.options.header_only:
            if self.options.error_code_header_only:
                self.cpp_info.defines.append("BOOST_ERROR_CODE_HEADER_ONLY")

            if not self.options.without_python:
                if not self.options.shared:
                    self.cpp_info.defines.append("BOOST_PYTHON_STATIC_LIB")

            if self._is_msvc:
                if not self.options.magic_autolink:
                    # DISABLES AUTO LINKING! NO SMART AND MAGIC DECISIONS THANKS!
                    self.cpp_info.defines.append("BOOST_ALL_NO_LIB")
                    self.output.info("Disabled magic autolinking (smart and magic decisions)")
                else:
                    if self.options.layout == "system":
                        self.cpp_info.defines.append("BOOST_AUTO_LINK_SYSTEM")
                    elif self.options.layout == "tagged":
                        self.cpp_info.defines.append("BOOST_AUTO_LINK_TAGGED")
                    self.output.info("Enabled magic autolinking (smart and magic decisions)")

                # https://github.com/conan-community/conan-boost/issues/127#issuecomment-404750974
                self.cpp_info.system_libs.append("bcrypt")
            elif self.settings.os == "Linux":
                # https://github.com/conan-community/conan-boost/issues/135
                self.cpp_info.system_libs.extend(["pthread", "rt"])

        self.env_info.BOOST_ROOT = self.package_folder
        self.cpp_info.bindirs.append("lib")
        self.cpp_info.names["cmake_find_package"] = "Boost"
        self.cpp_info.names["cmake_find_package_multi"] = "Boost"

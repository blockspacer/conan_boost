# About

Modified `boost` recipe

## EXTRA FEATURES

- supports "zlib/v1.2.11@conan/stable" with "openssl/OpenSSL_1_1_1-stable@conan/stable"
- able to disable ctest

# About

## Docker build

```bash
export MY_IP=$(ip route get 8.8.8.8 | sed -n '/src/{s/.*src *\([^ ]*\).*/\1/p;q}')
sudo -E docker build \
    --build-arg PKG_NAME=boost/1.71.0 \
    --build-arg PKG_CHANNEL=dev/stable \
    --build-arg PKG_UPLOAD_NAME=boost/1.71.0@dev/stable \
    --build-arg CONAN_EXTRA_REPOS="conan-local http://$MY_IP:8081/artifactory/api/conan/conan False" \
    --build-arg CONAN_EXTRA_REPOS_USER="user -p password1 -r conan-local admin" \
    --build-arg CONAN_INSTALL="conan install --profile clang --build missing" \
    --build-arg CONAN_CREATE="conan create --profile clang --build missing" \
    --build-arg CONAN_UPLOAD="conan upload --all -r=conan-local -c --retry 3 --retry-wait 10 --force" \
    --build-arg BUILD_TYPE=Debug \
    -f conan_boost.Dockerfile --tag conan_boost . --no-cache
```

## Local build

```bash
# see https://github.com/boostorg/build/issues/418
# use b2 provided by conan package
(sudo apt remove libboost-*-dev || true)
(sudo mv /usr/bin/b2 /usr/bin/b2_backup || true)

export PKG_NAME=boost/1.71.0@dev/stable
conan remove -f $PKG_NAME
conan create . dev/stable -s build_type=Debug --profile clang --build missing -o boost:without_ctest=True -o openssl:shared=True
CONAN_REVISIONS_ENABLED=1 CONAN_VERBOSE_TRACEBACK=1 CONAN_PRINT_RUN_COMMANDS=1 CONAN_LOGGING_LEVEL=10 conan upload $PKG_NAME --all -r=conan-local -c --retry 3 --retry-wait 10 --force

# clean build cache
conan remove "*" --build --force
```


## HOW TO BUILD WITH SANITIZERS ENABLED

Use `enable_asan` or `enable_ubsan`, etc.

```bash
export CC=$(find ~/.conan/data/llvm_tools/master/conan/stable/package/ -path "*bin/clang" | head -n 1)

export CXX=$(find ~/.conan/data/llvm_tools/master/conan/stable/package/ -path "*bin/clang++" | head -n 1)

export CFLAGS="-fsanitize=thread -fuse-ld=lld -stdlib=libc++ -lc++ -lc++abi -lunwind"

export CXXFLAGS="-fsanitize=thread -fuse-ld=lld -stdlib=libc++ -lc++ -lc++abi -lunwind"

export LDFLAGS="-stdlib=libc++ -lc++ -lc++abi -lunwind"

# must exist
file $(dirname $CXX)/../lib/clang/10.0.1/lib/linux/libclang_rt.tsan_cxx-x86_64.a

# NOTE: NO `--profile` argument cause we use `CXX` env. var
# NOTE: change `build_type=Debug` to `build_type=Release` in production
CONAN_REVISIONS_ENABLED=1 \
    CONAN_VERBOSE_TRACEBACK=1 \
    CONAN_PRINT_RUN_COMMANDS=1 \
    CONAN_LOGGING_LEVEL=10 \
    GIT_SSL_NO_VERIFY=true \
    conan create . \
        dev/stable \
        -s build_type=Debug \
        -s llvm_tools:build_type=Release \
        -o llvm_tools:enable_tsan=True \
        -o llvm_tools:include_what_you_use=False \
        -s llvm_tools:compiler=clang \
        -s llvm_tools:compiler.version=10 \
        -s llvm_tools:compiler.libcxx=libstdc++11 \
        -o boost:without_ctest=True \
        -o boost:enable_tsan=True \
        -e boost:enable_llvm_tools=True \
        -e boost:compile_with_llvm_tools=True \
        -s compiler=clang \
        -s compiler.version=10 \
        -s compiler.libcxx=libc++ \
        -o openssl:shared=True

# reset changed LDFLAGS
unset LDFLAGS

# reset changed CFLAGS
unset CFLAGS

# reset changed CXXFLAGS
unset CXXFLAGS

NOTE: during compilation conan will print `llvm_tools_ROOT =`. Make sure its path matches `$CC` and `$CXX`.

# clean build cache
conan remove "*" --build --force
```

## How to diagnose errors in conanfile (CONAN_PRINT_RUN_COMMANDS)

```bash
# NOTE: about `--keep-source` see https://bincrafters.github.io/2018/02/27/Updated-Conan-Package-Flow-1.1/
CONAN_REVISIONS_ENABLED=1 CONAN_VERBOSE_TRACEBACK=1 CONAN_PRINT_RUN_COMMANDS=1 CONAN_LOGGING_LEVEL=10 conan create . conan/stable -s build_type=Debug --profile clang --build missing --keep-source
```

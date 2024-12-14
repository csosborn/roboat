# Micropython-Builder Docker Container

The Roboat uses a custom build of the MicroPython firmware, primarily to include the non-default ulab module (which has native C components). The build process takes place within a Docker container constructed for the purpose.

Build docker container, and label it `micropython-builder`:
```
build -t micropython-builder src/build-tools/micropython-builder
```

Run `micropython-builder` with a volume called `build`, which should start empty and will receive the build products:
```
docker run -v ./build:/build -it micropython-builder
```

After running `build` will look something like this:
```
% ls -al build
total 37672
drwxr-xr-x  19 csosborn  staff      608 Dec 13 16:01 .
drwxr-xr-x  13 csosborn  staff      416 Dec 13 16:00 ..
-rw-r--r--   1 csosborn  staff    26538 Dec 13 16:00 CMakeCache.txt
drwxr-xr-x  16 csosborn  staff      512 Dec 13 16:01 CMakeFiles
-rw-r--r--   1 csosborn  staff   664645 Dec 13 16:00 Makefile
drwxr-xr-x   6 csosborn  staff      192 Dec 13 16:01 _deps
-rw-r--r--   1 csosborn  staff     1638 Dec 13 16:00 cmake_install.cmake
-rwxr-xr-x@  1 csosborn  staff   446104 Dec 13 16:01 firmware.bin
-rw-r--r--   1 csosborn  staff  6828978 Dec 13 16:01 firmware.dis
-rwxr-xr-x@  1 csosborn  staff  7383072 Dec 13 16:01 firmware.elf
-rw-r--r--   1 csosborn  staff  1937498 Dec 13 16:01 firmware.elf.map
-rw-r--r--   1 csosborn  staff   892416 Dec 13 16:01 firmware.uf2
-rw-r--r--   1 csosborn  staff   421940 Dec 13 16:00 frozen_content.c
drwxr-xr-x  11 csosborn  staff      352 Dec 13 16:00 frozen_mpy
drwxr-xr-x   3 csosborn  staff       96 Dec 13 16:00 generated
drwxr-xr-x  21 csosborn  staff      672 Dec 13 16:01 genhdr
drwxr-xr-x   8 csosborn  staff      256 Dec 13 16:00 pico-sdk
-rw-r--r--@  1 csosborn  staff       60 Dec 13 16:00 pico_flash_region.ld
-rw-r--r--   1 csosborn  staff    18484 Dec 13 16:00 pins_RPI_PICO.c
```

The file `firmware.uf2` should be copied to the RP2040 in bootsel mode.
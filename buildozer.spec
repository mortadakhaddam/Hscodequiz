[app]

# (str) Title of your application
title = رفيقك في حفظ الرموز الجمركية

# (str) Package name (letters/numbers only, no spaces)
package.name = hscodesquiz

# (str) Package domain (needed for android packaging)
package.domain = org.tariffquiz

# (str) Source code where the main.py lives
source.dir = .

# (list) Source files to include (let empty to include all the files)
source.include_exts = py,json,ttf,png,jpg,kv,atlas

# (str) Application versioning
version = 1.0

# (list) Application requirements
# arabic-reshaper and python-bidi are pure-Python and install fine via pip
requirements = python3,kivy==2.3.0,arabic-reshaper,python-bidi

# (str) Presplash / icon - leave commented out unless you add your own files
#icon.filename = %(source.dir)s/icon.png
#presplash.filename = %(source.dir)s/presplash.png

# (str) Supported orientation
orientation = portrait

# (bool) Indicate if the application should be fullscreen or not
fullscreen = 0

# (list) Permissions
android.permissions = INTERNET

# (list) Architectures to build for
android.archs = arm64-v8a, armeabi-v7a

# (int) Target Android API
android.api = 33

# (int) Minimum API your APK / AAB will support
android.minapi = 21

# (str) Android NDK version to use
android.ndk = 25b

[buildozer]

# (int) Log level (0 = error only, 1 = info, 2 = debug)
log_level = 2

# (int) Display warning if buildozer is run as root
warn_on_root = 1

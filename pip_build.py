"""Script to create (and optionally install) a `.whl` archive for Keras 3.

Usage:

1. Create a `.whl` file in `dist/`:

```
python3 pip_build.py
```

2. Also install the new package immediately after:

```
python3 pip_build.py --install
```
"""

import argparse
import datetime
import glob
import os
import pathlib
import re
import shutil

# Needed because importing torch after TF causes the runtime to crash
import torch  # noqa: F401

package = "keras"
build_directory = "tmp_build_dir"
dist_directory = "dist"
to_copy = ["setup.py", "README.md"]


def export_version_string(version, is_nightly=False, rc_index=None):
    """Export Version and Package Name."""
    if is_nightly:
        date = datetime.datetime.now()
        version += f".dev{date.strftime('%Y%m%d%H')}"
        # Replaces `name="keras"` string in `setup.py` with `keras-nightly`
        with open("setup.py") as f:
            setup_contents = f.read()
        with open("setup.py", "w") as f:
            setup_contents = setup_contents.replace(
                'name="keras"', 'name="keras-nightly"'
            )
            f.write(setup_contents)
    elif rc_index is not None:
        version += "rc" + str(rc_index)

    # Make sure to export the __version__ string
    with open(os.path.join(package, "src", "version.py")) as f:
        init_contents = f.read()
    with open(os.path.join(package, "src", "version.py"), "w") as f:
        init_contents = re.sub(
            "\n__version__ = .*\n",
            f'\n__version__ = "{version}"\n',
            init_contents,
        )
        f.write(init_contents)


def ignore_files(_, filenames):
    return [f for f in filenames if f.endswith("_test.py")]


def copy_source_to_build_directory(root_path):
    # Copy sources (`keras/` directory and setup files) to build
    # directory
    os.chdir(root_path)
    os.mkdir(build_directory)
    shutil.copytree(
        package, os.path.join(build_directory, package), ignore=ignore_files
    )
    for fname in to_copy:
        shutil.copy(fname, os.path.join(f"{build_directory}", fname))
    os.chdir(build_directory)


def build(root_path, is_nightly=False, rc_index=None):
    if os.path.exists(build_directory):
        raise ValueError(f"Directory already exists: {build_directory}")

    try:
        copy_source_to_build_directory(root_path)
        move_tf_keras_directory()
        print(os.getcwd())

        from keras.src.version import __version__  # noqa: E402

        export_version_string(__version__, is_nightly, rc_index)
        return build_and_save_output(root_path, __version__)
    finally:
        # Clean up: remove the build directory (no longer needed)
        shutil.rmtree(build_directory)


def move_tf_keras_directory():
    """Move `keras/api/_tf_keras` to `keras/_tf_keras`, update references."""
    shutil.move(os.path.join(package, "api", "_tf_keras"), "keras")
    with open(os.path.join(package, "api", "__init__.py")) as f:
        contents = f.read()
        contents = contents.replace("from keras.api import _tf_keras", "")
    with open(os.path.join(package, "api", "__init__.py"), "w") as f:
        f.write(contents)
    # Replace `keras.api._tf_keras` with `keras._tf_keras`.
    for root, _, fnames in os.walk(os.path.join(package, "_tf_keras")):
        for fname in fnames:
            if fname.endswith(".py"):
                tf_keras_fpath = os.path.join(root, fname)
                with open(tf_keras_fpath) as f:
                    contents = f.read()
                    contents = contents.replace(
                        "keras.api._tf_keras", "keras._tf_keras"
                    )
                with open(tf_keras_fpath, "w") as f:
                    f.write(contents)


def build_and_save_output(root_path, __version__):
    # Build the package
    os.system("python3 -m build")

    # Save the dist files generated by the build process
    os.chdir(root_path)
    if not os.path.exists(dist_directory):
        os.mkdir(dist_directory)
    for fpath in glob.glob(
        os.path.join(build_directory, dist_directory, "*.*")
    ):
        shutil.copy(fpath, dist_directory)

    # Find the .whl file path
    whl_path = None
    for fname in os.listdir(dist_directory):
        if __version__ in fname and fname.endswith(".whl"):
            whl_path = os.path.abspath(os.path.join(dist_directory, fname))
    if whl_path:
        print(f"Build successful. Wheel file available at {whl_path}")
    else:
        print("Build failed.")
    return whl_path


def install_whl(whl_fpath):
    print(f"Installing wheel file: {whl_fpath}")
    os.system(f"pip3 install {whl_fpath} --force-reinstall --no-dependencies")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--install",
        action="store_true",
        help="Whether to install the generated wheel file.",
    )
    parser.add_argument(
        "--nightly",
        action="store_true",
        help="Whether to generate nightly wheel file.",
    )
    parser.add_argument(
        "--rc",
        type=int,
        help="Specify `[0-9] when generating RC wheels.",
    )
    args = parser.parse_args()
    root_path = pathlib.Path(__file__).parent.resolve()
    whl_path = build(root_path, args.nightly, args.rc)
    if whl_path and args.install:
        install_whl(whl_path)

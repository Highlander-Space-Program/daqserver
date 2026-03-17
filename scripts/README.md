# Scripts

<!-- filetree start -->

```text
daqserver
├── scripts (You are here)
└── server
    ├── db
    ├── streaming
    └── web
        ├── static
        │   ├── css
        │   └── js
        └── templates
```

<!-- filetree end -->

## About scripts

This directory contains all of the scripts that are going to help you
throughout the development of this project. If you have other scripts that you
want to add to here, feel free to do so. Make sure you have documented the
scripts that you have added at the top of the script file so people know what's
going on in the script and how to use it.

Having the script be written in the Python language is preferred. Running the
Python scripts is usually just `uv run scripts/script_name.py`, and this
ensures cross platform compatibility (People using MacOS might not be able to
use a `batch` script). If you have a good reason to use batch like creating
some sort of installer for Windows users then feel free to use batch.

## How to use the scripts

If the script is written in Python (files that ends with `.py`), then you can
should be able to run it using `uv run scripts/script_name.py` where you have
to replace the `script_name` with the actual script's name. Please open the
script file that you are running for documentation about how to use it.

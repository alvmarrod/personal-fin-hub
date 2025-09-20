### Using VSCode Debugger
1. Open VSCode.
2. Select the **Run and Debug** option from the sidebar or use the keyboard shortcut `Ctrl+Shift+D`.
3. Launch a Uvicorn worker in debug mode.

### Requirements

* Pyenv
* Poetry (1.8.4)

### Get ready

#### Install the required python version

[pyenv](https://github.com/pyenv/pyenv) is recommended for handling Python versions:

```bash
$ pyenv install
$ pyenv local
```

**NOTE**: The python version will be chosen from the `.python-version` file.

#### Install poetry

```bash
$ pip install poetry
```

## Usage

Using `make` you will be able to see useful commands.

### Configure development enviroment

#### Install dependencies

```bash
$ make install
```

#### Set shell enviroment

```bash
$ make shell
```

#### Run local server
```bash
$ uvicorn main:app --reload --host 0.0.0.0 --port 8000
```
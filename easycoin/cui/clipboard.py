import subprocess
import platform

import pyperclip


def universal_copy(text: str):
    """Copies text to both CLIPBOARD and PRIMARY selections on Linux."""
    pyperclip.copy(text)

    if platform.system() == "Linux":
        try:
            process = subprocess.Popen(
                ['xclip', '-selection', 'primary'],
                stdin=subprocess.PIPE,
                close_fds=True
            )
            process.communicate(input=text.encode('utf-8'))
        except FileNotFoundError:
            try:
                process = subprocess.Popen(
                    ['xsel', '--primary', '--input'],
                    stdin=subprocess.PIPE,
                    close_fds=True
                )
                process.communicate(input=text.encode('utf-8'))
            except FileNotFoundError:
                pass

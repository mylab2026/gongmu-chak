"""File-based runtime check avoids PowerShell 5.1 native command quoting."""
import ssl
import pypdfium2
from PIL import Image


def main():
    image = Image.new('RGB', (8, 8), 'white')
    assert image.size == (8, 8)
    ssl.create_default_context()
    print('Runtime OK')


if __name__ == '__main__':
    main()

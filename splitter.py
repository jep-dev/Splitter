import os
import sys
from PIL import Image
import argparse
import requests
import re
from urllib.parse import urlparse
import mimetypes

def verify_or_create_directory(path, verbose=False):
    try:
        if not os.path.exists(path):
            os.makedirs(path, exist_ok=True)
            if verbose:
                print(f"Created directory: {path}")
        return True
    except Exception as e:
        if verbose:
            print(f"Error while creating directory {path}: {e}")
        return False

# Ensure config directory and files exist
def ensure_config_files(config_dir, verbose=False):
    verify_or_create_directory(config_dir, verbose)
    config_files = {
        'extensions.txt': 'png\njpg\njpeg\nwebp',
        'output_format.txt': 'default',
        'recursive.txt': 'true'
    }
    
    for filename, default_content in config_files.items():
        path = os.path.join(config_dir, filename)
        if not os.path.exists(path):
            with open(path, 'w') as f:
                f.write(default_content)
                if verbose:
                    print(f"Created {path} with content {default_content}")

# Load supported extensions from config
def load_supported_extensions(extension_path, verbose=False):
    try:
        with open(extension_path, 'r') as f:
            return {line.strip().lower() for line in f if line.strip()}
    except FileNotFoundError:
        if verbose:
            print(f"Error: Extensions config file not found at {extension_path}")
        sys.exit(1)

# Load output extension from config
def load_output_format(format_path, verbose=False):
    try:
        with open(format_path, 'r') as f:
            outputs = [line.strip().lower() for line in f if line.strip()]
            if not outputs:
                if verbose:
                    print(f"Could not load output format from {format_path}")
                sys.exit(1)
            else:
                return outputs[0]
    except FileNotFoundError:
        if verbose:
            print(f"Error: Output extension file not found at {format_path}")
        sys.exit(1)

# Load recursive search policy
def load_recursive_policy(recursive_path, verbose=False):
    try:
        with open(recursive_path, 'r') as f:
            value = f.read().strip().lower()
            if value in ['yes', 'true']:
                return True
            return False
    except FileNotFoundError:
        if verbose:
            print(f"Error: Recursive config file not found at {recursive_path}")
        sys.exit(1)

def get_content_type(path):
    # Check if the path is a local file
    if os.path.isfile(path):
        # Determine content type based on file content
        content_type, _ = mimetypes.guess_type(path)
        if content_type:
            return content_type

    # Check if the path is a remote URL
    parsed_url = urlparse(path)
    if parsed_url.scheme in ('http', 'https'):
        stripped_url = parsed_url._replace(query='').geturl()
        try:
            response = requests.head(path, allow_redirects=True)
            if response.status_code == 200:
                return response.headers.get('Content-Type')
        except requests.RequestException:
            return None
    return None

def get_image_type(path):
    content_type = get_content_type(path)
    types = content_type.split('/')
    return types[-1]

def extract_filename_from_url(url):
    # Check if the URL has a protocol; if not, assume 'http'
    if not re.match(r'https?://', url):
        url = f'http://{url}'

    # Parse the URL
    parsed_url = urlparse(url)

    # Get the path and strip GET parameters
    filename = parsed_url.path.split('?')[0]

    # Return the filename without leading slashes
    return filename.lstrip('/')


def download_file(url, download_location, verbose=False):
    try:
        response = requests.get(url, stream=True)
        response.raise_for_status()  # Raise an error for bad responses

        # Get the filename from the URL
        filename = os.path.basename(url)
        file_path = os.path.join(download_location, filename)

        # Write to file
        with open(file_path, 'wb') as f:
            f.write(response.content)

        if verbose:
            print(f"Downloaded: {file_path}")
        return file_path
    except Exception as e:
        if verbose:
            print(f"Error downloading {url}: {e}")
        return None

def check_file_type_and_dimensions(file_path, verbose=False):
    try:
        with Image.open(file_path) as img:
            width, height = img.size
            return img.format.lower(), (width, height)
    except Exception as e:
        if verbose:
            print(f"Error checking {file_path}: {e}")
        return None, None

def acquire_image(image_path, verbose=False, image_types=None):
    """
    Acquire an image from a local path or download it from a remote URL.

    :param image_path: Path to the image file (local or remote).
    :param verbose: Flag to enable verbose output.
    :param image_types: List of supported image types.
    :return: Image object if successful, None otherwise.
    """
    try:
        # Try to open the image locally
        img = Image.open(image_path)
        return img

    except Exception as local_e:
        # Try to open the image remotely if the local attempt fails
        if check_remote_file_content_type(image_path, image_types, verbose):
            try:
                response = requests.get(image_path, stream=True)
                response.raise_for_status()  # Raise an error for bad responses
                img = Image.open(response.raw)
                return img

            except Exception as remote_e:
                if verbose:
                    print(f"Remote open failed for {image_path}: {remote_e}")

    return None  # Both attempts failed

# Split the image into 4 quadrants (assuming a 2x2 grid)
def split_image(image_path, output_dir, output_format, verbose=False, image_types=None):
    """
    Split the image into four quadrants and save them.

    :param image_path: Path to the image file (local or remote).
    :param output_dir: Directory to save the output images.
    :param output_format: Desired output format.
    :param verbose: Flag to enable verbose output.
    :param image_types: List of supported image types.
    :return: True if processing was successful, False otherwise.
    """
    img = acquire_image(image_path, verbose, image_types)
    
    if img is None:
        return False  # Image acquisition failed

    width, height = img.size

    if width % 2 != 0 or height % 2 != 0:
        if verbose:
            print(f"Skipping {image_path}: dimensions not even")
        return False  # Skip if dimensions aren't even

    # Calculate split coordinates
    mid_x, mid_y = width // 2, height // 2
    quadrants = [
        img.crop((0, 0, mid_x, mid_y)),         # Top-left
        img.crop((mid_x, 0, width, mid_y)),     # Top-right
        img.crop((0, mid_y, mid_x, height)),    # Bottom-left
        img.crop((mid_x, mid_y, width, height)) # Bottom-right
    ]

    # Prepare output format
    #image_format = output_format if output_format != 'default' else get_image_format(image_path)
    if not output_format or output_format == 'default':
        output_format = get_image_type(image_path)
        if not output_format:
            return False
    if not output_format:
        if verbose:
            print(f"Skipping {image_path}: invalid image format")
        return False  # Skip if format isn't valid

    base_name = os.path.splitext(os.path.basename(image_path))[0]
    #base_name = extract_filename_from_url(base_name)
    for i, quadrant in enumerate(quadrants):
        try:
            output_file = os.path.join(output_dir, f"{base_name}_{i+1}.{output_format}")

            if not os.path.exists(output_file):
                quadrant.save(output_file, output_format.upper())
                if verbose:
                    print(f"{output_file}")
        except Exception as e:
            if verbose:
                print(f"Error occurred while processing {output_file}: {e}")
            return False

    return True

def check_remote_file_content_type(url, image_types, verbose=False):
    # Check if image_types is provided and is iterable
    if not image_types or not isinstance(image_types, (list, set)):
        if verbose:
            print(f"Invalid image types provided: {image_types}")
        return False

    # Construct the content types based on provided image types
    supported_extensions = [f"image/{img_type}" for img_type in image_types]
    
    # Check if the URL is valid by performing a HEAD request
    try:
        response = requests.head(url, allow_redirects=True)  # Perform a HEAD request
        response.raise_for_status()  # Raise an error for bad responses

        # Get the content type from the headers
        content_type = response.headers.get('content-type', '')

        # Check if the content type matches your supported extensions
        if any(content_type.lower().startswith(ext) for ext in supported_extensions):
            return True  # Supported content type
        else:
            if verbose:
                print(f"{url} is unsupported: {content_type}")
            return False  # Unsupported content type

    except requests.RequestException as e:
        if verbose:
            print(f"Error checking URL {url}: {e}")
        return False  # An error occurred while checking the URL

# Find all files matching the approved criteria
def find_qualified_files(input_paths, supported_extensions, recursive, output_dir, verbose=False):
    """
    Find qualified files based on supported extensions and dimensions.

    :param input_paths: List of input paths to search for files.
    :param supported_extensions: Set of supported image extensions.
    :param recursive: Boolean flag for recursive search.
    :param output_dir: Directory to save the output images.
    :param verbose: Flag to enable verbose output.
    :return: List of qualified files.
    """
    qualified_files = []
        #if os.path.samefile(image_path, config_dir):
    for input_path in input_paths:
        if os.path.isfile(input_path):
            ext = os.path.splitext(input_path)[1].lower()
            ext = ext[1:]
            if ext in supported_extensions:
                qualified_files.append(input_path)
        elif os.path.isdir(input_path) and not os.path.samefile(input_path, output_dir):
            if recursive:
                for root, _, files in os.walk(input_path):
                    for file in files:
                        file_path = os.path.join(root, file)
                        ext = os.path.splitext(file)[-1].lower()
                        if ext.startswith('.'):
                            ext = ext[1:]
                        if ext in supported_extensions:
                            qualified_files.append(file_path)
            else:
                for file in os.listdir(input_path):
                    file_path = os.path.join(input_path, file)
                    if os.path.isfile(file_path):
                        qualified_files.append(file_path)
        elif check_remote_file_content_type(input_path, supported_extensions, verbose):
            qualified_files.append(input_path)
    return qualified_files

def usage(msg, args=[]):
    print(f"TODO usage (given '{msg}', {args})")


def collision(x, y):
    if os.path.exists(x) and os.path.exists(y):
        if os.path.samefile(x, y):
            return True
    elif x == y:
        return True
    return False

def main():
    # Set up directories, files, and defaults
    args = sys.argv[1:]
    verbose = False
    inputs = []
    output = 'outputs'
    config_dir = 'config'

    while '-v' in args:
        args.remove('-v')
        verbose = True

    if '-o' in args:
        ind = args.index('-o')
        if ind == len(args):
            usage("A directory must follow '-o'", args)
            sys.exit(1)
        output = args[ind+1]
        # TODO this line will fail on some conditions, rewrite
        args = [x for x in args if x != '-o' and not collision(x, output)]
    else:
        output = args[0]
        # TODO rewrite this one too
        args = [x for x in args if not collision(x, output)]
    if verbose:
        print(f"Output path set to {output}; inputs: {args}")

    ensure_config_files(config_dir, verbose)

    extensions_path = os.path.join(config_dir, 'extensions.txt')
    output_format_path = os.path.join(config_dir, 'output_format.txt')
    recursive_path = os.path.join(config_dir, 'recursive.txt')

    supported_extensions = load_supported_extensions(extensions_path, verbose)
    output_format = load_output_format(output_format_path, verbose)
    recursive = load_recursive_policy(recursive_path, verbose)

    # Verify output directory
    if not verify_or_create_directory(output, verbose):
        print("Error: Output directory is not valid. Exiting.")
        sys.exit(1)

    # Find qualified files
    qualified_files = find_qualified_files(args, supported_extensions, recursive, output, verbose)

    # Split qualified images
    for image_path in qualified_files:
        split_image(image_path, output, output_format, verbose, supported_extensions)

if __name__ == "__main__":
    main()


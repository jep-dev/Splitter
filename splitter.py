import os
import sys
from PIL import Image
import argparse
import requests
import re
from urllib.parse import urlparse

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
        'output_location.txt': 'default',
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
                if verbose:
                    print("Running in recursive mode")
                return True
            else:
                if verbose:
                    print("Running in non-recursive mode")
                return False
    except FileNotFoundError:
        if verbose:
            print(f"Error: Recursive config file not found at {recursive_path}")
        sys.exit(1)

def get_content_type(path):
    # Check if the path is a local file
    if os.path.isfile(path):
        print(f"Path {path} is a file")
        # Determine content type based on file content
        content_type, _ = mimetypes.guess_type(path)
        if content_type:
            return content_type

    # Check if the path is a remote URL
    parsed_url = urlparse(path)
    if parsed_url.scheme in ('http', 'https'):
        #print(f"Path {path} is a url")
        # Strip GET parameters
        stripped_url = parsed_url._replace(query='').geturl()
        #print(f"Stripped url = {stripped_url}")
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

# Get the true file type of the image
#def get_image_format(image_path, verbose=False):
#    try:
#        if re.match(r'https?://', image_path):
#            if verbose:
#                print(f"### HERE (get_image_format) ###")
#            parsed_url = urlparse(url)
#            filename = parsed_url.path.split('?')[0]
#            filename = filename.lstrip('/')
#            ext = filename.split('.')[-1]
#            return ext
#        else:
#            print(f"### HERE ###")
#        with Image.open(image_path) as img:
#            f = img.format.lower()  # e.g., 'png', 'jpeg', etc.
#            if verbose:
#                print(f"{image_path} detected format: {format}")
#            return f
#    except Exception as e:
#        if verbose:
#            print(f"Error opening {image_path}: {e}")
#        return None

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
        if verbose:
            print(f"Local open passed for {image_path}")
        return img

    except Exception as local_e:
        if verbose:
            print(f"Local open failed for {image_path}: {local_e}")

        # Try to open the image remotely if the local attempt fails
        if check_remote_file_content_type(image_path, image_types, verbose):
            try:
                response = requests.get(image_path, stream=True)
                response.raise_for_status()  # Raise an error for bad responses
                img = Image.open(response.raw)
                if verbose:
                    print(f"Remote open passed for {image_path}")
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
        if verbose:
            print(f"Image {image_path} is 'None'")
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
        if not output_format and verbose:
            print(f"Found it?")
    if verbose:
        print(f"Image format: {output_format}")
    if not output_format:
        if verbose:
            print(f"Skipping {image_path}: invalid image format")
        return False  # Skip if format isn't valid
    elif verbose:
        print(f"Image {image_path} has valid image format")

    base_name = os.path.splitext(os.path.basename(image_path))[0]
    #base_name = extract_filename_from_url(base_name)
    for i, quadrant in enumerate(quadrants):
        try:
            print(f"Output dir = {output_dir}")
            output_file = os.path.join(output_dir, f"{base_name}_{i+1}.{output_format}")

            if not os.path.exists(output_file):
                quadrant.save(output_file, output_format.upper())
                if verbose:
                    print(f"Saved: {output_file}")
            else:
                if verbose:
                    print(f"Skipping {output_file}: already exists")
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
        if verbose:
            print(f"Content type for {url}: {content_type}")

        # Check if the content type matches your supported extensions
        if any(content_type.lower().startswith(ext) for ext in supported_extensions):
            if verbose:
                print(f"{url} is supported.")
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
    for input_path in input_paths:
        if os.path.isfile(input_path):
            ext = os.path.splitext(input_path)[1].lower()
            if ext in supported_extensions:
                qualified_files.append(input_path)
                if verbose:
                    print(f"Found file: {input_path}")
        elif os.path.isdir(input_path):
            for root, _, files in os.walk(input_path):
                for file in files:
                    file_path = os.path.join(root, file)
                    ext = os.path.splitext(file)[1].lower()
                    if ext in supported_extensions:
                        qualified_files.append(file_path)
                        if verbose:
                            print(f"Found file: {file_path}")
                if not recursive:
                    break  # Stop searching after the first directory
        elif check_remote_file_content_type(input_path, supported_extensions, verbose):
            qualified_files.append(input_path)
    return qualified_files

def main():
    # Set up argument parser
    parser = argparse.ArgumentParser(description='Split 2x2 image grids into quadrants.')
    parser.add_argument('inputs', nargs='+', help='Input file paths or URLs.')
    parser.add_argument('-o', '--output', default='outputs', help='Output directory (default: outputs).')
    parser.add_argument('-v', '--verbose', action='store_true', help='Enable verbose output.')
    
    args = parser.parse_args()

    # Set up directories and files
    config_dir = 'config'
    ensure_config_files(config_dir, args.verbose)

    extensions_path = os.path.join(config_dir, 'extensions.txt')
    output_format_path = os.path.join(config_dir, 'output_format.txt')
    recursive_path = os.path.join(config_dir, 'recursive.txt')

    supported_extensions = load_supported_extensions(extensions_path, args.verbose)
    output_format = load_output_format(output_format_path, args.verbose)
    recursive = load_recursive_policy(recursive_path, args.verbose)

    # Verify output directory
    if not verify_or_create_directory(args.output, args.verbose):
        print("Error: Output directory is not valid. Exiting.")
        sys.exit(1)

    # Find qualified files
    qualified_files = find_qualified_files(args.inputs, supported_extensions, recursive, args.output, args.verbose)
    print(f"Qualified files: {len(qualified_files)}")

    # Split qualified images
    for image_path in qualified_files:
        split_image(image_path, args.output, output_format, args.verbose, supported_extensions)
        print(f"Qualified file: {image_path}")

if __name__ == "__main__":
    main()


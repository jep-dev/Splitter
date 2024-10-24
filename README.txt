# Setup
git clone https://github.com/jep-dev/Splitter splitter
cd splitter
pip install -r requirements.txt

# Configuration
`config/download_location.txt` Temporary location for downloads
`config/extensions.txt` Supported file/types (add bmp/tiff/etc. as necessary)
`config/output_format.txt` Output extension override; 'default' to preserve
`config/output_location.txt` Directory for split images
`config/recursive.txt` Recursive file discovery policy (true/false or yes/no)

# Usage
`python3 splitter.py input1 input2 -o outputdir` where inputs might be files or directories
`python3 splitter.py outputdir input3` (`-o` is optional when `outputdir` comes first)
`python3 splitter.py outputdir input4 -v` (verbose mode)

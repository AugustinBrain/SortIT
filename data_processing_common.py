import os
import re
import datetime  # Import datetime for date operations
from rich.progress import Progress, TextColumn, BarColumn, TimeElapsedColumn

def sanitize_filename(name, max_length=50, max_words=5):
    """Sanitize the filename by removing unwanted words and characters."""
    # Remove file extension if present
    name = os.path.splitext(name)[0]
    # Remove unwanted words and data type words
    name = re.sub(
        r'\b(jpg|jpeg|png|gif|bmp|txt|md|pdf|docx|xls|xlsx|csv|ppt|pptx|image|picture|photo|this|that|these|those|here|there|'
        r'please|note|additional|notes|folder|name|sure|heres|a|an|the|and|of|in|'
        r'to|for|on|with|your|answer|should|be|only|summary|summarize|text|category)\b',
        '',
        name,
        flags=re.IGNORECASE
    )
    # Remove non-word characters except underscores
    sanitized = re.sub(r'[^\w\s]', '', name).strip()
    # Replace multiple underscores or spaces with a single underscore
    sanitized = re.sub(r'[\s_]+', '_', sanitized)
    # Convert to lowercase
    sanitized = sanitized.lower()
    # Remove leading/trailing underscores
    sanitized = sanitized.strip('_')
    # Split into words and limit the number of words
    words = sanitized.split('_')
    limited_words = [word for word in words if word]  # Remove empty strings
    limited_words = limited_words[:max_words]
    limited_name = '_'.join(limited_words)
    # Limit length
    return limited_name[:max_length] if limited_name else 'untitled'

def process_files_by_date(file_paths, output_path, dry_run=False, silent=False, log_file=None):
    """Process files to organize them by date."""
    operations = []
    for file_path in file_paths:
        # Get the modification time
        mod_time = os.path.getmtime(file_path)
        # Convert to datetime
        mod_datetime = datetime.datetime.fromtimestamp(mod_time)
        year = mod_datetime.strftime('%Y')
        month = mod_datetime.strftime('%B')  # e.g., 'January', or use '%m' for month number
        # Create directory path
        dir_path = os.path.join(output_path, year, month)
        # Prepare new file path
        new_file_name = os.path.basename(file_path)
        new_file_path = os.path.join(dir_path, new_file_name)
        # Decide whether to use hardlink or symlink
        link_type = 'hardlink'  # Assume hardlink for now
        # Record the operation
        operation = {
            'source': file_path,
            'destination': new_file_path,
            'link_type': link_type,
        }
        operations.append(operation)
    return operations

def process_files_by_type(file_paths, output_path, dry_run=False, silent=False, log_file=None):
    """Process files to organize them by type, with extensive categorization.
    Categories with only one subcategory will store files directly in the main category folder."""
    operations = []

    # Define comprehensive file extension categories
    file_categories = {
        # Images
        'images': {
            'raster_images': ['.jpg', '.jpeg', '.png', '.gif', '.bmp', '.tiff', '.tif', '.webp', '.heic', '.heif', '.raw', '.cr2', '.nef', '.arw'],
            'vector_images': ['.svg', '.ai', '.eps', '.cdr'],
            'photoshop': ['.psd', '.psb', '.xcf'],
            'icons': ['.ico', '.icns']
        },
        
        # Documents
        'documents': {
            'plain_text': ['.txt', '.md', '.markdown', '.rst', '.rtf', '.tex', '.log'],
            'word_processing': ['.doc', '.docx', '.odt', '.pages', '.wpd'],
            'spreadsheets': ['.xls', '.xlsx', '.xlsm', '.ods', '.numbers', '.csv', '.tsv'],
            'presentations': ['.ppt', '.pptx', '.odp', '.key'],
            'pdf': ['.pdf'],
            'ebooks': ['.epub', '.mobi', '.azw', '.azw3', '.fb2', '.djvu', '.cbr', '.cbz'],
            'technical_docs': ['.xml', '.xhtml', '.dtd', '.sgml', '.yaml', '.yml', '.json', '.toml']
        },
        
        # Audio
        'audio': {
            'music': ['.mp3', '.aac', '.flac', '.alac', '.wav', '.wma', '.ogg', '.opus'],
            'voice': ['.m4a', '.amr', '.aiff', '.aif', '.aifc'],
            'production': ['.mid', '.midi', '.aup', '.sesx', '.band']
        },
        
        # Video
        'video': {
            'common': ['.mp4', '.mov', '.avi', '.mkv', '.wmv', '.flv', '.webm', '.m4v', '.mpg', '.mpeg', '.3gp'],
            'professional': ['.mxf', '.r3d', '.braw', '.prproj', '.fcpx', '.dav']
        },
        
        # Archives
        'archives': {
            'common': ['.zip', '.rar', '.7z', '.tar', '.gz', '.bz2', '.xz', '.tgz', '.iso']
        },
        
        # Code
        'code': {
            'scripts': ['.py', '.js', '.php', '.rb', '.pl', '.sh', '.bash', '.ps1', '.bat', '.cmd'],
            'markup': ['.html', '.htm', '.css', '.scss', '.sass', '.less'],
            'compiled': ['.c', '.cpp', '.h', '.hpp', '.cs', '.java', '.go', '.rs', '.swift'],
            'data_science': ['.ipynb', '.r', '.rmd', '.jl'],
            'config': ['.ini', '.conf', '.cfg', '.properties']
        },
        
        # Databases and data
        'data': {
            'databases': ['.db', '.sqlite', '.sqlite3', '.mdb', '.accdb', '.sql', '.bak'],
            'data_formats': ['.dat', '.sav', '.bin', '.pkl', '.parquet', '.avro', '.orc']
        },
        
        # Executables and Installers
        'executables': {
            'programs': ['.exe', '.app', '.dmg', '.pkg', '.deb', '.rpm', '.msi', '.apk', '.ipa'],
            'libraries': ['.dll', '.so', '.dylib']
        },
        
        # 3D and Design files
        'design': {
            '3d_models': ['.obj', '.stl', '.fbx', '.blend', '.3ds', '.c4d', '.max'],
            'cad': ['.dwg', '.dxf', '.skp'],
            'design': ['.indd', '.sketch', '.fig', '.xd']
        },
        
        # Fonts and typography
        'fonts': {
            'font_files': ['.ttf', '.otf', '.woff', '.woff2', '.eot']
        },
        
        # Web-specific files
        'web': {
            'web_assets': ['.asp', '.aspx', '.jsp', '.php', '.htaccess', '.htpasswd', '.url', '.webloc']
        },
        
        # System files
        'system': {
            'system_files': ['.sys', '.tmp', '.cache', '.swp', '.bak', '.old', '.log', '.lnk', '.shortcut', '.plist']
        }
    }

    # Identify categories with only one subcategory
    single_subcategory_mains = []
    for main_category, subcategories in file_categories.items():
        if len(subcategories) == 1:
            single_subcategory_mains.append(main_category)

    # Create a flat mapping of extension to category for easy lookup
    extension_to_category = {}
    for main_category, subcategories in file_categories.items():
        for subcategory, extensions in subcategories.items():
            for ext in extensions:
                extension_to_category[ext] = (main_category, subcategory)

    for file_path in file_paths:
        # Exclude hidden files
        if os.path.basename(file_path).startswith('.'):
            continue

        # Get the file extension
        ext = os.path.splitext(file_path)[1].lower()

        # Determine category and subcategory
        if ext in extension_to_category:
            main_category, subcategory = extension_to_category[ext]
            
            # For categories with only one subcategory, use just the main category
            if main_category in single_subcategory_mains:
                folder_name = main_category
            else:
                folder_name = os.path.join(main_category, subcategory)
        else:
            # Default category for unknown extensions
            folder_name = 'others'

        # Create directory path
        dir_path = os.path.join(output_path, folder_name)
        
        # Prepare new file path
        new_file_name = os.path.basename(file_path)
        new_file_path = os.path.join(dir_path, new_file_name)
        
        # Decide whether to use hardlink or symlink
        link_type = 'hardlink'  # Assume hardlink for now
        
        # Record the operation
        operation = {
            'source': file_path,
            'destination': new_file_path,
            'link_type': link_type,
        }
        operations.append(operation)

    return operations

def compute_operations(data_list, new_path, renamed_files, processed_files):
    """Compute the file operations based on generated metadata."""
    operations = []
    for data in data_list:
        file_path = data['file_path']
        if file_path in processed_files:
            continue
        processed_files.add(file_path)

        # Prepare folder name and file name
        folder_name = data['foldername']
        new_file_name = data['filename'] + os.path.splitext(file_path)[1]

        # Prepare new file path
        dir_path = os.path.join(new_path, folder_name)
        new_file_path = os.path.join(dir_path, new_file_name)

        # Handle duplicates
        counter = 1
        original_new_file_name = new_file_name
        while new_file_path in renamed_files:
            new_file_name = f"{data['filename']}_{counter}" + os.path.splitext(file_path)[1]
            new_file_path = os.path.join(dir_path, new_file_name)
            counter += 1

        # Decide whether to use hardlink or symlink
        link_type = 'hardlink'  # Assume hardlink for now

        # Record the operation
        operation = {
            'source': file_path,
            'destination': new_file_path,
            'link_type': link_type,
            'folder_name': folder_name,
            'new_file_name': new_file_name
        }
        operations.append(operation)
        renamed_files.add(new_file_path)

    return operations  # Return the list of operations for display or further processing

def execute_operations(operations, dry_run=False, silent=False, log_file=None):
    """Execute the file operations."""
    total_operations = len(operations)

    with Progress(
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TimeElapsedColumn(),
        transient=True
    ) as progress:
        task = progress.add_task("Organizing Files...", total=total_operations)
        for operation in operations:
            source = operation['source']
            destination = operation['destination']
            link_type = operation['link_type']
            dir_path = os.path.dirname(destination)

            if dry_run:
                message = f"Dry run: would create {link_type} from '{source}' to '{destination}'"
            else:
                # Ensure the directory exists before performing the operation
                os.makedirs(dir_path, exist_ok=True)

                try:
                    if link_type == 'hardlink':
                        os.link(source, destination)
                    else:
                        os.symlink(source, destination)
                    message = f"Created {link_type} from '{source}' to '{destination}'"
                except Exception as e:
                    message = f"Error creating {link_type} from '{source}' to '{destination}': {e}"

            progress.advance(task)

            # Silent mode handling
            if silent:
                if log_file:
                    with open(log_file, 'a') as f:
                        f.write(message + '\n')
            else:
                print(message)
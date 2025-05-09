import sys
import os
import time
import datetime
import re
from collections import Counter
from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
                            QPushButton, QLabel, QRadioButton, QButtonGroup, QFileDialog, 
                            QTextEdit, QTabWidget, QGroupBox, QSplitter, QProgressBar, 
                            QMessageBox, QLineEdit, QFrame, QTreeWidget, QTreeWidgetItem)
from PyQt5.QtCore import Qt, QThread, pyqtSignal
from PyQt5.QtGui import QIcon, QFont, QColor, QPalette, QFontMetrics

# Import the required functions from the existing script
from file_utils import (
    display_directory_tree,
    collect_file_paths,
    separate_files_by_type,
    read_file_data
)

from data_processing_common import (
    compute_operations,
    execute_operations,
    process_files_by_date,
    process_files_by_type,
)

class WorkerThread(QThread):
    """Worker thread for background processing"""
    progress_signal = pyqtSignal(int)
    status_signal = pyqtSignal(str)
    finished_signal = pyqtSignal(list)  # For operations or analytics results
    
    def __init__(self, task_type, *args):
        super().__init__()
        self.task_type = task_type
        self.args = args
        
    def run(self):
        try:
            if self.task_type == "collect_files":
                input_path = self.args[0]
                self.status_signal.emit(f"Collecting files from {input_path}...")
                file_paths = collect_file_paths(input_path)
                self.status_signal.emit(f"Found {len(file_paths)} files.")
                self.finished_signal.emit(file_paths)
                
            elif self.task_type == "process_by_date":
                file_paths, output_path = self.args
                self.status_signal.emit("Processing files by date...")
                operations = process_files_by_date(file_paths, output_path, dry_run=True)
                self.status_signal.emit("Date-based operations prepared.")
                self.finished_signal.emit(operations)
                
            elif self.task_type == "process_by_type":
                file_paths, output_path = self.args
                self.status_signal.emit("Processing files by type...")
                operations = process_files_by_type(file_paths, output_path, dry_run=True)
                self.status_signal.emit("Type-based operations prepared.")
                self.finished_signal.emit(operations)
                
            elif self.task_type == "execute_operations":
                operations = self.args[0]
                self.status_signal.emit("Executing file operations...")
                total_ops = len(operations)
                
                for i, op in enumerate(operations):
                    execute_operations([op], dry_run=False, silent=True)
                    progress = int((i+1) / total_ops * 100)
                    self.progress_signal.emit(progress)
                    
                self.status_signal.emit("File operations completed.")
                self.finished_signal.emit([])
                
            elif self.task_type == "analytics":
                file_paths = self.args[0]
                self.status_signal.emit("Generating file analytics...")
                results = self.generate_file_analytics(file_paths)
                self.status_signal.emit("Analytics completed.")
                self.finished_signal.emit(results)
        except Exception as e:
            self.status_signal.emit(f"Error: {str(e)}")
            self.finished_signal.emit([])
    
    def generate_file_analytics(self, file_paths):
        """Generate analytics about the files in the directory."""
        # Initialize counters and stats
        extension_counter = Counter()
        size_by_type = {}
        total_size = 0
        oldest_file = {'path': None, 'date': datetime.datetime.now()}
        newest_file = {'path': None, 'date': datetime.datetime.min}
        largest_file = {'path': None, 'size': 0}
        text_stats = {'total_files': 0, 'total_words': 0, 'total_lines': 0}
        
        # Process each file
        for i, file_path in enumerate(file_paths):
            # Update progress every 10 files
            if i % 10 == 0:
                progress = int(i / len(file_paths) * 100)
                self.progress_signal.emit(progress)
                
            stats = self.get_file_stats(file_path)
            if not stats:
                continue
                
            # Update extension counter
            ext = stats['extension'] or 'no_extension'
            extension_counter[ext] += 1
            
            # Update size stats
            total_size += stats['size']
            if ext not in size_by_type:
                size_by_type[ext] = 0
            size_by_type[ext] += stats['size']
            
            # Check for oldest/newest files
            if stats['modified'] < oldest_file['date']:
                oldest_file = {'path': file_path, 'date': stats['modified']}
            if stats['modified'] > newest_file['date']:
                newest_file = {'path': file_path, 'date': stats['modified']}
                
            # Check for largest file
            if stats['size'] > largest_file['size']:
                largest_file = {'path': file_path, 'size': stats['size']}
                
            # Analyze text files
            if ext in ['.txt', '.md', '.py', '.js', '.html', '.css', '.json', '.xml', '.csv']:
                text_analysis = self.analyze_text_file(file_path)
                if text_analysis:
                    text_stats['total_files'] += 1
                    text_stats['total_words'] += text_analysis['word_count']
                    text_stats['total_lines'] += text_analysis['line_count']
        
        # Format results
        results = []
        results.append(f"Total files: {len(file_paths)}")
        results.append(f"Total size: {self.format_size(total_size)}")
        
        # Top file types
        results.append("\nTop file types:")
        for ext, count in extension_counter.most_common(10):
            ext_display = ext if ext != 'no_extension' else '(no extension)'
            results.append(f"  {ext_display}: {count} files ({self.format_size(size_by_type.get(ext, 0))})")
        
        # File age info
        if oldest_file['path']:
            results.append("\nFile age information:")
            results.append(f"  Oldest file: {os.path.basename(oldest_file['path'])} ({oldest_file['date'].strftime('%Y-%m-%d')})")
            results.append(f"  Newest file: {os.path.basename(newest_file['path'])} ({newest_file['date'].strftime('%Y-%m-%d')})")
        
        # Size information
        if largest_file['path']:
            results.append("\nSize information:")
            results.append(f"  Largest file: {os.path.basename(largest_file['path'])} ({self.format_size(largest_file['size'])})")
        
        # Text file statistics if available
        if text_stats['total_files'] > 0:
            results.append("\nText file statistics:")
            results.append(f"  Text files analyzed: {text_stats['total_files']}")
            results.append(f"  Total words: {text_stats['total_words']}")
            results.append(f"  Total lines: {text_stats['total_lines']}")
            if text_stats['total_files'] > 0:
                results.append(f"  Average words per file: {text_stats['total_words'] // text_stats['total_files']}")
        
        return results
    
    def get_file_stats(self, file_path):
        """Get basic statistics about a file."""
        try:
            stats = {}
            stats['size'] = os.path.getsize(file_path)
            stats['created'] = datetime.datetime.fromtimestamp(os.path.getctime(file_path))
            stats['modified'] = datetime.datetime.fromtimestamp(os.path.getmtime(file_path))
            stats['extension'] = os.path.splitext(file_path)[1].lower()
            return stats
        except Exception as e:
            return None
    
    def analyze_text_file(self, file_path):
        """Analyze content of a text file."""
        try:
            content = read_file_data(file_path)
            if content:
                word_count = len(re.findall(r'\w+', content))
                line_count = len(content.splitlines())
                char_count = len(content)
                return {
                    'word_count': word_count,
                    'line_count': line_count,
                    'char_count': char_count
                }
        except Exception:
            pass
        return None
    
    def format_size(self, size_in_bytes):
        """Format bytes into a readable format."""
        for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
            if size_in_bytes < 1024.0:
                return f"{size_in_bytes:.2f} {unit}"
            size_in_bytes /= 1024.0
        return f"{size_in_bytes:.2f} PB"

class FileOrganizerApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("File Organizer")
        self.setMinimumSize(1200, 850)  # Increased window size
        
        # Set app icon (if you have one)
        # self.setWindowIcon(QIcon("icon.png"))
        
        # Set application font
        self.app_font = QFont("Segoe UI", 10)  # Increased font size
        QApplication.instance().setFont(self.app_font)
        
        # Set dark theme
        self.setup_dark_theme()
        
        # Initialize variables
        self.input_path = ""
        self.output_path = ""
        self.file_paths = []
        self.current_operations = []
        
        # Create the main widget and layout
        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)
        self.main_layout = QVBoxLayout(self.central_widget)
        self.main_layout.setSpacing(15)  # Increased spacing between sections
        self.main_layout.setContentsMargins(20, 20, 20, 20)  # Increased margins
        
        # Create the UI elements
        self.create_path_section()
        self.create_operation_section()
        self.create_preview_section()
        self.create_status_section()
        
        # Connect signals
        self.setup_connections()
    
    def setup_dark_theme(self):
        """Setup dark theme for the application"""
        app = QApplication.instance()
        if app:
            # Set dark palette
            palette = QPalette()
            palette.setColor(QPalette.Window, QColor(35, 35, 35))
            palette.setColor(QPalette.WindowText, Qt.white)
            palette.setColor(QPalette.Base, QColor(25, 25, 25))
            palette.setColor(QPalette.AlternateBase, QColor(45, 45, 45))
            palette.setColor(QPalette.ToolTipBase, QColor(25, 25, 25))
            palette.setColor(QPalette.ToolTipText, Qt.white)
            palette.setColor(QPalette.Text, Qt.white)
            palette.setColor(QPalette.Button, QColor(45, 45, 45))
            palette.setColor(QPalette.ButtonText, Qt.white)
            palette.setColor(QPalette.BrightText, Qt.red)
            palette.setColor(QPalette.Link, QColor(42, 130, 218))
            palette.setColor(QPalette.Highlight, QColor(42, 130, 218))
            palette.setColor(QPalette.HighlightedText, Qt.white)
            app.setPalette(palette)
            
            # Set stylesheet for widgets with more modern look
            app.setStyleSheet("""
                QWidget {
                    background-color: #232323;
                    color: #ffffff;
                    font-size: 10pt;
                }
                QLabel {
                    color: #ffffff;
                    font-size: 10pt;
                }
                QPushButton {
                    background-color: #2d82b7;
                    color: white;
                    border: none;
                    padding: 8px 22px;
                    border-radius: 4px;
                    font-size: 10pt;
                    font-weight: bold;
                }
                QPushButton:hover {
                    background-color: #3498db;
                }
                QPushButton:pressed {
                    background-color: #1a5c8b;
                }
                QPushButton:disabled {
                    background-color: #444444;
                    color: #888888;
                }
                QRadioButton {
                    color: white;
                    spacing: 8px;
                    font-size: 10pt;
                }
                QRadioButton::indicator {
                    width: 18px;
                    height: 18px;
                    border-radius: 9px;
                }
                QRadioButton::indicator:checked {
                    background-color: #2d82b7;
                    border: 2px solid white;
                }
                QRadioButton::indicator:unchecked {
                    background-color: #232323;
                    border: 2px solid #2d82b7;
                }
                QProgressBar {
                    border: none;
                    border-radius: 3px;
                    background-color: #333333;
                    text-align: center;
                    color: white;
                    font-size: 10pt;
                    height: 20px;
                }
                QProgressBar::chunk {
                    background-color: #2d82b7;
                    border-radius: 3px;
                }
                QTextEdit {
                    background-color: #1a1a1a;
                    border: 1px solid #3a3a3a;
                    border-radius: 4px;
                    padding: 8px;
                    font-size: 10pt;
                    selection-background-color: #2d82b7;
                }
                QLineEdit {
                    background-color: #1a1a1a;
                    border: 1px solid #3a3a3a;
                    border-radius: 4px;
                    padding: 8px;
                    height: 30px;
                    font-size: 10pt;
                    selection-background-color: #2d82b7;
                }
                QGroupBox {
                    border: 1px solid #3a3a3a;
                    border-radius: 6px;
                    margin-top: 12px;
                    font-weight: bold;
                    font-size: 11pt;
                    padding: 15px;
                }
                QGroupBox::title {
                    subcontrol-origin: margin;
                    subcontrol-position: top center;
                    padding: 0 10px;
                    color: #3498db;
                }
                QTabWidget::pane {
                    border: 1px solid #3a3a3a;
                    border-radius: 4px;
                    background-color: #232323;
                }
                QTabBar::tab {
                    background-color: #2d2d2d;
                    border: 1px solid #3a3a3a;
                    border-bottom-color: #3a3a3a;
                    border-top-left-radius: 4px;
                    border-top-right-radius: 4px;
                    min-width: 12ex;
                    padding: 8px 15px;
                    font-size: 9pt;
                    font-weight: bold;
                }
                QTabBar::tab:selected {
                    background-color: #2d82b7;
                    color: white;
                }
                QTabBar::tab:!selected {
                    margin-top: 3px;
                    background-color: #353535;
                }
                QTreeWidget {
                    background-color: #1a1a1a;
                    alternate-background-color: #232323;
                    border: 1px solid #3a3a3a;
                    border-radius: 4px;
                    font-size: 10pt;
                    selection-background-color: #2d82b7;
                    selection-color: white;
                }
                QTreeWidget::item {
                    height: 30px;
                    border-bottom: 1px solid #2a2a2a;
                    padding-left: 5px;
                }
                QTreeWidget::item:selected {
                    background-color: #2d82b7;
                }
                QHeaderView::section {
                    background-color: #2d2d2d;
                    padding: 8px;
                    border: 1px solid #3a3a3a;
                    font-size: 10pt;
                    font-weight: bold;
                }
                QSplitter::handle {
                    background-color: #3a3a3a;
                    height: 2px;
                    width: 2px;
                }
                QScrollBar:vertical {
                    border: none;
                    background: #2d2d2d;
                    width: 12px;
                    margin: 15px 0 15px 0;
                    border-radius: 0px;
                }
                QScrollBar::handle:vertical {
                    background-color: #3a3a3a;
                    min-height: 30px;
                    border-radius: 6px;
                }
                QScrollBar::handle:vertical:hover {
                    background-color: #2d82b7;
                }
                QScrollBar::sub-line:vertical {
                    border: none;
                    background: none;
                    height: 15px;
                    subcontrol-position: top;
                    subcontrol-origin: margin;
                }
                QScrollBar::add-line:vertical {
                    border: none;
                    background: none;
                    height: 15px;
                    subcontrol-position: bottom;
                    subcontrol-origin: margin;
                }
                QScrollBar::up-arrow:vertical, QScrollBar::down-arrow:vertical {
                    background: none;
                }
                QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {
                    background: none;
                }
                QScrollBar:horizontal {
                    border: none;
                    background: #2d2d2d;
                    height: 12px;
                    margin: 0px 15px 0 15px;
                    border-radius: 0px;
                }
                QScrollBar::handle:horizontal {
                    background-color: #3a3a3a;
                    min-width: 30px;
                    border-radius: 6px;
                }
                QScrollBar::handle:horizontal:hover {
                    background-color: #2d82b7;
                }
                QScrollBar::sub-line:horizontal {
                    border: none;
                    background: none;
                    width: 15px;
                    subcontrol-position: left;
                    subcontrol-origin: margin;
                }
                QScrollBar::add-line:horizontal {
                    border: none;
                    background: none;
                    width: 15px;
                    subcontrol-position: right;
                    subcontrol-origin: margin;
                }
                QScrollBar::up-arrow:horizontal, QScrollBar::down-arrow:horizontal {
                    background: none;
                }
                QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal {
                    background: none;
                }
            """)
            
    
    def create_path_section(self):
        """Create the path selection section"""
        path_group = QGroupBox("Directory Selection")
        path_layout = QVBoxLayout(path_group)
        path_layout.setSpacing(12)  # Increased spacing
        path_layout.setContentsMargins(15, 20, 15, 15)  # Adjusted margins
        
        # Input path
        input_layout = QHBoxLayout()
        input_label = QLabel("Input Directory:")
        input_label.setMinimumWidth(120)  # Fixed width for alignment
        self.input_path_edit = QLineEdit()
        self.input_path_edit.setReadOnly(True)
        self.input_path_edit.setPlaceholderText("Select directory to organize")
        input_browse_btn = QPushButton("Browse")
        input_browse_btn.setFixedWidth(100)  # Fixed width button
        input_browse_btn.clicked.connect(self.browse_input_directory)
        
        input_layout.addWidget(input_label)
        input_layout.addWidget(self.input_path_edit, 1)
        input_layout.addWidget(input_browse_btn)
        
        # Output path
        output_layout = QHBoxLayout()
        output_label = QLabel("Output Directory:")
        output_label.setMinimumWidth(120)  # Fixed width for alignment
        self.output_path_edit = QLineEdit()
        self.output_path_edit.setReadOnly(True)
        self.output_path_edit.setPlaceholderText("Select directory for organized files")
        output_browse_btn = QPushButton("Browse")
        output_browse_btn.setFixedWidth(100)  # Fixed width button
        output_browse_btn.clicked.connect(self.browse_output_directory)
        
        output_layout.addWidget(output_label)
        output_layout.addWidget(self.output_path_edit, 1)
        output_layout.addWidget(output_browse_btn)
        
        path_layout.addLayout(input_layout)
        path_layout.addLayout(output_layout)
        
        self.main_layout.addWidget(path_group)
    
    def create_operation_section(self):
        """Create the operation selection section"""
        operation_group = QGroupBox("Operation Selection")
        operation_layout = QHBoxLayout(operation_group)
        operation_layout.setSpacing(20)  # Increased spacing
        operation_layout.setContentsMargins(15, 20, 15, 15)  # Adjusted margins
        
        # Radio buttons for operation types
        self.operation_group = QButtonGroup(self)
        
        # Create a container for radio buttons with horizontal layout
        radio_container = QWidget()
        radio_layout = QHBoxLayout(radio_container)
        radio_layout.setSpacing(30)  # More space between options
        radio_layout.setContentsMargins(0, 0, 0, 0)
        
        date_radio = QRadioButton("Organize by Date")
        type_radio = QRadioButton("Organize by Type")
        analytics_radio = QRadioButton("Generate Analytics")
        
        date_radio.setChecked(True)
        
        self.operation_group.addButton(date_radio, 1)
        self.operation_group.addButton(type_radio, 2)
        self.operation_group.addButton(analytics_radio, 3)
        
        radio_layout.addWidget(date_radio)
        radio_layout.addWidget(type_radio)
        radio_layout.addWidget(analytics_radio)
        radio_layout.addStretch(1)  # Add stretch to push buttons to the left
        
        operation_layout.addWidget(radio_container, 3)  # Give more space to radio buttons
        
        # Button container
        button_container = QWidget()
        button_layout = QHBoxLayout(button_container)
        button_layout.setSpacing(15)
        button_layout.setContentsMargins(0, 0, 0, 0)
        
        # Preview button
        self.preview_btn = QPushButton("Preview")
        self.preview_btn.setEnabled(False)
        self.preview_btn.clicked.connect(self.preview_operation)
        self.preview_btn.setCursor(Qt.PointingHandCursor)  # Hand cursor on hover
        
        # Execute button
        self.execute_btn = QPushButton("Execute")
        self.execute_btn.setEnabled(False)
        self.execute_btn.clicked.connect(self.execute_operation)
        self.execute_btn.setCursor(Qt.PointingHandCursor)  # Hand cursor on hover
        
        button_layout.addWidget(self.preview_btn)
        button_layout.addWidget(self.execute_btn)
        
        operation_layout.addWidget(button_container, 1)
        
        self.main_layout.addWidget(operation_group)
    
    def create_preview_section(self):
        """Create the preview section with tabs"""
        preview_group = QGroupBox("Preview")
        preview_layout = QVBoxLayout(preview_group)
        preview_layout.setSpacing(10)
        preview_layout.setContentsMargins(15, 20, 15, 15)  # Adjusted margins
        
        # Tab widget for different previews
        self.preview_tabs = QTabWidget()
        self.preview_tabs.setDocumentMode(True)  # More modern look
        
        # Tree preview tab
        self.tree_widget = QTreeWidget()
        self.tree_widget.setHeaderLabels(["Directory Structure"])
        self.tree_widget.setColumnCount(1)
        self.tree_widget.setAlternatingRowColors(True)  # Alternate row colors
        self.tree_widget.setAnimated(True)  # Animated expanding/collapsing
        self.tree_widget.setHeaderHidden(True)  # Show header
        self.tree_widget.setIndentation(30)  # Consistent indentation for hierarchy
        self.tree_widget.setUniformRowHeights(True)  # For performance
        
        # Use a dark stylesheet specifically for the tree widget header to fix white bar
        # Enhanced tree widget styling with better hierarchy indicators
        # Enhanced tree widget styling with better hierarchy indicators
        self.tree_widget.setStyleSheet("""
            QHeaderView::section {
                background-color: #2d2d2d;
                color: white;
                border: 1px solid #3a3a3a;
                padding: 6px;
            }
            QTreeView {
                show-decoration-selected: 1;
            }
            QTreeView::item {
                border: none;
                border-bottom: 1px solid #2a2a2a;
                padding-left: 5px;
            }
            QTreeView::branch {
                background: #1a1a1a;
            }
            QTreeView::branch:has-siblings:!adjoins-item {
                border-image: none;
                border-left: 1px solid #555555;
            }
            QTreeView::branch:has-siblings:adjoins-item {
                border-image: none;
                border-left: 1px solid #555555;
            }
            QTreeView::branch:!has-children:!has-siblings:adjoins-item {
                border-image: none;
                border-left: 1px solid #555555;
            }
            /* Custom styling for the collapse/expand arrows */
            QTreeView::branch:has-children:!has-siblings:closed,
            QTreeView::branch:closed:has-children:has-siblings {
                background-color: transparent;
                border-image: none;
                image: url(arrow.png);
            }
            QTreeView::branch:has-children:!has-siblings:closed,
            QTreeView::branch:closed:has-children:has-siblings {
                background-color: transparent;
                border-image: none;
                image: url(arrow.png);
                color: #aaaaaa;
            }
            QTreeView::branch:open:has-children:!has-siblings,
            QTreeView::branch:open:has-children:has-siblings {
                background-color: transparent;
                border-image: none;
                image: url(arrow_down.png);
                color: #aaaaaa;
            }
            QTreeView::branch:closed:has-children {
                border-image: none;
                image: url(arrow.png);
            }
            QTreeView::branch:open:has-children {
                border-image: none;
                image: url(arrow_down.png);
            }
            QTreeView::indicator {
                width: 13px;
                height: 13px;
            }
        """)
        
        # Operation preview tab
        self.operation_preview = QTextEdit()
        self.operation_preview.setReadOnly(True)
        
        # Analytics preview tab
        self.analytics_preview = QTextEdit()
        self.analytics_preview.setReadOnly(True)
        
        self.preview_tabs.addTab(self.tree_widget, "Directory Structure")
        self.preview_tabs.addTab(self.operation_preview, "Operations")
        self.preview_tabs.addTab(self.analytics_preview, "Analytics")
        
        preview_layout.addWidget(self.preview_tabs)
        self.main_layout.addWidget(preview_group, 1)  # Give this widget more space
    
    def create_status_section(self):
        """Create the status section with progress bar"""
        status_frame = QFrame()
        status_frame.setFrameShape(QFrame.StyledPanel)
        status_frame.setFrameShadow(QFrame.Sunken)
        status_layout = QHBoxLayout(status_frame)
        status_layout.setContentsMargins(15, 10, 15, 10)
        status_layout.setSpacing(15)
        
        # Status icon (could be added later)
        # status_icon = QLabel()
        # status_icon.setPixmap(QPixmap("status_icon.png").scaled(24, 24, Qt.KeepAspectRatio, Qt.SmoothTransformation))
        # status_layout.addWidget(status_icon)
        
        self.status_label = QLabel("Ready")
        self.status_label.setFont(QFont("Segoe UI", 10))
        
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setFixedHeight(12)  # Sleeker progress bar
        self.progress_bar.setTextVisible(False)  # Hide text on progress bar for cleaner look
        
        status_layout.addWidget(self.status_label, 1)
        status_layout.addWidget(self.progress_bar)
        
        self.main_layout.addWidget(status_frame)
    
    def setup_connections(self):
        """Setup signal connections"""
        # Connect operation selection buttons
        self.operation_group.buttonClicked.connect(self.on_operation_changed)
    
    def browse_input_directory(self):
        """Open a file dialog to select the input directory"""
        directory = QFileDialog.getExistingDirectory(self, "Select Input Directory")
        if directory:
            self.input_path = directory
            self.input_path_edit.setText(directory)
            self.update_buttons_state()
            
            # Start worker thread to collect files
            self.worker = WorkerThread("collect_files", directory)
            self.worker.status_signal.connect(self.update_status)
            self.worker.progress_signal.connect(self.update_progress)
            self.worker.finished_signal.connect(self.on_files_collected)
            self.worker.start()
    
    def browse_output_directory(self):
        """Open a file dialog to select the output directory"""
        directory = QFileDialog.getExistingDirectory(self, "Select Output Directory")
        if directory:
            self.output_path = directory
            self.output_path_edit.setText(directory)
            self.update_buttons_state()
    
    def update_buttons_state(self):
        """Update the state of preview and execute buttons"""
        self.preview_btn.setEnabled(bool(self.input_path))
        
        # For analytics, we don't need output path
        if self.operation_group.checkedId() == 3:
            self.execute_btn.setEnabled(bool(self.input_path) and bool(self.current_operations))
        else:
            self.execute_btn.setEnabled(bool(self.input_path) and bool(self.output_path) and bool(self.current_operations))
    
    def on_operation_changed(self, button):
        """Handle operation change"""
        self.current_operations = []
        self.operation_preview.clear()
        self.analytics_preview.clear()
        self.tree_widget.clear()
        
        # If analytics is selected, output path is not needed
        if self.operation_group.checkedId() == 3:
            self.output_path_edit.setEnabled(False)
        else:
            self.output_path_edit.setEnabled(True)
            
        self.update_buttons_state()
    
    def on_files_collected(self, file_paths):
        """Handle when files are collected"""
        self.file_paths = file_paths
        self.update_status(f"Found {len(file_paths)} files.")
        self.update_progress(0)
    
    def preview_operation(self):
        """Preview the selected operation"""
        if not self.file_paths:
            QMessageBox.warning(self, "Warning", "No files found in the input directory.")
            return
            
        operation_type = self.operation_group.checkedId()
        
        if operation_type == 1:  # By Date
            if not self.output_path:
                # Default to a subfolder of input path
                self.output_path = os.path.join(self.input_path, "organized_by_date")
                self.output_path_edit.setText(self.output_path)
                
            self.worker = WorkerThread("process_by_date", self.file_paths, self.output_path)
            self.worker.status_signal.connect(self.update_status)
            self.worker.progress_signal.connect(self.update_progress)
            self.worker.finished_signal.connect(self.on_operations_generated)
            self.worker.start()
            
        elif operation_type == 2:  # By Type
            if not self.output_path:
                # Default to a subfolder of input path
                self.output_path = os.path.join(self.input_path, "organized_by_type")
                self.output_path_edit.setText(self.output_path)
                
            self.worker = WorkerThread("process_by_type", self.file_paths, self.output_path)
            self.worker.status_signal.connect(self.update_status)
            self.worker.progress_signal.connect(self.update_progress)
            self.worker.finished_signal.connect(self.on_operations_generated)
            self.worker.start()
            
        elif operation_type == 3:  # Analytics
            self.worker = WorkerThread("analytics", self.file_paths)
            self.worker.status_signal.connect(self.update_status)
            self.worker.progress_signal.connect(self.update_progress)
            self.worker.finished_signal.connect(self.on_analytics_generated)
            self.worker.start()
    
    def on_operations_generated(self, operations):
        """Handle when operations are generated"""
        self.current_operations = operations
        self.update_buttons_state()
        
        # Update the operation preview
        if operations:
            preview_text = "Planned Operations:\n\n"
            for op in operations[:100]:  # Limit to 100 operations in preview
                src = os.path.basename(op['source'])
                dest = op['destination']
                preview_text += f"{src} -> {dest}\n"
                
            if len(operations) > 100:
                preview_text += f"\n... and {len(operations) - 100} more operations"
                
            self.operation_preview.setText(preview_text)
            
            # Update the tree preview
            self.update_tree_preview(operations)
        else:
            self.operation_preview.setText("No operations to perform.")
    
    def on_analytics_generated(self, results):
        """Handle when analytics are generated"""
        # We're treating analytics results as operations for button state
        self.current_operations = results if results else []
        self.update_buttons_state()
        
        if results:
            # Update the analytics preview
            self.analytics_preview.setText("\n".join(results))
            self.preview_tabs.setCurrentIndex(2)  # Switch to analytics tab
        else:
            self.analytics_preview.setText("No analytics results.")
    
    def update_tree_preview(self, operations):
        """Update the tree widget with the proposed directory structure"""
        self.tree_widget.clear()
        
        # Create a dictionary to represent the directory tree
        tree_dict = {}
        
        # Sort operations by destination path
        for op in operations:
            dest_path = op['destination']
            relative_path = os.path.relpath(dest_path, self.output_path)
            
            # Split the path into components
            components = relative_path.split(os.sep)
            
            # Build the tree structure
            current_dict = tree_dict
            for component in components[:-1]:  # All but the last component (which is the file)
                if component not in current_dict:
                    current_dict[component] = {}
                current_dict = current_dict[component]
                
            # Add the file to the current directory
            file_name = components[-1]
            if 'files' not in current_dict:
                current_dict['files'] = []
            current_dict['files'].append(file_name)
        
        # Build the tree widget
        root_item = QTreeWidgetItem(self.tree_widget, [os.path.basename(self.output_path)])
        # Style the root item (output directory) distinctively
        font = root_item.font(0)
        font.setBold(True)
        font.setPointSize(font.pointSize() + 1)  # Make it slightly larger
        root_item.setFont(0, font)
        root_item.setForeground(0, QColor("#3498db"))  # Green color for output root
        self.build_tree_widget(root_item, tree_dict)
        
        # Expand the root item
        root_item.setExpanded(True)
        self.tree_widget.expandItem(root_item)
        
        # Switch to the tree view tab
        self.preview_tabs.setCurrentIndex(0)
    
    def build_tree_widget(self, parent_item, tree_dict):
        """Recursively build the tree widget from the dictionary"""
        for key, value in tree_dict.items():
            if key == 'files':
                # Add files as leaf nodes
                for file_name in value:
                    file_item = QTreeWidgetItem(parent_item, [file_name])
                    # Use different color for files to distinguish from directories
                    file_item.setForeground(0, QColor("#bbbbbb"))
            else:
                # Add directories as internal nodes
                dir_item = QTreeWidgetItem(parent_item, [key])
                # Make directories bold and with a different color
                font = dir_item.font(0)
                font.setBold(True)
                dir_item.setFont(0, font)
                dir_item.setForeground(0, QColor("#bbbbbb"))
                
                self.build_tree_widget(dir_item, value)
                dir_item.setExpanded(True)
    
    def execute_operation(self):
        """Execute the selected operation"""
        operation_type = self.operation_group.checkedId()
        
        if operation_type == 3:  # Analytics
            # For analytics, just save the results to a file
            if self.current_operations:
                file_path, _ = QFileDialog.getSaveFileName(self, "Save Analytics Results", 
                                                          os.path.join(self.input_path, "file_analytics.txt"),
                                                          "Text Files (*.txt)")
                if file_path:
                    try:
                        with open(file_path, 'w') as f:
                            f.write("\n".join(self.current_operations))
                        QMessageBox.information(self, "Success", f"Analytics saved to {file_path}")
                    except Exception as e:
                        QMessageBox.critical(self, "Error", f"Failed to save analytics: {str(e)}")
        else:
            # For file operations, confirm with user
            reply = QMessageBox.question(self, "Confirm Operation", 
                                         f"Are you sure you want to organize {len(self.current_operations)} files?\n"
                                         f"This will copy files from {self.input_path} to {self.output_path}.",
                                         QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
            
            if reply == QMessageBox.Yes:
                # Ensure output directory exists
                os.makedirs(self.output_path, exist_ok=True)
                
                # Execute the operations
                self.worker = WorkerThread("execute_operations", self.current_operations)
                self.worker.status_signal.connect(self.update_status)
                self.worker.progress_signal.connect(self.update_progress)
                self.worker.finished_signal.connect(self.on_operations_completed)
                self.worker.start()
    
    def on_operations_completed(self, _):
        """Handle when operations are completed"""
        QMessageBox.information(self, "Success", "File organization completed successfully!")
        self.update_status("Operation completed.")
        self.update_progress(100)
    
    def update_status(self, message):
        """Update the status label"""
        self.status_label.setText(message)
    
    def update_progress(self, value):
        """Update the progress bar"""
        self.progress_bar.setValue(value)

def main():
    app = QApplication(sys.argv)
    window = FileOrganizerApp()
    window.show()
    sys.exit(app.exec_())

if __name__ == "__main__":
    main()
import sys
import os
from PyQt6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QLineEdit, QFileDialog, QListWidget, QMessageBox
)
from PyQt6.QtCore import Qt

from parser import parse_pdf, phone_numbers
from report_generator import generate_reports


class InvoiceAppGUI(QWidget):
    def __init__(self):
        super().__init__()
        self.init_ui()

    def init_ui(self):
        self.setWindowTitle("Vodafone Invoice Data Processor")
        self.resize(650, 450)

        # Enable drag and drop for the entire window
        self.setAcceptDrops(True)

        # Main Layout
        main_layout = QVBoxLayout()
        main_layout.setSpacing(12)

        # 1. File Selection Section
        file_label = QLabel("<b>Step 1: Drag & Drop PDFs Anywhere, or Browse</b>")
        main_layout.addWidget(file_label)

        # File list configuration
        self.drop_zone = QListWidget()
        self.drop_zone.setStyleSheet("""
            QListWidget {
                border: 2px dashed #3B82F6;
                border-radius: 6px;
                background-color: transparent; /* Matched to the window background */
                padding: 10px;
                font-size: 12px;
            }
        """)
        main_layout.addWidget(self.drop_zone)

        # File Action Buttons
        file_btn_layout = QHBoxLayout()
        self.btn_browse_files = QPushButton("Browse Files...")
        self.btn_browse_files.clicked.connect(self.browse_files)
        self.btn_clear_files = QPushButton("Clear Selection")
        self.btn_clear_files.clicked.connect(self.clear_files)

        file_btn_layout.addWidget(self.btn_browse_files)
        file_btn_layout.addWidget(self.btn_clear_files)
        main_layout.addLayout(file_btn_layout)

        # 2. Output Directory Section
        output_label = QLabel("<b>Step 2: Choose Report Output Destination</b>")
        main_layout.addWidget(output_label)

        output_layout = QHBoxLayout()
        self.output_edit = QLineEdit()
        self.output_edit.setPlaceholderText("No folder selected...")
        self.output_edit.setText("E:\\Dev\\invoice-data-app\\usage_reports")

        self.btn_browse_output = QPushButton("Browse...")
        self.btn_browse_output.clicked.connect(self.browse_output_dir)

        output_layout.addWidget(self.output_edit)
        output_layout.addWidget(self.btn_browse_output)
        main_layout.addLayout(output_layout)

        main_layout.addSpacing(10)

        # 3. Execution Section
        self.btn_process = QPushButton("Generate PDF Insight Reports")
        self.btn_process.setStyleSheet("""
            QPushButton {
                background-color: #3B82F6;
                color: white;
                font-weight: bold;
                font-size: 14px;
                padding: 10px;
                border-radius: 6px;
            }
            QPushButton:hover {
                background-color: #2563EB;
            }
        """)
        self.btn_process.clicked.connect(self.process_invoices)
        main_layout.addWidget(self.btn_process)

        self.setLayout(main_layout)

    # --- Window-Level Drag & Drop Handlers ---

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dragMoveEvent(self, event):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event):
        if event.mimeData().hasUrls():
            existing_items = [self.drop_zone.item(i).text() for i in range(self.drop_zone.count())]

            for url in event.mimeData().urls():
                file_path = url.toLocalFile()
                if file_path.lower().endswith('.pdf') and file_path not in existing_items:
                    self.drop_zone.addItem(file_path)

            event.acceptProposedAction()

    # --- Standard Button Actions ---

    def browse_files(self):
        files, _ = QFileDialog.getOpenFileNames(
            self, "Select PDF Invoices", "", "PDF Files (*.pdf)"
        )
        if files:
            existing_items = [self.drop_zone.item(i).text() for i in range(self.drop_zone.count())]
            for file in files:
                if file not in existing_items:
                    self.drop_zone.addItem(file)

    def clear_files(self):
        self.drop_zone.clear()

    def browse_output_dir(self):
        directory = QFileDialog.getExistingDirectory(self, "Select Output Directory")
        if directory:
            self.output_edit.setText(os.path.normpath(directory))

    def process_invoices(self):
        file_count = self.drop_zone.count()
        output_dir = self.output_edit.text().strip()

        if file_count == 0:
            QMessageBox.warning(self, "Missing Data", "Please drop or select at least one PDF invoice.")
            return
        if not output_dir:
            QMessageBox.warning(self, "Missing Destination", "Please specify an output folder.")
            return

        phone_numbers.clear()

        try:
            for i in range(file_count):
                pdf_path = self.drop_zone.item(i).text()
                parse_pdf(pdf_path)

            generate_reports(output_dir)

            QMessageBox.information(
                self, "Success!",
                f"Successfully parsed {file_count} file(s).\n\nReports generated in:\n{output_dir}"
            )

        except Exception as e:
            QMessageBox.critical(
                self, "Processing Error",
                f"An error occurred while compiling your data:\n\n{str(e)}"
            )


if __name__ == "__main__":
    app = QApplication(sys.argv)
    gui = InvoiceAppGUI()
    gui.show()
    sys.exit(app.exec())
# -*- coding: utf-8 -*-
"""
:author: Tim Häberlein
:version: 1.0
:date: 08.01.2025
:organisation: TU Dresden, FZM
"""

# -------- start import block ---------
import sys
import os
from PyQt6.QtWidgets import QApplication, QMainWindow, QPushButton, QLabel, QVBoxLayout, QHBoxLayout, QWidget, QMessageBox, QCheckBox
from PyQt6.QtCore import Qt
import subprocess
import threading

# -------- end import block ---------


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()

        self.setWindowTitle("Crawler Manager GUI")
        self.setGeometry(100, 100, 400, 300)

        # Create layout
        main_layout = QVBoxLayout()

        # Add checkboxes for crawlers
        self.checkboxes = {
            "TradeRepublic": QCheckBox("TradeRepublic Crawler"),
            "Amex": QCheckBox("Amex Crawler"),
            "AmazonVisa": QCheckBox("AmazonVisa Crawler"),
            "ArivaKurse": QCheckBox("ArivaKurse Crawler")
        }
        for cb in self.checkboxes.values():
            main_layout.addWidget(cb)

        # Create button to run selected crawlers
        self.run_button = QPushButton("Run Selected Crawlers")
        self.run_button.clicked.connect(self.run_crawlers)
        main_layout.addWidget(self.run_button)

        # Create label to show status
        self.status_label = QLabel("Idle")
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        main_layout.addWidget(self.status_label)

        # Set central widget
        container = QWidget()
        container.setLayout(main_layout)
        self.setCentralWidget(container)

    def run_crawlers(self):
        """Executes the selected crawlers."""
        selected_crawlers = [name for name, cb in self.checkboxes.items() if cb.isChecked()]

        if not selected_crawlers:
            QMessageBox.warning(self, "No Selection", "Please select at least one crawler to run.")
            return

        def run_crawler_instance(crawler_name):
            """Runs a specific crawler script as a subprocess."""
            try:
                self.status_label.setText(f"Running {crawler_name}...")

                # Subprocess commands for each crawler
                commands = {
                    "TradeRepublic": [".venv39\\Scripts\\python", "-m", "webcrawler.TradeRepublicCrawler.py"],
                    "Amex": ["python", "-m", "webcrawler.AmexCrawler"],
                    "AmazonVisa": ["python", "test.py"],
                    "ArivaKurse": ["python", "-m", "webcrawler.ArivaCrawler"]
                }

                if crawler_name not in commands:
                    raise ValueError(f"Unknown crawler: {crawler_name}")

                # Run the subprocess
                print(commands[crawler_name])
                print(os.getcwd())
                process = subprocess.run(commands[crawler_name], capture_output=True, text=True)

                # Show output in a message box
                QMessageBox.information(self, f"Output: {crawler_name}", process.stdout)
                self.status_label.setText("Idle")

            except Exception as e:
                self.status_label.setText("Error")
                QMessageBox.critical(self, "Error", f"Error in {crawler_name}: {str(e)}")

        # Start each selected crawler in its own thread
        for crawler_name in selected_crawlers:
            thread = threading.Thread(target=run_crawler_instance, args=(crawler_name,))
            thread.start()

if __name__ == "__main__":
    app = QApplication([])
    window = MainWindow()
    window.show()
    app.exec()



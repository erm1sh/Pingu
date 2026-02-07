"""Credits tab for Pingu."""
from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel
from PySide6.QtCore import Qt


class CreditsTab(QWidget):
    def __init__(self):
        super().__init__()
        layout = QVBoxLayout(self)

        title = QLabel("<b>Pingu – ICMP Host Monitor</b>")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)

        author = QLabel(
            'Created by <b>erm1sh</b><br>'
            '<a href="https://github.com/erm1sh">github.com/erm1sh</a><br>'
            '<a href="https://www.linkedin.com/in/erm1sh">linkedin.com/in/erm1sh</a>'
        )
        author.setAlignment(Qt.AlignmentFlag.AlignCenter)
        author.setOpenExternalLinks(True)

        blurb = QLabel(
            "Simple, async ICMP monitor with tray support, "
            "headless mode, logging and per-target outage tracking."
        )
        blurb.setWordWrap(True)
        blurb.setAlignment(Qt.AlignmentFlag.AlignCenter)

        layout.addWidget(title)
        layout.addWidget(author)
        layout.addWidget(blurb)
        layout.addStretch()


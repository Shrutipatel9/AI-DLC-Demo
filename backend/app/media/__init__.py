"""MediaStore: private storage for photos and, later, generated images and PDFs (U4; US1.10).

Files are never public (ADR-009): they live in a private directory behind the FileStorage
port and are served only by the owner-checked ``GET /media/{fileId}``. Other modules import
only :mod:`app.media.public`.
"""

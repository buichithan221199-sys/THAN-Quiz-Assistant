THAN Quiz Assistant v1.0.1 - PDF packaging fix

Fixed BUILD_WINDOWS.bat to include PyMuPDF and fitz package resources, including layout YAML files.

Steps:
1. Extract the ZIP to a new folder.
2. Run BUILD_WINDOWS.bat on Windows with internet access.
3. Launch dist\THAN Quiz Assistant.exe.
4. Import a PDF to test.

This ZIP contains source and a Windows build script, not a prebuilt EXE.
OCR also requires Tesseract installed with Vietnamese language data.

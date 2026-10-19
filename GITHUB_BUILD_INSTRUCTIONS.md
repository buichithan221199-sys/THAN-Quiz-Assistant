# THAN Quiz Assistant v1.0.1 - GitHub Windows build

1. Create a PRIVATE repository named THAN-Quiz-Assistant on GitHub (do not initialize with README).
2. Extract this ZIP. On the repository page select **uploading an existing file**; upload all root files AND the `.github/workflows/build-windows.yml` file (GitHub web may not preserve hidden folders in some upload flows; use the GitHub web editor to create the workflow path if needed).
3. Commit to main. Open Actions > Build Windows EXE > Run workflow (or wait for push trigger).
4. Once green, open the run > Artifacts > download THAN-Quiz-Assistant-v1.0.1-Windows, extract and launch EXE.

The EXE is NOT built yet. It must be built by GitHub Actions on Windows. Windows SmartScreen may warn about unsigned apps. OCR also requires Tesseract OCR with Vietnamese language data installed on the Windows PC; PyInstaller does not bundle Tesseract itself.

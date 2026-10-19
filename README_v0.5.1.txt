THAN Quiz Assistant v0.5.1 - OCR choice parsing fix

Fixed: radio buttons recognized as O, 0, ©, ® were previously included in the question stem, lowering question matching accuracy. Choices are now separated and trailing OCR counters ignored. Vietnamese OCR vie+eng remains enabled.

Install: close existing app, extract ZIP, run SETUP_ONE_CLICK.bat. Existing data in %APPDATA%\ThanQuizAssistant is not intentionally deleted.

Testing: Python unit tests including screenshot-derived OCR sample pass. Not yet tested interactively on Windows.

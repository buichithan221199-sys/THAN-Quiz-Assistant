THAN Quiz Assistant v0.6.3 — PDF answer-key parser fix

- Supports answer key format: Đáp án đúng: B - B. Sai
- Supports multi-answer: Đáp án đúng: A, B, C - A. ...; B. ...; C. ...
- PDF questions can be in a different order from website questions.
- Reimporting same PDF refreshes existing records rather than preserving broken old answers.
- Verified parsing of all 26 questions in Quiz26_Answers.pdf (0 unresolved).

INSTALL: close app, run SETUP_ONE_CLICK.bat, then open app and IMPORT Quiz26_Answers.pdf again.
IMPORTANT: Matching depends on OCR quality; low confidence will remain unverified, never guess.

"""Regression tests: no silent loss of numbered questions or repeated stems."""
from app import parse_pdf_questions
def test_24():
    blocks=[]
    for n in range(1,25):
        stem="Theo Kinh Thánh Tân Ước, hãy ghép những phước hạnh của sự giải cứu?" if n in (5,10,18,23) else f"Nội dung câu hỏi số {n}?"
        blocks.append(f"Câu {n}. {stem}\nA. Đáp án A\nB. Đáp án B\nC. Đáp án C\nĐÁP ÁN ĐÚNG: B. Đáp án B")
    rows,unresolved=parse_pdf_questions("\n\n".join(blocks))
    assert len(rows)==24,(len(rows),unresolved)
    assert all(row['answers']==['Đáp án B'] for row in rows)
    assert len(unresolved)==0,unresolved
    assert len({row['question'] for row in rows})<24,"Fixture must contain repeated questions"
if __name__=='__main__':
    test_24()
    print("PASS: 24/24 questions, 24/24 answers; repeated question text preserved")

def test_26_alternate_layout():
    blocks=[]
    for n in range(1,27):
        blocks.append(f"Câu {n}. Bài học này giải thích vấn đề số {n}?\nA. Nội dung thứ nhất\nB. Nội dung thứ hai\nC. Nội dung thứ ba\nĐáp án đúng: C - C. Nội dung thứ ba")
    rows,unresolved=parse_pdf_questions("\n\n".join(blocks))
    assert len(rows)==26,(len(rows),unresolved)
    assert len([x for x in rows if x['answers']])==26
    assert all(x['answer_letters']==['C'] for x in rows)
    print("PASS: 26/26 alternate-format questions and answers")
if __name__=='__main__':
    test_26_alternate_layout()

def test_real_uploaded_pdf_text():
    from pathlib import Path
    import re
    content=Path(__file__).parent.joinpath('tests','real_24_questions.txt').read_text(encoding='utf-8')
    rows,unresolved=parse_pdf_questions(content)
    assert len(rows)==24, f"REAL PDF: parsed {len(rows)} instead of 24; unresolved={unresolved}"
    assert len([r for r in rows if r['answers']])==24, "REAL PDF: missing answer(s)"
    expected=re.findall(r'(?m)^ĐÁP ÁN ĐÚNG:\\s*([A-Z])\\.',content)
    assert len(expected)==24, f"REAL PDF fixture has {len(expected)} answer labels"
    for i,(row,letter) in enumerate(zip(rows,expected),1):
        assert row['answer_letters']==[letter], f"Question {i}: expected {letter}, got {row['answer_letters']}"
    print("PASS: REAL uploaded PDF text: 24/24 questions and exact answer letters")
if __name__=='__main__':
    test_real_uploaded_pdf_text()

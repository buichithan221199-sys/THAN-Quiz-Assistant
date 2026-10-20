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

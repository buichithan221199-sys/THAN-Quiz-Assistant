import unittest
from app import clean_answer_text, option_similarity, extract_question_and_options
class AnswerDisplayTests(unittest.TestCase):
 def test_repeated_pdf_label(self):
  self.assertEqual(clean_answer_text('B - B. Sai'),'Sai')
 def test_reordered_options(self):
  choices=['Sai','Đúng']
  self.assertEqual(max(range(len(choices)),key=lambda i:option_similarity('B - B. Sai',choices[i])),0)
 def test_multiple_labels(self):
  self.assertEqual(clean_answer_text('C. Đúng'),'Đúng')
 def test_ocr(self):
  q,opts=extract_question_and_options('Câu hỏi 2 / 26\nĐúng hay sai? Đây là câu hỏi.\n© Sai\n© Đúng')
  self.assertEqual(opts,['Sai','Đúng'])
if __name__=='__main__':unittest.main()

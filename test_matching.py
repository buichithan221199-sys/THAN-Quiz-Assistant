import unittest
from app import extract_question_and_options, match_question, similarity

class TestMatching(unittest.TestCase):
 def setUp(self):
  self.question='Các trước giả Tân Ước có những phiên bản Cựu Ước sẵn có cho họ bằng những ngôn ngữ nào?'
  self.text='''Thời gian làm bài: 22:32
Câu hỏi 1/26
Các trước giả Tân Ước có những phiên bản Cựu Ước sẵn có
cho họ bằng những ngôn ngữ nào?
◉ Tiếng Hê-bơ-rơ và tiếng A-ram
◉ Tiếng A-ram và tiếng La-tinh
◉ Tiếng Hê-bơ-rơ và tiếng Hy Lạp'''
 def test_stem(self):
  q,opts=extract_question_and_options(self.text)
  self.assertEqual(q,self.question)
  self.assertEqual(len(opts),3)
 def test_match(self):
  records=[{'question':'Điều gì khác?','answers':['Khác']},{'question':self.question,'answers':['Tiếng Hê-bơ-rơ và tiếng Hy Lạp']}]
  self.assertGreater(match_question(self.text,records)[0][0],.99)
 def test_a_to_h(self):
  sample='Câu hỏi 2/26\nChọn đáp án\n'+ '\n'.join(f'{chr(65+i)}. Lựa chọn {i+1}' for i in range(8))
  q,opts=extract_question_and_options(sample)
  self.assertEqual(len(opts),8)
 def test_ocr_typo(self):
  self.assertGreater(similarity('Cac truoc gia Tan Uoc co nhung phien ban Cuu Uoc san co cho ho bang nhung ngon ngu nao',self.question),.8)


class TestScreenshotRegression(unittest.TestCase):
 def test_real_ocr_circle_as_o(self):
  text='''Các trước giả Tân Ước có những phiên bản Cựu Ước sẵn có
cho họ bằng những ngôn ngữ nào?
O Tiếng Hê-bơ-rơ và tiếng A-ram
O Tiếng A-ram và tiếng La-tinh
O Tiếng Hê-bơ-rơ và tiếng Hy Lạp
3'''
  stem,opts=extract_question_and_options(text)
  self.assertEqual(stem,'Các trước giả Tân Ước có những phiên bản Cựu Ước sẵn có cho họ bằng những ngôn ngữ nào?')
  self.assertEqual(len(opts),3)
  self.assertEqual(opts[-1],'Tiếng Hê-bơ-rơ và tiếng Hy Lạp')

if __name__=='__main__':unittest.main()

import csv, json, os, re, sys, threading, time, difflib, unicodedata, tkinter as tk
from tkinter import ttk, filedialog, messagebox
from pathlib import Path
from PIL import ImageFilter, ImageOps, ImageEnhance, Image, ImageTk

APP='THAN Quiz Assistant'
VERSION='1.0.11'
def asset_path(name):
 base=Path(getattr(sys,'_MEIPASS',Path(__file__).resolve().parent))
 return base/name
ROOT=Path(os.getenv('APPDATA',str(Path.home()))) / 'ThanQuizAssistant'
ROOT.mkdir(parents=True,exist_ok=True)
DB=ROOT/'questions.json'
CFG=ROOT/'settings.json'
try:
 import pyautogui as pg
except Exception: pg=None
try:
 import pytesseract
 from PIL import ImageEnhance,ImageOps
except ImportError: pytesseract=None

def norm(s):
 s=unicodedata.normalize('NFD',str(s).lower().replace('đ','d'))
 s=''.join(c for c in s if unicodedata.category(c)!='Mn')
 return re.sub(r'\s+',' ',re.sub(r'[^a-z0-9\s]',' ',s)).strip()

def _tokens(s):
 return norm(s).split()

def similarity(a,b):
 """OCR-tolerant score: character similarity plus fuzzy word alignment."""
 a,b=norm(a),norm(b)
 if not a or not b:return 0.0
 char=difflib.SequenceMatcher(None,a,b,autojunk=False).ratio()
 wa,wb=a.split(),b.split()
 def coverage(left,right):
  if not left or not right:return 0.0
  return sum(max(difflib.SequenceMatcher(None,x,y,autojunk=False).ratio() for y in right) for x in left)/len(left)
 word=(coverage(wa,wb)+coverage(wb,wa))/2
 return min(1.0,0.48*char+0.52*word)

# OCR can render radio circles as O, 0, ©, ®, or a Unicode circle.
CHOICE_MARKER=re.compile(r"^(?:[A-H][).:：-]\s*|[○◯◻□☐●◉◎◌☑✓•⊙©®◉◎]\s*|[O0o][.)]?\s+(?=[A-Za-zÀ-ỹ]))",re.I)
QUESTION_INDEX=re.compile(r"cau\s*hoi\s*\d+\s*(?:/|\s+)\s*\d+",re.I)

def extract_question_and_options(content):
 """Read the question stem only, separating radio/letter choices and UI debris."""
 lines=[x.strip() for x in content.splitlines() if x.strip()]
 start=next((i+1 for i,line in enumerate(lines) if QUESTION_INDEX.search(norm(line))),0)
 lines=lines[start:]
 stem=[];opts=[];in_choices=False
 for line in lines:
  plain=norm(line)
  if not plain or re.match(r"^(?:thoi gian lam bai|cau hoi\s*\d+)",plain):continue
  match=CHOICE_MARKER.match(line)
  if match:
   in_choices=True
   option=line[match.end():].strip()
   if option:opts.append(option)
  elif in_choices and opts:
   # OCR occasionally appends a stray counter (e.g. 3) after the choices.
   if re.fullmatch(r"\d{1,3}",line):continue
   if re.match(r"^(?:ket qua|tiep theo|quay lai)",plain):break
   opts[-1]+=' '+line
  elif not in_choices:stem.append(line)
 return ' '.join(stem).strip(),opts

def question_candidates(content):
 stem,_=extract_question_and_options(content)
 if not stem:return []
 return [stem]

def _stem_score(observed, reference):
 """Compare ONLY question stems, never answer choices; tolerate clipped OCR."""
 a,b=norm(observed),norm(reference)
 if not a or not b:return 0.0
 aw,bw=a.split(),b.split()
 if len(aw)<5:return 0.0
 # Longest shared consecutive run is a strong fingerprint of a question.
 matcher=difflib.SequenceMatcher(None,aw,bw,autojunk=False)
 run=max((m.size for m in matcher.get_matching_blocks()),default=0)
 common=sum(m.size for m in matcher.get_matching_blocks())
 coverage=common/max(1,min(len(aw),len(bw)))
 if run>=7 and coverage>=.55:
  return min(.995,.86+.012*min(run,10)+.03*coverage)
 if run>=5 and coverage>=.65:
  return min(.94,.79+.012*run+.035*coverage)
 return .65*similarity(a,b)+.35*coverage

def match_question(content,items):
 stem,options=extract_question_and_options(content)
 if not stem:return []
 ranked=[]
 for item in items:
  reference=item.get('question','')
  if not reference:continue
  score=_stem_score(stem,reference)
  # Reject a different question sharing a generic ending such as "đánh dấu mỗi câu".
  first_a=" ".join(norm(stem).split()[:9]);first_b=" ".join(norm(reference).split()[:9])
  prefix=similarity(first_a,first_b)
  score*= (.45+.55*prefix)
  # Option overlap is only a small tie-breaker; it cannot override the stem.
  pdf_opts=list((item.get('options') or {}).values())
  if options and pdf_opts:
   hits=sum(1 for x in options if max((option_similarity(x,y) for y in pdf_opts),default=0)>.78)
   score=min(.999,score+.008*min(hits,3))
  ranked.append((score,stem,item))
 return sorted(ranked,key=lambda x:x[0],reverse=True)

def clean_answer_text(answer):
 """Remove repeated PDF answer-key prefixes, e.g. 'B - B. Sai'."""
 answer=str(answer).strip()
 for _ in range(4):
  updated=re.sub(r'^\s*(?:[A-H]\s*[-.:)]+\s*)', '', answer, count=1, flags=re.I).strip()
  if updated==answer:break
  answer=updated
 return answer

def option_similarity(answer,option):
 answer=clean_answer_text(answer)
 if norm(answer)==norm(option):return 1.0
 return similarity(answer,option)

def load(p,default):
 try:return json.loads(p.read_text(encoding='utf-8'))
 except Exception:return default

def parse_options(text):
 return extract_question_and_options(text)

def parse_pdf_questions(text):
 """Flexible best-effort quiz parser. Never fabricate an answer key."""
 text=text.replace('\r\n','\n').replace('\r','\n')
 lines=[re.sub(r'\s+',' ',x).strip() for x in text.split('\n')]
 lines=[x for x in lines if x]
 start=re.compile(r'^(?:(?:câu(?: hỏi)?|question|q)\s*[#:.]?\s*\d+\s*[.):\-]?\s*|\d+\s*[.):]\s+(?=\S))',re.I)
 option=re.compile(r'^([A-Z])\s*[.):\-]\s*(.+)$',re.I)
 answer=re.compile(r'^(?:đáp\s*án(?:\s*đúng)?|đáp\s*án\s*chính\s*xác|answer(?:\s*key)?|correct\s*answer|đúng)\s*[:：\-]\s*(.*)$',re.I)
 keyline=re.compile(r'^(?:câu\s*)?(\d+)\s*[.):\-]\s*([A-H](?:\s*[,;/&+]\s*[A-H])*)\s*$',re.I)
 groups=[];current=[];key={}
 # Split on explicit numbered questions, or after answer followed by new stem.
 for line in lines:
  km=keyline.match(line)
  if km and not current:
   key[int(km.group(1))]=re.findall('[A-H]',km.group(2).upper());continue
  if start.match(line) and current:
   groups.append(current);current=[]
  current.append(line)
 if current:groups.append(current)
 # Fallback: unnumbered questions separated by options and/or answer lines.
 if len(groups)<=1:
  groups=[];current=[];seen_options=False;seen_answer=False
  for line in lines:
   om=option.match(line)
   am=answer.match(line)
   if current and not om and not am and (seen_answer or (seen_options and line.endswith('?'))):
    groups.append(current);current=[];seen_options=False;seen_answer=False
   current.append(line)
   seen_options|=bool(om);seen_answer|=bool(am)
  if current:groups.append(current)
 rows=[];unresolved=[]
 for group in groups:
  stem=[];opts={};raw=[];last=None;answer_mode=False
  for line in group:
   am=answer.match(line)
   if am:
    answer_mode=True;last=None;raw.append(am.group(1));continue
   if answer_mode:
    raw.append(line);continue
   om=option.match(line)
   if om and (stem or opts):
    last=om.group(1).upper();opts[last]=om.group(2);continue
   if last:opts[last]+=' '+line
   else:stem.append(line)
  question=' '.join(stem).strip()
  question=start.sub('',question,count=1).strip()
  if not question or not opts:
   unresolved.append(question[:100] or 'Không nhận diện được câu hỏi');continue
  raw_text=' '.join(raw).strip()
  raw_text=re.split(r'(?:giải thích|explanation|đối chiếu)\s*:',raw_text,flags=re.I)[0].strip()
  # Accept key letters only when clearly delimited; otherwise preserve literal answer text.
  labels=[]
  multi=re.match(r'^([A-Z](?:\s*[,;/&+]\s*[A-Z])+)(?:\s*[-:]\s*|$)',raw_text,re.I)
  labeled=re.match(r'^([A-Z])\s*[.):\-]\s*(.*)$',raw_text,re.I)
  if multi:labels=re.findall('[A-Z]',multi.group(1).upper())
  elif labeled:labels=[labeled.group(1).upper()]
  else:
   label_list=re.fullmatch(r'[A-H](?:\s*[,;/&+]\s*[A-H])*',raw_text,re.I)
   if label_list:labels=re.findall('[A-H]',raw_text.upper())
  answers=[opts[x] for x in labels if x in opts]
  if labels and len(answers)!=len(labels):answers=[]
  if not answers and raw_text and not labels:answers=[raw_text]
  number_match=re.search(r'(?:câu(?: hỏi)?|question|q)\s*[#:.]?\s*(\d+)',group[0],re.I)
  if not answers and number_match:
   for letter in key.get(int(number_match.group(1)),[]):
    if letter in opts:answers.append(opts[letter])
  rows.append({'question':question,'answers':answers,'answer_letters':labels if answers else [],
               'options':opts,'type':'multiple' if len(answers)>1 else 'single',
               'source':'PDF','needs_review':not bool(answers)})
  if not answers:unresolved.append(question[:100])
 return rows,unresolved

def read_pdf(path):
 import fitz
 doc=fitz.open(path);parts=[];empty=[]
 for i,page in enumerate(doc):
  t=page.get_text('text',sort=True)
  if len(t.strip())<30:
   empty.append(i+1)
   if pytesseract:
    try:
     if os.name=='nt' and Path(r'C:\\Program Files\\Tesseract-OCR\\tesseract.exe').exists():
      pytesseract.pytesseract.tesseract_cmd=r'C:\\Program Files\\Tesseract-OCR\\tesseract.exe'
     pix=page.get_pixmap(matrix=fitz.Matrix(2,2),alpha=False)
     picture=Image.frombytes('RGB',[pix.width,pix.height],pix.samples)
     langs=pytesseract.get_languages(config='')
     lang='vie+eng' if 'vie' in langs else 'eng'
     t=pytesseract.image_to_string(picture,lang=lang,config='--psm 3')
    except Exception:
     pass
  parts.append(t)
 doc.close()
 return '\\n'.join(parts),empty

class App:
 def __init__(self,root):
  self.root=root;root.title(APP+' 1.0.11 — Windows');root.geometry('990x730');root.minsize(820,630)
  self.items=[];self.current_pdf=None;self.cfg=load(CFG,{'region':[0,0,620,760],'next':[335,575],'threshold':0.78,'tesseract':''})
  self.active=False;self.busy=False;self.mode=tk.StringVar(value='manual');self.status=tk.StringVar(value='Sẵn sàng');self.choice=tk.StringVar(value='');self.match=None
  self.cfg.setdefault('region',[0,0,620,760]);self.cfg.setdefault('threshold',0.78);self.cfg.setdefault('next',[335,575]);self.cfg.setdefault('tesseract','')
  self.last_ocr='';self.answer_window=None;self.answer_signature=None;self.capture_running=False;self.overlay_status=None;self.brand_icon=None;self.brand_logo=None;self.build()
 def save(self):CFG.write_text(json.dumps(self.cfg,ensure_ascii=False,indent=2),encoding='utf-8')
 def build(self):
  C={'bg':'#071225','panel':'#101f36','panel2':'#152941','blue':'#1677ff','text':'#eff6ff','muted':'#a9bfdc','green':'#20dfad'}
  self.root.configure(bg=C['bg'])
  self.root.geometry('1120x790');self.root.minsize(940,670)
  style=ttk.Style();style.theme_use('clam')
  style.configure('TFrame',background=C['bg'])
  style.configure('Panel.TFrame',background=C['panel'])
  style.configure('TLabel',background=C['bg'],foreground=C['text'],font=('Segoe UI',11))
  style.configure('Muted.TLabel',background=C['bg'],foreground=C['muted'],font=('Segoe UI',10))
  style.configure('Panel.TLabel',background=C['panel'],foreground=C['text'],font=('Segoe UI',11))
  style.configure('TButton',font=('Segoe UI',10,'bold'),padding=(14,11),background=C['panel2'],foreground=C['text'],borderwidth=0)
  style.map('TButton',background=[('active','#245078')])
  style.configure('Primary.TButton',background=C['blue'],foreground='white')
  style.map('Primary.TButton',background=[('active','#378dff')])
  style.configure('Stop.TButton',background='#84304e',foreground='white')
  style.configure('TNotebook',background=C['bg'],borderwidth=0)
  style.configure('TNotebook.Tab',background=C['panel'],foreground=C['muted'],padding=(20,12),font=('Segoe UI',11,'bold'))
  style.map('TNotebook.Tab',background=[('selected',C['blue'])],foreground=[('selected','white')])
  style.configure('Treeview',background=C['panel'],fieldbackground=C['panel'],foreground=C['text'],rowheight=33)
  style.configure('Treeview.Heading',background=C['panel2'],foreground=C['text'])
  style.configure('TRadiobutton',background=C['panel'],foreground=C['text'],font=('Segoe UI',10))
  try:
   logo=Image.open(asset_path('brand_logo.png'))
   self.brand_icon=ImageTk.PhotoImage(logo.resize((48,48),Image.Resampling.LANCZOS))
   self.root.iconphoto(True,self.brand_icon)
  except Exception: pass
  header=tk.Frame(self.root,bg=C['bg']);header.pack(fill='x',padx=24,pady=(20,12))
  if self.brand_icon is not None: tk.Label(header,image=self.brand_icon,bg=C['bg']).pack(side='left',padx=(0,12))
  tk.Label(header,text='◈  THAN QUIZ ASSISTANT',bg=C['bg'],fg=C['text'],font=('Segoe UI',23,'bold')).pack(side='left')
  tk.Label(header,text='  v1.0.11  •  Windows',bg=C['bg'],fg=C['muted'],font=('Segoe UI',10)).pack(side='left')
  tk.Label(header,textvariable=self.status,bg=C['bg'],fg=C['green'],font=('Segoe UI',11,'bold')).pack(side='right')
  tk.Label(self.root,text='Developed by Chi Than Bui   •   Smart OCR & PDF Matching',bg=C['bg'],fg=C['muted'],font=('Segoe UI',10,'italic')).pack(side='bottom',pady=(0,9))
  tabs=ttk.Notebook(self.root);tabs.pack(fill='both',expand=True,padx=22,pady=(0,16))
  quiz=ttk.Frame(tabs);bank=ttk.Frame(tabs);settings=ttk.Frame(tabs)
  tabs.add(quiz,text='⌂  Trang chính');tabs.add(bank,text='▤  Kho đáp án PDF');tabs.add(settings,text='⚙  Cài đặt')
  toolbar=ttk.Frame(quiz,style='Panel.TFrame');toolbar.pack(fill='x',padx=8,pady=(12,12))
  ttk.Radiobutton(toolbar,text='Thủ công',variable=self.mode,value='manual').pack(side='left',padx=5,pady=9)
  ttk.Radiobutton(toolbar,text='Tự động (luyện tập)',variable=self.mode,value='auto').pack(side='left',padx=5)
  for label,fn,sty in [('▣  Chọn vùng',self.choose_region,'TButton'),('◉  Xem vùng',self.preview_region,'TButton'),('Đọc OCR  F8',self.capture,'Primary.TButton'),('▶  Theo dõi',self.start,'Primary.TButton'),('■  DỪNG  F9',self.stop,'Stop.TButton')]:
   ttk.Button(toolbar,text=label,command=fn,style=sty).pack(side='left',padx=4,pady=6)
  ttk.Label(quiz,text='NỘI DUNG NHẬN DIỆN',font=('Segoe UI',12,'bold')).pack(anchor='w',padx=16,pady=(4,6))
  self.raw=tk.Text(quiz,height=12,bg=C['panel'],fg=C['text'],insertbackground='white',wrap='word',relief='flat',padx=18,pady=15,font=('Segoe UI',12),selectbackground=C['blue'])
  self.raw.pack(fill='both',expand=True,padx=16,pady=(0,10))
  actions=ttk.Frame(quiz);actions.pack(fill='x',padx=16,pady=(0,12))
  ttk.Button(actions,text='✦  Tìm đáp án trong PDF',command=self.lookup,style='Primary.TButton').pack(side='left',padx=(0,9))
  ttk.Button(actions,text='▣  Hiện đáp án lớn',command=self.show_last_answer).pack(side='left')
  self.process_var=tk.StringVar(value='● Sẵn sàng')
  self.root.attributes('-topmost',True)
  # Keep main window visible when interacting with the browser.
  self.root.bind('<Map>',lambda event:self.root.after_idle(lambda:self.root.attributes('-topmost',True)))
  tk.Label(actions,textvariable=self.process_var,bg=C['bg'],fg=C['green'],font=('Segoe UI',10,'bold')).pack(side='right',padx=12)
  ttk.Label(quiz,text='KẾT QUẢ ĐỐI CHIẾU',font=('Segoe UI',12,'bold')).pack(anchor='w',padx=16,pady=(0,6))
  self.result=tk.Text(quiz,height=7,bg='#092e2c',fg='#d4fff3',wrap='word',relief='flat',padx=18,pady=14,font=('Segoe UI',11))
  self.result.pack(fill='both',expand=True,padx=16,pady=(0,12));self.result.configure(state='disabled')
  bt=ttk.Frame(bank);bt.pack(fill='x',padx=14,pady=15)
  for label,fn in [('＋ Nhập PDF',self.import_pdf),('⇄ Thay PDF khác',self.replace_pdf),('Nhập CSV',self.import_csv),('Xuất CSV mẫu',self.export_template),('Thêm câu hỏi',self.add),('Xóa mục chọn',self.delete)]:
   ttk.Button(bt,text=label,command=fn).pack(side='left',padx=4)
  self.tree=ttk.Treeview(bank,columns=('q','a','type'),show='headings')
  for col,label,width in [('q','Câu hỏi',470),('a','Đáp án (nội dung)',340),('type','Loại',110)]:
   self.tree.heading(col,text=label);self.tree.column(col,width=width)
  self.tree.pack(fill='both',expand=True,padx=14,pady=10);self.refresh()
  ttk.Label(settings,text='Vùng chụp câu hỏi: X, Y, chiều rộng, chiều cao (pixel)').pack(anchor='w',padx=18,pady=(25,8))
  self.reg=tk.StringVar(value=', '.join(map(str,self.cfg['region'])));ttk.Entry(settings,textvariable=self.reg,width=55).pack(anchor='w',padx=18)
  ttk.Label(settings,text='Vị trí nút Tiếp theo: X, Y (dành cho cài đặt tương lai)').pack(anchor='w',padx=18,pady=(18,8))
  self.nxt=tk.StringVar(value=', '.join(map(str,self.cfg['next'])));ttk.Entry(settings,textvariable=self.nxt,width=55).pack(anchor='w',padx=18)
  ttk.Label(settings,text='Đường dẫn tesseract.exe (nếu OCR không tìm thấy)').pack(anchor='w',padx=18,pady=(18,8))
  self.tess=tk.StringVar(value=self.cfg.get('tesseract',''));ttk.Entry(settings,textvariable=self.tess,width=75).pack(anchor='w',padx=18)
  ttk.Button(settings,text='Lưu cài đặt',command=self.save_settings,style='Primary.TButton').pack(anchor='w',padx=18,pady=22)
  ttk.Label(settings,text='F8: đọc vùng • F9: dừng • Chỉ sử dụng chế độ tự động trong bài luyện tập được phép.\nỨng dụng không tự chọn đáp án hoặc tự nộp bài.',wraplength=750).pack(anchor='w',padx=18,pady=10)
  self.root.bind_all('<F8>',lambda e:self.capture());self.root.bind_all('<F9>',lambda e:self.stop())
 def choose_region(self):
  """Select two corners by polling cursor coordinates, never create a fullscreen overlay."""
  if not pg:
   messagebox.showerror('Thiếu thư viện','Cần pyautogui để chọn vùng.');return
  self.stop()
  if getattr(self,'corner_window',None) and self.corner_window.winfo_exists():
   self.corner_window.lift();return
  self.corners={}
  win=tk.Toplevel(self.root)
  self.corner_window=win
  win.title('Chọn vùng an toàn — không phủ màn hình')
  win.geometry('550x305')
  win.resizable(False,False)
  win.attributes('-topmost',True)
  ttk.Label(win,text='Chọn vùng bằng 2 góc (không có màn hình phủ)',font=('Segoe UI',12,'bold')).pack(anchor='w',padx=18,pady=(15,8))
  ttk.Label(win,text='1. Đặt vbtm-tm ở vị trí cố định, không che câu hỏi.\n2. Nhấn nút GÓC 1, di chuột tới góc TRÊN TRÁI trong 5 giây.\n3. Làm tương tự với GÓC 2 ở góc DƯỚI PHẢI.\n4. Nhấn Lưu vùng.',wraplength=505,justify='left').pack(anchor='w',padx=18)
  info=tk.StringVar(value='Chưa ghi nhận tọa độ nào.')
  ttk.Label(win,textvariable=info,wraplength=505).pack(anchor='w',padx=18,pady=12)
  bar=ttk.Frame(win);bar.pack(fill='x',padx=12)
  buttons=[]
  def close():
   self.corner_cancelled=True
   if win.winfo_exists():win.destroy()
   self.corner_window=None
  def record(which):
   self.corner_cancelled=False
   for btn in buttons:btn.configure(state='disabled')
   remaining=[5]
   def countdown():
    if self.corner_cancelled or not win.winfo_exists():return
    if remaining[0]>0:
     info.set(f'Đưa chuột tới góc {which} của câu hỏi. Ghi nhận sau {remaining[0]} giây...')
     remaining[0]-=1
     win.after(1000,countdown)
     return
    try:
     pos=pg.position()
     self.corners[which]=(int(pos.x),int(pos.y))
     info.set('Đã ghi: '+', '.join(f'Góc {k}: {v}' for k,v in sorted(self.corners.items())))
    except Exception as exc:info.set('Không đọc được chuột: '+str(exc))
    for btn in buttons:btn.configure(state='normal')
   countdown()
  b1=ttk.Button(bar,text='GÓC 1 (trên trái)',command=lambda:record(1));b1.pack(side='left',padx=5);buttons.append(b1)
  b2=ttk.Button(bar,text='GÓC 2 (dưới phải)',command=lambda:record(2));b2.pack(side='left',padx=5);buttons.append(b2)
  def commit():
   if len(self.corners)!=2:
    messagebox.showwarning('Thiếu góc','Cần ghi nhận đủ 2 góc.',parent=win);return
   x1,y1=self.corners[1];x2,y2=self.corners[2]
   region=[min(x1,x2),min(y1,y2),abs(x2-x1),abs(y2-y1)]
   if region[2]<120 or region[3]<70:
    messagebox.showwarning('Vùng quá nhỏ','Vùng phải rộng ít nhất 120px và cao ít nhất 70px.',parent=win);return
   self.cfg['region']=region;self.reg.set(', '.join(map(str,region)));self.save()
   self.status.set('Đã lưu vùng câu hỏi: '+str(region))
   close()
  ttk.Button(win,text='Lưu vùng',command=commit).pack(side='left',padx=20,pady=18)
  ttk.Button(win,text='Hủy',command=close).pack(side='right',padx=20,pady=18)
  win.protocol('WM_DELETE_WINDOW',close)
  win.bind('<Escape>',lambda e:close())
 def refresh(self):
  for x in self.tree.get_children():self.tree.delete(x)
  for i,r in enumerate(self.items):self.tree.insert('', 'end',iid=str(i),values=(r.get('question',''),'; '.join(r.get('answers',[])),r.get('type','single')))
 def add(self):
  win=tk.Toplevel(self.root);win.title('Thêm câu hỏi');win.geometry('600x390')
  ttk.Label(win,text='Câu hỏi:').pack(anchor='w');q=tk.Text(win,height=5);q.pack(fill='x')
  ttk.Label(win,text='Đáp án đúng (nhập nguyên văn; nhiều đáp án phân cách bằng |):').pack(anchor='w');a=tk.Text(win,height=4);a.pack(fill='x')
  def commit():
   question=q.get('1.0','end').strip();answers=[x.strip() for x in a.get('1.0','end').split('|') if x.strip()]
   if not question:messagebox.showerror('Thiếu dữ liệu','Cần nội dung câu hỏi.');return
   self.items.append({'question':question,'answers':answers,'type':'multiple' if len(answers)>1 else 'single'});self.refresh();win.destroy()
  ttk.Button(win,text='Lưu câu hỏi',command=commit).pack(pady=14)
 def delete(self):
  ids=sorted([int(i) for i in self.tree.selection()],reverse=True)
  if ids and messagebox.askyesno('Xóa','Xóa câu hỏi đã chọn?'):
   for i in ids:self.items.pop(i)
   self.refresh()
 def replace_pdf(self):
  if self.items and not messagebox.askyesno('Thay PDF khác','Xóa toàn bộ câu hỏi trong phiên hiện tại và chọn PDF khác?'):return
  self.import_pdf(replace=True)

 def import_pdf(self,replace=False):
  path=filedialog.askopenfilename(title='Chọn PDF câu hỏi và đáp án',filetypes=[('PDF','*.pdf')])
  if not path:return
  try:
   text,empty=read_pdf(path)
   rows,unresolved=parse_pdf_questions(text)
   if not rows:
    messagebox.showwarning('Chưa nhập được',f'Không nhận diện được câu hỏi trong PDF.\\nCác trang ít văn bản: {empty}\\nHãy kiểm tra PDF hoặc dùng CSV.');return
   with_answers=sum(bool(row.get('answers')) for row in rows)
   numbered=[int(x) for x in re.findall(r'(?im)^\\s*Câu\\s+(\\d+)\\s*[.):]',text)]
   expected=set(numbered)
   if expected and len(rows)!=len(expected):
    messagebox.showwarning('PDF chưa nhận diện đủ',f'Tài liệu có {len(expected)} câu đánh số, nhưng chỉ nhận diện {len(rows)} câu.\\nỨng dụng sẽ KHÔNG âm thầm nhập thiếu.\\nVui lòng gửi file để kiểm tra hoặc chọn tài liệu khác.')
    return
   preview='\\n'.join(f'{row["question"][:85]} => {(" | ".join(row["answers"]) if row["answers"] else "[CHƯA CÓ ĐÁP ÁN]")[:90]}' for row in rows[:6])
   if not messagebox.askyesno('Xem trước PDF',f'Nhận diện {len(rows)} câu hỏi; {with_answers} câu có đáp án, {len(rows)-with_answers} câu cần kiểm tra.\\nCác trang cần OCR: {empty}\\n\\n{preview}\\n\\nDùng bộ câu hỏi này?'):return
   if replace:self.items.clear()
   # Keep each numbered question separate; similar wording is not proof of duplication.
   added=updated=0
   before=len(self.items)
   self.items.extend(rows);added=len(self.items)-before
   if added!=len(rows):
    messagebox.showerror('Lỗi kiểm đếm',f'Đã nhận diện {len(rows)} câu nhưng chỉ thêm {added} câu. Vui lòng báo lỗi.');return
   self.current_pdf=path
   self.match=None;self.last_verified=None
   self.refresh()
   self.status.set(f'PDF: {Path(path).name} — {len(self.items)} câu')
   messagebox.showinfo('Đã nhập PDF',f'Phiên bản: {VERSION}\\nTệp: {Path(path).name}\\nPDF có {len(expected) if expected else "không xác định"} câu đánh số.\\nBộ đọc nhận diện: {len(rows)} câu.\\nĐã thêm vào kho: {added} câu.\\nTổng câu trong kho: {len(self.items)}.\\n{with_answers} câu có đáp án; {len(rows)-with_answers} câu cần kiểm tra.\\nDữ liệu chỉ tồn tại đến khi thoát ứng dụng.')
  except ImportError:messagebox.showerror('Thiếu thư viện','Cần cài PyMuPDF.')
  except Exception as exc:messagebox.showerror('Lỗi đọc PDF',str(exc))
 def import_csv(self):
  path=filedialog.askopenfilename(filetypes=[('CSV UTF-8','*.csv')]);
  if not path:return
  n=0
  try:
   with open(path,encoding='utf-8-sig',newline='') as f:
    for row in csv.DictReader(f):
     q=(row.get('question') or row.get('cau_hoi') or '').strip();a=(row.get('answers') or row.get('dap_an') or '').strip()
     if q and a:self.items.append({'question':q,'answers':[v.strip() for v in a.split('|') if v.strip()],'type':row.get('type','single')});n+=1
   self.refresh();messagebox.showinfo('Hoàn tất',f'Đã nhập {n} câu hỏi.')
  except Exception as e:messagebox.showerror('Lỗi CSV',str(e))
 def export_template(self):
  p=filedialog.asksaveasfilename(defaultextension='.csv',initialfile='mau_dap_an.csv')
  if p:
   with open(p,'w',encoding='utf-8-sig',newline='') as f:
    w=csv.writer(f);w.writerow(['question','answers','type']);w.writerow(['Ví dụ: Kinh Thánh gồm bao nhiêu sách?','66','single']);w.writerow(['Ví dụ: Chọn hai đáp án đúng','Đáp án thứ nhất|Đáp án thứ ba','multiple'])
 def save_settings(self):
  try:
   reg=[int(x.strip()) for x in self.reg.get().split(',')];nxt=[int(x.strip()) for x in self.nxt.get().split(',')]
   if len(reg)!=4 or len(nxt)!=2 or min(reg[2:])<=0:raise ValueError('Sai số lượng tọa độ')
   self.cfg.update(region=reg,next=nxt,tesseract=self.tess.get().strip());self.save();messagebox.showinfo('Đã lưu','Đã lưu cài đặt.')
  except Exception as e:messagebox.showerror('Lỗi',str(e))
 def output(self,msg):
  self.result.configure(state='normal');self.result.delete('1.0','end');self.result.insert('end',msg);self.result.configure(state='disabled')
 def preview_region(self):
  if not pg:messagebox.showerror('Lỗi','Thiếu pyautogui');return
  try:
   shot=pg.screenshot(region=tuple(self.cfg['region']))
   from PIL import ImageTk
   win=tk.Toplevel(self.root);win.title('Xem trước vùng OCR — kiểm tra trước khi đọc')
   shot.thumbnail((1000,720))
   win.preview_photo=ImageTk.PhotoImage(shot)
   tk.Label(win,image=win.preview_photo).pack(padx=10,pady=10)
   ttk.Button(win,text='Đóng',command=win.destroy).pack(pady=6)
  except Exception as exc:messagebox.showerror('Lỗi vùng OCR',str(exc))
 def recognize(self):
  if not pg or not pytesseract:raise RuntimeError('Thiếu thư viện OCR. Chạy SETUP_ONE_CLICK.bat.')
  if self.cfg.get('tesseract') and Path(self.cfg['tesseract']).exists():pytesseract.pytesseract.tesseract_cmd=self.cfg['tesseract']
  elif os.name=='nt' and Path(r'C:\Program Files\Tesseract-OCR\tesseract.exe').exists():pytesseract.pytesseract.tesseract_cmd=r'C:\Program Files\Tesseract-OCR\tesseract.exe'
  languages=pytesseract.get_languages(config='')
  if 'vie' not in languages:raise RuntimeError('Chưa tìm thấy vie.traineddata. Kiểm tra thư mục tessdata và khởi động lại ứng dụng.')
  shot=pg.screenshot(region=tuple(self.cfg['region']))
  self.last_capture=shot.copy()
  # Enlarge the original dark-background UI, then compare several OCR passes.
  from PIL import Image
  large=shot.resize((shot.width*3,shot.height*3),Image.Resampling.LANCZOS)
  gray=ImageOps.grayscale(large)
  contrast=ImageEnhance.Contrast(gray).enhance(1.7)
  sharp=ImageEnhance.Sharpness(contrast).enhance(1.5)
  versions=[large,sharp,ImageOps.autocontrast(gray)]
  results=[]
  for picture in versions:
   for psm in (6,11):
    try:
     raw=pytesseract.image_to_string(picture,lang='vie+eng',config=f'--oem 1 --psm {psm}')
     stem,opts=extract_question_and_options(raw)
     quality=(len(norm(stem).split())*1.5 + len(opts)*7 + len(raw.strip())/60)
     if stem:results.append((quality,raw))
    except pytesseract.TesseractError:continue
  if not results:raise RuntimeError('Không đọc được văn bản tiếng Việt trong vùng đã chọn.')
  return max(results,key=lambda x:x[0])[1]
 def processing(self,message):
  self.process_var.set(message)
  self.status.set(message)
  if self.overlay_status is not None:
   try:self.overlay_status.configure(text=message)
   except tk.TclError:pass
  self.root.update_idletasks()
 def capture(self):
  if self.capture_running:return
  self.capture_running=True
  self.processing('◌ Đang đọc OCR tiếng Việt...')
  # Keep the answer window alive. Temporarily hide it only if it overlaps
  # the OCR region; restore immediately after the screenshot is taken.
  floating=self.answer_window
  was_hidden=False
  if floating is not None and floating.winfo_exists():
   x,y,w,h=self.cfg['region'];fx=floating.winfo_rootx();fy=floating.winfo_rooty()
   fw=floating.winfo_width();fh=floating.winfo_height()
   if x<fx+fw and x+w>fx and y<fy+fh and y+h>fy:
    floating.withdraw();was_hidden=True
  def work():
   try:
    content=self.recognize()
    self.root.after(0,lambda:self.capture_complete(content,None,was_hidden,floating))
   except Exception as exc:
    self.root.after(0,lambda err=str(exc):self.capture_complete(None,err,was_hidden,floating))
  threading.Thread(target=work,daemon=True).start()
 def capture_complete(self,content,error,was_hidden,floating):
  self.capture_running=False
  if was_hidden and floating is not None and floating.winfo_exists():
   floating.deiconify();floating.attributes('-topmost',True);floating.lift()
  if error:
   self.processing('✕ Lỗi OCR')
   self.output('Không đọc được màn hình: '+error)
   return
  self.raw.delete('1.0','end');self.raw.insert('end',content)
  self.processing('◌ Đang tìm câu hỏi trong PDF...')
  self.root.after(30,self.lookup)
 def lookup(self):
  self.process_var.set("◌ Đang đối chiếu PDF...")
  content=self.raw.get('1.0','end').strip();q,opts=parse_options(content)
  if not q or not self.items:
   self.match=None;self.processing('! Thiếu câu hỏi hoặc PDF');self.output('Chưa có câu hỏi hoặc kho đáp án trống.');return
  candidates=match_question(content,self.items)
  if not candidates:
   self.processing('! Không tìm thấy');self.output('Không tìm thấy câu hỏi phù hợp.');return
  score,fragment,item=candidates[0];self.match=(score,item,opts)
  runner_up=next((candidate[0] for candidate in candidates[1:] if norm(candidate[2].get('question',''))!=norm(item.get('question',''))),0)
  question_ok=score>=0.83 and (not runner_up or score-runner_up>=0.045 or score>=0.985)
  answers=item.get('answers',[])
  # Answers must be mapped to the visible text, not PDF letters.
  resolved=[];used=set();uncertain=[]
  for answer in answers:
   if not opts:
    uncertain.append(answer);continue
   ranks=sorted([(option_similarity(answer,o),idx) for idx,o in enumerate(opts)],reverse=True)
   best,idx=ranks[0];second=ranks[1][0] if len(ranks)>1 else 0
   if best>=0.78 and (best-second>=0.07 or best>=0.97) and idx not in used:
    resolved.append((idx,best,opts[idx]));used.add(idx)
   else:uncertain.append(answer)
  msg=(f'CÂU HỎI GẦN NHẤT: {item["question"]}\n'
       f'ĐỘ KHỚP CÂU HỎI: {score:.0%}\n'
       f'ĐỘ KHỚP CÂU THỨ HAI: {runner_up:.0%}\n'
       f'ĐOẠN OCR: {fragment}\n')
  if not question_ok:
   self.processing('! Chưa xác minh câu hỏi')
   self.output(msg+'CHƯA XÁC MINH CÂU HỎI: kiểm tra OCR hoặc các câu tương tự.')
   self.show_unverified('CHƯA XÁC MINH CÂU HỎI', 'Độ khớp: '+f'{score:.0%}')
   return
  if not answers:
   self.processing('! PDF thiếu đáp án')
   self.output(msg+'PDF chưa có đáp án rõ ràng.')
   self.show_unverified('PDF CHƯA CÓ ĐÁP ÁN', 'Kiểm tra nội dung PDF gốc')
   return
  if not opts:
   self.processing('! Chưa nhận diện lựa chọn')
   self.output(msg+'ĐÃ NHẬN DIỆN CÂU HỎI. Chưa đọc được lựa chọn để đối chiếu vị trí.\nĐáp án tham khảo từ PDF: '+' | '.join(answers))
   self.show_unverified('ĐÁP ÁN TRONG PDF (CHƯA GHÉP VỊ TRÍ)', ' | '.join(answers))
   return
  if uncertain or len(resolved)!=len(answers):
   self.processing('! Chưa xác minh lựa chọn')
   self.output(msg+'CÂU HỎI ĐÃ KHỚP nhưng CHƯA XÁC MINH LỰA CHỌN.\nĐáp án trong PDF: '+' | '.join(answers)+'\nCác lựa chọn chưa ghép chắc chắn: '+' | '.join(uncertain))
   self.show_unverified('ĐÁP ÁN TRONG PDF (CHƯA XÁC MINH VỊ TRÍ)', ' | '.join(answers))
   return
  labels=', '.join(chr(65+idx) for idx,_,_ in sorted(resolved))
  detail='\n'.join(f'{chr(65+idx)}. {choice} (khớp {sc:.0%})' for idx,sc,choice in sorted(resolved))
  self.output(msg+'ĐÁP ÁN ĐÃ ĐỐI CHIẾU: '+labels+'\n'+detail+'\nHãy kiểm tra trước khi nộp bài.')
  self.last_verified=(tuple((idx,choice) for idx,_,choice in sorted(resolved)),item['question'])
  self.processing('✓ Đã xác minh từ PDF')
  self.show_last_answer()  # Automatically display the verified answer after F8 or lookup.
 def hide_answer(self):
  self.last_verified=None
  if self.answer_window is not None:
   try:self.answer_window.destroy()
   except tk.TclError:pass
   self.answer_window=None
 def overlay(self,title,body,verified=False,positions=''):
  if self.answer_window is not None and self.answer_window.winfo_exists():
   win=self.answer_window
   for child in win.winfo_children():child.destroy()
  else:
   win=tk.Toplevel(self.root);self.answer_window=win
   win.geometry('650x380+960+180')
   win.minsize(450,260)
  win.title('THAN QUIZ ASSISTANT — ĐÁP ÁN TRỰC TIẾP')
  win.configure(bg='#081528')
  win.attributes('-topmost',True)
  win.lift()
  # Reassert topmost after window-manager focus changes without stealing keyboard focus.
  win.bind('<Map>',lambda event:win.after_idle(lambda:win.attributes('-topmost',True)))
  win.protocol('WM_DELETE_WINDOW',self.close_answer_window)
  self.overlay_status=tk.Label(win,text=self.process_var.get(),bg='#081528',fg='#52e8bb',font=('Segoe UI',12,'bold'))
  self.overlay_status.pack(fill='x',padx=16,pady=(16,4))
  tk.Label(win,text=title,bg='#081528',fg='#ffffff',font=('Segoe UI',15,'bold'),wraplength=590).pack(pady=8)
  box=tk.Frame(win,bg='#0d2b2b' if verified else '#342b19',highlightbackground='#18dfaa' if verified else '#f6bd60',highlightthickness=2)
  box.pack(fill='both',expand=True,padx=18,pady=10)
  if positions:
   tk.Label(box,text=positions,bg=box['bg'],fg='#52e8bb',font=('Segoe UI',40,'bold')).pack(pady=(15,4))
  answer_area=tk.Frame(box,bg=box['bg']);answer_area.pack(fill='both',expand=True,padx=12,pady=8)
  scrollbar=tk.Scrollbar(answer_area);scrollbar.pack(side='right',fill='y')
  answer_text=tk.Text(answer_area,bg=box['bg'],fg='white',font=('Segoe UI',16,'bold'),wrap='word',relief='flat',yscrollcommand=scrollbar.set)
  answer_text.pack(side='left',fill='both',expand=True)
  scrollbar.config(command=answer_text.yview)
  answer_text.insert('1.0',body);answer_text.config(state='disabled')
  tk.Button(win,text='Đóng',command=self.close_answer_window,bg='#183454',fg='white',relief='flat',font=('Segoe UI',11)).pack(pady=(2,12))
  win.bind('<Escape>',lambda event:self.close_answer_window())
 def show_unverified(self,title,answer):
  self.last_verified=None
  self.overlay(title,answer,verified=False)
 def show_last_answer(self):
  verified=getattr(self,'last_verified',None)
  if not verified:
   self.show_unverified('CHƯA CÓ ĐÁP ÁN ĐÃ XÁC MINH','Đọc câu hỏi và đối chiếu PDF trước')
   return
  answers,question=verified
  positions=', '.join(chr(65+idx) for idx,_ in answers)
  body='\n'.join(choice for idx,choice in answers)
  self.overlay('ĐÁP ÁN ĐÃ ĐỐI CHIẾU PDF',body,verified=True,positions=positions)
 def close_answer_window(self):
  if self.answer_window is not None:
   try:self.answer_window.destroy()
   except tk.TclError:pass
   self.answer_window=None
 def stop(self):self.active=False;self.status.set('Đã dừng');self.process_var.set('■ Đã dừng')
 def start(self):
  if self.active:return
  if self.mode.get()=='auto' and not messagebox.askyesno('Xác nhận quyền sử dụng','Chỉ bật Auto Mode cho bài LUYỆN TẬP được phép tự động hóa. Bạn xác nhận có quyền dùng tính năng này?'):return
  self.active=True;self.status.set('Đang theo dõi vùng đã chọn — F9 để dừng');self.tick()
 def tick(self):
  if not self.active:return
  if not self.busy and not self.capture_running:
   self.busy=True
   try:
    self.capture()
    if self.mode.get()=='auto':
     # Safety: OCR alone does not reliably locate controls; require manual selection.
     self.status.set('Auto: chờ cấu hình tọa độ lựa chọn chính xác; không tự nhấp để tránh chọn sai')
     self.active=False
   finally:self.busy=False
  if self.active:self.root.after(2200,self.tick)

if __name__=='__main__':
 if os.name=='nt':
  try:
   import ctypes
   ctypes.windll.shcore.SetProcessDpiAwareness(2)
  except Exception:pass
 root=tk.Tk();App(root);root.mainloop()

import asyncio
import aiohttp
import hashlib
from Crypto.Cipher import DES
import base64
from bs4 import BeautifulSoup
import statistics
import tkinter as tk
from tkinter import messagebox

url = "https://i-learning.cycu.edu.tw"

# MD5 Encrypt
def md5_encode(input_string) -> str:
    md5_hash = hashlib.md5()
    md5_hash.update(input_string.encode('utf-8'))
    return md5_hash.hexdigest()

# DES Encrypt ECB NoPadding
def des_encode(key: str, data) -> str:
    cipher = DES.new(key.encode('utf-8'), DES.MODE_ECB)
    encrypted_data = cipher.encrypt(data.encode('utf-8'))
    return str(base64.encodebytes(encrypted_data), encoding='utf-8').replace("\n", "")

async def fetch_login_key(session):
    while True:
        async with session.get(f"{url}/sys/door/re_gen_loginkey.php?xajax=reGenLoginKey", headers=headers) as response:
            res = await response.text()
            if "loginForm.login_key.value = \"" in res:
                return res.split("loginForm.login_key.value = \"")[1].split("\"")[0]

async def login(session, id, pwd, loginKey) -> bool:
    async with session.post(f"{url}/login.php", headers=headers, data={
        "username": id,
        "pwd": pwd,
        "password": "*" * len(pwd),
        "login_key": loginKey,
        "encrypt_pwd": des_encode(md5_encode(pwd)[:4] + loginKey[:4], pwd + " " * (16 - len(pwd) % 16) if len(pwd) % 16 != 0 else pwd),
    }) as response:
        res = await response.text()
        if "lang=\"big5" in res:
            return False
    return True

async def fetch_courses(session):
    async with session.get(f"{url}/learn/mooc_sysbar.php", headers=headers) as response:
        soup = BeautifulSoup(await response.text(), 'lxml')
        courses = {
            option["value"]: option.text
            for child in soup.select("optgroup[label=\"正式生、旁聽生\"]")
            for option in child.find_all("option")
        }
        
        return courses

async def goToCourse(session, course_id):
    xml_data = f'<manifest><ticket/><course_id>{course_id}</course_id><env/></manifest>'
    async with session.post(f"{url}/learn/goto_course.php", headers={"User-Agent": "Mozilla/5.0", 'Content-Type': 'application/xml'}, data=xml_data) as response:
        return response.status == 200

async def fetch_grades(session):
    async with session.post(f'{url}/learn/grade/grade_list.php', headers=headers) as response:
        soup = BeautifulSoup(await response.text(), 'lxml')
        return {
            btn['onclick'].split("'")[1].strip(): btn.find_parent("tr").find("div").get_text()
            for child in soup.select(".content .data2 .subject")
            for btn in child.select("input.btn")
        }, [
            float(tr.get_text()) if tr.get_text().replace('.', '', 1).isdigit() else 0.0
            for child in soup.select(".content .data2 .subject tr")
            if 'class' in child.parent.attrs and 'subject' in child.parent.attrs['class']
            for tr in child.select(".t1 div")
        ]

async def fetch_scores(session, gradeId):
    async with session.post(f'{url}/learn/grade/grade_team.php?{gradeId}', headers=headers) as response:
        soup = BeautifulSoup(await response.text(), 'lxml')
        return [float(num) for num in soup.select_one("input[name=\"scores\"]").attrs['value'].split(",")]

headers = {"User-Agent": "Mozilla/5.0"}

class Application(tk.Tk):
    def show_password(self):
        if self.entry_pwd['show'] == "*":
            self.entry_pwd['show'] = ""
        else:
            self.entry_pwd['show'] = "*"
    def __init__(self):
        super().__init__()
        self.iconbitmap("icon.ico")
        self.title("CYCU iLearning Score Analyzer")
        self.geometry("600x900")

        

        self.label_id = tk.Label(self, text="學號：")
        self.label_id.place(x=50, y=50)
        self.entry_id = tk.Entry(self)
        self.entry_id.place(x=150, y=50)

        
        
        self.label_pwd = tk.Label(self, text="itouch密碼：")
        self.label_pwd.place(x=50, y=80)
        self.entry_pwd = tk.Entry(self, show="*")
        self.entry_pwd.place(x=150, y=80)
        
        
        self.btn_show_pwd = tk.Button(self, text="顯示密碼", command=self.show_password)
        self.btn_show_pwd.place(x=250, y=80)
        
        self.btn_login = tk.Button(self, text="登入", command=self.login)
        self.btn_login.place(x=350, y=80)
        
        self.listbox_courses = tk.Listbox(self)
        self.listbox_courses.bind('<Double-Button-1>', self.select_course)
        self.listbox_courses.place(x=50, y=120, width=500, height=180)
        
        self.listbox_grades = tk.Listbox(self)
        self.listbox_grades.bind('<Double-Button-1>', self.select_grade)
        self.listbox_grades.place(x=50, y=300, width=200, height=70)
        
        self.text_output = tk.Text(self)
        self.text_output.place(x=50, y=370, width=500, height=500)
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)

    async def async_login(self):
        self.connector = aiohttp.TCPConnector(limit=50)
        self.session = aiohttp.ClientSession(connector=self.connector)
        self.login_key = await fetch_login_key(self.session)
        if not await login(self.session, self.entry_id.get(), self.entry_pwd.get(), self.login_key):
            messagebox.showerror("錯誤", "登入失敗，請重新再試!")
            return
        self.courses = await fetch_courses(self.session)
        self.listbox_courses.delete(0, tk.END)
        for course in self.courses.values():
            self.listbox_courses.insert(tk.END, course)
    def login(self):
        self.loop.run_until_complete(self.async_login())

    async def async_select_course(self):
        self.course_index = self.listbox_courses.curselection()
        if not self.course_index:
            messagebox.showerror("錯誤", "請先選擇一門課程！")
            return
        course_id = list(self.courses.keys())[self.course_index[0]]
        if not await goToCourse(self.session, course_id):
            messagebox.showerror("錯誤", "無法進入所選課程！")
            return
        self.grades, self.selfGrade = await fetch_grades(self.session)
        self.listbox_grades.delete(0, tk.END)
        for grade in self.grades.values():
            self.listbox_grades.insert(tk.END, grade)
        if self.listbox_grades.size() == 0:
            messagebox.showinfo("提示", "此課程無成績資料！")

    def select_course(self, event):
        self.loop.run_until_complete(self.async_select_course())

    async def async_select_grade(self):
        grade_index = self.listbox_grades.curselection()

        grade_id = list(self.grades.keys())[grade_index[0]]
        scores = await fetch_scores(self.session, grade_id)

        sorted_grades = sorted(scores)
        rank = sorted_grades.index(self.selfGrade[grade_index[0]]) + 1
        pr_value = ((rank - 0.5) / len(scores)) * 100
        max_grade = max(scores)
        min_grade = min(scores)
        range_grade = max_grade - min_grade
        quartiles = statistics.quantiles(scores, n=4)

        grade_distribution = dict()
        for grade in scores:
            range_start = (grade // 5) * 5
            if grade >= 100:
                grade_distribution["100"] = grade_distribution.get("100", 0) + 1
            else:
                range_end = range_start + 4
                grade_range = f"{int(range_start)}-{int(range_end)}"
                grade_distribution[grade_range] = grade_distribution.get(grade_range, 0) + 1

        sorted_grade_distribution = sorted(grade_distribution.items(), key=lambda x: (int(x[0].split('-')[0]) if '-' in x[0] else 100))

        output = f'{self.courses[list(self.courses.keys())[self.course_index[0]]]} - {self.grades[grade_id]}\n'
        output += f'你的分數: {self.selfGrade[grade_index[0]]}\n'
        output += f'你的PR: {"%.2f" % pr_value}\n'
        output += f'平均數: {"%.2f" % statistics.mean(scores)}\n'
        output += f'中位數: {"%.2f" % statistics.median(scores)}\n'
        output += f'標準差: {"%.3f" % statistics.stdev(scores)}\n'
        output += f'最高分: {max_grade}\n'
        output += f'最低分: {min_grade}\n'
        output += f'全距: {range_grade}\n'
        output += f'四分位數: {quartiles}\n'
        output += '成績分布:\n'
        for grade_range, frequency in sorted_grade_distribution:
            output += f'{grade_range:<8}- {frequency:>3}\n'

        self.text_output.delete(1.0, tk.END)
        self.text_output.insert(tk.END, output)

    def select_grade(self, event):
        self.loop.run_until_complete(self.async_select_grade())

    def on_closing(self):
        self.destroy()

if __name__ == "__main__":
    app = Application()
    app.protocol("WM_DELETE_WINDOW", app.on_closing)
    app.mainloop()

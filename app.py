import os
import aiohttp
import getpass
import hashlib
from Crypto.Cipher import DES
import base64
from bs4 import BeautifulSoup
import statistics
import asyncio
from rich.table import Table
from rich.console import Console

console = Console()
url = "https://i-learning.cycu.edu.tw"

# MD5 Encrypt
def md5_encode(input_string) -> str:
    md5_hash = hashlib.md5()
    md5_hash.update(input_string.encode('utf-8'))
    return md5_hash.hexdigest()

# DES Encrypt ECB NoPadding
def des_encode(key:str, data) -> str:
    cipher = DES.new(key.encode('utf-8'), DES.MODE_ECB)
    encrypted_data = cipher.encrypt(data.encode('utf-8'))
    return str(base64.encodebytes(encrypted_data),encoding='utf-8').replace("\n","")

async def fetch_login_key(session):
    while True:
        async with session.get(f"{url}/sys/door/re_gen_loginkey.php?xajax=reGenLoginKey", headers=headers) as response:
            res = await response.text()
            if "loginForm.login_key.value = \"" in res:
                return res.split("loginForm.login_key.value = \"")[1].split("\"")[0]

async def login(session, id, pwd, loginKey) -> bool:
    try:
        async with session.post(f"{url}/login.php", headers=headers, data={
            "username": id,
            "pwd": pwd,
            "password": "*" * len(pwd),
            "login_key": loginKey,
            "encrypt_pwd": des_encode(md5_encode(pwd)[:4] + loginKey[:4], pwd + " " * (16 - len(pwd) % 16) if len(pwd) % 16 != 0 else pwd),
        }, timeout=3 ) as response:
            res = await response.text()
            if "lang=\"big5" in res:
                print("登入失敗，請重新再試!")
                return False
    except Exception as e:
        print("登入失敗，請重新再試!")
        return False
    return True

async def fetch_courses(session):
    async with session.get(f"{url}/learn/mooc_sysbar.php", headers=headers) as response:
        soup = BeautifulSoup(await response.text(), 'lxml')
        courses = {
            option["value"]: option.text
            for child in soup.select("optgroup[label^=\"正式生、旁聽生\"]")
            for option in child.find_all("option")
        }
        return courses
    
async def goToCourse(session,course_id):
    xml_data = f'<manifest><ticket/><course_id>{course_id}</course_id><env/></manifest>'
    async with session.post(f"{url}/learn/goto_course.php", headers=
                            {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/15.0 Safari/605.1.15",'Content-Type':'application/xml'},
                            data=xml_data) as response:
        return response.status == 200

async def fetch_grades(session):
    async with session.post(f'{url}/learn/grade/grade_list.php',headers=headers) as response:
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
    async with session.post(f'{url}/learn/grade/grade_team.php?{gradeId}',headers=headers) as response:
        soup = BeautifulSoup(await response.text(), 'lxml')
        return [float(num) for num in soup.select_one("input[name=\"scores\"]").attrs['value'].split(",")]

headers = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/15.0 Safari/605.1.15"}

async def main():
    os.system("title CYCU-iLearning-Score-Analyzer")
    try:
        id = input("輸入您的學號：")
        pwd = getpass.getpass("輸入您的itouch密碼：")
        
        connector = aiohttp.TCPConnector(limit=50)
        async with aiohttp.ClientSession(connector=connector) as session:
            login_key = await fetch_login_key(session)
            if not await login(session, id, pwd, login_key):
                return await main()
            
            courses = await fetch_courses(session)
            
            while(True):
                courseKeys = list(reversed(courses.keys()))
                for i, key in enumerate(courseKeys):
                    console.print("[cyan3]"+ str(i) + ": "+ courses[key])
                
                console.print("[dark_cyan]輸入編號選擇課程")
                
                keyIndex = None
                while(keyIndex == None or keyIndex >= len(courseKeys) or keyIndex < -1):
                    try:
                        keyIndex = int(input("> "))
                    except Exception as e:
                        print(e)
                        continue
                if keyIndex == -1:
                    continue
                
                if not await goToCourse(session, courseKeys[keyIndex]):
                    continue
                
                grades, selfGrade = await fetch_grades(session)

                if len(grades) == 0:
                    console.input('[dark_cyan]找不到任何成績項目...')
                    continue
                
                gradeKeys = list(grades.keys())
                for i, key in enumerate(gradeKeys):
                    console.print("[cyan3]"+ str(i) + ": "+ grades[gradeKeys[i]])
                
                console.print("[dark_cyan]輸入編號選擇項目")
                
                gradeIndex = None
                while(gradeIndex == None or gradeIndex >= len(grades) or gradeIndex < -1):
                    try:
                        gradeIndex = int(input("> "))
                    except Exception as e:
                        print(e)
                        continue
                if gradeIndex == -1:
                    continue
                
                scores = await fetch_scores(session, gradeKeys[gradeIndex])
                
                sorted_grades = sorted(scores)
                rank = sorted_grades.index(selfGrade[gradeIndex]) + 1
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
                table = Table(title="成績分布")
                table.add_column("範圍", justify="center", style="cyan", no_wrap=True)
                table.add_column("人數", justify="center", style="magenta")
                for grade_range, frequency in sorted_grade_distribution:
                    table.add_row(grade_range, str(frequency))
                console.print(table)
                
                console.print(f'[cyan2][bold]{courses[courseKeys[keyIndex]]} - {grades[gradeKeys[gradeIndex]]}')
                console.print(f'[bright_green]你的分數: [green]{selfGrade[gradeIndex]}')
                console.print(f'[bright_green]你的PR: [green]{"%.2f" % pr_value}')
                console.print(f'[bright_green]平均數: [green]{"%.2f" % statistics.mean(scores)}')
                console.print(f'[bright_green]中位數: [green]{"%.2f" % statistics.median(scores)}')
                console.print(f'[bright_green]標準差: [green]{"%.3f" % statistics.stdev(scores)}')
                console.print(f'[bright_green]最高分: [green]{max_grade}')
                console.print(f'[bright_green]最低分: [green]{min_grade}')
                console.print(f'[bright_green]全距: [green]{range_grade}')
                console.print(f'[bright_green]四分位數: [green]{quartiles}')
                console.input("點擊 Enter 繼續...")
    finally:
        os.system("pause")

if __name__ == "__main__":
    asyncio.run(main())
# โปรแกรมตัดภาพออกเป็นช่องๆ

โปรแกรม Python สำหรับตัดภาพออกเป็นช่องๆ ตาม grid ที่กำหนด

## การติดตั้ง

```bash
pip install -r requirements.txt
```

## วิธีใช้งาน

### 🌐 วิธีที่ 1: ใช้ Web Application (แนะนำ)

รันเว็บแอปพลิเคชันด้วย Streamlit:

```bash
streamlit run app.py
```

หรือ

```bash
python -m streamlit run app.py
```

จากนั้นเปิดเบราว์เซอร์ไปที่ `http://localhost:8501`

**คุณสมบัติ:**
- ✅ อัพโหลดภาพผ่านเว็บ
- ✅ ตั้งค่าจำนวนแถวและคอลัมน์ได้ง่าย
- ✅ แสดงตัวอย่างภาพที่ตัดแล้ว
- ✅ ดาวน์โหลดผลลัพธ์เป็นไฟล์ ZIP
- ✅ UI สวยงาม ใช้งานง่าย

### 💻 วิธีที่ 2: ใช้ Command Line

### วิธีที่ 1: ใช้แบบ interactive
```bash
python cut_image.py
```
โปรแกรมจะถาม path ของไฟล์ภาพ และจำนวนแถว/คอลัมน์

### วิธีที่ 2: ระบุ path ใน command line
```bash
python cut_image.py path/to/image.jpg
```

### วิธีที่ 3: ระบุ path และ output directory
```bash
python cut_image.py path/to/image.jpg output_folder
```

### วิธีที่ 4: ระบุทุกอย่าง (path, output, rows, cols)
```bash
python cut_image.py path/to/image.jpg output_folder 8 10
```

## ตัวอย่าง

```bash
# ตัดภาพเป็น 8 แถว x 10 คอลัมน์ (default)
python cut_image.py my_image.jpg

# ตัดภาพเป็น 4 แถว x 5 คอลัมน์
python cut_image.py my_image.jpg output 4 5
```

## ผลลัพธ์

ภาพที่ตัดแล้วจะถูกบันทึกในรูปแบบ:
- `ชื่อไฟล์_row01_col01.png`
- `ชื่อไฟล์_row01_col02.png`
- ...
- `ชื่อไฟล์_row08_col10.png`

ไฟล์จะถูกบันทึกในโฟลเดอร์ output ที่กำหนด (default: `ชื่อไฟล์_cut`)


#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
โปรแกรมตัดภาพออกเป็นช่องๆ ตาม grid
รองรับการกำหนดจำนวนแถวและคอลัมน์
"""

from PIL import Image
import os
import sys


def cut_image_grid(input_path, output_dir, rows=8, cols=10):
    """
    ตัดภาพออกเป็นช่องๆ ตาม grid
    
    Args:
        input_path: path ของไฟล์ภาพต้นฉบับ
        output_dir: directory สำหรับเก็บภาพที่ตัดแล้ว
        rows: จำนวนแถว (default: 8)
        cols: จำนวนคอลัมน์ (default: 10)
    """
    # ตรวจสอบว่าไฟล์ภาพมีอยู่จริง
    if not os.path.exists(input_path):
        print(f"❌ ไม่พบไฟล์: {input_path}")
        return False
    
    # สร้าง output directory ถ้ายังไม่มี
    os.makedirs(output_dir, exist_ok=True)
    
    # เปิดภาพ
    try:
        img = Image.open(input_path)
        print(f"✅ โหลดภาพสำเร็จ: {img.size[0]}x{img.size[1]} pixels")
    except Exception as e:
        print(f"❌ ไม่สามารถเปิดภาพได้: {e}")
        return False
    
    # คำนวณขนาดของแต่ละช่อง
    img_width, img_height = img.size
    cell_width = img_width // cols
    cell_height = img_height // rows
    
    print(f"📐 ขนาดแต่ละช่อง: {cell_width}x{cell_height} pixels")
    print(f"📊 Grid: {rows} แถว x {cols} คอลัมน์ = {rows * cols} ช่อง")
    
    # ดึงชื่อไฟล์โดยไม่มี extension
    base_name = os.path.splitext(os.path.basename(input_path))[0]
    
    # ตัดภาพทีละช่อง
    count = 0
    for row in range(rows):
        for col in range(cols):
            # คำนวณตำแหน่งของช่อง
            left = col * cell_width
            top = row * cell_height
            right = left + cell_width
            bottom = top + cell_height
            
            # ตัดภาพ
            cell = img.crop((left, top, right, bottom))
            
            # บันทึกไฟล์ (ชื่อไฟล์: row_col.png)
            output_filename = f"{base_name}_row{row+1:02d}_col{col+1:02d}.png"
            output_path = os.path.join(output_dir, output_filename)
            cell.save(output_path, "PNG")
            
            count += 1
            if count % 10 == 0:
                print(f"  ⏳ ตัดไปแล้ว {count}/{rows * cols} ช่อง...")
    
    print(f"✅ ตัดภาพเสร็จสิ้น! บันทึก {count} ไฟล์ใน: {output_dir}")
    return True


def main():
    """ฟังก์ชันหลัก"""
    print("=" * 50)
    print("🔪 โปรแกรมตัดภาพออกเป็นช่องๆ")
    print("=" * 50)
    
    # รับ input จาก command line หรือถามผู้ใช้
    if len(sys.argv) >= 2:
        input_path = sys.argv[1]
    else:
        input_path = input("📁 กรุณาใส่ path ของไฟล์ภาพ: ").strip()
    
    # ตั้งค่า output directory
    if len(sys.argv) >= 3:
        output_dir = sys.argv[2]
    else:
        base_dir = os.path.dirname(input_path) if os.path.dirname(input_path) else "."
        base_name = os.path.splitext(os.path.basename(input_path))[0]
        output_dir = os.path.join(base_dir, f"{base_name}_cut")
        print(f"📂 Output directory: {output_dir}")
    
    # ตั้งค่าจำนวนแถวและคอลัมน์
    rows = 8
    cols = 10
    
    if len(sys.argv) >= 5:
        try:
            rows = int(sys.argv[3])
            cols = int(sys.argv[4])
        except ValueError:
            print("⚠️  จำนวนแถว/คอลัมน์ไม่ถูกต้อง ใช้ค่า default (8x10)")
    else:
        custom = input("⚙️  ต้องการกำหนดจำนวนแถวและคอลัมน์เองไหม? (y/n) [n]: ").strip().lower()
        if custom == 'y':
            try:
                rows = int(input(f"📏 จำนวนแถว [{rows}]: ") or rows)
                cols = int(input(f"📏 จำนวนคอลัมน์ [{cols}]: ") or cols)
            except ValueError:
                print("⚠️  ใช้ค่า default (8x10)")
    
    # เริ่มตัดภาพ
    print()
    success = cut_image_grid(input_path, output_dir, rows, cols)
    
    if success:
        print("\n🎉 เสร็จสมบูรณ์!")
    else:
        print("\n❌ เกิดข้อผิดพลาด")


if __name__ == "__main__":
    main()


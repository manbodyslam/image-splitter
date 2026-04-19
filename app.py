#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Web Application สำหรับตัดภาพออกเป็นช่องๆ
ใช้ Streamlit
"""

import streamlit as st
from PIL import Image
import io
import zipfile
import os
from pathlib import Path
import cv2
import numpy as np


def cut_image_grid(img, rows=8, cols=10, cut_mode="grid", auto_crop=True, debug=False, crop_intensity=50, margin_px=0):
    """
    ตัดภาพออกเป็นช่องๆ ตาม grid หรือแนวตั้ง/แนวนอน
    
    Args:
        img: PIL Image object
        rows: จำนวนแถว (ใช้กับ grid หรือ horizontal)
        cols: จำนวนคอลัมน์ (ใช้กับ grid หรือ vertical)
        cut_mode: "grid", "vertical", "horizontal"
        auto_crop: ถ้า True จะ crop เฉพาะส่วนที่เป็นรูปภาพจริงๆ
        debug: ถ้า True จะแสดง debug info
        crop_intensity: ความเข้มงวดในการตัดขอบ 0-100
        margin_px: ขอบเพิ่มรอบภาพ (pixels)
    
    Returns:
        list of PIL Image objects
    """
    img_width, img_height = img.size
    
    if debug:
        print(f"DEBUG: cut_image_grid - img_size={img_width}x{img_height}, rows={rows}, cols={cols}, cut_mode={cut_mode}, auto_crop={auto_crop}")
    
    cells = []
    
    if cut_mode == "vertical":
        # ตัดแนวตั้ง (เป็นคอลัมน์)
        cell_width = img_width // cols
        cell_height = img_height
        
        for col in range(cols):
            left = col * cell_width
            top = 0
            right = left + cell_width
            bottom = img_height
            
            cell = img.crop((left, top, right, bottom))
            
            # Auto crop ถ้าเปิดใช้งาน
            if auto_crop:
                cell = auto_crop_image(cell, crop_intensity=crop_intensity, margin_px=margin_px)
            
            cells.append({
                'image': cell,
                'row': 1,
                'col': col + 1,
                'index': col + 1
            })
        
        avg_width = sum(c['image'].size[0] for c in cells) // len(cells) if cells else cell_width
        return cells, avg_width, cell_height
    
    elif cut_mode == "horizontal":
        # ตัดแนวนอน (เป็นแถว)
        cell_width = img_width
        cell_height = img_height // rows
        
        for row in range(rows):
            left = 0
            top = row * cell_height
            right = img_width
            bottom = top + cell_height
            
            cell = img.crop((left, top, right, bottom))
            
            # Auto crop ถ้าเปิดใช้งาน
            if auto_crop:
                cell = auto_crop_image(cell, crop_intensity=crop_intensity, margin_px=margin_px)
            
            cells.append({
                'image': cell,
                'row': row + 1,
                'col': 1,
                'index': row + 1
            })
        
        avg_height = sum(c['image'].size[1] for c in cells) // len(cells) if cells else cell_height
        return cells, cell_width, avg_height
    
    else:
        # ตัดแบบ grid (ปกติ)
        cell_width = img_width // cols
        cell_height = img_height // rows
        
        for row in range(rows):
            for col in range(cols):
                left = col * cell_width
                top = row * cell_height
                right = left + cell_width
                bottom = top + cell_height
                
                # ตรวจสอบว่าตำแหน่งถูกต้อง
                if right > img_width or bottom > img_height:
                    if debug:
                        print(f"DEBUG: WARNING - Cell {row+1},{col+1} out of bounds: ({left},{top},{right},{bottom}) vs img {img_width}x{img_height}")
                    right = min(right, img_width)
                    bottom = min(bottom, img_height)
                
                cell = img.crop((left, top, right, bottom))
                
                if debug:
                    print(f"DEBUG: Cell {row+1},{col+1} - Before auto_crop: {cell.size}")
                
                # Auto crop ถ้าเปิดใช้งาน
                if auto_crop:
                    original_cell_size = cell.size
                    cell = auto_crop_image(cell, crop_intensity=crop_intensity, margin_px=margin_px)
                    if debug and cell.size != original_cell_size:
                        print(f"DEBUG: Cell {row+1},{col+1} - After auto_crop: {cell.size} (was {original_cell_size})")
                
                # ตรวจสอบว่าภาพไม่ว่างเปล่า
                if cell.size[0] == 0 or cell.size[1] == 0:
                    if debug:
                        print(f"DEBUG: ERROR - Cell {row+1},{col+1} is empty! Size: {cell.size}")
                    # ใช้ภาพเดิมก่อน auto_crop
                    cell = img.crop((left, top, right, bottom))
                
                cells.append({
                    'image': cell,
                    'row': row + 1,
                    'col': col + 1,
                    'index': row * cols + col + 1
                })
        
        avg_width = sum(c['image'].size[0] for c in cells) // len(cells) if cells else cell_width
        avg_height = sum(c['image'].size[1] for c in cells) // len(cells) if cells else cell_height
        return cells, avg_width, avg_height


def auto_crop_image(cell_img, threshold=240, crop_intensity=50, margin_px=0):
    """
    ตัดเฉพาะส่วนที่เป็นรูปภาพจริงๆ ข้างใน โดยตัดพื้นที่ว่างออก
    ใช้หลายวิธีเพื่อให้ได้ผลลัพธ์ที่ดีที่สุด
    
    Args:
        cell_img: PIL Image object (cell ที่ตัดได้)
        threshold: threshold สำหรับการตรวจจับพื้นที่ว่าง (default: 240)
        crop_intensity: ความเข้มงวดในการตัดขอบ 0-100 (0=ไม่ตัด, 100=ตัดแน่นมาก)
        margin_px: ขอบเพิ่มรอบภาพ (pixels)
    
    Returns:
        PIL Image object ที่ crop แล้ว
    """
    # ถ้า intensity เป็น 0 ให้คืนภาพเดิม
    if crop_intensity == 0:
        return cell_img
    try:
        original_size = cell_img.size

        # ใช้ OpenCV เพื่อหาขอบของเนื้อหา
        img_array = np.array(cell_img.convert('RGB'))
        gray = cv2.cvtColor(img_array, cv2.COLOR_RGB2GRAY)

        # ตรวจว่าขอบเป็นดำหรือขาว โดยดูค่าเฉลี่ยของขอบภาพ
        h_img, w_img = gray.shape
        border_w = max(2, min(h_img, w_img) // 20)
        border_pixels = np.concatenate([
            gray[:border_w, :].flatten(),
            gray[-border_w:, :].flatten(),
            gray[:, :border_w].flatten(),
            gray[:, -border_w:].flatten(),
        ])
        border_mean = float(np.mean(border_pixels))
        border_is_dark = border_mean < 100

        # วิธี bbox ตัดขอบสีเดียว (ดำหรือขาว)
        if border_is_dark:
            # ขอบดำ: เก็บ pixel ที่สว่างกว่า threshold
            threshold_val = min(80, int(border_mean + 30))
            mask = gray > threshold_val
        else:
            # ขอบขาว: เก็บ pixel ที่เข้มกว่า threshold
            threshold_val = max(200, int(border_mean - 30))
            mask = gray < threshold_val

        ys, xs = np.where(mask)
        if len(xs) > 10 and len(ys) > 10:
            x_min, x_max = int(xs.min()), int(xs.max())
            y_min, y_max = int(ys.min()), int(ys.max())
            w = x_max - x_min
            h = y_max - y_min
            if w >= original_size[0] * 0.2 and h >= original_size[1] * 0.2:
                padding_x = margin_px if margin_px > 0 else 0
                padding_y = margin_px if margin_px > 0 else 0
                x_min = max(0, x_min - padding_x)
                y_min = max(0, y_min - padding_y)
                x_max = min(original_size[0], x_max + 1 + padding_x)
                y_max = min(original_size[1], y_max + 1 + padding_y)
                cropped = cell_img.crop((x_min, y_min, x_max, y_max))
                if cropped.size[0] > 0 and cropped.size[1] > 0:
                    return cropped
        
        # คำนวณ thresholds ตาม crop_intensity
        # intensity สูง = threshold ต่ำลง = ตรวจจับสีที่เข้มขึ้นได้ = ตัดแน่นขึ้น
        base_threshold = 255 - int(crop_intensity * 0.7)  # intensity 100 -> threshold 185
        thresholds = [max(150, base_threshold - 20), base_threshold, min(250, base_threshold + 10)]
        
        best_bbox = None
        best_score = 0
        
        for thresh_val in thresholds:
            # หาเนื้อหาที่ไม่ใช่สีขาว/สว่าง
            _, binary = cv2.threshold(gray, thresh_val, 255, cv2.THRESH_BINARY_INV)
            
            # หา contours
            contours, _ = cv2.findContours(binary, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            
            if len(contours) > 0:
                # หา bounding box ของทุก contours รวมกัน
                all_x = []
                all_y = []
                total_area = 0
                
                for contour in contours:
                    x, y, w, h = cv2.boundingRect(contour)
                    area = cv2.contourArea(contour)
                    # ใช้เฉพาะ contours ที่มีขนาดใหญ่พอ
                    if area > (original_size[0] * original_size[1] * 0.01):
                        all_x.extend([x, x + w])
                        all_y.extend([y, y + h])
                        total_area += area
                
                if len(all_x) > 0 and len(all_y) > 0:
                    x_min = min(all_x)
                    x_max = max(all_x)
                    y_min = min(all_y)
                    y_max = max(all_y)
                    
                    w = x_max - x_min
                    h = y_max - y_min
                    
                    # คำนวณ score (พื้นที่เนื้อหา / พื้นที่ทั้งหมด)
                    score = total_area / (w * h) if w * h > 0 else 0
                    
                    # ตรวจสอบว่าขนาดเหมาะสม (อย่างน้อย 5% ของภาพเดิม)
                    if w >= original_size[0] * 0.05 and h >= original_size[1] * 0.05:
                        if score > best_score:
                            best_score = score
                            best_bbox = (x_min, y_min, x_max, y_max)
        
        # วิธีที่ 3: ใช้ edge detection เพื่อหาขอบของเนื้อหา
        if best_bbox is None:
            # ใช้ Canny edge detection
            edges = cv2.Canny(gray, 50, 150)
            
            # หา contours จาก edges
            contours, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            
            if len(contours) > 0:
                # หา bounding box ของทุก contours
                all_x = []
                all_y = []
                
                for contour in contours:
                    area = cv2.contourArea(contour)
                    if area > (original_size[0] * original_size[1] * 0.01):
                        x, y, w, h = cv2.boundingRect(contour)
                        all_x.extend([x, x + w])
                        all_y.extend([y, y + h])
                
                if len(all_x) > 0 and len(all_y) > 0:
                    x_min = min(all_x)
                    x_max = max(all_x)
                    y_min = min(all_y)
                    y_max = max(all_y)
                    
                    w = x_max - x_min
                    h = y_max - y_min
                    
                    if w >= original_size[0] * 0.05 and h >= original_size[1] * 0.05:
                        best_bbox = (x_min, y_min, x_max, y_max)
        
        # วิธีที่ 4: ใช้การหาความแตกต่างของสี (variance)
        if best_bbox is None:
            # หาพื้นที่ที่มีความแตกต่างของสีสูง (มีเนื้อหา)
            # แบ่งภาพเป็น grid และหาพื้นที่ที่มี variance สูง
            h, w = gray.shape
            block_size = min(20, w // 10, h // 10)
            
            variance_map = np.zeros((h // block_size, w // block_size))
            
            for i in range(0, h - block_size, block_size):
                for j in range(0, w - block_size, block_size):
                    block = gray[i:i+block_size, j:j+block_size]
                    variance_map[i//block_size, j//block_size] = np.var(block)
            
            # หา threshold ของ variance
            variance_threshold = np.percentile(variance_map, 30)
            
            # หา bounding box ของพื้นที่ที่มี variance สูง
            coords = np.where(variance_map > variance_threshold)
            if len(coords[0]) > 0:
                y_min = min(coords[0]) * block_size
                y_max = (max(coords[0]) + 1) * block_size
                x_min = min(coords[1]) * block_size
                x_max = (max(coords[1]) + 1) * block_size
                
                w = x_max - x_min
                h = y_max - y_min
                
                if w >= original_size[0] * 0.05 and h >= original_size[1] * 0.05:
                    best_bbox = (x_min, y_min, x_max, y_max)
        
        # ถ้าพบ bounding box ที่ดี ให้ crop
        if best_bbox:
            x_min, y_min, x_max, y_max = best_bbox
            
            # เพิ่ม padding ตามที่ผู้ใช้กำหนด
            padding_x = margin_px if margin_px > 0 else max(2, int(original_size[0] * 0.005))
            padding_y = margin_px if margin_px > 0 else max(2, int(original_size[1] * 0.005))
            
            x_min = max(0, x_min - padding_x)
            y_min = max(0, y_min - padding_y)
            x_max = min(original_size[0], x_max + padding_x)
            y_max = min(original_size[1], y_max + padding_y)
            
            # ตรวจสอบว่าขนาดไม่เล็กเกินไป
            if (x_max - x_min) >= 10 and (y_max - y_min) >= 10:
                cropped = cell_img.crop((x_min, y_min, x_max, y_max))
                if cropped.size[0] > 0 and cropped.size[1] > 0:
                    return cropped
        
        # ถ้ายังไม่พบ ให้คืนภาพเดิม
        return cell_img
        
    except Exception as e:
        # ถ้าเกิด error ใดๆ ให้คืนภาพเดิม
        return cell_img


def cut_image_by_positions(img, h_positions, v_positions, cut_mode="grid", auto_crop=True, debug=False, crop_intensity=50, margin_px=0):
    """
    ตัดภาพโดยใช้ตำแหน่งขอบที่ตรวจจับได้จริง
    
    Args:
        img: PIL Image object
        h_positions: list of y positions (horizontal lines)
        v_positions: list of x positions (vertical lines)
        cut_mode: "grid", "vertical", "horizontal"
        auto_crop: ถ้า True จะ crop เฉพาะส่วนที่เป็นรูปภาพจริงๆ
        debug: ถ้า True จะแสดง debug info
        crop_intensity: ความเข้มงวดในการตัดขอบ 0-100
        margin_px: ขอบเพิ่มรอบภาพ (pixels)
    
    Returns:
        list of PIL Image objects
    """
    img_width, img_height = img.size
    
    if debug:
        print(f"DEBUG: cut_image_by_positions - img_size={img_width}x{img_height}, cut_mode={cut_mode}, auto_crop={auto_crop}")
        print(f"DEBUG: h_positions={h_positions}")
        print(f"DEBUG: v_positions={v_positions}")
    
    cells = []
    
    # เพิ่มขอบภาพเข้าไปในตำแหน่ง และกรองค่าที่ใกล้กันเกินไป
    min_gap = 10
    def _dedupe(vals, limit):
        vals = sorted(vals)
        out = []
        for v in vals:
            v = max(0, min(limit, int(v)))
            if not out or v - out[-1] >= min_gap:
                out.append(v)
        return out
    h_boundaries = _dedupe([0] + list(h_positions) + [img_height], img_height)
    v_boundaries = _dedupe([0] + list(v_positions) + [img_width], img_width)
    
    if debug:
        print(f"DEBUG: h_boundaries={h_boundaries}")
        print(f"DEBUG: v_boundaries={v_boundaries}")
    
    if cut_mode == "vertical":
        # ตัดแนวตั้ง (คอลัมน์)
        for i in range(len(v_boundaries) - 1):
            left = v_boundaries[i]
            right = v_boundaries[i + 1]
            cell = img.crop((left, 0, right, img_height))
            
            # Auto crop ถ้าเปิดใช้งาน
            if auto_crop:
                cell = auto_crop_image(cell, crop_intensity=crop_intensity, margin_px=margin_px)
            
            cells.append({
                'image': cell,
                'row': 1,
                'col': i + 1,
                'index': i + 1
            })
        avg_width = sum(c['image'].size[0] for c in cells) // len(cells) if cells else 0
        return cells, avg_width, img_height
    
    elif cut_mode == "horizontal":
        # ตัดแนวนอน (แถว)
        for i in range(len(h_boundaries) - 1):
            top = h_boundaries[i]
            bottom = h_boundaries[i + 1]
            cell = img.crop((0, top, img_width, bottom))
            
            # Auto crop ถ้าเปิดใช้งาน
            if auto_crop:
                cell = auto_crop_image(cell, crop_intensity=crop_intensity, margin_px=margin_px)
            
            cells.append({
                'image': cell,
                'row': i + 1,
                'col': 1,
                'index': i + 1
            })
        avg_height = sum(c['image'].size[1] for c in cells) // len(cells) if cells else 0
        return cells, img_width, avg_height
    
    else:
        # ตัดแบบ grid
        for i in range(len(h_boundaries) - 1):
            for j in range(len(v_boundaries) - 1):
                left = v_boundaries[j]
                top = h_boundaries[i]
                right = v_boundaries[j + 1]
                bottom = h_boundaries[i + 1]
                
                # ตรวจสอบว่าตำแหน่งถูกต้อง
                if left >= right or top >= bottom:
                    if debug:
                        print(f"DEBUG: ERROR - Cell {i+1},{j+1} invalid bounds: left={left}, right={right}, top={top}, bottom={bottom}")
                    continue
                
                if right > img_width or bottom > img_height:
                    if debug:
                        print(f"DEBUG: WARNING - Cell {i+1},{j+1} out of bounds: ({left},{top},{right},{bottom}) vs img {img_width}x{img_height}")
                    right = min(right, img_width)
                    bottom = min(bottom, img_height)
                
                cell = img.crop((left, top, right, bottom))
                
                if debug:
                    print(f"DEBUG: Cell {i+1},{j+1} - Before auto_crop: {cell.size}, bounds=({left},{top},{right},{bottom})")
                
                # Auto crop ถ้าเปิดใช้งาน
                if auto_crop:
                    original_cell_size = cell.size
                    cell = auto_crop_image(cell, crop_intensity=crop_intensity, margin_px=margin_px)
                    if debug and cell.size != original_cell_size:
                        print(f"DEBUG: Cell {i+1},{j+1} - After auto_crop: {cell.size} (was {original_cell_size})")
                
                # ตรวจสอบว่าภาพไม่ว่างเปล่า
                if cell.size[0] == 0 or cell.size[1] == 0:
                    if debug:
                        print(f"DEBUG: ERROR - Cell {i+1},{j+1} is empty! Size: {cell.size}")
                    # ใช้ภาพเดิมก่อน auto_crop
                    cell = img.crop((left, top, right, bottom))
                
                cells.append({
                    'image': cell,
                    'row': i + 1,
                    'col': j + 1,
                    'index': i * (len(v_boundaries) - 1) + j + 1
                })
        
        avg_width = sum(c['image'].size[0] for c in cells) // len(cells) if cells else 0
        avg_height = sum(c['image'].size[1] for c in cells) // len(cells) if cells else 0
        return cells, avg_width, avg_height


def detect_content_blocks(img_pil, pixel_tol=30, gap_purity=0.97, min_cell_ratio=0.05,
                          target_aspect=None):
    """
    ตรวจจับ content blocks แบบ projection-based ที่ใช้ "pixel purity"

    หลักการ: แถว/คอลัมน์ที่เป็น separator คือแถวที่ "เกือบทุก pixel" เป็นสีขอบ
    (ไม่ใช่แค่ค่าเฉลี่ยต่ำ ซึ่งอาจเข้าใจผิดกับภาพ content ที่มืด)

    Args:
        img_pil: PIL Image
        pixel_tol: pixel ถือว่าเป็นสีขอบถ้าต่างจากสีขอบ ≤ tol
        gap_purity: สัดส่วน pixel สีขอบในแถวนั้นถึงจะเรียก gap (0.97 = 97%)
        min_cell_ratio: ขนาดช่องขั้นต่ำ (สัดส่วนของภาพรวม)
        target_aspect: ถ้าระบุ จะ center-crop แต่ละ cell ให้ได้ aspect ratio นี้ (เช่น 16/9)

    Returns:
        (h_ranges, v_ranges, border_color, debug_img)
    """
    arr = np.array(img_pil.convert('RGB'))
    gray = cv2.cvtColor(arr, cv2.COLOR_RGB2GRAY)
    H, W = gray.shape

    # 1) ตรวจสีขอบจาก 4 มุม (ใช้ patch ใหญ่ขึ้นเพื่อหาค่า noise)
    c = max(10, min(H, W) // 40)
    corners = np.concatenate([
        gray[:c, :c].flatten(),
        gray[:c, -c:].flatten(),
        gray[-c:, :c].flatten(),
        gray[-c:, -c:].flatten(),
    ])
    border_val = float(np.median(corners))
    border_std = float(np.std(corners))
    border_is_dark = border_val < 128

    # 2) pixel_tol fixed ตาม spec ไม่ใช้ auto
    auto_tol = pixel_tol

    # 3) Pixel purity
    is_border_pixel = np.abs(gray.astype(np.int16) - border_val) <= auto_tol
    row_border_frac = is_border_pixel.mean(axis=1)
    col_border_frac = is_border_pixel.mean(axis=0)

    # 4) ลอง gap_purity หลายระดับ
    row_is_gap = col_is_gap = None
    for purity in [gap_purity, 0.92, 0.85, 0.75, 0.65]:
        r_gap = row_border_frac >= purity
        c_gap = col_border_frac >= purity
        if r_gap.any() and (~r_gap).any() and c_gap.any() and (~c_gap).any():
            row_is_gap, col_is_gap = r_gap, c_gap
            break

    # 5) Fallback: ใช้ standard deviation (separator rows มี std ต่ำมาก เพราะเป็นสีเดียวกัน)
    if row_is_gap is None:
        row_std = gray.std(axis=1)
        col_std = gray.std(axis=0)
        # separator = std น้อยกว่า 10% ของ std สูงสุด
        row_is_gap = row_std < max(5, row_std.max() * 0.1)
        col_is_gap = col_std < max(5, col_std.max() * 0.1)

    def _runs_of_content(is_gap, length, min_size, min_separator):
        """
        หา content ranges แต่ต้องข้าม gap สั้นเกินไป (ไม่ใช่ separator จริง)
        min_separator: gap ต้องกว้างอย่างน้อยเท่านี้ถึงนับเป็น separator จริง
        """
        # รวม content runs เบื้องต้น
        raw = []
        in_content = False
        start = 0
        for i in range(length):
            if not is_gap[i] and not in_content:
                in_content = True
                start = i
            elif is_gap[i] and in_content:
                in_content = False
                raw.append([start, i])
        if in_content:
            raw.append([start, length])

        if not raw:
            return []

        # ถ้า gap ระหว่าง content run สั้นเกินไป → รวมเข้าด้วยกัน
        merged = [raw[0]]
        for (s, e) in raw[1:]:
            prev = merged[-1]
            if s - prev[1] < min_separator:
                prev[1] = e
            else:
                merged.append([s, e])

        return [(s, e) for (s, e) in merged if e - s >= min_size]

    min_row_size = max(20, int(H * min_cell_ratio))
    min_col_size = max(20, int(W * min_cell_ratio))
    # separator ต้องกว้างอย่างน้อย 0.3% ของภาพ (แต่ไม่น้อยกว่า 3px)
    min_sep_h = max(3, int(H * 0.003))
    min_sep_w = max(3, int(W * 0.003))
    h_ranges = _runs_of_content(row_is_gap, H, min_row_size, min_sep_h)
    v_ranges = _runs_of_content(col_is_gap, W, min_col_size, min_sep_w)

    # Regularize: บังคับ cell ทุกอันให้ขนาดเท่ากัน (median)
    # โดยยึดจุดกึ่งกลางของแต่ละ range เดิม แล้ว re-center ด้วย median size
    def _regularize(ranges, total):
        if len(ranges) < 2:
            return ranges
        sizes = [r1 - r0 for (r0, r1) in ranges]
        med = int(np.median(sizes))
        out = []
        for (r0, r1) in ranges:
            center = (r0 + r1) // 2
            new0 = max(0, center - med // 2)
            new1 = min(total, new0 + med)
            new0 = max(0, new1 - med)
            out.append((new0, new1))
        return out

    h_ranges = _regularize(h_ranges, H)
    v_ranges = _regularize(v_ranges, W)

    # 4) ถ้าระบุ target_aspect → center-crop แต่ละ range (apply ตอน cut)
    # เก็บไว้คืนกลับ ให้ cut_image_by_ranges handle
    if target_aspect:
        h_ranges = [(y0, y1) for (y0, y1) in h_ranges]
        v_ranges = [(x0, x1) for (x0, x1) in v_ranges]

    debug_img = arr.copy()
    for (y0, y1) in h_ranges:
        for (x0, x1) in v_ranges:
            cv2.rectangle(debug_img, (x0, y0), (x1 - 1, y1 - 1), (0, 255, 0), 2)

    return h_ranges, v_ranges, int(border_val), debug_img


def _fit_aspect(x0, y0, x1, y1, target_aspect, img_w=None, img_h=None):
    """ปรับ box ให้มี aspect = target_aspect โดย**ขยายออก**เมื่อทำได้ (ไม่ตัดเนื้อหา)
    ถ้าขยายชนขอบภาพแล้วยังไม่ได้ aspect → ค่อย crop ฝั่งตรงข้าม"""
    w = x1 - x0
    h = y1 - y0
    if w <= 0 or h <= 0 or target_aspect is None:
        return x0, y0, x1, y1
    current = w / h
    if abs(current - target_aspect) < 1e-3:
        return x0, y0, x1, y1

    if current < target_aspect:
        # แคบเกิน → ต้องการกว้างขึ้น: ขยายด้านข้าง
        need_w = int(round(h * target_aspect))
        if img_w is not None:
            extra = need_w - w
            left = extra // 2
            right = extra - left
            nx0 = x0 - left
            nx1 = x1 + right
            if nx0 < 0:
                nx1 += -nx0
                nx0 = 0
            if nx1 > img_w:
                nx0 -= (nx1 - img_w)
                nx1 = img_w
            nx0 = max(0, nx0)
            nw = nx1 - nx0
            if nw >= need_w:
                return nx0, y0, nx0 + need_w, y1
            # ขยายไม่พอ → ครอปสูงลงแทน
            new_h = int(round(nw / target_aspect))
            dy = (h - new_h) // 2
            return nx0, y0 + dy, nx1, y0 + dy + new_h
        # ไม่รู้ขนาดภาพ → ครอปสูง
        new_h = int(round(w / target_aspect))
        dy = (h - new_h) // 2
        return x0, y0 + dy, x1, y0 + dy + new_h
    else:
        # กว้างเกิน → ต้องการสูงขึ้น: ขยายบน/ล่าง
        need_h = int(round(w / target_aspect))
        if img_h is not None:
            extra = need_h - h
            top = extra // 2
            bot = extra - top
            ny0 = y0 - top
            ny1 = y1 + bot
            if ny0 < 0:
                ny1 += -ny0
                ny0 = 0
            if ny1 > img_h:
                ny0 -= (ny1 - img_h)
                ny1 = img_h
            ny0 = max(0, ny0)
            nh = ny1 - ny0
            if nh >= need_h:
                return x0, ny0, x1, ny0 + need_h
            new_w = int(round(nh * target_aspect))
            dx = (w - new_w) // 2
            return x0 + dx, ny0, x0 + dx + new_w, ny1
        new_w = int(round(h * target_aspect))
        dx = (w - new_w) // 2
        return x0 + dx, y0, x0 + dx + new_w, y1


def cut_image_by_ranges(img, h_ranges, v_ranges, cut_mode="grid", target_aspect=None):
    """
    ตัดภาพตาม content ranges
    ถ้าระบุ target_aspect จะ center-crop ให้ได้ aspect ratio ที่ต้องการ (เช่น 16/9)
    """
    img_width, img_height = img.size
    cells = []

    def _crop(x0, y0, x1, y1):
        if target_aspect:
            x0, y0, x1, y1 = _fit_aspect(x0, y0, x1, y1, target_aspect, img_w=img_width, img_h=img_height)
        return img.crop((x0, y0, x1, y1))

    if cut_mode == "vertical":
        for j, (x0, x1) in enumerate(v_ranges):
            cells.append({
                'image': _crop(x0, 0, x1, img_height),
                'row': 1, 'col': j + 1, 'index': j + 1,
            })
    elif cut_mode == "horizontal":
        for i, (y0, y1) in enumerate(h_ranges):
            cells.append({
                'image': _crop(0, y0, img_width, y1),
                'row': i + 1, 'col': 1, 'index': i + 1,
            })
    else:
        for i, (y0, y1) in enumerate(h_ranges):
            for j, (x0, x1) in enumerate(v_ranges):
                cells.append({
                    'image': _crop(x0, y0, x1, y1),
                    'row': i + 1, 'col': j + 1,
                    'index': i * len(v_ranges) + j + 1,
                })

    cells = [c for c in cells if c['image'].size[0] > 0 and c['image'].size[1] > 0]
    avg_w = sum(c['image'].size[0] for c in cells) // len(cells) if cells else 0
    avg_h = sum(c['image'].size[1] for c in cells) // len(cells) if cells else 0
    return cells, avg_w, avg_h


def detect_grid_auto(img_pil):
    """
    ตรวจจับ grid อัตโนมัติจากภาพ
    
    Args:
        img_pil: PIL Image object
    
    Returns:
        tuple: (rows, cols, h_positions, v_positions, debug_image) หรือ (None, None, None, None, None) ถ้าไม่พบ
    """
    # แปลง PIL เป็น numpy array
    img_array = np.array(img_pil.convert('RGB'))
    img_gray = cv2.cvtColor(img_array, cv2.COLOR_RGB2GRAY)
    
    # ปรับปรุงภาพเพื่อให้ตรวจจับขอบได้ดีขึ้น
    # ใช้ Gaussian blur เพื่อลด noise
    blurred = cv2.GaussianBlur(img_gray, (5, 5), 0)
    
    # ใช้ adaptive threshold เพื่อหาขอบที่ชัดเจนขึ้น
    thresh = cv2.adaptiveThreshold(
        blurred, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, 
        cv2.THRESH_BINARY_INV, 11, 2
    )
    
    # หาเส้นแนวนอน (horizontal lines)
    horizontal_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (40, 1))
    detected_lines_h = cv2.morphologyEx(thresh, cv2.MORPH_OPEN, horizontal_kernel, iterations=2)
    
    # หาเส้นแนวตั้ง (vertical lines)
    vertical_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (1, 40))
    detected_lines_v = cv2.morphologyEx(thresh, cv2.MORPH_OPEN, vertical_kernel, iterations=2)
    
    # รวมเส้นทั้งสองทิศทาง
    grid = cv2.addWeighted(detected_lines_h, 0.5, detected_lines_v, 0.5, 0.0)
    
    # ใช้ HoughLinesP เพื่อหาเส้น
    # หาเส้นแนวนอน
    h_lines = cv2.HoughLinesP(
        detected_lines_h, 1, np.pi/180, threshold=100,
        minLineLength=img_gray.shape[1]//4, maxLineGap=20
    )
    
    # หาเส้นแนวตั้ง
    v_lines = cv2.HoughLinesP(
        detected_lines_v, 1, np.pi/180, threshold=100,
        minLineLength=img_gray.shape[0]//4, maxLineGap=20
    )
    
    # สร้างภาพ debug
    debug_img = img_array.copy()
    
    # นับจำนวนเส้นที่ไม่ซ้ำกัน
    if h_lines is not None and v_lines is not None:
        # หาเส้นแนวนอนที่ไม่ซ้ำกัน (ประมาณ)
        h_positions = []
        for line in h_lines:
            y = (line[0][1] + line[0][3]) // 2
            h_positions.append(y)
            cv2.line(debug_img, (line[0][0], line[0][1]), (line[0][2], line[0][3]), (0, 255, 0), 2)
        
        # หาเส้นแนวตั้งที่ไม่ซ้ำกัน (ประมาณ)
        v_positions = []
        for line in v_lines:
            x = (line[0][0] + line[0][2]) // 2
            v_positions.append(x)
            cv2.line(debug_img, (line[0][0], line[0][1]), (line[0][2], line[0][3]), (255, 0, 0), 2)
        
        # คำนวณจำนวนแถวและคอลัมน์
        # ใช้การจัดกลุ่มตำแหน่งที่ใกล้กัน
        h_positions = sorted(set(h_positions))
        v_positions = sorted(set(v_positions))
        
        # กรองตำแหน่งที่ใกล้กันเกินไป (tolerance = 10 pixels)
        h_filtered = []
        v_filtered = []
        
        for pos in h_positions:
            if not h_filtered or abs(pos - h_filtered[-1]) > 10:
                h_filtered.append(pos)
        
        for pos in v_positions:
            if not v_filtered or abs(pos - v_filtered[-1]) > 10:
                v_filtered.append(pos)
        
        # จำนวนแถว = จำนวนเส้นแนวนอน - 1 (หรือ +1 ถ้ามีเส้นขอบ)
        # จำนวนคอลัมน์ = จำนวนเส้นแนวตั้ง - 1 (หรือ +1 ถ้ามีเส้นขอบ)
        rows = max(1, len(h_filtered) - 1)
        cols = max(1, len(v_filtered) - 1)
        
        # ถ้าจำนวนแถว/คอลัมน์มากเกินไป อาจจะตรวจจับผิด
        if rows > 50 or cols > 50:
            return None, None, None
        
        # ถ้าจำนวนแถว/คอลัมน์น้อยเกินไป อาจจะไม่ใช่ grid
        if rows < 1 or cols < 1:
            return None, None, None, None, None
        
        return rows, cols, h_filtered, v_filtered, debug_img
    
    # ถ้าไม่พบเส้น ให้ลองวิธีอื่น - ใช้การวิเคราะห์ความแตกต่างของสี
    # หาเส้นโดยใช้ edge detection
    edges = cv2.Canny(blurred, 50, 150)
    
    # ใช้ morphological operations เพื่อเชื่อมเส้น
    kernel_h = np.ones((1, 30), np.uint8)
    kernel_v = np.ones((30, 1), np.uint8)
    
    horizontal = cv2.morphologyEx(edges, cv2.MORPH_CLOSE, kernel_h)
    vertical = cv2.morphologyEx(edges, cv2.MORPH_CLOSE, kernel_v)
    
    # นับจำนวนเส้นโดยการหา contours
    h_contours, _ = cv2.findContours(horizontal, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    v_contours, _ = cv2.findContours(vertical, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    
    if len(h_contours) > 0 and len(v_contours) > 0:
        # หาตำแหน่งจาก contours
        h_positions_from_contours = []
        for contour in h_contours:
            y = int(np.mean([pt[0][1] for pt in contour]))
            h_positions_from_contours.append(y)
        
        v_positions_from_contours = []
        for contour in v_contours:
            x = int(np.mean([pt[0][0] for pt in contour]))
            v_positions_from_contours.append(x)
        
        # กรองตำแหน่ง
        h_filtered = sorted(set(h_positions_from_contours))
        v_filtered = sorted(set(v_positions_from_contours))
        
        # กรองตำแหน่งที่ใกล้กันเกินไป
        h_final = []
        for pos in h_filtered:
            if not h_final or abs(pos - h_final[-1]) > 10:
                h_final.append(pos)
        
        v_final = []
        for pos in v_filtered:
            if not v_final or abs(pos - v_final[-1]) > 10:
                v_final.append(pos)
        
        rows = max(1, len(h_final) - 1)
        cols = max(1, len(v_final) - 1)
        
        if rows <= 50 and cols <= 50 and rows >= 1 and cols >= 1:
            # สร้าง debug image
            debug_img = img_array.copy()
            cv2.drawContours(debug_img, h_contours, -1, (0, 255, 0), 2)
            cv2.drawContours(debug_img, v_contours, -1, (255, 0, 0), 2)
            return rows, cols, h_final, v_final, debug_img
    
    return None, None, None, None, None


def create_zip(cells, base_name, cut_mode="grid"):
    """สร้างไฟล์ ZIP จากภาพที่ตัดแล้ว"""
    zip_buffer = io.BytesIO()
    
    with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
        for cell in cells:
            img_buffer = io.BytesIO()
            cell['image'].save(img_buffer, format='PNG')
            
            if cut_mode == "vertical":
                filename = f"{base_name}_col{cell['col']:02d}.png"
            elif cut_mode == "horizontal":
                filename = f"{base_name}_row{cell['row']:02d}.png"
            else:
                filename = f"{base_name}_row{cell['row']:02d}_col{cell['col']:02d}.png"
            
            zip_file.writestr(filename, img_buffer.getvalue())
    
    zip_buffer.seek(0)
    return zip_buffer




# ═══════════════════════════════════════════════════════════════════
# UI Design — clean, minimal, fast
# ═══════════════════════════════════════════════════════════════════

CSS = """
<style>
/* Hide default Streamlit chrome */
#MainMenu, footer, header[data-testid="stHeader"] { visibility: hidden; }
.block-container { padding-top: 2rem; padding-bottom: 4rem; max-width: 1200px; }

/* Hero */
.hero-title {
    font-size: 2.4rem; font-weight: 700; letter-spacing: -0.02em;
    background: linear-gradient(135deg, #6366f1, #ec4899);
    -webkit-background-clip: text; -webkit-text-fill-color: transparent;
    margin-bottom: 0.25rem;
}
.hero-sub { color: #94a3b8; font-size: 1rem; margin-bottom: 2rem; }

/* Uploader */
section[data-testid="stFileUploadDropzone"] {
    border: 2px dashed #334155 !important;
    border-radius: 14px !important;
    background: rgba(30, 41, 59, 0.3) !important;
    padding: 2rem !important;
    transition: all 0.2s ease;
}
section[data-testid="stFileUploadDropzone"]:hover {
    border-color: #6366f1 !important;
    background: rgba(99, 102, 241, 0.05) !important;
}

/* Result card */
.result-card {
    background: rgba(30, 41, 59, 0.4);
    border: 1px solid #334155;
    border-radius: 14px;
    padding: 1.5rem;
    margin: 1rem 0;
}

/* Chips */
.chip {
    display: inline-block;
    background: rgba(99, 102, 241, 0.15);
    color: #a5b4fc;
    padding: 0.25rem 0.75rem;
    border-radius: 999px;
    font-size: 0.8rem;
    margin-right: 0.5rem;
    font-weight: 500;
}
.chip-ok { background: rgba(34, 197, 94, 0.15); color: #86efac; }

/* Download button polish */
.stDownloadButton > button {
    border-radius: 10px !important;
    font-weight: 600 !important;
    height: 48px !important;
}

/* Image grid spacing */
div[data-testid="column"] img { border-radius: 8px; }

/* Sidebar polish */
section[data-testid="stSidebar"] { background: #0f172a; }
section[data-testid="stSidebar"] h2 { font-size: 1rem !important; color: #cbd5e1; }
</style>
"""

ASPECT_OPTIONS = {
    "ตามต้นฉบับ": None,
    "16:9 (กว้าง)": 16/9,
    "9:16 (แนวตั้ง)": 9/16,
    "4:3": 4/3,
    "1:1 (สี่เหลี่ยม)": 1.0,
    "3:2": 3/2,
}


def detect_cells_cc(img_pil, min_area_ratio=0.02):
    """
    ตรวจจับ cells แบบ Connected Components — robust กับทุก resolution
    ลองหลายกลยุทธ์ (border-distance + Otsu + kernel sizes) แล้วเลือกอันที่ให้ grid สม่ำเสมอและมีจำนวน cell มากที่สุด
    """
    arr = np.array(img_pil.convert('RGB'))
    gray = cv2.cvtColor(arr, cv2.COLOR_RGB2GRAY)
    H, W = gray.shape

    # ตรวจสีขอบ
    c = max(10, min(H, W) // 40)
    corners = np.concatenate([
        gray[:c, :c].flatten(),
        gray[:c, -c:].flatten(),
        gray[-c:, :c].flatten(),
        gray[-c:, -c:].flatten(),
    ])
    border_val = float(np.median(corners))

    def _cluster(values, tol):
        sorted_idx = sorted(range(len(values)), key=lambda i: values[i])
        groups = [[sorted_idx[0]]]
        for idx in sorted_idx[1:]:
            if values[idx] - values[groups[-1][-1]] < tol:
                groups[-1].append(idx)
            else:
                groups.append([idx])
        group_id = [0] * len(values)
        for gid, g in enumerate(groups):
            for idx in g:
                group_id[idx] = gid
        return group_id, len(groups)

    def _try(mask, k, erode_iter=1):
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (k, k))
        m = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel, iterations=1)
        m = cv2.erode(m, kernel, iterations=erode_iter)
        n_labels, _, stats, _ = cv2.connectedComponentsWithStats(m, connectivity=4)
        total_area = H * W
        min_area = total_area * min_area_ratio
        raw = []
        for i in range(1, n_labels):
            x, y, w, h, area = stats[i]
            if area >= min_area and w >= W * 0.05 and h >= H * 0.05:
                raw.append((int(x), int(y), int(w), int(h)))
        if not raw:
            return []
        y_c = [y + h / 2 for (x, y, w, h) in raw]
        x_c = [x + w / 2 for (x, y, w, h) in raw]
        med_h = float(np.median([h for (_, _, _, h) in raw]))
        med_w = float(np.median([w for (_, _, w, _) in raw]))
        row_ids, _ = _cluster(y_c, med_h / 2)
        col_ids, _ = _cluster(x_c, med_w / 2)
        bx = [(x, y, w, h, r + 1, cc + 1) for (x, y, w, h), r, cc in zip(raw, row_ids, col_ids)]
        bx.sort(key=lambda b: (b[4], b[5]))
        return bx

    # สร้าง candidate masks: border-distance หลายค่า + Otsu
    candidates = []
    for dist in (25, 40, 60, 15):
        if border_val < 128:
            m = (gray > border_val + dist).astype(np.uint8) * 255
        else:
            m = (gray < border_val - dist).astype(np.uint8) * 255
        candidates.append(m)
    # Otsu
    if border_val < 128:
        _, m_otsu = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    else:
        _, m_otsu = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
    candidates.append(m_otsu)

    # Local variance mask — ทนต่อ content สีเข้ม/สว่างที่ใกล้สีขอบ
    # หลักการ: content มี texture (variance สูง), ขอบสีเดียวเรียบ (variance ต่ำ)
    blur_k = max(5, min(H, W) // 100) | 1  # odd
    g32 = gray.astype(np.float32)
    mean = cv2.blur(g32, (blur_k, blur_k))
    sqmean = cv2.blur(g32 * g32, (blur_k, blur_k))
    var = np.clip(sqmean - mean * mean, 0, None)
    std_map = np.sqrt(var)
    for th in (5.0, 10.0, 20.0):
        m_var = (std_map > th).astype(np.uint8) * 255
        candidates.append(m_var)

    # Color saturation mask — content มีสี, ขอบดำ/ขาวไม่มีสี
    hsv = cv2.cvtColor(arr, cv2.COLOR_RGB2HSV)
    sat = hsv[:, :, 1]
    for th in (15, 30):
        m_sat = (sat > th).astype(np.uint8) * 255
        candidates.append(m_sat)

    # kernel sizes หลายค่า ครอบคลุมทั้ง low-res และ 4K (separator บางลง relative)
    base = min(H, W)
    kernel_sizes = sorted(set([
        max(3, base // 300),
        max(3, base // 200),
        max(3, base // 150),
        max(3, base // 100),
        max(3, base // 70),
    ]))
    erode_iters = [1, 2, 3]

    # Score: เลือก boxes ที่ regular + มีจำนวน cell มาก + variance ต่ำ
    def _score(bx):
        if not bx or not _boxes_are_regular_grid(bx):
            return -1
        ws = [b[2] for b in bx]
        hs = [b[3] for b in bx]
        med_w = float(np.median(ws)) or 1
        med_h = float(np.median(hs)) or 1
        var = (float(np.std(ws)) / med_w + float(np.std(hs)) / med_h)
        return len(bx) * 1000 - var * 100

    best_boxes = []
    best_score = -1
    for mask in candidates:
        for k in kernel_sizes:
            for it in erode_iters:
                bx = _try(mask, k, erode_iter=it)
                s = _score(bx)
                if s > best_score:
                    best_score = s
                    best_boxes = bx

    if not best_boxes:
        # สุดท้ายลอง Otsu kernel เริ่มต้น (เผื่อไม่ regular แต่ยังดีกว่าไม่มีอะไร)
        best_boxes = _try(m_otsu, kernel_sizes[0])

    boxes = best_boxes
    if not boxes:
        debug_img = arr.copy()
        return [], int(border_val), debug_img

    # 7) Debug image: วาดกรอบ + เลข
    debug_img = arr.copy()
    for (x, y, w, h, r, c) in boxes:
        cv2.rectangle(debug_img, (x, y), (x + w, y + h), (0, 255, 0), 3)
        cv2.putText(debug_img, f"R{r}C{c}", (x + 10, y + 40),
                    cv2.FONT_HERSHEY_SIMPLEX, 1.0, (0, 255, 255), 2)

    return boxes, int(border_val), debug_img


def detect_cells_by_borders(img_pil):
    """
    ตรวจจับ grid จาก "ขอบ" (ทางตรงข้าม CC ที่หา content)
    หลักการ: ขอบ = สีเดียวเรียบ → row/col ที่ 100% เป็นสีขอบ = separator
    Sweep หลาย (tol, purity) แล้วเลือกผลที่ได้ grid ใหญ่ที่สุดและสม่ำเสมอ
    """
    arr = np.array(img_pil.convert('RGB'))
    gray = cv2.cvtColor(arr, cv2.COLOR_RGB2GRAY)
    H, W = gray.shape

    c = max(10, min(H, W) // 40)
    corners = np.concatenate([
        gray[:c, :c].flatten(), gray[:c, -c:].flatten(),
        gray[-c:, :c].flatten(), gray[-c:, -c:].flatten(),
    ])
    corner_median = float(np.median(corners))
    corner_std = float(np.std(corners))
    # ถ้ามุมมี variance สูง แปลว่ามุมเป็น content (ไม่ใช่ขอบสีเดียว)
    # → ลองหลายค่า: จากมุม + 0 (ดำ) + 255 (ขาว)
    border_candidates = {int(corner_median), 0, 255}
    border_val = corner_median
    gi = gray.astype(np.int32)

    def _runs_false(flags, min_run):
        """หา run ของค่า False → คืน [(start, end), ...] ที่ยาว ≥ min_run"""
        ranges = []
        n = len(flags)
        i = 0
        while i < n:
            if not flags[i]:
                j = i
                while j < n and not flags[j]:
                    j += 1
                if j - i >= min_run:
                    ranges.append((i, j))
                i = j
            else:
                i += 1
        return ranges

    best = None
    best_score = -1
    min_cell_ratio = 0.05

    for bval in border_candidates:
     for tol in (5, 10, 15, 25, 40):
        border_mask = (np.abs(gi - bval) < tol)
        row_frac = border_mask.mean(axis=1)
        col_frac = border_mask.mean(axis=0)
        for purity in (0.98, 0.95, 0.90):
            row_sep = row_frac >= purity
            col_sep = col_frac >= purity
            h_ranges = _runs_false(row_sep, int(H * min_cell_ratio))
            v_ranges = _runs_false(col_sep, int(W * min_cell_ratio))
            if not h_ranges or not v_ranges:
                continue
            # Build boxes
            bx = []
            for ri, (y0, y1) in enumerate(h_ranges):
                for ci, (x0, x1) in enumerate(v_ranges):
                    bx.append((x0, y0, x1 - x0, y1 - y0, ri + 1, ci + 1))
            if not _boxes_are_regular_grid(bx, tol=0.15):
                continue
            ws = [b[2] for b in bx]
            hs = [b[3] for b in bx]
            med_w = float(np.median(ws)) or 1
            med_h = float(np.median(hs)) or 1
            var = (float(np.std(ws)) / med_w + float(np.std(hs)) / med_h)
            score = len(bx) * 1000 - var * 500
            if score > best_score:
                best_score = score
                best = bx
                border_val = bval

    debug_img = arr.copy()
    if best:
        for (x, y, w, h, r, c) in best:
            cv2.rectangle(debug_img, (x, y), (x + w, y + h), (0, 200, 255), 3)
            cv2.putText(debug_img, f"R{r}C{c}", (x + 10, y + 40),
                        cv2.FONT_HERSHEY_SIMPLEX, 1.0, (0, 255, 0), 2)
    return best or [], int(border_val), debug_img


def _boxes_are_regular_grid(boxes, tol=0.20):
    """ตรวจว่า boxes สร้าง grid ที่สม่ำเสมอหรือไม่ (ขนาดต่างกัน ≤ 30%)"""
    if len(boxes) < 2:
        return False
    ws = [b[2] for b in boxes]
    hs = [b[3] for b in boxes]
    med_w = float(np.median(ws))
    med_h = float(np.median(hs))
    if med_w == 0 or med_h == 0:
        return False
    for (_, _, w, h, _, _) in boxes:
        if abs(w - med_w) / med_w > tol or abs(h - med_h) / med_h > tol:
            return False
    return True


def _boxes_from_ranges(h_ranges, v_ranges):
    """แปลง ranges (projection) → boxes เพื่อ pipeline เดียว"""
    boxes = []
    for ri, (y0, y1) in enumerate(h_ranges):
        for ci, (x0, x1) in enumerate(v_ranges):
            boxes.append((x0, y0, x1 - x0, y1 - y0, ri + 1, ci + 1))
    return boxes


def _process_one(img, cut_mode, target_aspect):
    """Primary: Connected Components. Fallback: Projection-based"""
    W, H = img.size
    megapixels = (W * H) / 1_000_000

    # Primary: border-based detection (แม่นที่สุด — ใช้สีขอบเป็น anchor)
    boxes, border_val, dbg = detect_cells_by_borders(img)
    method = "borders"

    # ถ้า cut_mode = vertical/horizontal → ยุบเป็นแถวเดียว / คอลัมน์เดียว
    def _collapse(bx, mode):
        if not bx:
            return bx
        if mode == "vertical":
            # 1 row, M cols: ใช้ x-range ของแต่ละคอลัมน์, y เต็มภาพ
            cols_set = sorted({b[5] for b in bx})
            new = []
            for ci, c in enumerate(cols_set):
                col_boxes = [b for b in bx if b[5] == c]
                x_min = min(b[0] for b in col_boxes)
                x_max = max(b[0] + b[2] for b in col_boxes)
                new.append((x_min, 0, x_max - x_min, H, 1, ci + 1))
            return new
        if mode == "horizontal":
            rows_set = sorted({b[4] for b in bx})
            new = []
            for ri, r in enumerate(rows_set):
                row_boxes = [b for b in bx if b[4] == r]
                y_min = min(b[1] for b in row_boxes)
                y_max = max(b[1] + b[3] for b in row_boxes)
                new.append((0, y_min, W, y_max - y_min, ri + 1, 1))
            return new
        return bx

    def _grid_score(bx):
        if not bx or not _boxes_are_regular_grid(bx):
            return -1
        ws = [b[2] for b in bx]; hs = [b[3] for b in bx]
        mw = float(np.median(ws)) or 1; mh = float(np.median(hs)) or 1
        return len(bx) * 1000 - (float(np.std(ws))/mw + float(np.std(hs))/mh) * 500

    best_score = _grid_score(boxes)

    # เทียบกับ CC
    bx_cc, bv_cc, dbg_cc = detect_cells_cc(img)
    s_cc = _grid_score(bx_cc)
    if s_cc > best_score:
        boxes, border_val, dbg, method, best_score = bx_cc, bv_cc, dbg_cc, "cc", s_cc

    # เทียบกับ projection เดิม
    h_ranges, v_ranges, bv2, dbg2 = detect_content_blocks(img)
    if h_ranges and v_ranges:
        fb = _boxes_from_ranges(h_ranges, v_ranges)
        s_fb = _grid_score(fb)
        if s_fb > best_score:
            boxes, border_val, dbg, method, best_score = fb, bv2, dbg2, "projection", s_fb

    # ถ้าไม่มี method ไหน regular → ใช้อันที่ได้ cells เยอะสุด
    if not boxes:
        for cand in [(bx_cc, bv_cc, dbg_cc, "cc"),
                     (_boxes_from_ranges(h_ranges or [], v_ranges or []), bv2, dbg2, "projection")]:
            if cand[0] and len(cand[0]) > len(boxes or []):
                boxes, border_val, dbg, method = cand

    # Collapse ตาม cut_mode
    boxes = _collapse(boxes, cut_mode)

    debug = {
        'method': method,
        'boxes': boxes,
        'border_val': border_val,
        'debug_img': dbg,
        'megapixels': round(megapixels, 1),
    }
    if not boxes:
        return None, None, None, None, debug

    # === Grid-geometry regularization ===
    # สร้างช่องจากเรขาคณิตของ grid แทนการใช้ bbox ดิบแต่ละอัน
    img_w, img_h = img.size
    rows_set = sorted({b[4] for b in boxes})
    cols_set = sorted({b[5] for b in boxes})
    N, M = len(rows_set), len(cols_set)

    # Outer frame
    x_min = min(b[0] for b in boxes)
    x_max = max(b[0] + b[2] for b in boxes)
    y_min = min(b[1] for b in boxes)
    y_max = max(b[1] + b[3] for b in boxes)

    # Cell size จากค่ามัธยฐาน แล้วหารพื้นที่รวมให้สมมาตร
    med_w = float(np.median([b[2] for b in boxes]))
    med_h = float(np.median([b[3] for b in boxes]))
    frame_w = x_max - x_min
    frame_h = y_max - y_min
    gap_x = max(0, (frame_w - M * med_w) / max(1, M - 1)) if M > 1 else 0
    gap_y = max(0, (frame_h - N * med_h) / max(1, N - 1)) if N > 1 else 0
    cell_w = (frame_w - (M - 1) * gap_x) / M
    cell_h = (frame_h - (N - 1) * gap_y) / N

    # Snap aspect ratio ที่ระดับ grid (ใช้ค่ากลาง ไม่ใช่ per-cell jitter)
    if target_aspect:
        cur = cell_w / cell_h if cell_h > 0 else target_aspect
        if cur > target_aspect:
            cell_w = cell_h * target_aspect
        else:
            cell_h = cell_w / target_aspect

    # กำหนดขนาดคงที่ให้ทุก cell (หลังจาก clamp ขอบภาพแล้ว) — ทุกรูปจะ w×h เท่ากันเป๊ะ
    cw_px = int(round(cell_w))
    ch_px = int(round(cell_h))
    cw_px = max(1, min(cw_px, img_w))
    ch_px = max(1, min(ch_px, img_h))

    cells = []
    for ri, r in enumerate(rows_set):
        for ci, c in enumerate(cols_set):
            slot_cx = x_min + ci * (frame_w / M) + (frame_w / M) / 2
            slot_cy = y_min + ri * (frame_h / N) + (frame_h / N) / 2
            x0 = int(round(slot_cx - cw_px / 2))
            y0 = int(round(slot_cy - ch_px / 2))
            # clamp ให้อยู่ในภาพ โดย**รักษาขนาด**คงที่
            if x0 < 0: x0 = 0
            if y0 < 0: y0 = 0
            if x0 + cw_px > img_w: x0 = img_w - cw_px
            if y0 + ch_px > img_h: y0 = img_h - ch_px
            x1 = x0 + cw_px
            y1 = y0 + ch_px
            cells.append({
                'image': img.crop((x0, y0, x1, y1)),
                'row': r, 'col': c, 'index': len(cells) + 1,
            })
    cells = [c for c in cells if c['image'].size[0] > 0 and c['image'].size[1] > 0]
    if not cells:
        return None, None, None, None, debug
    cw = sum(c['image'].size[0] for c in cells) // len(cells)
    ch = sum(c['image'].size[1] for c in cells) // len(cells)
    return cells, cw, ch, border_val, debug


def _render_result_card(uf, img, cells, cw, ch, border_val, cut_mode, idx, debug=None, naming_mode="sequential"):
    """การ์ดผลลัพธ์ 1 ภาพ — แสดงสรุป, พรีวิว grid จริง, ปุ่มดาวน์โหลด"""
    base_name = Path(uf.name).stem
    with st.container(border=True):
        # Header
        st.markdown(f"#### {uf.name}")
        border_type = "ขอบดำ" if border_val is not None and border_val < 128 else "ขอบขาว"
        rows_in = max(c['row'] for c in cells)
        cols_in = max(c['col'] for c in cells)
        st.markdown(
            f"<span class='chip chip-ok'>{len(cells)} ช่อง</span>"
            f"<span class='chip'>{rows_in}×{cols_in}</span>"
            f"<span class='chip'>ต้นฉบับ {img.size[0]}×{img.size[1]}</span>"
            f"<span class='chip'>แต่ละช่อง {cw}×{ch}px</span>"
            f"<span class='chip'>{border_type}</span>",
            unsafe_allow_html=True,
        )
        st.write("")

        # Preview — grid ตามโครงสร้างจริง
        cells_sorted = sorted(cells, key=lambda c: (c['row'], c['col']))
        preview_cols = max(1, min(cols_in, 4))
        for i in range(0, len(cells_sorted), preview_cols):
            row = st.columns(preview_cols)
            for j, cell in enumerate(cells_sorted[i:i+preview_cols]):
                with row[j]:
                    st.image(cell['image'], use_container_width=True)

        # Download
        ordered = sorted(cells, key=lambda c: (c['row'], c['col']))
        pad = max(2, len(str(len(ordered))))
        zip_buf = io.BytesIO()
        with zipfile.ZipFile(zip_buf, 'w', zipfile.ZIP_DEFLATED) as zf:
            for n, cell in enumerate(ordered, start=1):
                b = io.BytesIO()
                cell['image'].save(b, format='PNG')
                if naming_mode == "sequential":
                    fn = f"{base_name}_{str(n).zfill(pad)}.png"
                elif cut_mode == "vertical":
                    fn = f"{base_name}_col{cell['col']:02d}.png"
                elif cut_mode == "horizontal":
                    fn = f"{base_name}_row{cell['row']:02d}.png"
                else:
                    fn = f"{base_name}_r{cell['row']:02d}c{cell['col']:02d}.png"
                zf.writestr(fn, b.getvalue())
        zip_buf.seek(0)
        st.download_button(
            f"ดาวน์โหลด {len(cells)} ภาพ (.zip)",
            data=zip_buf,
            file_name=f"{base_name}.zip",
            mime="application/zip",
            key=f"dl_{idx}",
            use_container_width=True,
        )

        # Debug info
        if debug:
            with st.expander("🔧 รายละเอียดการตรวจจับ"):
                method_label = {
                    "cc": "Connected Components",
                    "projection": "Projection (fallback)",
                }.get(debug.get('method'), debug.get('method', '?'))
                st.caption(
                    f"วิธี: **{method_label}** · "
                    f"Border value: {debug.get('border_val')} · "
                    f"MP: {debug.get('megapixels')}"
                )
                if debug.get('debug_img') is not None:
                    st.image(debug['debug_img'], caption="กรอบที่ตรวจจับได้", use_container_width=True)
        return zip_buf.getvalue()


def main():
    st.set_page_config(
        page_title="Image Splitter",
        page_icon="✂️",
        layout="centered",
        initial_sidebar_state="collapsed",
    )
    st.markdown(CSS, unsafe_allow_html=True)

    # Sidebar — minimal
    with st.sidebar:
        st.markdown("## ตั้งค่า")
        aspect_label = st.selectbox(
            "Aspect ratio ผลลัพธ์",
            list(ASPECT_OPTIONS.keys()),
            index=1,
        )
        target_aspect = ASPECT_OPTIONS[aspect_label]

        cut_mode_label = st.radio(
            "ทิศทางการตัด",
            ["Grid", "แนวตั้ง", "แนวนอน"],
            index=0,
            horizontal=True,
        )
        cut_mode = {"Grid": "grid", "แนวตั้ง": "vertical", "แนวนอน": "horizontal"}[cut_mode_label]

        naming_label = st.radio(
            "ตั้งชื่อไฟล์",
            ["เรียงเลข (1, 2, 3...)", "ตามตำแหน่ง (R1C1, R1C2...)"],
            index=0,
            horizontal=False,
        )
        naming_mode = "sequential" if naming_label.startswith("เรียง") else "position"

        st.markdown("---")
        st.caption(
            "ระบบจะตรวจจับขอบ (ดำ/ขาว) อัตโนมัติ "
            "และ crop ให้ได้ aspect ratio ที่เลือก"
        )

    # Hero
    st.markdown('<div class="hero-title">Image Splitter</div>', unsafe_allow_html=True)
    st.markdown(
        '<div class="hero-sub">ตัดภาพ grid เป็นภาพย่อยอัตโนมัติ · รองรับหลายไฟล์พร้อมกัน</div>',
        unsafe_allow_html=True,
    )

    # Upload
    uploaded = st.file_uploader(
        "อัพโหลดภาพ",
        type=['png', 'jpg', 'jpeg', 'bmp', 'gif', 'webp'],
        accept_multiple_files=True,
        label_visibility="collapsed",
    )

    if not uploaded:
        st.info("ลากไฟล์มาวาง หรือคลิกเลือก — รองรับหลายไฟล์พร้อมกัน")
        return

    # Process all
    all_entries = []
    processed = []  # [(uf, cells_sorted)]
    failed = []

    for idx, uf in enumerate(uploaded):
        try:
            img = Image.open(uf)
        except Exception as e:
            failed.append((uf.name, str(e)))
            continue

        with st.spinner(f"กำลังประมวลผล {uf.name}..."):
            cells, cw, ch, border_val, dbg = _process_one(img, cut_mode, target_aspect)

        if not cells:
            err = (
                f"ตรวจจับขอบไม่ได้ — border_val={dbg.get('border_val')}, "
                f"tol={dbg.get('tol_used')}, MP={dbg.get('megapixels')}, "
                f"h_ranges={len(dbg.get('h_ranges') or [])}, "
                f"v_ranges={len(dbg.get('v_ranges') or [])}"
            )
            failed.append((uf.name, err))
            with st.container(border=True):
                st.markdown(f"#### ⚠️ {uf.name} — ตรวจจับไม่ได้")
                st.caption(err)
                if dbg.get('debug_img') is not None:
                    st.image(dbg['debug_img'], caption="สิ่งที่ระบบเห็น", use_container_width=True)
            continue

        zip_bytes = _render_result_card(uf, img, cells, cw, ch, border_val, cut_mode, idx, debug=dbg, naming_mode=naming_mode)
        processed.append((uf, sorted(cells, key=lambda c: (c['row'], c['col']))))

    # Combined ZIP — global sequential numbering across all files
    if naming_mode == "sequential":
        total = sum(len(cs) for _, cs in processed)
        pad = max(3, len(str(total)))
        counter = 1
        for uf, cs in processed:
            base_name = Path(uf.name).stem
            for cell in cs:
                b = io.BytesIO()
                cell['image'].save(b, format='PNG')
                fn = f"{str(counter).zfill(pad)}_{base_name}.png"
                all_entries.append((fn, b.getvalue()))
                counter += 1
    else:
        for uf, cs in processed:
            base_name = Path(uf.name).stem
            for cell in cs:
                b = io.BytesIO()
                cell['image'].save(b, format='PNG')
                if cut_mode == "vertical":
                    fn = f"{base_name}/col{cell['col']:02d}.png"
                elif cut_mode == "horizontal":
                    fn = f"{base_name}/row{cell['row']:02d}.png"
                else:
                    fn = f"{base_name}/r{cell['row']:02d}c{cell['col']:02d}.png"
                all_entries.append((fn, b.getvalue()))

    if len(uploaded) > 1 and all_entries:
        st.markdown("---")
        combined = io.BytesIO()
        with zipfile.ZipFile(combined, 'w', zipfile.ZIP_DEFLATED) as zf:
            for fn, data in all_entries:
                zf.writestr(fn, data)
        combined.seek(0)
        st.download_button(
            f"ดาวน์โหลดทั้งหมด — {len(all_entries)} ภาพ จาก {len(uploaded)} ไฟล์",
            data=combined,
            file_name="all_images.zip",
            mime="application/zip",
            type="primary",
            use_container_width=True,
        )

    if failed:
        with st.expander(f"{len(failed)} ไฟล์ที่มีปัญหา"):
            for name, err in failed:
                st.write(f"• **{name}** — {err}")


if __name__ == "__main__":
    main()

# -*- coding: utf-8 -*-
"""
KwanNurse-Bot v3.0 - Perfect Core Features
3 Core Features: ReportSymptoms, AssessRisk, RequestAppointment
Optimized for production use with enhanced error handling and user experience
"""
from flask import Flask, request, jsonify
import gspread
from datetime import datetime, date
import os
import json
import requests
import logging
import re
from zoneinfo import ZoneInfo

# ---------- App config ----------
app = Flask(__name__)
DEBUG = os.environ.get("DEBUG", "false").lower() in ("1", "true", "yes")
logging.basicConfig(level=logging.DEBUG if DEBUG else logging.INFO,
                    format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

LOCAL_TZ = ZoneInfo("Asia/Bangkok")
WORKSHEET_LINK = os.environ.get("WORKSHEET_LINK", "https://docs.google.com/spreadsheets/d/1Jteh4XLzgQM3YKMzUeW3PGuBjUkvnS61rm2IXfGPnPo/edit?usp=sharing")
LINE_CHANNEL_ACCESS_TOKEN = os.environ.get("CHANNEL_ACCESS_TOKEN")
NURSE_GROUP_ID = os.environ.get("NURSE_GROUP_ID")

# ---------- gspread helper ----------
def get_sheet_client():
    try:
        creds_env = os.environ.get("GSPREAD_CREDENTIALS")
        if creds_env:
            creds_json = json.loads(creds_env)
            if hasattr(gspread, "service_account_from_dict"):
                return gspread.service_account_from_dict(creds_json)
        if os.path.exists("credentials.json"):
            return gspread.service_account(filename="credentials.json")
        logger.warning("No Google credentials found (credentials.json or GSPREAD_CREDENTIALS).")
    except Exception:
        logger.exception("Connect Sheet Error")
    return None

# ---------- LINE push helper ----------
def send_line_push(message, target_id=None):
    """Send LINE push notification to nurse group or specific user"""
    try:
        access_token = LINE_CHANNEL_ACCESS_TOKEN
        if not target_id:
            target_id = NURSE_GROUP_ID
        
        if not access_token or not target_id:
            logger.warning("LINE token or target_id not configured.")
            return False
            
        url = 'https://api.line.me/v2/bot/message/push'
        headers = {
            'Content-Type': 'application/json',
            'Authorization': f'Bearer {access_token}'
        }
        payload = {
            "to": target_id,
            "messages": [{"type": "text", "text": message}]
        }
        
        resp = requests.post(url, headers=headers, json=payload, timeout=8)
        if resp.status_code // 100 == 2:
            logger.info("Push Notification Sent to %s", target_id)
            return True
        else:
            logger.error("LINE push failed: %s %s", resp.status_code, resp.text)
            return False
    except Exception: 
        logger.exception("Push Error")
        return False

# ---------- Helpers for date/time/phone ----------
def parse_date_iso(s: str):
    """Validate YYYY-MM-DD -> datetime.date or None. Accept '2026-02-22T00:00:00Z' too."""
    if not s:
        return None
    try:
        if isinstance(s, dict):
            for k in ("date", "value", "original"):
                if k in s and isinstance(s[k], str):
                    s = s[k]
                    break
            else:
                s = json.dumps(s, ensure_ascii=False)
        s2 = str(s).split("T")[0]
        return datetime.strptime(s2.strip(), "%Y-%m-%d").date()
    except Exception:
        try:
            m = re.search(r'(\d{4}-\d{2}-\d{2})', str(s))
            if m:
                return datetime.strptime(m.group(1), "%Y-%m-%d").date()
        except Exception:
            return None
    return None

def parse_time_hhmm(s: str):
    """Normalize various time shapes into 'HH:MM' or None."""
    if not s:
        return None
    try: 
        if isinstance(s, dict):
            s = json.dumps(s, ensure_ascii=False)
        s = str(s).strip()
        if "T" in s:
            parts = s.split("T")[-1]
            s = parts
        parts = s.split(":")
        if len(parts) >= 2 and parts[0].isdigit() and parts[1].isdigit():
            h = int(parts[0]) % 24
            m = int(parts[1]) % 60
            return f"{h:02d}:{m:02d}"
        m = re.search(r'(\d{1,2})[:.]\s*(\d{2})', s)
        if m:
            h = int(m.group(1)) % 24
            m2 = int(m.group(2)) % 60
            return f"{h:02d}:{m2:02d}"
    except Exception:
        logger.exception("parse_time_hhmm error")
    return None

TIME_OF_DAY_MAP = {
    "morning": "09:00",
    "late_morning": "10:30",
    "noon": "12:00",
    "afternoon": "14:00",
    "evening": "18:00",
    "night": "20:00",
    "เช้า": "09:00",
    "สาย": "10:30",
    "เที่ยง": "12:00",
    "บ่าย": "14:00",
    "เย็น": "18:00",
    "กลางคืน": "20:00"
}

def resolve_time_from_params(sys_time_param, timeofday_param):
    """Prefer explicit time; else map timeofday to default."""
    t = parse_time_hhmm(sys_time_param) if sys_time_param else None
    if t:
        return t
    if not timeofday_param:
        return None
    if isinstance(timeofday_param, dict):
        for k in ("value", "name", "original", "displayName"):
            if k in timeofday_param: 
                timeofday_param = timeofday_param[k]
                break
        else: 
            timeofday_param = json.dumps(timeofday_param, ensure_ascii=False)
    if isinstance(timeofday_param, str):
        key = timeofday_param.strip().lower()
        if key in TIME_OF_DAY_MAP: 
            return TIME_OF_DAY_MAP[key]
        if "morning" in key or "เช้า" in key:
            return TIME_OF_DAY_MAP["morning"]
        if "afternoon" in key or "บ่าย" in key or "pm" in key:
            return TIME_OF_DAY_MAP["afternoon"]
        if "evening" in key or "เย็น" in key:
            return TIME_OF_DAY_MAP["evening"]
        if "noon" in key or "เที่ยง" in key:
            return TIME_OF_DAY_MAP["noon"]
    return None

def normalize_phone_number(raw: str):
    """Normalize various phone formats to local '0xxxxxxxxx' or return raw digits if unknown."""
    if not raw:
        return None
    s = str(raw).strip()
    s = re.sub(r"[^\d+]", "", s)
    if s.startswith("+"):
        if s.startswith("+66"):
            s = "0" + s[3:]
        else:
            s = s.lstrip("+")
    elif s.startswith("66") and len(s) > 2:
        s = "0" + s[2:]
    return s

def is_valid_thai_mobile(s: str):
    """Basic check: 10 digits starting with 0 and second digit 6-9 (typical mobile)"""
    if not s:
        return False
    if not s.isdigit():
        return False
    return len(s) == 10 and s.startswith("0") and s[1] in "6789"

# ========== CORE FEATURE 1: REPORT SYMPTOMS (Enhanced) ==========

def save_symptom_data(user_id, pain, wound, fever, mobility, risk_result, risk_score):
    """Save symptom report to Google Sheets with enhanced data"""
    try:
        client = get_sheet_client()
        if not client:
            logger.error("No gspread client available.")
            return False
            
        spreadsheet = client.open('KhwanBot_Data')
        sheet = spreadsheet.worksheet('SymptomLog')
        
        timestamp = datetime.now(tz=LOCAL_TZ).strftime("%Y-%m-%d %H:%M:%S")
        row = [
            timestamp,
            user_id,
            pain or "",
            wound or "",
            fever or "",
            mobility or "",
            risk_result,
            risk_score
        ]
        sheet.append_row(row, value_input_option='USER_ENTERED')
        logger.info("Symptom data saved for user %s", user_id)
        return True
    except Exception:
        logger.exception("Save Symptom Error")
        return False

def calculate_symptom_risk(user_id, pain, wound, fever, mobility):
    """
    Enhanced symptom risk calculation with detailed feedback
    Returns: (message, risk_level, risk_score)
    """
    risk_score = 0
    risk_details = []
    
    # Pain Score Analysis
    try:
        p_val = int(pain) if pain is not None and str(pain).strip() != "" else 0
    except: 
        p_val = 0
    
    if p_val >= 8:
        risk_score += 3
        risk_details.append(f"🔴 ความปวดระดับสูง ({p_val}/10)")
    elif p_val >= 6:
        risk_score += 1
        risk_details.append(f"🟡 ความปวดปานกลาง ({p_val}/10)")
    elif p_val > 0:
        risk_details.append(f"🟢 ความปวดเล็กน้อย ({p_val}/10)")
    
    # Wound Status Analysis
    wound_text = str(wound or "").lower()
    if any(x in wound_text for x in ["หนอง", "มีกลิ่น", "แฉะ", "pus", "discharge"]):
        risk_score += 3
        risk_details.append("🔴 แผลมีหนองหรือมีกลิ่น - ต้องพบแพทย์ทันที!")
    elif any(x in wound_text for x in ["บวมแดง", "อักเสบ", "swelling", "red", "inflamed"]):
        risk_score += 2
        risk_details.append("🟡 แผลบวมแดงอักเสบ")
    elif any(x in wound_text for x in ["ปกติ", "ดี", "แห้ง", "normal", "dry", "good"]):
        risk_details.append("🟢 สภาพแผลปกติ")
    
    # Fever Check
    fever_text = str(fever or "").lower()
    if any(x in fever_text for x in ["มี", "ตัวร้อน", "fever", "hot", "ไข้"]):
        risk_score += 2
        risk_details.append("🔴 มีไข้ - อาจมีการติดเชื้อ")
    else:
        risk_details.append("🟢 ไม่มีไข้")
    
    # Mobility Status
    mobility_text = str(mobility or "").lower()
    if any(x in mobility_text for x in ["ไม่ได้", "ติดเตียง", "ไม่เดิน", "cannot", "bedridden"]):
        risk_score += 1
        risk_details.append("🟡 เคลื่อนไหวลำบาก")
    elif any(x in mobility_text for x in ["เดินได้", "ปกติ", "normal", "can walk"]):
        risk_details.append("🟢 เคลื่อนไหวได้ปกติ")
    
    # Risk Level Classification
    if risk_score >= 5:
        risk_level = "🚨 อันตราย - ต้องพบแพทย์ทันที!"
        emoji = "🚨"
        action = "กรุณาติดต่อพยาบาลหรือมาโรงพยาบาลทันที!"
        color = "🔴"
    elif risk_score >= 3:
        risk_level = "⚠️ เสี่ยงสูง"
        emoji = "⚠️"
        action = "กรุณากดปุ่ม 'ปรึกษาพยาบาล' หรือโทรติดต่อทันที"
        color = "🟠"
    elif risk_score >= 2:
        risk_level = "🟡 เสี่ยงปานกลาง"
        emoji = "🟡"
        action = "เฝ้าระวังอาการใกล้ชิด 24 ชม. ถ้าอาการแย่กรุณาติดต่อ"
        color = "🟡"
    elif risk_score == 1:
        risk_level = "🟢 เสี่ยงต่ำ (เฝ้าระวัง)"
        emoji = "🟢"
        action = "โดยรวมปกติดี แต่ต้องสังเกตอาการต่อไป"
        color = "🟢"
    else:
        risk_level = "✅ ปกติดี"
        emoji = "✅"
        action = "แผลหายดี ยอดเยี่ยมมาก! กรุณารายงานอาการต่อเนื่อง"
        color = "🟢"
    
    # Build message
    message = f"{emoji} ผลประเมินอาการ\n"
    message += "=" * 30 + "\n\n"
    message += "📋 รายละเอียด:\n"
    for detail in risk_details:
        message += f"  {detail}\n"
    message += f"\n{color} ระดับความเสี่ยง: {risk_level}\n"
    message += f"(คะแนนรวม: {risk_score})\n\n"
    message += f"💡 คำแนะนำ:\n{action}"
    
    # Save to sheet
    save_symptom_data(user_id, pain, wound, fever, mobility, risk_level, risk_score)
    
    # Send notification to nurse if high risk
    if risk_score >= 3:
        notify_msg = (
            f"🚨 รายงานอาการเร่งด่วน!\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"👤 User ID: {user_id}\n"
            f"⚠️ ความเสี่ยง: {risk_level}\n"
            f"📊 คะแนน: {risk_score}\n\n"
            f"📋 อาการ:\n"
            f"  • ความปวด: {pain}/10\n"
            f"  • แผล: {wound}\n"
            f"  • ไข้: {fever}\n"
            f"  • เคลื่อนไหว: {mobility}\n\n"
            f"⚡ กรุณาตรวจสอบทันที!\n"
            f"📊 ดูข้อมูล: {WORKSHEET_LINK}"
        )
        send_line_push(notify_msg)
    
    return message

# ========== CORE FEATURE 2: ASSESS PERSONAL RISK (Enhanced) ==========

def normalize_diseases(disease_param):
    """Extract and normalize disease/condition names from various formats."""
    if not disease_param:
        return []
    
    def extract_items(param):
        items = []
        if isinstance(param, list):
            raw = param
        else:
            raw = [param]
        for it in raw:
            if it is None:
                continue
            if isinstance(it, dict):
                v = it.get('name') or it.get('value') or it.get('original') or it.get('displayName')
                if not v:
                    try:
                        v = json.dumps(it, ensure_ascii=False)
                    except: 
                        v = str(it)
            else:
                v = str(it)
            v = v.strip()
            if v:
                items.append(v)
        return items

    raw_items = extract_items(disease_param)
    mapping = {
        "hypertension": "ความดัน", "high blood pressure": "ความดัน", "blood pressure": "ความดัน",
        "diabetes": "เบาหวาน", "type 1 diabetes": "เบาหวาน", "type 2 diabetes": "เบาหวาน", "t2d": "เบาหวาน",
        "cancer": "มะเร็ง", "tumor": "มะเร็ง", 
        "kidney": "ไต", "renal": "ไต",
        "heart": "หัวใจ", "cardiac": "หัวใจ",
        "ความดัน": "ความดัน", "เบาหวาน": "เบาหวาน", "มะเร็ง": "มะเร็ง", "ไต": "ไต", "หัวใจ": "หัวใจ",
        "ht": "ความดัน", "dm": "เบาหวาน",
    }
    negatives = {"none", "no", "no disease", "ไม่มี", "ไม่มีโรค", "healthy", "null", "n/a", "ไม่"}
    
    normalized = []
    seen = set()
    for raw in raw_items:
        s = raw.lower().strip()
        if s in negatives or any(neg in s for neg in ["no disease", "ไม่มี"]):
            continue
        found = False
        for key in sorted(mapping.keys(), key=lambda x: -len(x)):
            if key in s:
                canon = mapping[key]
                if canon not in seen:
                    normalized.append(canon)
                    seen.add(canon)
                found = True
                break
        if not found:
            candidate = raw.strip()
            if candidate and candidate not in seen:
                normalized.append(candidate)
                seen.add(candidate)
    return normalized

def save_profile_data(user_id, age, weight, height, bmi, diseases, risk_level, risk_score):
    """Save risk profile to Google Sheets with enhanced data"""
    try:
        client = get_sheet_client()
        if not client:
            logger.error("No gspread client available.")
            return False
            
        spreadsheet = client.open('KhwanBot_Data')
        sheet = spreadsheet.worksheet('RiskProfile')
        
        timestamp = datetime.now(tz=LOCAL_TZ).strftime("%Y-%m-%d %H:%M:%S")
        diseases_str = ", ".join(diseases) if isinstance(diseases, list) else str(diseases)
        
        row = [
            timestamp,
            user_id,
            age or "",
            weight or "",
            height or "",
            f"{bmi:.1f}" if bmi > 0 else "",
            diseases_str,
            risk_level,
            risk_score
        ]
        sheet.append_row(row, value_input_option='USER_ENTERED')
        logger.info("Profile data saved for user %s", user_id)
        return True
    except Exception: 
        logger.exception("Save Profile Error")
        return False

def calculate_personal_risk(user_id, age, weight, height, disease):
    """
    Enhanced personal risk calculation with detailed analysis
    Returns: formatted message string
    """
    risk_score = 0
    risk_factors = []
    bmi = 0.0
    
    # Parse inputs
    try:
        age_val = int(age) if age is not None and str(age).strip() != "" else None
    except:
        age_val = None
    try:
        weight_val = float(weight) if weight is not None and str(weight).strip() != "" else None
    except: 
        weight_val = None
    try:
        height_cm = float(height) if height is not None and str(height).strip() != "" else None
    except:
        height_cm = None
    
    # Calculate BMI
    if height_cm and weight_val and height_cm > 0:
        height_m = height_cm / 100.0
        bmi = weight_val / (height_m ** 2)
    
    # Age Risk Factor
    if age_val is not None:
        if age_val >= 70:
            risk_score += 2
            risk_factors.append(f"🔴 อายุ {age_val} ปี (สูงอายุมาก)")
        elif age_val >= 60:
            risk_score += 1
            risk_factors.append(f"🟡 อายุ {age_val} ปี (สูงอายุ)")
        else:
            risk_factors.append(f"🟢 อายุ {age_val} ปี (ปกติ)")
    
    # BMI Risk Factor
    if bmi > 0:
        if bmi >= 35:
            risk_score += 2
            risk_factors.append(f"🔴 BMI {bmi:.1f} (อ้วนมาก)")
        elif bmi >= 30:
            risk_score += 1
            risk_factors.append(f"🟡 BMI {bmi:.1f} (อ้วน)")
        elif bmi < 18.5:
            risk_score += 1
            risk_factors.append(f"🟡 BMI {bmi:.1f} (ผอมเกินไป)")
        elif 18.5 <= bmi < 23:
            risk_factors.append(f"🟢 BMI {bmi:.1f} (ปกติดี)")
        elif 23 <= bmi < 25:
            risk_factors.append(f"🟢 BMI {bmi:.1f} (ค่อนข้างมาตรฐาน)")
        else:
            risk_factors.append(f"🟡 BMI {bmi:.1f} (น้ำหนักเกิน)")
    
    # Disease Risk Factors
    disease_normalized = normalize_diseases(disease)
    logger.debug("normalized diseases: %s", disease_normalized)
    
    risk_diseases = {"เบาหวาน", "หัวใจ", "ความดัน", "ไต", "มะเร็ง"}
    high_risk_diseases = []
    
    for d in disease_normalized:
        if d in risk_diseases:
            high_risk_diseases.append(d)
    
    if len(high_risk_diseases) >= 2:
        risk_score += 3
        risk_factors.append(f"🔴 มีโรคประจำตัวหลายโรค: {', '.join(high_risk_diseases)}")
    elif len(high_risk_diseases) == 1:
        risk_score += 2
        risk_factors.append(f"🟡 มีโรคประจำตัว: {high_risk_diseases[0]}")
    elif disease_normalized:
        risk_factors.append(f"🟡 โรคอื่นๆ: {', '.join(disease_normalized)}")
    else:
        risk_factors.append("🟢 ไม่มีโรคประจำตัว")
    
    # Risk Level Classification
    if risk_score >= 5:
        risk_level = "🔴 สูงมาก (Very High Risk)"
        emoji = "🚨"
        desc = "มีความเสี่ยงสูงมากต่อภาวะแทรกซ้อน"
        advice = [
            "• พยาบาลจะติดตามใกล้ชิดเป็นพิเศษ",
            "• รายงานอาการทุกวัน",
            "• ปฏิบัติตามคำแนะนำอย่างเคร่งครัด",
            "• หากมีอาการผิดปกติให้รีบติดต่อทันที"
        ]
    elif risk_score >= 4:
        risk_level = "🟠 สูง (High Risk)"
        emoji = "⚠️"
        desc = "มีความเสี่ยงสูงต่อภาวะแทรกซ้อน"
        advice = [
            "• พยาบาลจะติดตามใกล้ชิดเป็นพิเศษ",
            "• คุมโรคประจำตัวให้ดี",
            "• รายงานอาการสม่ำเสมอ",
            "• ระวังสัญญาณเตือน"
        ]
    elif risk_score >= 2:
        risk_level = "🟡 ปานกลาง (Moderate Risk)"
        emoji = "🟡"
        desc = "มีความเสี่ยงปานกลาง"
        advice = [
            "• คุมโรคประจำตัวและรายงานอาการสม่ำเสมอ",
            "• ดูแลสุขภาพให้ดี",
            "• ออกกำลังกายตามที่แนะนำ",
            "• รับประทานยาตรงเวลา"
        ]
    else:
        risk_level = "🟢 ต่ำ (Low Risk)"
        emoji = "✅"
        desc = "ความเสี่ยงเกณฑ์ปกติ"
        advice = [
            "• ปฏิบัติตัวตามคำแนะนำทั่วไป",
            "• ดูแลสุขภาพให้ดี",
            "• รายงานอาการถ้ามีอาการผิดปกติ"
        ]
    
    # Build message
    diseases_str = ", ".join(disease_normalized) if disease_normalized else "ไม่มีโรคประจำตัว"
    
    message = f"{emoji} ผลประเมินความเสี่ยงส่วนบุคคล\n"
    message += "=" * 35 + "\n\n"
    message += "👤 ข้อมูลพื้นฐาน:\n"
    message += f"  • อายุ: {age_val if age_val is not None else '-'} ปี\n"
    message += f"  • น้ำหนัก: {weight_val if weight_val is not None else '-'} กก.\n"
    message += f"  • ส่วนสูง: {height_cm if height_cm is not None else '-'} ซม.\n"
    message += f"  • BMI: {bmi:.1f}\n"
    message += f"  • โรคประจำตัว: {diseases_str}\n\n"
    
    message += "📊 ปัจจัยความเสี่ยง:\n"
    for factor in risk_factors:
        message += f"  {factor}\n"
    
    message += f"\n⚠️ ระดับความเสี่ยง: {risk_level}\n"
    message += f"(คะแนนรวม: {risk_score})\n\n"
    message += f"📝 {desc}\n\n"
    message += "💡 คำแนะนำ:\n"
    for adv in advice:
        message += f"  {adv}\n"
    
    # Save to sheet
    save_profile_data(user_id, age_val, weight_val, height_cm, bmi, disease_normalized, risk_level, risk_score)
    
    # Send notification to nurse if high risk
    if risk_score >= 4:
        notify_msg = (
            f"🆕 ผู้ป่วยกลุ่มเสี่ยงสูง!\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"👤 User ID: {user_id}\n"
            f"⚠️ ระดับ: {risk_level}\n"
            f"📊 คะแนน: {risk_score}\n\n"
            f"📋 ข้อมูล:\n"
            f"  • อายุ: {age_val} ปี\n"
            f"  • BMI: {bmi:.1f}\n"
            f"  • โรค: {diseases_str}\n\n"
            f"⚡ โปรดวางแผนติดตามใกล้ชิด\n"
            f"📊 ดูข้อมูล: {WORKSHEET_LINK}"
        )
        send_line_push(notify_msg)
    
    return message

# ========== CORE FEATURE 3: REQUEST APPOINTMENT (Enhanced) ==========

def save_appointment_to_sheet(user_id, name, phone, preferred_date, preferred_time, reason, status="New", assigned_to="", notes=""):
    """Save appointment request to Google Sheets"""
    try:
        client = get_sheet_client()
        if not client:
            logger.error("No gspread client available.")
            return False
        
        # แก้ไข: ใช้แท็บ Appointments จากไฟล์ KhwanBot_Data
        spreadsheet = client.open("KhwanBot_Data")
        sheet = spreadsheet.worksheet("Appointments")
        
        timestamp = datetime.now(tz=LOCAL_TZ).strftime("%Y-%m-%d %H:%M:%S")
        row = [
            timestamp,
            user_id,
            name or "",
            phone or "",
            preferred_date or "",
            preferred_time or "",
            reason or "",
            status,
            assigned_to,
            notes
        ]
        sheet.append_row(row, value_input_option="USER_ENTERED")
        logger.info("Saved appointment row for user %s", user_id)
        return True
    except Exception: 
        logger.exception("Error saving appointment to sheet")
        return False

def build_appointment_notification(user_id, name, phone, preferred_date, preferred_time, reason):
    """Build enhanced notification message for nurses"""
    sheet_link = WORKSHEET_LINK
    
    # Format date nicely
    try:
        date_obj = datetime.strptime(preferred_date, "%Y-%m-%d")
        thai_date = date_obj.strftime("%d/%m/%Y")
        day_name = ["จันทร์", "อังคาร", "พุธ", "พฤหัสบดี", "ศุกร์", "เสาร์", "อาทิตย์"][date_obj.weekday()]
        date_display = f"{day_name} {thai_date}"
    except:
        date_display = preferred_date
    
    message = (
        f"📅 การนัดหมายใหม่!\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"👤 User ID: {user_id}\n"
    )
    
    if name:
        message += f"📝 ชื่อ: {name}\n"
    if phone:
        message += f"📞 เบอร์: {phone}\n"
    
    message += (
        f"📆 วัน: {date_display}\n"
        f"🕐 เวลา: {preferred_time} น.\n"
        f"💬 เรื่อง: {reason}\n\n"
        f"⚡ โปรดตรวจสอบและยืนยันนัด\n"
        f"📊 ดูรายละเอียด: {sheet_link}"
    )
    
    return message

# ---------- Dialogflow webhook ----------
@app.route('/', methods=['GET', 'HEAD'])
def health_check():
    """Health check endpoint for monitoring services"""
    return jsonify({
        "status": "ok",
        "service": "KwanNurse-Bot v3.0",
        "version": "3.0 - Perfect Core",
        "features": ["ReportSymptoms", "AssessRisk", "RequestAppointment"],
        "timestamp": datetime.now(tz=LOCAL_TZ).isoformat()
    }), 200

@app.route('/webhook', methods=['POST'])
def webhook():
    req = request.get_json(silent=True, force=True)
    if not req:
        return jsonify({"fulfillmentText": "Request body empty"}), 400
    
    try:
        intent = req.get('queryResult', {}).get('intent', {}).get('displayName')
        params = req.get('queryResult', {}).get('parameters', {}) or {}
        user_id = req.get('session', 'unknown').split('/')[-1]
    except Exception:
        logger.exception("Parse Error")
        return jsonify({"fulfillmentText": "เกิดข้อผิดพลาดในการประมวลผล กรุณาลองใหม่อีกครั้ง"}), 200

    logger.info("Intent incoming: %s user=%s params=%s", intent, user_id, json.dumps(params, ensure_ascii=False))

    # ========== CORE FEATURE 1: Report Symptoms ==========
    if intent == 'ReportSymptoms':
        pain = params.get('pain_score')
        wound = params.get('wound_status')
        fever = params.get('fever_check')
        mobility = params.get('mobility_status')
        
        # Validate required parameters
        missing = []
        if pain is None or str(pain).strip() == "":
            missing.append("ระดับความปวด (0-10)")
        if not wound:
            missing.append("สภาพแผล")
        if not fever:
            missing.append("อาการไข้")
        if not mobility:
            missing.append("การเคลื่อนไหว")
        
        if missing:
            ask = "กรุณาระบุ " + " และ ".join(missing) + " ด้วยค่ะ"
            return jsonify({"fulfillmentText": ask}), 200
        
        result = calculate_symptom_risk(user_id, pain, wound, fever, mobility)
        return jsonify({"fulfillmentText": result}), 200

    # ========== CORE FEATURE 2: Assess Personal Risk ==========
    elif intent == 'AssessPersonalRisk' or intent == 'AssessRisk':
        age = params.get('age')
        weight = params.get('weight')
        height = params.get('height')
        disease = params.get('disease') or params.get('diseases')
        
        # Validate required parameters
        missing = []
        if age is None or str(age).strip() == "":
            missing.append("อายุ")
        if weight is None or str(weight).strip() == "":
            missing.append("น้ำหนัก (กิโลกรัม)")
        if height is None or str(height).strip() == "":
            missing.append("ส่วนสูง (เซนติเมตร)")
        if not disease:
            missing.append("โรคประจำตัว (หรือพิมพ์ 'ไม่มี')")
        
        if missing:
            ask = "กรุณาระบุ " + " และ ".join(missing) + " ด้วยค่ะ"
            return jsonify({"fulfillmentText": ask}), 200
        
        result = calculate_personal_risk(user_id, age, weight, height, disease)
        return jsonify({"fulfillmentText": result}), 200

    # ========== CORE FEATURE 3: Request Appointment ==========
    elif intent == 'RequestAppointment':
        preferred_date_raw = params.get('date') or params.get('preferred_date') or params.get('date-original')
        preferred_time_raw = params.get('time') or params.get('preferred_time')
        timeofday_raw = params.get('timeofday') or params.get('time_of_day')
        reason = params.get('reason') or params.get('symptom') or params.get('description')
        name = params.get('name') or None
        phone_raw = params.get('phone-number') or params.get('phone') or None

        preferred_date = parse_date_iso(preferred_date_raw)
        preferred_time = resolve_time_from_params(preferred_time_raw, timeofday_raw)

        # Validate required parameters
        missing = []
        if not preferred_date:
            missing.append("วันที่นัด (เช่น 25 มกราคม หรือ 2026-01-25)")
        else:
            today_local = datetime.now(tz=LOCAL_TZ).date()
            if preferred_date < today_local:
                return jsonify({
                    "fulfillmentText": "⚠️ วันที่ที่เลือกเป็นอดีตแล้ว กรุณาเลือกวันที่ในอนาคตค่ะ"
                }), 200

        if not preferred_time: 
            missing.append("เวลานัด (เช่น 09:00 หรือ 'เช้า'/'บ่าย')")

        if not reason:
            missing.append("เหตุผลการนัด (เช่น เปลี่ยนผ้าพันแผล, ตรวจแผล)")

        phone_norm = normalize_phone_number(phone_raw) if phone_raw else None
        if phone_norm and not is_valid_thai_mobile(phone_norm):
            return jsonify({
                "fulfillmentText": "⚠️ เบอร์โทรศัพท์ไม่ถูกต้อง กรุณาพิมพ์เป็นตัวเลข 10 หลัก (เช่น 0812345678)"
            }), 200

        if missing:
            ask = "กรุณาระบุ " + " และ ".join(missing) + " ด้วยค่ะ"
            return jsonify({"fulfillmentText": ask}), 200

        # Save appointment
        pd_str = preferred_date.isoformat()
        pt_str = preferred_time

        ok = save_appointment_to_sheet(user_id, name, phone_norm, pd_str, pt_str, reason, status="New")
        if ok:
            notif = build_appointment_notification(user_id, name, phone_norm, pd_str, pt_str, reason)
            send_line_push(notif)
            
            # Format confirmation message
            try:
                date_obj = datetime.strptime(pd_str, "%Y-%m-%d")
                thai_date = date_obj.strftime("%d/%m/%Y")
                day_name = ["จันทร์", "อังคาร", "พุธ", "พฤหัสบดี", "ศุกร์", "เสาร์", "อาทิตย์"][date_obj.weekday()]
                date_display = f"{day_name} {thai_date}"
            except:
                date_display = pd_str
            
            confirm_msg = (
                f"✅ รับเรื่องการนัดหมายเรียบร้อยแล้วค่ะ\n\n"
                f"📅 วันที่: {date_display}\n"
                f"🕐 เวลา: {pt_str} น.\n"
                f"💬 เรื่อง: {reason}\n\n"
                f"ทีมพยาบาลจะติดต่อกลับเพื่อยืนยันวันเวลาภายใน 24 ชั่วโมง\n"
                f"หากมีข้อสงสัยกรุณากดปุ่ม 'ปรึกษาพยาบาล' ค่ะ"
            )
            return jsonify({"fulfillmentText": confirm_msg}), 200
        else:
            return jsonify({
                "fulfillmentText": "❌ เกิดปัญหาในการบันทึกนัดหมาย กรุณาลองใหม่อีกครั้งหรือติดต่อพยาบาลโดยตรงค่ะ"
            }), 200

    # ========== Debug Intent ==========
    elif intent == 'GetGroupID':
        return jsonify({
            "fulfillmentText": f"🔧 Debug Info:\nNURSE_GROUP_ID: {os.environ.get('NURSE_GROUP_ID', 'Not Set')}"
        })

    # ========== Fallback ==========
    logger.warning("Unhandled intent: %s with params: %s", intent, json.dumps(params, ensure_ascii=False))
    return jsonify({
        "fulfillmentText": f"ขอโทษค่ะ บอทยังไม่รองรับคำสั่ง '{intent}' ในขณะนี้\n\nคุณสามารถใช้ฟีเจอร์หลักได้:\n• รายงานอาการ\n• ประเมินความเสี่ยง\n• นัดหมายพยาบาล"
    }), 200

# ---------- Run ----------
if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(port=port, debug=DEBUG)

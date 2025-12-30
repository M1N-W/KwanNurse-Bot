from flask import Flask, request, jsonify
import gspread
from datetime import datetime
import os
import json
import requests

app = Flask(__name__)

# ==========================================
# 🔧 CONFIGURATION & UTILS (ส่วนตั้งค่าระบบ)
# ==========================================

def get_sheet_client():
    """เชื่อมต่อ Google Sheet แบบปลอดภัย"""
    try:
        # ตรวจสอบว่ามีไฟล์ credentials.json หรือไม่
        if not os.path.exists('credentials.json'):
            print("⚠️ Warning: ไม่พบไฟล์ credentials.json (ระบบจะพยายามใช้ Environment Variable)")
        return gspread.service_account(filename='credentials.json')
    except Exception as e:
        print(f"❌ Connect Sheet Error: {e}")
        return None

def send_line_push(message):
    """ฟังก์ชันส่งข้อความหาพยาบาล"""
    try:
        access_token = os.environ.get('LINE_CHANNEL_ACCESS_TOKEN')
        target_id = os.environ.get('NURSE_GROUP_ID')
        
        if not access_token or not target_id:
            print("⚠️ Config Error: ขาด Token หรือ Group ID")
            return

        url = 'https://api.line.me/v2/bot/message/push'
        headers = {
            'Content-Type': 'application/json',
            'Authorization': f'Bearer {access_token}'
        }
        payload = {
            "to": target_id,
            "messages": [{"type": "text", "text": message}]
        }
        requests.post(url, headers=headers, data=json.dumps(payload))
        print("✅ Push Notification Sent!")
    except Exception as e:
        print(f"❌ Push Error: {e}")

# ==========================================
# 🧠 LOGIC PART 1: DAILY SYMPTOM (อาการรายวัน)
# ==========================================

def save_symptom_data(pain, wound, fever, mobility, risk_result):
    try:
        client = get_sheet_client()
        if client:
            sheet = client.open('KhwanBot_Data').sheet1 # แผ่นที่ 1
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            sheet.append_row([timestamp, pain, wound, fever, mobility, risk_result], value_input_option='USER_ENTERED')
            print("✅ Symptom Saved")
    except Exception as e:
        print(f"❌ Save Symptom Error: {e}")

def calculate_symptom_risk(pain, wound, fever, mobility):
    risk_score = 0
    
    # Pain Logic
    try: p_val = int(pain)
    except: p_val = 0
    if p_val >= 8: risk_score += 3
    elif p_val >= 6: risk_score += 1

    # Wound Logic
    try:
        wound_text = str(wound)
    except:
        wound_text = ""
    if any(x in wound_text for x in ["หนอง", "มีกลิ่น", "แฉะ"]): risk_score += 3
    elif any(x in wound_text for x in ["บวมแดง", "อักเสบ"]): risk_score += 2

    # Fever & Mobility Logic
    try:
        fever_text = str(fever)
    except:
        fever_text = ""
    try:
        mobility_text = str(mobility)
    except:
        mobility_text = ""
    if any(x in fever_text for x in ["มี", "ตัวร้อน"]): risk_score += 2
    if any(x in mobility_text for x in ["ไม่ได้", "ติดเตียง"]): risk_score += 1

    # Evaluation
    if risk_score >= 3:
        risk_level = "สูง (อันตราย)"
        msg = f"⚠️ เสี่ยง{risk_level} (คะแนน {risk_score})\nกรุณากดปุ่ม 'ติดต่อพยาบาล' ทันที"
        # Alert Nurse
        notify_msg = f"🚨 DAILY REPORT (อาการแย่)\nRisk: {risk_score}\nPain: {pain}\nWound: {wound}\nกรุณาตรวจสอบทันที!"
        send_line_push(notify_msg)
    elif risk_score >= 2:
        risk_level = "ปานกลาง"
        msg = f"⚠️ เสี่ยง{risk_level} (คะแนน {risk_score})\nเฝ้าระวังอาการใกล้ชิด 24 ชม.นะคะ"
    elif risk_score == 1:
        risk_level = "ต่ำ (เฝ้าระวัง)"
        msg = f"🟡 เสี่ยง{risk_level}\nโดยรวมปกติดี แต่ต้องสังเกตอาการนะคะ"
    else:
        risk_level = "ต่ำ (ปกติ)"
        msg = f"✅ เสี่ยง{risk_level}\nแผลหายดี ยอดเยี่ยมมากค่ะ"

    save_symptom_data(pain, wound, fever, mobility, risk_level)
    return msg

# ==========================================
# 🧠 LOGIC PART 2: PATIENT PROFILE (ประเมินความเสี่ยงบุคคล)
# ==========================================

def save_profile_data(user_id, age, weight, height, bmi, diseases, risk_level):
    try:
        client = get_sheet_client()
        if client:
            # 🔥 ข้อควรระวัง: ต้องสร้าง Tab ชื่อ 'RiskProfile' ใน Sheet รอไว้ด้วยนะครับ
            sheet = client.open('KhwanBot_Data').worksheet('RiskProfile')
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            # แปลง diseases list เป็น string สวยๆ
            diseases_str = ", ".join(diseases) if isinstance(diseases, list) else str(diseases)
            
            sheet.append_row([timestamp, user_id, age, weight, height, bmi, diseases_str, risk_level], value_input_option='USER_ENTERED')
            print("✅ Profile Saved")
    except Exception as e:
        print(f"❌ Save Profile Error: {e}")

# --------- New helper: normalize diseases ----------
def normalize_diseases(disease_param):
    """
    รับค่า disease_param ได้หลายรูปแบบ (None, string, list, list of dicts, dict)
    คืนค่าเป็น list ของโรคในรูปแบบ canonical (ภาษาไทย) เช่น ["ความดัน", "เบาหวาน"]
    """
    if not disease_param:
        return []

    # helper: แปลง input เป็นรายการของ raw strings
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
                # Dialogflow บางเวอร์ชันส่ง object เช่น {'name': 'hypertension'} หรือ {'value':'hypertension'}
                v = it.get('name') or it.get('value') or it.get('original') or it.get('displayName') if isinstance(it, dict) else None
                if not v:
                    # fallback stringify
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
    # mapping ของคำต่าง ๆ -> canonical ไทย
    mapping = {
        # อังกฤษ -> ไทย
        "hypertension": "ความดัน",
        "high blood pressure": "ความดัน",
        "high blood-pressure": "ความดัน",
        "blood pressure": "ความดัน",
        "diabetes": "เบาหวาน",
        "type 1 diabetes": "เบาหวาน",
        "type 2 diabetes": "เบาหวาน",
        "t2d": "เบาหวาน",
        "cancer": "มะเร็ง",
        "tumor": "มะเร็ง",
        "malignant": "มะเร็ง",
        "kidney": "ไต",
        "renal": "ไต",
        "heart": "หัวใจ",
        "cardiac": "หัวใจ",
        # ไทย
        "ความดัน": "ความดัน",
        "เบาหวาน": "เบาหวาน",
        "มะเร็ง": "มะเร็ง",
        "ไต": "ไต",
        "หัวใจ": "หัวใจ",
        # บางคำย่อ/สำนวน
        "ht": "ความดัน",
        "dm": "เบาหวาน",
    }
    # คำที่แปลว่า "ไม่มีโรค"
    negatives = {"none", "no", "no disease", "ไม่มี", "ไม่มีโรค", "healthy", "null", "n/a", "ไม่"}

    normalized = []
    seen = set()

    for raw in raw_items:
        s = raw.lower().strip()
        # ข้ามคำที่แปลว่าไม่มีโรค
        if s in negatives or any(neg in s for neg in ["no disease", "ไม่มี"]):
            continue

        found = False
        # ตรวจหา exact match หรือ partial match กับ key ใน mapping
        # เรียงตรวจ key ที่ยาวก่อน (เพื่อป้องกัน match กับคำสั้นก่อน)
        for key in sorted(mapping.keys(), key=lambda x: -len(x)):
            if key in s:
                canon = mapping[key]
                if canon not in seen:
                    normalized.append(canon)
                    seen.add(canon)
                found = True
                break
        if not found:
            # ถ้าไม่เจอ mapping ให้เอาค่าเดิม (แปลงเป็น title แบบเรียบร้อย)
            candidate = raw.strip()
            if candidate and candidate not in seen:
                normalized.append(candidate)
                seen.add(candidate)

    return normalized

# -----------------------------------------------

def calculate_personal_risk(user_id, age, weight, height, disease):
    risk_score = 0
    risk_level = "ต่ำ"
    bmi = 0
    message = ""

    # Debug log (ช่วยดูรูปแบบ params ที่รับมา)
    try:
        print("DEBUG calculate_personal_risk params:", json.dumps({
            "user_id": user_id,
            "age": age,
            "weight": weight,
            "height": height,
            "disease_raw": disease
        }, ensure_ascii=False))
    except Exception:
        print("DEBUG calculate_personal_risk params (non-jsonifiable)")

    # 1. แปลงค่าตัวเลข
    try:
        age = int(age)
        weight = float(weight)
        height_cm = float(height)
        height_m = height_cm / 100
        if height_m > 0:
            bmi = weight / (height_m ** 2)
    except:
        age = 0
        bmi = 0.0

    # 2. Scoring System
    if age >= 60:
        risk_score += 1
    
    if bmi >= 30:
        risk_score += 1
    elif bmi > 0 and bmi < 18.5:
        risk_score += 1 

    # Normalize disease input and score
    disease_normalized = normalize_diseases(disease)
    print("DEBUG normalized diseases:", disease_normalized)

    risk_diseases = {"เบาหวาน", "หัวใจ", "ความดัน", "ไต", "มะเร็ง"}
    if any(d in risk_diseases for d in disease_normalized):
        risk_score += 2

    # 3. Triage
    if risk_score >= 4:
        risk_level = "สูง (High Risk)"
        desc = "มีความเสี่ยงสูงต่อภาวะแทรกซ้อน"
        advice = "พยาบาลจะติดตามใกล้ชิดเป็นพิเศษค่ะ"
    elif risk_score >= 2:
        risk_level = "ปานกลาง (Moderate Risk)"
        desc = "มีความเสี่ยงปานกลาง"
        advice = "คุมโรคประจำตัวและรายงานอาการทุกวันนะคะ"
    else:
        risk_level = "ต่ำ (Low Risk)"
        desc = "ความเสี่ยงเกณฑ์ปกติ"
        advice = "ปฏิบัติตัวตามคำแนะนำทั่วไปได้เลยค่ะ"

    # เตรียมข้อความแสดงโรคให้สวย
    diseases_str = ", ".join(disease_normalized) if disease_normalized else "ไม่มีโรคประจำตัว"

    # สร้างข้อความตอบกลับ
    message = (
        f"📊 ผลประเมินความเสี่ยงของคุณ\n"
        f"---------------------------\n"
        f"👤 ข้อมูล: อายุ {age}, BMI {bmi:.1f}\n"
        f"🏥 โรค: {diseases_str}\n"
        f"⚠️ ระดับ: {risk_level}\n"
        f"({desc})\n"
        f"💡 {advice}"
    )

    # 4. 🔥 บันทึกข้อมูลลง Sheet (สำคัญมาก!)
    # ส่ง diseases เป็น list เพื่อให้ save_profile_data แปลงเป็น string ได้สวย
    try:
        save_profile_data(user_id, age, weight, height, bmi, disease_normalized, risk_level)
    except Exception as e:
        print(f"❌ Error saving profile: {e}")

    # 5. แจ้งเตือนพยาบาลกรณีเสี่ยงสูง
    if risk_score >= 4:
        notify_msg = f"🆕 ผู้ป่วยใหม่ (เสี่ยงสูง)\nUser: {user_id}\nอายุ {age}, โรค {diseases_str}\nโปรดวางแผนเยี่ยมบ้าน"
        send_line_push(notify_msg)

    return message

# ==========================================
# 🌐 WEBHOOK HANDLER
# ==========================================

@app.route('/webhook', methods=['POST'])
def webhook():
    req = request.get_json(silent=True, force=True)
    try:
        intent = req.get('queryResult', {}).get('intent', {}).get('displayName')
        params = req.get('queryResult', {}).get('parameters', {})
        
        # ดึง User ID
        original_req = req.get('originalDetectIntentRequest', {})
        user_id = original_req.get('payload', {}).get('data', {}).get('source', {}).get('userId', 'Unknown')
    except Exception as e:
        print(f"❌ Parse Error: {e}")
        return jsonify({"fulfillmentText": "Error parsing request"})

    print(f"🔔 Intent Incoming: {intent}")
    # temporary debug print of params
    try:
        print("DEBUG params:", json.dumps(params, ensure_ascii=False))
    except Exception:
        print("DEBUG params (non-jsonifiable)")

    # --- ROUTING ---
    
    # ✅ เช็ค Intent 1: รายงานอาการ
    if intent == 'ReportSymptoms':
        res = calculate_symptom_risk(
            params.get('pain_score'), 
            params.get('wound_status'), 
            params.get('fever_check'), 
            params.get('mobility_status')
        )
        return jsonify({"fulfillmentText": res})

    # ✅ เช็ค Intent 2: ประเมินความเสี่ยงบุคคล (แก้ชื่อ Intent ให้ตรงกับ Dialogflow นะครับ)
    elif intent == 'AssessPersonalRisk': 
        res = calculate_personal_risk(
            user_id, # ส่ง user_id ไปด้วยเพื่อบันทึก
            params.get('age'),
            params.get('weight'),
            params.get('height'),
            params.get('disease')
        )
        return jsonify({"fulfillmentText": res})

    # ✅ เช็ค Intent 3: หา Group ID (ของแถม)
    elif intent == 'GetGroupID':
         return jsonify({"fulfillmentText": f"ID: {os.environ.get('NURSE_GROUP_ID', 'Not Set')}"})

    return jsonify({"fulfillmentText": "ขอโทษค่ะ บอทไม่เข้าใจคำสั่งนี้"})

if __name__ == '__main__':
    app.run(port=5000, debug=True)


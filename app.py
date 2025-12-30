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
    if any(x in wound for x in ["หนอง", "มีกลิ่น", "แฉะ"]): risk_score += 3
    elif any(x in wound for x in ["บวมแดง", "อักเสบ"]): risk_score += 2

    # Fever & Mobility Logic
    if any(x in fever for x in ["มี", "ตัวร้อน"]): risk_score += 2
    if any(x in mobility for x in ["ไม่ได้", "ติดเตียง"]): risk_score += 1

    # Evaluation
    if risk_score >= 3:
        risk_level = "สูง (อันตราย)"
        msg = f"⚠️ เสี่ยง{risk_level} (คะแนน {risk_score})\nกรุณากดปุ่ม 'ติดต่อพยาบาล' ทันที"
        # Alert Nurse
        notify_msg = f"🚨 DAILY REPORT (อาการแย่)\nRisk: {risk_score}\nPain: {pain}\nWound: {wound}\nCheck ASAP!"
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

def calculate_personal_risk(user_id, age, weight, height, disease):
    risk_score = 0
    risk_level = "ต่ำ"
    bmi = 0
    message = ""

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
        bmi = 0

    # 2. Scoring System
    if age >= 60: risk_score += 1
    
    if bmi >= 30: risk_score += 1
    elif bmi > 0 and bmi < 18.5: risk_score += 1 

    disease_list = ["เบาหวาน", "หัวใจ", "ความดัน", "ไต", "มะเร็ง"]
    # แปลง input เป็น string เพื่อเช็ค (เผื่อ Dialogflow ส่งมาเป็น list)
    disease_str = str(disease)
    if any(d in disease_str for d in disease_list):
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

    # สร้างข้อความตอบกลับ
    message = (
        f"📊 ผลประเมินความเสี่ยงของคุณ\n"
        f"---------------------------\n"
        f"👤 ข้อมูล: อายุ {age}, BMI {bmi:.1f}\n"
        f"🏥 โรค: {disease}\n"
        f"⚠️ ระดับ: {risk_level}\n"
        f"({desc})\n"
        f"💡 {advice}"
    )

    # 4. 🔥 บันทึกข้อมูลลง Sheet (สำคัญมาก!)
    save_profile_data(user_id, age, weight, height, bmi, disease, risk_level)

    # 5. แจ้งเตือนพยาบาลกรณีเสี่ยงสูง
    if risk_score >= 4:
        notify_msg = f"🆕 ผู้ป่วยใหม่ (เสี่ยงสูง)\nUser: {user_id}\nอายุ {age}, โรค {disease}\nโปรดวางแผนเยี่ยมบ้าน"
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

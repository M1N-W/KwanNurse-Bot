# -*- coding: utf-8 -*-
"""
Webhook Routes Module
Handles Dialogflow webhook endpoints
"""
import json
import os
from datetime import datetime
from flask import request, jsonify
from config import get_logger, LOCAL_TZ
from utils import (
    parse_date_iso,
    resolve_time_from_params,
    normalize_phone_number,
    is_valid_thai_mobile
)
from services import (
    calculate_symptom_risk,
    calculate_personal_risk,
    create_appointment,
    get_knowledge_menu,
    get_wound_care_guide,
    get_physical_therapy_guide,
    get_dvt_prevention_guide,
    get_medication_guide,
    get_warning_signs_guide
)
from services.teleconsult import (
    is_office_hours,
    get_category_menu,
    parse_category_choice,
    start_teleconsult,
    cancel_consultation,
    get_queue_info_message
)

logger = get_logger(__name__)


def register_routes(app):
    """Register all webhook routes with Flask app"""
    
    @app.route('/', methods=['GET', 'HEAD'])
    def health_check():
        """Health check endpoint for monitoring services"""
        return jsonify({
            "status": "ok",
            "service": "KwanNurse-Bot v4.0",
            "version": "4.0 - Complete (6/6 Features)",
            "features": [
                "ReportSymptoms", 
                "AssessRisk", 
                "RequestAppointment", 
                "GetKnowledge",
                "FollowUpReminders",
                "Teleconsult"
            ],
            "timestamp": datetime.now(tz=LOCAL_TZ).isoformat()
        }), 200
    
    @app.route('/webhook', methods=['POST'])
    def webhook():
        """Main Dialogflow webhook endpoint"""
        req = request.get_json(silent=True, force=True)
        if not req:
            return jsonify({"fulfillmentText": "Request body empty"}), 400
        
        try:
            intent = req.get('queryResult', {}).get('intent', {}).get('displayName')
            params = req.get('queryResult', {}).get('parameters', {}) or {}
            user_id = req.get('session', 'unknown').split('/')[-1]
            query_text = req.get('queryResult', {}).get('queryText', '')
        except Exception:
            logger.exception("Error parsing request")
            return jsonify({
                "fulfillmentText": "เกิดข้อผิดพลาดในการประมวลผล กรุณาลองใหม่อีกครั้ง"
            }), 200
        
        logger.info("Intent: %s | User: %s | Params: %s", 
                   intent, user_id, json.dumps(params, ensure_ascii=False))
        
        # Route to appropriate handler
        if intent == 'ReportSymptoms':
            return handle_report_symptoms(user_id, params)
        
        elif intent == 'AssessPersonalRisk' or intent == 'AssessRisk':
            return handle_assess_risk(user_id, params)
        
        elif intent == 'RequestAppointment':
            return handle_request_appointment(user_id, params)
        
        elif intent == 'GetKnowledge':
            return handle_get_knowledge(params)
        
        elif intent == 'ContactNurse':
            return handle_contact_nurse(user_id, params, query_text)
        
        elif intent == 'CancelConsultation':
            return handle_cancel_consultation(user_id)
        
        elif intent == 'GetGroupID':
            return handle_get_group_id()
        
        else:
            return handle_unknown_intent(intent)


def handle_report_symptoms(user_id, params):
    """Handle ReportSymptoms intent"""
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
    
    # Calculate risk
    result = calculate_symptom_risk(user_id, pain, wound, fever, mobility)
    return jsonify({"fulfillmentText": result}), 200


def handle_assess_risk(user_id, params):
    """Handle AssessRisk intent"""
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
    
    # Calculate risk
    result = calculate_personal_risk(user_id, age, weight, height, disease)
    return jsonify({"fulfillmentText": result}), 200


def handle_request_appointment(user_id, params):
    """Handle RequestAppointment intent"""
    preferred_date_raw = (params.get('date') or 
                         params.get('preferred_date') or 
                         params.get('date-original'))
    preferred_time_raw = params.get('time') or params.get('preferred_time')
    timeofday_raw = params.get('timeofday') or params.get('time_of_day')
    reason = params.get('reason') or params.get('symptom') or params.get('description')
    name = params.get('name') or None
    phone_raw = params.get('phone-number') or params.get('phone') or None
    
    # Parse date and time
    preferred_date = parse_date_iso(preferred_date_raw)
    preferred_time = resolve_time_from_params(preferred_time_raw, timeofday_raw)
    
    # Validate required parameters
    missing = []
    
    if not preferred_date:
        missing.append("วันที่นัด (เช่น 25 มกราคม หรือ 2026-01-25)")
    else:
        # Check if date is in the past
        today_local = datetime.now(tz=LOCAL_TZ).date()
        if preferred_date < today_local:
            return jsonify({
                "fulfillmentText": "⚠️ วันที่ที่เลือกเป็นอดีตแล้ว กรุณาเลือกวันที่ในอนาคตค่ะ"
            }), 200
    
    if not preferred_time:
        missing.append("เวลานัด (เช่น 09:00 หรือ 'เช้า'/'บ่าย')")
    
    if not reason:
        missing.append("เหตุผลการนัด (เช่น เปลี่ยนผ้าพันแผล, ตรวจแผล)")
    
    # Validate phone if provided
    phone_norm = normalize_phone_number(phone_raw) if phone_raw else None
    if phone_norm and not is_valid_thai_mobile(phone_norm):
        return jsonify({
            "fulfillmentText": "⚠️ เบอร์โทรศัพท์ไม่ถูกต้อง กรุณาพิมพ์เป็นตัวเลข 10 หลัก (เช่น 0812345678)"
        }), 200
    
    if missing:
        ask = "กรุณาระบุ " + " และ ".join(missing) + " ด้วยค่ะ"
        return jsonify({"fulfillmentText": ask}), 200
    
    # Create appointment
    pd_str = preferred_date.isoformat()
    pt_str = preferred_time
    
    success, message = create_appointment(
        user_id, name, phone_norm, pd_str, pt_str, reason
    )
    
    return jsonify({"fulfillmentText": message}), 200


def handle_get_knowledge(params):
    """Handle GetKnowledge intent"""
    topic = params.get('topic') or params.get('knowledge_topic')
    
    # Map topics to guide functions
    knowledge_map = {
        'wound_care': ('การดูแลแผล', get_wound_care_guide),
        'ดูแลแผล': ('การดูแลแผล', get_wound_care_guide),
        'แผล': ('การดูแลแผล', get_wound_care_guide),
        
        'physical_therapy': ('กายภาพบำบัด', get_physical_therapy_guide),
        'กายภาพบำบัด': ('กายภาพบำบัด', get_physical_therapy_guide),
        'กายภาพ': ('กายภาพบำบัด', get_physical_therapy_guide),
        'ออกกำลังกาย': ('กายภาพบำบัด', get_physical_therapy_guide),
        
        'dvt': ('ป้องกันลิ่มเลือด', get_dvt_prevention_guide),
        'dvt_prevention': ('ป้องกันลิ่มเลือด', get_dvt_prevention_guide),
        'ลิ่มเลือด': ('ป้องกันลิ่มเลือด', get_dvt_prevention_guide),
        'ป้องกันลิ่มเลือด': ('ป้องกันลิ่มเลือด', get_dvt_prevention_guide),
        
        'medication': ('การรับประทานยา', get_medication_guide),
        'ยา': ('การรับประทานยา', get_medication_guide),
        'ทานยา': ('การรับประทานยา', get_medication_guide),
        'รับประทานยา': ('การรับประทานยา', get_medication_guide),
        
        'warning_signs': ('สัญญาณอันตราย', get_warning_signs_guide),
        'สัญญาณอันตราย': ('สัญญาณอันตราย', get_warning_signs_guide),
        'อาการอันตราย': ('สัญญาณอันตราย', get_warning_signs_guide),
        'อันตราย': ('สัญญาณอันตราย', get_warning_signs_guide),
    }
    
    # If no topic or "menu", return menu
    if not topic or str(topic).lower() in ['menu', 'เมนู', 'ความรู้', 'knowledge']:
        result = get_knowledge_menu()
        return jsonify({"fulfillmentText": result}), 200
    
    # Normalize topic
    topic_key = str(topic).lower().strip()
    
    # Find matching guide
    if topic_key in knowledge_map:
        topic_name, guide_func = knowledge_map[topic_key]
        logger.info("Knowledge request: %s", topic_name)
        result = guide_func()
        return jsonify({"fulfillmentText": result}), 200
    
    # Topic not found
    return jsonify({
        "fulfillmentText": (
            f"ขอโทษค่ะ ไม่พบหัวข้อ '{topic}'\n\n"
            f"กรุณาพิมพ์ 'ความรู้' เพื่อดูหัวข้อที่มีค่ะ"
        )
    }), 200


def handle_get_group_id():
    """Handle GetGroupID debug intent"""
    return jsonify({
        "fulfillmentText": f"🔧 Debug Info:\nNURSE_GROUP_ID: {os.environ.get('NURSE_GROUP_ID', 'Not Set')}"
    }), 200


def handle_contact_nurse(user_id, params, query_text):
    """
    Handle ContactNurse intent
    
    Manages the teleconsult flow including:
    - Category selection
    - Queue management
    - Office hours checking
    """
    try:
        logger.info(f"ContactNurse request from {user_id}")
        
        # Check if user provided category or description
        category_param = params.get('issue_category') or params.get('category')
        description_param = params.get('description') or params.get('issue_description')
        
        # If category is provided (or can be parsed from text)
        if category_param:
            issue_type = parse_category_choice(str(category_param))
        else:
            # Try to parse from query text
            issue_type = parse_category_choice(query_text)
        
        if issue_type:
            # Start teleconsult with the category
            description = str(description_param) if description_param else ""
            result = start_teleconsult(user_id, issue_type, description)
            
            return jsonify({"fulfillmentText": result['message']}), 200
        
        else:
            # No category yet, show menu
            menu = get_category_menu()
            
            # Add office hours info if outside hours
            if not is_office_hours():
                from datetime import datetime
                from config import OFFICE_HOURS
                now = datetime.now(tz=LOCAL_TZ)
                current_time = now.strftime("%H:%M")
                
                menu = (
                    f"⏰ ขณะนี้นอกเวลาทำการ ({current_time} น.)\n"
                    f"เวลาทำการ: {OFFICE_HOURS['start']}-{OFFICE_HOURS['end']} น.\n\n"
                    f"{menu}\n\n"
                    f"💡 หากเป็นเรื่องฉุกเฉิน เลือกหมายเลข 1"
                )
            
            return jsonify({"fulfillmentText": menu}), 200
        
    except Exception as e:
        logger.exception(f"Error in ContactNurse: {e}")
        return jsonify({
            "fulfillmentText": "เกิดข้อผิดพลาด กรุณาลองใหม่ภายหลัง"
        }), 200


def handle_cancel_consultation(user_id):
    """Handle cancellation of consultation"""
    try:
        result = cancel_consultation(user_id)
        return jsonify({"fulfillmentText": result['message']}), 200
        
    except Exception as e:
        logger.exception(f"Error cancelling consultation: {e}")
        return jsonify({
            "fulfillmentText": "เกิดข้อผิดพลาดในการยกเลิก กรุณาลองใหม่"
        }), 200


def handle_unknown_intent(intent):
    """Handle unknown/unhandled intents"""
    logger.warning("Unhandled intent: %s", intent)
    return jsonify({
        "fulfillmentText": (
            f"ขอโทษค่ะ บอทยังไม่รองรับคำสั่ง '{intent}' ในขณะนี้\n\n"
            f"คุณสามารถใช้ฟีเจอร์หลักได้:\n"
            f"• รายงานอาการ\n"
            f"• ประเมินความเสี่ยง\n"
            f"• นัดหมายพยาบาล\n"
            f"• ความรู้และคำแนะนำ"
        )
    }), 200
